# Scraping Architecture Research

> Author: @scraping-architect | Date: 2026-03-24

## Recommendations Summary

| Area | Recommendation | Rationale |
|---|---|---|
| HTTP scraping | `httpx` + `selectolax` | Lowest memory (~25MB), fastest parsing, native async |
| Browser scraping | Playwright (lazy-loaded fallback) | Only for 1-2 JS-rendered boards |
| Anti-bot | Rotating UAs + per-domain delays + conditional requests | Target boards have minimal anti-bot |
| Scheduling | APScheduler 3.x (AsyncIOScheduler) | Lightweight, async-native, per-source intervals |
| Retry/backoff | `tenacity` library | Exponential backoff with jitter |
| Database | SQLite WAL mode + `aiosqlite` | FTS5 for description search |
| Dedup | Exact `(source_board, external_id)` + fuzzy cross-board | rapidfuzz for title similarity |
| Logging | `structlog` → JSON stdout → Promtail → Loki | Decoupled, structured, low-cardinality labels |

## Key Dependencies

```
httpx[http2]
selectolax
playwright (optional)
apscheduler>=3.10,<4
aiosqlite
tenacity
structlog
rapidfuzz
curl_cffi (optional)
```

## Board Anti-Bot Assessment

| Board | Anti-Bot | JS Required? | Strategy |
|---|---|---|---|
| HN Who's Hiring | None (public API) | No | HN Algolia API |
| Greenhouse pages | None to light | No | Boards API (JSON) |
| Lever pages | None to light | No | Postings API (JSON) |
| YC Work at a Startup | Light | Partial (React, but JSON API) | Intercept internal API |
| Wellfound | Moderate (Cloudflare) | Yes | SKIP |
| BuiltIn | Moderate | Partial | curl_cffi or Playwright |

## SQLite Schema

```sql
CREATE TABLE jobs (
    id              TEXT PRIMARY KEY,
    source_board    TEXT NOT NULL,
    external_id     TEXT NOT NULL,
    url             TEXT NOT NULL,
    title           TEXT NOT NULL,
    company_name    TEXT NOT NULL,
    company_url     TEXT,
    location        TEXT,
    is_remote       INTEGER DEFAULT 0,
    description_text TEXT,
    description_html TEXT,
    posted_at       TEXT,
    discovered_at   TEXT NOT NULL,
    salary_min      INTEGER,
    salary_max      INTEGER,
    salary_currency TEXT DEFAULT 'USD',
    experience_level TEXT DEFAULT 'unknown',
    job_type        TEXT DEFAULT 'full_time',
    filter_status   TEXT DEFAULT 'pending',
    filter_reason   TEXT,
    resume_generated INTEGER DEFAULT 0,
    notified        INTEGER DEFAULT 0,
    notified_at     TEXT,
    UNIQUE(source_board, external_id)
);

CREATE INDEX idx_jobs_discovered ON jobs(discovered_at);
CREATE INDEX idx_jobs_company ON jobs(company_name COLLATE NOCASE);
CREATE INDEX idx_jobs_filter ON jobs(filter_status);
CREATE INDEX idx_jobs_pipeline ON jobs(filter_status, resume_generated, notified);

CREATE TABLE scrape_runs (
    id          TEXT PRIMARY KEY,
    source_board TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL,
    jobs_found  INTEGER DEFAULT 0,
    new_jobs    INTEGER DEFAULT 0,
    error_msg   TEXT
);
```

## Logging to Loki

Use `structlog` → JSON to stdout → Promtail → Loki.

Loki labels (low cardinality):
- `service="job-hunter"`
- `layer="detection"` / `"filter"` / `"resume"` / `"notify"`
- `level` from JSON

Log events: `scrape_completed`, `new_job_detected`, `scrape_failed`, `rate_limited`, `job_filtered`, `health_check`
