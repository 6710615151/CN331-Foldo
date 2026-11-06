from django.urls import path

from . import views

app_name = "profiles"

urlpatterns = [
    path("", views.profile_detail, name="detail"),
    path("edit/", views.profile_edit, name="edit"),
]
