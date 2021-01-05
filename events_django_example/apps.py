"""Configuration event app"""
from django.apps import AppConfig


class EventsConfig(AppConfig):
    """Configuration event"""
    name = 'events'

    def ready(self):
        """Mount signals to our event app"""
        import events.signals  # noqa: F401
