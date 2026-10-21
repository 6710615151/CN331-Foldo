from django.urls import path  # noqa: F401  (used once auth views exist)

from django.contrib.auth import views as auth_views
from . import views

from django.urls import path, reverse_lazy

app_name = "accounts"

# Login / logout / sign-up routes are added with the authentication Issue.
urlpatterns = [
    # Registration
    path("register/", views.register, name="register"),

    # Login / Logout
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # Example protected page
    path("dashboard/", views.dashboard, name="dashboard"),

     # --- Password reset flow (4 steps) ---

    # 1. User requests a reset by entering their email
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",

            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),

    # 2. Confirmation page: "check your email"
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),

    # 3. The link from the email lands here - uidb64/token identify the user securely
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),

    # 4. Success page after the password is actually changed
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]
