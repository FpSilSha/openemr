"""SQLite-backed persistence for sessions and LangGraph checkpointing.

Used for:
- Conversation sessions (patient binding, thread mapping)
- LangGraph state checkpoints (survives container restarts)
- Pending approval tracking (HITL write operations)

Single SQLite DB for both session store and LangGraph checkpointer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "/app/data/agent_state.db"


@dataclass
class SessionRecord:
    """A persisted session row."""

    conversation_id: str
    thread_id: str
    patient_uuid: str | None = None
    created_at: str = ""
    pending_approval: bool = False
    pending_action: str | None = None


class SessionStore:
    """Async SQLite-backed session store."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def init_db(self) -> None:
        """Create tables if they don't exist."""
        self._conn = await aiosqlite.connect(self.db_path)
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                conversation_id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                patient_uuid TEXT,
                created_at TEXT NOT NULL,
                pending_approval INTEGER DEFAULT 0,
                pending_action TEXT
            )
            """
        )
        await self._conn.commit()

    async def _ensure_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            await self.init_db()
        assert self._conn is not None
        return self._conn

    async def get_session(self, conversation_id: str) -> SessionRecord | None:
        """Look up a session by conversation_id."""
        conn = await self._ensure_conn()
        cursor = await conn.execute(
            "SELECT conversation_id, thread_id, patient_uuid, created_at, "
            "pending_approval, pending_action FROM sessions WHERE conversation_id = ?",
            (conversation_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return SessionRecord(
            conversation_id=row[0],
            thread_id=row[1],
            patient_uuid=row[2],
            created_at=row[3],
            pending_approval=bool(row[4]),
            pending_action=row[5],
        )

    async def upsert_session(self, session: SessionRecord) -> None:
        """Insert or update a session."""
        conn = await self._ensure_conn()
        await conn.execute(
            """
            INSERT INTO sessions
                (conversation_id, thread_id, patient_uuid, created_at,
                 pending_approval, pending_action)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(conversation_id) DO UPDATE SET
                patient_uuid = COALESCE(excluded.patient_uuid, sessions.patient_uuid),
                pending_approval = excluded.pending_approval,
                pending_action = excluded.pending_action
            """,
            (
                session.conversation_id,
                session.thread_id,
                session.patient_uuid,
                session.created_at,
                int(session.pending_approval),
                session.pending_action,
            ),
        )
        await conn.commit()

    async def list_pending(self) -> list[SessionRecord]:
        """List all sessions with pending approvals."""
        conn = await self._ensure_conn()
        cursor = await conn.execute(
            "SELECT conversation_id, thread_id, patient_uuid, created_at, "
            "pending_approval, pending_action FROM sessions WHERE pending_approval = 1"
        )
        rows = await cursor.fetchall()
        return [
            SessionRecord(
                conversation_id=r[0],
                thread_id=r[1],
                patient_uuid=r[2],
                created_at=r[3],
                pending_approval=bool(r[4]),
                pending_action=r[5],
            )
            for r in rows
        ]

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None


async def get_checkpointer(
    db_path: str = DEFAULT_DB_PATH,
) -> AsyncSqliteSaver:
    """Create an async SQLite checkpointer for LangGraph state persistence."""
    conn = await aiosqlite.connect(db_path)
    return AsyncSqliteSaver(conn)


def _now_iso() -> str:
    """Current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()
