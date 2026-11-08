from django.urls import path

from .views import ContentSelectionView

# Included from apps/portfolios/urls.py, so the names live in the ``portfolios`` namespace.
urlpatterns = [
    path("<int:pk>/content/", ContentSelectionView.as_view(), name="content"),
]
