"""Remote OK scraper — free public JSON API, no auth required.

API: https://remoteok.com/api
Returns the 20 most recently posted remote jobs across all categories.
No tag filtering available at API level — role matching handled by filter layer.
Poll every 6 hours; low volume but high signal (tech-focused, startup-heavy).
"""
from __future__ import annotations

import re

import httpx
from selectolax.parser import HTMLParser

from src.detection.base import BaseScraper, RawJob
from src.logging import get_logger

log = get_logger("remoteok")

API_URL = "https://remoteok.com/api"


class RemoteOKScraper(BaseScraper):
    @property
    def source_name(self) -> str:
        return "remoteok"

    async def fetch_jobs(self, client: httpx.AsyncClient) -> list[RawJob]:
        try:
            resp = await client.get(
                API_URL,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.warning("remoteok_fetch_failed", error=str(e))
            return []

        jobs: list[RawJob] = []
        for item in data:
            # First element is a legal notice object, not a job
            if not isinstance(item, dict) or "id" not in item:
                continue

            job_id = str(item["id"])
            title = item.get("position", "")
            if not title:
                continue

            desc_html = item.get("description", "") or ""
            desc_text = _html_to_text(desc_html) if desc_html else ""

            # Tags as comma-separated text to help the filter layer
            tags = item.get("tags") or []
            tags_text = ", ".join(tags) if tags else ""

            # Combine description + tags for better keyword matching
            full_desc = f"{desc_text}\n\nTags: {tags_text}" if tags_text else desc_text

            location = item.get("location", "") or "Remote"

            jobs.append(
                RawJob(
                    source_board="remoteok",
                    external_id=job_id,
                    url=item.get("apply_url") or item.get("url", ""),
                    title=title,
                    company_name=item.get("company", ""),
                    location=location,
                    description_text=full_desc,
                    description_html=desc_html,
                    posted_at=item.get("date"),
                )
            )

        log.info("scrape_completed", source_board="remoteok", jobs_found=len(jobs))
        return jobs


def _html_to_text(html: str) -> str:
    try:
        tree = HTMLParser(html)
        return tree.text(separator="\n", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html).strip()
