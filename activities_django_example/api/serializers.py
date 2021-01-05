from rest_framework import serializers
from rest_framework.fields import JSONField

from server.apps.activity.models import ActivityLog
from server.apps.users.api.serializers import UserSerializer


class ActivitySerializer(serializers.ModelSerializer):  # noqa: D101
    actor = UserSerializer()
    target = JSONField(source="target.rendered_json", default=None)

    class Meta:
        model = ActivityLog
        fields = ("id", "actor", "target", "activity_type", "data", "created_at")
