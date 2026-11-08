import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin

from .forms import PortfolioForm
from .models import Portfolio
from .services import build_portfolio_context, get_portfolio, get_portfolios, layout_for, profile_choices

logger = logging.getLogger(__name__)

from django.http import Http404, HttpResponse
from .rendering_bridge import render_html, theme_for

def _owned_or_404(request, pk):
    """Looked up by id AND owner, so another user's id behaves exactly like a missing one."""
    portfolio = get_portfolio(request.user, pk)
    if portfolio is None:
        raise Http404("Portfolio not found")
    return portfolio


def _render_portfolio(request, portfolio, *, preview):
    theme = theme_for(portfolio)
    if theme is not None:
        return HttpResponse(render_html(portfolio, theme, request=request, preview=preview))
    context = build_portfolio_context(portfolio)
    context["preview"] = preview
    return render(request, layout_for(portfolio), context)


def _process_form(request, portfolio):
    """Shared create/edit flow. Returns (redirect_response_or_None, form)."""
    instance = portfolio or Portfolio(owner=request.user)

    if request.method != "POST":
        return None, PortfolioForm(instance=instance, owner=request.user)

    form = PortfolioForm(request.POST, instance=instance, owner=request.user)
    if not form.is_valid():
        messages.error(request, "Not saved. Please fix the highlighted fields. Everything else you typed has been kept.")
        return None, form

    try:
        with transaction.atomic():
            obj = form.save(commit=False)
            obj.owner = request.user  # never trust the client for ownership
            obj.save()
    except DatabaseError:
        logger.exception("Failed saving portfolio for user %s", request.user.pk)
        form.add_error(None, "We couldn't save your portfolio because of a temporary problem. "
                             "Your entries are still in the form below. Please try again.")
        messages.error(request, "Not saved. Please try again.")
        return None, form

    saved_at = timezone.localtime(obj.updated_at).strftime("%H:%M")
    state = "published" if obj.is_published else "saved as a private draft"
    messages.success(request, f"“{obj.title}” {state} at {saved_at}.")
    return redirect("portfolios:preview", pk=obj.pk), form


@login_required
def portfolio_list(request):
    portfolios = list(get_portfolios(request.user).select_related("profile"))
    return render(request, "portfolios/list.html", {"portfolios": portfolios})


@login_required
def portfolio_create(request):
    response, form = _process_form(request, None)
    if response:
        return response
    return render(request, "portfolios/form.html", {
        "form": form, "is_new": True, "portfolio": None,
        "has_profiles": profile_choices(request.user).exists(),
    })


@login_required
def portfolio_edit(request, pk):
    portfolio = _owned_or_404(request, pk)
    response, form = _process_form(request, portfolio)
    if response:
        return response
    return render(request, "portfolios/form.html", {
        "form": form, "is_new": False, "portfolio": portfolio,
        "has_profiles": profile_choices(request.user).exists(),
    })


@login_required
def portfolio_preview(request, pk):
    """Owner-only view, works whether or not the portfolio is published."""
    return _render_portfolio(request, _owned_or_404(request, pk), preview=True)


def portfolio_public(request, slug):
    """Anyone with the link, but only if the owner has published it."""
    portfolio = get_object_or_404(
        Portfolio.objects.select_related("owner", "profile"), slug=slug, is_published=True
    )
    return _render_portfolio(request, portfolio, preview=False)


@login_required
def portfolio_delete(request, pk):
    portfolio = _owned_or_404(request, pk)
    if request.method == "POST":
        title = portfolio.title
        try:
            portfolio.delete()
        except DatabaseError:
            logger.exception("Failed deleting portfolio %s for user %s", pk, request.user.pk)
            messages.error(request, "Couldn't delete that portfolio. Please try again.")
            return redirect("portfolios:list")
        messages.success(request, f"“{title}” was deleted.")
        return redirect("portfolios:list")
    return render(request, "portfolios/confirm_delete.html", {"portfolio": portfolio})




# --- FOLDO-08: device preview (desktop / mobile), loading and rendering-error states ---

PREVIEW_MODES = {"desktop": "Desktop", "mobile": "Mobile"}


@login_required
def portfolio_device_preview(request, pk):
    """Owner-only page with a Desktop / Mobile switch. The portfolio loads in an iframe below it."""
    portfolio = _owned_or_404(request, pk)
    mode = request.GET.get("mode")
    if mode not in PREVIEW_MODES:
        mode = "desktop"
    return render(request, "portfolios/device_preview.html", {
        "portfolio": portfolio, "mode": mode, "modes": PREVIEW_MODES,
    })


@xframe_options_sameorigin
@login_required
def portfolio_preview_frame(request, pk):
    """The portfolio itself, shown inside the device preview. A template error shows a message, not a blank frame."""
    portfolio = _owned_or_404(request, pk)
    try:
        response = _render_portfolio(request, portfolio, preview=False)
    except Exception:
        logger.exception("Failed rendering preview of portfolio %s for user %s", pk, request.user.pk)
        response = render(request, "portfolios/preview_error.html", {"portfolio": portfolio}, status=500)
    response["X-Robots-Tag"] = "noindex"
    return response