from django import template

from ..services import build_display

register = template.Library()


@register.inclusion_tag("profiles/_profile_card.html")
def profile_card(user, profile=None):
    """
    Drop-in block for any portfolio template:

        {% load profile_tags %}
        {% profile_card request.user %}              {# the user's default profile #}
        {% profile_card request.user some_profile %} {# a specific one #}

    Safe when the profile is missing or partly filled in.
    """
    return {"display": build_display(user, profile)}
