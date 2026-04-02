"""Sync company lists from Feashliaa/job-board-aggregator GitHub repo.

Pulls ~6,000+ company slugs for Greenhouse, Lever, and Ashby ATS platforms.
Updated daily by the upstream repo.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import httpx

from src.logging import get_logger

log = get_logger("company_sync")

RAW_BASE = "https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data"

SOURCES = {
    "greenhouse": f"{RAW_BASE}/greenhouse_companies.json",
    "lever": f"{RAW_BASE}/lever_companies.json",
    "ashby": f"{RAW_BASE}/ashby_companies.json",
}


@dataclass
class CompanyList:
    greenhouse: list[str]
    lever: list[str]
    ashby: list[str]

    @property
    def total(self) -> int:
        return len(self.greenhouse) + len(self.lever) + len(self.ashby)


async def sync_companies(cache_dir: Path) -> CompanyList:
    """Fetch latest company lists from GitHub and cache locally."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, list[str]] = {}

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        for platform, url in SOURCES.items():
            cache_file = cache_dir / f"{platform}_companies.json"
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                slugs = resp.json()
                # Cache locally for offline use
                cache_file.write_text(json.dumps(slugs))
                result[platform] = slugs
                log.info("company_list_synced", platform=platform, count=len(slugs))
            except Exception as e:
                # Fall back to cached version
                if cache_file.exists():
                    slugs = json.loads(cache_file.read_text())
                    result[platform] = slugs
                    log.warning(
                        "company_sync_failed_using_cache",
                        platform=platform,
                        count=len(slugs),
                        error=str(e),
                    )
                else:
                    result[platform] = []
                    log.error(
                        "company_sync_failed_no_cache",
                        platform=platform,
                        error=str(e),
                    )

    companies = CompanyList(
        greenhouse=result.get("greenhouse", []),
        lever=result.get("lever", []),
        ashby=result.get("ashby", []),
    )
    log.info("company_sync_complete", total=companies.total)
    return companies


def load_cached_companies(cache_dir: Path) -> CompanyList | None:
    """Load companies from local cache without network."""
    result: dict[str, list[str]] = {}
    for platform in SOURCES:
        cache_file = cache_dir / f"{platform}_companies.json"
        if cache_file.exists():
            result[platform] = json.loads(cache_file.read_text())
        else:
            return None
    return CompanyList(
        greenhouse=result.get("greenhouse", []),
        lever=result.get("lever", []),
        ashby=result.get("ashby", []),
    )
