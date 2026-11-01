"""
NewGenHealthAI — services/chat_service.py
ClinicalEngine: orchestrates the LangGraph agentic workflow for each chat message.
Enforces multi-user clinical memory isolation, server-side conversation ownership,
bounded per-conversation asyncio locking with guaranteed release, state rehydration
from persisted history, and clear/delete race guards.

Result-State Taxonomy (internal, not transmitted verbatim):
  SUCCESSFUL_EDUCATIONAL   — provider returned a usable educational response
  SUCCESSFUL_URGENT        — deterministic urgent-care advisory delivered
  CLARIFICATION_QUESTION   — triage follow-up question returned
  INCONCLUSIVE             — providers returned content insufficient for response
  PROVIDER_UNAVAILABLE     — all configured providers offline / not configured
  PROVIDER_TIMEOUT         — overall consultation deadline expired
  INTERNAL_ERROR           — unexpected exception during workflow execution
"""

import asyncio
import os
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from app.core.logging_config import logger
from app.core.state import AgentState, initialize_conversation_state, reset_query_state
from app.services.database_service import db_service

# ── Timeout Configuration ────────────────────────────────────────────────────
# Overall per-consultation wall-clock deadline (seconds).
# Individual provider HTTP timeouts are managed by the provider SDK layers.
# Overridable via CONSULTATION_TIMEOUT_SECONDS env var.
CONSULTATION_TIMEOUT_SECONDS: float = float(
    os.getenv("CONSULTATION_TIMEOUT_SECONDS", "90")
)


class ConversationLockManager:
    """
    Bounded, reference-counted asyncio.Lock manager for per-conversation serialization.
    Guarantees that active operations on the same conversation are strictly serialized
    while different conversations proceed concurrently without unbounded lock leaks.

    Architectural Note:
    This lock manager provides single-process ASGI event-loop synchronization.
    For multi-worker deployments, cross-worker safety requires sticky session routing
    or a distributed lock coordinator (e.g. Redis Redlock).
    """

    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._ref_counts: Dict[str, int] = {}
        self._mutex = asyncio.Lock()

    def lock(self, key: str) -> "_LockContext":
        return _LockContext(self, key)


class _LockContext:
    def __init__(self, manager: ConversationLockManager, key: str):
        self.manager = manager
        self.key = key
        self.lock: Optional[asyncio.Lock] = None

    async def __aenter__(self):
        async with self.manager._mutex:
            if self.key not in self.manager._locks:
                self.manager._locks[self.key] = asyncio.Lock()
                self.manager._ref_counts[self.key] = 0
            self.manager._ref_counts[self.key] += 1
            self.lock = self.manager._locks[self.key]

        acquired = False
        try:
            await self.lock.acquire()
            acquired = True
            return self
        except BaseException:
            # Cancellation or exception during acquire: clean up ref count and lock
            if acquired and self.lock and self.lock.locked():
                self.lock.release()
            async with self.manager._mutex:
                if self.key in self.manager._ref_counts:
                    self.manager._ref_counts[self.key] -= 1
                    if self.manager._ref_counts[self.key] <= 0:
                        self.manager._locks.pop(self.key, None)
                        self.manager._ref_counts.pop(self.key, None)
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.lock and self.lock.locked():
                self.lock.release()
        finally:
            async with self.manager._mutex:
                if self.key in self.manager._ref_counts:
                    self.manager._ref_counts[self.key] -= 1
                    if self.manager._ref_counts[self.key] <= 0:
                        self.manager._locks.pop(self.key, None)
                        self.manager._ref_counts.pop(self.key, None)


class ClinicalEngine:
    """Orchestrates the agentic medical intelligence workflow with strict owner isolation and concurrency safety."""

    MAX_CONVERSATION_CACHE = 500
    MAX_RESTORE_TURNS = 20

    def __init__(self):
        self.workflow_app = None
        # Memory keyed by f"{user_id}:{session_id}" to guarantee cross-user isolation
        self.conversation_states: OrderedDict[str, Dict] = OrderedDict()
        self.lock_manager = ConversationLockManager()
        self._versions: Dict[str, int] = {}
        self._deleted_sessions: Set[str] = set()
        logger.info("ClinicalEngine initialized with isolated multi-user memory and per-conversation locks")

    def initialize_workflow(self) -> None:
        """Compile and cache the LangGraph workflow (lazy-loaded)."""
        if not self.workflow_app:
            logger.info("Initializing Clinical Intelligence workflow...")
            try:
                from app.core.langgraph_workflow import create_workflow
                self.workflow_app = create_workflow()
                logger.info("Clinical Intelligence workflow ready")
            except Exception as e:
                logger.error("Failed to compile LangGraph workflow: %s", e)
                raise

    def _get_memory_key(self, user_id: int, session_id: str) -> str:
        """Construct secure user-scoped memory key."""
        return f"{user_id}:{session_id}"

    def _get_version(self, memory_key: str) -> int:
        return self._versions.get(memory_key, 1)

    def _bump_version(self, memory_key: str) -> int:
        new_v = self._versions.get(memory_key, 1) + 1
        self._versions[memory_key] = new_v
        return new_v

    def _mark_deleted(self, memory_key: str) -> None:
        self._deleted_sessions.add(memory_key)
        self._bump_version(memory_key)

    def _is_deleted(self, memory_key: str) -> bool:
        return memory_key in self._deleted_sessions

    def _get_or_restore_state(self, session_id: str, user_id: int) -> AgentState:
        """
        Retrieve existing in-memory state or safely rehydrate from authorized persisted history.
        Restores up to MAX_RESTORE_TURNS (20) turns in chronological order,
        excluding failed/incomplete assistant responses.
        Derived clinical triage state is cleanly initialized without fabricating decisions.
        """
        memory_key = self._get_memory_key(user_id, session_id)

        if memory_key in self.conversation_states:
            self.conversation_states.move_to_end(memory_key)
            return self.conversation_states[memory_key]

        # Enforce bounded cache size
        if len(self.conversation_states) >= self.MAX_CONVERSATION_CACHE:
            evicted_key, _ = self.conversation_states.popitem(last=False)
            logger.debug("Evicted oldest conversation memory: %s", evicted_key)

        state = initialize_conversation_state()

        # Rehydrate from authorized database records
        messages = db_service.get_chat_history(session_id, user_id=user_id)
        if messages:
            valid_history = []
            for msg in messages:
                content = (msg.get("content") or "").strip()
                role = msg.get("role", "")
                if not content:
                    continue
                # Exclude failed or error responses from rehydrated context
                if role == "assistant" and (
                    "Unable to generate response" in content
                    or "Sorry, I encountered an error" in content
                    or "Connection error" in content
                    or "temporarily unavailable" in content.lower()
                    or "service is currently unable" in content.lower()
                ):
                    continue
                valid_history.append({"role": role, "content": content})

            # Bound history to last MAX_RESTORE_TURNS
            if len(valid_history) > self.MAX_RESTORE_TURNS:
                valid_history = valid_history[-self.MAX_RESTORE_TURNS:]

            state["conversation_history"] = valid_history
            logger.info("Rehydrated %d history turns for session %s, user %s", len(valid_history), session_id[:8], user_id)

        self.conversation_states[memory_key] = state
        return state

    async def process_message(
        self, session_id: str, message: str, user_id: int
    ) -> Dict[str, Any]:
        """
        Run the clinical pipeline for a single user message.
        Requires authenticated user_id; enforces conversation ownership,
        per-conversation serialization, and clear/delete race guards.
        """
        if not user_id:
            raise ValueError("user_id is strictly required for clinical processing")
        if not session_id:
            raise ValueError("session_id is strictly required for clinical processing")
        if not message or not message.strip():
            raise ValueError("Message cannot be empty or whitespace only")
        if len(message) > 4000:
            raise ValueError("Message exceeds maximum permitted length of 4000 characters")

        memory_key = self._get_memory_key(user_id, session_id)

        async with self.lock_manager.lock(memory_key):
            # 1. Guard against deleted conversations
            if self._is_deleted(memory_key):
                raise PermissionError(f"Access denied: conversation {session_id} is deleted")

            # 2. Verify conversation ownership and non-quarantine status
            conv = db_service.get_conversation(session_id, user_id)
            if not conv and hasattr(db_service, "get_or_create_conversation"):
                conv = db_service.get_or_create_conversation(session_id, user_id)

            if not conv:
                logger.warning(
                    "Security violation: user %s attempted to access session %s owned by another user",
                    user_id, session_id[:8]
                )
                raise PermissionError(f"Access denied: conversation {session_id} is not owned by user {user_id}")

            if not self.workflow_app:
                raise ValueError("Workflow not initialized")

            # 3. Snapshot generation version to detect concurrent clear/delete
            version_start = self._get_version(memory_key)

            # 4. Retrieve or rehydrate conversation state from prior turns
            state = self._get_or_restore_state(session_id, user_id)
            state = reset_query_state(state)
            state["question"] = message.strip()

            # 5. Persist user message under confirmed user ownership
            db_service.save_message(session_id, "user", message.strip(), user_id=user_id)

            # 6. Run workflow with bounded wall-clock deadline
            result: Dict[str, Any] = {}
            _timeout = CONSULTATION_TIMEOUT_SECONDS
            try:
                async def _run_workflow() -> Dict[str, Any]:
                    if hasattr(self.workflow_app, "ainvoke"):
                        raw_res = self.workflow_app.ainvoke(state)
                        if hasattr(raw_res, "__await__"):
                            return await raw_res
                        return raw_res
                    return self.workflow_app.invoke(state)

                try:
                    result = await asyncio.wait_for(_run_workflow(), timeout=_timeout)
                except AttributeError:
                    # Sync-only workflow fallback (LangGraph older versions)
                    logger.warning("ClinicalEngine: falling back to sync invoke (session=%s)", session_id[:8])
                    result = self.workflow_app.invoke(state)

            except asyncio.TimeoutError:
                # Deadline expired — lock is released by _LockContext.__aexit__ automatically.
                logger.warning(
                    "ClinicalEngine: consultation deadline expired after %.0fs (session=%s, result_state=PROVIDER_TIMEOUT)",
                    _timeout, session_id[:8],
                )
                # Return a timeout service-unavailable response; do not persist as successful clinical turn.
                timeout_text = (
                    "Our health information service took too long to respond. "
                    "If you are experiencing concerning symptoms, please consult your "
                    "healthcare provider, local clinic, or emergency services directly."
                )
                return {
                    "response": timeout_text,
                    "source": "Service Unavailable",
                    "timestamp": datetime.now().strftime("%I:%M %p"),
                    "success": False,
                    "result_state": "PROVIDER_TIMEOUT",
                }
            except Exception as e:
                # Redact exception message — may contain prompt content or credentials.
                logger.error(
                    "ClinicalEngine: workflow error (session=%s, result_state=INTERNAL_ERROR): %s",
                    session_id[:8], type(e).__name__,
                )
                raise

            # 7. Post-invocation race check: verify conversation was not cleared or deleted during processing
            version_current = self._get_version(memory_key)
            if self._is_deleted(memory_key) or version_current != version_start:
                logger.warning(
                    "ClinicalEngine: conversation cleared/deleted during processing (session=%s, v%d→v%d); discarding in-flight response",
                    session_id[:8], version_start, version_current,
                )
                raise RuntimeError(f"Conversation {session_id} was cleared or deleted during processing")

            # Verify conversation still exists in database
            conv_after = db_service.get_conversation(session_id, user_id)
            if not conv_after and hasattr(db_service, "get_or_create_conversation"):
                conv_after = db_service.get_or_create_conversation(session_id, user_id)

            if not conv_after:
                logger.warning(
                    "ClinicalEngine: conversation removed from DB during processing (session=%s); discarding response",
                    session_id[:8],
                )
                raise RuntimeError(f"Conversation {session_id} no longer exists")

            # 8. Update in-memory state
            self.conversation_states[memory_key].update(result)

            is_failed = bool(
                result.get("is_failed_generation")
                or result.get("source") == "Service Unavailable"
                or not result.get("generation")
            )
            response_text = result.get(
                "generation",
                "Our health information service is temporarily unavailable. If you are experiencing concerning symptoms, please contact your healthcare provider or local clinic directly.",
            )
            source = result.get("source", "Unknown")

            # Determine result_state for consistent HTTP/DB/frontend alignment
            if result.get("is_urgent"):
                result_state = "SUCCESSFUL_URGENT"
            elif result.get("triage_status") == "needs_info":
                result_state = "CLARIFICATION_QUESTION"
            elif is_failed and source == "Service Unavailable":
                result_state = "PROVIDER_UNAVAILABLE"
            elif is_failed:
                result_state = "INCONCLUSIVE"
            else:
                result_state = "SUCCESSFUL_EDUCATIONAL"

            if not is_failed:
                # Persist assistant response tagged with owner only on genuine success
                db_service.save_message(session_id, "assistant", response_text, source, user_id=user_id)
                success = True
                logger.info(
                    "ClinicalEngine: response persisted (session=%s, result_state=%s, source_category=%s)",
                    session_id[:8], result_state, source,
                )
            else:
                # Do NOT persist service-unavailable or failed responses as valid clinical turns
                logger.warning(
                    "ClinicalEngine: generation not persisted (session=%s, result_state=%s)",
                    session_id[:8], result_state,
                )
                success = False

            response_dict: Dict[str, Any] = {
                "response": response_text,
                "source": source,
                "timestamp": datetime.now().strftime("%I:%M %p"),
                "success": success,
                "result_state": result_state,
            }

            follow_up_data = result.get("follow_up_data")
            if follow_up_data and result.get("triage_status") == "needs_info":
                response_dict["follow_up"] = follow_up_data
                logger.info(
                    "ClinicalEngine: triage follow-up included (session=%s, round=%s)",
                    session_id[:8], follow_up_data.get("triage_round", "?"),
                )

            return response_dict


    def clear_conversation(self, session_id: str, user_id: int) -> bool:
        """
        Reset in-memory state and clear persisted messages for an owned conversation.
        Increments conversation version to invalidate any in-flight assistant generation.
        Returns False if conversation is not owned by user_id.
        """
        if not user_id or not session_id:
            return False

        conv = db_service.get_conversation(session_id, user_id)
        if not conv:
            return False

        memory_key = self._get_memory_key(user_id, session_id)
        self._bump_version(memory_key)

        if memory_key in self.conversation_states:
            self.conversation_states[memory_key] = initialize_conversation_state()

        # Clear persisted messages in database
        db_service.clear_session(session_id, user_id)
        logger.info("Conversation cleared for session %s, user %s", session_id[:8], user_id)
        return True

    async def async_clear_conversation(self, session_id: str, user_id: int) -> bool:
        """Async variant of clear_conversation that synchronizes on conversation lock."""
        memory_key = self._get_memory_key(user_id, session_id)
        async with self.lock_manager.lock(memory_key):
            return self.clear_conversation(session_id, user_id)

    def delete_conversation(self, session_id: str, user_id: int) -> bool:
        """
        Evict in-memory state and delete persisted conversation and messages.
        Marks conversation deleted to prevent in-flight restorations or resurrection.
        Returns False if conversation is not owned by user_id.
        """
        if not user_id or not session_id:
            return False

        conv = db_service.get_conversation(session_id, user_id)
        if not conv:
            return False

        memory_key = self._get_memory_key(user_id, session_id)
        self._mark_deleted(memory_key)
        self.conversation_states.pop(memory_key, None)

        return db_service.delete_session(session_id, user_id)

    async def async_delete_conversation(self, session_id: str, user_id: int) -> bool:
        """Async variant of delete_conversation that synchronizes on conversation lock."""
        memory_key = self._get_memory_key(user_id, session_id)
        async with self.lock_manager.lock(memory_key):
            return self.delete_conversation(session_id, user_id)


# Module-level singleton
clinical_engine = ClinicalEngine()

# Backwards-compatibility alias used by tests
ChatService = ClinicalEngine


def __getattr__(name: str) -> Any:
    """Forward module attribute lookups to the clinical_engine singleton."""
    if hasattr(clinical_engine, name):
        return getattr(clinical_engine, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __setattr__(name: str, value: Any) -> None:
    """Forward module attribute sets to the clinical_engine singleton."""
    if hasattr(clinical_engine, name) or name in ("workflow_app", "initialize_workflow"):
        setattr(clinical_engine, name, value)
    else:
        globals()[name] = value
