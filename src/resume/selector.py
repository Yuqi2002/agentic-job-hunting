"""GPT-4o mini selection pass — picks the most relevant resume entries for a JD.

Calls GPT-4o mini with a compact summary of the master resume + job description
and returns a SelectionManifest (IDs and bullet indices only, no text).
"""
from __future__ import annotations

import json
import re

from openai import OpenAI

from src.resume.types import BulletSelection, SelectionManifest

_MODEL = "gpt-4o-mini"
_MAX_TOKENS = 1000
_EXPECTED_SKILL_KEYS = {"languages", "frameworks", "devops", "certifications"}


def _summarise_experiences(experiences: list[dict]) -> str:
    """Build a compact summary of all experiences for the prompt."""
    lines: list[str] = []
    for exp in experiences:
        header = (
            f"### {exp['id']} | {exp['title']} @ {exp['company']} "
            f"| {exp['dates']} | {exp['location']}"
        )
        lines.append(header)
        for i, bullet in enumerate(exp["bullets"]):
            text = bullet["text"][:80]
            suffix = f"... ({bullet['metrics']})" if bullet.get("metrics") else "..."
            lines.append(f"  [{i}] {text}{suffix}")
    return "\n".join(lines)


def _summarise_projects(projects: list[dict]) -> str:
    """Build a compact summary of all projects for the prompt."""
    lines: list[str] = []
    for proj in projects:
        lines.append(f"### {proj['id']} | {proj['name']}")
        for i, bullet in enumerate(proj["bullets"]):
            text = bullet["text"][:80]
            suffix = f"... ({bullet['metrics']})" if bullet.get("metrics") else "..."
            lines.append(f"  [{i}] {text}{suffix}")
    return "\n".join(lines)


def _summarise_leadership(leadership: list[dict]) -> str:
    """Build a compact summary of all leadership entries for the prompt."""
    lines: list[str] = []
    for entry in leadership:
        lines.append(f"### {entry['id']} | {entry['title']}")
        lines.append(f"  {entry['description'][:120]}...")
    return "\n".join(lines)


def _summarise_skills(skills: dict[str, list[str]]) -> str:
    """List available skills by category."""
    lines: list[str] = []
    for category, items in skills.items():
        if category == "soft_skills":
            continue
        lines.append(f"{category.title()}: {', '.join(items)}")
    return "\n".join(lines)


def _build_prompt(job: dict, master: dict) -> str:
    """Assemble the full selection prompt."""
    exp_summary = _summarise_experiences(master["experiences"])
    proj_summary = _summarise_projects(master["projects"])
    lead_summary = _summarise_leadership(master["leadership"])
    skill_summary = _summarise_skills(master["skills"])

    return f"""You are a resume optimization assistant. Given a job description and a candidate's full experience inventory, select the most relevant entries to include on a one-page resume.

## Job Description
Title: {job["title"]}
Company: {job["company"]}
Location: {job["location"]}

{job["description"]}

## Candidate's Experience Inventory

### EXPERIENCES
{exp_summary}

### PROJECTS
{proj_summary}

### LEADERSHIP
{lead_summary}

### AVAILABLE SKILLS
{skill_summary}

## Selection Rules
- Select 2-3 experiences, with 2-4 bullet_indices each (most relevant first)
- Select 1-2 projects, with 2-3 bullet_indices each
- Select exactly 1 leadership entry
- Maximum 12-14 total bullets across all sections (one-page constraint)
- For skills: pick a subset of available skills most relevant to the JD, using exact names from the lists above
- Order bullet_indices by relevance (most relevant first = displayed first)

Return a JSON object with this exact structure (raw JSON only, no markdown fences, no commentary):

{{"experiences": [{{"id": "exp-id", "bullet_indices": [2, 0, 1]}}, ...], "projects": [{{"id": "proj-id", "bullet_indices": [0, 1]}}, ...], "leadership_ids": ["lead-id"], "skills": {{"languages": ["Python", "TypeScript"], "frameworks": ["React.js"], "devops": ["AWS", "Docker"], "certifications": ["ServiceNow Certified Application Developer"]}}}}"""


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences if present."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _validate(parsed: dict, master: dict) -> None:
    """Validate that all IDs and indices reference real master resume entries."""
    # Build lookup maps
    exp_map: dict[str, int] = {
        exp["id"]: len(exp["bullets"]) for exp in master["experiences"]
    }
    proj_map: dict[str, int] = {
        proj["id"]: len(proj["bullets"]) for proj in master["projects"]
    }
    lead_ids: set[str] = {entry["id"] for entry in master["leadership"]}

    # Validate experiences
    for entry in parsed["experiences"]:
        eid = entry["id"]
        if eid not in exp_map:
            raise ValueError(
                f"Experience ID '{eid}' not found in master resume. "
                f"Valid IDs: {sorted(exp_map.keys())}"
            )
        num_bullets = exp_map[eid]
        for idx in entry["bullet_indices"]:
            if idx < 0 or idx >= num_bullets:
                raise ValueError(
                    f"Bullet index {idx} out of range for experience '{eid}' "
                    f"(has {num_bullets} bullets, valid indices: 0-{num_bullets - 1})"
                )

    # Validate projects
    for entry in parsed["projects"]:
        pid = entry["id"]
        if pid not in proj_map:
            raise ValueError(
                f"Project ID '{pid}' not found in master resume. "
                f"Valid IDs: {sorted(proj_map.keys())}"
            )
        num_bullets = proj_map[pid]
        for idx in entry["bullet_indices"]:
            if idx < 0 or idx >= num_bullets:
                raise ValueError(
                    f"Bullet index {idx} out of range for project '{pid}' "
                    f"(has {num_bullets} bullets, valid indices: 0-{num_bullets - 1})"
                )

    # Validate leadership
    for lid in parsed["leadership_ids"]:
        if lid not in lead_ids:
            raise ValueError(
                f"Leadership ID '{lid}' not found in master resume. "
                f"Valid IDs: {sorted(lead_ids)}"
            )

    # Validate skills categories — allow subsets but reject unknown keys
    skill_keys = set(parsed["skills"].keys())
    unknown = skill_keys - _EXPECTED_SKILL_KEYS
    if unknown:
        raise ValueError(
            f"Unknown skills categories: {sorted(unknown)}. "
            f"Valid: {sorted(_EXPECTED_SKILL_KEYS)}"
        )


def select(job: dict, master: dict, api_key: str) -> SelectionManifest:
    """Call GPT-4o mini to select the most relevant resume entries for a job.

    Args:
        job: Dict with keys ``title``, ``company``, ``location``, ``description``.
        master: Parsed master_resume.yaml dict with keys
                ``experiences``, ``projects``, ``leadership``, ``skills``.
        api_key: OpenAI API key string.

    Returns:
        A ``SelectionManifest`` containing only IDs and bullet indices.

    Raises:
        ValueError: If the model returns IDs or indices that don't exist in
                     the master resume.
    """
    prompt = _build_prompt(job, master)

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.choices[0].message.content
    cleaned = _strip_markdown_fences(raw)
    parsed = json.loads(cleaned)

    _validate(parsed, master)

    return SelectionManifest(
        experiences=[
            BulletSelection(id=e["id"], bullet_indices=e["bullet_indices"])
            for e in parsed["experiences"]
        ],
        projects=[
            BulletSelection(id=p["id"], bullet_indices=p["bullet_indices"])
            for p in parsed["projects"]
        ],
        leadership_ids=parsed["leadership_ids"],
        skills=parsed["skills"],
    )
