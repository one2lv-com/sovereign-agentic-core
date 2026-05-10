"""
Flux Compass — The Anchor of Polarity
======================================
Prevents energy leakage (context drift) by keeping all state grounded
in a persistent local SQLite database. This is the "singular polarity"
anchor — every session traces back here.

Real implementation:
  - SQLite for durable memory (conversations, facts, sessions)
  - Per-session context windows
  - Fact extraction and recall
  - Toroidal logic: all queries flow through the compass and return enriched
"""

import sqlite3
import json
import time
import uuid
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "compass.db"


class FluxCompass:
    """
    The persistent state anchor. All memory flows through here.
    Think of it as the local filesystem root that keeps the AI grounded
    rather than floating stateless in the cloud.
    """

    def __init__(self):
        self.db_path = DB_PATH
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id          TEXT PRIMARY KEY,
                    created_at  REAL NOT NULL,
                    updated_at  REAL NOT NULL,
                    title       TEXT,
                    metadata    TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id          TEXT PRIMARY KEY,
                    session_id  TEXT NOT NULL,
                    role        TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    seat        TEXT,
                    created_at  REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS facts (
                    id          TEXT PRIMARY KEY,
                    session_id  TEXT,
                    key         TEXT NOT NULL,
                    value       TEXT NOT NULL,
                    source      TEXT,
                    created_at  REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_facts_key
                    ON facts(key);
            """)

    # ── Sessions ──────────────────────────────────────────────────────────────

    def create_session(self, title: str = "Unnamed Session") -> str:
        sid = str(uuid.uuid4())
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions VALUES (?,?,?,?,?)",
                (sid, now, now, title, "{}"),
            )
        return sid

    def get_session(self, session_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_sessions(self, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Messages ──────────────────────────────────────────────────────────────

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        seat: Optional[str] = None,
    ) -> str:
        mid = str(uuid.uuid4())
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages VALUES (?,?,?,?,?,?)",
                (mid, session_id, role, content, seat, now),
            )
            conn.execute(
                "UPDATE sessions SET updated_at=? WHERE id=?",
                (now, session_id),
            )
        return mid

    def get_history(
        self, session_id: str, limit: int = 40
    ) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT role, content, seat, created_at
                   FROM messages WHERE session_id=?
                   ORDER BY created_at DESC LIMIT ?""",
                (session_id, limit),
            ).fetchall()
            # Return in chronological order for LLM context
            return [dict(r) for r in reversed(rows)]

    def get_llm_history(self, session_id: str, limit: int = 20) -> list[dict]:
        """Return message history in the format the LLM expects."""
        history = self.get_history(session_id, limit)
        return [
            {"role": m["role"], "content": m["content"]}
            for m in history
            if m["role"] in ("user", "assistant")
        ]

    # ── Facts (long-term memory) ──────────────────────────────────────────────

    def store_fact(
        self,
        key: str,
        value: str,
        session_id: Optional[str] = None,
        source: Optional[str] = None,
    ) -> str:
        fid = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO facts VALUES (?,?,?,?,?,?)",
                (fid, session_id, key, value, source, time.time()),
            )
        return fid

    def recall_facts(self, query: str, limit: int = 5) -> list[dict]:
        """Simple keyword recall from the fact store."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT key, value, source, created_at FROM facts
                   WHERE key LIKE ? OR value LIKE ?
                   ORDER BY created_at DESC LIMIT ?""",
                (f"%{query}%", f"%{query}%", limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_facts(self, session_id: Optional[str] = None) -> list[dict]:
        with self._connect() as conn:
            if session_id:
                rows = conn.execute(
                    "SELECT * FROM facts WHERE session_id=? ORDER BY created_at DESC",
                    (session_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM facts ORDER BY created_at DESC LIMIT 50"
                ).fetchall()
            return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        with self._connect() as conn:
            sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            facts = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        return {
            "sessions": sessions,
            "messages": messages,
            "facts": facts,
            "db_path": str(self.db_path),
        }
