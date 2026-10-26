"""
Validation layer for the ``core`` app.

The shared shell has no forms; domain forms live in each app's ``forms.py``.
"""

# ---------------------------------------------------------------------------
# FOLDO-10: shared form styling and error display
# ---------------------------------------------------------------------------

from django import forms  # noqa: E402


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
        # After validation: red border + screen-reader flag on every bad field.
        for name in self.errors:
            if name in self.fields:
                widget = self.fields[name].widget
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()
                widget.attrs["aria-invalid"] = "true"