from collections import Iterable
from typing import List, Type, Union

from django.db.models import Model

from server.apps.activity.tracker.base import BaseActivity
from server.apps.activity.tracker.instance_created import ActivityInstanceCreated


class SubscribeInstanceActivity:
    """Subscribes needed activities to model."""

    _base_activities = [ActivityInstanceCreated]

    def __init__(self, instance_model):
        """Set instance model."""
        self._activities = []
        self.instance_model = instance_model

    def connect(self, activities: Union[List[Type[BaseActivity]], Type[BaseActivity]] = None):  # noqa: TAE002, E501
        """Connect activity."""
        self._activities.extend(self._base_activities)

        if not activities:
            return

        # convert to list if not
        if not isinstance(activities, Iterable):
            activities = [activities]

        # connect activities
        for activity in activities:
            if activity not in self._activities:
                self._activities.append(activity)

    def check_instance(self, instance):
        """Check instance is the instance of instance_model."""

        return isinstance(instance, self.instance_model)

    def run(self, instance: Model, created: bool, signal_type: str):
        """Run processing all of subscribed activities."""

        if not self.check_instance(instance):
            return

        for activity in self._activities:
            activity(instance=instance, created=created, signal_type=signal_type).process()
