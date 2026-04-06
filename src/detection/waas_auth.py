"""Work at a Startup (YC) — authentication and session management.

Usage (one-time setup):
    uv run python -m src.detection.waas_auth

This opens a headless Chromium browser, logs in via YC SSO, and saves:
  - data/waas_cookies.json   — session cookies (valid for weeks)
  - data/waas_algolia_key.txt — Algolia secured key (refresh each login)

The scraper (workatastartup.py) loads these files and uses httpx — no
browser needed per scrape cycle. Re-run this script when cookies expire
(scraper will log a warning and skip gracefully).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from src.logging import get_logger

log = get_logger("waas_auth")

COOKIES_PATH = Path("data/waas_cookies.json")       # legacy, kept for compat
STORAGE_STATE_PATH = Path("data/waas_state.json")   # Playwright full state (cookies + localStorage)
ALGOLIA_KEY_PATH = Path("data/waas_algolia_key.txt")

YC_SSO_URL = "https://account.ycombinator.com/?continue=https%3A%2F%2Fwww.workatastartup.com%2F"
WAAS_HOME = "https://www.workatastartup.com"


async def login_and_save(username: str, password: str) -> tuple[list[dict], str]:
    """Login via YC SSO and persist cookies + Algolia key.

    Returns (cookies, algolia_key). Raises on failure.
    """
    from playwright.async_api import async_playwright

    COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        log.info("waas_login_start", url=YC_SSO_URL)
        await page.goto(YC_SSO_URL, wait_until="networkidle")

        # Fill YC SSO form
        await page.fill("#ycid-input", username)
        await page.fill("#password-input", password)

        # Click sign-in button
        await page.click("button[type=submit]")

        # Wait for the first navigation away from YC SSO.
        # Use wait_until='commit' to avoid blocking on client-side navigations.
        try:
            await page.wait_for_url("*workatastartup.com*", timeout=30000, wait_until="commit")
        except Exception:
            # Navigation may have already completed — verify by checking current URL
            if "workatastartup.com" not in page.url:
                raise RuntimeError(
                    "Login failed — never reached workatastartup.com. "
                    "Possible CAPTCHA or wrong credentials. Current URL: " + page.url
                )

        # Give the SPA a moment to settle (client-side redirects + Inertia hydration)
        await page.wait_for_timeout(3000)

        log.info("waas_login_success", url=page.url)

        # Save full browser state immediately after login — before any optional navigation
        await context.storage_state(path=str(STORAGE_STATE_PATH))
        log.info("waas_state_saved", path=str(STORAGE_STATE_PATH))

        # Optionally navigate to companies page to extract Algolia key (best-effort)
        algolia_key: str = ""
        try:
            algolia_key = await page.evaluate("window.AlgoliaOpts && window.AlgoliaOpts.key || ''")
            if not algolia_key:
                await page.goto(
                    f"{WAAS_HOME}/companies?role=eng&layout=list",
                    wait_until="networkidle",
                    timeout=20000,
                )
                algolia_key = await page.evaluate("window.AlgoliaOpts && window.AlgoliaOpts.key || ''")
        except Exception as e:
            log.warning("waas_algolia_key_extract_failed", error=str(e))

        # Also save cookies separately (for httpx fallback / inspection)
        cookies = await context.cookies()
        await browser.close()

    # Persist cookies to disk (legacy)
    COOKIES_PATH.write_text(json.dumps(cookies, indent=2))
    log.info("waas_cookies_saved", path=str(COOKIES_PATH), count=len(cookies))

    if algolia_key:
        ALGOLIA_KEY_PATH.write_text(algolia_key)
        log.info("waas_algolia_key_saved", path=str(ALGOLIA_KEY_PATH))
    else:
        log.warning("waas_algolia_key_not_found")

    return cookies, algolia_key


def load_auth_state() -> tuple[dict[str, str], str] | None:
    """Load saved cookies and Algolia key from disk.

    Returns (cookie_header_dict, algolia_key) or None if not found.
    cookie_header_dict maps cookie name → value for use with httpx.
    """
    if not COOKIES_PATH.exists():
        return None

    cookies_list: list[dict] = json.loads(COOKIES_PATH.read_text())
    # Convert to {name: value} dict for httpx
    cookies = {c["name"]: c["value"] for c in cookies_list}

    algolia_key = ""
    if ALGOLIA_KEY_PATH.exists():
        algolia_key = ALGOLIA_KEY_PATH.read_text().strip()

    return cookies, algolia_key


if __name__ == "__main__":
    import asyncio
    import getpass
    import os

    from dotenv import load_dotenv

    load_dotenv()

    username = os.getenv("WAAS_YC_USERNAME") or input("YC username (ycid): ").strip()
    password = os.getenv("WAAS_YC_PASSWORD") or getpass.getpass("YC password: ")

    if not username or not password:
        print("Username and password required.")
        sys.exit(1)

    async def main() -> None:
        cookies, key = await login_and_save(username, password)
        print(f"\nSaved {len(cookies)} cookies to {COOKIES_PATH}")
        if key:
            print(f"Algolia key saved to {ALGOLIA_KEY_PATH}")
            print(f"  Key prefix: {key[:20]}...")
        else:
            print("WARNING: Algolia key not found — scraper will use keyword search fallback.")
        print("\nSetup complete. The scraper will use these credentials automatically.")

    asyncio.run(main())
