"""
Presentation layer for skills and experience (FOLDO-04).

Ownership rules (docs/CONVENTIONS.md section 1):
- list / add views take ``profile_pk`` from the URL, but it is only used to look
  up a profile the signed-in user owns; anything else is a 404.
- edit / delete views use ``OwnerRequiredMixin`` with ``profile__owner``.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, TemplateView, UpdateView

from apps.core.mixins import OwnerRequiredMixin

from ..models import Experience, Skill
from ..services import get_profile
from . import selectors, services
from .forms import ExperienceForm, SkillForm

FORM_TEMPLATE = "profiles/skills_experience/form.html"
DELETE_TEMPLATE = "profiles/skills_experience/confirm_delete.html"
DUPLICATE_SKILL = "You already have this skill on this profile."


def overview_url(profile_pk):
    return reverse("profiles:skills_experience", args=[profile_pk])


class OwnedProfileMixin(LoginRequiredMixin):
    """Resolve ``<profile_pk>`` to a profile the user owns (404 otherwise)."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.profile = get_profile(request.user, kwargs["profile_pk"])
        if self.profile is None:
            raise Http404("Profile not found")
        return super().dispatch(request, *args, **kwargs)


class SkillsExperienceView(OwnedProfileMixin, TemplateView):
    template_name = "profiles/skills_experience/overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            profile=self.profile,
            skills=selectors.get_skills(self.profile),
            experiences=selectors.get_experiences(self.profile),
        )
        return context


# --- shared behaviour ------------------------------------------------------


class _FormPageMixin:
    """Context shared by the add / edit pages, which use one template."""

    heading = ""
    submit_label = "Save"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            heading=self.heading,
            submit_label=self.submit_label,
            cancel_url=overview_url(self.get_profile().pk),
        )
        return context


class _ChildMixin(_FormPageMixin):
    """Edit / delete: the row's own profile decides where to go back to."""

    def get_profile(self):
        return self.object.profile

    def get_success_url(self):
        return overview_url(self.object.profile_id)


class _EditFormMixin(_ChildMixin):
    """Edit pages only: the form needs the row's profile (delete pages use a plain form)."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["profile"] = self.object.profile
        return kwargs


# --- skills ----------------------------------------------------------------


class SkillCreateView(OwnedProfileMixin, _FormPageMixin, CreateView):
    model = Skill
    form_class = SkillForm
    template_name = FORM_TEMPLATE
    heading = "Add skill"
    submit_label = "Add skill"

    def get_profile(self):
        return self.profile

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["profile"] = self.profile
        return kwargs

    def form_valid(self, form):
        try:
            skill = services.create_skill(profile=self.profile, data=form.cleaned_data)
        except IntegrityError:  # two requests raced past the form's duplicate check
            form.add_error("name", DUPLICATE_SKILL)
            return self.form_invalid(form)
        messages.success(self.request, f"Skill “{skill.name}” added.")
        return HttpResponseRedirect(overview_url(self.profile.pk))

    def form_invalid(self, form):
        messages.error(self.request, "Not saved. Please fix the highlighted fields.")
        return super().form_invalid(form)


class SkillUpdateView(OwnerRequiredMixin, _EditFormMixin, UpdateView):
    model = Skill
    owner_field = "profile__owner"
    form_class = SkillForm
    template_name = FORM_TEMPLATE
    heading = "Edit skill"

    def form_valid(self, form):
        try:
            skill = services.update_skill(skill=self.object, data=form.cleaned_data)
        except IntegrityError:
            form.add_error("name", DUPLICATE_SKILL)
            return self.form_invalid(form)
        messages.success(self.request, f"Skill “{skill.name}” saved.")
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Not saved. Please fix the highlighted fields.")
        return super().form_invalid(form)


class SkillDeleteView(OwnerRequiredMixin, _ChildMixin, DeleteView):
    model = Skill
    owner_field = "profile__owner"
    template_name = DELETE_TEMPLATE
    heading = "Delete skill"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["item_label"] = str(self.object)
        return context

    def form_valid(self, form):
        success_url, name = self.get_success_url(), self.object.name
        services.delete_skill(skill=self.object)
        messages.success(self.request, f"Skill “{name}” deleted.")
        return HttpResponseRedirect(success_url)


# --- experience --------------------------------------------------------------


class ExperienceCreateView(OwnedProfileMixin, _FormPageMixin, CreateView):
    model = Experience
    form_class = ExperienceForm
    template_name = FORM_TEMPLATE
    heading = "Add experience"
    submit_label = "Add experience"

    def get_profile(self):
        return self.profile

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["profile"] = self.profile
        return kwargs

    def form_valid(self, form):
        experience = services.create_experience(profile=self.profile, data=form.cleaned_data)
        messages.success(self.request, f"Experience “{experience.job_title}” added.")
        return HttpResponseRedirect(overview_url(self.profile.pk))

    def form_invalid(self, form):
        messages.error(self.request, "Not saved. Please fix the highlighted fields.")
        return super().form_invalid(form)


class ExperienceUpdateView(OwnerRequiredMixin, _EditFormMixin, UpdateView):
    model = Experience
    owner_field = "profile__owner"
    form_class = ExperienceForm
    template_name = FORM_TEMPLATE
    heading = "Edit experience"

    def form_valid(self, form):
        experience = services.update_experience(experience=self.object, data=form.cleaned_data)
        messages.success(self.request, f"Experience “{experience.job_title}” saved.")
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Not saved. Please fix the highlighted fields.")
        return super().form_invalid(form)


class ExperienceDeleteView(OwnerRequiredMixin, _ChildMixin, DeleteView):
    model = Experience
    owner_field = "profile__owner"
    template_name = DELETE_TEMPLATE
    heading = "Delete experience"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["item_label"] = str(self.object)
        return context

    def form_valid(self, form):
        success_url, title = self.get_success_url(), self.object.job_title
        services.delete_experience(experience=self.object)
        messages.success(self.request, f"Experience “{title}” deleted.")
        return HttpResponseRedirect(success_url)
