from django.contrib import admin

from .models import MainProfile

from .models import Project  

@admin.register(MainProfile)
class MainProfileAdmin(admin.ModelAdmin):
    list_display = ("label", "full_name", "owner", "is_default", "updated_at")
    list_filter = ("is_default",)
    search_fields = ("label", "full_name", "owner__username", "owner__email", "contact_email")
    readonly_fields = ("created_at", "updated_at")

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("project_name", "profile", "start_date", "end_date", "updated_at")
    search_fields = ("project_name", "profile__full_name", "profile__owner__username")
    readonly_fields = ("created_at", "updated_at")