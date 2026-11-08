from django.urls import path

from . import views

app_name = "profiles"

urlpatterns = [
    path("", views.profile_list, name="list"),
    # Kept so existing links / LOGIN_REDIRECT_URL = "profiles:detail" keep working.
    path("default/", views.default_profile, name="detail"),
    path("default/edit/", views.default_profile_edit, name="edit"),
    path("new/", views.profile_create, name="create"),
    path("<int:pk>/", views.profile_detail, name="view"),
    path("<int:pk>/edit/", views.profile_edit, name="update"),
    path("<int:pk>/default/", views.profile_make_default, name="make_default"),
    path("<int:pk>/delete/", views.profile_delete, name="delete"),
]
