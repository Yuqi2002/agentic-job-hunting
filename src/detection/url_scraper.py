"""Fetch a single job posting from a URL, detecting the ATS automatically."""
from __future__ import annotations

import re

import httpx
from selectolax.parser import HTMLParser

from src.logging import get_logger

log = get_logger("url_scraper")

# Match job URLs for each ATS
_GH_RE = re.compile(
    r"https?://(?:boards|job-boards)\.greenhouse\.io/([^/?#\s]+)/jobs/(\d+)"
)
_LEVER_RE = re.compile(r"https?://jobs\.lever\.co/([^/?#\s]+)/([^/?#\s]+)")
_ASHBY_RE = re.compile(r"https?://jobs\.ashbyhq\.com/([^/?#\s]+)/([^/?#\s]+)")
_URL_RE = re.compile(r"https?://[^\s>\"']+")


def extract_urls(text: str) -> list[str]:
    """Return all URLs found in *text*."""
    return _URL_RE.findall(text)


async def fetch_job_from_url(url: str) -> dict | None:
    """Detect ATS from *url* and return a job dict ready for generate_resume().

    Returned dict keys: title, company, location, url, description, source_board.
    Returns None if the job cannot be fetched.
    """
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        if m := _GH_RE.search(url):
            return await _greenhouse(client, m.group(1), m.group(2), url)
        if m := _LEVER_RE.search(url):
            return await _lever(client, m.group(1), m.group(2), url)
        if m := _ASHBY_RE.search(url):
            return await _ashby(client, m.group(1), m.group(2), url)
        return await _generic(client, url)


# ── per-ATS fetchers ────────────────────────────────────────────────────────


async def _greenhouse(
    client: httpx.AsyncClient, token: str, job_id: str, original_url: str
) -> dict | None:
    api = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{job_id}?content=true"
    try:
        resp = await client.get(api)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("greenhouse_fetch_failed", token=token, job_id=job_id, error=str(exc))
        return None

    loc_raw = data.get("location", {})
    location = loc_raw.get("name", "") if isinstance(loc_raw, dict) else ""
    description = _html_to_text(data.get("content", "") or "")
    company = _title_case(token)

    return {
        "source_board": "greenhouse",
        "url": data.get("absolute_url", original_url),
        "title": data.get("title", ""),
        "company": company,
        "location": location,
        "description": description,
    }


async def _lever(
    client: httpx.AsyncClient, slug: str, posting_id: str, original_url: str
) -> dict | None:
    api = f"https://api.lever.co/v0/postings/{slug}/{posting_id}"
    try:
        resp = await client.get(api)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("lever_fetch_failed", slug=slug, posting_id=posting_id, error=str(exc))
        return None

    categories = data.get("categories") or {}
    location = categories.get("location", "")
    desc = (data.get("descriptionPlain") or "") + "\n" + (data.get("additionalPlain") or "")

    return {
        "source_board": "lever",
        "url": data.get("hostedUrl", original_url),
        "title": data.get("text", ""),
        "company": data.get("company") or _title_case(slug),
        "location": location,
        "description": desc.strip(),
    }


async def _ashby(
    client: httpx.AsyncClient, slug: str, job_id: str, original_url: str
) -> dict | None:
    api = f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
    try:
        resp = await client.get(api)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("ashby_fetch_failed", slug=slug, job_id=job_id, error=str(exc))
        return None

    for item in data.get("jobs", []):
        if item.get("id") == job_id:
            location = item.get("location", "")
            if item.get("isRemote"):
                location = f"{location} (Remote)".strip()
            return {
                "source_board": "ashby",
                "url": item.get("jobUrl", original_url),
                "title": item.get("title", ""),
                "company": _title_case(slug),
                "location": location,
                "description": item.get("descriptionPlain", ""),
            }

    log.warning("ashby_job_not_found", slug=slug, job_id=job_id)
    return None


async def _generic(client: httpx.AsyncClient, url: str) -> dict | None:
    """Fallback: fetch page HTML and extract text with selectolax."""
    try:
        resp = await client.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            verify=False,  # Allow self-signed certs as fallback
        )
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:
        log.warning("generic_fetch_failed", url=url, error=str(exc))
        return None

    tree = HTMLParser(html)

    # Remove noise tags
    for tag in tree.css("script, style, nav, header, footer, [aria-hidden]"):
        tag.decompose()

    title = ""
    if t := tree.css_first("title"):
        title = t.text(strip=True)
    elif h := tree.css_first("h1"):
        title = h.text(strip=True)

    body_text = tree.body.text(separator="\n", strip=True) if tree.body else ""

    return {
        "source_board": "manual",
        "url": url,
        "title": title,
        "company": "",
        "location": "",
        "description": body_text[:6000],
    }


# ── helpers ─────────────────────────────────────────────────────────────────


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    return HTMLParser(html).root.text(separator="\n", strip=True)


def _title_case(slug: str) -> str:
    """'stripe-inc' → 'Stripe Inc'"""
    return slug.replace("-", " ").replace("_", " ").title()
