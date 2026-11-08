"""
Public interface of the portfolios module, and the only place that talks to other apps.

Dependencies point one way:  portfolios -> profiles / education / skills.
None of those apps import portfolios.
"""
from __future__ import annotations

from apps.education.services import get_education_display, get_entries
from apps.profiles.services import build_display, get_default_profile, get_profiles

from .models import Portfolio

LAYOUT_TEMPLATES = {
    "classic": "portfolios/layouts/classic.html",
    "midnight": "portfolios/layouts/midnight.html",
    "ocean": "portfolios/layouts/ocean.html",
    "mono": "portfolios/layouts/mono.html",
}


def get_portfolios(user):
    """All portfolios owned by this user. Empty for anonymous users."""
    if user is None or not getattr(user, "is_authenticated", False):
        return Portfolio.objects.none()
    return Portfolio.objects.filter(owner=user)


def get_portfolio(user, pk):
    return get_portfolios(user).select_related("profile").filter(pk=pk).first()


def layout_for(portfolio: Portfolio) -> str:
    return LAYOUT_TEMPLATES.get(portfolio.template_key, LAYOUT_TEMPLATES[Portfolio.DEFAULT_TEMPLATE])


def resolve_profile(portfolio: Portfolio):
    """The profile this portfolio shows: the chosen one, else the owner's default (or None)."""
    chosen = portfolio.profile
    # Defensive: a profile that isn't the owner's is never shown.
    if chosen is not None and chosen.owner_id == portfolio.owner_id:
        return chosen
    return get_default_profile(portfolio.owner)


def build_portfolio_context(portfolio: Portfolio) -> dict:
    """Everything a layout needs. Every value is safe to render when data is missing."""
    from .content_selection.selectors import get_selected_ids  # local: avoids an import cycle

    owner = portfolio.owner
    profile = resolve_profile(portfolio)
    education = get_education_display(owner)
    skills = list(profile.skills.all()) if profile else []
    experiences = list(profile.experiences.all()) if profile else []

    # FOLDO-06: None = never customised = show everything.
    selected = get_selected_ids(portfolio)
    if selected is not None:
        skills = [s for s in skills if s.pk in selected["skills"]]
        experiences = [e for e in experiences if e.pk in selected["experience"]]
        if education is not None:
            levels = set(
                get_entries(owner).filter(pk__in=selected["education"]).values_list("level", flat=True)
            )
            kept = [entry for entry in education.entries if entry.level in levels]
            education = type(education)(entries=kept) if kept else None

    return {
        "portfolio": portfolio,
        "display": build_display(owner, profile),
        "education": education,
        "skills": skills,
        "experiences": experiences,
    }


def profile_choices(user):
    """The profiles this user may pick from."""
    return get_profiles(user)
