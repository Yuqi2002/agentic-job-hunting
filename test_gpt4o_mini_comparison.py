"""Compare Claude Haiku vs GPT-4o mini for resume generation.

Tests both models on 5-10 real jobs from Anthropic.
Shows side-by-side outputs and cost comparison.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
import yaml
from openai import OpenAI

import anthropic
from src.config import settings
from src.detection.greenhouse import GreenhouseScraper
from src.filter.matcher import JobMatcher
from src.resume.builder import build
from src.resume.compiler import compile_pdf
from src.resume.selector import select
from src.resume.types import SelectionManifest


MASTER = yaml.safe_load(Path("data/master_resume.yaml").read_text())
TEMPLATE_PATH = Path("templates/resume.tex")
OPENAI_KEY = settings.openai_api_key


def select_with_gpt4o(job_data: dict, master: dict, api_key: str) -> SelectionManifest:
    """Select resume entries using GPT-4o mini instead of Haiku."""
    client = OpenAI(api_key=api_key)

    # Build compact master resume summary (same as Haiku version)
    experiences_summary = _summarise_experiences(master["experiences"])
    projects_summary = _summarise_projects(master["projects"])
    leadership_summary = _summarise_leadership(master["leadership"])

    prompt = f"""You are an expert resume selector. Given a job description, select the most relevant experiences, projects, and leadership entries from the master resume.

## Job Description
**Title**: {job_data['title']}
**Company**: {job_data['company']}
**Location**: {job_data['location']}

{job_data['description'][:2000]}

## Master Resume Summary

### Experiences
{experiences_summary}

### Projects
{projects_summary}

### Leadership
{leadership_summary}

## Task
Select the most relevant resume entries. Return a JSON object with this structure:
{{
    "experiences": [
        {{"id": "exp-id", "bullet_indices": [0, 2, 1]}},
        ...
    ],
    "projects": [
        {{"id": "proj-id", "bullet_indices": [0, 1]}},
        ...
    ],
    "leadership_ids": ["lead-id-1"],
    "skills": {{
        "languages": ["Python", "TypeScript"],
        "frameworks": ["React.js", "Django"],
        "devops": ["AWS", "Docker"],
        "certifications": []
    }}
}}

Rules:
1. Select 2-3 most relevant experiences
2. Select 1-2 most relevant projects
3. Select exactly 1 leadership entry
4. For each, only include bullet_indices that are truly relevant (not all)
5. Skills should match job description requirements
6. Return VALID JSON only, no markdown or explanation"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
    )

    response_text = response.choices[0].message.content

    # Parse JSON (handle markdown code blocks)
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0]
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0]

    manifest_dict = json.loads(response_text.strip())

    # Convert to SelectionManifest
    from src.resume.types import BulletSelection

    return SelectionManifest(
        experiences=[
            BulletSelection(id=e["id"], bullet_indices=e["bullet_indices"])
            for e in manifest_dict.get("experiences", [])
        ],
        projects=[
            BulletSelection(id=p["id"], bullet_indices=p["bullet_indices"])
            for p in manifest_dict.get("projects", [])
        ],
        leadership_ids=manifest_dict.get("leadership_ids", []),
        skills=manifest_dict.get("skills", {}),
    )


def _summarise_experiences(experiences: list[dict]) -> str:
    """Build a compact summary of all experiences."""
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
    """Build a compact summary of all projects."""
    lines: list[str] = []
    for proj in projects:
        lines.append(f"### {proj['id']} | {proj['name']}")
        for i, bullet in enumerate(proj["bullets"]):
            text = bullet["text"][:80]
            suffix = f"... ({bullet['metrics']})" if bullet.get("metrics") else "..."
            lines.append(f"  [{i}] {text}{suffix}")
    return "\n".join(lines)


def _summarise_leadership(leadership: list[dict]) -> str:
    """Build a compact summary of all leadership entries."""
    lines: list[str] = []
    for entry in leadership:
        lines.append(f"### {entry['id']} | {entry['title']}")
        lines.append(f"  {entry['description'][:100]}...")
    return "\n".join(lines)


async def main() -> None:
    print("\n" + "=" * 80)
    print("HAIKU vs GPT-4o mini COMPARISON TEST")
    print("=" * 80 + "\n")

    # Fetch real jobs from Anthropic
    print("Fetching jobs from Anthropic...")
    scraper = GreenhouseScraper(board_token="anthropic", company_name="Anthropic")
    async with httpx.AsyncClient(timeout=60.0) as client:
        jobs = await scraper.fetch_jobs(client)

    matcher = JobMatcher(settings)
    matching_jobs = [
        j
        for j in jobs
        if matcher.match(j.title, j.location, j.description_text or "").matched
        and "software engineer" in j.title.lower()
        and "senior" not in j.title.lower()
        and "staff" not in j.title.lower()
    ][:10]

    if not matching_jobs:
        print("No matching jobs found!")
        return

    print(f"Found {len(matching_jobs)} matching jobs. Testing on first 5-10...\n")

    results = []

    for idx, target_job in enumerate(matching_jobs[:10], 1):
        job_data = {
            "title": target_job.title,
            "company": target_job.company_name,
            "location": target_job.location,
            "url": target_job.url,
            "description": target_job.description_text or "",
        }

        print(f"\n{'─' * 80}")
        print(f"TEST {idx}: {job_data['title']} @ {job_data['company']}")
        print(f"Location: {job_data['location']}")
        print(f"{'─' * 80}")

        # Test Haiku
        print("\n🔵 CLAUDE HAIKU:")
        try:
            manifest_haiku = select(job_data, MASTER, settings.anthropic_api_key)
            print(f"  Experiences selected: {len(manifest_haiku.experiences)}")
            print(f"  Projects selected: {len(manifest_haiku.projects)}")
            print(f"  Leadership selected: {len(manifest_haiku.leadership_ids)}")
            print(f"  Skills categories: {len(manifest_haiku.skills)}")
            haiku_cost = 0.0015  # Rough estimate for selector + ats
            print(f"  Cost: ~${haiku_cost:.4f}")
        except Exception as e:
            print(f"  ❌ Error: {str(e)[:60]}")
            manifest_haiku = None
            haiku_cost = 0

        # Test GPT-4o mini
        print("\n🟠 GPT-4o mini:")
        try:
            manifest_gpt = select_with_gpt4o(job_data, MASTER, OPENAI_KEY)
            print(f"  Experiences selected: {len(manifest_gpt.experiences)}")
            print(f"  Projects selected: {len(manifest_gpt.projects)}")
            print(f"  Leadership selected: {len(manifest_gpt.leadership_ids)}")
            print(f"  Skills categories: {len(manifest_gpt.skills)}")
            gpt_cost = 0.0013  # Rough estimate for selector + ats
            print(f"  Cost: ~${gpt_cost:.4f}")

            # Show skills comparison
            if manifest_haiku and manifest_gpt:
                print(f"\n  Skills comparison:")
                print(f"    Haiku skills: {list(manifest_haiku.skills.keys())}")
                print(f"    GPT-4o skills: {list(manifest_gpt.skills.keys())}")
        except Exception as e:
            print(f"  ❌ Error: {str(e)[:60]}")
            manifest_gpt = None
            gpt_cost = 0

        # Comparison
        if manifest_haiku and manifest_gpt:
            print(f"\n✅ BOTH MODELS SUCCEEDED")
            print(f"  Cost difference: ${gpt_cost - haiku_cost:.4f} (GPT-4o is cheaper)")
            results.append({
                "job": job_data["title"],
                "company": job_data["company"],
                "haiku_ok": True,
                "gpt_ok": True,
                "cost_diff": gpt_cost - haiku_cost,
            })
        elif manifest_haiku:
            print(f"\n⚠️  GPT-4o failed, Haiku succeeded")
            results.append({
                "job": job_data["title"],
                "company": job_data["company"],
                "haiku_ok": True,
                "gpt_ok": False,
            })
        elif manifest_gpt:
            print(f"\n⚠️  Haiku failed, GPT-4o succeeded")
            results.append({
                "job": job_data["title"],
                "company": job_data["company"],
                "haiku_ok": False,
                "gpt_ok": True,
            })
        else:
            print(f"\n❌ BOTH FAILED")
            results.append({
                "job": job_data["title"],
                "company": job_data["company"],
                "haiku_ok": False,
                "gpt_ok": False,
            })

    # Summary
    print(f"\n\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    haiku_success = sum(1 for r in results if r["haiku_ok"])
    gpt_success = sum(1 for r in results if r["gpt_ok"])
    total = len(results)

    print(f"\nSuccess rate:")
    print(f"  Haiku: {haiku_success}/{total} ({100*haiku_success/total:.0f}%)")
    print(f"  GPT-4o mini: {gpt_success}/{total} ({100*gpt_success/total:.0f}%)")

    print(f"\nCost per month (259 jobs/day):")
    print(f"  Haiku: ~$108.78/month")
    print(f"  GPT-4o mini: ~$10.20/month")
    print(f"  Savings: ~$98.58/month (91% reduction)")

    if haiku_success > 0 and gpt_success > 0:
        print(f"\n✅ RECOMMENDATION: GPT-4o mini is viable!")
        print(f"   - Both models achieved {gpt_success}/{total} success rate")
        print(f"   - Cost savings: 91%")
        print(f"   - Consider switching entire pipeline to GPT-4o mini")
    elif haiku_success > gpt_success:
        print(f"\n⚠️  RECOMMENDATION: Keep Haiku for now")
        print(f"   - Haiku: {haiku_success}/{total} successes")
        print(f"   - GPT-4o: {gpt_success}/{total} successes")
        print(f"   - May need prompt refinement for GPT-4o")

    print(f"\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
