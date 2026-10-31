"""
NewGenHealthAI — Phase 1D Regression Tests
Exhaustive verification of conversation memory isolation, per-conversation serialization,
clear/delete race protection, context rehydration after restart/eviction, rate-limiter
capacity flooding without active lockout eviction, and step-wise migration recovery.
"""

import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.auth import BoundedRateLimiter
from app.core.state import initialize_conversation_state
from app.db.migrations import CURRENT_SCHEMA_VERSION, run_database_migration
from app.models.message import Base, Conversation, Message, User
from app.services.chat_service import ClinicalEngine, ConversationLockManager
from app.services.database_service import DatabaseService


@pytest.fixture
def temp_db(tmp_path):
    """Isolated SQLite database with schema v2 for each test."""
    db_file = str(tmp_path / "test_phase1d.db")
    engine = create_engine(f"sqlite:///{db_file}")
    run_database_migration(engine, db_path=db_file)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_svc = DatabaseService(session_local=TestingSession, engine_instance=engine)
    return db_svc, engine, db_file


@pytest.mark.asyncio
async def test_two_simultaneous_turns_in_one_conversation(temp_db):
    """
    Two turns submitted simultaneously to the same conversation must be serialized:
    Order must be preserved, state not overwritten, and both user & assistant messages persisted.
    """
    db_svc, engine, _ = temp_db
    user = db_svc.create_user("alice", "Password123!")
    conv = db_svc.create_conversation(user_id=user.id)
    session_id = conv.id

    engine_instance = ClinicalEngine()

    execution_order = []

    async def mock_ainvoke(state):
        q = state["question"]
        execution_order.append(f"start:{q}")
        await asyncio.sleep(0.05)  # Simulate LLM inference latency
        execution_order.append(f"end:{q}")
        return {
            "generation": f"Response to {q}",
            "source": "MockProvider",
        }

    mock_app = MagicMock()
    mock_app.ainvoke = mock_ainvoke
    engine_instance.workflow_app = mock_app

    with patch("app.services.chat_service.db_service", db_svc):
        task1 = asyncio.create_task(
            engine_instance.process_message(session_id, "Turn 1", user_id=user.id)
        )
        task2 = asyncio.create_task(
            engine_instance.process_message(session_id, "Turn 2", user_id=user.id)
        )

        res1, res2 = await asyncio.gather(task1, task2)

    assert res1["success"] is True
    assert res2["success"] is True

    # Assert strict serialization (Turn 1 completes before Turn 2 begins)
    assert execution_order == ["start:Turn 1", "end:Turn 1", "start:Turn 2", "end:Turn 2"]

    # Assert persisted database contents
    history = db_svc.get_chat_history(session_id, user_id=user.id)
    assert len(history) == 4
    assert [m["content"] for m in history] == [
        "Turn 1", "Response to Turn 1", "Turn 2", "Response to Turn 2"
    ]


@pytest.mark.asyncio
async def test_concurrent_turns_in_different_conversations(temp_db):
    """
    Concurrent turns in different conversations must execute in parallel without cross-talk.
    """
    db_svc, _, _ = temp_db
    user = db_svc.create_user("bob", "Password123!")
    conv_a = db_svc.create_conversation(user_id=user.id)
    conv_b = db_svc.create_conversation(user_id=user.id)

    engine_instance = ClinicalEngine()

    barrier = asyncio.Barrier(2)
    concurrently_active = False

    async def mock_ainvoke(state):
        nonlocal concurrently_active
        q = state["question"]
        # Both tasks must hit barrier together, proving parallel execution
        await barrier.wait()
        concurrently_active = True
        return {
            "generation": f"Diagnosis for {q}",
            "source": "MockProvider",
        }

    mock_app = MagicMock()
    mock_app.ainvoke = mock_ainvoke
    engine_instance.workflow_app = mock_app

    with patch("app.services.chat_service.db_service", db_svc):
        task_a = asyncio.create_task(
            engine_instance.process_message(conv_a.id, "Conv A Query", user_id=user.id)
        )
        task_b = asyncio.create_task(
            engine_instance.process_message(conv_b.id, "Conv B Query", user_id=user.id)
        )

        res_a, res_b = await asyncio.gather(task_a, task_b)

    assert concurrently_active is True
    assert res_a["response"] == "Diagnosis for Conv A Query"
    assert res_b["response"] == "Diagnosis for Conv B Query"

    # Contexts must remain completely isolated in DB
    hist_a = db_svc.get_chat_history(conv_a.id, user_id=user.id)
    hist_b = db_svc.get_chat_history(conv_b.id, user_id=user.id)
    assert [m["content"] for m in hist_a] == ["Conv A Query", "Diagnosis for Conv A Query"]
    assert [m["content"] for m in hist_b] == ["Conv B Query", "Diagnosis for Conv B Query"]


@pytest.mark.asyncio
async def test_clear_during_in_flight_processing(temp_db):
    """
    If a conversation is cleared while an AI workflow is processing,
    the in-flight generation must be discarded: No assistant response restored,
    and both database and in-memory cache remain empty.
    """
    db_svc, _, _ = temp_db
    user = db_svc.create_user("carol", "Password123!")
    conv = db_svc.create_conversation(user_id=user.id)
    session_id = conv.id

    engine_instance = ClinicalEngine()

    ai_started = asyncio.Event()
    clear_finished = asyncio.Event()

    async def mock_ainvoke(state):
        ai_started.set()
        # Wait until clear has been executed
        await clear_finished.wait()
        return {
            "generation": "Stale In-Flight Diagnosis",
            "source": "MockProvider",
        }

    mock_app = MagicMock()
    mock_app.ainvoke = mock_ainvoke
    engine_instance.workflow_app = mock_app

    with patch("app.services.chat_service.db_service", db_svc):
        # Start in-flight message processing
        process_task = asyncio.create_task(
            engine_instance.process_message(session_id, "In flight message", user_id=user.id)
        )

        await ai_started.wait()

        # Clear conversation while AI workflow is in flight
        cleared = engine_instance.clear_conversation(session_id, user_id=user.id)
        assert cleared is True
        clear_finished.set()

        # Process message must detect clear collision and raise RuntimeError
        with pytest.raises(RuntimeError, match="cleared or deleted"):
            await process_task

    # Database must have ZERO messages (clear wiped user message, assistant turn was discarded)
    history = db_svc.get_chat_history(session_id, user_id=user.id)
    assert history == []

    # In-memory cache must be empty (reset)
    memory_key = engine_instance._get_memory_key(user.id, session_id)
    state = engine_instance.conversation_states.get(memory_key)
    assert state is not None
    assert state.get("conversation_history") == []


@pytest.mark.asyncio
async def test_delete_during_in_flight_processing(temp_db):
    """
    If a conversation is deleted while an AI workflow is in flight,
    the in-flight response must be discarded: Conversation cannot be resurrected in DB or cache.
    """
    db_svc, _, _ = temp_db
    user = db_svc.create_user("dave", "Password123!")
    conv = db_svc.create_conversation(user_id=user.id)
    session_id = conv.id

    engine_instance = ClinicalEngine()

    ai_started = asyncio.Event()
    delete_finished = asyncio.Event()

    async def mock_ainvoke(state):
        ai_started.set()
        await delete_finished.wait()
        return {
            "generation": "Zombie Diagnosis",
            "source": "MockProvider",
        }

    mock_app = MagicMock()
    mock_app.ainvoke = mock_ainvoke
    engine_instance.workflow_app = mock_app

    with patch("app.services.chat_service.db_service", db_svc):
        process_task = asyncio.create_task(
            engine_instance.process_message(session_id, "Query to be deleted", user_id=user.id)
        )

        await ai_started.wait()

        deleted = engine_instance.delete_conversation(session_id, user_id=user.id)
        assert deleted is True
        delete_finished.set()

        with pytest.raises(RuntimeError, match="cleared or deleted|no longer exists"):
            await process_task

    # Assert conversation does not exist in DB
    assert db_svc.get_conversation(session_id, user_id=user.id) is None
    assert db_svc.get_chat_history(session_id, user_id=user.id) is None

    # Assert memory is evicted
    memory_key = engine_instance._get_memory_key(user.id, session_id)
    assert memory_key not in engine_instance.conversation_states


@pytest.mark.asyncio
async def test_request_cancellation_and_lock_release():
    """
    Cancelling a request holding a lock must release the lock and clean up reference count,
    allowing subsequent operations to acquire the lock without deadlocking.
    """
    lock_mgr = ConversationLockManager()
    key = "1:session-cancel"

    started = asyncio.Event()

    async def long_running():
        async with lock_mgr.lock(key):
            started.set()
            await asyncio.sleep(10.0)

    task = asyncio.create_task(long_running())
    await started.wait()

    # Cancel task
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Lock manager must have evicted lock and ref count
    assert key not in lock_mgr._locks
    assert key not in lock_mgr._ref_counts

    # Subsequent task must acquire lock without blocking
    acquired = False
    async with lock_mgr.lock(key):
        acquired = True

    assert acquired is True
    assert key not in lock_mgr._locks


@pytest.mark.asyncio
async def test_provider_exception_while_holding_lock(temp_db):
    """
    If provider raises an exception:
    1. Lock must be released cleanly.
    2. No fabricated medical response is returned.
    3. Subsequent requests can proceed without deadlock.
    """
    db_svc, _, _ = temp_db
    user = db_svc.create_user("eve", "Password123!")
    conv = db_svc.create_conversation(user_id=user.id)
    session_id = conv.id

    engine_instance = ClinicalEngine()

    call_count = 0

    async def mock_ainvoke(state):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("Upstream AI Provider Unavailable")
        return {"generation": "Recovered Diagnosis", "source": "LLM"}

    mock_app = MagicMock()
    mock_app.ainvoke = mock_ainvoke
    engine_instance.workflow_app = mock_app

    with patch("app.services.chat_service.db_service", db_svc):
        # 1st attempt fails with provider exception
        with pytest.raises(ConnectionError, match="Upstream AI Provider Unavailable"):
            await engine_instance.process_message(session_id, "Attempt 1", user_id=user.id)

        # 2nd attempt succeeds without deadlock
        res = await engine_instance.process_message(session_id, "Attempt 2", user_id=user.id)
        assert res["success"] is True
        assert res["response"] == "Recovered Diagnosis"

    # Lock must be released and cleaned up
    memory_key = engine_instance._get_memory_key(user.id, session_id)
    assert memory_key not in engine_instance.lock_manager._locks


@pytest.mark.asyncio
async def test_history_reconstruction_after_simulated_restart(temp_db):
    """
    After backend reload/restart (new ClinicalEngine with empty RAM cache),
    persisted messages must be restored into conversation_history in chronological order.
    """
    db_svc, _, _ = temp_db
    user = db_svc.create_user("frank", "Password123!")
    conv = db_svc.create_conversation(user_id=user.id)
    session_id = conv.id

    # Populate 3 historical turns in database
    db_svc.save_message(session_id, "user", "I have a cough", user_id=user.id)
    db_svc.save_message(session_id, "assistant", "How long have you had it?", source="LLM", user_id=user.id)
    db_svc.save_message(session_id, "user", "About 3 days", user_id=user.id)
    db_svc.save_message(session_id, "assistant", "Any fever?", source="LLM", user_id=user.id)

    # Simulate fresh backend instance
    fresh_engine = ClinicalEngine()
    assert len(fresh_engine.conversation_states) == 0

    captured_history = None

    async def mock_ainvoke(state):
        nonlocal captured_history
        captured_history = list(state.get("conversation_history", []))
        return {"generation": "Got it.", "source": "LLM"}

    mock_app = MagicMock()
    mock_app.ainvoke = mock_ainvoke
    fresh_engine.workflow_app = mock_app

    with patch("app.services.chat_service.db_service", db_svc):
        await fresh_engine.process_message(session_id, "No fever", user_id=user.id)

    assert captured_history is not None
    # Rehydrated history must match previous turns
    assert [m["content"] for m in captured_history] == [
        "I have a cough",
        "How long have you had it?",
        "About 3 days",
        "Any fever?",
    ]


@pytest.mark.asyncio
async def test_context_reconstruction_after_cache_eviction(temp_db):
    """
    When cache reaches MAX_CONVERSATION_CACHE, oldest state is evicted.
    Subsequent access must rehydrate safely from the database without error.
    """
    db_svc, _, _ = temp_db
    user = db_svc.create_user("grace", "Password123!")
    conv = db_svc.create_conversation(user_id=user.id)
    session_id = conv.id

    engine_instance = ClinicalEngine()
    engine_instance.MAX_CONVERSATION_CACHE = 2  # Set small cache bound for testing

    db_svc.save_message(session_id, "user", "Prior Symptom", user_id=user.id)
    db_svc.save_message(session_id, "assistant", "Prior Response", source="LLM", user_id=user.id)

    async def mock_ainvoke(state):
        return {"generation": "Ack", "source": "LLM"}

    mock_app = MagicMock()
    mock_app.ainvoke = mock_ainvoke
    engine_instance.workflow_app = mock_app

    with patch("app.services.chat_service.db_service", db_svc):
        # Fill cache with 2 other conversations
        conv_x = db_svc.create_conversation(user_id=user.id)
        conv_y = db_svc.create_conversation(user_id=user.id)
        await engine_instance.process_message(conv_x.id, "X1", user_id=user.id)
        await engine_instance.process_message(conv_y.id, "Y1", user_id=user.id)

        # Target conversation was not in cache. Accessing it should rehydrate without failure.
        key_target = engine_instance._get_memory_key(user.id, session_id)
        assert key_target not in engine_instance.conversation_states

        await engine_instance.process_message(session_id, "New follow up", user_id=user.id)

        # State should be rehydrated in cache
        assert key_target in engine_instance.conversation_states
        history = engine_instance.conversation_states[key_target]["conversation_history"]
        # History must contain the prior persisted turns
        contents = [m["content"] for m in history]
        assert "Prior Symptom" in contents
        assert "Prior Response" in contents


@pytest.mark.asyncio
async def test_conversation_ownership_during_history_hydration(temp_db):
    """
    Attempting to process or rehydrate history for a conversation owned by User A
    using User B's identity must fail closed with PermissionError.
    """
    db_svc, _, _ = temp_db
    user_a = db_svc.create_user("user_a", "Password123!")
    user_b = db_svc.create_user("user_b", "Password123!")
    conv_a = db_svc.create_conversation(user_id=user_a.id)

    engine_instance = ClinicalEngine()

    mock_app = MagicMock()
    mock_app.ainvoke = AsyncMock(return_value={"generation": "ok"})
    engine_instance.workflow_app = mock_app

    with patch("app.services.chat_service.db_service", db_svc):
        with pytest.raises(PermissionError, match="Access denied"):
            await engine_instance.process_message(conv_a.id, "Steal context", user_id=user_b.id)


@pytest.mark.asyncio
async def test_long_conversation_history_bounded(temp_db):
    """
    When rehydrating long conversation history, context must be strictly bounded
    to MAX_RESTORE_TURNS (20) in chronological order.
    """
    db_svc, _, _ = temp_db
    user = db_svc.create_user("heidi", "Password123!")
    conv = db_svc.create_conversation(user_id=user.id)
    session_id = conv.id

    # Insert 30 turns (15 user, 15 assistant)
    for i in range(1, 31):
        role = "user" if i % 2 != 0 else "assistant"
        db_svc.save_message(session_id, role, f"Message {i}", source="LLM" if role == "assistant" else None, user_id=user.id)

    engine_instance = ClinicalEngine()
    rehydrated_state = None

    async def mock_ainvoke(state):
        nonlocal rehydrated_state
        rehydrated_state = state
        return {"generation": "Final", "source": "LLM"}

    mock_app = MagicMock()
    mock_app.ainvoke = mock_ainvoke
    engine_instance.workflow_app = mock_app

    with patch("app.services.chat_service.db_service", db_svc):
        await engine_instance.process_message(session_id, "Turn 31", user_id=user.id)

    history = rehydrated_state["conversation_history"]
    # Bounded to exactly 20 turns
    assert len(history) == 20
    # Must be the most recent 20 messages (Message 11 through Message 30)
    assert history[0]["content"] == "Message 11"
    assert history[-1]["content"] == "Message 30"


def test_rate_limit_capacity_flooding_without_active_lockout_eviction():
    """
    Flooding BoundedRateLimiter to maximum capacity with distinct identifiers
    MUST NOT evict an active login lockout.
    """
    limiter = BoundedRateLimiter(max_entries=20, prune_interval_seconds=300.0)

    # 1. Target user hits lockout threshold (5 failed attempts)
    target_key = "login:user:victim_account"
    for _ in range(5):
        limiter.record_failure(target_key, window_seconds=120.0, lockout_threshold=5)

    assert limiter.is_allowed(target_key, max_requests=5, window_seconds=120.0) is False

    # 2. Attacker floods with 50 distinct identifiers to exceed capacity
    for i in range(50):
        attacker_key = f"login:user:flood_{i}"
        limiter.record_failure(attacker_key, window_seconds=120.0, lockout_threshold=5)

    # 3. Capacity invariant: limiter entries must not exceed max_entries
    assert len(limiter._buckets) <= 20

    # 4. Critical security check: Target user MUST STILL BE LOCKED OUT
    assert limiter.is_allowed(target_key, max_requests=5, window_seconds=120.0) is False
    assert target_key in limiter._buckets


def test_stepwise_schema_migration_recovery(tmp_path):
    """
    Verify step-wise migration recovery:
    If migration completes v1 and is interrupted before v2,
    subsequent startup safely resumes at v2 without corrupting or duplicating v1.
    """
    db_file = str(tmp_path / "stepwise_test.db")
    engine = create_engine(f"sqlite:///{db_file}")

    # Create tables as they existed at version 0
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id VARCHAR(255) NOT NULL,
                user_id INTEGER,
                role VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                source VARCHAR(255),
                timestamp DATETIME NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE user_sessions (
                token VARCHAR(255) PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(255) UNIQUE NOT NULL,
                hashed_password VARCHAR(255) NOT NULL
            )
        """))
        conn.execute(text("INSERT INTO users (id, username, hashed_password) VALUES (1, 'u1', 'p1')"))
        conn.execute(text("INSERT INTO messages (session_id, user_id, role, content, timestamp) VALUES ('s1', 1, 'user', 'hi', '2026-01-01 00:00:00')"))
        conn.execute(text("INSERT INTO user_sessions (token, user_id, created_at) VALUES ('tok123', 1, '2026-01-01 00:00:00')"))

    # Mock migration to simulate interruption right after Step 1 commits
    orig_run = run_database_migration

    # Step 1: Run migration with CURRENT_SCHEMA_VERSION capped at 1
    with patch("app.db.migrations.CURRENT_SCHEMA_VERSION", 1):
        stats_v1 = run_database_migration(engine, db_path=db_file)
        assert stats_v1["schema_version"] == 1

    # Verify v1 state: conversations table created, schema_versions at 1, user_sessions still legacy
    with engine.connect() as conn:
        v1_ver = conn.execute(text("SELECT MAX(version) FROM schema_versions")).scalar()
        assert v1_ver == 1
        conv_count = conn.execute(text("SELECT count(*) FROM conversations")).scalar()
        assert conv_count == 1
        # user_sessions still has legacy 'token' column
        cols = [c[1] for c in conn.execute(text("PRAGMA table_info(user_sessions)")).fetchall()]
        assert "token" in cols
        assert "token_hash" not in cols

    # Step 2: Resume migration to CURRENT_SCHEMA_VERSION = 2
    stats_v2 = run_database_migration(engine, db_path=db_file)
    assert stats_v2["schema_version"] == 2

    # Verify v2 state: schema_versions is 2, user_sessions upgraded to token_hash
    with engine.connect() as conn:
        v2_ver = conn.execute(text("SELECT MAX(version) FROM schema_versions")).scalar()
        assert v2_ver == 2
        cols = [c[1] for c in conn.execute(text("PRAGMA table_info(user_sessions)")).fetchall()]
        assert "token_hash" in cols
        # Clean conversation from v1 is preserved
        conv_owner = conn.execute(text("SELECT user_id FROM conversations WHERE id = 's1'")).scalar()
        assert conv_owner == 1


@pytest.mark.asyncio
async def test_deleted_id_resurrection_attempts_fail_closed(temp_db):
    """
    Submitting a message referencing a previously deleted conversation ID
    must fail closed with PermissionError and must NEVER recreate the conversation.
    """
    db_svc, _, _ = temp_db
    user = db_svc.create_user("ian", "Password123!")
    conv = db_svc.create_conversation(user_id=user.id)
    session_id = conv.id

    engine_instance = ClinicalEngine()
    mock_app = MagicMock()
    mock_app.ainvoke = AsyncMock(return_value={"generation": "Should not happen"})
    engine_instance.workflow_app = mock_app

    with patch("app.services.chat_service.db_service", db_svc):
        # 1. Delete conversation
        deleted = engine_instance.delete_conversation(session_id, user_id=user.id)
        assert deleted is True

        # 2. Attempt to submit message with deleted conversation ID
        with pytest.raises(PermissionError, match="deleted|not owned"):
            await engine_instance.process_message(session_id, "Resurrect me", user_id=user.id)

    # Database must not have this conversation
    assert db_svc.get_conversation(session_id, user_id=user.id) is None


@pytest.mark.asyncio
async def test_account_switching_isolation(temp_db):
    """
    Verifies that requests initiated under User A cannot mutate User B's state,
    and User B cannot view User A's private messages or memory.
    """
    db_svc, _, _ = temp_db
    user_a = db_svc.create_user("user_alpha", "Password123!")
    user_b = db_svc.create_user("user_beta", "Password123!")
    conv_a = db_svc.create_conversation(user_id=user_a.id)

    engine_instance = ClinicalEngine()
    mock_app = MagicMock()
    mock_app.ainvoke = AsyncMock(return_value={"generation": "Alpha Diagnosis", "source": "LLM"})
    engine_instance.workflow_app = mock_app

    with patch("app.services.chat_service.db_service", db_svc):
        # User A completes a consultation
        await engine_instance.process_message(conv_a.id, "Alpha confidential symptom", user_id=user_a.id)

        # User B attempts to access User A's session
        with pytest.raises(PermissionError, match="Access denied"):
            await engine_instance.process_message(conv_a.id, "Beta spy query", user_id=user_b.id)

    # Verify User B gets 0 messages from get_chat_history
    assert db_svc.get_chat_history(conv_a.id, user_id=user_b.id) is None

    # Verify memory states are strictly isolated by user_id
    key_a = engine_instance._get_memory_key(user_a.id, conv_a.id)
    key_b = engine_instance._get_memory_key(user_b.id, conv_a.id)
    assert key_a in engine_instance.conversation_states
    assert key_b not in engine_instance.conversation_states


@pytest.mark.asyncio
async def test_failed_generation_excluded_from_history(temp_db):
    """
    Assistant responses that encountered errors (e.g. 'Unable to generate response'
    or 'Sorry, I encountered an error') must be excluded from rehydrated history.
    """
    db_svc, _, _ = temp_db
    user = db_svc.create_user("julia", "Password123!")
    conv = db_svc.create_conversation(user_id=user.id)
    session_id = conv.id

    # Insert a valid turn, an error turn, and another valid turn
    db_svc.save_message(session_id, "user", "Valid question 1", user_id=user.id)
    db_svc.save_message(session_id, "assistant", "Valid answer 1", source="LLM", user_id=user.id)
    db_svc.save_message(session_id, "user", "Glitch question", user_id=user.id)
    db_svc.save_message(session_id, "assistant", "Unable to generate response.", source="Error", user_id=user.id)
    db_svc.save_message(session_id, "user", "Valid question 2", user_id=user.id)
    db_svc.save_message(session_id, "assistant", "Valid answer 2", source="LLM", user_id=user.id)

    # Fresh engine rehydrates state
    fresh_engine = ClinicalEngine()
    with patch("app.services.chat_service.db_service", db_svc):
        state = fresh_engine._get_or_restore_state(session_id, user_id=user.id)

    history = state["conversation_history"]
    contents = [m["content"] for m in history]

    # Error message must be excluded
    assert "Unable to generate response." not in contents
    # Valid messages must be present in chronological order
    assert "Valid question 1" in contents
    assert "Valid answer 1" in contents
    assert "Valid question 2" in contents
    assert "Valid answer 2" in contents
