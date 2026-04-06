"""FWDDeploy.com scraper — free public JSON API, no auth required.

API: https://www.fwddeploy.com/jobs.json
Returns ~350 active Forward Deployed Engineer and adjacent roles.
Poll every 6 hours; filter by expires_at to skip stale listings.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
from selectolax.parser import HTMLParser

from src.detection.base import BaseScraper, RawJob
from src.logging import get_logger

log = get_logger("fwddeploy")

API_URL = "https://www.fwddeploy.com/jobs.json"


class FwdDeployScraper(BaseScraper):
    @property
    def source_name(self) -> str:
        return "fwddeploy"

    async def fetch_jobs(self, client: httpx.AsyncClient) -> list[RawJob]:
        try:
            resp = await client.get(API_URL)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.warning("fwddeploy_fetch_failed", error=str(e))
            return []

        now = datetime.now(timezone.utc)
        jobs: list[RawJob] = []

        for item in data:
            # Skip expired listings
            expires_at_str = item.get("expires_at")
            if expires_at_str:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    if expires_at < now:
                        continue
                except ValueError:
                    pass

            application_link = item.get("application_link", "")
            if not application_link:
                continue

            # Use application_link as external_id — unique per job posting
            external_id = application_link

            company_info = item.get("company") or {}
            company_name = company_info.get("name", "")
            company_location = company_info.get("location", "")

            # Prefer explicit location field, fall back to company location
            location = item.get("location") or company_location or ""

            desc_html = (item.get("description") or {}).get("html", "")
            desc_text = _html_to_text(desc_html) if desc_html else ""

            jobs.append(
                RawJob(
                    source_board="fwddeploy",
                    external_id=external_id,
                    url=application_link,
                    title=item.get("title", ""),
                    company_name=company_name,
                    location=location,
                    description_text=desc_text,
                    description_html=desc_html,
                    posted_at=item.get("published_at"),
                )
            )

        log.info("scrape_completed", source_board="fwddeploy", jobs_found=len(jobs))
        return jobs


def _html_to_text(html: str) -> str:
    tree = HTMLParser(html)
    return tree.text(separator="\n", strip=True)
