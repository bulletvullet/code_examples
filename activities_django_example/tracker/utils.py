from django.db.models import Model

from server.apps.activity.tracker.connector import subscribed_activity_models


def process_subscribed_activities(instance: Model, created: bool, signal_type: str):
    """Process signals for subscribed models for activity logs."""

    for subscription in subscribed_activity_models:
        subscription.run(instance=instance, created=created, signal_type=signal_type)
