"""
Presentation layer for projects and Project Story (FOLDO-04, FOLDO-15).

Ownership rules (docs/CONVENTIONS.md section 1):
- list / add pages take ``profile_pk`` from the URL, but only to look up a
  profile the signed-in user owns; anything else is a 404.
- detail / edit / delete pages use ``OwnerRequiredMixin`` with
  ``owner_field = "profile__owner"``, so another user's project is a 404.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.mixins import AddAnotherMixin, OwnerRequiredMixin

from ..models import Project
from ..services import get_profile
from . import selectors, services
from .forms import ProjectForm


def list_url(profile_pk):
    return reverse("profiles:projects", args=[profile_pk])


class ProfileFromUrlMixin(LoginRequiredMixin):
    """Turn ``<profile_pk>`` into a profile the signed-in user owns (404 otherwise)."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.profile = get_profile(request.user, kwargs["profile_pk"])
        if self.profile is None:
            raise Http404("Profile not found")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["profile"] = self.profile
        return context


class OwnProjectMixin(OwnerRequiredMixin):
    """Detail / edit / delete: only the owner of the project's profile gets in."""

    model = Project
    owner_field = "profile__owner"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["profile"] = self.object.profile
        return context


class ProjectListView(ProfileFromUrlMixin, ListView):
    template_name = "profiles/projects/list.html"
    context_object_name = "projects"

    def get_queryset(self):
        return selectors.get_projects(self.profile)


class ProjectCreateView(AddAnotherMixin, ProfileFromUrlMixin, CreateView):
    add_another_url_name = "profiles:project_add"
    form_class = ProjectForm
    template_name = "profiles/projects/form.html"
    extra_context = {"heading": "เพิ่มโปรเจกต์", "submit_label": "บันทึกโปรเจกต์"}

    def form_valid(self, form):
        self.object = services.save_project(form, profile=self.profile)
        messages.success(self.request, f"เพิ่มโปรเจกต์ “{self.object.project_name}” แล้ว")
        return HttpResponseRedirect(reverse("profiles:project_detail", args=[self.object.pk]))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cancel_url"] = list_url(self.profile.pk)
        return context


class ProjectDetailView(OwnProjectMixin, DetailView):
    template_name = "profiles/projects/detail.html"
    context_object_name = "project"


class ProjectUpdateView(OwnProjectMixin, UpdateView):
    form_class = ProjectForm
    template_name = "profiles/projects/form.html"
    context_object_name = "project"
    extra_context = {"heading": "แก้ไขโปรเจกต์", "submit_label": "บันทึกการแก้ไข"}

    def form_valid(self, form):
        self.object = services.save_project(form)
        messages.success(self.request, "บันทึกการแก้ไขแล้ว")
        return HttpResponseRedirect(reverse("profiles:project_detail", args=[self.object.pk]))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cancel_url"] = reverse("profiles:project_detail", args=[self.object.pk])
        return context


class ProjectDeleteView(OwnProjectMixin, DeleteView):
    template_name = "profiles/projects/confirm_delete.html"
    context_object_name = "project"

    def form_valid(self, form):
        profile_pk, name = self.object.profile_id, self.object.project_name
        services.delete_project(self.object)
        messages.success(self.request, f"ลบโปรเจกต์ “{name}” แล้ว")
        return HttpResponseRedirect(list_url(profile_pk))