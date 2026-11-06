import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import MainProfileForm
from .models import MAX_PROFILES_PER_USER, MainProfile
from .services import build_display, get_profile, get_profiles, set_default_profile

logger = logging.getLogger(__name__)


def _owned_or_404(request, pk):
    """Look up by id AND owner, so another user's id behaves exactly like a missing one."""
    profile = get_profile(request.user, pk)
    if profile is None:
        raise Http404("Profile not found")
    return profile


def _process_form(request, profile):
    """Shared create/edit flow. Returns (redirect_response_or_None, form)."""
    instance = profile or MainProfile(owner=request.user)

    if request.method != "POST":
        return None, MainProfileForm(instance=instance, owner=request.user)

    form = MainProfileForm(request.POST, request.FILES, instance=instance, owner=request.user)
    if not form.is_valid():
        messages.error(
            request,
            "Not saved. Please fix the highlighted fields. Everything else you typed has been kept.",
        )
        return None, form

    try:
        with transaction.atomic():
            obj = form.save(commit=False)
            obj.owner = request.user  # never trust the client for ownership
            obj.save()
    except (DatabaseError, OSError):
        logger.exception("Failed saving profile for user %s", request.user.pk)
        form.add_error(
            None,
            "We couldn't save your profile because of a temporary problem. "
            "Your entries are still in the form below. Please try again "
            "(re-select your photo if you added one).",
        )
        messages.error(request, "Not saved. Please try again.")
        return None, form

    saved_at = timezone.localtime(obj.updated_at).strftime("%H:%M")
    if obj.is_complete:
        messages.success(request, f"“{obj.label}” saved at {saved_at}.")
    else:
        messages.warning(
            request,
            f"“{obj.label}” saved at {saved_at}, but it's incomplete. "
            f"Still needed: {', '.join(obj.missing_fields)}.",
        )
    return redirect("profiles:view", pk=obj.pk), form


@login_required
def profile_list(request):
    profiles = list(get_profiles(request.user))
    return render(
        request,
        "profiles/list.html",
        {
            "profiles": profiles,
            "can_create": len(profiles) < MAX_PROFILES_PER_USER,
            "max_profiles": MAX_PROFILES_PER_USER,
        },
    )


@login_required
def default_profile(request):
    """Keeps the old `profiles:detail` link working: go to the default profile."""
    profile = get_profile(request.user)
    if profile is None:
        messages.info(request, "You haven't created a profile yet. Add the basics to get started.")
        return redirect("profiles:create")
    return redirect("profiles:view", pk=profile.pk)


@login_required
def default_profile_edit(request):
    """Keeps the old `profiles:edit` link working: edit the default profile."""
    profile = get_profile(request.user)
    if profile is None:
        return redirect("profiles:create")
    return redirect("profiles:update", pk=profile.pk)


@login_required
def profile_detail(request, pk):
    profile = _owned_or_404(request, pk)
    return render(
        request,
        "profiles/detail.html",
        {"profile": profile, "display": build_display(request.user, profile)},
    )


@login_required
def profile_create(request):
    if get_profiles(request.user).count() >= MAX_PROFILES_PER_USER:
        messages.error(request, f"You can have up to {MAX_PROFILES_PER_USER} profiles. Delete one to add another.")
        return redirect("profiles:list")

    response, form = _process_form(request, None)
    if response:
        return response
    return render(request, "profiles/edit.html", {"form": form, "is_new": True, "profile": None})


@login_required
def profile_edit(request, pk):
    profile = _owned_or_404(request, pk)
    response, form = _process_form(request, profile)
    if response:
        return response
    return render(request, "profiles/edit.html", {"form": form, "is_new": False, "profile": profile})


@login_required
@require_POST
def profile_make_default(request, pk):
    profile = _owned_or_404(request, pk)
    set_default_profile(profile)
    messages.success(request, f"“{profile.label}” is now your default profile.")
    return redirect(request.POST.get("next") or "profiles:list")


@login_required
def profile_delete(request, pk):
    profile = _owned_or_404(request, pk)
    if request.method == "POST":
        label = profile.label
        try:
            profile.delete()
        except (DatabaseError, OSError):
            logger.exception("Failed deleting profile %s for user %s", pk, request.user.pk)
            messages.error(request, "Couldn't delete that profile. Please try again.")
            return redirect("profiles:view", pk=pk)
        messages.success(request, f"“{label}” was deleted.")
        return redirect("profiles:list")
    return render(request, "profiles/confirm_delete.html", {"profile": profile})
