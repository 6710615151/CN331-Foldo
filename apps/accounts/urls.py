from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import LoginForm, ThaiPasswordResetForm, ThaiSetPasswordForm

app_name = "accounts"

urlpatterns = [
    path("settings/", views.AccountSettingsView.as_view(), name="settings"),
    path("password/", views.PasswordChangeView.as_view(), name="password_change"),
    # Registration
    path("register/", views.register, name="register"),
    # Login / Logout
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=LoginForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Legacy example page: kept so old links work, now sends people to the real dashboard.
    path("dashboard/", views.dashboard, name="dashboard"),
    # --- Password reset flow (4 steps) ---
    # 1. User requests a reset by entering their email
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
            form_class=ThaiPasswordResetForm,
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    # 2. Confirmation page: "check your email"
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"),
        name="password_reset_done",
    ),
    # 3. The link from the email lands here - uidb64/token identify the user securely
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            form_class=ThaiSetPasswordForm,
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    # 4. Success page after the password is actually changed
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"),
        name="password_reset_complete",
    ),
]
