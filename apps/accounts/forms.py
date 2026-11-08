"""
Validation layer for the ``accounts`` app.

Never trust user input: every field is cleaned here before it reaches
``services.py``. Django's built-in user forms are bound to ``auth.User``; these
subclasses point them at ``CustomUser`` so the admin (and, later, sign-up)
validate against the right model.
"""

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserChangeForm,
    UserCreationForm,
)
from django.core.exceptions import ValidationError

from apps.core.forms import BootstrapFormMixin

from .models import CustomUser
from .selectors import email_is_taken

# replace usual User from from django.contrib.auth.models import User to CustomUser
from django.contrib.auth import get_user_model
User = get_user_model()

class _CleanEmailMixin:
    """Normalise the e-mail and keep it unique across accounts."""

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if email and email_is_taken(email, exclude_pk=self.instance.pk):
            raise forms.ValidationError("อีเมลนี้มีบัญชีอยู่แล้ว ลองเข้าสู่ระบบ หรือใช้อีเมลอื่น")
        return email


class CustomUserCreationForm(_CleanEmailMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("username", "email")


class CustomUserChangeForm(_CleanEmailMixin, UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = CustomUser
        fields = ("username", "email", "first_name", "last_name")


class AccountSettingsForm(BootstrapFormMixin, _CleanEmailMixin, forms.ModelForm):
    """Basic account details a signed-in user may edit (username is read-only)."""

    class Meta:
        model = CustomUser
        fields = ("first_name", "last_name", "email")
        labels = {"first_name": "ชื่อ", "last_name": "นามสกุล", "email": "อีเมล"}
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True


# ---------------------------------------------------------------------------
# Authentication forms, in Thai to match the rest of the app.
# Django's own messages stay English elsewhere (LANGUAGE_CODE = "en-us"), so the
# sign-in / sign-up / password screens set their own labels and messages here.
# ---------------------------------------------------------------------------

PASSWORD_HINT = "อย่างน้อย 8 ตัวอักษร ไม่ใช่ตัวเลขล้วน ไม่ใช่รหัสที่เดาง่าย และไม่คล้ายชื่อผู้ใช้หรืออีเมล"

# Django's password validator codes -> Thai messages.
_PASSWORD_ERRORS = {
    "password_too_short": "รหัสผ่านสั้นเกินไป ต้องมีอย่างน้อย 8 ตัวอักษร",
    "password_too_common": "รหัสผ่านนี้เดาง่ายเกินไป ลองใช้รหัสอื่น",
    "password_entirely_numeric": "รหัสผ่านต้องไม่เป็นตัวเลขล้วน",
    "password_too_similar": "รหัสผ่านคล้ายกับชื่อผู้ใช้หรืออีเมลมากเกินไป",
}


class ThaiPasswordMixin:
    """Thai labels / mismatch message, and Thai versions of the validator errors."""

    error_messages = {"password_mismatch": "รหัสผ่านทั้งสองช่องไม่ตรงกัน"}

    def validate_password_for_user(self, user, password_field_name="password2"):
        password = self.cleaned_data.get(password_field_name)
        if not password:
            return
        try:
            password_validation.validate_password(password, user)
        except ValidationError as error:
            messages = [
                _PASSWORD_ERRORS.get(item.code, item.messages[0]) for item in error.error_list
            ]
            self.add_error(password_field_name, list(dict.fromkeys(messages)))


class SignUpForm(BootstrapFormMixin, ThaiPasswordMixin, UserCreationForm):
    """
    Registration form. Extends Django's built-in UserCreationForm
    to also require and save an email address.
    """

    error_messages = ThaiPasswordMixin.error_messages

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
        labels = {"username": "ชื่อผู้ใช้", "email": "อีเมล"}
        help_texts = {"username": "ใช้ตัวอักษรภาษาอังกฤษ ตัวเลข และ @ . + - _ ได้ ไม่เกิน 150 ตัว"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        self.fields["username"].widget.attrs.update(autocomplete="username", placeholder="เช่น napat.c")
        self.fields["email"].widget.attrs.update(autocomplete="email", placeholder="you@example.com")
        self.fields["password1"].label = "รหัสผ่าน"
        self.fields["password1"].help_text = PASSWORD_HINT
        self.fields["password2"].label = "ยืนยันรหัสผ่าน"
        self.fields["password2"].help_text = ""

    def clean_username(self):
        """Same rule as Django's (no case-only duplicates), with a Thai message."""
        username = self.cleaned_data.get("username")
        if username and User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("ชื่อผู้ใช้นี้มีคนใช้แล้ว ลองชื่ออื่น")
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    error_messages = {
        "invalid_login": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง (ตัวพิมพ์เล็ก–ใหญ่มีผล)",
        "inactive": "บัญชีนี้ถูกปิดใช้งาน ติดต่อผู้ดูแลระบบ",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "ชื่อผู้ใช้"
        self.fields["password"].label = "รหัสผ่าน"
        self.fields["username"].widget.attrs["placeholder"] = "ชื่อผู้ใช้ของคุณ"


class ThaiPasswordResetForm(BootstrapFormMixin, PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "อีเมลที่ใช้สมัคร"
        self.fields["email"].widget.attrs["placeholder"] = "you@example.com"


class ThaiSetPasswordForm(BootstrapFormMixin, ThaiPasswordMixin, SetPasswordForm):
    error_messages = ThaiPasswordMixin.error_messages

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "รหัสผ่านใหม่"
        self.fields["new_password1"].help_text = PASSWORD_HINT
        self.fields["new_password2"].label = "ยืนยันรหัสผ่านใหม่"
        self.fields["new_password2"].help_text = "พิมพ์รหัสผ่านใหม่อีกครั้งให้ตรงกัน"


class ThaiPasswordChangeForm(BootstrapFormMixin, ThaiPasswordMixin, PasswordChangeForm):
    error_messages = {
        **ThaiPasswordMixin.error_messages,
        "password_incorrect": "รหัสผ่านปัจจุบันไม่ถูกต้อง",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "รหัสผ่านปัจจุบัน"
        self.fields["new_password1"].label = "รหัสผ่านใหม่"
        self.fields["new_password1"].help_text = PASSWORD_HINT
        self.fields["new_password2"].label = "ยืนยันรหัสผ่านใหม่"
        self.fields["new_password2"].help_text = "พิมพ์รหัสผ่านใหม่อีกครั้งให้ตรงกัน"
