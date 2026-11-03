"""Views for the ``core`` app: the shared FOLDO shell."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View
from django.views.generic import TemplateView

from .selectors import (
    get_health_report,
    get_mock_dashboard_summary,
    get_mock_onboarding_steps,
)


class LandingView(TemplateView):
    """Public landing page: a single hero screen with one call to action."""

    template_name = "core/landing.html"


class OnboardingView(LoginRequiredMixin, TemplateView):
    """First-time entry flow: a three-step walkthrough before the dashboard.

    Signed-in users only. The steps are mock data until FOLDO-03 defines what
    an empty Main Profile looks like.
    """

    template_name = "core/onboarding.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["steps"] = get_mock_onboarding_steps()
        return context


class DashboardView(LoginRequiredMixin, TemplateView):
    """Signed-in app shell: navigation, layout and an empty-state summary.

    Signed-in users only. Swap the mock summary for ``apps.profiles`` /
    ``apps.portfolios`` selectors as those apps arrive.
    """

    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["summary"] = get_mock_dashboard_summary()
        return context


class HealthCheckView(View):
    """Minimal JSON health check for uptime monitoring.

    Returns HTTP 200 when every dependency is reachable and HTTP 503 when one
    is not. The payload exposes a version string and boolean check results
    only — never configuration values or connection details.
    """

    def get(self, request, *args, **kwargs):
        report = get_health_report()
        status_code = 200 if report.is_healthy else 503
        return JsonResponse(report.as_dict(), status=status_code)


def page_not_found(request, exception):
    """Render the custom 404 page (used when DEBUG is False)."""
    return render(request, "404.html", status=404)


def server_error(request):
    """Render the custom 500 page (used when DEBUG is False)."""
    return render(request, "500.html", status=500)
