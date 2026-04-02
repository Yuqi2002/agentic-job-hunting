from __future__ import annotations

import httpx

from src.detection.base import BaseScraper, RawJob
from src.logging import get_logger

log = get_logger("ashby")

API_BASE = "https://api.ashbyhq.com/posting-api/job-board"


class AshbyScraper(BaseScraper):
    def __init__(self, company_slug: str, company_name: str | None = None) -> None:
        self.company_slug = company_slug
        self.company_name = company_name or company_slug

    @property
    def source_name(self) -> str:
        return "ashby"

    async def fetch_jobs(self, client: httpx.AsyncClient) -> list[RawJob]:
        url = f"{API_BASE}/{self.company_slug}"
        resp = await client.get(url, params={"includeCompensation": "true"})
        resp.raise_for_status()
        data = resp.json()

        jobs: list[RawJob] = []
        for item in data.get("jobs", []):
            if not item.get("isListed", True):
                continue

            location = item.get("location", "")
            if item.get("isRemote"):
                location = f"{location} (Remote)" if location else "Remote"

            jobs.append(
                RawJob(
                    source_board="ashby",
                    external_id=item["id"],
                    url=item.get("jobUrl", f"https://jobs.ashbyhq.com/{self.company_slug}/{item['id']}"),
                    title=item.get("title", ""),
                    company_name=self.company_name,
                    location=location,
                    description_text=item.get("descriptionPlain", ""),
                    description_html=item.get("descriptionHtml", ""),
                    posted_at=item.get("publishedAt"),
                )
            )

        log.info(
            "scrape_completed",
            source_board="ashby",
            company=self.company_name,
            jobs_found=len(jobs),
        )
        return jobs
