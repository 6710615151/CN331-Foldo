from django.urls import path

from .views import PortfolioDnaView, QualityCheckView

app_name = "insights"

urlpatterns = [
    path("profiles/<int:pk>/dna/", PortfolioDnaView.as_view(), name="dna"),
    path("profiles/<int:pk>/quality/", QualityCheckView.as_view(), name="quality"),
]
