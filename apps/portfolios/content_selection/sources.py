"""
What can be selected for a portfolio, per section (FOLDO-06).

Section keys match ``apps.rendering.selectors.SECTION_SPECS`` so the same
``{section: {ids}}`` mapping can be handed to ``build_portfolio_content(selected=...)``.
A source that does not exist yet (e.g. projects before the FOLDO-04 projects PR merges)
simply yields no items.
"""
from __future__ import annotations

from dataclasses import dataclass

from apps.portfolios.services import resolve_profile

SECTIONS = (
    ("experience", "Experience"),
    ("education", "Education"),
    ("projects", "Projects"),
    ("skills", "Skills"),
)
SECTION_KEYS = tuple(key for key, _ in SECTIONS)


@dataclass(frozen=True)
class Choice:
    id: int
    label: str
    detail: str = ""


# UI labels for skill levels (the portfolio document keeps the English ones).
SKILL_LEVELS_TH = {"beginner": "เริ่มต้น", "intermediate": "ปานกลาง", "advanced": "ชำนาญ", "expert": "เชี่ยวชาญ"}


def _skills(profile, owner):
    if not profile:
        return []
    return [Choice(s.pk, s.name, SKILL_LEVELS_TH.get(s.proficiency, s.get_proficiency_display()))
            for s in profile.skills.all()]


def _experience(profile, owner):
    if not profile:
        return []
    return [Choice(e.pk, e.job_title, e.company) for e in profile.experiences.all()]


def _education(profile, owner):
    if not profile:
        return []
    return [Choice(e.pk, e.institution, e.degree or e.field_of_study) for e in profile.educations.all()]


def _projects(profile, owner):
    manager = getattr(profile, "projects", None) if profile else None
    if manager is None:
        return []
    return [
        Choice(p.pk, getattr(p, "project_name", "") or getattr(p, "name", "") or getattr(p, "title", ""))
        for p in manager.all()
    ]


_LOADERS = {"experience": _experience, "education": _education, "projects": _projects, "skills": _skills}


def available_items(portfolio) -> dict[str, list[Choice]]:
    """Everything the portfolio's owner could include, per section (their own data only)."""
    owner = portfolio.owner
    profile = resolve_profile(portfolio)
    return {key: _LOADERS[key](profile, owner) for key in SECTION_KEYS}
