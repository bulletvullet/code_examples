from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import JSONField
from django.db import models


class ActivityLog(models.Model):
    """Activity log model."""

    class Types(models.TextChoices):  # noqa: WPS431
        OBJECT_CREATED = "object_created", "Object created"
        OBJECT_CHANGED = "object_changed", "Object changed"
        OBJECT_DELETED = "object_deleted", "Object deleted"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )

    target_id = models.PositiveIntegerField()
    target_ct = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        limit_choices_to={"model__in": ("Task", "Subtask", "Epic", "Sprint", "Project")},
    )
    target = GenericForeignKey("target_ct", "target_id")

    data = JSONField(default=dict, blank=True)

    activity_type = models.CharField(max_length=30, choices=Types.choices)
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "ActivityLogs"
