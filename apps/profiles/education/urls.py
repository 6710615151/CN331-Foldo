"""
Routes for education. Included from ``apps/profiles/urls.py`` with no namespace
of its own, so the names are ``profiles:education_list``, ``profiles:education_add``
and so on.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("<int:profile_pk>/education/", views.EducationListView.as_view(), name="education_list"),
    path("<int:profile_pk>/education/add/", views.EducationCreateView.as_view(), name="education_add"),
    path("education/<int:pk>/edit/", views.EducationUpdateView.as_view(), name="education_edit"),
    path("education/<int:pk>/delete/", views.EducationDeleteView.as_view(), name="education_delete"),
]
