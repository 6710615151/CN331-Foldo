from django.urls import path

from .views import PortfolioDnaView

app_name = "insights"

urlpatterns = [
    path("profiles/<int:pk>/dna/", PortfolioDnaView.as_view(), name="dna"),
]
