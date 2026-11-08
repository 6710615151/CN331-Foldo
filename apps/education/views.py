import logging
from collections import namedtuple

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import EducationLevelForm
from .models import EducationEntry
from .services import get_entries

logger = logging.getLogger(__name__)

LevelBlock = namedtuple("LevelBlock", "level label form")


def _build_blocks(request):
    """One form per level, pre-filled from the user's existing row (if any)."""
    existing = {entry.level: entry for entry in get_entries(request.user)}
    data = request.POST if request.method == "POST" else None

    blocks = []
    for level, label in EducationEntry.Level.choices:
        instance = existing.get(level) or EducationEntry(owner=request.user, level=level)
        form = EducationLevelForm(data, instance=instance, prefix=level)
        blocks.append(LevelBlock(level, label, form))
    return blocks


def _save_blocks(request, blocks):
    """All-or-nothing: a blank level removes its row; a filled one is created or updated."""
    with transaction.atomic():
        for block in blocks:
            form = block.form
            if form.is_blank:
                if form.instance.pk:
                    form.instance.delete()
                continue
            entry = form.save(commit=False)
            entry.owner = request.user  # never trust the client for ownership
            entry.level = block.level
            entry.save()


@login_required
def education_settings(request):
    blocks = _build_blocks(request)

    if request.method == "POST":
        # Validate every level (no short-circuit) so all errors show at once.
        results = [block.form.is_valid() for block in blocks]
        if all(results):
            try:
                _save_blocks(request, blocks)
            except DatabaseError:
                logger.exception("Failed saving education for user %s", request.user.pk)
                messages.error(
                    request,
                    "Not saved because of a temporary problem. Your entries are still in the form. Please try again.",
                )
            else:
                messages.success(request, f"Education saved at {timezone.localtime().strftime('%H:%M')}.")
                return redirect("education:settings")
        else:
            messages.error(
                request,
                "Not saved. Please fix the highlighted fields. Everything else you typed has been kept.",
            )

    latest = get_entries(request.user).order_by("-updated_at").first()
    return render(
        request,
        "education/settings.html",
        {"blocks": blocks, "last_saved": latest.updated_at if latest else None},
    )
