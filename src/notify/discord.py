from __future__ import annotations

import asyncio

import httpx

from src.logging import get_logger

log = get_logger("discord")

# Discord rate limit: 30 requests/minute per webhook
RATE_LIMIT_DELAY = 2.0  # seconds between messages

# Colour scale for match percentage
def _match_colour(pct: int) -> int:
    if pct >= 70:
        return 0x57F287  # green
    if pct >= 40:
        return 0xFEE75C  # yellow
    return 0xED4245      # red


class DiscordNotifier:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url
        self._semaphore = asyncio.Semaphore(1)

    async def send_job(
        self,
        job: dict,
        total_comp: str | None = None,
        match_pct: int | None = None,
        match_keywords: list[str] | None = None,
    ) -> str | None:
        """Send a job summary embed. Returns Discord message ID if successful."""
        if not self.webhook_url:
            log.warning("discord_webhook_not_configured")
            return None

        pct = match_pct or 0
        comp = total_comp or "Not listed"
        keywords = match_keywords or []

        embed = {
            "title": f"{job['company_name']} — {job['title']}",
            "url": job["url"],
            "color": _match_colour(pct),
            "fields": [
                {
                    "name": "📍 Location",
                    "value": job.get("location") or "Remote",
                    "inline": True,
                },
                {
                    "name": "💰 Total Comp",
                    "value": comp,
                    "inline": True,
                },
                {
                    "name": f"🎯 Resume Match — {pct}%",
                    "value": ", ".join(keywords) if keywords else "See job link",
                    "inline": False,
                },
            ],
            "footer": {
                "text": "React with ✅ to generate a tailored resume"
            },
        }

        payload = {"embeds": [embed]}

        async with self._semaphore:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                    # ?wait=true makes Discord return the created message (with ID)
                    resp = await client.post(
                        self.webhook_url + "?wait=true", json=payload
                    )

                    if resp.status_code == 429:
                        retry_after = resp.json().get("retry_after", 5)
                        log.warning("discord_rate_limited", retry_after=retry_after)
                        await asyncio.sleep(retry_after)
                        resp = await client.post(
                            self.webhook_url + "?wait=true", json=payload
                        )

                    resp.raise_for_status()
                    message_id = str(resp.json().get("id", ""))

                log.info(
                    "discord_notification_sent",
                    company=job["company_name"],
                    title=job["title"],
                    match_pct=pct,
                    message_id=message_id,
                )
                await asyncio.sleep(RATE_LIMIT_DELAY)
                return message_id or None

            except Exception as e:
                log.error(
                    "discord_notification_failed",
                    company=job.get("company_name"),
                    error=str(e),
                )
                return None

    async def reply_with_resume(
        self,
        channel_id: str,
        message_id: str,
        pdf_bytes: bytes,
        filename: str,
        bot_token: str,
    ) -> bool:
        """Reply to a specific message with a resume PDF using the bot token."""
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        headers = {"Authorization": f"Bot {bot_token}"}

        payload = {"message_reference": {"message_id": message_id}}

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            try:
                resp = await client.post(
                    url,
                    headers=headers,
                    data={"payload_json": __import__("json").dumps(payload)},
                    files={"files[0]": (filename, pdf_bytes, "application/pdf")},
                )
                resp.raise_for_status()
                log.info("resume_reply_sent", message_id=message_id, filename=filename)
                return True
            except Exception as e:
                log.error("resume_reply_failed", message_id=message_id, error=str(e))
                return False
