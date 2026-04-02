from __future__ import annotations

import httpx
from selectolax.parser import HTMLParser

from src.detection.base import BaseScraper, RawJob
from src.logging import get_logger

log = get_logger("lever")

API_BASE = "https://api.lever.co/v0/postings"


class LeverScraper(BaseScraper):
    def __init__(self, company_slug: str, company_name: str) -> None:
        self.company_slug = company_slug
        self.company_name = company_name

    @property
    def source_name(self) -> str:
        return "lever"

    async def fetch_jobs(self, client: httpx.AsyncClient) -> list[RawJob]:
        url = f"{API_BASE}/{self.company_slug}"
        resp = await client.get(url, params={"mode": "json"})
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, dict) and not data.get("ok", True):
            log.warning(
                "lever_board_not_found",
                company=self.company_name,
                slug=self.company_slug,
            )
            return []

        jobs: list[RawJob] = []
        for item in data:
            categories = item.get("categories", {})
            location = categories.get("location", "") if categories else ""

            desc_html = item.get("descriptionPlain", "") or ""
            desc_additional = item.get("additionalPlain", "") or ""
            desc_text = f"{desc_html}\n{desc_additional}".strip()

            lists_html = ""
            for lst in item.get("lists", []):
                lists_html += lst.get("content", "")

            full_html = (item.get("description", "") or "") + lists_html

            jobs.append(
                RawJob(
                    source_board="lever",
                    external_id=item["id"],
                    url=item.get("hostedUrl", f"https://jobs.lever.co/{self.company_slug}/{item['id']}"),
                    title=item.get("text", ""),
                    company_name=self.company_name,
                    location=location,
                    description_text=desc_text,
                    description_html=full_html,
                    posted_at=_epoch_to_iso(item.get("createdAt")),
                )
            )

        log.info(
            "scrape_completed",
            source_board="lever",
            company=self.company_name,
            jobs_found=len(jobs),
        )
        return jobs


def _epoch_to_iso(epoch_ms: int | None) -> str | None:
    if epoch_ms is None:
        return None
    from datetime import datetime, timezone

    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).isoformat()
