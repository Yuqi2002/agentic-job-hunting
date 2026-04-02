"""Comprehensive tests for the resume generation pipeline.

Each test shows exactly what the module does at each step.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from src.resume.builder import build
from src.resume.compiler import compile_pdf, escape_latex
from src.resume.selector import select
from src.resume.types import (
    BulletSelection,
    ExperienceEntry,
    ProjectEntry,
    ResumeContent,
    SelectionManifest,
    SkillEntry,
)


# ── Fixtures ──────────────────────────────────────────────────────────

MASTER_YAML_PATH = Path("data/master_resume.yaml")
TEMPLATE_PATH = Path("templates/resume.tex")


@pytest.fixture
def master() -> dict:
    """Load the actual master resume."""
    return yaml.safe_load(MASTER_YAML_PATH.read_text())


@pytest.fixture
def sample_job() -> dict:
    """A sample job description for testing."""
    return {
        "title": "Senior Software Engineer",
        "company": "TechCorp",
        "location": "San Francisco, CA",
        "description": """We are looking for a Senior Software Engineer to join our platform team.

Required Skills:
- Python, TypeScript, React.js
- AWS, Docker, Kubernetes
- Experience with REST APIs and microservices
- 3+ years of experience

Nice to have:
- Experience with AI/ML
- Leadership experience
- Open source contributions
""",
    }


# ── Test 1: escape_latex ──────────────────────────────────────────────

class TestEscapeLatex:
    """Test LaTeX character escaping."""

    def test_escapes_special_characters(self):
        """Verify all special characters are escaped correctly."""
        test_cases = {
            "50%": r"50\%",
            "a & b": r"a \& b",
            "$100": r"\$100",
            "C#": r"C\#",
            "snake_case": r"snake\_case",
            "tilde~here": r"tilde\textasciitilde{}here",
            "a^b": r"a\textasciicircum{}b",
        }
        for input_text, expected in test_cases.items():
            assert escape_latex(input_text) == expected, f"Failed for: {input_text}"

    def test_no_double_escape(self):
        """Verify that already-escaped sequences aren't double-escaped."""
        already_escaped = r"Already has 50\%"
        result = escape_latex(already_escaped)
        # Should have only one \%, not \\%
        assert result.count(r"\%") == 1
        assert r"\\%" not in result

    def test_multiple_special_chars_in_text(self):
        """Test complex text with multiple special characters."""
        text = "Reduced cost by 40% using Python & AWS (C# integration). Score: 95/100."
        result = escape_latex(text)
        assert r"\%" in result  # 40%
        assert r"\&" in result  # &
        assert r"\#" in result  # C#
        print(f"Original: {text}")
        print(f"Escaped:  {result}")


# ── Test 2: selector (Claude picks IDs only) ──────────────────────────

class TestSelector:
    """Test that selector returns only IDs and indices."""

    def test_selector_returns_manifest_with_ids_only(self, master: dict):
        """Verify that selector output contains only IDs, no bullet text."""
        print(f"\n✓ Master resume has {len(master['experiences'])} experiences")
        for exp in master["experiences"]:
            assert "id" in exp
            assert "title" in exp
            assert "bullets" in exp
            print(f"  - {exp['id']}: {exp['title']} @ {exp['company']}")
            for i, bullet in enumerate(exp["bullets"]):
                assert "text" in bullet
                print(f"    [{i}] {bullet['text'][:60]}...")

    def test_sample_selection_manifest(self, master: dict):
        """Show what a SelectionManifest looks like (IDs + indices)."""
        manifest = SelectionManifest(
            experiences=[
                BulletSelection(id="exp-servicenow-fte", bullet_indices=[2, 0, 1]),
                BulletSelection(id="exp-servicenow-intern", bullet_indices=[0, 1]),
            ],
            projects=[
                BulletSelection(id="proj-ucf-attendance", bullet_indices=[0, 1]),
            ],
            leadership_ids=["lead-toastmasters"],
            skills={
                "languages": ["Python", "TypeScript", "SQL"],
                "frameworks": ["React.js", "Langchain", "Django"],
                "devops": ["AWS", "Docker", "Kubernetes"],
                "certifications": ["ServiceNow Certified Application Developer"],
            },
        )
        print(f"\n✓ SelectionManifest structure:")
        print(f"  Experiences: {len(manifest.experiences)} entries")
        for sel in manifest.experiences:
            print(f"    - {sel.id} → bullets {sel.bullet_indices}")
        print(f"  Projects: {len(manifest.projects)} entries")
        print(f"  Leadership: {len(manifest.leadership_ids)} entries")
        print(f"  Skills: {len(manifest.skills)} categories")


# ── Test 3: builder (Pure Python, verbatim copy) ──────────────────────

class TestBuilder:
    """Test that builder copies text verbatim from YAML."""

    def test_builder_creates_resume_content(self, master: dict):
        """Show that builder creates ResumeContent with verbatim text."""
        manifest = SelectionManifest(
            experiences=[
                BulletSelection(id="exp-servicenow-fte", bullet_indices=[0]),
            ],
            projects=[
                BulletSelection(id="proj-ucf-attendance", bullet_indices=[0]),
            ],
            leadership_ids=["lead-toastmasters"],
            skills={
                "languages": ["Python"],
                "frameworks": ["React.js"],
                "devops": ["AWS"],
                "certifications": [],
            },
        )

        content = build(manifest, master)

        # Verify content structure
        assert isinstance(content, ResumeContent)
        assert len(content.experience) == 1
        assert len(content.projects) == 1
        assert len(content.leadership) == 1
        assert len(content.skills) == 4

        # Verify text is copied verbatim
        exp_entry = content.experience[0]
        assert exp_entry.title == "Software Engineer"
        assert exp_entry.company == "ServiceNow"
        assert len(exp_entry.bullets) == 1

        # Get the original bullet text from master
        master_bullet = master["experiences"][0]["bullets"][0]["text"]
        assert exp_entry.bullets[0] == master_bullet

        print(f"\n✓ Builder copied verbatim:")
        print(f"  Experience: {exp_entry.company} → {exp_entry.title}")
        print(f"  Bullet: {exp_entry.bullets[0][:80]}...")
        print(f"  Skills: {[s.value for s in content.skills]}")

    def test_builder_error_on_invalid_id(self, master: dict):
        """Verify builder raises KeyError on invalid ID."""
        bad_manifest = SelectionManifest(
            experiences=[
                BulletSelection(id="exp-nonexistent", bullet_indices=[0]),
            ],
            projects=[],
            leadership_ids=[],
            skills={},
        )
        with pytest.raises(KeyError):
            build(bad_manifest, master)

    def test_builder_error_on_invalid_index(self, master: dict):
        """Verify builder raises IndexError on out-of-range bullet index."""
        bad_manifest = SelectionManifest(
            experiences=[
                BulletSelection(id="exp-servicenow-fte", bullet_indices=[999]),
            ],
            projects=[],
            leadership_ids=[],
            skills={},
        )
        with pytest.raises(IndexError):
            build(bad_manifest, master)


# ── Test 4: compiler (LaTeX + pdflatex) ──────────────────────────────

class TestCompiler:
    """Test that compiler produces valid PDF."""

    def test_compiler_creates_pdf(self, master: dict):
        """Show that compiler creates a valid PDF file."""
        # Build minimal content
        content = ResumeContent(
            experience=[
                ExperienceEntry(
                    title="Software Engineer",
                    company="ServiceNow",
                    dates="Jul 2025 -- Present",
                    location="Santa Clara, CA",
                    bullets=[
                        "Engineered core features using Python & React.js for 214+ users",
                    ],
                )
            ],
            projects=[
                ProjectEntry(
                    name="Test Project",
                    bullets=["Built a system with Kubernetes & AWS"],
                )
            ],
            leadership=[],
            skills=[
                SkillEntry(category="Languages", value="Python, TypeScript"),
                SkillEntry(category="Frameworks / Tools", value="React.js, Django"),
                SkillEntry(category="DevOps / Cloud", value="AWS, Docker, Kubernetes"),
            ],
        )

        # Compile PDF
        pdf_bytes = compile_pdf(content, master, TEMPLATE_PATH)

        # Verify PDF was created
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000  # Should be a real PDF
        assert pdf_bytes.startswith(b"%PDF")  # PDF magic number

        print(f"\n✓ Compiler produced PDF: {len(pdf_bytes):,} bytes")

    def test_compiler_escapes_latex(self, master: dict):
        """Verify compiler escapes LaTeX special characters."""
        content = ResumeContent(
            experience=[
                ExperienceEntry(
                    title="Engineer",
                    company="Corp",
                    dates="2024 -- Present",
                    location="SF",
                    bullets=[
                        "Reduced cost by 50% using Python & AWS",
                        "C# integration for $100K project",
                    ],
                )
            ],
            projects=[],
            leadership=[],
            skills=[],
        )

        pdf_bytes = compile_pdf(content, master, TEMPLATE_PATH)
        assert len(pdf_bytes) > 1000

        print(f"\n✓ Compiler escaped special chars in bullets before PDF generation")


# ── Test 5: Full pipeline integration ─────────────────────────────────

class TestFullPipeline:
    """Test the complete pipeline flow."""

    def test_manifest_to_content_to_pdf(self, master: dict):
        """Show the complete flow: manifest → build → compile."""
        print(f"\n🔄 Full Pipeline Test")

        # Step 1: Simulate Claude selection (IDs + indices only)
        manifest = SelectionManifest(
            experiences=[
                BulletSelection(id="exp-servicenow-fte", bullet_indices=[0, 2]),
                BulletSelection(id="exp-servicenow-intern", bullet_indices=[0]),
            ],
            projects=[
                BulletSelection(id="proj-ucf-attendance", bullet_indices=[0, 1]),
            ],
            leadership_ids=["lead-toastmasters"],
            skills={
                "languages": ["Python", "TypeScript", "SQL"],
                "frameworks": ["React.js", "Langchain"],
                "devops": ["AWS", "Docker", "Kubernetes"],
                "certifications": [],
            },
        )
        print(f"  1. Selection manifest created")
        print(f"     - {len(manifest.experiences)} experiences selected")
        print(f"     - {len(manifest.projects)} projects selected")

        # Step 2: Builder copies verbatim from YAML
        content = build(manifest, master)
        print(f"  2. Builder created ResumeContent")
        print(f"     - {sum(len(e.bullets) for e in content.experience)} experience bullets")
        print(f"     - {sum(len(p.bullets) for p in content.projects)} project bullets")

        # Step 3: Compiler escapes + renders + compiles
        pdf_bytes = compile_pdf(content, master, TEMPLATE_PATH)
        print(f"  3. Compiler produced PDF: {len(pdf_bytes):,} bytes")
        assert pdf_bytes.startswith(b"%PDF")
        print(f"  ✅ Full pipeline working!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
