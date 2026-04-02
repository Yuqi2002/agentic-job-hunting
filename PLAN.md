# Implementation Plan — Agentic Job Hunting System

## Finalized Decisions

| Decision | Choice |
|---|---|
| Language | Python 3.11+ |
| AI Provider | Claude API (Haiku for analysis, Sonnet for generation) |
| Runtime | Hetzner VPS (always-on) |
| Logging | structlog → JSON stdout → Promtail → Grafana Loki |
| Database | SQLite (WAL mode, aiosqlite) |
| HTTP Client | httpx + selectolax (Playwright lazy fallback) |
| Scheduler | APScheduler 3.x (AsyncIOScheduler) |
| Resume Format | User's LaTeX Overleaf template → pdflatex → .pdf |
| Notifications | Discord webhook — job link + PDF attachment (minimal) |
| Location Filter | Remote + specific cities (configurable) |
| Auto-apply | No — prepare resume only, user submits manually |
| Company Discovery | Auto-synced from Feashliaa/job-board-aggregator (6,262 companies) |

---

## Project Structure (Current)

```
agentic-job-hunting/
├── CLAUDE.md
├── PLAN.md
├── pyproject.toml
├── .env.example
├── .env                        # (gitignored)
├── .gitignore
├── research/
│   ├── job_board_evaluation.md
│   ├── scraping_architecture.md
│   └── resume_ai_pipeline.md
├── data/
│   ├── master_resume.yaml      # User's full experience inventory (tagged YAML)
│   ├── cache/                  # (gitignored) Auto-synced company lists
│   │   ├── greenhouse_companies.json
│   │   ├── lever_companies.json
│   │   └── ashby_companies.json
│   └── jobs.db                 # (gitignored) SQLite database
├── templates/
│   └── resume.tex              # LaTeX template (needs user's Overleaf file)
├── src/
│   ├── __init__.py
│   ├── main.py                 # Entry point — async, graceful shutdown
│   ├── config.py               # pydantic-settings from .env
│   ├── logging.py              # structlog JSON config
│   ├── db.py                   # SQLite WAL + aiosqlite
│   ├── pipeline.py             # Orchestrates: insert → filter → notify
│   ├── detection/
│   │   ├── __init__.py
│   │   ├── base.py             # RawJob dataclass + BaseScraper ABC
│   │   ├── greenhouse.py       # Greenhouse Boards API
│   │   ├── lever.py            # Lever Postings API
│   │   ├── ashby.py            # Ashby Posting API
│   │   ├── hackernews.py       # HN Who is Hiring (Algolia API)
│   │   ├── company_sync.py     # Auto-sync from Feashliaa GitHub repo
│   │   └── scheduler.py        # APScheduler + BatchRunner
│   ├── filter/
│   │   ├── __init__.py
│   │   └── matcher.py          # Role, location, experience matching
│   └── notify/
│       ├── __init__.py
│       └── discord.py          # Discord webhook sender
└── tests/                      # (not yet created)
```

---

## Phase 1: Foundation — COMPLETE ✓

### 1.1 Project Setup ✓
- [x] uv project with `pyproject.toml`
- [x] `.env.example` with all config vars
- [x] `.gitignore` for .env, jobs.db, cache/, .venv
- [x] `src/config.py` — pydantic-settings with comma-separated string parsing
- [x] `src/logging.py` — structlog JSON config
- [x] `src/db.py` — SQLite WAL mode, async, full schema

### 1.2 Detection Layer ✓
- [x] `src/detection/base.py` — RawJob dataclass + BaseScraper ABC
- [x] `src/detection/greenhouse.py` — Greenhouse Boards API (`?content=true` for full JD)
- [x] `src/detection/lever.py` — Lever Postings API
- [x] `src/detection/ashby.py` — Ashby Posting API (`?includeCompensation=true`)
- [x] `src/detection/hackernews.py` — HN Algolia API, 3-strategy comment parser
- [x] `src/detection/company_sync.py` — Auto-sync 6,262 companies from GitHub
- [x] `src/detection/scheduler.py` — BatchRunner (200/batch, 1.5s delay, 30min interval)

### 1.3 Filter Layer ✓
- [x] `src/filter/matcher.py` — Role keywords, abbreviations, location, experience level
- [x] Tested: Anthropic (439 jobs → 64 matched)

### 1.4 Notification Layer ✓
- [x] `src/notify/discord.py` — Webhook with embeds, rate limiting, retry on 429

### 1.5 Pipeline + Entrypoint ✓
- [x] `src/pipeline.py` — insert → filter → notify orchestration
- [x] `src/main.py` — async entrypoint with SIGINT/SIGTERM graceful shutdown

**Status**: All code written, imports verified, scheduler builds successfully with 6,262 companies. **Not yet tested end-to-end with Discord notifications.**

---

## Phase 2: Resume AI — IN PROGRESS

### What's Working (prototype in `test_resume_e2e.py`)
- [x] End-to-end pipeline validated: detect → tailor → ATS optimize → PDF → Discord
- [x] `templates/resume.tex` confirmed working with Jinja2 + pdflatex
- [x] `data/master_resume.yaml` populated with IDs on every entry
- [x] ATS optimization pass with 7 rules (keyword injection, XYZ bullets, verb strength, etc.)
- [x] LaTeX escaping applied programmatically after ATS pass (covers all text fields)
- [x] Model: Haiku 4.5 for all Claude calls (cost optimization)

### Next: Refactor into `src/resume/` module
See **Section: Resume Pipeline Refactor** below for full spec.

### 2.2 Integration (after refactor)
- [ ] Update `src/pipeline.py` — call `generate_resume()` between filter and notify
- [ ] Install `texlive-latex-base texlive-fonts-recommended texlive-latex-extra` on VPS

---

---

## Resume Pipeline Refactor — Implementation Spec

### Goal
Move all resume logic out of `test_resume_e2e.py` into a clean, importable
`src/resume/` module. Each file has one job. `test_resume_e2e.py` becomes a
thin ~60-line integration test.

### Data Flow
```
job_data + master YAML
    │
    ▼  selector.py  (Claude Haiku — picks IDs + bullet indices only)
SelectionManifest
    │
    ▼  builder.py   (Pure Python — copies verbatim text from YAML by ID)
ResumeContent
    │
    ▼  ats.py       (Claude Haiku — rewrites bullets for ATS keyword/structure)
ResumeContent (optimized)
    │
    ▼  compiler.py  (Jinja2 + pdflatex — applies escape_latex, renders, compiles)
bytes (PDF)
```

**Core principle**: Claude never copies text. `selector.py` returns IDs only.
`builder.py` copies text verbatim. `ats.py` is the only place wording changes.

### File Structure
```
src/resume/
├── __init__.py   — re-exports generate_resume() convenience fn
├── types.py      — shared dataclasses (SelectionManifest, ResumeContent, etc.)
├── selector.py   — Claude Haiku: job → SelectionManifest
├── builder.py    — Pure Python: SelectionManifest + master YAML → ResumeContent
├── ats.py        — Claude Haiku: ResumeContent → ResumeContent (ATS-optimized)
└── compiler.py   — Jinja2 + pdflatex: ResumeContent → PDF bytes
```

---

### `src/resume/types.py` — Shared Dataclasses

```python
@dataclass
class BulletSelection:
    id: str                    # matches id field in master_resume.yaml
    bullet_indices: list[int]  # 0-based, in display order

@dataclass
class SelectionManifest:
    experiences: list[BulletSelection]  # 2-3 entries
    projects: list[BulletSelection]     # 1-2 entries
    leadership_ids: list[str]           # exactly 1
    skills: dict[str, list[str]]        # category → skill names from master
                                        # keys: languages, frameworks, devops, certifications

@dataclass
class ExperienceEntry:
    title: str
    company: str
    dates: str
    location: str
    bullets: list[str]   # plain text, no LaTeX escaping until compiler.py

@dataclass
class ProjectEntry:
    name: str
    bullets: list[str]

@dataclass
class LeadershipEntry:
    title: str
    description: str

@dataclass
class SkillEntry:
    category: str   # display name e.g. "Languages"
    value: str      # comma-joined e.g. "Python, TypeScript, SQL"

@dataclass
class ResumeContent:
    experience: list[ExperienceEntry]
    projects: list[ProjectEntry]
    leadership: list[LeadershipEntry]
    skills: list[SkillEntry]
```

---

### `src/resume/selector.py`

**Public API**: `select(job: dict, master: dict, api_key: str) -> SelectionManifest`

**What Claude sees** — compact summary, NOT full bullet text:
```
### exp-servicenow-fte | Software Engineer @ ServiceNow | Jul 2025 -- Present
  [0] Engineered core features of CRIR escalation management system... (214+ users, 128 escalations)
  [1] Developed UI/UX and backend features for C2C Customer Cockpit... ($4.7B obligations)
  [2] Spearheaded AI-native transformation... (18% → 95% AI adoption, 500% increase)
  [3] Led 3 AI adoption workshops... (90 engineers trained)
  [4] Maintained Engineering Excellence Workspace...
```
Format: `[index] first 80 chars of bullet text (metrics field if present)`

**Claude returns** (IDs + indices only, no text):
```json
{
  "experiences": [
    {"id": "exp-servicenow-fte", "bullet_indices": [2, 0, 1]},
    {"id": "exp-servicenow-intern", "bullet_indices": [0, 1]}
  ],
  "projects": [
    {"id": "proj-ucf-attendance", "bullet_indices": [0, 1]}
  ],
  "leadership_ids": ["lead-toastmasters"],
  "skills": {
    "languages": ["Python", "TypeScript", "SQL"],
    "frameworks": ["React.js", "Langchain", "Django"],
    "devops": ["AWS", "Docker", "Kubernetes", "CI/CD"],
    "certifications": ["ServiceNow Certified Application Developer"]
  }
}
```

**Selection rules** (in prompt):
- 2-3 experiences, 2-4 bullets each (most relevant first)
- 1-2 projects, 2-3 bullets each
- Exactly 1 leadership entry
- Max 12-14 total bullets across all sections (1-page constraint)
- Skills: subset of master skills most relevant to JD; use exact names from master

**Post-parse validation**: all IDs must exist in master, all indices must be in range.
Raise `ValueError` with clear message on failure.

**Model**: `claude-haiku-4-5-20251001`, `max_tokens=800`
(Output is just IDs — very short, Haiku sufficient)

---

### `src/resume/builder.py`

**Public API**: `build(manifest: SelectionManifest, master: dict) -> ResumeContent`

**Logic**:
1. Build lookup dicts from master: `{exp["id"]: exp for exp in master["experiences"]}` etc.
2. For each `BulletSelection` in `manifest.experiences`:
   - Copy `exp["title"]`, `exp["company"]`, `exp["dates"]`, `exp["location"]` verbatim
   - Copy `exp["bullets"][i]["text"]` for each `i` in `bullet_indices`
3. Same for projects (`proj["bullets"][i]["text"]`) and leadership (`lead["description"]`)
4. Skills: join each list in `manifest.skills` with `", "` → `SkillEntry`
   - Category display name map: `{"languages": "Languages", "frameworks": "Frameworks / Tools", "devops": "DevOps / Cloud", "certifications": "Certifications"}`

**No Claude. No network. Fully deterministic. Zero text modification.**

---

### `src/resume/ats.py`

**Public API**: `optimize(content: ResumeContent, job: dict, api_key: str) -> ResumeContent`

**Prompt input**: serialize `ResumeContent` to JSON (same structure as current
`build_ats_prompt()` in `test_resume_e2e.py`).

**7 ATS rules** (carry forward unchanged from prototype):
1. Keyword injection — 6-8 critical JD keywords, verbatim exact match
2. Action verb strength — ban "worked on/responsible for/helped with", replace with strong mapped verbs
3. XYZ bullet structure — "Accomplished X as measured by Y by doing Z"
4. Special char safety — smart quotes/em dash/ellipsis → plain ASCII
5. Skills ordering — most JD-relevant first
6. Date consistency — "Mon YYYY -- Present" throughout
7. Guardrails — no new content, no fake metrics, no company/title/date changes

**CRITICAL in prompt**: "Output plain text only. No LaTeX escape sequences."

**Model**: `claude-haiku-4-5-20251001`, `max_tokens=3000`

---

### `src/resume/compiler.py`

**Public API**:
```python
def compile_pdf(
    content: ResumeContent,
    master: dict,
    template_path: Path = Path("templates/resume.tex"),
    debug_tex_path: Path | None = None,
) -> bytes
```

**Steps**:
1. Apply `escape_latex()` to ALL text fields:
   - `exp.bullets`, `proj.bullets`, `lead.title`, `lead.description`
   - `skill.category`, `skill.value`
2. Convert dataclasses to dicts (`dataclasses.asdict()`)
3. Render Jinja2 template (same env config as prototype: `\VAR{...}`, `<% %>` blocks)
4. Write to tmpdir, run pdflatex, return `pdf_path.read_bytes()`
5. On failure: save `.tex` to `debug_tex_path` if set, raise `CompilationError(latex_stdout)`

**`escape_latex()`**: handles `& % $ # _ ~ ^` with double-escape protection (same as prototype).

**`CompilationError`**: custom exception with `latex_stdout: str` attribute.

---

### `src/resume/__init__.py` — Convenience Function

```python
from src.resume.selector import select
from src.resume.builder import build
from src.resume.ats import optimize
from src.resume.compiler import compile_pdf

def generate_resume(job: dict, master: dict, api_key: str) -> bytes:
    """Full pipeline: job + master YAML → PDF bytes."""
    manifest = select(job, master, api_key)
    content = build(manifest, master)
    optimized = optimize(content, job, api_key)
    return compile_pdf(optimized, master)
```

---

### `test_resume_e2e.py` — Thin Integration Test (after refactor)

Reduce to ~60 lines: detect job → call `generate_resume()` → save PDF → send Discord.
All business logic moves to `src/resume/`. The test only wires together the layers.

---

### Subagent Task Breakdown

| Task | File | Depends on | Can parallelize? |
|---|---|---|---|
| Task 0 | `src/resume/types.py` + `__init__.py` stub | nothing | No (blocking) |
| Task 1 | `src/resume/selector.py` | Task 0 | Yes (with 2,3,4) |
| Task 2 | `src/resume/builder.py` | Task 0 | Yes (with 1,3,4) |
| Task 3 | `src/resume/ats.py` | Task 0 | Yes (with 1,2,4) |
| Task 4 | `src/resume/compiler.py` | Task 0 | Yes (with 1,2,3) |
| Task 5 | Rewrite `test_resume_e2e.py` + run e2e | Tasks 1-4 | No (final) |

Tasks 1-4 can all be run in parallel once Task 0 is done.

---

### Invariants (must hold across all tasks)

1. Claude never copies text — `selector.py` returns IDs only; `builder.py` does all copying
2. LaTeX escaping is always programmatic — `escape_latex()` in `compiler.py`, never ask Claude
3. Plain text in/out of ATS pass — no `\%`, `\&` etc. in Claude's input or output
4. Model: `claude-haiku-4-5-20251001` for all Claude calls
5. `master_resume.yaml` is source of truth — titles, companies, dates, locations never modified by any Claude pass

---

## Phase 3: Polish & Scale — NOT STARTED

- [ ] Additional sources: SimplifyJobs, YC WaaS, Muse, Remotive
- [ ] Batch API for cost optimization
- [ ] systemd service + Promtail config for VPS
- [ ] Grafana dashboard
- [ ] Cross-board fuzzy dedup (rapidfuzz)

---

## Deployment on Hetzner VPS

```bash
# Install system deps
sudo apt install python3.11 texlive-latex-base texlive-fonts-recommended texlive-latex-extra

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# Clone and setup
git clone <repo> ~/job-hunter
cd ~/job-hunter
uv sync

# Configure
cp .env.example .env
# Edit .env with your keys

# Test locally first
uv run python -m src.main

# Create systemd service
sudo tee /etc/systemd/system/job-hunter.service << 'EOF'
[Unit]
Description=Agentic Job Hunter
After=network.target

[Service]
Type=simple
User=yuqi
WorkingDirectory=/home/yuqi/job-hunter
Environment="PATH=/home/yuqi/.local/bin:/usr/bin:/usr/local/bin"
ExecStart=/home/yuqi/.local/bin/uv run python -m src.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now job-hunter
```

**Note**: The systemd service needs `PATH` set explicitly for uv to work. Do NOT use `EnvironmentFile` for PATH — use the `Environment=` directive in the service file.
