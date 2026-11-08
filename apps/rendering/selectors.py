"""Read side of rendering: turn a Main Profile into ``PortfolioContent`` (FOLDO-07).

``PortfolioContent`` is the one shape every renderer takes (template preview,
public page, PDF), so templates never touch models directly and never crash on
missing data.

Sections are read through these reverse relations on ``MainProfile`` (the
agreed contract for FOLDO-04/15 — see docs/CONVENTIONS.md):

    profile.skills, profile.experiences, profile.educations, profile.projects
    project.evidence

The Project Story fields (problem, role, process, solution, outcome) are read
from ``project.story`` when such a record exists, otherwise from the project
itself (that is where FOLDO-15 stores them).

A relation whose model does not exist yet simply yields an empty section, and a
caller (or a test) can hand in its own ``providers``.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass

from apps.profiles.services import ProfileDisplay, build_display

STORY_FIELDS = (
    ("problem", "Problem"),
    ("role", "My role"),
    ("process", "Process"),
    ("solution", "Solution"),
    ("outcome", "Outcome"),
    ("impact", "Impact"),
)


@dataclass(frozen=True)
class SectionItem:
    id: int
    title: str
    subtitle: str = ""
    period: str = ""
    description: str = ""
    url: str = ""
    level: str = ""
    note: str = ""
    story: tuple[tuple[str, str], ...] = ()
    evidence: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    items: tuple[SectionItem, ...]


@dataclass(frozen=True)
class PortfolioContent:
    profile: ProfileDisplay
    sections: tuple[Section, ...]

    def section(self, key: str) -> Section | None:
        return next((s for s in self.sections if s.key == key), None)

    @property
    def is_empty(self) -> bool:
        return not self.sections and not self.profile.bio


# --- small helpers -----------------------------------------------------------


def _text(obj, name: str) -> str:
    value = getattr(obj, name, "") or ""
    return str(value).strip()


def _safe_url(value: str) -> str:
    """Only http(s) links are rendered as links; anything else is dropped."""
    value = (value or "").strip()
    return value if value.lower().startswith(("http://", "https://")) else ""


def _month(value) -> str:
    return value.strftime("%b %Y") if value else ""


def _period(obj) -> str:
    start = _month(getattr(obj, "start_date", None))
    if not start:
        return ""
    end = getattr(obj, "end_date", None)
    return f"{start} – {_month(end) if end else 'Present'}"


def _display(obj, name: str) -> str:
    """``get_<name>_display()`` for a choices field, else the raw value."""
    method = getattr(obj, f"get_{name}_display", None)
    return str(method()).strip() if callable(method) else _text(obj, name)


def _related(obj, name: str) -> Iterable:
    manager = getattr(obj, name, None)
    return manager.all() if manager is not None else ()


# --- adapters: one model row → SectionItem ------------------------------------


def skill_item(skill) -> SectionItem:
    return SectionItem(id=skill.pk, title=_text(skill, "name"), level=_display(skill, "proficiency"))


def experience_item(experience) -> SectionItem:
    return SectionItem(
        id=experience.pk,
        title=_text(experience, "job_title"),
        subtitle=_text(experience, "company"),
        period=_period(experience),
        description=_text(experience, "description"),
    )


def education_item(education) -> SectionItem:
    degree = _text(education, "degree")
    field = _text(education, "field_of_study")
    institution = _text(education, "institution")
    grade = _text(education, "grade")
    return SectionItem(
        id=education.pk,
        title=", ".join(part for part in (degree, field) if part) or institution,
        subtitle=institution if (degree or field) else "",
        period=_period(education),
        description=_text(education, "description"),
        note=f"Grade: {grade}" if grade else "",
    )


def project_item(project, *, include_story: bool = True) -> SectionItem:
    story = ()
    if include_story:
        record = getattr(project, "story", None) or project
        story = tuple(
            (label, _text(record, name)) for name, label in STORY_FIELDS if _text(record, name)
        )
    evidence = tuple(
        (_text(e, "caption") or _text(e, "evidence_type") or "Evidence", _safe_url(_text(e, "file_url")))
        for e in _related(project, "evidence")
        if _safe_url(_text(e, "file_url"))
    )
    return SectionItem(
        id=project.pk,
        title=_text(project, "project_name") or _text(project, "name") or _text(project, "title"),
        period=_period(project),
        description=_text(project, "description"),
        url=_safe_url(_text(project, "project_url")),
        story=story,
        evidence=evidence,
    )


# key, heading, related name, adapter — in display order.
SECTION_SPECS = (
    ("experience", "Experience", "experiences", experience_item),
    ("education", "Education", "educations", education_item),
    ("projects", "Projects", "projects", project_item),
    ("skills", "Skills", "skills", skill_item),
)

Provider = Callable[[object], Iterable]


def default_providers() -> dict[str, Provider]:
    return {key: (lambda profile, rel=rel: _related(profile, rel)) for key, _, rel, _ in SECTION_SPECS}


def build_portfolio_content(
    profile,
    *,
    selected: Mapping[str, Collection[int]] | None = None,
    include_story: bool = True,
    providers: Mapping[str, Provider] | None = None,
) -> PortfolioContent:
    """Everything a template needs to render ``profile``.

    ``selected`` — per section key, the ids to include (FOLDO-06). ``None`` means
    "everything"; a missing key means "nothing from that section".
    ``include_story`` — whether project stories are shown (FOLDO-15).
    Empty sections are left out, so templates never print an empty heading.
    """
    providers = providers or default_providers()
    sections = []
    for key, title, _, adapter in SECTION_SPECS:
        rows = providers.get(key, lambda _p: ())(profile)
        if selected is not None:
            wanted = set(selected.get(key, ()))
            rows = [row for row in rows if row.pk in wanted]
        if adapter is project_item:
            items = tuple(project_item(row, include_story=include_story) for row in rows)
        else:
            items = tuple(adapter(row) for row in rows)
        items = tuple(item for item in items if item.title)
        if items:
            sections.append(Section(key=key, title=title, items=items))

    return PortfolioContent(
        profile=build_display(profile.owner, profile),
        sections=tuple(sections),
    )
