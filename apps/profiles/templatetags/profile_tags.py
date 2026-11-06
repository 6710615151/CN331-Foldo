from django import template

from ..services import build_display

register = template.Library()


@register.inclusion_tag("profiles/_profile_card.html")
def profile_card(user):
    """
    Drop-in block for any portfolio template:

        {% load profile_tags %}
        {% profile_card request.user %}

    Safe when the profile is missing or partly filled in.
    """
    return {"display": build_display(user)}


@register.filter
def add_class(bound_field, css):
    """Render a form field with extra CSS classes, keeping any the widget already has.

        {{ field|add_class:"form-control" }}
    """
    existing = bound_field.field.widget.attrs.get("class", "")
    return bound_field.as_widget(attrs={"class": f"{existing} {css}".strip()})
