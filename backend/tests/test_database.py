"""Tests for database service — Explicit Owner Enforcement"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import get_engine, get_session_factory  # noqa: E402
from app.services.database_service import DatabaseService  # noqa: E402

TEST_DB = "tests/test_database/test_chat.db"


@pytest.fixture(autouse=True)
def setup_teardown_db():
    """Setup and teardown test database"""
    os.makedirs(os.path.dirname(TEST_DB), exist_ok=True)
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except PermissionError:
            pass

    test_engine = get_engine(TEST_DB)
    test_session = get_session_factory(test_engine)
    test_db_service = DatabaseService(session_local=test_session, engine_instance=test_engine)
    test_db_service.init_db()

    yield test_db_service

    test_engine.dispose()
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except PermissionError:
            print(f"Warning: Could not delete {TEST_DB} - file still in use")


def test_save_and_get_message(setup_teardown_db):
    db = setup_teardown_db
    session_id = "sess_1"
    user_id = 1

    # Saving without user_id must raise ValueError (A01 enforcement)
    with pytest.raises(ValueError):
        db.save_message(session_id, "user", "Hello World", user_id=None)

    db.save_message(session_id, "user", "Hello World", user_id=user_id)
    db.save_message(session_id, "assistant", "Hi there", "AI", user_id=user_id)

    # Owner can retrieve history
    history = db.get_chat_history(session_id, user_id=user_id)
    assert history is not None
    assert len(history) == 2
    assert history[0]["content"] == "Hello World"
    assert history[1]["source"] == "AI"

    # Non-owner receives None (404 behavior, no data disclosed)
    assert db.get_chat_history(session_id, user_id=999) is None


def test_get_all_sessions(setup_teardown_db):
    db = setup_teardown_db
    user_a = 1
    user_b = 2

    db.save_message("sess_1", "user", "msg1", user_id=user_a)
    db.save_message("sess_2", "user", "msg2", user_id=user_a)
    db.save_message("sess_b", "user", "b_msg", user_id=user_b)

    sessions_a = db.get_all_sessions(user_id=user_a)
    assert len(sessions_a) == 2
    ids_a = [s["session_id"] for s in sessions_a]
    assert "sess_1" in ids_a
    assert "sess_2" in ids_a
    assert "sess_b" not in ids_a

    sessions_b = db.get_all_sessions(user_id=user_b)
    assert len(sessions_b) == 1
    assert sessions_b[0]["session_id"] == "sess_b"

    # Anonymous call returns empty list, never all sessions
    assert db.get_all_sessions(user_id=None) == []


def test_delete_session(setup_teardown_db):
    db = setup_teardown_db
    user_id = 1

    db.save_message("sess_to_del", "user", "delete me", user_id=user_id)
    assert len(db.get_chat_history("sess_to_del", user_id=user_id)) == 1

    # Other user cannot delete
    assert db.delete_session("sess_to_del", user_id=999) is False
    assert len(db.get_chat_history("sess_to_del", user_id=user_id)) == 1

    # Owner can delete
    assert db.delete_session("sess_to_del", user_id=user_id) is True
    assert db.get_chat_history("sess_to_del", user_id=user_id) is None
