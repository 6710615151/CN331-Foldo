from django.urls import path

from .views import HealthCheckView, LandingView

app_name = "core"

urlpatterns = [
    path("", LandingView.as_view(), name="landing"),
    path("health/", HealthCheckView.as_view(), name="health"),
]
