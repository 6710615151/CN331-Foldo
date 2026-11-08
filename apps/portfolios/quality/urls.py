from django.urls import path

from .views import QualityCheckView

urlpatterns = [
    path("<int:pk>/quality/", QualityCheckView.as_view(), name="quality"),
]
