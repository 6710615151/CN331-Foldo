"""
Presentation layer for the ``accounts`` app.

Keep views skinny: validate with ``forms.py``, read through ``selectors.py``,
write through ``services.py``.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import UpdateView

from . import selectors, services
from .forms import AccountSettingsForm

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from .forms import SignUpForm


class AccountSettingsView(LoginRequiredMixin, UpdateView):
    """Show and edit the signed-in user's own account (never anyone else's)."""

    form_class = AccountSettingsForm
    template_name = "accounts/settings.html"
    success_url = reverse_lazy("accounts:settings")

    def get_object(self, queryset=None):
        # No pk/username from the URL: the account always comes from the session.
        return selectors.get_account(self.request.user.pk)

    def form_valid(self, form):
        services.update_account(user=self.request.user, data=form.cleaned_data)
        messages.success(self.request, "บันทึกการตั้งค่าเรียบร้อยแล้ว")
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "กรุณาตรวจสอบข้อมูลที่กรอกอีกครั้ง")
        return super().form_invalid(form)

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

