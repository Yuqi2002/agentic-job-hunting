"""E2E test: detect a job → generate tailored resume → send to Discord."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import yaml

from src.config import settings
from src.detection.greenhouse import GreenhouseScraper
from src.filter.matcher import JobMatcher
from src.resume import generate_resume


MASTER = yaml.safe_load(Path("data/master_resume.yaml").read_text())


async def main() -> None:
    # ── Step 1: Detect a matching job ──────────────────────────────
    print("Fetching jobs from Anthropic...")
    scraper = GreenhouseScraper(board_token="anthropic", company_name="Anthropic")
    async with httpx.AsyncClient(timeout=60.0) as client:
        jobs = await scraper.fetch_jobs(client)

    matcher = JobMatcher(settings)
    target_job = next(
        (
            j
            for j in jobs
            if matcher.match(j.title, j.location, j.description_text).matched
            and "software engineer" in j.title.lower()
            and "senior" not in j.title.lower()
            and "staff" not in j.title.lower()
        ),
        None,
    )

    if not target_job:
        print("No matching job found!")
        return

    job_data = {
        "title": target_job.title,
        "company": target_job.company_name,
        "location": target_job.location,
        "url": target_job.url,
        "description": target_job.description_text or "",
    }
    print(f"Selected: {job_data['title']} @ {job_data['company']}")

    # ── Steps 2-4: Generate tailored resume ────────────────────────
    pdf_bytes = generate_resume(job_data, MASTER, settings.openai_api_key)
    Path("data/tailored_resume.pdf").write_bytes(pdf_bytes)
    print(f"PDF generated: {len(pdf_bytes):,} bytes")

    # ── Step 5: Send to Discord ────────────────────────────────────
    print("Sending to Discord...")
    embed = {
        "title": job_data["title"],
        "description": f"**{job_data['company']}** — {job_data['location']}",
        "url": job_data["url"],
        "color": 0x5865F2,
    }

    async with httpx.AsyncClient() as http:
        resp = await http.post(
            settings.discord_webhook_url,
            data={"payload_json": json.dumps({"embeds": [embed]})},
            files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
        )

    if resp.status_code in (200, 204):
        print("Sent to Discord!")
    else:
        print(f"Discord error {resp.status_code}: {resp.text}")


if __name__ == "__main__":
    asyncio.run(main())
