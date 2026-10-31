"""
NewGenHealthAI — api/v1/endpoints/auth.py
Authentication endpoints: /register, /login, /logout, /me.
Hardened with Argon2id rehashing, trusted reverse proxy IP resolution,
bounded sliding-window rate limiting for registration and login, and per-account lockout protection.
"""

import ipaddress
import re
import threading
import time
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.config import (
    LEGACY_PBKDF2_SALT,
    TRUSTED_PROXIES,
    RATE_LIMIT_LOGIN_PER_IP,
    RATE_LIMIT_LOGIN_PER_USER,
    RATE_LIMIT_REGISTER_PER_IP,
    RATE_LIMIT_WINDOW_SECONDS,
)
from app.core.dependencies import get_current_user
from app.core.logging_config import logger
from app.models.message import User
from app.services.database_service import db_service

router = APIRouter(prefix="/auth", tags=["Auth"])

# Regex for allowed username characters: letters, numbers, underscores, periods, hyphens
_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")


# ── Proxy Verification & Client IP Extraction (SEC-01) ───────────────────────────

def is_ip_in_trusted_proxies(ip_str: str, trusted_proxies: Optional[List[str]] = None) -> bool:
    """
    Check whether a candidate IP string falls within the trusted proxy list or CIDRs.
    Supports IPv4, IPv6, CIDR blocks, and 'testclient' for unit test environments.
    """
    if not ip_str:
        return False
    if trusted_proxies is None:
        trusted_proxies = TRUSTED_PROXIES

    clean_ip = ip_str.strip()
    if clean_ip == "testclient":
        return "testclient" in trusted_proxies or "127.0.0.1" in trusted_proxies

    try:
        ip = ipaddress.ip_address(clean_ip)
    except ValueError:
        return False

    for proxy_pattern in trusted_proxies:
        try:
            if "/" in proxy_pattern:
                net = ipaddress.ip_network(proxy_pattern, strict=False)
                if ip in net:
                    return True
            else:
                target_ip = ipaddress.ip_address(proxy_pattern.strip())
                if ip == target_ip:
                    return True
        except ValueError:
            continue

    return False


def get_client_ip(req: Optional[Request], trusted_proxies: Optional[List[str]] = None) -> str:
    """
    Securely extract client IP address.
    If the direct connecting peer (req.client.host) is NOT an explicitly trusted proxy,
    any X-Forwarded-For header is treated as spoofed and ignored; the peer IP is returned.
    If the peer is trusted, X-Forwarded-For is traversed from right to left to find
    the first untrusted IP in the proxy chain.
    """
    if req is None or not req.client or not req.client.host:
        return "unknown"

    if trusted_proxies is None:
        trusted_proxies = TRUSTED_PROXIES

    peer_ip = req.client.host.strip()

    # If the connecting peer is not in trusted_proxies, ignore any forwarded headers
    if not is_ip_in_trusted_proxies(peer_ip, trusted_proxies):
        return peer_ip

    forwarded = req.headers.get("X-Forwarded-For")
    if not forwarded:
        return peer_ip

    # Split hops from proxy chain
    hops = [h.strip() for h in forwarded.split(",") if h.strip()]
    if not hops:
        return peer_ip

    # Walk backwards from rightmost (nearest proxy hop) to leftmost
    for hop in reversed(hops):
        if not is_ip_in_trusted_proxies(hop, trusted_proxies):
            try:
                ipaddress.ip_address(hop)
                return hop
            except ValueError:
                continue

    # If all hops are trusted proxies, the earliest hop represents the client
    return hops[0]


# Backwards compatibility alias
_get_client_ip = get_client_ip


# ── Bounded Sliding-Window Rate Limiter (SEC-02) ─────────────────────────────────

class BoundedRateLimiter:
    """
    Thread-safe, memory-bounded sliding-window rate limiter with automatic TTL pruning
    and capacity capping to prevent unbounded memory growth under DDoS.

    Architectural Note:
    This rate limiter is process-local (single-instance / in-memory).
    For distributed multi-worker deployments (e.g. Uvicorn with multiple workers or Kubernetes),
    production deployments should back rate limiting with a shared cache such as Redis.
    """

    def __init__(self, max_entries: int = 10000, prune_interval_seconds: float = 60.0):
        self.max_entries = max_entries
        self.prune_interval = prune_interval_seconds
        self._lock = threading.Lock()
        self._buckets: Dict[str, List[float]] = {}
        self._last_prune = time.time()

    def _prune(self, now: float, max_window: float = 300.0) -> None:
        """Remove entries with no timestamps within max_window."""
        keys_to_remove = []
        for key, timestamps in self._buckets.items():
            valid = [t for t in timestamps if now - t < max_window]
            if valid:
                self._buckets[key] = valid
            else:
                keys_to_remove.append(key)
        for key in keys_to_remove:
            del self._buckets[key]
        self._last_prune = now

    def is_allowed(self, key: str, max_requests: int, window_seconds: float) -> bool:
        """Check if an action is allowed for the given key without recording an attempt."""
        now = time.time()
        with self._lock:
            if now - self._last_prune > self.prune_interval:
                self._prune(now, max_window=max(window_seconds, self.prune_interval))

            timestamps = self._buckets.get(key, [])
            valid = [t for t in timestamps if now - t < window_seconds]
            return len(valid) < max_requests

    def record_failure(self, key: str, window_seconds: float = 300.0) -> None:
        """Record a failed attempt under the given key."""
        now = time.time()
        with self._lock:
            if now - self._last_prune > self.prune_interval:
                self._prune(now, max_window=max(window_seconds, self.prune_interval))

            if len(self._buckets) >= self.max_entries and key not in self._buckets:
                self._prune(now, max_window=window_seconds)
                if len(self._buckets) >= self.max_entries:
                    oldest_key = next(iter(self._buckets))
                    del self._buckets[oldest_key]

            if key not in self._buckets:
                self._buckets[key] = []
            self._buckets[key].append(now)

    def check_and_record(self, key: str, max_requests: int, window_seconds: float) -> bool:
        """Check whether action is allowed; if allowed, records timestamp. Returns True if allowed."""
        now = time.time()
        with self._lock:
            if now - self._last_prune > self.prune_interval:
                self._prune(now, max_window=max(window_seconds, self.prune_interval))

            timestamps = self._buckets.get(key, [])
            valid = [t for t in timestamps if now - t < window_seconds]
            if len(valid) >= max_requests:
                self._buckets[key] = valid
                return False

            if len(self._buckets) >= self.max_entries and key not in self._buckets:
                self._prune(now, max_window=window_seconds)
                if len(self._buckets) >= self.max_entries:
                    oldest_key = next(iter(self._buckets))
                    del self._buckets[oldest_key]

            valid.append(now)
            self._buckets[key] = valid
            return True

    def clear(self, key: str) -> None:
        """Clear recorded attempts for a key upon successful action."""
        with self._lock:
            self._buckets.pop(key, None)

    def reset(self) -> None:
        """Reset all rate limiter state (useful for test isolation)."""
        with self._lock:
            self._buckets.clear()
            self._last_prune = time.time()


# Shared rate limiter instance
rate_limiter = BoundedRateLimiter(max_entries=10000, prune_interval_seconds=60.0)


# Backwards compatibility wrappers for tests
def _check_rate_limit(client_ip: str) -> bool:
    return rate_limiter.is_allowed(f"login:ip:{client_ip}", RATE_LIMIT_LOGIN_PER_IP, RATE_LIMIT_WINDOW_SECONDS)


def _record_failed_attempt(client_ip: str) -> None:
    rate_limiter.record_failure(f"login:ip:{client_ip}")


def _clear_failed_attempts(client_ip: str) -> None:
    rate_limiter.clear(f"login:ip:{client_ip}")


# ── Request / Response Models ────────────────────────────────────────────────────

class AuthRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=256)


# ── Endpoints ────────────────────────────────────────────────────────────────────

@router.post("/register")
async def register(req: AuthRequest, request: Request = None):
    """Register a new user account with strict boundaries and bounded rate limiting."""
    client_ip = get_client_ip(request) if request else "unknown"

    if client_ip != "unknown":
        if not rate_limiter.check_and_record(
            f"reg:ip:{client_ip}",
            max_requests=RATE_LIMIT_REGISTER_PER_IP,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        ):
            logger.warning("Registration rate limit exceeded for IP %s", client_ip)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many registration attempts. Please try again later.",
            )

    username_clean = req.username.strip()
    if len(username_clean) < 3 or len(username_clean) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be between 3 and 50 characters long",
        )
    if not _USERNAME_PATTERN.match(username_clean):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username may only contain letters, numbers, underscores, periods, and hyphens",
        )
    if len(req.password) < 8 or len(req.password) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be between 8 and 128 characters long",
        )

    user = db_service.create_user(username_clean, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    # Generate cryptographically secure session token
    token = db_service.create_user_session(user.id)
    return {
        "success": True,
        "token": token,
        "username": user.username,
        "user_id": user.id,
    }


@router.post("/login")
async def login(req: AuthRequest, request: Request = None):
    """Authenticate credentials, rate limit brute force, and rehash legacy passwords."""
    client_ip = get_client_ip(request) if request else "unknown"
    username_clean = req.username.strip()
    user_key = f"login:user:{username_clean.lower()}"
    ip_key = f"login:ip:{client_ip}"

    # Check IP-level rate limit
    if client_ip != "unknown" and not rate_limiter.is_allowed(
        ip_key, max_requests=RATE_LIMIT_LOGIN_PER_IP, window_seconds=RATE_LIMIT_WINDOW_SECONDS
    ):
        logger.warning("Rate limit exceeded for login attempts from IP %s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
        )

    # Check Account/Username lockout rate limit
    if not rate_limiter.is_allowed(
        user_key, max_requests=RATE_LIMIT_LOGIN_PER_USER, window_seconds=RATE_LIMIT_WINDOW_SECONDS * 2
    ):
        logger.warning("Account lockout rate limit exceeded for user %s", username_clean)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts for this account. Please try again later.",
        )

    user = db_service.get_user_by_username(username_clean)
    if not user:
        if client_ip != "unknown":
            rate_limiter.record_failure(ip_key)
        rate_limiter.record_failure(user_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Verify password (supports both Argon2id and legacy PBKDF2 with migration salt)
    verification = user.verify_password(req.password, legacy_salt=LEGACY_PBKDF2_SALT)
    if not verification.is_valid:
        if client_ip != "unknown":
            rate_limiter.record_failure(ip_key)
        rate_limiter.record_failure(user_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Authentication succeeded: clear rate limit counter
    if client_ip != "unknown":
        rate_limiter.clear(ip_key)
    rate_limiter.clear(user_key)

    # Automatic safe credential migration to Argon2id
    if verification.needs_rehash and verification.new_hash:
        success = db_service.update_user_password_hash(
            user.id, verification.new_hash, expected_old_hash=user.hashed_password
        )
        if success:
            logger.info("Successfully rehashed credentials to Argon2id for user %d", user.id)

    token = db_service.create_user_session(user.id)
    return {
        "success": True,
        "token": token,
        "username": user.username,
        "user_id": user.id,
    }


@router.post("/logout")
async def logout(req: Request):
    """Invalidate active session token."""
    auth_header = req.headers.get("Authorization")
    if auth_header and auth_header.strip().lower().startswith("bearer "):
        token = auth_header.strip().split(" ", 1)[1].strip()
        db_service.delete_user_session(token)
    return {"success": True, "message": "Logged out successfully"}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve details for active authenticated user."""
    return {
        "success": True,
        "username": current_user.username,
        "user_id": current_user.id,
    }
