"""
Public interface of the portfolios module, and the only place that talks to other apps.

Dependencies point one way:  portfolios -> rendering / profiles.
None of those apps import portfolios.

Rendering a version (FOLDO-07):

    portfolio --resolve_profile--> profile
              --selected_ids-----> {section: {ids}} | None     (FOLDO-06)
              --theme_for--------> PortfolioTheme              (template_key)
    build_version_content() -> PortfolioContent -> render_version_html() -> HTML

Every output (owner preview, device-preview frame, public page, later the PDF)
goes through ``render_version_html`` so they can never disagree.
"""
from __future__ import annotations

from django.urls import reverse

from apps.profiles.services import build_display, get_default_profile, get_profiles
from apps.rendering.selectors import PortfolioContent, build_portfolio_content
from apps.rendering.services import render_portfolio_html
from apps.rendering.themes import PortfolioTheme, resolve_theme

from .models import Portfolio

# Sentinel: "look the selection up" (as opposed to None = "show everything").
_LOOKUP = object()


def get_portfolios(user):
    """All portfolios owned by this user. Empty for anonymous users."""
    if user is None or not getattr(user, "is_authenticated", False):
        return Portfolio.objects.none()
    return Portfolio.objects.filter(owner=user)


def get_portfolio(user, pk):
    return get_portfolios(user).select_related("profile").filter(pk=pk).first()


def resolve_profile(portfolio: Portfolio):
    """The profile this portfolio shows: the chosen one, else the owner's default (or None)."""
    chosen = portfolio.profile
    # Defensive: a profile that isn't the owner's is never shown.
    if chosen is not None and chosen.owner_id == portfolio.owner_id:
        return chosen
    return get_default_profile(portfolio.owner)


def profile_choices(user):
    """The profiles this user may pick from."""
    return get_profiles(user)


# --- FOLDO-07: templates and rendering ---------------------------------------


def theme_for(portfolio: Portfolio) -> PortfolioTheme:
    """The template this version uses. A stored key that no longer exists renders as the default."""
    return resolve_theme(portfolio.template_key)


def selected_ids(portfolio: Portfolio):
    """``{section: {ids}}`` chosen for this version, or ``None`` = show everything.

    The selection itself is owned by FOLDO-06 (``content_selection``). Until that
    module is merged every version shows all of its profile's content.
    """
    try:
        from .content_selection.selectors import get_selected_ids  # local: avoids an import cycle
    except ModuleNotFoundError as error:
        if error.name != f"{__package__}.content_selection":
            raise
        return None
    return get_selected_ids(portfolio)


def build_version_content(portfolio: Portfolio, *, selected=_LOOKUP) -> PortfolioContent:
    """Everything a template needs for this version: its profile, filtered by its selection.

    Never raises on missing data: no profile gives an empty page with the owner's name.
    Source rows are only read, never changed.
    """
    profile = resolve_profile(portfolio)
    if profile is None:
        return PortfolioContent(profile=build_display(portfolio.owner), sections=())

    if selected is _LOOKUP:
        selected = selected_ids(portfolio)
    return build_portfolio_content(profile, selected=selected)


def _preview_toolbar(portfolio: Portfolio, theme: PortfolioTheme) -> dict:
    if portfolio.is_published:
        status = f"ตัวอย่าง · {theme.name} · เผยแพร่แล้ว"
    else:
        status = f"ตัวอย่าง · {theme.name} · ส่วนตัว เห็นได้เฉพาะคุณ"
    links = [
        ("แก้ไขเวอร์ชันและเทมเพลต", reverse("portfolios:update", args=[portfolio.pk])),
        ("Desktop / Mobile", reverse("portfolios:device_preview", args=[portfolio.pk])),
        ("ดาวน์โหลด PDF", reverse("portfolios:pdf", args=[portfolio.pk])),
        ("ตรวจคุณภาพ", reverse("portfolios:quality", args=[portfolio.pk])),
    ]
    if portfolio.is_published:
        links.append(("หน้าสาธารณะ", portfolio.public_path))
    return {
        "aria_label": "ตัวอย่างพอร์ตโฟลิโอ",
        "back_url": reverse("portfolios:list"),
        "back_label": "พอร์ตโฟลิโอทั้งหมด",
        "status": status,
        "links": links,
    }


def render_version_html(portfolio: Portfolio, *, request=None, preview: bool = False,
                        toolbar: bool | None = None) -> str:
    """The complete HTML page of one version in its own template.

    ``preview`` — owner is looking (not the public page): adds ``noindex``.
    ``toolbar`` — show the owner bar; defaults to ``preview``. The device-preview
    frame passes ``preview=True, toolbar=False``.
    """
    theme = theme_for(portfolio)
    show_toolbar = preview if toolbar is None else toolbar
    return render_portfolio_html(
        theme,
        build_version_content(portfolio),
        request=request,
        toolbar=_preview_toolbar(portfolio, theme) if show_toolbar else None,
        noindex=preview,
    )
