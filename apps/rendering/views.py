"""Template gallery and template preview of the user's own profile (FOLDO-07)."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.urls import reverse
from django.views.generic import DetailView, TemplateView

from apps.core.mixins import OwnerRequiredMixin
from apps.profiles.models import MainProfile
from apps.profiles.services import get_default_profile

from .selectors import build_portfolio_content
from .services import render_portfolio_html
from .themes import THEMES, get_theme


class ThemeGalleryView(LoginRequiredMixin, TemplateView):
    template_name = "rendering/gallery.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["themes"] = THEMES
        context["profile"] = get_default_profile(self.request.user)
        return context


class ThemePreviewView(OwnerRequiredMixin, DetailView):
    """One of the user's profiles rendered with one template, full page."""

    model = MainProfile
    owner_field = "owner"

    def get(self, request, *args, **kwargs):
        theme = get_theme(kwargs["theme"])
        if theme is None:
            raise Http404("Unknown template")
        profile = self.get_object()
        toolbar = {
            "back_url": reverse("rendering:gallery"),
            "current": theme.key,
            "switch": [
                (t.key, t.name, reverse("rendering:preview", args=[t.key, profile.pk])) for t in THEMES
            ],
        }
        html = render_portfolio_html(
            theme, build_portfolio_content(profile), request=request, toolbar=toolbar, noindex=True
        )
        return HttpResponse(html)
