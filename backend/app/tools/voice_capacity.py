"""
NewGenHealthAI — tools/voice_capacity.py
Process-local capacity management and per-user concurrency tracking for STT and TTS.
"""

import asyncio
from typing import Set, Optional
from fastapi import HTTPException
import logging

from app.core.config import (
    MAX_CONCURRENT_STT,
    MAX_CONCURRENT_TTS,
    VOICE_QUEUE_TIMEOUT_SECONDS,
)

logger = logging.getLogger("newgenhealthai")


class VoicePermit:
    """Resource permit that guarantees release of semaphore and per-user tracking on exit."""
    def __init__(self, manager: "VoiceCapacityManager", user_id: int, service_type: str):
        self.manager = manager
        self.user_id = user_id
        self.service_type = service_type
        self._released = False

    async def release(self):
        if self._released:
            return
        self._released = True
        await self.manager._release_permit(self.user_id, self.service_type)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()


class VoiceCapacityManager:
    """
    Process-local bounded capacity manager for STT transcriptions and TTS synthesis streams.
    Enforces per-user concurrency isolation and global queue timeouts.
    Safe against asyncio cancellation during wait or active processing.
    """
    def __init__(
        self,
        max_concurrent_stt: int = MAX_CONCURRENT_STT,
        max_concurrent_tts: int = MAX_CONCURRENT_TTS,
        queue_timeout: float = VOICE_QUEUE_TIMEOUT_SECONDS,
    ):
        self.stt_semaphore = asyncio.Semaphore(max_concurrent_stt)
        self.tts_semaphore = asyncio.Semaphore(max_concurrent_tts)
        self.queue_timeout = queue_timeout
        self._active_stt_users: Set[int] = set()
        self._active_tts_users: Set[int] = set()
        self._lock = asyncio.Lock()

    async def acquire_stt(self, user_id: int) -> VoicePermit:
        """Acquire an STT capacity permit for user_id with timeout and per-user limits."""
        async with self._lock:
            if user_id in self._active_stt_users:
                logger.warning("Voice STT concurrency violation: user %s already has active STT", user_id)
                raise HTTPException(
                    status_code=429,
                    detail="User already has an active speech-to-text request in progress. Please wait for completion.",
                )
            self._active_stt_users.add(user_id)

        acquired_semaphore = False
        try:
            try:
                await asyncio.wait_for(self.stt_semaphore.acquire(), timeout=self.queue_timeout)
                acquired_semaphore = True
            except asyncio.TimeoutError:
                logger.warning("Voice STT capacity exhausted (queue timeout %.1fs)", self.queue_timeout)
                raise HTTPException(
                    status_code=503,
                    detail="Voice transcription service is at maximum capacity. Please retry shortly.",
                )
        except BaseException:
            # Safely release semaphore and active-user reservation on cancellation or error
            if acquired_semaphore:
                self.stt_semaphore.release()
            async with self._lock:
                self._active_stt_users.discard(user_id)
            raise

        return VoicePermit(self, user_id, "stt")

    async def acquire_tts(self, user_id: int) -> VoicePermit:
        """Acquire a TTS capacity permit for user_id with timeout and per-user limits."""
        async with self._lock:
            if user_id in self._active_tts_users:
                logger.warning("Voice TTS concurrency violation: user %s already has active TTS", user_id)
                raise HTTPException(
                    status_code=429,
                    detail="User already has an active speech synthesis request in progress. Please wait for completion.",
                )
            self._active_tts_users.add(user_id)

        acquired_semaphore = False
        try:
            try:
                await asyncio.wait_for(self.tts_semaphore.acquire(), timeout=self.queue_timeout)
                acquired_semaphore = True
            except asyncio.TimeoutError:
                logger.warning("Voice TTS capacity exhausted (queue timeout %.1fs)", self.queue_timeout)
                raise HTTPException(
                    status_code=503,
                    detail="Speech synthesis service is at maximum capacity. Please retry shortly.",
                )
        except BaseException:
            # Safely release semaphore and active-user reservation on cancellation or error
            if acquired_semaphore:
                self.tts_semaphore.release()
            async with self._lock:
                self._active_tts_users.discard(user_id)
            raise

        return VoicePermit(self, user_id, "tts")

    async def _release_permit(self, user_id: int, service_type: str):
        if service_type == "stt":
            self.stt_semaphore.release()
            async with self._lock:
                self._active_stt_users.discard(user_id)
        elif service_type == "tts":
            self.tts_semaphore.release()
            async with self._lock:
                self._active_tts_users.discard(user_id)


# Global singleton instance
voice_capacity_manager = VoiceCapacityManager()
