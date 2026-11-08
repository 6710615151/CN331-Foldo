"""
Public interface of the education module.

portfolios calls `get_education_display(user)` and renders the result with
templates/education/_portfolio_section.html. Every lookup is scoped to the given user.
Other apps should import from here, not from models.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import EducationEntry

# Highest qualification first, which is how most CVs read.
LEVEL_ORDER = [
    EducationEntry.Level.PHD,
    EducationEntry.Level.GRADUATE,
    EducationEntry.Level.UNDERGRADUATE,
    EducationEntry.Level.HIGH_SCHOOL,
]


@dataclass(frozen=True)
class EntryDisplay:
    level: str
    level_label: str
    title: str          # the school if known, otherwise the level
    subtitle: str = ""  # "Undergraduate degree, Computer Engineering"
    grade: str = ""
    years: str = ""


@dataclass(frozen=True)
class EducationDisplay:
    entries: list[EntryDisplay] = field(default_factory=list)


def get_entries(user):
    """All of this user's education rows. Empty for anonymous users."""
    if user is None or not getattr(user, "is_authenticated", False):
        return EducationEntry.objects.none()
    return EducationEntry.objects.filter(owner=user)


def _years_text(start, end) -> str:
    if start and end:
        return f"{start} – {end}" if start != end else str(start)
    if end:
        return str(end)
    if start:
        return f"{start} – present"
    return ""


def get_education_display(user):
    """Render-safe education data for `user`, or None when nothing has been filled in."""
    by_level = {entry.level: entry for entry in get_entries(user)}

    items = []
    for level in LEVEL_ORDER:
        entry = by_level.get(level)
        if entry is None or entry.is_blank:
            continue
        label = EducationEntry.Level(level).label
        if entry.institution:
            title = entry.institution
            subtitle = ", ".join(part for part in (label, entry.subject) if part)
        else:
            title = label
            subtitle = entry.subject
        items.append(
            EntryDisplay(
                level=level,
                level_label=label,
                title=title,
                subtitle=subtitle,
                grade=entry.grade,
                years=_years_text(entry.start_year, entry.end_year),
            )
        )

    return EducationDisplay(entries=items) if items else None
