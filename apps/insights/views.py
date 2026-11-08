"""Portfolio DNA views (FOLDO-14). Owner only: others -> 404."""

from django.views.generic import DetailView

from apps.core.mixins import OwnerRequiredMixin
from apps.profiles.models import MainProfile

from .dna import build_dna


class OwnProfileMixin(OwnerRequiredMixin):
    model = MainProfile
    owner_field = "owner"
    context_object_name = "profile"


class PortfolioDnaView(OwnProfileMixin, DetailView):
    """GET-only view showing which portfolio versions reuse each profile item."""

    template_name = "insights/dna.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["dna"] = build_dna(self.object)
        return context
