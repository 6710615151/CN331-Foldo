"""Presentation layer for the ``profiles`` app (FOLDO-03 Main Profile).

Views stay skinny: ownership comes from ``OwnerRequiredMixin`` (another user's
id → 404), validation from ``forms.py`` and writes from ``services.py``.
"""

import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import DatabaseError
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
from django.views.generic.detail import SingleObjectMixin

from apps.core.mixins import OwnerRequiredMixin

from . import services
from .forms import MainProfileForm
from .models import MAX_PROFILES_PER_USER, MainProfile

logger = logging.getLogger(__name__)


class OwnProfileMixin(OwnerRequiredMixin):
    model = MainProfile
    owner_field = "owner"
    context_object_name = "profile"


class ProfileFormMixin:
    """Shared create/edit behaviour: owner from the session, honest save messages."""

    form_class = MainProfileForm
    template_name = "profiles/edit.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["owner"] = self.request.user
        return kwargs

    def form_valid(self, form):
        try:
            profile = services.save_profile(form, owner=self.request.user)
        except (DatabaseError, OSError):
            logger.exception("Failed saving profile for user %s", self.request.user.pk)
            form.add_error(
                None,
                "บันทึกไม่สำเร็จเพราะระบบขัดข้องชั่วคราว ข้อมูลที่กรอกยังอยู่ในฟอร์ม "
                "ลองกดบันทึกอีกครั้ง (ถ้าเลือกรูปไว้ ต้องเลือกรูปใหม่)",
            )
            messages.error(self.request, "บันทึกไม่สำเร็จ ลองอีกครั้ง")
            return self.render_to_response(self.get_context_data(form=form))

        saved_at = services.saved_at_label(profile)
        if profile.is_complete:
            messages.success(self.request, f"บันทึก “{profile.label}” แล้ว เวลา {saved_at} น.")
        else:
            from apps.core.selectors import profile_missing_labels

            messages.warning(
                self.request,
                f"บันทึก “{profile.label}” แล้ว แต่พอร์ตโฟลิโอยังต้องใช้ "
                f"{', '.join(profile_missing_labels(profile))}",
            )
        return redirect("profiles:view", pk=profile.pk)

    def form_invalid(self, form):
        messages.error(
            self.request,
            "ยังไม่ได้บันทึก — แก้ช่องที่ไฮไลต์ ข้อมูลอื่นที่กรอกไว้ยังอยู่ครบ",
        )
        return super().form_invalid(form)


class ProfileListView(LoginRequiredMixin, ListView):
    template_name = "profiles/list.html"
    context_object_name = "profiles"

    def get_queryset(self):
        return services.get_profiles(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_create"] = len(context["profiles"]) < MAX_PROFILES_PER_USER
        context["max_profiles"] = MAX_PROFILES_PER_USER
        return context


class ProfileDetailView(OwnProfileMixin, DetailView):
    template_name = "profiles/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["display"] = services.build_display(self.request.user, self.object)
        # What would make *this* profile stronger (portfolio steps live on the dashboard).
        from apps.core.selectors import get_next_steps

        steps = get_next_steps(self.request.user, profile=self.object)
        context["next_steps"] = [step for step in steps if step["key"] not in ("portfolio", "publish")][:3]
        return context


class ProfileCreateView(LoginRequiredMixin, ProfileFormMixin, CreateView):
    extra_context = {"is_new": True, "profile": None}

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not services.can_create_profile(request.user):
            messages.error(
                request,
                f"มีโปรไฟล์ได้สูงสุด {MAX_PROFILES_PER_USER} โปรไฟล์ ลบโปรไฟล์ที่ไม่ใช้ก่อนแล้วค่อยสร้างใหม่",
            )
            return redirect("profiles:list")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = MainProfile(owner=self.request.user)
        return kwargs


class ProfileUpdateView(OwnProfileMixin, ProfileFormMixin, UpdateView):
    extra_context = {"is_new": False}


class ProfileDeleteView(OwnProfileMixin, DeleteView):
    template_name = "profiles/confirm_delete.html"
    success_url = reverse_lazy("profiles:list")

    def form_valid(self, form):
        label = self.object.label
        try:
            services.delete_profile(self.object)
        except (DatabaseError, OSError):
            logger.exception("Failed deleting profile %s for user %s", self.object.pk, self.request.user.pk)
            messages.error(self.request, "ลบโปรไฟล์ไม่สำเร็จ ลองอีกครั้ง")
            return redirect("profiles:view", pk=self.object.pk)
        messages.success(self.request, f"ลบ “{label}” แล้ว")
        return redirect(self.success_url)


class ProfileMakeDefaultView(OwnProfileMixin, SingleObjectMixin, View):
    """POST only (GET → 405). Redirects back only to a page on this site."""

    def post(self, request, *args, **kwargs):
        profile = self.get_object()
        services.set_default_profile(profile)
        messages.success(request, f"ตั้ง “{profile.label}” เป็นโปรไฟล์หลักแล้ว พอร์ตโฟลิโอที่ใช้โปรไฟล์หลักจะแสดงข้อมูลชุดนี้")
        next_url = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            next_url = reverse("profiles:list")
        return redirect(next_url)


class DefaultProfileView(LoginRequiredMixin, View):
    """``/profiles/default/``: open the default profile, or start one."""

    target = "profiles:view"

    def get(self, request):
        profile = services.get_default_profile(request.user)
        if profile is None:
            if self.target == "profiles:view":
                messages.info(request, "ยังไม่มีโปรไฟล์ เริ่มจากชื่อและหัวข้อแนะนำตัวก่อน ที่เหลือเติมทีหลังได้")
            return redirect("profiles:create")
        return redirect(self.target, pk=profile.pk)


# URL names in urls.py point at these (kept as functions so urls.py is unchanged).
profile_list = ProfileListView.as_view()
profile_detail = ProfileDetailView.as_view()
profile_create = ProfileCreateView.as_view()
profile_edit = ProfileUpdateView.as_view()
profile_delete = ProfileDeleteView.as_view()
profile_make_default = ProfileMakeDefaultView.as_view()
default_profile = DefaultProfileView.as_view()
default_profile_edit = DefaultProfileView.as_view(target="profiles:update")
