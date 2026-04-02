"""Resume generation pipeline: select → build → optimize → compile."""
from __future__ import annotations

from src.resume.selector import select
from src.resume.builder import build
from src.resume.ats import optimize
from src.resume.compiler import compile_pdf


def generate_resume(job: dict, master: dict, api_key: str) -> bytes:
    """Full pipeline: job + master YAML → PDF bytes."""
    manifest = select(job, master, api_key)
    content = build(manifest, master)
    optimized = optimize(content, job, api_key)
    return compile_pdf(optimized, master)
