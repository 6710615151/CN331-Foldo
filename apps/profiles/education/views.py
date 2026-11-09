"""
Presentation layer for education (FOLDO-04).

Ownership rules (docs/CONVENTIONS.md section 1):
- list / add views take ``profile_pk`` from the URL, but it is only used to look
  up a profile the signed-in user owns; anything else is a 404.
- edit / delete views use ``OwnerRequiredMixin`` with ``profile__owner``.
"""

import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import DatabaseError
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, TemplateView, UpdateView

from apps.core.mixins import AddAnotherMixin, OwnerRequiredMixin

from ..models import Education
from ..services import get_profile
from . import selectors, services
from .forms import EducationForm

logger = logging.getLogger(__name__)

FORM_TEMPLATE = "profiles/education/form.html"
NOT_SAVED = "Not saved. Please fix the highlighted fields. Everything else you typed has been kept."
SAVE_FAILED = (
    "We couldn't save this because of a temporary problem. "
    "Your entries are still in the form below. Please try again."
)


def list_url(profile_pk):
    return reverse("profiles:education_list", args=[profile_pk])


class OwnedProfileMixin(LoginRequiredMixin):
    """Resolve ``<profile_pk>`` to a profile the signed-in user owns (404 otherwise)."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.profile = get_profile(request.user, kwargs["profile_pk"])
        if self.profile is None:
            raise Http404("Profile not found")
        return super().dispatch(request, *args, **kwargs)


class EducationListView(OwnedProfileMixin, TemplateView):
    template_name = "profiles/education/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(profile=self.profile, educations=selectors.get_educations(self.profile))
        return context


class _EducationFormMixin:
    """Shared add / edit behaviour: one template, honest save and error messages."""

    model = Education
    form_class = EducationForm
    template_name = FORM_TEMPLATE
    heading = ""
    submit_label = "Save"

    def get_profile(self):
        raise NotImplementedError

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["profile"] = self.get_profile()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            profile=self.get_profile(),
            heading=self.heading,
            submit_label=self.submit_label,
            cancel_url=list_url(self.get_profile().pk),
        )
        return context

    def save(self, form):
        raise NotImplementedError

    def form_valid(self, form):
        try:
            education = self.save(form)
        except DatabaseError:
            logger.exception("Failed saving education for user %s", self.request.user.pk)
            form.add_error(None, SAVE_FAILED)
            messages.error(self.request, "Not saved. Please try again.")
            return self.render_to_response(self.get_context_data(form=form))
        messages.success(self.request, f"“{education.institution}” saved.")
        return HttpResponseRedirect(list_url(education.profile_id))

    def form_invalid(self, form):
        messages.error(self.request, NOT_SAVED)
        return super().form_invalid(form)


class EducationCreateView(AddAnotherMixin, OwnedProfileMixin, _EducationFormMixin, CreateView):
    add_another_url_name = "profiles:education_add"
    heading = "Add education"
    submit_label = "Add education"

    def get_profile(self):
        return self.profile

    def save(self, form):
        return services.create_education(profile=self.profile, data=form.cleaned_data)


class EducationUpdateView(OwnerRequiredMixin, _EducationFormMixin, UpdateView):
    owner_field = "profile__owner"
    heading = "Edit education"

    def get_queryset(self):
        return super().get_queryset().select_related("profile")

    def get_profile(self):
        return self.object.profile

    def save(self, form):
        return services.update_education(education=self.object, data=form.cleaned_data)


class EducationDeleteView(OwnerRequiredMixin, DeleteView):
    model = Education
    owner_field = "profile__owner"
    template_name = "profiles/education/confirm_delete.html"
    context_object_name = "education"

    def get_queryset(self):
        return super().get_queryset().select_related("profile")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(profile=self.object.profile, cancel_url=list_url(self.object.profile_id))
        return context

    def form_valid(self, form):
        success_url, name = list_url(self.object.profile_id), self.object.institution
        try:
            services.delete_education(education=self.object)
        except DatabaseError:
            logger.exception("Failed deleting education %s for user %s", self.object.pk, self.request.user.pk)
            messages.error(self.request, "Couldn't delete that entry. Please try again.")
            return HttpResponseRedirect(success_url)
        messages.success(self.request, f"“{name}” deleted.")
        return HttpResponseRedirect(success_url)
