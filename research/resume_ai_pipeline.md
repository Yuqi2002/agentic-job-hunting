# Resume AI Pipeline Research

> Author: @resume-ai-architect | Date: 2026-03-24

## Key Decisions

| Decision | Recommendation | Rationale |
|---|---|---|
| Base document | **YAML** with tagged metadata per bullet | Human-editable + LLM-parseable |
| Pipeline | **3 separate API calls** (analyze → select → generate) | Debuggability, caching, model routing |
| Models | Haiku (JD analysis) + Sonnet (selection + writing) | Cost-effective; Opus unnecessary for short-form |
| Output format | **python-docx → .docx** + LibreOffice → PDF | .docx is most ATS-compatible |
| Cost optimization | **Batch API** (50% off) + **prompt caching** | ~$0.02-0.03/resume |
| Quality control | Rule-based checks + Haiku review call | Automated gate, no manual blocking |

## 3-Step Resume Pipeline

### Step 1: JD Analysis (Haiku)
- Extract: required_skills, preferred_skills, experience_level, role_type, key_themes, ats_keywords
- Output: Structured YAML

### Step 2: Experience Selection (Sonnet)
- Input: JD analysis + full master resume YAML
- Select: experiences, projects, skills, leadership items
- Output: Selected item IDs with relevance reasoning

### Step 3: Content Generation (Sonnet)
- Input: JD analysis + selected items + original bullets
- Generate: Tailored, human-sounding resume content
- Banned phrases: "leverage", "utilize", "spearhead", "cutting-edge"
- Temperature: 0.3-0.4

## Base Document Format (YAML)

```yaml
meta:
  name: "Your Name"
  email: "email@example.com"
  # ...

experiences:
  - id: "exp-company-role"
    company: "Company"
    title: "Role"
    dates: "Jun 2023 - Aug 2023"
    tags:
      role_types: [swe, backend, ml]
      skills: [python, go, kubernetes]
      impact_level: high
      years_relevance: [0, 1, 2, 3]
    bullets:
      - text: "Built X reducing Y by Z%"
        metrics: "Z% reduction"
        skills_demonstrated: [python, kubernetes]
        theme: performance
```

Key: every item has `tags` for filtering, bullets have sub-metadata for granular selection.

## ATS Optimization Rules

1. Use BOTH acronym and full form: "Machine Learning (ML)"
2. Mirror exact phrases from JD
3. Conventional section headers: "Experience", "Education", "Skills", "Projects"
4. No tables, columns, graphics (single-column only)
5. .docx preferred by ATS over PDF
6. Target 60%+ required skills, 30%+ preferred skills

## Output Pipeline

```
Claude Step 3 (YAML) → python-docx → .docx (ATS)
                      → libreoffice --headless → .pdf (Discord preview)
```

## Cost Analysis

| Scenario | Per Resume | Daily (50-100) | Monthly |
|---|---|---|---|
| Real-time API | ~$0.055 | $2.75-5.50 | $80-165 |
| Batch API + caching | ~$0.025 | $1.25-2.50 | $40-85 |

## Quality Control (Automated)

Rule-based checks (no API):
- Word count 350-550
- ATS keyword coverage ≥60%
- AI-ism regex detection
- Metric presence in ≥60% of bullets
- Action verb validation

LLM check (Haiku, ~$0.003):
- Rate relevance, authenticity, impact, ATS readiness (1-10)
- Gate: all scores ≥6, else retry (max 2x)

## A/B Testing

Store prompt variants in config, track with variant → quality scores → user feedback (Discord reactions). After 50+ data points, converge on winner.
