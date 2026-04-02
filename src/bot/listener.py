"""Discord bot — listens for ✅ reactions and triggers resume generation."""
from __future__ import annotations

import re
from pathlib import Path

import discord
import yaml

from src.db import Database
from src.logging import get_logger
from src.notify.discord import DiscordNotifier
from src.resume import generate_resume

log = get_logger("bot")

APPROVE_EMOJI = "✅"
MASTER_RESUME_PATH = Path("data/master_resume.yaml")


def _make_filename(company: str, title: str) -> str:
    """Generate a clean filename: Company_JobTitle_Resume.pdf"""
    def clean(s: str) -> str:
        s = re.sub(r"[^\w\s-]", "", s)
        return re.sub(r"\s+", "_", s.strip())

    return f"{clean(company)}_{clean(title)}_Resume.pdf"


class JobHunterBot(discord.Client):
    def __init__(
        self,
        db: Database,
        notifier: DiscordNotifier,
        openai_api_key: str,
        channel_id: int,
        bot_token: str,
    ) -> None:
        # reactions = GUILD_MESSAGE_REACTIONS (non-privileged)
        intents = discord.Intents.none()
        intents.guilds = True
        intents.reactions = True
        super().__init__(intents=intents)
        self.db = db
        self.notifier = notifier
        self.openai_api_key = openai_api_key
        self.channel_id = channel_id
        self.bot_token = bot_token
        self.master: dict = yaml.safe_load(MASTER_RESUME_PATH.read_text())

    async def on_ready(self) -> None:
        log.info("discord_bot_ready", user=str(self.user))

        # Diagnostic: check if the bot can see the target channel
        channel = self.get_channel(self.channel_id)
        if channel is None:
            log.error(
                "target_channel_not_found",
                channel_id=self.channel_id,
                hint="Bot may not have VIEW_CHANNEL permission or wrong channel ID",
            )
        else:
            perms = channel.permissions_for(channel.guild.me)
            log.info(
                "target_channel_found",
                channel_name=channel.name,
                can_read=perms.read_messages,
                can_send=perms.send_messages,
                can_read_history=perms.read_message_history,
                can_add_reactions=perms.add_reactions,
            )

        # List all guilds and channels the bot can see
        for guild in self.guilds:
            visible = [c.name for c in guild.channels if hasattr(c, 'permissions_for') and c.permissions_for(guild.me).read_messages]
            log.info("guild_visible", guild=guild.name, visible_channels=visible[:10])

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Fires when any reaction is added to any message the bot can see."""
        # Debug: log ALL incoming reactions so we can diagnose issues
        log.info(
            "reaction_received_raw",
            emoji=str(payload.emoji),
            channel_id=payload.channel_id,
            message_id=payload.message_id,
            user_id=payload.user_id,
            expected_channel=self.channel_id,
            emoji_match=str(payload.emoji) == APPROVE_EMOJI,
            channel_match=payload.channel_id == self.channel_id,
        )

        if str(payload.emoji) != APPROVE_EMOJI:
            return
        if payload.channel_id != self.channel_id:
            log.warning(
                "reaction_wrong_channel",
                got=payload.channel_id,
                expected=self.channel_id,
            )
            return
        if payload.user_id == self.user.id:
            return

        message_id = str(payload.message_id)
        log.info("reaction_received", message_id=message_id, emoji=str(payload.emoji))

        # Look up the job by message ID
        job = await self.db.get_job_by_message_id(message_id)
        if not job:
            log.debug("reaction_no_job_found", message_id=message_id)
            return

        # Skip if already approved or resume already sent
        if job.get("approval_status") in ("approved", "resume_sent"):
            log.info(
                "reaction_job_already_processed",
                job_id=job["id"],
                status=job.get("approval_status"),
            )
            return

        log.info(
            "job_approved",
            job_id=job["id"],
            company=job["company_name"],
            title=job["title"],
        )

        await self.db.mark_approved(job["id"])

        # Build job_data dict for generate_resume
        job_data = {
            "title": job["title"],
            "company": job["company_name"],
            "location": job.get("location") or "",
            "url": job["url"],
            "description": job.get("description_text") or "",
        }

        try:
            pdf_bytes = generate_resume(job_data, self.master, self.openai_api_key)
            filename = _make_filename(job["company_name"], job["title"])

            log.info(
                "resume_generated",
                company=job["company_name"],
                title=job["title"],
                bytes=len(pdf_bytes),
                filename=filename,
            )

            sent = await self.notifier.reply_with_resume(
                channel_id=str(self.channel_id),
                message_id=message_id,
                pdf_bytes=pdf_bytes,
                filename=filename,
                bot_token=self.bot_token,
            )

            if sent:
                await self.db.mark_resume_sent(job["id"])
                log.info(
                    "resume_sent",
                    company=job["company_name"],
                    title=job["title"],
                )

        except Exception as e:
            log.error(
                "resume_generation_failed",
                job_id=job["id"],
                company=job["company_name"],
                error=str(e),
            )
