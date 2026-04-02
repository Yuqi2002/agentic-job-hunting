"""Job summary generation — extracts comp and calculates resume match % via GPT-4o mini."""
from __future__ import annotations

import json

from openai import OpenAI

_MODEL = "gpt-4o-mini"

_PROMPT = """\
Given a job description, extract the following information and return ONLY a JSON object.

## Job Posting
Title: {title}
Company: {company}
Location: {location}

Description:
{description}

## Master Resume Keywords
{resume_keywords}

## Task
Return a JSON object with EXACTLY these fields:
{{
    "total_comp": "e.g. $150k-$200k, $180k, Competitive, Not listed",
    "match_pct": <integer 0-100>,
    "match_keywords": ["keyword1", "keyword2", "keyword3"]
}}

Rules:
- total_comp: Extract base+equity if mentioned. If only base, say "$Xk base". If not listed, say "Not listed".
- match_pct: Count how many of the job's required tech skills appear in the master resume keywords. Integer only.
- match_keywords: List the 3-5 specific skills/keywords from the JD that match the resume (empty list if none).
- Return raw JSON only, no markdown, no explanation."""


def _build_resume_keywords(master: dict) -> str:
    """Extract a flat list of all skills from the master resume."""
    keywords: set[str] = set()
    for category, items in master.get("skills", {}).items():
        if category == "soft_skills":
            continue
        keywords.update(items)
    # Also pull tech terms from experience bullets
    for exp in master.get("experiences", []):
        for bullet in exp.get("bullets", []):
            if bullet.get("skills_demonstrated"):
                keywords.update(bullet["skills_demonstrated"])
    return ", ".join(sorted(keywords))


def summarize(job: dict, master: dict, api_key: str) -> dict:
    """Extract comp and calculate match % for a job posting.

    Args:
        job: Dict with keys title, company, location, description.
        master: Parsed master_resume.yaml.
        api_key: OpenAI API key.

    Returns:
        Dict with keys: total_comp, match_pct, match_keywords.
    """
    resume_keywords = _build_resume_keywords(master)

    prompt = _PROMPT.format(
        title=job["title"],
        company=job["company"],
        location=job.get("location", ""),
        description=job.get("description", "")[:2000],
        resume_keywords=resume_keywords,
    )

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=_MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0].strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {}

    return {
        "total_comp": result.get("total_comp", "Not listed"),
        "match_pct": int(result.get("match_pct", 0)),
        "match_keywords": result.get("match_keywords", []),
    }
