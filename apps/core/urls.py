from django.urls import path

from .views import DashboardView, HealthCheckView, LandingView, OnboardingView

app_name = "core"

urlpatterns = [
    path("", LandingView.as_view(), name="landing"),
    path("health/", HealthCheckView.as_view(), name="health"),
    path("onboarding/", OnboardingView.as_view(), name="onboarding"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
]
