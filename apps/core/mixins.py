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