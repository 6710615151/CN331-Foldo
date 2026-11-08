"""Portfolio DNA (FOLDO-14) and Quality Check (FOLDO-16). Owner only: others → 404."""

from django.http import Http404
from django.views.generic import DetailView

from apps.core.mixins import OwnerRequiredMixin
from apps.profiles.models import MainProfile
from apps.rendering.themes import DEFAULT_THEME_KEY, THEMES

from .dna import build_dna
from .quality import run_quality_check
from .sources import portfolio_versions


class OwnProfileMixin(OwnerRequiredMixin):
    model = MainProfile
    owner_field = "owner"
    context_object_name = "profile"


class PortfolioDnaView(OwnProfileMixin, DetailView):
    template_name = "insights/dna.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["dna"] = build_dna(self.object)
        return context


class QualityCheckView(OwnProfileMixin, DetailView):
    """GET only, so running (or re-running) the check can never change data.

    ``?version=<id>`` checks that version's selection and template;
    ``?theme=<key>`` checks the whole profile with that template.
    """

    template_name = "insights/quality.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        versions = portfolio_versions(self.object)
        version = None
        version_id = self.request.GET.get("version", "")
        if version_id:
            version = next((v for v in versions if str(v.id) == version_id), None)
            if version is None:
                raise Http404("Portfolio version not found")

        theme_key = (version.template if version else "") or self.request.GET.get("theme") or DEFAULT_THEME_KEY
        context.update(
            report=run_quality_check(
                self.object,
                theme_key=theme_key,
                selected=dict(version.selected) if version else None,
            ),
            themes=THEMES,
            versions=versions,
            version=version,
            theme_key=theme_key,
        )
        return context
