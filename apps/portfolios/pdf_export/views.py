"""
Export page for a portfolio version (FOLDO-11, Dev 2): page size, progress, success,
failure and retry around the PDF that ``portfolios:pdf`` generates.

Read only: exporting never publishes or changes anything.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from apps.portfolios.pdf import DEFAULT_PAGE_SIZE, PAGE_SIZES
from apps.portfolios.services import get_portfolio

TEMPLATE = "portfolios/pdf_export/export.html"

# How long the page waits for the server before telling the user it took too long (seconds).
CLIENT_TIMEOUT_SECONDS = 150


@method_decorator(never_cache, name="dispatch")
class ExportView(LoginRequiredMixin, View):
    """Owner only; another user's id is a 404 exactly like a missing one."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.portfolio = get_portfolio(request.user, kwargs["pk"])
        if self.portfolio is None:
            raise Http404("Portfolio not found")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        return render(
            request,
            TEMPLATE,
            {
                "portfolio": self.portfolio,
                "page_sizes": PAGE_SIZES,
                "default_page_size": DEFAULT_PAGE_SIZE,
                "timeout_seconds": CLIENT_TIMEOUT_SECONDS,
            },
        )
