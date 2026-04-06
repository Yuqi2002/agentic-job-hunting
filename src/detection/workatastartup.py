"""Work at a Startup (workatastartup.com) — YC job board scraper.

Requires one-time login setup:
    uv run python -m src.detection.waas_auth

Architecture:
  Uses Playwright with saved session cookies to navigate the companies page.
  The React app internally searches Algolia and calls /companies/fetch.
  We intercept those /companies/fetch responses to capture full company+job data.
  No Algolia key reverse-engineering needed — the page does the work for us.

If cookies have expired, logs a warning and returns empty list.
Re-run waas_auth.py to refresh.
"""
from __future__ import annotations

import json
import re

import httpx

from src.detection.base import BaseScraper, RawJob
from src.detection.waas_auth import COOKIES_PATH, STORAGE_STATE_PATH, load_auth_state
from src.logging import get_logger

log = get_logger("workatastartup")

WAAS_BASE = "https://www.workatastartup.com"
COMPANIES_FETCH_URL = f"{WAAS_BASE}/companies/fetch"

# Role URL params to scrape: "eng" = SWE/AI/ML, "sales" = SE/FDE/solutions
_ROLE_PARAMS = ["eng", "sales"]

# Title keywords to keep within all fetched jobs
_TITLE_KEYWORDS = [
    "sales engineer",
    "solutions engineer",
    "forward deployed",
    "field engineer",
    "pre-sales",
    "presales",
    "software engineer",
    "ai engineer",
    "ml engineer",
    "machine learning",
]


class WaaScraper(BaseScraper):
    @property
    def source_name(self) -> str:
        return "workatastartup"

    async def fetch_jobs(self, client: httpx.AsyncClient) -> list[RawJob]:
        # client param kept for BaseScraper compatibility but unused here
        # (we use Playwright to maintain the authenticated browser session)
        if not STORAGE_STATE_PATH.exists():
            log.warning(
                "waas_no_auth_state",
                hint="Run: uv run python -m src.detection.waas_auth",
            )
            return []

        companies = await _playwright_scrape()

        if companies is None:
            log.warning(
                "waas_session_expired",
                hint="Run: uv run python -m src.detection.waas_auth",
            )
            return []

        jobs = _extract_jobs(companies)
        log.info("scrape_completed", source_board="workatastartup", jobs_found=len(jobs))
        return jobs


async def _playwright_scrape() -> list[dict] | None:
    """Navigate WAAS companies pages with Playwright, intercept /companies/fetch responses."""
    from playwright.async_api import async_playwright

    all_companies: list[dict] = []
    session_expired = False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Restore full browser state (cookies + localStorage) saved at login
        context = await browser.new_context(
            storage_state=str(STORAGE_STATE_PATH),
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

        page = await context.new_page()
        captured: list[dict] = []

        # Intercept /companies/fetch responses
        async def handle_response(response) -> None:
            if "/companies/fetch" in response.url and response.status == 200:
                try:
                    data = await response.json()
                    companies = data.get("companies", [])
                    if companies:
                        captured.extend(companies)
                        log.info(
                            "waas_intercepted_batch",
                            count=len(companies),
                            total=len(captured),
                        )
                except Exception as e:
                    log.warning("waas_intercept_parse_failed", error=str(e))

        page.on("response", handle_response)

        for role in _ROLE_PARAMS:
            url = (
                f"{WAAS_BASE}/companies"
                f"?role={role}"
                f"&jobType=fulltime"
                f"&sortBy=created_desc"
                f"&layout=list"
            )
            log.info("waas_navigating", role=role, url=url)
            try:
                response = await page.goto(url, wait_until="networkidle", timeout=30000)
                if response and response.url and "account.ycombinator.com" in response.url:
                    log.warning("waas_redirected_to_login", role=role)
                    session_expired = True
                    break

                # Check if we landed on login page (session expired)
                if "account.ycombinator.com" in page.url:
                    session_expired = True
                    break

                # Scroll to trigger lazy-loading of more companies
                for _ in range(3):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(1500)

            except Exception as e:
                log.warning("waas_navigation_failed", role=role, error=str(e))

        await browser.close()

    if session_expired:
        return None

    all_companies.extend(captured)
    log.info("waas_total_companies_captured", count=len(all_companies))
    return all_companies


def _extract_jobs(companies: list[dict]) -> list[RawJob]:
    """Extract RawJob objects from /companies/fetch response data."""
    jobs: list[RawJob] = []
    seen: set[str] = set()

    for company in companies:
        company_name = company.get("name", "")
        company_id = str(company.get("id", ""))

        for job in company.get("jobs", []):
            title = job.get("title", "")

            # Filter by title keywords
            title_lower = title.lower()
            if not any(kw in title_lower for kw in _TITLE_KEYWORDS):
                continue

            job_id = str(job.get("id", ""))
            if not job_id:
                continue

            external_id = f"{company_id}_{job_id}"
            if external_id in seen:
                continue
            seen.add(external_id)

            location_parts = []
            if job.get("remote"):
                location_parts.append("Remote")
            for loc in job.get("locations") or []:
                if isinstance(loc, str):
                    if loc:
                        location_parts.append(loc)
                elif isinstance(loc, dict):
                    name = loc.get("name", "")
                    if name:
                        location_parts.append(name)
            location = ", ".join(location_parts)

            desc_html = job.get("description", "") or ""
            desc_text = re.sub(r"<[^>]+>", " ", desc_html)
            desc_text = re.sub(r"\s+", " ", desc_text).strip()

            jobs.append(
                RawJob(
                    source_board="workatastartup",
                    external_id=external_id,
                    url=f"{WAAS_BASE}/jobs/{job_id}",
                    title=title,
                    company_name=company_name,
                    location=location,
                    description_text=desc_text,
                    description_html=desc_html,
                    posted_at=job.get("created_at"),
                )
            )

    return jobs
