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
