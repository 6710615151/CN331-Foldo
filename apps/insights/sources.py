"""Where insights read their data from (shared by Portfolio DNA and Quality Check).

Source items come from the profile sections (same contract as rendering,
docs/CONVENTIONS.md §8). Portfolio versions come from FOLDO-05/06 through:

    profile.portfolio_versions            (PortfolioVersion, FK profile)
        version.version_name, version.pk
        version.selections                (PortfolioContentSelection, FK version)
            selection.content_type        "skills" | "experience" | "education" | "projects"
            selection.content_id          id of the source row (no FK, per the ER diagram)

Until those models exist the version list is empty, so every item shows as
unused — no mock data is involved.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.urls import NoReverseMatch, reverse

from apps.rendering.selectors import SECTION_SPECS, default_providers

# Edit page per section; a section whose page doesn't exist yet links to the profile.
EDIT_URL_NAMES = {
    "skills": "profiles:skill_edit",
    "experience": "profiles:experience_edit",
    "education": "profiles:education_edit",
    "projects": "profiles:project_edit",
}

# Where to add a first item to an empty section (falls back to the profile page).
ADD_URL_NAMES = {
    "skills": "profiles:skills_experience",
    "experience": "profiles:skills_experience",
    "education": "profiles:education_list",
    "projects": "profiles:project_list",
}

# Version pages from FOLDO-05; fall back to the dashboard until they exist.
VERSION_URL_NAME = "portfolios:detail"


@dataclass(frozen=True)
class SourceItem:
    section: str
    id: int
    title: str
    edit_url: str


@dataclass(frozen=True)
class VersionRef:
    id: int
    name: str
    url: str
    selected: dict[str, frozenset[int]] = field(default_factory=dict)
    template: str = ""

    def uses(self, section: str, item_id: int) -> bool:
        return item_id in self.selected.get(section, frozenset())


def section_add_url(profile, section: str) -> str:
    return _url(ADD_URL_NAMES[section], profile.pk, reverse("profiles:view", args=[profile.pk]))


def item_edit_url(profile, section: str, item_id: int) -> str:
    return _url(EDIT_URL_NAMES[section], item_id, reverse("profiles:view", args=[profile.pk]))


def _url(name: str, pk: int, fallback: str) -> str:
    try:
        return reverse(name, args=[pk])
    except NoReverseMatch:
        return fallback


def source_sections(profile, providers=None) -> list[tuple[str, str, list[SourceItem]]]:
    """(key, title, items) for every section, including empty ones."""
    providers = providers or default_providers()
    fallback = reverse("profiles:view", args=[profile.pk])
    sections = []
    for key, title, _, adapter in SECTION_SPECS:
        items = []
        for row in providers.get(key, lambda _p: ())(profile):
            item = adapter(row)
            items.append(
                SourceItem(
                    section=key,
                    id=row.pk,
                    title=item.title or f"(untitled #{row.pk})",
                    edit_url=_url(EDIT_URL_NAMES[key], row.pk, fallback),
                )
            )
        sections.append((key, title, items))
    return sections


def portfolio_versions(profile) -> list[VersionRef]:
    manager = getattr(profile, "portfolio_versions", None)
    if manager is None:
        return []
    fallback = reverse("core:dashboard")
    versions = []
    for version in manager.all():
        selected: dict[str, set[int]] = {}
        selections = getattr(version, "selections", None)
        for selection in selections.all() if selections is not None else ():
            selected.setdefault(selection.content_type, set()).add(selection.content_id)
        versions.append(
            VersionRef(
                id=version.pk,
                name=getattr(version, "version_name", "") or f"Version {version.pk}",
                url=_url(VERSION_URL_NAME, version.pk, fallback),
                selected={key: frozenset(ids) for key, ids in selected.items()},
                template=getattr(version, "template", "") or "",
            )
        )
    return versions
