"""Shared dataclasses for the resume generation pipeline."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BulletSelection:
    """A reference to an experience/project by ID with specific bullet indices."""
    id: str                    # matches id field in master_resume.yaml
    bullet_indices: list[int]  # 0-based, in display order


@dataclass
class SelectionManifest:
    """Claude's output from selector — contains only IDs and indices, no text."""
    experiences: list[BulletSelection]   # 2-3 entries
    projects: list[BulletSelection]      # 1-2 entries
    leadership_ids: list[str]            # exactly 1
    skills: dict[str, list[str]]         # category key → list of skill names
                                         # keys: languages, frameworks, devops, certifications


@dataclass
class ExperienceEntry:
    title: str
    company: str
    dates: str
    location: str
    bullets: list[str]   # plain text, no LaTeX escaping


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
    """Fully resolved resume content ready for rendering."""
    experience: list[ExperienceEntry]
    projects: list[ProjectEntry]
    leadership: list[LeadershipEntry]
    skills: list[SkillEntry]


class CompilationError(Exception):
    """Raised when pdflatex fails to compile the resume."""
    def __init__(self, message: str, latex_stdout: str) -> None:
        super().__init__(message)
        self.latex_stdout = latex_stdout
