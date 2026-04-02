from __future__ import annotations

import httpx
from selectolax.parser import HTMLParser

from src.detection.base import BaseScraper, RawJob
from src.logging import get_logger

log = get_logger("greenhouse")

API_BASE = "https://boards-api.greenhouse.io/v1/boards"


class GreenhouseScraper(BaseScraper):
    def __init__(self, board_token: str, company_name: str) -> None:
        self.board_token = board_token
        self.company_name = company_name

    @property
    def source_name(self) -> str:
        return "greenhouse"

    async def fetch_jobs(self, client: httpx.AsyncClient) -> list[RawJob]:
        url = f"{API_BASE}/{self.board_token}/jobs"
        resp = await client.get(url, params={"content": "true"})
        resp.raise_for_status()
        data = resp.json()

        jobs: list[RawJob] = []
        for item in data.get("jobs", []):
            location_name = ""
            loc = item.get("location")
            if loc and isinstance(loc, dict):
                location_name = loc.get("name", "")

            desc_html = item.get("content", "")
            desc_text = _html_to_text(desc_html) if desc_html else ""

            jobs.append(
                RawJob(
                    source_board="greenhouse",
                    external_id=str(item["id"]),
                    url=item.get("absolute_url", f"https://boards.greenhouse.io/{self.board_token}/jobs/{item['id']}"),
                    title=item.get("title", ""),
                    company_name=self.company_name,
                    location=location_name,
                    description_text=desc_text,
                    description_html=desc_html,
                    posted_at=item.get("updated_at"),
                )
            )

        log.info(
            "scrape_completed",
            source_board="greenhouse",
            company=self.company_name,
            jobs_found=len(jobs),
        )
        return jobs


def _html_to_text(html: str) -> str:
    tree = HTMLParser(html)
    return tree.text(separator="\n", strip=True)
