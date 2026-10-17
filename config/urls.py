from django.conf import settings
from django.contrib import admin
from django.urls import include, path

# ---------------------------------------------------------------------------
# FOLDO URL configuration
# ---------------------------------------------------------------------------
# Top-level routing only. Each app owns its own urls.py so features stay
# self-contained and easier for five developers to work on in parallel.
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
]

# Development-only: endpoint used by django-browser-reload to trigger a refresh
# when files change (see requirements-dev.txt). Never routed in production.
if settings.DEBUG:
    urlpatterns += [path("__reload__/", include("django_browser_reload.urls"))]

# Custom error handlers render friendly, non-technical pages in production
# (DEBUG must be False for these to be used).
handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"
