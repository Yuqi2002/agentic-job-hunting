"""Remotive.com scraper — free public API, no auth required.

API: https://remotive.com/api/remote-jobs
Rate limit: max 4 requests/day recommended (24h delay on feed).
Only fetches software/data/devops categories relevant to target roles.
"""
from __future__ import annotations

import httpx
from selectolax.parser import HTMLParser

from src.detection.base import BaseScraper, RawJob
from src.logging import get_logger

log = get_logger("remotive")

API_URL = "https://remotive.com/api/remote-jobs"

# Only fetch categories relevant to SWE/AI/ML/FDE target roles
_CATEGORIES = ["software-dev", "devops-sysadmin", "data"]


class RemotiveScraper(BaseScraper):
    @property
    def source_name(self) -> str:
        return "remotive"

    async def fetch_jobs(self, client: httpx.AsyncClient) -> list[RawJob]:
        jobs: list[RawJob] = []
        seen: set[str] = set()

        for category in _CATEGORIES:
            try:
                resp = await client.get(
                    API_URL,
                    params={"category": category, "limit": 100},
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                log.warning("remotive_fetch_failed", category=category, error=str(e))
                continue

            for item in data.get("jobs", []):
                job_id = str(item.get("id", ""))
                if not job_id or job_id in seen:
                    continue
                seen.add(job_id)

                desc_html = item.get("description", "")
                desc_text = _html_to_text(desc_html) if desc_html else ""

                jobs.append(
                    RawJob(
                        source_board="remotive",
                        external_id=job_id,
                        url=item.get("url", ""),
                        title=item.get("title", ""),
                        company_name=item.get("company_name", ""),
                        location=item.get("candidate_required_location") or "Remote",
                        description_text=desc_text,
                        description_html=desc_html,
                        posted_at=item.get("publication_date"),
                    )
                )

        log.info("scrape_completed", source_board="remotive", jobs_found=len(jobs))
        return jobs


def _html_to_text(html: str) -> str:
    tree = HTMLParser(html)
    return tree.text(separator="\n", strip=True)
