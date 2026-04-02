# Agentic Job Hunting 🤖

Automatically detect, filter, tailor, and apply to tech jobs using AI. Finds roles on ATS boards (Greenhouse, Lever, Ashby) and curated sources, generates personalized resumes with GPT-4o mini, and delivers them to Discord.

**Status**: Production-ready. Phases 1-2 complete. Tested end-to-end with real job data.

---

## Features

### Detection & Filtering
- ✅ **Job Detection** — Scrapes 6,262+ companies across Greenhouse, Lever, Ashby, HN
- ✅ **Smart Filtering** — Role keywords, location matching, experience level validation
- ✅ **Always-On Scheduler** — Batch processing via APScheduler, systemd service-ready

### Job Summaries & Approval
- ✅ **Job Summaries** — GPT-4o mini extracts compensation + calculates resume match %
- ✅ **Rich Discord Embeds** — Color-coded by match %, shows keywords + match reasoning
- ✅ **Human-in-the-Loop Approval** — React ✅ to a message to trigger resume generation (not auto)

### AI Resume Generation
- ✅ **AI Resume Generation** — GPT-4o mini-powered, modular, deterministic pipeline (91% cheaper)
- ✅ **ATS Optimization** — 7-rule keyword matching, strong verbs, XYZ bullet structure
- ✅ **PDF Compilation** — LaTeX-based, fully customizable resume template
- ✅ **Smart Replies** — Bot replies to original message with named PDF: `Company_JobTitle_Resume.pdf`

### Configuration
- ✅ **Configurable Roles & Locations** — Easy to modify for your target criteria

---

## How It Works

### Phase 1: Detection → Filter → Notify
1. **Detection**: Batch-scrapes 200 companies every 30 min (full cycle ~2.5 hours)
2. **Filtering**: Keywords (SWE, AI/ML, FDE, Sales Eng), location (remote + cities), experience (0-4 years)
3. **Notification**: Discord webhook with job details

### Phase 2: Job Summaries + Human Approval
When a matching job is found:
1. **Summary** (GPT-4o mini): Extracts compensation, calculates resume match % vs your skills
2. **Rich Embed**: Sends Discord message with company, title, location, compensation, match %, and matching keywords
3. **Human Gate**: You review and react ✅ to approve (stops bad matches from wasting resume-generation tokens)

### Phase 3: Tailored Resume (On-Demand)
When you approve a job (react ✅), the pipeline:
1. **Selection** (GPT-4o mini): Analyzes job + master resume → picks 2-3 relevant experiences/projects (returns IDs only)
2. **Building** (Pure Python): Copies text verbatim from your master resume by ID
3. **ATS Optimization** (GPT-4o mini): Restructures bullets for keyword density and impact (7 rules)
4. **Compilation** (Pure Python): LaTeX escaping + render + pdflatex → PDF bytes
5. **Smart Reply**: Bot replies to the original message with named PDF: `Company_JobTitle_Resume.pdf`

**Pipeline Design**: AI never copies text. `selector.py` returns IDs only; `builder.py` copies. This ensures determinism and eliminates hallucination risk. Uses GPT-4o mini for 91% cost savings vs Claude Haiku. Human-in-the-loop approval prevents wasting tokens on rejected jobs.

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/Yuqi2002/agentic-job-hunting
cd agentic-job-hunting

# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

### 2. Set Up Environment

```bash
cp .env.example .env
# Edit .env with your values:
#   OPENAI_API_KEY=sk-proj-...
#   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
#   DISCORD_BOT_TOKEN=... (see Discord Bot Setup section)
#   DISCORD_CHANNEL_ID=... (see Discord Bot Setup section)
#   TARGET_CITIES=San Francisco,New York,Seattle
#   TARGET_ROLES=software engineer,ai engineer,machine learning engineer
```

Optional: Set up Discord bot for human-in-the-loop approval (see [Discord Bot Setup](#discord-bot-setup) section for detailed instructions)

### 3. Populate Your Master Resume (Critical Step)

The master resume is the **source of truth** for all your experiences, projects, and skills. The AI will use this to intelligently select the most relevant content for each job.

**Copy the template:**
```bash
cp data/master_resume.example.yaml data/master_resume.yaml
```

**Key Principles:**

1. **Include EVERYTHING** — Add every single experience, project, and skill you've had
   - Don't pre-filter or limit to "only relevant" roles
   - The AI is smart enough to select what matters for each job
   - More content = better matching and more tailored resumes

2. **Use specific, quantified bullet points** — Each bullet should include:
   - What you built/accomplished
   - Metrics: scale, users, performance gains, time saved, adoption, etc.
   - Example: "Reduced API latency from 5s to 100ms" not "Improved performance"

3. **Pressure Test Your Bullets** — This is critical!
   - Open Claude (https://claude.ai) and chat with it about your bullet points
   - Ask: "Does this bullet clearly show impact and use strong action verbs?"
   - Example prompt: "Here are my resume bullets. Do they show quantified impact? Should I add metrics?"
   - Refine until each bullet is compelling and specific

**Structure:**

```yaml
meta:
  name: "Your Name"
  email: "your.email@example.com"
  phone: "(555) 123-4567"
  linkedin: "https://www.linkedin.com/in/yourprofile/"
  location: "City, State"

skills:
  languages: [Python, Java, JavaScript, ...]
  frameworks: [React, Django, AWS, ...]
  devops: [Docker, Kubernetes, GitHub Actions, ...]

experiences:
  - id: "exp-company1"        # Unique identifier
    company: "Company Name"
    title: "Software Engineer"
    dates: "Jan 2024 -- Present"
    location: "San Francisco, CA"
    bullets:
      - text: "Built a real-time data pipeline handling 1M+ events/day using Apache Kafka"
        metrics: "reduced latency from 5s to 100ms, improved system stability"
      - text: "Led migration of legacy monolith to microservices architecture"
        metrics: "enabled 5x faster deployment cycles, improved team velocity"
      - text: "Mentored 3 junior engineers on system design best practices"
        metrics: "all 3 promoted to mid-level within 18 months"

projects:
  - id: "proj-ai-app"         # Unique identifier
    name: "AI-Powered Job Application Assistant"
    bullets:
      - text: "Automated job detection and resume tailoring system"
        metrics: "scans 6,262+ companies, saves 10+ hours per week"
      - text: "Implemented GPT-4o mini integration for AI resume optimization"
        metrics: "91% cheaper than Claude Haiku, identical quality, 500+ jobs processed"

leadership:
  - id: "lead-mentoring"
    title: "Technical Mentor"
    description: "Mentored 3 junior engineers on system design and career development. Created comprehensive onboarding documentation used across entire team."
```

**Pro Tips:**
- Each experience should have 2-4 bullets (not just 1)
- Skills should be comprehensive: languages, frameworks, tools, DevOps, certifications
- Use "Jan 2024 -- Present" format for consistency
- Each bullet combines WHAT + HOW + IMPACT (metrics)
- The system will intelligently pick 2-3 most relevant experiences per job

### 4. Update LaTeX Template (Optional)

`templates/resume.tex` uses Jinja2 variables:
- `\VAR{meta.name}` → your name
- `\VAR{experience}` → array of experience entries
- `\VAR{skills}` → array of skill categories

If you have your own Overleaf template, copy the `.tex` file here and ensure:
- Variables use `\VAR{...}` syntax
- Single-column layout (ATS compatibility)
- No images, tables, or graphics

### 5. Test It

```bash
# Run unit tests (11 tests, all passing)
uv run pytest tests/test_resume_pipeline.py -v -s

# Run e2e test (detects real job, generates resume, sends Discord)
python test_resume_e2e.py
```

### 6. Deploy to Always-On Server

See [Deployment](#deployment) section below.

---

## Architecture

### Full Pipeline Architecture

**Layer 1: Detection**
```
src/detection/
├── greenhouse.py  — Greenhouse Boards API (free, 4,516+ companies)
├── lever.py       — Lever Postings API (free, 947+ companies)
├── ashby.py       — Ashby Posting API (free, 799+ companies)
└── hackernews.py  — HN Who is Hiring (monthly threads)
```
Batch processing: 200 companies every 30 min, full cycle ~2.5 hours

**Layer 2: Filtering**
```
src/filter/
└── matcher.py     — Keyword, location, experience matching
```
Rejects: senior/staff/principal roles, mismatched locations, wrong experience level

**Layer 3: Job Summaries**
```
src/resume/
└── summarizer.py  — GPT-4o mini: extract compensation + calculate match %
```
Runs on ALL matched jobs; determines which ones are worth your time

**Layer 4: Human Approval Gate**
```
src/bot/
└── listener.py    — Discord bot: listens for ✅ reactions
```
Only generates resumes for jobs you explicitly approve (saves tokens on rejected jobs)

**Layer 5: Tailored Resume (On-Demand)**
```
src/resume/
├── selector.py    — GPT-4o mini: pick experience/project/skill IDs (returns IDs only)
├── builder.py     — Pure Python: copy text verbatim by ID from master resume
├── ats.py         — GPT-4o mini: optimize bullets for ATS (7 rules)
└── compiler.py    — Pure Python: LaTeX escape + render + pdflatex → PDF bytes
```

**Why this design?**
- **No text copying by Claude** → eliminates hallucination & maintains determinism
- **Pure Python builder** → 100% predictable, no network calls
- **Modular separation** → easy to test, extend, or swap components
- **Programmatic LaTeX escaping** → reliable, handles all edge cases
- **Human approval gate** → prevents wasting tokens on jobs you don't want

**Layer 6: Notifications**
```
src/notify/
└── discord.py     — Webhook + bot reply with named PDF
```

---

## Configuration

### .env Variables

```bash
# OpenAI (resume generation + job summaries)
OPENAI_API_KEY=sk-proj-...

# Discord webhook (sends job summaries one-way)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Discord bot (listens for ✅ reactions to trigger resume generation)
DISCORD_BOT_TOKEN=...
DISCORD_CHANNEL_ID=123456789012345678

# Job filtering
TARGET_CITIES=San Francisco,New York,Seattle,Austin
TARGET_ROLES=software engineer,ai engineer,ml engineer,forward deployed engineer,solutions engineer
MAX_EXPERIENCE_YEARS=4

# Database & logging
DB_PATH=data/jobs.db
LOG_LEVEL=INFO
CACHE_DIR=data/cache

# Anthropic API (kept for reference, not used in current pipeline)
ANTHROPIC_API_KEY=sk-ant-...
```

### Configurable Parameters

**Role matching** — Edit `TARGET_ROLES` to filter for specific titles. The pipeline checks:
- Exact match in job title (case-insensitive)
- Abbreviations (e.g., "swe", "sde", "mle")

**Location matching** — Edit `TARGET_CITIES` to target specific metros. Also matches:
- "remote" in any job
- Substring match in city name (e.g., "San Francisco", "SF", "California")

**Experience level** — `MAX_EXPERIENCE_YEARS=4` auto-rejects "senior staff", "principal", "director" and accepts "junior", "new grad", "0-4 years".

---

## Testing

### Unit Tests

```bash
# Full visibility into each module
uv run pytest tests/test_resume_pipeline.py -v -s

# Output shows:
# ✓ Master resume has 3 experiences
# ✓ SelectionManifest structure (IDs + indices)
# ✓ Builder copied verbatim: ...
# ✓ Compiler produced PDF: 61,887 bytes
# 🔄 Full Pipeline Test: ...
```

### E2E Test

```bash
# Detects real job from Anthropic → generates resume → sends Discord
python test_resume_e2e.py

# Output:
# Fetching jobs from Anthropic...
# Selected: Model Quality Software Engineer, Claude Code @ Anthropic
# PDF generated: 67,004 bytes
# Sending to Discord...
# Sent to Discord!
```

---

## Deployment

### Local Development

```bash
# Manual run
python test_resume_e2e.py

# Continuous monitoring (manual check every hour)
while true; do python test_resume_e2e.py; sleep 3600; done
```

### Production (Hetzner VPS)

```bash
# 1. Install system dependencies
sudo apt install python3.11 texlive-latex-base texlive-fonts-recommended texlive-latex-extra

# 2. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# 3. Clone & setup
git clone https://github.com/Yuqi2002/agentic-job-hunting ~/job-hunter
cd ~/job-hunter
uv sync

# 4. Configure
cp .env.example .env
nano .env  # Edit with your keys

# 5. Create systemd service
sudo tee /etc/systemd/system/job-hunter.service > /dev/null << 'EOF'
[Unit]
Description=Agentic Job Hunter
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/job-hunter
Environment="PATH=/home/ubuntu/.local/bin:/usr/bin:/usr/local/bin"
ExecStart=/home/ubuntu/.local/bin/uv run python -m src.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 6. Enable & start
sudo systemctl enable --now job-hunter
sudo systemctl status job-hunter

# View logs
sudo journalctl -u job-hunter -f
```

### Discord Bot Setup

To enable the human-in-the-loop approval system, you need to:

1. **Create a Discord bot application**:
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Click "New Application"
   - Give it a name (e.g., "Job Hunter Bot")
   - Go to "Bot" → "Add Bot"
   - Under "TOKEN", click "Copy" to get your `DISCORD_BOT_TOKEN`

2. **Get your bot token**:
   - Paste the bot token into `.env` as `DISCORD_BOT_TOKEN=...`

3. **Get your Discord channel ID**:
   - In Discord, enable Developer Mode (User Settings → Advanced → Developer Mode)
   - Right-click on the channel where you want job notifications
   - Click "Copy Channel ID"
   - Paste into `.env` as `DISCORD_CHANNEL_ID=123456789...`

4. **Invite the bot to your server**:
   - In Developer Portal, go to OAuth2 → URL Generator
   - Select scopes: `bot`
   - Select permissions: `Send Messages`, `Embed Links`, `Attach Files`, `Read Message History`, `Read Messages/View Channels`
   - Copy the generated URL and open it in your browser to add the bot to your server

5. **Verify bot permissions**:
   - The bot needs: `send_messages`, `embed_links`, `attach_files`, `read_message_history` in your target channel
   - Right-click channel → Edit Channel → Permissions → Bot permissions

The bot will automatically start listening for ✅ reactions when the service starts (if `DISCORD_BOT_TOKEN` and `DISCORD_CHANNEL_ID` are set).

### With Grafana Logging

The system uses `structlog` for JSON logging:

```bash
# Enable JSON output to stdout
export LOG_LEVEL=INFO

# Pipe to Promtail (if you have Grafana Loki running)
# In your Promtail config, add:
# - job_name: job-hunter
#   static_configs:
#     - targets:
#         - localhost
#       labels:
#         job: job-hunter
#         __path__: /var/log/job-hunter.log
```

---

## Cost

**OpenAI GPT-4o mini** ($0.15/$0.60 per 1M input/output tokens):

Per job (all matched jobs):
- Job summary (~1500 input + 200 output tokens): ~$0.00092

Per approved job (only generated resumes):
- Selector (~800 input + 200 output tokens): ~$0.00024
- ATS optimizer (~3000 input + 1000 output tokens): ~$0.00105
- **Total per resume: ~$0.0013** (91% cheaper than Claude Haiku!)

**Detection**: Negligible (API calls are free)

**Daily cost example** (259 matched jobs/day, ~30% approval rate):
- Job summaries (all 259): ~$0.24/day = **~$7.20/month**
- Resume generation (78 approved): ~$0.10/day = **~$3/month**
- Job detection: $0/day (free APIs)
- **Total: ~$10/month** (human-in-the-loop approval prevents wasting tokens on rejected jobs)

---

## Customization

### Add New Data Sources

Implement `src/detection/base.py:BaseScraper`:

```python
class YourSourceScraper(BaseScraper):
    async def fetch_jobs(self, client: httpx.AsyncClient) -> list[RawJob]:
        # Fetch & parse jobs
        return [RawJob(...), ...]
```

Then register in `src/detection/scheduler.py`.

### Modify Filtering Logic

Edit `src/filter/matcher.py:JobMatcher`:

```python
def match(self, title: str, location: str, description: str) -> MatchResult:
    # Custom role/location/experience logic
    ...
```

### Customize Resume Template

Update `templates/resume.tex` — uses Jinja2 variables:
- `\VAR{meta.name}`, `\VAR{meta.email}`, `\VAR{meta.linkedin}`
- `\VAR{education}`
- `\VAR{experience}` (array of `{title, company, dates, location, bullets}`)
- `\VAR{projects}` (array of `{name, bullets}`)
- `\VAR{skills}` (array of `{category, value}`)

### Modify ATS Rules

Edit `src/resume/ats.py` — update the 7 rules in `_USER_PROMPT_TEMPLATE`.

---

## Troubleshooting

### Jobs not being detected
- Check `TARGET_ROLES` and `TARGET_CITIES` in `.env`
- Verify company list is cached: `ls data/cache/`
- Check Discord webhook URL is valid
- View logs: `tail -f data/jobs.log` or `journalctl -u job-hunter -f`

### Resume PDF not generating
- Ensure `pdflatex` is installed: `which pdflatex`
- Check LaTeX template: `templates/resume.tex` must be valid
- Debug .tex file: `cat data/debug_resume.tex` (saved on failure)
- Run unit tests: `uv run pytest tests/test_resume_pipeline.py::TestCompiler -v`

### LaTeX compilation errors
- "Misplaced alignment tab" → unescaped `&` in bullet text (shouldn't happen, report if it does)
- "File ended while scanning" → missing closing brace (check template)
- "Undefined control sequence" → unsupported LaTeX command (check template)

### OpenAI API errors
- Check `OPENAI_API_KEY` is valid in `.env`
- Check rate limits: varies by account tier
- Verify job description is < 3000 chars (auto-truncated in code)

### Discord bot not receiving reactions
- Verify bot is in the server: Discord Settings → Server Members (look for bot name)
- Check bot permissions: Right-click channel → Permissions. Bot needs:
  - `Send Messages`
  - `Embed Links`
  - `Attach Files`
  - `Read Message History`
- Verify channel ID is correct: `DISCORD_CHANNEL_ID` should match the target channel
- Check logs: `journalctl -u job-hunter -f | grep "reaction"` to see if reactions are being detected
- Make sure you're reacting in the SAME channel where job notifications are sent
- Bot intents are correct in code (guilds + reactions, non-privileged)

### Job summaries not showing compensation or match %
- Ensure `OPENAI_API_KEY` is set
- Check that `data/master_resume.yaml` has valid skills and experiences
- Verify job description is not truncated: logs show actual description length

---

## Contributing

Issues, pull requests, and feature requests are welcome!

### Development

```bash
# Install dev deps (includes pytest)
uv sync --group dev

# Run tests
uv run pytest -v -s

# Format code (using uv's built-in tools)
uv run black src/ tests/
uv run isort src/ tests/

# Type check
uv run mypy src/
```

### Architecture Goals

- **Determinism**: Same input always produces same output
- **Modularity**: Each layer has a single job
- **Testability**: Every module has tests with full visibility
- **No hallucination**: Claude never copies text or fabricates metrics
- **Open source**: Zero dependencies on closed APIs except Claude

---

## License

MIT — Use freely, modify, redistribute. See LICENSE file.

---

## Acknowledgments

- **Feashliaa**: [job-board-aggregator](https://github.com/Feashliaa/job-board-aggregator) for company discovery
- **OpenAI**: GPT-4o mini for cost-effective job summaries and resume tailoring (91% cheaper than alternatives)
- **Discord.py**: Python Discord bot library for human-in-the-loop approval system
- **Discord**: Webhook + bot APIs for notifications and reactions
- **ATS Research**: Heavy inspiration from Jobscan, Resume Worded, and industry ATS documentation

---

## FAQ

**Q: Will this auto-apply to jobs?**
A: No. This generates tailored resumes and sends them to Discord. You review summaries, approve with ✅, and apply manually.

**Q: How does the approval system work?**
A: All matched jobs get a summary with compensation + match % as a Discord embed. You react ✅ to approve, which triggers tailored resume generation and reply. This saves tokens on jobs you don't want.

**Q: What's shown in job summaries?**
A: Company, title, location, compensation, resume match % (% of job keywords found in your master resume), and matching keywords.

**Q: Can I use my own LaTeX resume?**
A: Yes! Replace `templates/resume.tex` with your Overleaf file. Ensure single-column layout and Jinja2 `\VAR{...}` variables.

**Q: What if a job is a bad match?**
A: The filter is conservative (better to over-include), so you get summaries to decide. If job summaries are too noisy, adjust `TARGET_ROLES` and `TARGET_CITIES`. You can also just skip jobs you don't want to approve.

**Q: How often does it check?**
A: Every 30 minutes (configurable in `src/detection/scheduler.py`). Full cycle through all 6,262 companies takes ~2.5 hours.

**Q: How much does it cost?**
A: ~$10/month using GPT-4o mini ($7/month for summaries, $3/month for approved resumes at 30% approval rate). See [Cost](#cost) section.

**Q: Can I test without deploying?**
A: Absolutely. `python test_e2e_approval.py` runs the full pipeline end-to-end locally, including Discord bot listener.

---

## What's Next?

**Phase 3** (future):
- Additional sources: SimplifyJobs, YC Work at a Startup, The Muse, Remotive
- Batch API for cost optimization
- Grafana dashboard for monitoring
- LinkedIn/Indeed integration (if possible)
- Email forwarding (in addition to Discord)

---

**Built by Yuqi Zhou** | [GitHub](https://github.com/Yuqi2002) | [LinkedIn](https://linkedin.com/in/yuqizhou2002/)
