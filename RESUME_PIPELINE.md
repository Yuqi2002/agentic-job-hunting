# Resume Pipeline — Execution Flow & Visibility

## Architecture Summary

```
job_data                master_resume.yaml
  │                              │
  └──────────────────────────────┘
         │
         ▼
   selector.py (Claude Haiku)
   ├─ Analyzes JD + compact master summary
   ├─ Selects 2-3 experiences, 1-2 projects, exactly 1 leadership, relevant skills
   └─ Returns: SelectionManifest (IDs + bullet indices ONLY — no text)
         │
         ├─ experiences: [BulletSelection(id="exp-servicenow-fte", bullet_indices=[2, 0, 1]), ...]
         ├─ projects: [BulletSelection(id="proj-ucf-attendance", bullet_indices=[0, 1]), ...]
         ├─ leadership_ids: ["lead-toastmasters"]
         └─ skills: {"languages": [...], "frameworks": [...], ...}
         │
         ▼
   builder.py (Pure Python)
   ├─ NO Claude, NO network, 100% deterministic
   ├─ Looks up each ID in master resume
   ├─ Copies bullet text verbatim at specified indices
   └─ Returns: ResumeContent (fully resolved text, no LaTeX escaping yet)
         │
         ├─ experience: [ExperienceEntry(title="...", company="...", bullets=["original text", ...]), ...]
         ├─ projects: [ProjectEntry(name="...", bullets=["original text", ...]), ...]
         ├─ leadership: [LeadershipEntry(title="...", description="..."), ...]
         └─ skills: [SkillEntry(category="Languages", value="Python, TypeScript, ..."), ...]
         │
         ▼
   ats.py (Claude Haiku)
   ├─ Optimizes bullets for ATS keyword matching and structure
   ├─ 7 rules: keyword injection, strong verbs, XYZ bullets, special chars, skills ordering, dates, guardrails
   ├─ Returns SAME JSON structure with optimized text
   └─ Returns: ResumeContent (ATS-optimized, still no LaTeX escaping)
         │
         ▼
   compiler.py (Pure Python + pdflatex)
   ├─ Applies escape_latex() to ALL text fields:
   │   • experience[].bullets[]
   │   • projects[].bullets[]
   │   • leadership[].title, leadership[].description
   │   • skills[].category, skills[].value
   ├─ Renders Jinja2 template with escaped content
   ├─ Writes .tex file
   ├─ Runs pdflatex in temporary directory
   └─ Returns: bytes (raw PDF)
         │
         ▼
   PDF file + Discord notification
```

---

## Test Results: Full Visibility

### 1. LaTeX Escaping (`test_escape_latex`)
**What's being tested**: Special characters are escaped correctly without double-escaping.

```
Original: Reduced cost by 40% using Python & AWS (C# integration). Score: 95/100.
Escaped:  Reduced cost by 40\% using Python \& AWS (C\# integration). Score: 95/100.
```

✅ **All 3 tests passed**:
- `test_escapes_special_characters` — each char (`%`, `&`, `$`, `#`, `_`, `~`, `^`) escaped correctly
- `test_no_double_escape` — already-escaped sequences don't get escaped again
- `test_multiple_special_chars_in_text` — complex text handled correctly

---

### 2. Selector (Claude picks IDs only) (`test_selector_returns_manifest_with_ids_only`)
**What's being tested**: Selector returns only ID references, never bullet text.

```
✓ Master resume has 3 experiences
  - exp-servicenow-fte: Software Engineer @ ServiceNow
    [0] Engineered core features of CRIR (Customer Risk Intelligence...
    [1] Developed UI/UX and backend features for C2C (Commit to Cons...
    [2] Spearheaded AI-native transformation...
    [3] Led 3 AI adoption workshops...
    [4] Maintained and upgraded the Engineering Excellence Workspace...
  - exp-servicenow-intern: Software Engineer Intern @ ServiceNow
    [0] Developed a full-stack employee onboarding application...
    [1] Engineered REST API integration with NowLearning...
    [2] Earned ServiceNow Certified Application Developer...
  - exp-universal-intern: Software Engineer Intern @ Universal Studios
    [0] Maintained and debugged Universal Orlando's ticket processing...
    [1] Executed end-to-end server migration...
```

✅ **Selector tests passed**:
- `test_selector_returns_manifest_with_ids_only` — shows master resume structure with IDs
- `test_sample_selection_manifest` — shows SelectionManifest output format:
  ```
  ✓ SelectionManifest structure:
    Experiences: 2 entries
      - exp-servicenow-fte → bullets [2, 0, 1]
      - exp-servicenow-intern → bullets [0, 1]
    Projects: 1 entries
    Leadership: 1 entries
    Skills: 4 categories
  ```

---

### 3. Builder (Verbatim copy from YAML) (`test_builder_creates_resume_content`)
**What's being tested**: Builder copies text exactly as-is, no modifications.

```
✓ Builder copied verbatim:
  Experience: ServiceNow → Software Engineer
  Bullet: Engineered core features of CRIR (Customer Risk Intelligence and Response), Serv...
  Skills: ['Python', 'React.js', 'AWS', '']
```

✅ **Builder tests passed**:
- `test_builder_creates_resume_content` — verifies text is copied verbatim
- `test_builder_error_on_invalid_id` — raises KeyError on missing ID
- `test_builder_error_on_invalid_index` — raises IndexError on out-of-range bullet index

---

### 4. Compiler (LaTeX + pdflatex) (`test_compiler_creates_pdf`)
**What's being tested**: Compiler produces valid PDF with proper escaping and rendering.

```
✓ Compiler produced PDF: 61,887 bytes
✓ Compiler escaped special chars in bullets before PDF generation
```

✅ **Compiler tests passed**:
- `test_compiler_creates_pdf` — produces valid PDF (starts with `%PDF` magic bytes)
- `test_compiler_escapes_latex` — escapes special chars before compiling

---

### 5. Full Pipeline (`test_manifest_to_content_to_pdf`)
**What's being tested**: Complete end-to-end flow works correctly.

```
🔄 Full Pipeline Test
  1. Selection manifest created
     - 2 experiences selected
     - 1 projects selected
  2. Builder created ResumeContent
     - 3 experience bullets
     - 2 project bullets
  3. Compiler produced PDF: 67,033 bytes
  ✅ Full pipeline working!
```

---

## Key Guarantees

| Step | Module | Claude? | Text Modified? | Output Type |
|---|---|---|---|---|
| 1. Selection | `selector.py` | ✅ Haiku | ❌ No (IDs only) | `SelectionManifest` |
| 2. Building | `builder.py` | ❌ Pure Python | ❌ No (verbatim copy) | `ResumeContent` |
| 3. ATS Opt | `ats.py` | ✅ Haiku | ✅ Yes (restructured) | `ResumeContent` |
| 4. Compile | `compiler.py` | ❌ Pure Python | ✅ Yes (LaTeX escaping) | `bytes` (PDF) |

---

## How to Run Tests

```bash
cd /Users/yuqizhou/Downloads/"Agentic Job Hunting"

# Run all tests with full output
uv run pytest tests/test_resume_pipeline.py -v -s

# Run specific test class
uv run pytest tests/test_resume_pipeline.py::TestBuilder -v -s

# Run with minimal output
uv run pytest tests/test_resume_pipeline.py -v
```

---

## How to Run Full E2E Test

```bash
# Detects real job from Anthropic → generates resume → sends to Discord
cd /Users/yuqizhou/Downloads/"Agentic Job Hunting"
python test_resume_e2e.py
```

Output:
```
Fetching jobs from Anthropic...
2026-04-01 15:45:55 [info     ] scrape_completed               company=Anthropic jobs_found=431 source_board=greenhouse
Selected: Model Quality Software Engineer, Claude Code @ Anthropic
PDF generated: 67,004 bytes
Sending to Discord...
Sent to Discord!
```

---

## Code Organization

```
src/resume/
├── __init__.py                # Exports generate_resume() convenience function
├── types.py                   # Shared dataclasses (SelectionManifest, ResumeContent, etc.)
├── selector.py                # Claude: IDs + bullet indices
├── builder.py                 # Pure Python: verbatim copy by ID
├── ats.py                     # Claude: ATS optimization
└── compiler.py                # Pure Python: LaTeX escape + render + compile

tests/
├── __init__.py
└── test_resume_pipeline.py    # 11 comprehensive tests, all passing

test_resume_e2e.py             # Integration test with real job detection & Discord
```

---

## What Each Module Does (In Detail)

### `selector.py` — Claude Haiku Selection
- **Input**: Job description + compact master resume summary
- **Output**: SelectionManifest (IDs + bullet_indices)
- **Logic**: Claude analyzes JD, returns which experience/project/skill entries are most relevant
- **Key Guarantee**: Only returns IDs — Claude never sees or copies bullet text
- **Model**: claude-haiku-4-5-20251001 (800 tokens max)

### `builder.py` — Pure Python Verbatim Copy
- **Input**: SelectionManifest + full master_resume.yaml
- **Output**: ResumeContent (all text fields fully populated)
- **Logic**: Lookup each ID in master, copy exp["bullets"][i]["text"] exactly
- **Key Guarantee**: Zero text modification, 100% deterministic
- **Network**: None (purely local YAML lookup)

### `ats.py` — Claude Haiku ATS Optimization
- **Input**: ResumeContent + job description
- **Output**: ResumeContent with optimized bullets
- **Logic**: Claude rewrites bullets for ATS keyword matching, strong verbs, XYZ structure
- **Key Guarantee**: Never changes company/title/dates/location; never adds/removes bullets
- **Model**: claude-haiku-4-5-20251001 (3000 tokens max)

### `compiler.py` — Pure Python LaTeX + pdflatex
- **Input**: ResumeContent + master_resume.yaml
- **Output**: bytes (PDF)
- **Logic**: Escape LaTeX chars → render Jinja2 template → run pdflatex → return PDF bytes
- **Key Guarantee**: All special chars escaped before rendering; template never modified
- **Network**: None (local pdflatex execution)

---

## Performance Notes

- **Claude calls**: 2 (selector + ats), each ~1-2 seconds
- **Compilation**: ~1 second (pdflatex)
- **Total pipeline**: ~5-7 seconds from job to PDF
- **Cost per resume**: ~$0.01 (Haiku is cheap)

---

## Invariants (Must Always Hold)

1. ✅ **Claude never copies text** — selector returns IDs only
2. ✅ **LaTeX escaping is always programmatic** — never asked of Claude
3. ✅ **master_resume.yaml is source of truth** — never modified by Claude
4. ✅ **Builder is pure Python** — no network, fully deterministic
5. ✅ **All tests pass** — 11/11 passing with full visibility
