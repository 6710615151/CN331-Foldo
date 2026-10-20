"""
Presentation layer for the ``accounts`` app.

Log in, log out and sign-up views arrive with the authentication Issue. Keep
them skinny: validate with ``forms.py``, write through ``services.py``.
"""

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from .forms import SignUpForm


def register(request):
    """
    Handle new user sign-up. On success, logs the user in immediately
    and redirects to the 'home' URL (change to whatever your app uses).
    """
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # log the user in right after signup
            return redirect("accounts:dashboard")
    else:
        form = SignUpForm()

    return render(request, "registration/register.html", {"form": form})


@login_required
def dashboard(request):
    """
    Example of a protected view. @login_required redirects
    anonymous users to LOGIN_URL (set in settings.py).
    """
    return render(request, "registration/dashboard.html")