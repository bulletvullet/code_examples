from django.contrib import admin

from server.apps.activity.models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):  # noqa: D101
    list_display = ("actor", "target", "activity_type", "created_at", "data")
    readonly_fields = ("target", "target_ct")
