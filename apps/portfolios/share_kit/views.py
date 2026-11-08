"""Presentation layer for the Share Kit (FOLDO-17). Owner only; read only."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from apps.portfolios.services import get_portfolio

from . import services

TEMPLATE = "portfolios/share_kit/share.html"


class _OwnedPortfolioMixin(LoginRequiredMixin):
    """The portfolio is looked up by id AND owner, so another user's id is a 404."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.portfolio = get_portfolio(request.user, kwargs["pk"])
        if self.portfolio is None:
            raise Http404("Portfolio not found")
        return super().dispatch(request, *args, **kwargs)


@method_decorator(never_cache, name="dispatch")  # publish state can change at any time
class ShareKitView(_OwnedPortfolioMixin, View):
    def get(self, request, pk):
        portfolio = self.portfolio
        context = {"portfolio": portfolio, "published": services.is_shareable(portfolio)}
        if context["published"]:
            url = services.public_url(portfolio, request)
            context.update(
                public_url=url,
                qr_svg=services.qr_svg_inline(url, title=f"QR code for {portfolio.title}"),
            )
        return render(request, TEMPLATE, context)


@method_decorator(never_cache, name="dispatch")
class QrDownloadView(_OwnedPortfolioMixin, View):
    """Serves the QR image. An unpublished version has no public page, so no QR (404)."""

    fmt = "png"

    def get(self, request, pk):
        if not services.is_shareable(self.portfolio):
            raise Http404("This portfolio is not published")
        url = services.public_url(self.portfolio, request)
        response = HttpResponse(services.qr_file(url, self.fmt), content_type=services.CONTENT_TYPES[self.fmt])
        response["Content-Disposition"] = f'attachment; filename="{services.download_name(self.portfolio, self.fmt)}"'
        return response
