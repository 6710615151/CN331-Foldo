"""
Rule: a signed-in user can only see, edit or delete rows they own.
Every class-based view that shows private data uses OwnerRequiredMixin
instead of writing its own ownership check.
"""

from django.contrib.auth.mixins import LoginRequiredMixin


class OwnerRequiredMixin(LoginRequiredMixin):
    
    owner_field = "user"

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(**{self.owner_field: self.request.user.pk})

ADD_ANOTHER = "add_another"


class AddAnotherMixin:
    """Create pages: a second submit button (name="add_another") saves and
    returns to an empty form, so entering several rows needs no extra clicks.

    It only changes where a *successful* save goes; validation, saving and
    messages stay in the view. Put it first in the bases; set
    ``add_another_url_name`` to a route that takes the profile's pk.
    """

    add_another_url_name = ""

    def post(self, request, *args, **kwargs):
        from django.http import HttpResponseRedirect
        from django.urls import reverse

        response = super().post(request, *args, **kwargs)
        if ADD_ANOTHER in request.POST and response.status_code == 302:
            return HttpResponseRedirect(reverse(self.add_another_url_name, args=[self.profile.pk]))
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_add_another"] = True
        return context
