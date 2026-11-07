"""
Routes for skills and experience. Included from ``apps/profiles/urls.py`` with
no namespace of its own, so the names are ``profiles:skills_experience``,
``profiles:skill_add`` and so on.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("<int:profile_pk>/skills-experience/", views.SkillsExperienceView.as_view(), name="skills_experience"),
    path("<int:profile_pk>/skills/add/", views.SkillCreateView.as_view(), name="skill_add"),
    path("skills/<int:pk>/edit/", views.SkillUpdateView.as_view(), name="skill_edit"),
    path("skills/<int:pk>/delete/", views.SkillDeleteView.as_view(), name="skill_delete"),
    path("<int:profile_pk>/experience/add/", views.ExperienceCreateView.as_view(), name="experience_add"),
    path("experience/<int:pk>/edit/", views.ExperienceUpdateView.as_view(), name="experience_edit"),
    path("experience/<int:pk>/delete/", views.ExperienceDeleteView.as_view(), name="experience_delete"),
]
