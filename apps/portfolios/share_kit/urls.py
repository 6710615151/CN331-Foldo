from django.urls import path

from .views import QrDownloadView, ShareKitView

# Included from apps/portfolios/urls.py, so the names live in the ``portfolios`` namespace.
urlpatterns = [
    path("<int:pk>/share/", ShareKitView.as_view(), name="share"),
    path("<int:pk>/share/qr.png", QrDownloadView.as_view(fmt="png"), name="share_qr_png"),
    path("<int:pk>/share/qr.svg", QrDownloadView.as_view(fmt="svg"), name="share_qr_svg"),
]
