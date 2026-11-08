"""
Validation layer for the ``core`` app.

The shared shell has no forms; domain forms live in each app's ``forms.py``.
"""

# ---------------------------------------------------------------------------
# FOLDO-10: shared form styling and error display
# ---------------------------------------------------------------------------

from django import forms  # noqa: E402


THAI_ERRORS = {
    "required": "ต้องกรอกช่องนี้",
    "max_length": "ยาวเกิน %(limit_value)d ตัวอักษร (ตอนนี้ %(show_value)d)",
    "min_length": "สั้นเกินไป ต้องมีอย่างน้อย %(limit_value)d ตัวอักษร",
    "invalid_choice": "ตัวเลือกนี้ใช้ไม่ได้แล้ว ลองเลือกใหม่",
    "invalid_extension": "ใช้ไฟล์นามสกุล %(allowed_extensions)s เท่านั้น",
    "invalid_image": "ไฟล์นี้ไม่ใช่รูปภาพหรือไฟล์เสีย ลองใช้ไฟล์ JPG หรือ PNG",
    "empty": "ไฟล์นี้ว่างเปล่า ลองเลือกไฟล์ใหม่",
    "missing": "ไม่พบไฟล์ ลองเลือกไฟล์ใหม่",
}

# "invalid" means something different for each kind of field.
THAI_INVALID = (
    (forms.EmailField, "อีเมลไม่ถูกต้อง เช่น name@example.com"),
    (forms.URLField, "ลิงก์ไม่ถูกต้อง เช่น github.com/yourname"),
    (forms.DateField, "วันที่ไม่ถูกต้อง เลือกจากปฏิทินหรือพิมพ์แบบ 2025-08-01"),
    (forms.IntegerField, "ใส่เป็นตัวเลข"),
)


def _thai_errors_for(field) -> dict:
    messages = {code: text for code, text in THAI_ERRORS.items() if code in field.error_messages
                or code in ("max_length", "min_length", "invalid_extension")}
    for kind, text in THAI_INVALID:
        if isinstance(field, kind):
            messages["invalid"] = text
            break
    return messages


def _custom_messages(field) -> dict:
    """Messages the form author passed explicitly (differ from the class defaults)."""
    defaults = {}
    for cls in reversed(type(field).__mro__):
        defaults.update(getattr(cls, "default_error_messages", {}))
    return {code: text for code, text in field.error_messages.items() if defaults.get(code) != text}


class BootstrapFormMixin:
    """Give every field Bootstrap 5 classes and mark fields that have errors.

    Put it left-most on any form, then render with
    ``templates/partials/form_field.html``:

        class EducationForm(BootstrapFormMixin, forms.ModelForm):
            ...
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            # Django's built-in errors are English; the UI is Thai (docs/CONTENT_GUIDE.md).
            # Messages a form sets itself (error_messages=…) still win.
            field.error_messages = {**_thai_errors_for(field), **_custom_messages(field)}
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect)):
                css = "form-check-input"
            elif isinstance(widget, forms.Select):
                css = "form-select"
            else:
                css = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()

    def full_clean(self):
        super().full_clean()
        # The form field and the model field can both reject a value with the same
        # message (e.g. a bad URL); say it once.
        for errors in self._errors.values():
            seen, kept = set(), []
            for error in errors.as_data():
                text = " ".join(error.messages)
                if text not in seen:
                    seen.add(text)
                    kept.append(error)
            errors.data[:] = kept
        # After validation: red border + screen-reader flag on every bad field.
        for name in self.errors:
            if name in self.fields:
                widget = self.fields[name].widget
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()
                widget.attrs["aria-invalid"] = "true"