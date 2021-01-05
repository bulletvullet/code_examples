from rest_framework import mixins, viewsets

from server.apps.activity.api.serializers import ActivitySerializer
from server.apps.activity.models import ActivityLog


class ActivityViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):  # noqa: D101
    queryset = ActivityLog.objects.select_related("actor").prefetch_related("target")
    serializer_class = ActivitySerializer
    filterset_fields = ("activity_type", "actor")
