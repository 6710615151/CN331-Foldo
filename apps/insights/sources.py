"""Where Portfolio DNA reads its data from (FOLDO-14).

Source items come from the profile sections (same contract as rendering,
docs/CONVENTIONS.md §8). Portfolio versions come from apps.portfolios through:
    apps.portfolios.services.get_portfolios(user)
    apps.portfolios.services.resolve_profile(portfolio)
    apps.portfolios.services.selected_ids(portfolio)

selected_ids() returns either a {section: {ids}} dict or None (= show everything).
VersionRef.selected preserves this 3-state contract:
    None  -> portfolio shows everything (every source item is used)
    {}    -> explicit empty selection (nothing from that section is used)
    {...} -> explicit selection of item IDs
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.urls import NoReverseMatch, reverse

from apps.rendering.selectors import SECTION_SPECS, default_providers

# Edit page per section (all take item PK).
EDIT_URL_NAMES = {
    "skills": "profiles:skill_edit",
    "experience": "profiles:experience_edit",
    "education": "profiles:education_edit",
    "projects": "profiles:project_edit",
}

# Where to add an item to a section (takes profile PK).
ADD_URL_NAMES = {
    "skills": "profiles:skills_experience",
    "experience": "profiles:skills_experience",
    "education": "profiles:education_add",
    "projects": "profiles:project_add",
}

# Version preview URL from FOLDO-05.
VERSION_URL_NAME = "portfolios:preview"


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
    # None = show everything (FOLDO-06 unconfigured); dict = explicit selection
    selected: dict[str, frozenset[int]] | None = field(default=None)
    template: str = ""

    def uses(self, section: str, item_id: int) -> bool:
        """Return True when this portfolio includes item_id from section.

        When selected is None, the portfolio shows all items from its profile.
        """
        if self.selected is None:
            return True
        return item_id in self.selected.get(section, frozenset())


def section_add_url(profile, section: str) -> str:
    name = ADD_URL_NAMES.get(section, "")
    fallback = reverse("profiles:view", args=[profile.pk])
    if not name:
        return fallback
    return _url(name, profile.pk, fallback)


def item_edit_url(profile, section: str, item_id: int) -> str:
    name = EDIT_URL_NAMES.get(section, "")
    fallback = reverse("profiles:view", args=[profile.pk])
    if not name:
        return fallback
    return _url(name, item_id, fallback)


def _url(name: str, pk: int, fallback: str) -> str:
    try:
        return reverse(name, args=[pk])
    except NoReverseMatch:
        return fallback


def source_sections(profile, providers=None) -> list[tuple[str, str, list[SourceItem]]]:
    """Return [(key, title, [SourceItem])] for every section on the profile."""
    providers = providers or default_providers()
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
                    edit_url=item_edit_url(profile, key, row.pk),
                )
            )
        sections.append((key, title, items))
    return sections


def portfolio_versions_for_profile(profile) -> list[VersionRef]:
    """All Portfolio rows that resolve to this profile.

    Batched on purpose: a fixed number of queries however many portfolios the
    owner has (no N+1). The profile comes with select_related, the chosen items
    with prefetch_related, and "is it customised?", the owner's default profile
    and the profile's available items are each read once.
    """
    from apps.portfolios.content_selection.sources import SECTION_KEYS
    from apps.portfolios.models import PortfolioContentSetup
    from apps.portfolios.services import get_portfolios
    from apps.profiles.services import get_default_profile

    fallback = reverse("portfolios:list")

    owner = profile.owner
    portfolios = list(get_portfolios(owner).select_related("profile").prefetch_related("content_selections"))
    if not portfolios:
        return []
    customised = set(
        PortfolioContentSetup.objects.filter(portfolio__in=portfolios).values_list("portfolio_id", flat=True)
    )
    default = get_default_profile(owner)
    available = None  # this profile's item ids per section, read once if any version needs them

    versions = []
    for portfolio in portfolios:
        chosen = portfolio.profile
        # Same rule as portfolios.services.resolve_profile: a profile that isn't the owner's is never shown.
        resolved = chosen if chosen is not None and chosen.owner_id == portfolio.owner_id else default
        if resolved is None or resolved.pk != profile.pk:
            continue
        if portfolio.pk in customised:
            if available is None:
                available = _available_ids(profile)
            picked = {key: set() for key in SECTION_KEYS}
            for row in portfolio.content_selections.all():
                if row.section in picked:
                    picked[row.section].add(row.item_id)
            # Same rule as content_selection.selectors.get_selected_ids: deleted items drop out.
            frozen_selected = {key: frozenset(picked[key] & available.get(key, set())) for key in SECTION_KEYS}
        else:
            frozen_selected = None
        versions.append(
            VersionRef(
                id=portfolio.pk,
                name=portfolio.title or f"Portfolio {portfolio.pk}",
                url=_url(VERSION_URL_NAME, portfolio.pk, fallback),
                selected=frozen_selected,
                template=getattr(portfolio, "template_key", ""),
            )
        )
    return versions


def _available_ids(profile) -> dict[str, set[int]]:
    """Ids of every item on the profile, per content section (one query per section)."""
    return {
        "education": set(profile.educations.values_list("pk", flat=True)),
        "skills": set(profile.skills.values_list("pk", flat=True)),
        "experience": set(profile.experiences.values_list("pk", flat=True)),
        "projects": set(profile.projects.values_list("pk", flat=True)),
    }


def portfolio_versions(profile) -> list[VersionRef]:
    """Alias for portfolio_versions_for_profile."""
    return portfolio_versions_for_profile(profile)
