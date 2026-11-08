from django.urls import path

from .views import ThemeGalleryView, ThemePreviewView

app_name = "rendering"

urlpatterns = [
    path("", ThemeGalleryView.as_view(), name="gallery"),
    path("<slug:theme>/profiles/<int:pk>/", ThemePreviewView.as_view(), name="preview"),
]
