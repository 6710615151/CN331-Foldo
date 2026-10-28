from django.urls import path

from . import views

app_name = "accounts"

# Login / logout / sign-up routes are added with the authentication Issue.
urlpatterns = [
    path("settings/", views.AccountSettingsView.as_view(), name="settings"),
]
