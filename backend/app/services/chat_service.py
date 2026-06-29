"""
NewGenHealthAI — services/chat_service.py
ClinicalEngine: orchestrates the LangGraph agentic workflow for each chat message.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from app.core.langgraph_workflow import create_workflow
from app.core.logging_config import logger
from app.core.state import initialize_conversation_state, reset_query_state
from app.services.database_service import db_service


class ClinicalEngine:
    """Orchestrates the agentic medical intelligence workflow."""

    def __init__(self):
        self.workflow_app = None
        self.conversation_states: Dict[str, Dict] = {}
        logger.info("ClinicalEngine initialized")

    def initialize_workflow(self) -> None:
        """Compile and cache the LangGraph workflow (called once at startup)."""
        if not self.workflow_app:
            logger.info("Initializing Clinical Intelligence workflow...")
            self.workflow_app = create_workflow()
            logger.info("Clinical Intelligence workflow ready")

    async def process_message(
        self, session_id: str, message: str, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Run the clinical pipeline for a single user message."""
        logger.info("Processing message for session %s...", session_id[:8])

        if not self.workflow_app:
            raise ValueError("Workflow not initialized")

        # Persist user message (tagged with user_id for isolation)
        db_service.save_message(session_id, "user", message, user_id=user_id)

        # Initialize or retrieve conversation state
        if session_id not in self.conversation_states:
            self.conversation_states[session_id] = initialize_conversation_state()

        state = self.conversation_states[session_id]
        state = reset_query_state(state)
        state["question"] = message

        # Run workflow (async preferred, sync fallback)
        try:
            result = await self.workflow_app.ainvoke(state)
        except AttributeError:
            logger.warning("Falling back to sync invoke")
            result = self.workflow_app.invoke(state)

        self.conversation_states[session_id].update(result)

        response_text = result.get("generation", "Unable to generate response.")
        source = result.get("source", "Unknown")

        # Persist assistant response (tagged with user_id for isolation)
        db_service.save_message(session_id, "assistant", response_text, source, user_id=user_id)

        # Build response — include follow-up data if triage is asking questions
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

    def clear_conversation(self, session_id: str) -> None:
        """Reset the in-memory conversation state for a session."""
        if session_id in self.conversation_states:
            self.conversation_states[session_id] = initialize_conversation_state()
            logger.info("Conversation cleared for session %s", session_id[:8])


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


