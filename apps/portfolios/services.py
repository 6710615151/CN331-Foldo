"""
Public interface of the portfolios module, and the only place that talks to other apps.

Dependencies point one way:  portfolios -> profiles / education / skills.
None of those apps import portfolios.
"""
from __future__ import annotations

from apps.education.services import get_education_display
from apps.profiles.services import build_display, get_default_profile, get_profiles
from apps.skills.services import get_skills_display

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
    owner = portfolio.owner
    profile = resolve_profile(portfolio)
    return {
        "portfolio": portfolio,
        "display": build_display(owner, profile),
        "education": get_education_display(owner),  # None until that module exists
        "skills": get_skills_display(owner),        # None until that module exists
    }


def profile_choices(user):
    """The profiles this user may pick from."""
    return get_profiles(user)
