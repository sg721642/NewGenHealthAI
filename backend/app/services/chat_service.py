"""
NewGenHealthAI — services/chat_service.py
ClinicalEngine: orchestrates the LangGraph agentic workflow for each chat message.
Enforces multi-user clinical memory isolation and server-side conversation ownership.
"""

from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, Optional

from app.core.logging_config import logger
from app.core.state import initialize_conversation_state, reset_query_state
from app.services.database_service import db_service


class ClinicalEngine:
    """Orchestrates the agentic medical intelligence workflow with strict owner isolation."""

    MAX_CONVERSATION_CACHE = 500

    def __init__(self):
        self.workflow_app = None
        # Memory keyed by f"{user_id}:{session_id}" to guarantee cross-user isolation
        self.conversation_states: OrderedDict[str, Dict] = OrderedDict()
        logger.info("ClinicalEngine initialized with isolated multi-user memory")

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

    async def process_message(
        self, session_id: str, message: str, user_id: int
    ) -> Dict[str, Any]:
        """
        Run the clinical pipeline for a single user message.
        Requires authenticated user_id; enforces conversation ownership.
        """
        if not user_id:
            raise ValueError("user_id is strictly required for clinical processing")

        # Verify or register conversation ownership
        conv = db_service.get_or_create_conversation(session_id, user_id)
        if not conv:
            logger.warning(
                "Security violation: user %s attempted to access session %s owned by another user",
                user_id, session_id[:8]
            )
            raise PermissionError(f"Access denied: conversation {session_id} is not owned by user {user_id}")

        logger.info("Processing message for user %s, session %s...", user_id, session_id[:8])

        if not self.workflow_app:
            raise ValueError("Workflow not initialized")

        # Persist user message under confirmed user ownership
        db_service.save_message(session_id, "user", message, user_id=user_id)

        # Retrieve or initialize user-isolated conversation state
        memory_key = self._get_memory_key(user_id, session_id)
        if memory_key not in self.conversation_states:
            # Enforce bounded in-memory cache
            if len(self.conversation_states) >= self.MAX_CONVERSATION_CACHE:
                evicted_key, _ = self.conversation_states.popitem(last=False)
                logger.debug("Evicted oldest conversation memory: %s", evicted_key)
            self.conversation_states[memory_key] = initialize_conversation_state()
        else:
            # Move to end (most recently used)
            self.conversation_states.move_to_end(memory_key)

        state = self.conversation_states[memory_key]
        state = reset_query_state(state)
        state["question"] = message

        # Run workflow
        try:
            result = await self.workflow_app.ainvoke(state)
        except AttributeError:
            logger.warning("Falling back to sync invoke")
            result = self.workflow_app.invoke(state)

        self.conversation_states[memory_key].update(result)

        response_text = result.get("generation", "Unable to generate response.")
        source = result.get("source", "Unknown")

        # Persist assistant response tagged with owner
        db_service.save_message(session_id, "assistant", response_text, source, user_id=user_id)

        response_dict = {
            "response": response_text,
            "source": source,
            "timestamp": datetime.now().strftime("%I:%M %p"),
            "success": bool(result.get("generation")),
        }

        follow_up_data = result.get("follow_up_data")
        if follow_up_data and result.get("triage_status") == "needs_info":
            response_dict["follow_up"] = follow_up_data
            logger.info("Triage follow-up included in response (round %s)",
                        follow_up_data.get("triage_round", "?"))

        return response_dict

    def clear_conversation(self, session_id: str, user_id: int) -> bool:
        """
        Reset in-memory state and clear persisted messages for an owned conversation.
        Returns False if conversation is not owned by user_id.
        """
        if not user_id or not session_id:
            return False

        conv = db_service.get_conversation(session_id, user_id)
        if not conv:
            return False

        memory_key = self._get_memory_key(user_id, session_id)
        if memory_key in self.conversation_states:
            self.conversation_states[memory_key] = initialize_conversation_state()

        # Also clear persisted messages in database
        db_service.clear_session(session_id, user_id)
        logger.info("Conversation cleared for session %s, user %s", session_id[:8], user_id)
        return True

    def delete_conversation(self, session_id: str, user_id: int) -> bool:
        """
        Evict in-memory state and delete persisted conversation and messages.
        Returns False if conversation is not owned by user_id.
        """
        if not user_id or not session_id:
            return False

        conv = db_service.get_conversation(session_id, user_id)
        if not conv:
            return False

        memory_key = self._get_memory_key(user_id, session_id)
        self.conversation_states.pop(memory_key, None)

        return db_service.delete_session(session_id, user_id)


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
