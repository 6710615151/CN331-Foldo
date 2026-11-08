from django.urls import include, path

from . import views

app_name = "portfolios"

urlpatterns = [
    path("", views.portfolio_list, name="list"),
    path("new/", views.portfolio_create, name="create"),
    path("<int:pk>/preview/", views.portfolio_preview, name="preview"),
    path("<int:pk>/preview/device/", views.portfolio_device_preview, name="device_preview"),
    path("<int:pk>/preview/frame/", views.portfolio_preview_frame, name="preview_frame"),
    path("<int:pk>/edit/", views.portfolio_edit, name="update"),
    path("<int:pk>/delete/", views.portfolio_delete, name="delete"),
    path("p/<slug:slug>/", views.portfolio_public, name="public"),
    # FOLDO-06: per-version content selection (Dev 2)
    path("", include("apps.portfolios.content_selection.urls")),
    # FOLDO-16: Quality Check (Dev 3)
    path("", include("apps.portfolios.quality.urls")),
    # FOLDO-17: share kit, copy link and QR code (Dev 4 task, done by Dev 2)
    path("", include("apps.portfolios.share_kit.urls")),
]
