# Job Board Research & Evaluation Report

> **Author**: @job-board-researcher
> **Date**: 2026-03-24
> **Scope**: Evaluate job boards for automated detection pipeline targeting New Grad to Mid-level SWE, AI/ML Engineer, Forward Deployed Engineer, and Sales/Solutions Engineer roles at big tech and Series D+ startups.
> **Caveat**: Web access was unavailable during this research session. All findings are based on knowledge current through May 2025. **Before implementation, verify robots.txt, ToS, and API docs for each source, as these change frequently.** Specific verification commands are provided at the end.

---

## TIER 1: HIGHEST PRIORITY (Build first)

These sources have the best combination of: API/structured access, job quality, target company overlap, and community reputation.

---

### 1. Hacker News "Who is Hiring?" Monthly Threads

**Overall Score: 9.5/10 for this project**

**What it is**: On the 1st of every month, a "Who is Hiring?" thread is posted by `whoishiring` on Hacker News. Companies post directly — no recruiter spam. Extremely well-regarded in tech communities. Typical thread has 500-1000+ comments, each a job posting.

**API Access: EXCELLENT**
- **HN Firebase API** (https://hacker-news.firebaseio.com/v0/): Free, no auth required, no official rate limit (but be respectful, ~1 req/sec recommended). Get items by ID, get user profiles, etc.
- **HN Algolia API** (https://hn.algolia.com/api): Full-text search. Can query `search_by_date?tags=comment&query=who+is+hiring` or filter by story ID. Returns JSON. Rate limit: ~10,000 requests/hour for unauthenticated.
- **Strategy**: Find the monthly "Who is Hiring?" story (posted by user `whoishiring`, title contains "Who is hiring?"), fetch all child comment IDs, then fetch each comment. Each top-level comment is one job posting.
- **No ToS concerns**: HN API is explicitly public. Algolia API is also intended for public use.

**Job Quality**: Very high. Direct from hiring managers and engineers, not recruiters. Often includes: company name, role, location/remote, tech stack, salary range, visa sponsorship status. Heavily weighted toward startups and mid-size tech companies, but big tech also posts here.

**Freshness**: Monthly cadence (1st of each month). All posts within a single thread. Easy to track which comments you have already processed.

**Role Coverage**: Excellent for SWE and AI/ML roles. Moderate for Forward Deployed / Sales Engineer (less common but present). Startup-heavy which matches Series D+ target.

**Integration Recommendation**:
```
Source: HN Algolia API
Polling: Once on the 1st of each month to get the new thread ID, then poll every 2-4 hours for new comments in the thread for the first 3-5 days.
Parser: Regex/NLP on unstructured comment text. Most follow a loose format:
  "Company | Role | Location | Remote? | URL | Description"
  but format varies. Need flexible parsing.
Data model: story_id, comment_id, author, text, timestamp
Dedup key: comment_id (globally unique on HN)
```

**Risks**: Comment text is unstructured — parsing quality will vary. Some comments are replies/discussions, not job posts (filter to top-level comments only).

---

### 2. Greenhouse Job Board API

**Overall Score: 9/10 for this project**

**What it is**: Greenhouse is one of the two dominant ATS platforms (alongside Lever). Hundreds of companies expose their job boards via Greenhouse. This includes many big tech companies and well-funded startups: Airbnb, Coinbase, Cloudflare, Datadog, Discord, DoorDash, Figma, Notion, Plaid, Ramp, Scale AI, Stripe, and many more.

**API Access: EXCELLENT**
- **Greenhouse Job Board API** is publicly documented: `https://boards-api.greenhouse.io/v1/boards/{company_board_token}/jobs`
- Returns JSON with: job ID, title, location, departments, description (full HTML), updated_at, absolute_url
- Individual job detail: `https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}`
- **No authentication required**. No API key needed.
- **No official rate limit documented**, but standard courtesy applies (~1 req/sec per company board).
- Each company has a board token (e.g., `stripe`, `figma`, `airbnb`, `scaleai`). You need to know/discover these tokens.

**Job Quality**: Excellent. Full HTML job descriptions with requirements, qualifications, compensation (when included), location details. This is the actual ATS data — as detailed as it gets.

**Freshness**: Real-time. Jobs appear on the API as soon as they are published on the company's career page.

**Role Coverage**: All roles. Companies post everything through their ATS.

**Integration Recommendation**:
```
Source: Greenhouse Boards API (JSON)
Polling: Every 4-6 hours per company board
Strategy: Maintain a curated list of board tokens for target companies.
  Start with ~50-100 companies (big tech + Series D+ startups).
  Compare job IDs against SQLite to detect new postings.
Data model: board_token, job_id, title, location, department, content_html, url, updated_at
Dedup key: (board_token, job_id)
Discovery: Board token is usually the company's subdomain: boards.greenhouse.io/{token}
```

**How to discover board tokens**:
- Visit a company's careers page, look for `greenhouse.io` in the iframe or redirect URL
- Many lists exist on GitHub (e.g., search for "greenhouse board tokens" repos)
- Cross-reference with Crunchbase Series D+ list (see below)

**Risks**: Need to manually curate and maintain the list of target companies/tokens. A company switching ATS means the token stops working. Some companies use custom domains that proxy Greenhouse — harder to detect.

---

### 3. Lever Job Board API

**Overall Score: 8.5/10 for this project**

**What it is**: Lever is the other dominant ATS. Companies using Lever include: Netflix, Anthropic, Twitch, Lyft, and many growth-stage startups.

**API Access: GOOD**
- **Lever Postings API**: `https://api.lever.co/v0/postings/{company_slug}?mode=json`
- Returns JSON array of all open postings with: id, text (title), description (HTML), categories (team, location, commitment), lists (requirements), hostedUrl, createdAt
- **No authentication required**.
- Rate limits: Not officially documented, but reasonable use is fine (~1 req/sec).
- Company slug is typically the company name: `jobs.lever.co/{company_slug}`

**Job Quality**: Excellent. Full structured data similar to Greenhouse. Rich HTML descriptions.

**Freshness**: Real-time. Same as Greenhouse.

**Role Coverage**: All roles posted by the company.

**Integration Recommendation**:
```
Source: Lever Postings API (JSON)
Polling: Every 4-6 hours per company
Strategy: Same as Greenhouse — maintain curated list of company slugs.
Data model: company_slug, posting_id, title, description_html, categories, url, created_at
Dedup key: (company_slug, posting_id)
```

**Risks**: Same as Greenhouse — need curated company list. Lever's market share is smaller than Greenhouse, so fewer companies.

---

### 4. Y Combinator — Work at a Startup (workatastartup.com)

**Overall Score: 8/10 for this project**

**What it is**: YC's official job board aggregating roles from all YC-backed companies. Very high signal for startup roles. Includes companies from seed to public (Stripe, Airbnb, DoorDash were all YC).

**API Access: MODERATE (no public API, but good scraping target)**
- **No official public API**.
- The site is a React SPA that fetches data from internal API endpoints. These internal endpoints return JSON and can potentially be called directly.
- Known internal endpoints (may have changed): The site loads job data dynamically. Network tab inspection reveals JSON API calls.
- **robots.txt**: Historically permissive for the main job listing pages. Disallows some internal paths.
- The site does not have aggressive anti-bot measures (no Cloudflare challenge, etc., as of mid-2025).

**Job Quality**: Very good. Structured data: role, company, location, experience level, salary range (often included), company batch/stage, description.

**Freshness**: Continuously updated as YC companies post and remove jobs.

**Role Coverage**: Strong for SWE and AI/ML at startups. Less relevant for big tech (YC companies only). Good coverage of Forward Deployed / Solutions Engineer roles at YC growth-stage companies.

**Integration Recommendation**:
```
Source: Scrape internal JSON API (inspect network requests on the site)
Polling: Every 6-12 hours
Strategy: Replicate the XHR requests the SPA makes. The site likely has
  filtering parameters (role type, experience level, etc.) in the API call.
  Prefer this over HTML scraping.
Data model: job_id, company_name, company_stage, title, location, salary_range, description, url
Dedup key: job_id
```

**Risks**: Internal API endpoints can change without notice. No official support. YC might add auth or rate limiting. Should implement robust error handling and alerting. **Verify current endpoint structure before building.**

---

## TIER 2: HIGH VALUE (Build second)

These sources provide good signal but have more integration complexity or narrower coverage.

---

### 5. Levels.fyi Jobs

**Overall Score: 7.5/10**

**What it is**: Levels.fyi started as a compensation data site and added a job board. Unique advantage: jobs often include verified salary data. Popular in the tech community, particularly on Blind and r/cscareerquestions.

**API Access: LIMITED**
- **No public API** as of mid-2025.
- Site uses a mix of server-rendered pages and client-side API calls.
- Internal API endpoints exist and return JSON (discoverable via network inspection).
- **robots.txt**: Generally allows crawling of job listing pages.
- No aggressive anti-bot (no Cloudflare/Akamai challenges historically).

**Job Quality**: Good. Includes salary/compensation data which is rare and valuable for filtering. Job descriptions link through to company career pages.

**Freshness**: Regularly updated. Aggregates from multiple sources.

**Role Coverage**: Strong for SWE at big tech. Growing for AI/ML. Less coverage for niche roles like FDE.

**Integration Recommendation**:
```
Source: Scrape internal API endpoints or HTML
Polling: Every 12-24 hours
Strategy: Focus on the salary data as a unique enrichment source.
  Even if you get jobs from Greenhouse/Lever, cross-reference with Levels.fyi
  for compensation data.
Data model: job_id, company, title, location, salary_range, url
```

---

### 6. Simplify.jobs

**Overall Score: 7.5/10**

**What it is**: A popular job aggregator in the new-grad/intern community. Maintains the widely-known "New Grad Positions" and "Summer Internships" GitHub repos (pittcsc/Summer2025-Internships style, now maintained by SimplifyJobs). Very strong signal for new grad and early career roles.

**API Access: MODERATE**
- **No official public API**.
- **However**: Their GitHub repos are the real gold mine:
  - `github.com/SimplifyJobs/New-Grad-Positions` — Maintained list of new grad roles, structured as a JSON/markdown table with company, role, location, link, date posted.
  - `github.com/SimplifyJobs/Summer2025-Internships` (and subsequent years) — Same for internships.
  - These repos are updated daily by community + maintainers. Data is in a parseable format (typically a README.md with a markdown table, or a JSON file).
- **GitHub API access**: These repos can be fetched via GitHub API or raw.githubusercontent.com. No rate limit concerns for occasional polling.
- The simplify.jobs website itself has internal APIs discoverable via network inspection.

**Job Quality**: Good. Curated for new grad relevance. Links to actual applications. Includes location and date added.

**Freshness**: GitHub repos updated daily. Website updated continuously.

**Role Coverage**: Excellent for new grad SWE. Moderate for AI/ML. Limited for Sales/Solutions Engineer.

**Integration Recommendation**:
```
Source: GitHub API for their curated repos (primary), website scraping (secondary)
Polling: Every 12-24 hours for GitHub repos (check commit diff)
Strategy: Parse the markdown table or JSON from the GitHub repo.
  Use git diff to detect newly added entries since last poll.
Data model: company, role, location, application_url, date_posted
Dedup key: application_url
```

---

### 7. Otta

**Overall Score: 7/10**

**What it is**: UK-founded job platform that has expanded to the US. Focused on tech/startup roles. Known for curated, high-quality job listings with good company profiles. Popular in HN/tech communities as a LinkedIn alternative.

**API Access: POOR**
- **No public API**.
- Requires user account/login to view jobs. This is a significant barrier to automated access.
- The site is a React SPA with internal APIs, but they are behind authentication.
- **Anti-bot measures**: Moderate. Uses session-based auth.
- **robots.txt**: Restrictive — disallows most crawling paths.

**Job Quality**: Excellent. Curated listings with company culture info, salary ranges, tech stack details. Among the best job description quality.

**Freshness**: Continuously updated. Strong employer base.

**Role Coverage**: Good for SWE, AI/ML, and growth-stage startup roles. Some Sales/Solutions Eng coverage.

**Integration Recommendation**:
```
Source: Difficult to automate. Would require maintaining an authenticated session.
Alternative: Use Otta manually for discovery, but rely on Greenhouse/Lever APIs
  to fetch the actual job data from the same companies.
Priority: LOW for automated pipeline. HIGH for manual discovery of target companies
  to add to the Greenhouse/Lever polling lists.
```

**Risks**: ToS likely prohibits scraping. Auth requirement makes automation fragile. Not recommended for automated pipeline.

---

### 8. BuiltIn

**Overall Score: 7/10**

**What it is**: Job board focused on tech companies, organized by city (BuiltIn NYC, BuiltIn SF, BuiltIn Chicago, etc.). Good coverage of mid-size and growth-stage companies.

**API Access: POOR**
- **No public API**.
- Server-rendered HTML pages. Scrapeable but requires parsing HTML.
- **robots.txt**: Allows crawling of job listing pages (historically).
- Moderate anti-bot measures. May use Cloudflare on some endpoints.

**Job Quality**: Good. Detailed company profiles and job descriptions. Includes company size, funding stage, tech stack.

**Freshness**: Daily updates. Companies actively post here.

**Role Coverage**: Good across all target roles. Strong in SWE and AI/ML at funded startups.

**Integration Recommendation**:
```
Source: HTML scraping
Polling: Every 12-24 hours
Strategy: Scrape listing pages filtered by role type and location.
  Parse company info for Series D+ filtering.
  Follow links to full job descriptions.
Data model: job_id, company, title, location, company_size, funding, description, url
```

---

### 9. Arc.dev

**Overall Score: 6.5/10**

**What it is**: Remote-focused job board (formerly CodementorX). Strong in remote SWE roles. Used by both startups and established companies.

**API Access: MODERATE**
- **No official public API**.
- Website is scrapeable. Job listings are server-rendered or loaded via internal API.
- **robots.txt**: Generally permissive for job listing pages.
- No aggressive anti-bot.

**Job Quality**: Good for remote roles. Includes salary ranges, experience requirements, tech stack.

**Freshness**: Regularly updated.

**Role Coverage**: Strong for remote SWE. Moderate for AI/ML. Limited for Sales/FDE roles.

**Integration Recommendation**:
```
Source: Scrape or discover internal API
Polling: Every 24 hours
Priority: Medium — good supplement for remote roles
```

---

## TIER 3: SUPPLEMENTARY (Build if time permits)

---

### 10. Wellfound (formerly AngelList Talent)

**Overall Score: 6/10**

**What it is**: The rebranded AngelList talent platform. Was once THE startup job board. Has declined in community perception — many report more spam, less curation, and companies that ghost applicants. Still has decent startup coverage.

**API Access: POOR**
- The old AngelList API was deprecated/restricted.
- **No public job listing API** as of mid-2025.
- Requires account to view most job details.
- **Anti-bot measures**: Moderate to aggressive. Uses Cloudflare, requires JavaScript rendering.
- **robots.txt**: Restrictive.

**Job Quality**: Declining. More noise than signal compared to 2019-2021 era. Many listings are stale or from early-stage companies (pre-Series D).

**Freshness**: Variable. Some listings are stale.

**Role Coverage**: Broad but heavily skewed toward early-stage startups (not ideal for Series D+ focus).

**Integration Recommendation**:
```
Priority: LOW. The effort to scrape (auth + Cloudflare bypass) is not worth
  the signal quality. Better to invest that effort in Greenhouse/Lever coverage
  of the same companies.
Alternative: Manual use for company discovery only.
```

---

### 11. Triplebyte / Hired

**Overall Score: 4/10**

**What it is**: Triplebyte was acquired by Karat in 2023 and effectively shut down its job marketplace. Hired.com still operates but is more of a "reverse recruiting" platform where companies reach out to candidates.

**API Access: N/A**
- Triplebyte: **Defunct as a job board**. Do not build integration.
- Hired: Requires candidate profile creation. Companies reach out to you. Not a traditional job board to scrape.

**Integration Recommendation**: Skip entirely. Not suitable for automated job detection pipeline.

---

### 12. Key Values

**Overall Score: 3/10**

**What it is**: Culture-focused job board that matches engineers with companies by values. Very small, curated. Seems to have stagnated in recent years with infrequent updates.

**API Access**: No API. Small enough to scrape trivially, but too few listings to justify integration.

**Integration Recommendation**: Skip. Too few listings, uncertain maintenance status.

---

### 13. Climatebase

**Overall Score: 3/10 (for this project)**

**What it is**: Job board focused on climate tech companies. Niche.

**API Access**: No public API. Scrapeable.

**Integration Recommendation**: Skip unless specifically targeting climate tech roles. Too niche for this project's scope.

---

### 14. TopStartups.io

**Overall Score: 5/10**

**What it is**: Curated lists of top startups, often with job links. More of a discovery tool than a job board.

**Integration Recommendation**: Useful for discovering which companies to add to the Greenhouse/Lever polling lists. Not a job source itself.

---

## TIER S: META-SOURCES (Company Discovery & Aggregation)

These are not job boards but are critical for building and maintaining the target company list.

---

### 15. Crunchbase (Company Discovery)

**Overall Score: CRITICAL for company list maintenance**

**What it is**: The definitive database for startup funding data. Essential for identifying Series D+ companies programmatically.

**API Access: AVAILABLE (paid)**
- **Crunchbase Basic API**: Free tier with limited access. Returns company data including funding rounds, total funding, category, location.
- **Crunchbase Enterprise API**: Paid. Full access to funding round data, investor info, etc.
- **Query capability**: Can filter by `funding_type = series_d, series_e, series_f, ...` and `category = software, AI, ...`
- **Alternative**: Crunchbase Open Data Map has some free data. Also, the Crunchbase website can be scraped for basic funding stage info (but ToS prohibits this).

**Integration Recommendation**:
```
Purpose: Build and refresh the list of Series D+ companies for Greenhouse/Lever polling
Strategy:
  1. Initial build: Use Crunchbase API to query all companies with Series D+ funding
     in tech/software/AI categories.
  2. For each company, discover their ATS (Greenhouse board token, Lever slug, or
     custom career page URL).
  3. Periodic refresh: Monthly query for newly funded Series D rounds.
Data model: company_name, crunchbase_url, funding_stage, total_funding, category,
            careers_url, ats_type (greenhouse|lever|custom), ats_identifier
```

**Alternative to Crunchbase API (free)**:
- **PitchBook**: Paid, enterprise-focused
- **Tracxn**: Has API, paid
- **Dealroom**: Has API, paid
- **Manual curation**: Start with well-known lists (Forbes Cloud 100, YC Top Companies, a16z portfolio, etc.) and manually tag funding stages. This is the most realistic free approach.

---

### 16. GitHub Curated Job Board Lists

**Overall Score: HIGH for bootstrapping**

Several well-maintained GitHub repos aggregate job board information:

- **`github.com/SimplifyJobs/New-Grad-Positions`**: New grad job listings (mentioned above)
- **`github.com/pittcsc/Summer2025-Internships`**: Internship listings
- **`github.com/tramcar/awesome-job-boards`**: Meta-list of job boards
- **`github.com/remoteintech/remote-jobs`**: Companies that hire remotely
- **`github.com/poteto/hiring-without-whiteboards`**: Companies with humane interview processes (useful for company discovery)
- **`github.com/Effective-Immediately/effective-immediately`**: Curated lists of companies actively hiring

**API Access**: All accessible via GitHub API (free, 5000 req/hour authenticated).

**Integration Recommendation**: Parse these repos for company discovery and add target companies to the Greenhouse/Lever polling system.

---

### 17. Aggregator APIs

**Note**: Most job aggregator APIs are commercial and expensive.

- **Adzuna API**: Free tier available. Aggregates from multiple sources. Good international coverage. Returns JSON. Rate limited.
- **The Muse API**: Free, documented API (`https://www.themuse.com/api/public/jobs`). Returns JSON with company info, job descriptions, locations. Good for mid-size to large companies. No auth required.
- **Arbeitnow API**: Free API for tech jobs, returns JSON. Smaller dataset.
- **Remotive API**: Free API for remote tech jobs (`https://remotive.com/api/remote-jobs`). Returns JSON. Good for remote SWE roles.
- **JoBoard API**: Some free endpoints for job listings.

**Integration Recommendation**: The Muse API and Remotive API are worth integrating as low-effort supplementary sources (free, no auth, JSON responses).

---

## RANKED INTEGRATION PRIORITY

| Priority | Source | Integration Method | Effort | Signal Quality | Coverage |
|----------|--------|--------------------|--------|----------------|----------|
| **P0** | HN Who is Hiring | HN Algolia API | Low | Very High | Monthly burst, startups |
| **P0** | Greenhouse Boards API | REST API (no auth) | Medium* | Excellent | Per-company, all roles |
| **P0** | Lever Postings API | REST API (no auth) | Medium* | Excellent | Per-company, all roles |
| **P1** | Simplify GitHub repos | GitHub API | Low | High | New grad SWE |
| **P1** | YC Work at a Startup | Internal API scrape | Medium | High | YC startups only |
| **P1** | Levels.fyi | Internal API scrape | Medium | High | Big tech, salary data |
| **P2** | The Muse API | REST API (no auth) | Low | Medium | Large/mid companies |
| **P2** | Remotive API | REST API (no auth) | Low | Medium | Remote roles |
| **P2** | BuiltIn | HTML scraping | High | Medium-High | City-based tech |
| **P3** | Arc.dev | Scrape | Medium | Medium | Remote SWE |
| **Skip** | Wellfound | Auth + anti-bot | Very High | Declining | Not worth effort |
| **Skip** | Otta | Auth required | Very High | High quality but... | Blocked by auth |
| **Skip** | Triplebyte | Defunct | N/A | N/A | N/A |
| **Skip** | Key Values | Stagnant | N/A | Low volume | N/A |

*Medium effort for Greenhouse/Lever because you need to build and maintain the company list, not because the API is hard.

---

## RECOMMENDED BUILD ORDER

### Phase 1: Core Pipeline (Week 1-2)
1. **Greenhouse Boards API** — Start with a hand-curated list of ~50 target companies
2. **Lever Postings API** — Same approach, ~30 companies
3. **HN Who is Hiring** — Monthly thread parser using Algolia API

### Phase 2: Expansion (Week 3-4)
4. **Simplify GitHub repos** — Parse new grad listings
5. **YC Work at a Startup** — Scrape internal API
6. **The Muse API + Remotive API** — Quick supplementary sources

### Phase 3: Enrichment (Week 5+)
7. **Levels.fyi** — Cross-reference for salary data
8. **Crunchbase** — Automate Series D+ company discovery
9. **BuiltIn** — HTML scraping for additional coverage

---

## INITIAL TARGET COMPANY LIST (Greenhouse/Lever)

### Greenhouse (known board tokens to verify):
```
stripe, figma, airbnb, coinbase, cloudflare, datadog, discord, doordash,
notion, plaid, ramp, scaleai, anduril, brex, airtable, gusto, lattice,
benchling, retool, vercel, linear, mercury, openai, anthropic, databricks,
snyk, hashicorp, gitlab, twilio, okta, pagerduty, elastic, confluent,
mongodb, cockroachlabs, samsara, toast, marqeta, affirm, chime, robinhood,
instacart, lyft, pinterest, snap, spotify, uber, palantir
```

### Lever (known slugs to verify):
```
netflix, anthropic, twitch, lever, reddit, quora, figma (check both),
flexport, calm, nerdwallet, coursera, udemy
```

*Note: Companies may switch ATS providers. Verify each token/slug before building.*

---

## LEGAL & ETHICAL NOTES

1. **Greenhouse & Lever APIs**: These are explicitly public, unauthenticated APIs designed for embedding job boards. Using them is clearly permitted.

2. **HN API & Algolia**: Explicitly public APIs. Free use is encouraged.

3. **GitHub API**: Public repos, public API. Standard rate limits apply.

4. **Work at a Startup / Levels.fyi**: No explicit API. Using undocumented internal APIs is a gray area. Respect rate limits, identify your bot in User-Agent, and be prepared for endpoints to change.

5. **BuiltIn / Arc.dev scraping**: Check robots.txt before scraping. Respect crawl-delay directives. Do not hammer servers.

6. **General**: Never bypass CAPTCHAs or auth systems. Never misrepresent your bot as a human browser. Store only job posting data (not user data). Attribute sources properly.

---

## VERIFICATION CHECKLIST (Do before implementation)

Before building each integration, verify the following with live web access:

```bash
# Greenhouse API — verify a known board token works
curl -s "https://boards-api.greenhouse.io/v1/boards/stripe/jobs" | head -c 500

# Lever API — verify a known slug works
curl -s "https://api.lever.co/v0/postings/netflix?mode=json" | head -c 500

# HN Algolia — verify Who is Hiring search works
curl -s "https://hn.algolia.com/api/v1/search?query=%22Who%20is%20hiring%22&tags=story&hitsPerPage=5" | head -c 500

# robots.txt checks
curl -s https://www.workatastartup.com/robots.txt
curl -s https://wellfound.com/robots.txt
curl -s https://www.levels.fyi/robots.txt
curl -s https://www.builtinnyc.com/robots.txt
curl -s https://otta.com/robots.txt
curl -s https://arc.dev/robots.txt

# The Muse API
curl -s "https://www.themuse.com/api/public/jobs?page=1&descending=true" | head -c 500

# Remotive API
curl -s "https://remotive.com/api/remote-jobs?limit=5" | head -c 500

# SimplifyJobs GitHub repo structure
curl -s "https://api.github.com/repos/SimplifyJobs/New-Grad-Positions/contents/" | head -c 1000
```

---

## ARCHITECTURE IMPLICATIONS

Based on this research, the detection layer should be built as a **plugin/adapter system**:

```
src/detection/
  base.py           # Abstract base class for job sources
  greenhouse.py     # Greenhouse Boards API adapter
  lever.py          # Lever Postings API adapter
  hackernews.py     # HN Who is Hiring parser
  simplify.py       # GitHub repo parser
  yc_waas.py        # Work at a Startup scraper
  muse.py           # The Muse API adapter
  remotive.py       # Remotive API adapter
  levelsfyi.py      # Levels.fyi scraper (enrichment)
  config/
    companies.json  # Target company list with ATS type + identifier
    sources.json    # Source-specific config (poll intervals, etc.)
```

Each adapter should implement:
- `fetch_jobs() -> list[RawJob]`
- `get_poll_interval() -> timedelta`
- `get_source_name() -> str`

The scheduler calls each adapter at its configured interval, passes results to the filter layer, and tracks seen job IDs in SQLite.
