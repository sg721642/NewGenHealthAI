"""Tests for services — Deep Modular Architecture"""
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import get_engine, get_session_factory  # noqa: E402
from app.services.chat_service import ChatService  # noqa: E402
from app.services.database_service import DatabaseService  # noqa: E402


class TestChatService:
    """Tests for ChatService (ClinicalEngine)"""

    def test_chat_service_initialization(self):
        service = ChatService()
        assert service.workflow_app is None
        assert service.conversation_states == {}

    def test_initialize_workflow(self):
        service = ChatService()
        with patch('app.core.langgraph_workflow.create_workflow') as mock_create:
            mock_create.return_value = MagicMock()
            service.initialize_workflow()
            assert service.workflow_app is not None
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_success(self):
        service = ChatService()
        service.workflow_app = MagicMock()
        service.workflow_app.ainvoke = AsyncMock(return_value={
            "generation": "Test response",
            "source": "Test Source",
            "llm_success": True
        })
        from app.services import db_service
        with patch.object(db_service, 'get_or_create_conversation', return_value=MagicMock()), \
             patch.object(db_service, 'save_message'):
            result = await service.process_message("test-session", "Hello", user_id=1)
            assert result["success"] is True
            assert result["response"] == "Test response"
            assert result["source"] == "Test Source"

    @pytest.mark.asyncio
    async def test_process_message_no_workflow(self):
        service = ChatService()
        from app.services import db_service
        with patch.object(db_service, 'get_or_create_conversation', return_value=MagicMock()):
            with pytest.raises(ValueError, match="Workflow not initialized"):
                await service.process_message("test-session", "Hello", user_id=1)

    @pytest.mark.asyncio
    async def test_process_message_fallback_sync(self):
        service = ChatService()
        service.workflow_app = MagicMock()
        service.workflow_app.ainvoke = AsyncMock(side_effect=AttributeError)
        service.workflow_app.invoke = MagicMock(return_value={
            "generation": "Sync response",
            "source": "Sync Source",
            "llm_success": True
        })
        from app.services import db_service
        with patch.object(db_service, 'get_or_create_conversation', return_value=MagicMock()), \
             patch.object(db_service, 'save_message'):
            result = await service.process_message("test-session", "Hello", user_id=1)
            assert result["success"] is True
            assert result["response"] == "Sync response"

    def test_clear_conversation(self):
        service = ChatService()
        service.conversation_states["1:test-session"] = {"question": "old"}
        from app.services import db_service
        with patch.object(db_service, 'get_conversation', return_value=MagicMock()), \
             patch.object(db_service, 'clear_session', return_value=True):
            res = service.clear_conversation("test-session", user_id=1)
            assert res is True
            assert service.conversation_states["1:test-session"]["question"] == ""

    def test_clear_conversation_nonexistent(self):
        service = ChatService()
        res = service.clear_conversation("nonexistent", user_id=1)  # Returns False
        assert res is False



class TestDatabaseService:
    """Tests for DatabaseService"""

    def test_database_service_initialization(self, tmp_path):
        test_db = str(tmp_path / "test_init.db")
        test_engine = get_engine(test_db)
        test_session = get_session_factory(test_engine)
        service = DatabaseService(session_local=test_session, engine_instance=test_engine)
        service.init_db()
        assert os.path.exists(test_db)
        test_engine.dispose()

    def test_save_and_retrieve_message(self, tmp_path):
        test_db = str(tmp_path / "test_save.db")
        test_engine = get_engine(test_db)
        test_session = get_session_factory(test_engine)
        service = DatabaseService(session_local=test_session, engine_instance=test_engine)
        service.init_db()
        user = service.create_user("alice", "Password123!")
        assert user is not None
        service.create_conversation(user_id=user.id, session_id="sess1")
        service.save_message("sess1", "user", "Hello", None, user_id=user.id)
        service.save_message("sess1", "assistant", "Hi there", "AI", user_id=user.id)

        history = service.get_chat_history("sess1", user_id=user.id)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["content"] == "Hi there"
        test_engine.dispose()

    def test_get_all_sessions(self, tmp_path):
        test_db = str(tmp_path / "test_sessions.db")
        test_engine = get_engine(test_db)
        test_session = get_session_factory(test_engine)
        service = DatabaseService(session_local=test_session, engine_instance=test_engine)
        service.init_db()
        user = service.create_user("bob", "Password123!")
        assert user is not None
        service.create_conversation(user_id=user.id, session_id="sess1")
        service.create_conversation(user_id=user.id, session_id="sess2")
        service.save_message("sess1", "user", "Message 1", user_id=user.id)
        service.save_message("sess2", "user", "Message 2", user_id=user.id)

        sessions = service.get_all_sessions(user_id=user.id)
        assert len(sessions) >= 2
        session_ids = [s["session_id"] for s in sessions]
        assert "sess1" in session_ids
        assert "sess2" in session_ids
        test_engine.dispose()

    def test_delete_session(self, tmp_path):
        test_db = str(tmp_path / "test_delete.db")
        test_engine = get_engine(test_db)
        test_session = get_session_factory(test_engine)
        service = DatabaseService(session_local=test_session, engine_instance=test_engine)
        service.init_db()
        user = service.create_user("carol", "Password123!")
        assert user is not None
        service.create_conversation(user_id=user.id, session_id="sess_del")
        service.save_message("sess_del", "user", "Delete me", user_id=user.id)
        assert len(service.get_chat_history("sess_del", user_id=user.id)) == 1

        service.delete_session("sess_del", user_id=user.id)
        assert service.get_chat_history("sess_del", user_id=user.id) is None
        test_engine.dispose()



