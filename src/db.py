from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from src.detection.base import RawJob
from src.logging import get_logger

log = get_logger("db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    source_board    TEXT NOT NULL,
    external_id     TEXT NOT NULL,
    url             TEXT NOT NULL,
    title           TEXT NOT NULL,
    company_name    TEXT NOT NULL,
    company_url     TEXT,
    location        TEXT,
    is_remote       INTEGER DEFAULT 0,
    description_text TEXT,
    description_html TEXT,
    posted_at       TEXT,
    discovered_at   TEXT NOT NULL,
    salary_min      INTEGER,
    salary_max      INTEGER,
    salary_currency TEXT DEFAULT 'USD',
    experience_level TEXT DEFAULT 'unknown',
    job_type        TEXT DEFAULT 'full_time',
    filter_status   TEXT DEFAULT 'pending',
    filter_reason   TEXT,
    resume_generated INTEGER DEFAULT 0,
    notified        INTEGER DEFAULT 0,
    notified_at     TEXT,
    discord_message_id TEXT,
    approval_status TEXT DEFAULT 'pending',
    total_comp      TEXT,
    match_pct       INTEGER DEFAULT 0,
    match_keywords  TEXT,
    UNIQUE(source_board, external_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_discovered ON jobs(discovered_at);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_jobs_filter ON jobs(filter_status);
CREATE INDEX IF NOT EXISTS idx_jobs_pipeline ON jobs(filter_status, resume_generated, notified);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id          TEXT PRIMARY KEY,
    source_board TEXT NOT NULL,
    company     TEXT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL,
    jobs_found  INTEGER DEFAULT 0,
    new_jobs    INTEGER DEFAULT 0,
    error_msg   TEXT
);
"""


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        log.info("database_connected", path=str(self.db_path))

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    @property
    def db(self) -> aiosqlite.Connection:
        assert self._db is not None, "Database not connected"
        return self._db

    async def insert_job(self, job: RawJob) -> bool:
        """Insert a job, return True if it was new (not a duplicate)."""
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        try:
            await self.db.execute(
                """INSERT INTO jobs
                (id, source_board, external_id, url, title, company_name,
                 location, description_text, description_html, posted_at, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    job.source_board,
                    job.external_id,
                    job.url,
                    job.title,
                    job.company_name,
                    job.location,
                    job.description_text,
                    job.description_html,
                    job.posted_at,
                    now,
                ),
            )
            await self.db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def get_pending_jobs(self) -> list[dict]:
        cursor = await self.db.execute(
            "SELECT * FROM jobs WHERE filter_status = 'pending' ORDER BY discovered_at"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_matched_unnotified(self) -> list[dict]:
        cursor = await self.db.execute(
            "SELECT * FROM jobs WHERE filter_status = 'matched' AND notified = 0 ORDER BY discovered_at"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def update_filter_status(
        self, job_id: str, status: str, reason: str
    ) -> None:
        await self.db.execute(
            "UPDATE jobs SET filter_status = ?, filter_reason = ? WHERE id = ?",
            (status, reason, job_id),
        )
        await self.db.commit()

    async def mark_notified(
        self,
        job_id: str,
        discord_message_id: str | None = None,
        total_comp: str | None = None,
        match_pct: int | None = None,
        match_keywords: list[str] | None = None,
    ) -> None:
        import json as _json

        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            """UPDATE jobs
               SET notified = 1, notified_at = ?,
                   discord_message_id = COALESCE(?, discord_message_id),
                   total_comp = COALESCE(?, total_comp),
                   match_pct = COALESCE(?, match_pct),
                   match_keywords = COALESCE(?, match_keywords)
               WHERE id = ?""",
            (
                now,
                discord_message_id,
                total_comp,
                match_pct,
                _json.dumps(match_keywords) if match_keywords is not None else None,
                job_id,
            ),
        )
        await self.db.commit()

    async def get_job_by_message_id(self, message_id: str) -> dict | None:
        cursor = await self.db.execute(
            "SELECT * FROM jobs WHERE discord_message_id = ?",
            (message_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def mark_approved(self, job_id: str) -> None:
        await self.db.execute(
            "UPDATE jobs SET approval_status = 'approved' WHERE id = ?",
            (job_id,),
        )
        await self.db.commit()

    async def mark_resume_sent(self, job_id: str) -> None:
        await self.db.execute(
            "UPDATE jobs SET resume_generated = 1, approval_status = 'resume_sent' WHERE id = ?",
            (job_id,),
        )
        await self.db.commit()

    async def record_scrape_run(
        self,
        source_board: str,
        company: str | None,
        started_at: str,
        finished_at: str,
        status: str,
        jobs_found: int,
        new_jobs: int,
        error_msg: str | None = None,
    ) -> None:
        run_id = str(uuid.uuid4())
        await self.db.execute(
            """INSERT INTO scrape_runs
            (id, source_board, company, started_at, finished_at, status, jobs_found, new_jobs, error_msg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, source_board, company, started_at, finished_at, status, jobs_found, new_jobs, error_msg),
        )
        await self.db.commit()
