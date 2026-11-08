"""Quality Check page for one portfolio version (FOLDO-16)."""
from django.views.generic import DetailView

from apps.core.mixins import OwnerRequiredMixin

from ..models import Portfolio
from .checks import run_quality_check


class QualityCheckView(OwnerRequiredMixin, DetailView):
    """GET only: running or re-running the check can never change data.

    Owner only (another user's id is a 404, a visitor goes to login).
    """

    model = Portfolio
    owner_field = "owner"
    context_object_name = "portfolio"
    template_name = "portfolios/quality/report.html"
    http_method_names = ["get", "head"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["report"] = run_quality_check(self.object)
        return context
