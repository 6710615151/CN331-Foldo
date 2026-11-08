"""Writes for projects (FOLDO-04). The profile always comes from the view, never from the form."""

from django.db import transaction


@transaction.atomic
def save_project(form, profile=None):
    """Create (profile given) or update (profile None) a project from a valid ProjectForm."""
    project = form.save(commit=False)
    if profile is not None:
        project.profile = profile
    project.save()
    return project


@transaction.atomic
def delete_project(project):
    project.delete()