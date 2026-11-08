"""Rendering a portfolio to HTML (FOLDO-07).

``render_portfolio_html`` is the single entry point for every output: the
template preview here, the version preview (FOLDO-08), the public page
(FOLDO-09) and the PDF export (FOLDO-11) all pass a theme and a
``PortfolioContent`` and get a complete HTML document back.
"""

from django.template.loader import render_to_string

from .selectors import PortfolioContent
from .themes import PortfolioTheme


def render_portfolio_html(
    theme: PortfolioTheme,
    content: PortfolioContent,
    *,
    request=None,
    toolbar: dict | None = None,
) -> str:
    """Return the full HTML page. ``toolbar`` (preview only) adds a back/switch bar."""
    return render_to_string(
        theme.template_name,
        {"theme": theme, "content": content, "profile": content.profile, "toolbar": toolbar},
        request=request,
    )
