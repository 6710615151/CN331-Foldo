import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import MainProfileForm
from .models import MainProfile
from .services import build_display, get_profile

logger = logging.getLogger(__name__)


@login_required
def profile_detail(request):
    # Always looked up by the logged-in user; there is no id in the URL, so no cross-user access.
    profile = get_profile(request.user)
    if profile is None:
        messages.info(request, "You haven't created your Main Profile yet. Add the basics to get started.")
        return redirect("profiles:edit")
    return render(
        request,
        "profiles/detail.html",
        {"profile": profile, "display": build_display(request.user, profile)},
    )


@login_required
def profile_edit(request):
    profile = get_profile(request.user)
    instance = profile or MainProfile(owner=request.user)

    if request.method == "POST":
        form = MainProfileForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            try:
                with transaction.atomic():
                    obj = form.save(commit=False)
                    obj.owner = request.user  # never trust the client for ownership
                    obj.save()
            except (DatabaseError, OSError):
                logger.exception("Failed saving main profile for user %s", request.user.pk)
                form.add_error(
                    None,
                    "We couldn't save your profile because of a temporary problem. "
                    "Your entries are still in the form below. Please try again "
                    "(re-select your photo if you added one).",
                )
                messages.error(request, "Not saved. Please try again.")
            else:
                saved_at = timezone.localtime(obj.updated_at).strftime("%H:%M")
                if obj.is_complete:
                    messages.success(request, f"Profile saved at {saved_at}.")
                else:
                    messages.warning(
                        request,
                        f"Profile saved at {saved_at}, but it's incomplete. "
                        f"Still needed: {', '.join(obj.missing_fields)}.",
                    )
                return redirect("profiles:detail")
        else:
            messages.error(
                request,
                "Not saved. Please fix the highlighted fields. Everything else you typed has been kept.",
            )
    else:
        form = MainProfileForm(instance=instance)

    return render(request, "profiles/edit.html", {"form": form, "is_new": profile is None, "profile": profile})
