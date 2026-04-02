"""LaTeX escaping, Jinja2 template rendering, and pdflatex compilation."""
from __future__ import annotations

import dataclasses
import re
import subprocess
import tempfile
from pathlib import Path

from jinja2 import Environment

from src.resume.types import (
    CompilationError,
    ExperienceEntry,
    LeadershipEntry,
    ProjectEntry,
    ResumeContent,
    SkillEntry,
)


def escape_latex(text: str) -> str:
    """Escape special LaTeX characters without double-escaping."""
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for char, replacement in replacements.items():
        # Protect already-escaped sequences, apply escaping, then restore
        text = text.replace(replacement, f"__ESCAPED_{char}__")
        text = text.replace(char, replacement)
        text = text.replace(f"__ESCAPED_{char}__", replacement)
    return text


def _escape_content(content: ResumeContent) -> ResumeContent:
    """Return a new ResumeContent with all text fields LaTeX-escaped.

    Does NOT escape meta or education (those come from master and the
    template already handles them).
    """
    experience = [
        dataclasses.replace(e, bullets=[escape_latex(b) for b in e.bullets])
        for e in content.experience
    ]
    projects = [
        dataclasses.replace(p, bullets=[escape_latex(b) for b in p.bullets])
        for p in content.projects
    ]
    leadership = [
        dataclasses.replace(
            entry,
            title=escape_latex(entry.title),
            description=escape_latex(entry.description),
        )
        for entry in content.leadership
    ]
    skills = [
        dataclasses.replace(
            s,
            category=escape_latex(s.category),
            value=escape_latex(s.value),
        )
        for s in content.skills
    ]
    return ResumeContent(
        experience=experience,
        projects=projects,
        leadership=leadership,
        skills=skills,
    )


def compile_pdf(
    content: ResumeContent,
    master: dict,
    template_path: Path = Path("templates/resume.tex"),
    debug_tex_path: Path | None = None,
) -> bytes:
    """Render a resume PDF from content and the master data.

    Applies escape_latex() to all text fields in content.
    Renders templates/resume.tex with Jinja2.
    Runs pdflatex in a temp directory.
    Returns raw PDF bytes on success.
    Raises CompilationError on failure.
    If debug_tex_path is set, saves the .tex there on failure for debugging.
    """
    escaped_content = _escape_content(content)

    # Jinja2 environment with LaTeX-friendly delimiters
    jinja_env = Environment(
        block_start_string="<%",
        block_end_string="%>",
        variable_start_string=r"\VAR{",
        variable_end_string="}",
        comment_start_string="<#",
        comment_end_string="#>",
        autoescape=False,
    )

    # Load and convert template block syntax from %% ... to <% ... %>
    template_src = template_path.read_text()
    template_src = re.sub(
        r"^%% (.+)$", r"<% \1 %>", template_src, flags=re.MULTILINE
    )
    template = jinja_env.from_string(template_src)

    rendered = template.render(
        meta=master["meta"],
        education=master["education"],
        experience=[dataclasses.asdict(e) for e in escaped_content.experience],
        projects=[dataclasses.asdict(p) for p in escaped_content.projects],
        leadership=[dataclasses.asdict(entry) for entry in escaped_content.leadership],
        skills=[dataclasses.asdict(s) for s in escaped_content.skills],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / "resume.tex"
        tex_path.write_text(rendered)

        result = subprocess.run(
            ["/Library/TeX/texbin/pdflatex", "-interaction=nonstopmode", "resume.tex"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=30,
        )

        pdf_path = Path(tmpdir) / "resume.pdf"
        if not pdf_path.exists():
            if debug_tex_path:
                debug_tex_path.write_text(rendered)
            errors = [
                line
                for line in result.stdout.split("\n")
                if line.startswith("!") or "Error" in line
            ]
            raise CompilationError(
                f"pdflatex failed: {'; '.join(errors[:5])}",
                latex_stdout=result.stdout,
            )

        return pdf_path.read_bytes()
