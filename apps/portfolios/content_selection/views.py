"""Presentation layer for per-version content selection (FOLDO-06)."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect, render
from django.views import View

from apps.portfolios.services import get_portfolio

from . import selectors, services
from .forms import parse_selection
from .sources import SECTIONS, available_items

TEMPLATE = "portfolios/content_selection/select.html"


class ContentSelectionView(LoginRequiredMixin, View):
    """Owner-only. The portfolio is looked up by id AND owner, so other ids are a 404."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.portfolio = get_portfolio(request.user, kwargs["pk"])
        if self.portfolio is None:
            raise Http404("Portfolio not found")
        return super().dispatch(request, *args, **kwargs)

    def _render(self, request):
        available = available_items(self.portfolio)
        ticked = selectors.selection_state(self.portfolio)
        sections = [
            {
                "key": key,
                "title": title,
                "items": [
                    {"id": c.id, "label": c.label, "detail": c.detail, "checked": c.id in ticked[key]}
                    for c in available[key]
                ],
            }
            for key, title in SECTIONS
        ]
        return render(request, TEMPLATE, {
            "portfolio": self.portfolio,
            "sections": sections,
            "customised": selectors.is_customised(self.portfolio),
            "has_content": any(section["items"] for section in sections),
        })

    def get(self, request, pk):
        return self._render(request)

    def post(self, request, pk):
        if "reset" in request.POST:
            services.reset_selection(self.portfolio)
            messages.success(request, "This version now shows all of your profile content.")
        else:
            ignored = services.save_selection(self.portfolio, parse_selection(request.POST))
            messages.success(request, f"Content for “{self.portfolio.title}” saved.")
            if ignored:
                messages.warning(request, f"{ignored} item(s) were no longer available and were skipped.")
        return redirect("portfolios:content", pk=self.portfolio.pk)
