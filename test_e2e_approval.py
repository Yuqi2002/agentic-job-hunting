"""E2E test for the full human-in-the-loop approval flow.

Steps:
  1. Fetch real jobs from Anthropic
  2. Generate summaries (comp + match%) via GPT-4o mini
  3. Send 3 rich embeds to Discord
  4. Start the bot listener — react ✅ to any message to trigger resume generation
  5. Bot replies to that message with a named PDF

Press Ctrl+C to stop after testing.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import yaml

from src.config import settings
from src.db import Database
from src.detection.greenhouse import GreenhouseScraper
from src.filter.matcher import JobMatcher
from src.notify.discord import DiscordNotifier
from src.resume.summarizer import summarize

MASTER = yaml.safe_load(Path("data/master_resume.yaml").read_text())
TEST_DB_PATH = Path("data/test_approval.db")
NUM_JOBS = 3


async def send_job_summaries(db: Database, notifier: DiscordNotifier) -> list[str]:
    """Fetch jobs, generate summaries, send to Discord. Returns message IDs."""

    print("\nFetching jobs from Anthropic...")
    scraper = GreenhouseScraper(board_token="anthropic", company_name="Anthropic")
    async with httpx.AsyncClient(timeout=60.0) as client:
        jobs = await scraper.fetch_jobs(client)

    matcher = JobMatcher(settings)
    matching = [
        j for j in jobs
        if matcher.match(j.title, j.location, j.description_text or "").matched
        and "software engineer" in j.title.lower()
        and "senior" not in j.title.lower()
        and "staff" not in j.title.lower()
    ][:NUM_JOBS]

    if not matching:
        print("No matching jobs found!")
        return []

    print(f"Found {len(matching)} matching jobs. Sending to Discord...\n")

    message_ids: list[str] = []

    for job in matching:
        job_dict = {
            "title": job.title,
            "company": job.company_name,
            "location": job.location or "",
            "description": job.description_text or "",
        }

        print(f"  Summarising: {job.title} @ {job.company_name}...")
        summary = summarize(job_dict, MASTER, settings.openai_api_key)

        print(f"    Comp: {summary['total_comp']}")
        print(f"    Match: {summary['match_pct']}%  ({', '.join(summary['match_keywords'][:3])})")

        # Insert into test DB so the bot can find it by message ID
        from src.detection.base import RawJob
        raw = RawJob(
            source_board=job.source_board,
            external_id=job.external_id,
            url=job.url,
            title=job.title,
            company_name=job.company_name,
            location=job.location,
            description_text=job.description_text,
        )
        await db.insert_job(raw)

        # Find the DB record we just inserted
        cursor = await db.db.execute(
            "SELECT id FROM jobs WHERE source_board=? AND external_id=?",
            (job.source_board, job.external_id),
        )
        row = await cursor.fetchone()
        if not row:
            print("    ❌ DB insert failed, skipping")
            continue
        job_id = row["id"]

        # Mark as matched so the bot handles it
        await db.update_filter_status(job_id, "matched", "e2e test")

        # Send to Discord
        job_row = {
            "company_name": job.company_name,
            "title": job.title,
            "url": job.url,
            "location": job.location or "",
            "filter_reason": "e2e test",
            "source_board": job.source_board,
        }
        message_id = await notifier.send_job(
            job_row,
            total_comp=summary["total_comp"],
            match_pct=summary["match_pct"],
            match_keywords=summary["match_keywords"],
        )

        if message_id:
            await db.mark_notified(
                job_id,
                discord_message_id=message_id,
                total_comp=summary["total_comp"],
                match_pct=summary["match_pct"],
                match_keywords=summary["match_keywords"],
            )
            message_ids.append(message_id)
            print(f"    ✅ Sent! Message ID: {message_id}")
        else:
            print("    ❌ Failed to send")

    return message_ids


async def main() -> None:
    print("=" * 70)
    print("E2E APPROVAL FLOW TEST")
    print("=" * 70)

    db = Database(TEST_DB_PATH)
    await db.connect()

    notifier = DiscordNotifier(settings.discord_webhook_url)

    # Step 1-3: Send job summaries
    message_ids = await send_job_summaries(db, notifier)

    if not message_ids:
        print("No messages sent. Exiting.")
        await db.close()
        return

    print(f"\n{'=' * 70}")
    print(f"✅ {len(message_ids)} job summaries sent to Discord!")
    print(f"{'=' * 70}")
    print("\nNow starting bot listener...")
    print("→ Go to Discord and react ✅ to any message")
    print("→ The bot will generate a tailored resume and reply to that message")
    print("→ Press Ctrl+C to stop\n")

    # Step 4: Start the bot listener
    if not settings.discord_bot_token or not settings.discord_channel_id:
        print("❌ DISCORD_BOT_TOKEN or DISCORD_CHANNEL_ID not configured in .env")
        await db.close()
        return

    from src.bot.listener import JobHunterBot

    bot = JobHunterBot(
        db=db,
        notifier=notifier,
        openai_api_key=settings.openai_api_key,
        channel_id=settings.discord_channel_id,
        bot_token=settings.discord_bot_token,
    )

    try:
        await bot.start(settings.discord_bot_token)
    except KeyboardInterrupt:
        pass
    finally:
        await bot.close()
        await db.close()
        print("\nBot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
