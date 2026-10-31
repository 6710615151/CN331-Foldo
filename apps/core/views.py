"""Views for the ``core`` app: the shared FOLDO shell."""

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


class OnboardingView(TemplateView):
    """First-time entry flow: a three-step walkthrough before the dashboard.

    Not gated behind login yet — authentication lands with the rest of
    FOLDO-02. Once it does, this view should be reached only right after
    registration (e.g. redirected to from the sign-up service) and the steps
    below should read the user's real state instead of mock data.
    """

    template_name = "core/onboarding.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["steps"] = get_mock_onboarding_steps()
        return context


class DashboardView(TemplateView):
    """Signed-in app shell: navigation, layout and an empty-state summary.

    Not gated behind login yet for the same reason as ``OnboardingView``.
    Add ``LoginRequiredMixin`` as the left-most base class once FOLDO-02's
    authentication lands, and swap the mock summary for
    ``apps.profiles``/``apps.portfolios`` selectors as those apps arrive.
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
