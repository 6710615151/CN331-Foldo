import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.utils.text import slugify
from .pdf import PdfUnavailable, normalize_page_size, render_pdf
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from apps.rendering.themes import get_theme

from .forms import PortfolioForm
from .models import Portfolio
from .services import (
    duplicate_portfolio,
    get_portfolio,
    get_portfolios,
    profile_choices,
    render_version_html,
)

logger = logging.getLogger(__name__)


def _owned_or_404(request, pk):
    """Looked up by id AND owner, so another user's id behaves exactly like a missing one."""
    portfolio = get_portfolio(request.user, pk)
    if portfolio is None:
        raise Http404("Portfolio not found")
    return portfolio


def _render_portfolio(request, portfolio, *, preview, toolbar=None):
    """One version in its own template (FOLDO-07). Read-only: never publishes or saves anything."""
    return HttpResponse(render_version_html(portfolio, request=request, preview=preview, toolbar=toolbar))


def _process_form(request, portfolio):
    """Shared create/edit flow. Returns (redirect_response_or_None, form)."""
    instance = portfolio or Portfolio(owner=request.user)

    if request.method != "POST":
        # "Use this template" in the gallery links here with ?template=<key>.
        initial = {}
        if portfolio is None and get_theme(request.GET.get("template", "")):
            initial["template_key"] = request.GET["template"]
        return None, PortfolioForm(instance=instance, owner=request.user, initial=initial)

    form = PortfolioForm(request.POST, instance=instance, owner=request.user)
    if not form.is_valid():
        messages.error(request, "ยังไม่ได้บันทึก — แก้ช่องที่ไฮไลต์ ข้อมูลอื่นที่กรอกไว้ยังอยู่ครบ")
        return None, form

    try:
        with transaction.atomic():
            obj = form.save(commit=False)
            obj.owner = request.user  # never trust the client for ownership
            obj.save()
    except DatabaseError:
        logger.exception("Failed saving portfolio for user %s", request.user.pk)
        form.add_error(None, "บันทึกไม่สำเร็จเพราะระบบขัดข้องชั่วคราว ข้อมูลที่กรอกยังอยู่ในฟอร์ม ลองกดบันทึกอีกครั้ง")
        messages.error(request, "บันทึกไม่สำเร็จ ลองอีกครั้ง")
        return None, form

    saved_at = timezone.localtime(obj.updated_at).strftime("%H:%M")
    state = "เผยแพร่แล้ว" if obj.is_published else "ยังไม่เผยแพร่"
    messages.success(request, f"บันทึก “{obj.title}” แล้ว ({state}) เวลา {saved_at} น.")
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
    return render(
        request,
        "portfolios/form.html",
        {
            "form": form,
            "is_new": True,
            "portfolio": None,
            "has_profiles": profile_choices(request.user).exists(),
        },
    )


@login_required
def portfolio_edit(request, pk):
    portfolio = _owned_or_404(request, pk)
    response, form = _process_form(request, portfolio)
    if response:
        return response
    return render(
        request,
        "portfolios/form.html",
        {
            "form": form,
            "is_new": False,
            "portfolio": portfolio,
            "has_profiles": profile_choices(request.user).exists(),
        },
    )


@login_required
def portfolio_preview(request, pk):
    """Owner-only view, works whether or not the portfolio is published."""
    return _render_portfolio(request, _owned_or_404(request, pk), preview=True)


def portfolio_public(request, slug):
    """Anyone with the link, but only if the owner has published it."""
    portfolio = get_object_or_404(Portfolio.objects.select_related("owner", "profile"), slug=slug, is_published=True)
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
            messages.error(request, "ลบพอร์ตโฟลิโอไม่สำเร็จ ลองอีกครั้ง")
            return redirect("portfolios:list")
        messages.success(request, f"ลบ “{title}” แล้ว")
        return redirect("portfolios:list")
    return render(request, "portfolios/confirm_delete.html", {"portfolio": portfolio})


@require_POST
@login_required
def portfolio_duplicate(request, pk):
    """POST only. Copies one of the user's own versions as a new private draft."""
    portfolio = _owned_or_404(request, pk)
    try:
        copy = duplicate_portfolio(portfolio)
    except DatabaseError:
        logger.exception("Failed duplicating portfolio %s for user %s", pk, request.user.pk)
        messages.error(request, "ทำสำเนาไม่สำเร็จ ลองอีกครั้ง")
        return redirect("portfolios:list")
    messages.success(
        request, f"สร้างสำเนา “{copy.title}” แล้ว สำเนายังไม่เผยแพร่ ตั้งชื่อใหม่ให้ตรงกับงานที่จะสมัครได้เลย"
    )
    return redirect("portfolios:update", pk=copy.pk)


# --- FOLDO-08: device preview (desktop / mobile), loading and rendering-error states ---

PREVIEW_MODES = {"desktop": "Desktop", "mobile": "Mobile"}


@login_required
def portfolio_device_preview(request, pk):
    """Owner-only page with a Desktop / Mobile switch. The portfolio loads in an iframe below it."""
    portfolio = _owned_or_404(request, pk)
    mode = request.GET.get("mode")
    if mode not in PREVIEW_MODES:
        mode = "desktop"
    return render(
        request,
        "portfolios/device_preview.html",
        {
            "portfolio": portfolio,
            "mode": mode,
            "modes": PREVIEW_MODES,
        },
    )


@xframe_options_sameorigin
@login_required
def portfolio_preview_frame(request, pk):
    """The portfolio itself, shown inside the device preview. A template error shows a message, not a blank frame."""
    portfolio = _owned_or_404(request, pk)
    try:
        response = _render_portfolio(request, portfolio, preview=True, toolbar=False)
    except Exception:
        logger.exception("Failed rendering preview of portfolio %s for user %s", pk, request.user.pk)
        response = render(request, "portfolios/preview_error.html", {"portfolio": portfolio}, status=500)
    response["X-Robots-Tag"] = "noindex"
    return response


@login_required
def portfolio_pdf(request, pk):
    portfolio = _owned_or_404(request, pk)
    page_size = normalize_page_size(request.GET.get("size"))
    # The export page (JavaScript) sends this header and wants a status code it can show,
    # not a redirect. Everything else (a plain link) keeps the redirect plus message.
    in_page = request.headers.get("X-Foldo-Export") == "1"
    try:
        pdf = render_pdf(portfolio, request=request, page_size=page_size)
    except PdfUnavailable:
        logger.warning("PDF export unavailable: WeasyPrint or Pango missing", exc_info=True)
        message = "เซิร์ฟเวอร์นี้ยังสร้าง PDF ไม่ได้ ใช้ “ดูตัวอย่าง” แล้วสั่งพิมพ์เป็น PDF จากเบราว์เซอร์แทนได้"
        if in_page:
            return JsonResponse({"error": message}, status=503)
        messages.error(request, message)
        return redirect("portfolios:list")
    except Exception:
        logger.exception("PDF export failed for portfolio %s", pk)
        message = "สร้าง PDF ไม่สำเร็จ ลองอีกครั้ง"
        if in_page:
            return JsonResponse({"error": message}, status=500)
        messages.error(request, message)
        return redirect("portfolios:list")

    filename = f"{slugify(portfolio.title) or 'portfolio'}.pdf"
    disposition = "inline" if request.GET.get("inline") else "attachment"
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    return response
