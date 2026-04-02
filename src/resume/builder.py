"""Resolve a SelectionManifest against the master resume dict into ResumeContent.

Pure lookup — no Claude calls, no network, no text modification.
"""
from __future__ import annotations

from src.resume.types import (
    BulletSelection,
    ExperienceEntry,
    LeadershipEntry,
    ProjectEntry,
    ResumeContent,
    SelectionManifest,
    SkillEntry,
)

CATEGORY_DISPLAY: dict[str, str] = {
    "languages": "Languages",
    "frameworks": "Frameworks / Tools",
    "devops": "DevOps / Cloud",
    "certifications": "Certifications",
}


def build(manifest: SelectionManifest, master: dict) -> ResumeContent:
    """Copy text verbatim from master YAML using IDs and indices.

    No text modification of any kind.

    Raises:
        KeyError: if an ID in the manifest is missing from master.
        IndexError: if a bullet index is out of range.
    """
    exp_lookup = {exp["id"]: exp for exp in master["experiences"]}
    proj_lookup = {proj["id"]: proj for proj in master["projects"]}
    lead_lookup = {lead["id"]: lead for lead in master["leadership"]}

    # -- experiences --
    experiences: list[ExperienceEntry] = []
    for sel in manifest.experiences:
        exp = _get(exp_lookup, sel.id, "Experience")
        bullets = _resolve_bullets(exp["bullets"], sel, "experience", exp["id"])
        experiences.append(
            ExperienceEntry(
                title=exp["title"],
                company=exp["company"],
                dates=exp["dates"],
                location=exp["location"],
                bullets=bullets,
            )
        )

    # -- projects --
    projects: list[ProjectEntry] = []
    for sel in manifest.projects:
        proj = _get(proj_lookup, sel.id, "Project")
        bullets = _resolve_bullets(proj["bullets"], sel, "project", proj["id"])
        projects.append(ProjectEntry(name=proj["name"], bullets=bullets))

    # -- leadership --
    leadership_entries: list[LeadershipEntry] = []
    for lid in manifest.leadership_ids:
        lead = _get(lead_lookup, lid, "Leadership")
        leadership_entries.append(
            LeadershipEntry(title=lead["title"], description=lead["description"])
        )

    # -- skills --
    skills: list[SkillEntry] = []
    for category, names in manifest.skills.items():
        skills.append(
            SkillEntry(
                category=CATEGORY_DISPLAY[category],
                value=", ".join(names),
            )
        )

    return ResumeContent(
        experience=experiences,
        projects=projects,
        leadership=leadership_entries,
        skills=skills,
    )


# ── helpers ──────────────────────────────────────────────────────────


def _get(lookup: dict, id_: str, kind: str) -> dict:
    """Look up an entry by ID, raising a clear KeyError on miss."""
    try:
        return lookup[id_]
    except KeyError:
        raise KeyError(f"{kind} ID '{id_}' not found in master resume")


def _resolve_bullets(
    bullets: list[dict],
    sel: BulletSelection,
    kind: str,
    entry_id: str,
) -> list[str]:
    """Return bullet texts at the requested indices, validating bounds."""
    result: list[str] = []
    for i in sel.bullet_indices:
        if i < 0 or i >= len(bullets):
            raise IndexError(
                f"Bullet index {i} out of range for {kind} '{entry_id}' "
                f"(has {len(bullets)} bullets)"
            )
        result.append(bullets[i]["text"])
    return result
