"""ATS optimization pass — rewrites resume bullets for keyword matching and structure."""
from __future__ import annotations

import dataclasses
import json

from openai import OpenAI

from src.resume.types import (
    ExperienceEntry,
    LeadershipEntry,
    ProjectEntry,
    ResumeContent,
    SkillEntry,
)

_SYSTEM_PROMPT = """\
You are an expert ATS (Applicant Tracking System) resume optimizer. Your job is to rewrite the resume bullets and skills to maximize ATS parse scores for the specific job description below, without fabricating any information."""

_USER_PROMPT_TEMPLATE = """\
## Job Description
**Title**: {title}
**Company**: {company}
**Location**: {location}

{description}

## Current Tailored Resume (JSON)
{content_json}

## Your Task
Optimize the resume JSON for ATS. Return the EXACT same JSON structure with the same fields — only modify the text content of bullets, skill values, and leadership descriptions. Do NOT change company names, job titles, dates, locations, or project names.

---

## RULE 1 — Keyword Extraction and Injection
Step 1: Extract the 6-8 most critical technical keywords from the job description (e.g. specific languages, frameworks, tools, methodologies, platforms explicitly named).
Step 2: For each extracted keyword, ensure it appears verbatim at least once in either a bullet point or the skills section.
Step 3: Use EXACT phrasing from the JD. If the JD says "React.js", use "React.js" not "React" or "ReactJS". If it says "distributed systems", use "distributed systems" not "scalable architecture".
Step 4: For ambiguous tech terms, include both the full name and abbreviation at first mention: e.g., "Kubernetes (K8s)", "Machine Learning (ML)".
Step 5: Keyword density target is 2-3% of total word count — natural integration only. Do not stuff.

## RULE 2 — Action Verb Strength
Replace ANY of these weak verbs/phrases immediately — they kill ATS scores:
BANNED: "Worked on", "Helped with", "Assisted", "Responsible for", "Involved in", "Participated in", "Supported", "Contributed to", "Part of the team"

Replace with STRONG verbs matched to the type of work:
- Architecture/Design work → Architected, Engineered, Designed, Restructured, Standardized
- Feature/Code work → Developed, Built, Implemented, Constructed
- Performance/Efficiency work → Optimized, Reduced, Accelerated, Streamlined, Improved
- Automation/CI-CD work → Automated, Deployed, Integrated, Orchestrated, Instrumented
- Scaling/Infrastructure work → Scaled, Migrated, Containerized, Provisioned, Distributed
- Debugging/Fix work → Resolved, Diagnosed, Debugged, Troubleshot, Identified
- Testing work → Validated, Verified, Wrote tests for
- Leadership/Collab work → Led, Mentored, Spearheaded, Drove, Coordinated

Rules for action verbs:
- Past tense for past roles, present tense for current role only
- Never start two consecutive bullets in the same role with the same verb
- Use the strongest verb that accurately describes the work

## RULE 3 — Bullet Structure (XYZ / CAR format)
Rewrite bullets to follow the XYZ format where possible:
  "Accomplished [X] as measured by [Y] by doing [Z]"
  Example: "Reduced API latency by 62% (850ms → 320ms) by introducing Redis caching layer for hot database queries"

Priority order for bullet structure:
1. Lead with the metric/outcome when a strong one exists: "Reduced X by Y% by doing Z"
2. If no metric exists, lead with the action and include scale: "Engineered microservices migration for 2M+ daily active users using Kubernetes and Helm charts"
3. Always include: WHAT you did + at WHAT SCALE + with WHAT TECH + WHAT OUTCOME
4. All four elements give ATS multiple keyword surfaces to score against

Rules:
- Preserve ALL existing numbers and percentages — never fabricate or change them
- If a bullet has a metric, make it prominent (move to front of bullet)
- Each bullet should mention at least one specific technology or tool
- Target bullet length: 15-25 words. Under 10 words is too weak; over 30 is too long.
- 3-4 bullets per role is optimal; do not add bullets

## RULE 4 — Special Character Safety (ATS Parser Compliance)
Replace ALL of the following — they corrupt parsing in Taleo and older iCIMS:
- Smart/curly quotes → straight quotes
- Em dash — → hyphen-minus - or en dash --
- Ellipsis character … → three periods ...
- Decorative bullets → remove or use plain hyphen
- Math symbols ≤ ≥ ≠ → spell out
- Emojis → remove entirely

IMPORTANT: Do NOT add any LaTeX escape characters (backslashes). Write plain text only.
LaTeX escaping will be applied programmatically after your output.
If you output "500%" that is correct. Do NOT output "500\\%".

## RULE 5 — Skills Section Optimization
- Order skills categories: most JD-relevant first, least relevant last
- Within each category, list JD-mentioned tools first, then others
- Include BOTH the exact form from the JD AND any equivalent you already have listed
- Include version numbers only if specified in the JD
- Do not add skills you don't have — only reorder and standardize existing ones

## RULE 6 — Date Format Consistency
All dates must use exactly one format throughout: "Mon YYYY" (e.g., "Jan 2024")
- "Present" for current role end date (not "Current", "Now", "Ongoing")
- Separator between start/end: " -- " (space hyphen hyphen space)
- If any date uses a different format, standardize it to "Mon YYYY"

## RULE 7 — What NOT to Change
- Company names, job titles, dates, locations — copy verbatim from input
- Project names — copy verbatim
- Do NOT add new bullet points or expand to more than the input bullet count
- Do NOT hallucinate metrics, tools, or accomplishments not present in the input
- Do NOT change the structure/keys of the JSON

---

Return ONLY the optimized JSON object with the same structure as the input. No explanation, no markdown fences, no commentary — just the raw JSON starting with {{."""


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` wrapping if present."""
    stripped = text.strip()
    if stripped.startswith("```"):
        # Remove opening fence (```json or ```)
        first_newline = stripped.index("\n")
        stripped = stripped[first_newline + 1 :]
        # Remove closing fence
        if stripped.endswith("```"):
            stripped = stripped[: -3].rstrip()
    return stripped


def _parse_response(raw: str) -> ResumeContent:
    """Parse Claude's JSON response into a ResumeContent dataclass."""
    cleaned = _strip_markdown_fences(raw)
    parsed = json.loads(cleaned)

    experiences = [
        ExperienceEntry(
            title=exp["title"],
            company=exp["company"],
            dates=exp["dates"],
            location=exp["location"],
            bullets=exp["bullets"],
        )
        for exp in parsed["experience"]
    ]

    projects = [
        ProjectEntry(
            name=proj["name"],
            bullets=proj["bullets"],
        )
        for proj in parsed["projects"]
    ]

    leadership = [
        LeadershipEntry(
            title=lead["title"],
            description=lead["description"],
        )
        for lead in parsed["leadership"]
    ]

    skills: list[SkillEntry] = []
    for skill in parsed["skills"]:
        # Handle Claude sometimes using "items" instead of "value"
        value = skill.get("value") or skill.get("items", "")
        if isinstance(value, list):
            value = ", ".join(value)
        skills.append(SkillEntry(category=skill["category"], value=value))

    return ResumeContent(
        experience=experiences,
        projects=projects,
        leadership=leadership,
        skills=skills,
    )


def optimize(content: ResumeContent, job: dict, api_key: str) -> ResumeContent:
    """Rewrite resume bullets for ATS keyword matching and structure.

    Args:
        content: Verbatim ResumeContent from builder.py.
        job: Dict with keys "title", "company", "location", "description".
        api_key: OpenAI API key.

    Returns:
        ResumeContent with ATS-optimized bullet text (plain text, no LaTeX).
    """
    content_json = json.dumps(dataclasses.asdict(content), indent=2)

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        title=job["title"],
        company=job["company"],
        location=job["location"],
        description=job["description"][:3000],
        content_json=content_json,
    )

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=3000,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    raw_response = response.choices[0].message.content
    return _parse_response(raw_response)
