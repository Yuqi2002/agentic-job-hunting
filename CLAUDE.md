# Agentic Job Hunting System

## Project Overview
An automated pipeline that detects job postings in near-real-time from ATS APIs (Greenhouse, Lever, Ashby) and curated sources (HN), filters by role/location/experience, generates job summaries with match percentages, sends rich Discord embeds, and waits for human approval via ✅ reaction before generating tailored resumes.

## Tech Stack
- **Language**: Python 3.11+
- **AI**: OpenAI GPT-4o mini for summaries + resume generation (selection + ATS optimization)
  - Job summaries: ~$0.92/month (259 jobs/day)
  - Resume generation: ~$10.20/month (on approval only)
- **HTTP**: httpx + selectolax + Playwright (for JS-rendered / auth-gated pages)
- **Scheduler**: APScheduler 3.x (AsyncIOScheduler)
- **Database**: SQLite WAL mode + aiosqlite
- **Resume Output**: LaTeX template (user's Overleaf template) → pdflatex → .pdf
- **Discord**: discord.py 2.7+ (bot for reaction listening) + httpx webhooks (job summaries)
- **Runtime**: Hetzner VPS (always-on, systemd service)
- **Logging**: structlog → JSON stdout → Promtail → Grafana Loki
- **Deps**: uv for package management

## Current Status
- **Phase 1 COMPLETE**: Detection → Filter → Notify pipeline built and tested
- **Phase 2 COMPLETE**: AI resume generation with GPT-4o mini + human-in-the-loop approval
  - **Job Summary Generation** (`src/resume/summarizer.py`):
    - GPT-4o mini extracts: company, title, total compensation, resume match %
    - Match % calculated by comparing job keywords to master resume skills

  - **Rich Discord Embeds** with reaction-based approval:
    - Color-coded by match % (🟢 70%+, 🟡 40-70%, 🔴 <40%)
    - Shows: company, location, compensation, match %, relevant keywords
    - Prompt: "React with ✅ to generate resume"

  - **URL-Based Resume Generation** (NEW):
    - Post job links to Discord → bot instantly fetches + tailors resume
    - Supports Greenhouse, Lever, Ashby URLs (auto-detects ATS)
    - Falls back to generic web scraping for unknown job boards
    - Message content intent required (enabled in Discord settings)

  - **Human-in-the-Loop Approval System** (`src/bot/listener.py`):
    - Discord bot listens for ✅ reactions on webhook embeds
    - Discord bot listens for URLs posted in messages
    - On approval: instantly triggers resume generation
    - Names PDF after job: `Company_JobTitle_Resume.pdf`
    - Replies to original message with PDF attached

  - **Resume Pipeline** (`src/resume/`):
    1. `selector.py` — GPT-4o mini picks experiences/projects (IDs only)
    2. `builder.py` — Pure Python: copies text verbatim from master resume by ID
    3. `ats.py` — GPT-4o mini: optimizes bullets for ATS (7 rules)
    4. `compiler.py` — Pure Python: LaTeX escape + render + compile

  - **12+ comprehensive tests** (all passing) with full visibility
  - **e2e tested**: Full approval flow validated (detect → summarize → approve → generate → reply)
  - **e2e tested**: URL-based resume generation tested live
  - See `RESUME_PIPELINE.md` for detailed flow and test results

## Target Roles
- New Grad to Mid-level SWE (0-4 years)
- AI/ML Engineer — open to all companies and startups
- Forward Deployed Engineer, Solutions Engineer, Sales Engineer
- Location: Remote + configurable target cities

## Data Sources

### Implemented (Phase 1 + Phase 3 partial)
1. **Greenhouse Boards API** — `boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` (free, no auth, JSON)
2. **Lever Postings API** — `api.lever.co/v0/postings/{slug}?mode=json` (free, no auth, JSON)
3. **Ashby Posting API** — `api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true` (free, no auth, JSON)
4. **HN Who is Hiring** — HN Algolia API (`hn.algolia.com/api/v1/`) (free, monthly threads)
5. **FWDDeploy.com** — `fwddeploy.com/jobs.json` (free, no auth, ~350 FDE-specific jobs, every 6h)
6. **Work at a Startup (YC)** — Playwright-based, requires one-time login (see setup below), every 6h
7. **Remote OK** — `remoteok.com/api` (free, no auth, ~100 remote tech jobs, every 6h)
8. **Remotive** — `remotive.com/api/remote-jobs` (free, no auth, low volume ~20 jobs, every 6h)

### Company Discovery
- **Auto-synced from [Feashliaa/job-board-aggregator](https://github.com/Feashliaa/job-board-aggregator)**
- 6,262 companies: 4,516 Greenhouse + 947 Lever + 799 Ashby
- Pulled from GitHub on startup, cached locally in `data/cache/`
- Re-synced every 24 hours automatically
- No manual `companies.yaml` — fully automated discovery

### Researched and Rejected (Phase 3)
- **Wellfound** — auth-gated, aggressive anti-bot (Cloudflare), declining quality
- **Otta / Welcome to the Jungle** — auth-gated GraphQL, Euro-focused, low US startup volume
- **workatastartup.com (YC) Algolia API** — secured key has `tagFilters=[["none"]]` even after login; use Playwright interception instead (implemented)
- **The Muse** — 494k jobs but dominated by Walmart/retail/enterprise, poor startup signal
- **Himalayas** — 98k jobs but `q` filter broken, returns unrelated enterprise roles
- **Jobicy** — 401 unauthorized
- **Arbeitnow** — 25 jobs, Germany-focused
- **levels.fyi** — paid enterprise API only
- **SimplifyJobs GitHub** — Markdown tables, not machine-readable
- **Triplebyte** — defunct
- **LinkedIn/Indeed** — oversaturated, aggressive anti-bot, no public API

### Future (Phase 3 remaining)
- iCIMS API (many enterprise companies; FWDDeploy surfaces these but no direct scraper yet)
- Workday API (same — high volume but complex auth)

## Architecture — 6 Layer Pipeline

### Layer 1: Detection
- **Batch processing**: 200 companies per batch, every 30 minutes, 1.5s delay between requests
- Full cycle through all 6,262 companies takes ~2.5 hours
- HN: every 6 hours, finds latest thread via Algolia `author_whoishiring` tag
- FWDDeploy, Remote OK, Remotive, Work at a Startup: every 6 hours (single API call each)
- Dedup: exact on `UNIQUE(source_board, external_id)` — SQLite handles it via INSERT OR IGNORE
- Track scrape runs in `scrape_runs` table

### Layer 2: Filter
- Role matching: configurable keywords in .env (SWE, AI/ML, FDE, Sales Eng)
- Also checks abbreviations (swe, sde, mle)
- Location: "remote" auto-matches + target cities substring match
- Experience: rejects "senior staff", "principal", "director"; accepts "new grad", "junior", "0-4 years"
- Defaults to MATCH if experience level is unclear (better to over-include)
- Store match/reject reason in `filter_reason`

### Layer 3: Job Summary + Discord Notification
- **Summarization** via `src/resume/summarizer.py`:
  - GPT-4o mini extracts: company, title, total compensation, match %
  - Match % = (keywords from job found in master resume) / (total job keywords) × 100
  - Returns: `{total_comp, match_pct, match_keywords}`

- **Discord Rich Embed**:
  - Color-coded by match %: 🟢 (70%+), 🟡 (40-70%), 🔴 (<40%)
  - Fields: Location, Compensation, Resume Match %, Keywords
  - Includes message: "React with ✅ to generate resume"
  - **Stores message ID** in database for reaction tracking

### Layer 4: Human-in-the-Loop Approval (NEW)
- **Discord Bot Listener** (`src/bot/listener.py`):
  - Runs alongside the scheduler
  - **Reaction-based**: Listens for ✅ reactions on webhook embeds
  - **URL-based**: Listens for job URLs posted directly in channel (NEW)
  - Requires: `DISCORD_BOT_TOKEN` and `DISCORD_CHANNEL_ID` in `.env`
  - Message content intent required (enabled in Discord Developer Portal)

- **Resume Generation Triggers**:
  - **✅ Reaction**: React to auto-detected job summaries
  - **URL Post**: Post any Greenhouse/Lever/Ashby URL (auto-detected, instant generation)
  - `src/detection/url_scraper.py` fetches job details, auto-detects ATS
  - Only triggered when user explicitly approves (saves tokens on rejected jobs)

### Layer 5: Resume Generation (COMPLETE — Phase 2)
**Entry point**: `src/resume/__init__.py` — exports `generate_resume(job, master, api_key) -> bytes`

**4-step resume pipeline** (modular design in `src/resume/`):

1. **Step 1 — Selection** via `src/resume/selector.py`
   - GPT-4o mini analyzes job description + compact master resume summary
   - Selects 2-3 relevant experiences, 1-2 projects, exactly 1 leadership entry, relevant skills
   - **KEY**: Returns `SelectionManifest` with IDs + bullet indices ONLY — no text
   - Model: `gpt-4o-mini` (~800 tokens input, ~200 output)

2. **Step 2 — Building** via `src/resume/builder.py`
   - Pure Python: zero network calls, 100% deterministic
   - Looks up each ID in `data/master_resume.yaml`
   - Copies bullet text verbatim at specified indices
   - Returns `ResumeContent` with all text fields populated (no modification)

3. **Step 3 — ATS Optimization** via `src/resume/ats.py`
   - GPT-4o mini optimizes bullets for ATS keyword matching and structure
   - 7 rules: keyword injection, action verb strength, XYZ structure, special char safety, skills ordering, date consistency, guardrails
   - **KEY**: Returns same JSON structure with optimized text (no company/title/date/location changes)
   - Model: `gpt-4o-mini` (~3000 tokens input, ~1000 output)

4. **Step 4 — Compilation** via `src/resume/compiler.py`
   - Pure Python: LaTeX escaping + Jinja2 render + pdflatex compile
   - Applies `escape_latex()` to ALL text fields: bullets, titles, descriptions, skill values
   - Renders `templates/resume.tex` with escaped content
   - Runs `/Library/TeX/texbin/pdflatex` in temp directory
   - Returns PDF as bytes

### Layer 6: Quality Gate
- Currently no separate quality gate — ATS optimization pass serves this role

### Layer 7: Notification (Async Reply to Approved Jobs)
- After user approves via ✅: bot replies to original Discord message with PDF
- Direct reply (thread) keeps conversation organized
- PDF filename: `Company_JobTitle_Resume.pdf`
- Marks job as `approval_status = 'resume_sent'` in database

## Key Files

### Core Pipeline
```
src/resume/
├── __init__.py             # Public API: generate_resume(job, master, api_key) -> bytes
├── types.py                # Shared dataclasses (SelectionManifest, ResumeContent, etc.)
├── selector.py             # GPT-4o mini: select experience/project/skill IDs (no text)
├── builder.py              # Pure Python: copy text verbatim by ID from master resume
├── ats.py                  # GPT-4o mini: optimize bullets for ATS (7 rules)
├── compiler.py             # Pure Python: LaTeX escape + render + pdflatex → PDF bytes
└── summarizer.py           # GPT-4o mini: extract comp + calculate match % for jobs

src/bot/
└── listener.py             # Discord bot: listens for ✅ reactions, listens for URLs in messages

src/detection/
├── url_scraper.py          # Fetch individual job from URL (Greenhouse, Lever, Ashby, or generic)
├── fwddeploy.py            # FWDDeploy.com — free JSON API, ~350 FDE-specific jobs
├── remoteok.py             # Remote OK — free JSON API, ~100 remote tech jobs
├── remotive.py             # Remotive — free JSON API, low volume remote jobs
├── workatastartup.py       # Work at a Startup (YC) — Playwright session + /companies/fetch interception
└── waas_auth.py            # YC SSO login script — run once to save data/waas_state.json

tests/
├── test_resume_pipeline.py # 11 comprehensive tests (all passing) with full visibility
├── test_e2e_approval.py    # Full approval flow test: detect → summarize → approve → generate → reply
├── test_url_resume_e2e.py  # End-to-end URL-based resume generation test
└── test_gpt4o_mini_comparison.py # Haiku vs GPT-4o mini quality comparison
```

### Detection & Filtering
```
src/
├── main.py                 # Entry point — async, graceful SIGINT/SIGTERM shutdown
├── config.py               # pydantic-settings, loads .env, exposes cities_list/roles_list properties
├── logging.py              # structlog JSON config
├── db.py                   # SQLite WAL + aiosqlite, schema auto-creation
├── pipeline.py             # Orchestrates: insert → filter → notify
├── detection/
│   ├── base.py             # RawJob dataclass + BaseScraper ABC
│   ├── greenhouse.py       # Greenhouse Boards API scraper
│   ├── lever.py            # Lever Postings API scraper
│   ├── ashby.py            # Ashby Posting API scraper
│   ├── hackernews.py       # HN Who is Hiring parser (Algolia API)
│   ├── url_scraper.py      # Fetch single job from URL (auto-detects ATS)
│   ├── company_sync.py     # Auto-sync company lists from Feashliaa GitHub repo
│   └── scheduler.py        # APScheduler + BatchRunner (200 companies/batch)
├── filter/
│   └── matcher.py          # Role, location, experience matching
└── notify/
    └── discord.py          # Discord webhook for job summaries + bot reply with PDF

data/
├── master_resume.yaml      # Full experience inventory with IDs and tagged metadata
├── cache/                  # (gitignored) Cached company lists from GitHub
│   ├── greenhouse_companies.json
│   ├── lever_companies.json
│   └── ashby_companies.json
├── jobs.db                 # (gitignored) SQLite database
├── tailored_resume.pdf     # (gitignored) Latest generated resume PDF
├── debug_resume.tex        # (gitignored) Saved on LaTeX compile failure for debugging
├── waas_state.json         # (gitignored) Playwright browser state for workatastartup.com
├── waas_cookies.json       # (gitignored) Raw cookies saved at login (legacy/inspection)
└── waas_algolia_key.txt    # (gitignored) Algolia key (restricted; not used by scraper)

templates/
└── resume.tex              # LaTeX template with Jinja2 variables (confirmed working)

test_resume_e2e.py          # Simple e2e: detect job → generate resume → send to Discord (via webhook)
test_e2e_approval.py        # Full approval flow: detect → summarize → send embed → listen for ✅ → generate → reply
test_filter_scale.py        # Estimate daily volume: sample companies, extrapolate total, estimate costs
RESUME_PIPELINE.md          # Detailed pipeline flow, test results, and guarantees
```

## Work at a Startup (YC) — One-Time Setup
The `workatastartup.com` scraper requires a YC account (same as HN / Bookface login).

```bash
# Add to .env:
WAAS_YC_USERNAME=your_ycid
WAAS_YC_PASSWORD=your_password

# Run once to save session state:
uv run python -m src.detection.waas_auth
```

This opens headless Chromium, logs in via YC SSO, and saves `data/waas_state.json`. The recurring scraper loads this state — no browser needed per scrape cycle. Re-run when cookies expire (scraper logs `waas_session_expired`; typically monthly).

**If reCAPTCHA fires**: Run from a local machine (same IP as normal browser usage), then copy `data/waas_state.json` to the VPS.

## Config (.env)
```
# OpenAI API
OPENAI_API_KEY=sk-proj-...

# Discord — Webhook for job summaries (one-way)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Discord — Bot for reaction-based approval (optional but recommended)
DISCORD_BOT_TOKEN=...               # Get from Discord Developer Portal
DISCORD_CHANNEL_ID=123456789012345  # Right-click channel → Copy ID

# Job filtering
TARGET_CITIES=San Francisco,New York,Seattle,Austin
TARGET_ROLES=software engineer,ai engineer,ml engineer,machine learning engineer,forward deployed engineer,solutions engineer,sales engineer
MAX_EXPERIENCE_YEARS=4

# System
DB_PATH=data/jobs.db
LOG_LEVEL=INFO
CACHE_DIR=data/cache
ANTHROPIC_API_KEY=sk-ant-...        # Optional (kept for reference, not used in resume pipeline)

# Work at a Startup (YC) — optional, enables workatastartup.com scraper
WAAS_YC_USERNAME=your_ycid          # Same as HN / Bookface login
WAAS_YC_PASSWORD=your_password      # Run waas_auth.py after setting these
```

**IMPORTANT**:
- `TARGET_CITIES` and `TARGET_ROLES` are plain comma-separated strings, NOT JSON arrays. Parsed via `settings.cities_list` / `settings.roles_list`.
- `DISCORD_BOT_TOKEN` + `DISCORD_CHANNEL_ID` are optional. If both are set, the bot enables human-in-the-loop approval. If missing, the system works with webhook-only notifications (no approval needed).

## Conventions
- `uv` for dependency management (`uv sync` to install, `uv run` to execute)
- Type hints on all functions
- Structured logging (JSON via structlog) — low-cardinality Loki labels only
- Config via `.env` file — use `settings.cities_list` / `settings.roles_list` (not `target_cities` raw string)
- Each layer is its own module under `src/`
- Retry with `tenacity` (exponential backoff + jitter)
- No manual review gates — fully automated pipeline

## Known Issues & Gotchas

### pydantic-settings + comma-separated lists
**Problem**: pydantic-settings v2 tries to JSON-parse `list[str]` fields from .env, so `TARGET_CITIES=San Francisco,New York` fails with `JSONDecodeError`.
**Solution**: Declare fields as `str` type in Settings, parse via `@property` methods (`cities_list`, `roles_list`). Do NOT use `list[str]` type for env vars that are comma-separated.

### Lever API — many companies migrated away
**Problem**: Most well-known companies (Netflix, Anthropic, Reddit, Figma, Flexport) return 404 or empty from Lever API. They've moved to Greenhouse or other ATS.
**Finding**: Lever has 947 companies in Feashliaa's list, but many return errors. The scraper handles this gracefully (logs warning, returns empty list). Greenhouse (4,516) and Ashby (799) are more reliable.

### Greenhouse API — board tokens are unpredictable
**Problem**: Token is NOT always the company name. E.g., Anduril's token is `andurilindustries`, not `anduril`. OpenAI, Notion, Ramp, Snap, Spotify, Uber had no working token with obvious names.
**Solution**: The Feashliaa repo handles discovery — we don't need to guess tokens.

### HN Who is Hiring — unstructured comment parsing
**Problem**: HN comments have no standard format. Most use "Company | Role | Location | ..." but many don't.
**Solution**: Three parsing strategies in `hackernews.py` (pipe-separated, regex, fallback). Some comments will be missed — acceptable tradeoff.

### uv not in PATH by default
**Problem**: After installing uv via curl, it's at `~/.local/bin/uv` which may not be in PATH.
**Solution**: `export PATH="$HOME/.local/bin:$PATH"` or source the shell profile.

### LaTeX escaping must be applied programmatically, not by Claude
**Problem**: Asking Claude to escape LaTeX special chars in bullet text is unreliable. The ATS optimization pass strips escaping added by the tailoring step. The two models fighting over escaping caused `% → \%` to get stripped, breaking pdflatex with "Misplaced alignment tab" and "File ended while scanning" errors.
**Solution**: Both tailoring and ATS prompts instruct Claude to output PLAIN TEXT with no LaTeX escaping. After the ATS pass, `escape_latex()` is called programmatically on every text field: `exp["bullets"]`, `proj["bullets"]`, `lead["title"]`, `lead["description"]`, `skill["category"]`, `skill["value"]`. Do NOT skip `skill["category"]` or `lead["title"]` — Claude renames them (e.g., "Infrastructure & Systems") and the `&` must be escaped.

### Claude never copies resume text
**Problem**: If Claude is asked to select AND copy text in the same pass, hallucination risk increases and you lose determinism. Changes to the master resume could be silently overridden.
**Solution**: `selector.py` returns ONLY IDs and bullet indices (no text). `builder.py` does all copying via pure Python lookup. This separation means: (1) Claude's job is purely ranking/relevance, (2) text is always verbatim, (3) changes to master_resume.yaml immediately reflect in the pipeline.

### Skills category keys are validated
**Problem**: Claude might invent new skill categories or miss expected ones, causing template rendering to fail.
**Solution**: `selector.py` validates that returned skills dict contains exactly these keys (any/all): `languages`, `frameworks`, `devops`, `certifications`. Unknown keys are rejected; missing keys are allowed (Claude can omit if irrelevant to JD).

### Date format must be consistent throughout
**Problem**: ATS systems miscalculate years of experience if dates are inconsistent ("2024--Present" vs "2024 -- Present" vs "2024-Present").
**Solution**: ATS prompt (Rule 6) enforces "Mon YYYY" format throughout (e.g., "Jan 2024"), with " -- " (spaces) as separator and "Present" for current roles. Compiler preserves these dates verbatim.

### Duplicate \documentclass in user's original LaTeX
**Problem**: The user's original resume.tex had two `\documentclass` declarations (lines 7 and 9), which causes compilation failure.
**Solution**: Fixed in `templates/resume.tex`. Watch for this if user provides updated Overleaf template.

### Discord Bot Setup (Human-in-the-Loop Approval)
**Problem**: The bot needs to listen for reactions on webhook-sent messages. Webhooks only send (one-way); bots receive (two-way).
**Solution**:
1. Create bot at https://discord.com/developers/applications → New Application
2. Add a Bot to the application
3. Enable Privileged Intents if needed (currently using non-privileged: `guilds` + `reactions`)
4. OAuth2 → URL Generator:
   - Scopes: `bot`
   - Permissions: Read Messages, Send Messages, Read History, Add Reactions
5. Add bot to server via generated URL
6. Get bot token and channel ID, add to `.env`
7. Bot starts automatically when `DISCORD_BOT_TOKEN` + `DISCORD_CHANNEL_ID` are set
**Key**: The bot and webhook can coexist — webhook sends initial summaries, bot replies with resumes.

### Work at a Startup — Algolia key is always restricted
**Problem**: `window.AlgoliaOpts.key` on workatastartup.com always contains `tagFilters=[["none"]]` — even when logged in. The auth-scoped key is fetched via a separate XHR after page load and is not accessible from window state.
**Solution**: Don't use Algolia directly. Instead, use Playwright with `context.storage_state` to restore the full session, navigate the companies page, and intercept the `/companies/fetch` POST responses that the React app fires naturally. The page does the Algolia search internally; we capture the results.

### Work at a Startup — YC SSO multi-step redirect
**Problem**: After clicking the login button, YC SSO does a server redirect to `workatastartup.com` followed immediately by an Inertia.js client-side navigation. Playwright's `wait_for_url` and `expect_navigation` both time out because they wait for `load` event on the second (client-side) navigation, which never fires.
**Solution**: Use `wait_for_url(..., wait_until="commit")` which returns as soon as the URL matches without waiting for a load event. Then `wait_for_timeout(3000)` to let Inertia settle.

### Work at a Startup — storage_state must be saved on workatastartup.com, not account.ycombinator.com
**Problem**: `context.storage_state()` must be called after the redirect completes. If saved while still on `account.ycombinator.com`, the restored context will lack `www.workatastartup.com` cookies and every `/companies` request will 302 to the homepage.
**Solution**: Call `storage_state()` only after `wait_for_url("*workatastartup.com*", ...)` confirms we're on the right domain.

### FWDDeploy — most jobs link to iCIMS/Workday, not Greenhouse/Lever/Ashby
**Note**: FWDDeploy is a pure aggregator. ~60% of its jobs link to ATS platforms not covered by the main batch scraper (iCIMS, Workday, Recruiterflow). This makes it genuinely additive — not duplicating what Greenhouse/Lever/Ashby already surface.

### Remote OK — returns ~100 jobs (not 20 as docs suggest)
**Note**: The `remoteok.com/api` endpoint returns more jobs than the 20 shown in their documentation. In practice, ~97 jobs per call. No pagination needed. Role filtering is handled by the existing filter layer — don't pre-filter at the API level as there's no reliable tag-based API filter.

## API Verification Commands
```bash
# Greenhouse
curl -s "https://boards-api.greenhouse.io/v1/boards/stripe/jobs" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['jobs']))"

# Lever
curl -s "https://api.lever.co/v0/postings/palantir?mode=json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))"

# Ashby
curl -s "https://api.ashbyhq.com/posting-api/job-board/1password?includeCompensation=true" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['jobs']))"

# HN Algolia — latest Who is Hiring thread
curl -s "https://hn.algolia.com/api/v1/search_by_date?query=%22who+is+hiring%22&tags=story,author_whoishiring&hitsPerPage=1"

# FWDDeploy
curl -s "https://www.fwddeploy.com/jobs.json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))"

# Remote OK
curl -s "https://remoteok.com/api" -H "Accept: application/json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len([x for x in d if 'id' in x]))"

# Work at a Startup (YC) — verify login state is still valid
uv run python -c "
import asyncio, httpx
from src.detection.workatastartup import WaaScraper
async def t():
    s = WaaScraper()
    async with httpx.AsyncClient(timeout=30.0) as c:
        jobs = await s.fetch_jobs(c)
    print(f'{len(jobs)} jobs found')
asyncio.run(t())
"
```

## Documentation

### For Users (Open Source)
- **`README.md`** — Complete guide: features, quick start, deployment, customization
- **`RESUME_PIPELINE.md`** — Detailed architecture, test results, full visibility into each module
- **`.env.example`** — Template for configuration

### For Developers
- **`CLAUDE.md`** (this file) — Implementation notes, design decisions, known gotchas
- **`plan.md`** — High-level project plan, phase breakdown, future roadmap
- **`tests/test_resume_pipeline.py`** — 11 comprehensive tests demonstrating exact behavior

### Research Docs
- `research/job_board_evaluation.md` — Board-by-board analysis with API details, verified tokens
- `research/scraping_architecture.md` — Scraping stack, scheduling, DB schema, logging design
- `research/resume_ai_pipeline.md` — Prompt architecture, ATS optimization, cost analysis
