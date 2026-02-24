"""Unit tests for SQLite-backed session persistence."""

import os
import tempfile

import pytest

from app.persistence.store import SessionRecord, SessionStore


@pytest.fixture
async def store():
    """Create a temporary SessionStore for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    s = SessionStore(db_path)
    await s.init_db()
    yield s
    await s.close()
    os.unlink(db_path)


@pytest.mark.asyncio
async def test_create_and_get_session(store):
    """Creating a session and retrieving it returns matching data."""
    record = SessionRecord(
        conversation_id="conv-1",
        thread_id="thread-1",
        patient_uuid="uuid-1",
        created_at="2026-02-24T00:00:00Z",
    )
    await store.upsert_session(record)
    result = await store.get_session("conv-1")
    assert result is not None
    assert result.conversation_id == "conv-1"
    assert result.thread_id == "thread-1"
    assert result.patient_uuid == "uuid-1"


@pytest.mark.asyncio
async def test_get_missing_session(store):
    """Looking up a non-existent conversation returns None."""
    result = await store.get_session("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_upsert_preserves_patient_uuid(store):
    """Upserting without patient_uuid keeps the existing value."""
    await store.upsert_session(SessionRecord(
        conversation_id="conv-2",
        thread_id="thread-2",
        patient_uuid="uuid-original",
        created_at="2026-02-24T00:00:00Z",
    ))
    # Upsert with None patient_uuid — should keep original
    await store.upsert_session(SessionRecord(
        conversation_id="conv-2",
        thread_id="thread-2",
        patient_uuid=None,
        created_at="2026-02-24T00:00:00Z",
    ))
    result = await store.get_session("conv-2")
    assert result is not None
    assert result.patient_uuid == "uuid-original"


@pytest.mark.asyncio
async def test_upsert_updates_patient_uuid(store):
    """Upserting with a new patient_uuid updates the value (late binding)."""
    await store.upsert_session(SessionRecord(
        conversation_id="conv-3",
        thread_id="thread-3",
        patient_uuid=None,
        created_at="2026-02-24T00:00:00Z",
    ))
    await store.upsert_session(SessionRecord(
        conversation_id="conv-3",
        thread_id="thread-3",
        patient_uuid="uuid-late",
        created_at="2026-02-24T00:00:00Z",
    ))
    result = await store.get_session("conv-3")
    assert result is not None
    assert result.patient_uuid == "uuid-late"


@pytest.mark.asyncio
async def test_thread_id_stored(store):
    """Thread ID is persisted and retrievable."""
    await store.upsert_session(SessionRecord(
        conversation_id="conv-4",
        thread_id="my-thread-id",
        created_at="2026-02-24T00:00:00Z",
    ))
    result = await store.get_session("conv-4")
    assert result is not None
    assert result.thread_id == "my-thread-id"


@pytest.mark.asyncio
async def test_pending_approval_flag(store):
    """Pending approval flag is stored and queryable."""
    await store.upsert_session(SessionRecord(
        conversation_id="conv-5",
        thread_id="thread-5",
        created_at="2026-02-24T00:00:00Z",
        pending_approval=True,
        pending_action='{"type": "clinical_note"}',
    ))
    result = await store.get_session("conv-5")
    assert result is not None
    assert result.pending_approval is True
    assert result.pending_action == '{"type": "clinical_note"}'


@pytest.mark.asyncio
async def test_list_pending(store):
    """list_pending returns only sessions with pending_approval=True."""
    await store.upsert_session(SessionRecord(
        conversation_id="conv-a",
        thread_id="thread-a",
        created_at="2026-02-24T00:00:00Z",
        pending_approval=False,
    ))
    await store.upsert_session(SessionRecord(
        conversation_id="conv-b",
        thread_id="thread-b",
        created_at="2026-02-24T00:00:00Z",
        pending_approval=True,
    ))
    pending = await store.list_pending()
    assert len(pending) == 1
    assert pending[0].conversation_id == "conv-b"


@pytest.mark.asyncio
async def test_multiple_sessions(store):
    """Multiple sessions can coexist without interference."""
    for i in range(5):
        await store.upsert_session(SessionRecord(
            conversation_id=f"conv-{i}",
            thread_id=f"thread-{i}",
            patient_uuid=f"uuid-{i}",
            created_at="2026-02-24T00:00:00Z",
        ))
    for i in range(5):
        result = await store.get_session(f"conv-{i}")
        assert result is not None
        assert result.patient_uuid == f"uuid-{i}"


@pytest.mark.asyncio
async def test_init_creates_table():
    """init_db creates the sessions table from scratch."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    s = SessionStore(db_path)
    await s.init_db()
    # Should be able to insert immediately
    await s.upsert_session(SessionRecord(
        conversation_id="init-test",
        thread_id="t-1",
        created_at="2026-02-24T00:00:00Z",
    ))
    result = await s.get_session("init-test")
    assert result is not None
    await s.close()
    os.unlink(db_path)
