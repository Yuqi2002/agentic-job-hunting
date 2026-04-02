from __future__ import annotations

import asyncio
import signal
from pathlib import Path

import yaml

from src.config import settings
from src.db import Database
from src.detection.scheduler import build_scheduler
from src.filter.matcher import JobMatcher
from src.logging import get_logger, setup_logging
from src.notify.discord import DiscordNotifier
from src.pipeline import JobPipeline

log = get_logger("main")

MASTER_RESUME_PATH = Path("data/master_resume.yaml")


async def main() -> None:
    setup_logging(settings.log_level)

    master: dict = {}
    if MASTER_RESUME_PATH.exists():
        master = yaml.safe_load(MASTER_RESUME_PATH.read_text())

    log.info("starting", config={
        "db_path": str(settings.db_path),
        "target_roles": settings.roles_list,
        "target_cities": settings.cities_list,
        "max_exp_years": settings.max_experience_years,
        "discord_configured": bool(settings.discord_webhook_url),
        "bot_configured": bool(settings.discord_bot_token),
        "openai_configured": bool(settings.openai_api_key),
    })

    db = Database(settings.db_path)
    await db.connect()

    matcher = JobMatcher(settings)
    notifier = DiscordNotifier(settings.discord_webhook_url)
    pipeline = JobPipeline(
        db=db,
        matcher=matcher,
        notifier=notifier,
        openai_api_key=settings.openai_api_key,
        master=master,
    )

    scheduler = await build_scheduler(settings.cache_dir, pipeline)
    scheduler.start()
    log.info("scheduler_started", job_count=len(scheduler.get_jobs()))

    # Graceful shutdown
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _shutdown(sig: signal.Signals) -> None:
        log.info("shutdown_signal_received", signal=sig.name)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown, sig)

    tasks: list[asyncio.Task] = []

    # Start Discord bot if configured
    if settings.discord_bot_token and settings.discord_channel_id:
        from src.bot.listener import JobHunterBot

        bot = JobHunterBot(
            db=db,
            notifier=notifier,
            openai_api_key=settings.openai_api_key,
            channel_id=settings.discord_channel_id,
            bot_token=settings.discord_bot_token,
        )
        bot_task = asyncio.create_task(bot.start(settings.discord_bot_token))
        tasks.append(bot_task)
        log.info("discord_bot_started", channel_id=settings.discord_channel_id)
    else:
        log.warning(
            "discord_bot_not_configured",
            hint="Set DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID in .env to enable reaction-based resume approval",
        )

    await stop_event.wait()

    log.info("shutting_down")
    for task in tasks:
        task.cancel()
    scheduler.shutdown(wait=False)
    await db.close()
    log.info("shutdown_complete")


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
