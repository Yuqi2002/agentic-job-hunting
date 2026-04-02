from __future__ import annotations

import re

import httpx

from src.detection.base import BaseScraper, RawJob
from src.logging import get_logger

log = get_logger("hackernews")

ALGOLIA_SEARCH = "https://hn.algolia.com/api/v1/search_by_date"
ALGOLIA_ITEMS = "https://hn.algolia.com/api/v1/items"


class HackerNewsScraper(BaseScraper):
    @property
    def source_name(self) -> str:
        return "hackernews"

    async def fetch_jobs(self, client: httpx.AsyncClient) -> list[RawJob]:
        story_id = await self._find_latest_thread(client)
        if not story_id:
            log.warning("no_hiring_thread_found")
            return []

        log.info("fetching_hn_thread", story_id=story_id)
        resp = await client.get(f"{ALGOLIA_ITEMS}/{story_id}")
        resp.raise_for_status()
        thread = resp.json()

        jobs: list[RawJob] = []
        for comment in thread.get("children", []):
            if comment.get("type") != "comment":
                continue
            text = comment.get("text", "")
            if not text:
                continue

            parsed = _parse_hn_comment(text)
            if not parsed:
                continue

            company, title, location = parsed
            comment_id = str(comment["id"])

            jobs.append(
                RawJob(
                    source_board="hackernews",
                    external_id=comment_id,
                    url=f"https://news.ycombinator.com/item?id={comment_id}",
                    title=title,
                    company_name=company,
                    location=location,
                    description_text=_strip_html(text),
                    description_html=text,
                    posted_at=comment.get("created_at"),
                )
            )

        log.info(
            "scrape_completed",
            source_board="hackernews",
            jobs_found=len(jobs),
            total_comments=len(thread.get("children", [])),
        )
        return jobs

    async def _find_latest_thread(self, client: httpx.AsyncClient) -> str | None:
        resp = await client.get(
            ALGOLIA_SEARCH,
            params={
                "query": '"who is hiring"',
                "tags": "story,author_whoishiring",
                "hitsPerPage": 1,
            },
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        if hits:
            return hits[0]["objectID"]
        return None


def _parse_hn_comment(html: str) -> tuple[str, str, str] | None:
    """Parse HN Who is Hiring comment into (company, title, location).

    Most follow a pattern like:
    Company Name | Role Title | Location | Remote | URL
    But format varies widely. We try multiple strategies.
    """
    text = _strip_html(html)
    lines = text.strip().split("\n")
    if not lines:
        return None

    first_line = lines[0].strip()

    # Strategy 1: Pipe-separated first line (most common format)
    if "|" in first_line:
        parts = [p.strip() for p in first_line.split("|")]
        if len(parts) >= 2:
            company = parts[0]
            title = parts[1] if len(parts) > 1 else ""
            location = parts[2] if len(parts) > 2 else ""
            # Skip if first part looks like a URL or is too long
            if company and len(company) < 80 and not company.startswith("http"):
                return (company, title, location)

    # Strategy 2: "Company (Location) - Title" or "Company - Title"
    m = re.match(r"^(.+?)(?:\s*\(([^)]+)\))?\s*[-–]\s*(.+)", first_line)
    if m:
        company = m.group(1).strip()
        location = m.group(2) or ""
        title = m.group(3).strip()
        if company and title and len(company) < 80:
            return (company, title, location)

    # Strategy 3: Just take the first line as company, guess the rest
    if len(first_line) < 80 and first_line:
        return (first_line, "See posting", "")

    return None


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&#x2F;", "/").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#x27;", "'")
    return re.sub(r"\s+", " ", text).strip()
