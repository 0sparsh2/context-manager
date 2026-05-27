from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path

from context_manager.errors import ErrorCode, ErrorEnvelope, StoreError
from context_manager.models import Segment


class SQLiteSegmentStore:
    """Warm store: full content by ID with lightweight preview for hot context."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._path = Path(db_path) if db_path else Path(":memory:")
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        try:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS segments (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    preview TEXT NOT NULL,
                    content TEXT NOT NULL,
                    name TEXT,
                    tool_call_id TEXT,
                    created_at_unix REAL NOT NULL DEFAULT 0,
                    verified_at_unix REAL NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'session'
                )
                """
            )
            cols = {
                str(r["name"])
                for r in self._conn.execute("PRAGMA table_info(segments)").fetchall()
            }
            if "created_at_unix" not in cols:
                self._conn.execute("ALTER TABLE segments ADD COLUMN created_at_unix REAL NOT NULL DEFAULT 0")
            if "verified_at_unix" not in cols:
                self._conn.execute("ALTER TABLE segments ADD COLUMN verified_at_unix REAL NOT NULL DEFAULT 0")
            if "source" not in cols:
                self._conn.execute("ALTER TABLE segments ADD COLUMN source TEXT NOT NULL DEFAULT 'session'")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_segments_session ON segments(session_id)"
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise StoreError(
                ErrorEnvelope(
                    code=ErrorCode.STORE,
                    message=f"Failed to initialize segment store: {exc}",
                    component="sqlite_store",
                    retryable=False,
                    boundary="storage",
                )
            ) from exc

    def save(
        self,
        *,
        session_id: str,
        position: int,
        role: str,
        content: str,
        preview_chars: int = 80,
        name: str | None = None,
        tool_call_id: str | None = None,
        segment_id: str | None = None,
        verified: bool = False,
        source: str = "session",
    ) -> Segment:
        seg_id = segment_id or str(uuid.uuid4())
        preview = content[:preview_chars]
        if len(content) > preview_chars:
            preview += "…"
        created_at = time.time()
        verified_at = created_at if verified else 0.0
        try:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO segments
                (id, session_id, position, role, preview, content, name, tool_call_id, created_at_unix, verified_at_unix, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    seg_id,
                    session_id,
                    position,
                    role,
                    preview,
                    content,
                    name,
                    tool_call_id,
                    created_at,
                    verified_at,
                    source,
                ),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise StoreError(
                ErrorEnvelope(
                    code=ErrorCode.STORE,
                    message=f"Failed to save segment: {exc}",
                    component="sqlite_store",
                    retryable=True,
                    boundary="storage",
                )
            ) from exc
        return Segment(
            id=seg_id,
            session_id=session_id,
            position=position,
            role=role,
            preview=preview,
            content=content,
            name=name,
            tool_call_id=tool_call_id,
            created_at_unix=created_at,
            verified_at_unix=verified_at,
            source=source,
        )

    def get(self, segment_id: str) -> Segment | None:
        try:
            row = self._conn.execute(
                "SELECT * FROM segments WHERE id = ?", (segment_id,)
            ).fetchone()
        except sqlite3.Error as exc:
            raise StoreError(
                ErrorEnvelope(
                    code=ErrorCode.STORE,
                    message=f"Failed to fetch segment: {exc}",
                    component="sqlite_store",
                    retryable=True,
                    boundary="storage",
                )
            ) from exc
        if row is None:
            return None
        return self._row_to_segment(row)

    def list_session(self, session_id: str) -> list[Segment]:
        try:
            rows = self._conn.execute(
                "SELECT * FROM segments WHERE session_id = ? ORDER BY position",
                (session_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise StoreError(
                ErrorEnvelope(
                    code=ErrorCode.STORE,
                    message=f"Failed to list segments: {exc}",
                    component="sqlite_store",
                    retryable=True,
                    boundary="storage",
                )
            ) from exc
        return [self._row_to_segment(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _row_to_segment(row: sqlite3.Row) -> Segment:
        return Segment(
            id=row["id"],
            session_id=row["session_id"],
            position=row["position"],
            role=row["role"],
            preview=row["preview"],
            content=row["content"],
            name=row["name"],
            tool_call_id=row["tool_call_id"],
            created_at_unix=float(row["created_at_unix"] or 0.0),
            verified_at_unix=float(row["verified_at_unix"] or 0.0),
            source=str(row["source"] or "session"),
        )
