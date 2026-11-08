"""
Bridge between portfolios and the rendering app's paper themes (classic / modern / creative).

portfolios decides WHICH profile and theme to show; apps.rendering knows HOW to draw
the theme. This module feeds the second from the first. Dependencies point one way:
portfolios -> rendering -> profiles. rendering never imports portfolios.

Two gaps in apps.rendering.selectors are patched here, without touching that app:

1. Education: rendering reads `profile.educations`, but education is stored per user
   (apps.education), so that section is rebuilt from `get_education_display(owner)`.
2. Project Story: rendering reads `project.story`, but the five story fields live on
   the Project itself, so each project is exposed as its own story record.
   (Remove `_projects_with_story` if rendering.selectors.project_item is changed to
   `record = getattr(project, "story", None) or project`.)
"""
from __future__ import annotations

from dataclasses import replace

from django.template.loader import render_to_string

from apps.education.services import get_education_display
from apps.profiles.projects.selectors import get_projects
from apps.profiles.services import build_display
from apps.rendering.selectors import (
    SECTION_SPECS,
    PortfolioContent,
    Section,
    SectionItem,
    build_portfolio_content,
    default_providers,
)
from apps.rendering.services import render_portfolio_html
from apps.rendering.themes import get_theme

from .models import RENDERING_PREFIX
from .services import resolve_profile


def theme_for(portfolio):
    """The rendering-app theme chosen for this portfolio, or None for the built-in layouts."""
    key = portfolio.template_key
    if not key.startswith(RENDERING_PREFIX):
        return None
    return get_theme(key[len(RENDERING_PREFIX):])


def _projects_with_story(profile):
    projects = list(get_projects(profile))
    for project in projects:
        project.story = project  # the story fields live on the project itself
    return projects


def build_content(portfolio) -> PortfolioContent:
    """Everything a rendering theme needs for this portfolio's chosen profile."""
    owner = portfolio.owner
    profile = resolve_profile(portfolio)
    if profile is None:
        return PortfolioContent(profile=build_display(owner), sections=())

    providers = {**default_providers(), "projects": _projects_with_story}
    content = build_portfolio_content(profile, providers=providers)

    sections = [section for section in content.sections if section.key != "education"]
    education = get_education_display(owner)
    if education:
        items = tuple(
            SectionItem(
                id=index,
                title=entry.title,
                subtitle=entry.subtitle,
                period=entry.years,
                description=f"Grade: {entry.grade}" if entry.grade else "",
            )
            for index, entry in enumerate(education.entries, start=1)
        )
        sections.append(Section(key="education", title="Education", items=items))

    order = [spec[0] for spec in SECTION_SPECS]
    sections.sort(key=lambda s: order.index(s.key) if s.key in order else len(order))
    return replace(content, sections=tuple(sections))


def render_html(portfolio, theme, *, request, preview: bool) -> str:
    """A complete HTML page. In preview mode the owner gets a status bar and noindex."""
    html = render_portfolio_html(theme, build_content(portfolio), request=request)
    if preview:
        bar = render_to_string("portfolios/_preview_bar.html", {"portfolio": portfolio}, request=request)
        html = html.replace("<main", bar + "<main", 1)
        html = html.replace("</head>", '<meta name="robots" content="noindex"></head>', 1)
    return html
