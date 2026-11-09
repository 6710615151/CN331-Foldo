from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.templatetags.static import static as static_url
from django.urls import include, path
from django.views.generic import RedirectView


class FaviconView(RedirectView):
    """Resolved per request (not at import) so hashed static storages also work."""

    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        return static_url("images/favicon.ico")


# ---------------------------------------------------------------------------
# FOLDO URL configuration
# ---------------------------------------------------------------------------
# Top-level routing only. Each app owns its own urls.py so features stay
# self-contained and easier for five developers to work on in parallel.
urlpatterns = [
    # Browsers ask for /favicon.ico even on pages without a <link rel="icon">
    # (the PDF source, JSON responses); send them to the static file.
    path("favicon.ico", FaviconView.as_view()),
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("profiles/", include("apps.profiles.urls")),
    path("portfolios/", include("apps.portfolios.urls")),
    path("templates/", include("apps.rendering.urls")),
    path("insights/", include("apps.insights.urls")),
]

# Development-only: endpoint used by django-browser-reload to trigger a refresh
# when files change (see requirements-dev.txt). Never routed in production, and
# skipped when the optional package is not installed (e.g. in CI).
if settings.DEBUG and settings.DEV_TOOLS_INSTALLED:
    urlpatterns += [path("__reload__/", include("django_browser_reload.urls"))]
    
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom error handlers render friendly, non-technical pages in production
# (DEBUG must be False for these to be used).
handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"
