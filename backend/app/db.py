from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


@dataclass(slots=True)
class RetrievedUnit:
    id: str
    granth_name: str
    prakran_name: str
    prakran_number: int | None
    prakran_confidence: float | None
    chopai_number: str | None
    prakran_chopai_index: int | None
    chopai_lines: list[str]
    meaning_text: str
    language_script: str
    page_number: int
    pdf_path: str
    source_set: str
    normalized_text: str
    translit_hi_latn: str
    translit_gu_latn: str
    chunk_text: str
    chunk_type: str


def _dict_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = _dict_factory
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS chopai_units (
                    id TEXT PRIMARY KEY,
                    granth_name TEXT NOT NULL,
                    prakran_name TEXT NOT NULL,
                    prakran_number INTEGER,
                    prakran_confidence REAL,
                    chopai_number TEXT,
                    prakran_chopai_index INTEGER,
                    chopai_lines_json TEXT NOT NULL,
                    meaning_text TEXT NOT NULL,
                    language_script TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    pdf_path TEXT NOT NULL,
                    source_set TEXT NOT NULL,
                    normalized_text TEXT NOT NULL,
                    translit_hi_latn TEXT NOT NULL,
                    translit_gu_latn TEXT NOT NULL,
                    chunk_text TEXT NOT NULL,
                    chunk_type TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    style_tag TEXT NOT NULL,
                    citations_json TEXT,
                    cost_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS chat_threads (
                    session_id TEXT PRIMARY KEY,
                    title_text TEXT NOT NULL DEFAULT 'New chat',
                    is_archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS session_memory (
                    session_id TEXT PRIMARY KEY,
                    summary_text TEXT NOT NULL,
                    key_facts_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS session_context (
                    session_id TEXT PRIMARY KEY,
                    granth_name TEXT,
                    prakran_number INTEGER,
                    prakran_range_start INTEGER,
                    prakran_range_end INTEGER,
                    chopai_number INTEGER,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS ingest_runs (
                    run_id TEXT PRIMARY KEY,
                    files_processed INTEGER NOT NULL,
                    chunks_created INTEGER NOT NULL,
                    failed_files INTEGER NOT NULL,
                    ocr_pages INTEGER NOT NULL,
                    notes_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS fx_rates (
                    rate_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    usd_inr REAL NOT NULL,
                    fetched_at TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS usage_events (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    cached_input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    usd_cost REAL NOT NULL DEFAULT 0,
                    inr_cost REAL NOT NULL DEFAULT 0,
                    pricing_version TEXT NOT NULL DEFAULT '',
                    fx_rate REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS chopai_fts USING fts5(
                    id UNINDEXED,
                    chunk_text,
                    normalized_text,
                    translit_hi_latn,
                    translit_gu_latn,
                    granth_name,
                    prakran_name,
                    tokenize='unicode61 remove_diacritics 2'
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session_created
                ON messages (session_id, created_at);

                CREATE INDEX IF NOT EXISTS idx_chat_threads_updated_at
                ON chat_threads (updated_at DESC);

                CREATE INDEX IF NOT EXISTS idx_chopai_units_granth_prakran_chopai
                ON chopai_units (granth_name, prakran_name, chopai_number);

                CREATE INDEX IF NOT EXISTS idx_usage_events_session_created
                ON usage_events (session_id, created_at);
                """
            )

            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(chopai_units)").fetchall()
            }
            if "prakran_chopai_index" not in columns:
                conn.execute("ALTER TABLE chopai_units ADD COLUMN prakran_chopai_index INTEGER")
            if "prakran_number" not in columns:
                conn.execute("ALTER TABLE chopai_units ADD COLUMN prakran_number INTEGER")
            if "prakran_confidence" not in columns:
                conn.execute("ALTER TABLE chopai_units ADD COLUMN prakran_confidence REAL")

            message_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(messages)").fetchall()
            }
            if "cost_json" not in message_columns:
                conn.execute("ALTER TABLE messages ADD COLUMN cost_json TEXT")

            thread_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(chat_threads)").fetchall()
            }
            if "is_archived" not in thread_columns:
                conn.execute("ALTER TABLE chat_threads ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0")

            conn.execute(
                """
                INSERT OR IGNORE INTO chat_threads (session_id, title_text, created_at, updated_at)
                SELECT
                    m.session_id AS session_id,
                    COALESCE(
                        (
                            SELECT x.text
                            FROM messages x
                            WHERE x.session_id = m.session_id
                            AND x.role = 'user'
                            ORDER BY datetime(x.created_at) ASC, x.rowid ASC
                            LIMIT 1
                        ),
                        'New chat'
                    ) AS title_text,
                    MIN(m.created_at) AS created_at,
                    MAX(m.created_at) AS updated_at
                FROM messages m
                GROUP BY m.session_id
                """
            )

    def clear_ingested_content(self) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM chopai_units")
            conn.execute("DELETE FROM chopai_fts")

    def upsert_units(self, units: list[dict[str, Any]]) -> None:
        if not units:
            return

        prepared_units: list[dict[str, Any]] = []
        for unit in units:
            row = dict(unit)
            row.setdefault("prakran_number", None)
            row.setdefault("prakran_confidence", None)
            prepared_units.append(row)

        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO chopai_units (
                    id, granth_name, prakran_name, prakran_number, prakran_confidence, chopai_number, prakran_chopai_index, chopai_lines_json,
                    meaning_text, language_script, page_number, pdf_path, source_set,
                    normalized_text, translit_hi_latn, translit_gu_latn, chunk_text, chunk_type
                ) VALUES (
                    :id, :granth_name, :prakran_name, :prakran_number, :prakran_confidence, :chopai_number, :prakran_chopai_index, :chopai_lines_json,
                    :meaning_text, :language_script, :page_number, :pdf_path, :source_set,
                    :normalized_text, :translit_hi_latn, :translit_gu_latn, :chunk_text, :chunk_type
                )
                ON CONFLICT(id) DO UPDATE SET
                    granth_name=excluded.granth_name,
                    prakran_name=excluded.prakran_name,
                    prakran_number=excluded.prakran_number,
                    prakran_confidence=excluded.prakran_confidence,
                    chopai_number=excluded.chopai_number,
                    prakran_chopai_index=excluded.prakran_chopai_index,
                    chopai_lines_json=excluded.chopai_lines_json,
                    meaning_text=excluded.meaning_text,
                    language_script=excluded.language_script,
                    page_number=excluded.page_number,
                    pdf_path=excluded.pdf_path,
                    source_set=excluded.source_set,
                    normalized_text=excluded.normalized_text,
                    translit_hi_latn=excluded.translit_hi_latn,
                    translit_gu_latn=excluded.translit_gu_latn,
                    chunk_text=excluded.chunk_text,
                    chunk_type=excluded.chunk_type
                """,
                prepared_units,
            )

            # Rebuild FTS index for deterministic runs.
            conn.execute("DELETE FROM chopai_fts")
            conn.execute(
                """
                INSERT INTO chopai_fts (id, chunk_text, normalized_text, translit_hi_latn, translit_gu_latn, granth_name, prakran_name)
                SELECT id, chunk_text, normalized_text, translit_hi_latn, translit_gu_latn, granth_name, prakran_name
                FROM chopai_units
                """
            )

    def count_units(self) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM chopai_units").fetchone()
        return int(row["count"]) if row else 0

    def fetch_units_by_ids(self, ids: list[str]) -> dict[str, RetrievedUnit]:
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM chopai_units WHERE id IN ({placeholders})", ids
            ).fetchall()
        result: dict[str, RetrievedUnit] = {}
        for row in rows:
            result[row["id"]] = _row_to_unit(row)
        return result

    def search_fts(
        self,
        query: str,
        limit: int,
        granth: str | None = None,
        prakran: str | None = None,
    ) -> list[tuple[RetrievedUnit, float]]:
        fts_query = _build_fts_query(query)
        if not fts_query:
            return []

        where = ["chopai_fts MATCH ?"]
        args: list[Any] = [fts_query]
        if granth:
            where.append("u.granth_name = ?")
            args.append(granth)
        if prakran:
            where.append("u.prakran_name = ?")
            args.append(prakran)

        args.append(limit)
        sql = f"""
            SELECT u.*, bm25(chopai_fts) AS bm25_score
            FROM chopai_fts
            JOIN chopai_units u ON u.id = chopai_fts.id
            WHERE {' AND '.join(where)}
            ORDER BY bm25_score ASC
            LIMIT ?
        """

        with self.connect() as conn:
            rows = conn.execute(sql, args).fetchall()

        results: list[tuple[RetrievedUnit, float]] = []
        for row in rows:
            unit = _row_to_unit(row)
            score = float(row.get("bm25_score", 0.0))
            # bm25 lower is better. Convert to positive relevance.
            relevance = 1.0 / (1.0 + max(score, 0.0))
            results.append((unit, relevance))
        return results

    def list_filters(self) -> tuple[list[str], list[str]]:
        with self.connect() as conn:
            granths = [
                row["granth_name"]
                for row in conn.execute(
                    "SELECT DISTINCT granth_name FROM chopai_units ORDER BY granth_name"
                ).fetchall()
            ]
            prakrans = [
                row["prakran_name"]
                for row in conn.execute(
                    """
                    SELECT DISTINCT prakran_name
                    FROM chopai_units
                    WHERE prakran_name IS NOT NULL
                    AND TRIM(prakran_name) <> ''
                    AND LOWER(TRIM(prakran_name)) <> 'unknown prakran'
                    AND LOWER(TRIM(prakran_name)) <> 'prakran not parsed'
                    ORDER BY CAST(REPLACE(LOWER(prakran_name), 'prakran ', '') AS INTEGER), prakran_name
                    """
                ).fetchall()
            ]
            if not prakrans:
                prakrans = [
                    row["prakran_name"]
                    for row in conn.execute(
                        "SELECT DISTINCT prakran_name FROM chopai_units ORDER BY prakran_name"
                    ).fetchall()
                ]
        return granths, prakrans

    def get_neighbor_context(
        self,
        current_id: str,
        pdf_path: str,
        granth_name: str,
        prakran_name: str,
    ) -> tuple[str | None, str | None]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, chunk_text
                FROM chopai_units
                WHERE pdf_path = ? AND granth_name = ? AND prakran_name = ?
                ORDER BY page_number ASC, id ASC
                """,
                (pdf_path, granth_name, prakran_name),
            ).fetchall()

        if not rows:
            return None, None

        current_idx = next((idx for idx, row in enumerate(rows) if row["id"] == current_id), None)
        if current_idx is None:
            return None, None

        prev_text = rows[current_idx - 1]["chunk_text"] if current_idx > 0 else None
        next_text = rows[current_idx + 1]["chunk_text"] if current_idx + 1 < len(rows) else None

        def _trim(value: str | None) -> str | None:
            if value is None:
                return None
            return value[:280].strip()

        return _trim(prev_text), _trim(next_text)

    def get_unit_by_id(self, unit_id: str) -> RetrievedUnit | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM chopai_units WHERE id = ? LIMIT 1", (unit_id,)).fetchone()
        if not row:
            return None
        return _row_to_unit(row)

    def add_message(
        self,
        message_id: str,
        session_id: str,
        role: str,
        text: str,
        style_tag: str,
        citations_json: str | None = None,
        cost_json: str | None = None,
    ) -> None:
        title_candidate = (text or "").strip()[:120] if role == "user" else ""
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO chat_threads (session_id, title_text, updated_at)
                VALUES (?, COALESCE(NULLIF(TRIM(?), ''), 'New chat'), CURRENT_TIMESTAMP)
                """,
                (session_id, title_candidate),
            )
            conn.execute(
                """
                INSERT INTO messages (message_id, session_id, role, text, style_tag, citations_json, cost_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (message_id, session_id, role, text, style_tag, citations_json, cost_json),
            )
            if role == "user":
                conn.execute(
                    """
                    UPDATE chat_threads
                    SET title_text = CASE
                        WHEN TRIM(title_text) = '' OR LOWER(title_text) = 'new chat' THEN ?
                        ELSE title_text
                    END,
                    updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = ?
                    """,
                    (title_candidate or "New chat", session_id),
                )
            else:
                conn.execute(
                    "UPDATE chat_threads SET updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                    (session_id,),
                )

    def get_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT message_id, session_id, role, text, style_tag, citations_json, cost_json, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY datetime(created_at) ASC, rowid ASC
                """,
                (session_id,),
            ).fetchall()
        return rows

    def get_recent_messages(self, session_id: str, limit: int = 6) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT role, text, style_tag, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY datetime(created_at) DESC, rowid DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return list(reversed(rows))

    def has_prakran_metadata(self) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM chopai_units
                WHERE prakran_name IS NOT NULL
                AND TRIM(prakran_name) <> ''
                AND LOWER(TRIM(prakran_name)) <> 'unknown prakran'
                AND LOWER(TRIM(prakran_name)) <> 'prakran not parsed'
                """
            ).fetchone()
        return bool(int(row["count"])) if row else False

    def lookup_reference_units(
        self,
        *,
        granth_name: str | None = None,
        chopai_number: int | None = None,
        prakran_number: int | None = None,
        prakran_range: tuple[int, int] | None = None,
        limit: int = 60,
    ) -> list[RetrievedUnit]:
        where: list[str] = []
        args: list[Any] = []

        if granth_name:
            where.append("granth_name = ?")
            args.append(granth_name)

        if chopai_number is not None:
            where.append("(CAST(chopai_number AS INTEGER) = ? OR prakran_chopai_index = ?)")
            args.append(chopai_number)
            args.append(chopai_number)

        if prakran_number is not None:
            clause, clause_args = _build_prakran_number_clause(prakran_number)
            where.append(clause)
            args.extend(clause_args)

        if prakran_range is not None:
            start, end = sorted(prakran_range)
            numbers = list(range(start, min(end, start + 20) + 1))
            range_clauses: list[str] = []
            for number in numbers:
                clause, clause_args = _build_prakran_number_clause(number)
                range_clauses.append(clause)
                args.extend(clause_args)
            if range_clauses:
                where.append(f"({' OR '.join(range_clauses)})")

        sql = "SELECT * FROM chopai_units"
        if where:
            sql += f" WHERE {' AND '.join(where)}"
        sql += " ORDER BY page_number ASC, id ASC LIMIT ?"
        args.append(max(1, limit))

        with self.connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [_row_to_unit(row) for row in rows]

    def count_chopai_reference(
        self,
        *,
        granth_name: str | None = None,
        prakran_number: int | None = None,
        prakran_range: tuple[int, int] | None = None,
    ) -> int:
        where = [
            "(prakran_chopai_index IS NOT NULL OR (chopai_number IS NOT NULL AND TRIM(chopai_number) <> ''))",
        ]
        args: list[Any] = []

        if granth_name:
            where.append("granth_name = ?")
            args.append(granth_name)

        if prakran_number is not None:
            clause, clause_args = _build_prakran_number_clause(prakran_number)
            where.append(clause)
            args.extend(clause_args)
        elif prakran_range is not None:
            start, end = sorted(prakran_range)
            numbers = list(range(start, min(end, start + 20) + 1))
            range_clauses: list[str] = []
            for number in numbers:
                clause, clause_args = _build_prakran_number_clause(number)
                range_clauses.append(clause)
                args.extend(clause_args)
            if range_clauses:
                where.append(f"({' OR '.join(range_clauses)})")

        count_expr = "COALESCE(CAST(prakran_chopai_index AS TEXT), TRIM(chopai_number), id)"
        if prakran_number is not None or prakran_range is not None:
            count_expr = f"(prakran_name || ':' || {count_expr})"

        with self.connect() as conn:
            row = conn.execute(
                f"SELECT COUNT(DISTINCT {count_expr}) AS count FROM chopai_units WHERE {' AND '.join(where)}",
                args,
            ).fetchone()
        return int(row["count"]) if row else 0

    def get_session_memory(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT session_id, summary_text, key_facts_json, updated_at
                FROM session_memory
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()

        if not row:
            return None

        try:
            key_facts = json.loads(row["key_facts_json"] or "[]")
            if not isinstance(key_facts, list):
                key_facts = []
        except Exception:
            key_facts = []

        return {
            "session_id": row["session_id"],
            "summary_text": row["summary_text"] or "",
            "key_facts": [str(item) for item in key_facts if str(item).strip()],
            "updated_at": row["updated_at"],
        }

    def upsert_session_memory(self, session_id: str, summary_text: str, key_facts: list[str]) -> None:
        payload = json.dumps([item for item in key_facts if item], ensure_ascii=False)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO session_memory (session_id, summary_text, key_facts_json, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET
                    summary_text=excluded.summary_text,
                    key_facts_json=excluded.key_facts_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (session_id, summary_text.strip(), payload),
            )

    def get_session_context(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT session_id, granth_name, prakran_number, prakran_range_start, prakran_range_end, chopai_number, updated_at
                FROM session_context
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        return row if row else None

    def upsert_session_context(
        self,
        *,
        session_id: str,
        granth_name: str | None,
        prakran_number: int | None,
        prakran_range_start: int | None,
        prakran_range_end: int | None,
        chopai_number: int | None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO session_context (
                    session_id, granth_name, prakran_number, prakran_range_start, prakran_range_end, chopai_number, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET
                    granth_name=excluded.granth_name,
                    prakran_number=excluded.prakran_number,
                    prakran_range_start=excluded.prakran_range_start,
                    prakran_range_end=excluded.prakran_range_end,
                    chopai_number=excluded.chopai_number,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    session_id,
                    granth_name,
                    prakran_number,
                    prakran_range_start,
                    prakran_range_end,
                    chopai_number,
                ),
            )

    def list_sessions(self, limit: int = 50, include_archived: bool = False) -> list[dict[str, Any]]:
        return self.list_threads(limit=limit, include_archived=include_archived)

    def list_threads(self, limit: int = 50, include_archived: bool = False) -> list[dict[str, Any]]:
        where = "" if include_archived else "WHERE COALESCE(t.is_archived, 0) = 0"
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    t.session_id AS session_id,
                    t.title_text AS title_text,
                    COALESCE((
                        SELECT m.text
                        FROM messages m
                        WHERE m.session_id = t.session_id
                        AND m.role = 'user'
                        ORDER BY datetime(m.created_at) DESC, m.rowid DESC
                        LIMIT 1
                    ), (
                        SELECT m.text
                        FROM messages m
                        WHERE m.session_id = t.session_id
                        ORDER BY datetime(m.created_at) DESC, m.rowid DESC
                        LIMIT 1
                    ), '') AS preview_text,
                    COALESCE((
                        SELECT MAX(m.created_at)
                        FROM messages m
                        WHERE m.session_id = t.session_id
                    ), t.updated_at) AS last_message_at,
                    COALESCE((
                        SELECT COUNT(*)
                        FROM messages m
                        WHERE m.session_id = t.session_id
                    ), 0) AS message_count
                FROM chat_threads t
                """
                + where
                + """
                ORDER BY datetime(last_message_at) DESC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        return rows

    def create_thread(self, title: str | None = None) -> str:
        session_id = str(uuid.uuid4())
        title_text = (title or "").strip()[:120] or "New chat"
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_threads (session_id, title_text, is_archived, created_at, updated_at)
                VALUES (?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (session_id, title_text),
            )
        return session_id

    def archive_threads_by_patterns(self, patterns: list[str]) -> list[str]:
        cleaned = [item.strip() for item in patterns if item and item.strip()]
        if not cleaned:
            return []

        archived_ids: list[str] = []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT session_id, title_text
                FROM chat_threads
                WHERE COALESCE(is_archived, 0) = 0
                """
            ).fetchall()
            for row in rows:
                session_id = str(row.get("session_id", ""))
                title = str(row.get("title_text", ""))
                target = f"{session_id} {title}".lower()
                if not any(target.startswith(pattern.lower()) or f" {pattern.lower()}" in target for pattern in cleaned):
                    continue
                conn.execute("UPDATE chat_threads SET is_archived = 1 WHERE session_id = ?", (session_id,))
                archived_ids.append(session_id)
        return archived_ids

    def record_fx_rate(self, *, source: str, usd_inr: float, fetched_at: str) -> None:
        if usd_inr <= 0:
            return
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO fx_rates (rate_id, source, usd_inr, fetched_at, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (str(uuid.uuid4()), source.strip()[:80] or "unknown", float(usd_inr), fetched_at.strip()[:64]),
            )

    def get_latest_fx_rate(self) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT rate_id, source, usd_inr, fetched_at, created_at
                FROM fx_rates
                ORDER BY datetime(created_at) DESC, rowid DESC
                LIMIT 1
                """
            ).fetchone()
        return row if row else None

    def add_usage_event(
        self,
        *,
        session_id: str,
        stage: str,
        provider: str,
        model: str,
        endpoint: str,
        input_tokens: int,
        cached_input_tokens: int,
        output_tokens: int,
        usd_cost: float,
        inr_cost: float,
        pricing_version: str,
        fx_rate: float,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO usage_events (
                    event_id, session_id, stage, provider, model, endpoint,
                    input_tokens, cached_input_tokens, output_tokens,
                    usd_cost, inr_cost, pricing_version, fx_rate, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    str(uuid.uuid4()),
                    session_id,
                    stage,
                    provider,
                    model,
                    endpoint,
                    int(input_tokens),
                    int(cached_input_tokens),
                    int(output_tokens),
                    float(usd_cost),
                    float(inr_cost),
                    pricing_version,
                    float(fx_rate),
                ),
            )

    def get_session_costs(self, session_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT cost_json
                FROM messages
                WHERE session_id = ?
                AND role = 'assistant'
                AND cost_json IS NOT NULL
                AND TRIM(cost_json) <> ''
                ORDER BY datetime(created_at) ASC, rowid ASC
                """,
                (session_id,),
            ).fetchall()

        total_usd = 0.0
        total_inr = 0.0
        turns = 0
        fx_rate = 0.0
        fx_source = "fallback"
        items: list[dict[str, Any]] = []
        by_model: dict[str, dict[str, float]] = {}

        for row in rows:
            raw = row.get("cost_json")
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            turns += 1
            usd = float(payload.get("total_usd", 0.0) or 0.0)
            inr = float(payload.get("total_inr", 0.0) or 0.0)
            total_usd += usd
            total_inr += inr
            fx_rate = float(payload.get("fx_rate", fx_rate) or fx_rate)
            fx_source = str(payload.get("fx_source", fx_source) or fx_source)
            items.append(payload)

            line_items = payload.get("line_items", [])
            if not isinstance(line_items, list):
                continue
            for line in line_items:
                if not isinstance(line, dict):
                    continue
                model = str(line.get("model", "")).strip() or "unknown"
                model_row = by_model.setdefault(model, {"usd": 0.0, "inr": 0.0, "calls": 0.0})
                model_row["usd"] += float(line.get("usd_cost", 0.0) or 0.0)
                model_row["inr"] += float(line.get("inr_cost", 0.0) or 0.0)
                model_row["calls"] += 1.0

        rounded_by_model = {
            model: {"usd": round(values["usd"], 6), "inr": round(values["inr"], 4), "calls": int(values["calls"])}
            for model, values in by_model.items()
        }
        return {
            "session_id": session_id,
            "turns": turns,
            "total_usd": round(total_usd, 6),
            "total_inr": round(total_inr, 4),
            "fx_rate": fx_rate,
            "fx_source": fx_source,
            "by_model": rounded_by_model,
            "items": items,
        }

    def record_ingest_run(
        self,
        run_id: str,
        files_processed: int,
        chunks_created: int,
        failed_files: int,
        ocr_pages: int,
        notes: list[str],
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO ingest_runs (run_id, files_processed, chunks_created, failed_files, ocr_pages, notes_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, files_processed, chunks_created, failed_files, ocr_pages, json.dumps(notes, ensure_ascii=False)),
            )


def _row_to_unit(row: dict[str, Any]) -> RetrievedUnit:
    return RetrievedUnit(
        id=row["id"],
        granth_name=row["granth_name"],
        prakran_name=row["prakran_name"],
        prakran_number=int(row["prakran_number"]) if row.get("prakran_number") is not None else None,
        prakran_confidence=float(row["prakran_confidence"]) if row.get("prakran_confidence") is not None else None,
        chopai_number=row.get("chopai_number"),
        prakran_chopai_index=int(row["prakran_chopai_index"]) if row.get("prakran_chopai_index") is not None else None,
        chopai_lines=json.loads(row["chopai_lines_json"]),
        meaning_text=row["meaning_text"],
        language_script=row["language_script"],
        page_number=int(row["page_number"]),
        pdf_path=row["pdf_path"],
        source_set=row["source_set"],
        normalized_text=row["normalized_text"],
        translit_hi_latn=row["translit_hi_latn"],
        translit_gu_latn=row["translit_gu_latn"],
        chunk_text=row["chunk_text"],
        chunk_type=row["chunk_type"],
    )


def _build_fts_query(query: str) -> str:
    cleaned = " ".join(query.replace('"', " ").replace("'", " ").split())
    if not cleaned:
        return ""

    parts: list[str] = []
    for token in cleaned.split(" "):
        token = token.strip()
        if not token:
            continue
        token = "".join(ch for ch in token if ch.isalnum())
        if not token:
            continue
        parts.append(f"{token}*")

    return " OR ".join(parts)


def _build_prakran_number_clause(prakran_number: int) -> tuple[str, list[str]]:
    value = str(prakran_number)
    clause = (
        "(prakran_number = ? "
        "OR LOWER(TRIM(prakran_name)) = ? "
        "OR prakran_name LIKE ? "
        "OR chunk_text LIKE ? "
        "OR chunk_text LIKE ? "
        "OR normalized_text LIKE ? "
        "OR normalized_text LIKE ?)"
    )
    args = [
        int(prakran_number),
        f"prakran {value}",
        f"%{value}%",
        f"%-{value}-%",
        f"% {value} %",
        f"%-{value}-%",
        f"% {value} %",
    ]
    return clause, args
