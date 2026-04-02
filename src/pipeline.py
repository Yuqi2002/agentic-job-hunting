from __future__ import annotations

from src.db import Database
from src.detection.base import RawJob
from src.filter.matcher import JobMatcher
from src.logging import get_logger
from src.notify.discord import DiscordNotifier
from src.resume.summarizer import summarize

log = get_logger("pipeline")


class JobPipeline:
    def __init__(
        self,
        db: Database,
        matcher: JobMatcher,
        notifier: DiscordNotifier,
        openai_api_key: str = "",
        master: dict | None = None,
    ) -> None:
        self.db = db
        self.matcher = matcher
        self.notifier = notifier
        self.openai_api_key = openai_api_key
        self.master = master or {}

    async def process_new_jobs(self, jobs: list[RawJob]) -> int:
        """Insert jobs, filter, summarize, notify. Returns count of new jobs inserted."""
        new_count = 0
        for job in jobs:
            is_new = await self.db.insert_job(job)
            if is_new:
                new_count += 1

        if new_count > 0:
            log.info("new_jobs_inserted", count=new_count)

        # Filter all pending jobs
        pending = await self.db.get_pending_jobs()
        for job in pending:
            result = self.matcher.match(
                title=job["title"],
                location=job["location"],
                description=job["description_text"],
            )

            status = "matched" if result.matched else "rejected"
            await self.db.update_filter_status(job["id"], status, result.reason_str)

            log.info(
                "job_filtered",
                job_id=job["id"],
                company=job["company_name"],
                title=job["title"],
                status=status,
                reason=result.reason_str,
            )

        # Notify matched but unnotified jobs
        to_notify = await self.db.get_matched_unnotified()
        for job in to_notify:
            summary = self._get_summary(job)

            message_id = await self.notifier.send_job(
                job,
                total_comp=summary.get("total_comp"),
                match_pct=summary.get("match_pct"),
                match_keywords=summary.get("match_keywords"),
            )

            await self.db.mark_notified(
                job["id"],
                discord_message_id=message_id,
                total_comp=summary.get("total_comp"),
                match_pct=summary.get("match_pct"),
                match_keywords=summary.get("match_keywords"),
            )

        if to_notify:
            log.info("notifications_sent", count=len(to_notify))

        return new_count

    def _get_summary(self, job: dict) -> dict:
        """Call GPT-4o mini to generate job summary. Falls back gracefully on error."""
        if not self.openai_api_key or not self.master:
            return {"total_comp": "Not listed", "match_pct": 0, "match_keywords": []}

        try:
            job_data = {
                "title": job["title"],
                "company": job["company_name"],
                "location": job.get("location") or "",
                "description": job.get("description_text") or "",
            }
            return summarize(job_data, self.master, self.openai_api_key)
        except Exception as e:
            log.warning("summary_failed", company=job.get("company_name"), error=str(e))
            return {"total_comp": "Not listed", "match_pct": 0, "match_keywords": []}
