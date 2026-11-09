from django.urls import path

from .views import ExportView

# Included from apps/portfolios/urls.py, so the name lives in the ``portfolios`` namespace.
urlpatterns = [
    path("<int:pk>/export/", ExportView.as_view(), name="export"),
]
