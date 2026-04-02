"""Scheduler for job detection.

Handles 6,000+ companies by processing them in batches rather than
scheduling one APScheduler job per company. Each batch run scrapes
a chunk of companies with a delay between requests to be polite.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.detection.ashby import AshbyScraper
from src.detection.base import BaseScraper, RawJob
from src.detection.company_sync import CompanyList, sync_companies
from src.detection.greenhouse import GreenhouseScraper
from src.detection.hackernews import HackerNewsScraper
from src.detection.lever import LeverScraper
from src.logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from src.pipeline import JobPipeline

log = get_logger("scheduler")

# Delay between individual company requests within a batch (seconds)
REQUEST_DELAY = 1.5
# How many companies to process per batch cycle
BATCH_SIZE = 200


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=10, max=60),
    retry=retry_if_exception_type(
        (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout)
    ),
    reraise=True,
)
async def _scrape_with_retry(
    scraper: BaseScraper, client: httpx.AsyncClient
) -> list[RawJob]:
    return await scraper.fetch_jobs(client)


async def run_scraper(scraper: BaseScraper, pipeline: JobPipeline) -> None:
    started_at = datetime.now(timezone.utc).isoformat()
    company = getattr(scraper, "company_name", None)
    source = scraper.source_name

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={"User-Agent": "JobHunterBot/1.0"},
            follow_redirects=True,
        ) as client:
            jobs = await _scrape_with_retry(scraper, client)

        new_count = await pipeline.process_new_jobs(jobs)
        finished_at = datetime.now(timezone.utc).isoformat()

        await pipeline.db.record_scrape_run(
            source_board=source,
            company=company,
            started_at=started_at,
            finished_at=finished_at,
            status="success",
            jobs_found=len(jobs),
            new_jobs=new_count,
        )

    except Exception as e:
        finished_at = datetime.now(timezone.utc).isoformat()
        log.warning(
            "scrape_failed",
            source_board=source,
            company=company,
            error=str(e),
        )
        await pipeline.db.record_scrape_run(
            source_board=source,
            company=company,
            started_at=started_at,
            finished_at=finished_at,
            status="failure",
            jobs_found=0,
            new_jobs=0,
            error_msg=str(e),
        )


class BatchRunner:
    """Processes companies in rotating batches.

    With 6,000+ companies and BATCH_SIZE=200, each batch run handles 200 companies.
    At 1.5s delay per request, one batch takes ~5 minutes.
    With a 30-minute interval, all companies get scraped every ~2.5 hours.
    """

    def __init__(self, companies: CompanyList) -> None:
        self._scrapers: list[BaseScraper] = []

        for slug in companies.greenhouse:
            self._scrapers.append(GreenhouseScraper(board_token=slug, company_name=slug))
        for slug in companies.lever:
            self._scrapers.append(LeverScraper(company_slug=slug, company_name=slug))
        for slug in companies.ashby:
            self._scrapers.append(AshbyScraper(company_slug=slug, company_name=slug))

        self._offset = 0
        log.info(
            "batch_runner_initialized",
            total_scrapers=len(self._scrapers),
            greenhouse=len(companies.greenhouse),
            lever=len(companies.lever),
            ashby=len(companies.ashby),
            batch_size=BATCH_SIZE,
        )

    async def run_batch(self, pipeline: JobPipeline) -> None:
        """Run the next batch of scrapers."""
        total = len(self._scrapers)
        if total == 0:
            return

        batch = []
        for i in range(BATCH_SIZE):
            idx = (self._offset + i) % total
            batch.append(self._scrapers[idx])
        self._offset = (self._offset + BATCH_SIZE) % total

        log.info(
            "batch_started",
            batch_size=len(batch),
            offset=self._offset,
            total_companies=total,
        )

        total_new = 0
        failures = 0
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={"User-Agent": "JobHunterBot/1.0"},
            follow_redirects=True,
        ) as client:
            for scraper in batch:
                started_at = datetime.now(timezone.utc).isoformat()
                company = getattr(scraper, "company_name", None)
                source = scraper.source_name
                try:
                    jobs = await _scrape_with_retry(scraper, client)
                    new_count = await pipeline.process_new_jobs(jobs)
                    total_new += new_count

                    await pipeline.db.record_scrape_run(
                        source_board=source,
                        company=company,
                        started_at=started_at,
                        finished_at=datetime.now(timezone.utc).isoformat(),
                        status="success",
                        jobs_found=len(jobs),
                        new_jobs=new_count,
                    )
                except Exception as e:
                    failures += 1
                    log.warning(
                        "scrape_failed",
                        source_board=source,
                        company=company,
                        error=str(e),
                    )
                    await pipeline.db.record_scrape_run(
                        source_board=source,
                        company=company,
                        started_at=started_at,
                        finished_at=datetime.now(timezone.utc).isoformat(),
                        status="failure",
                        jobs_found=0,
                        new_jobs=0,
                        error_msg=str(e),
                    )

                await asyncio.sleep(REQUEST_DELAY)

        log.info(
            "batch_completed",
            new_jobs=total_new,
            failures=failures,
            batch_size=len(batch),
        )


async def build_scheduler(
    cache_dir: Path, pipeline: JobPipeline
) -> AsyncIOScheduler:
    """Build scheduler with auto-synced company lists."""
    # Sync company lists from GitHub
    companies = await sync_companies(cache_dir)

    scheduler = AsyncIOScheduler()

    # Batch runner for Greenhouse + Lever + Ashby
    batch_runner = BatchRunner(companies)
    scheduler.add_job(
        batch_runner.run_batch,
        "interval",
        minutes=30,
        args=[pipeline],
        id="batch_ats_scrape",
        name="Batch ATS Scrape (Greenhouse + Lever + Ashby)",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=5),
    )

    # HN Who is Hiring — every 6 hours
    hn_scraper = HackerNewsScraper()
    scheduler.add_job(
        run_scraper,
        "interval",
        hours=6,
        args=[hn_scraper, pipeline],
        id="hackernews_who_is_hiring",
        name="HN Who is Hiring",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=10),
    )

    # Re-sync company lists daily
    scheduler.add_job(
        _resync_companies,
        "interval",
        hours=24,
        args=[cache_dir, batch_runner],
        id="company_list_sync",
        name="Sync Company Lists from GitHub",
        next_run_time=datetime.now(timezone.utc) + timedelta(hours=24),
    )

    log.info(
        "scheduler_built",
        total_companies=companies.total,
        greenhouse=len(companies.greenhouse),
        lever=len(companies.lever),
        ashby=len(companies.ashby),
    )

    return scheduler


async def _resync_companies(cache_dir: Path, batch_runner: BatchRunner) -> None:
    """Re-sync company lists and update the batch runner."""
    companies = await sync_companies(cache_dir)
    batch_runner.__init__(companies)  # type: ignore[misc]
    log.info("company_lists_resynced", total=companies.total)
