"""
Routes for projects (FOLDO-04, FOLDO-15). Included from ``apps/profiles/urls.py``
with no namespace of its own, so the names are ``profiles:projects``,
``profiles:project_add`` and so on.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("<int:profile_pk>/projects/", views.ProjectListView.as_view(), name="projects"),
    path("<int:profile_pk>/projects/add/", views.ProjectCreateView.as_view(), name="project_add"),
    path("projects/<int:pk>/", views.ProjectDetailView.as_view(), name="project_detail"),
    path("projects/<int:pk>/edit/", views.ProjectUpdateView.as_view(), name="project_edit"),
    path("projects/<int:pk>/delete/", views.ProjectDeleteView.as_view(), name="project_delete"),
]
