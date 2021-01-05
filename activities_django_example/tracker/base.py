from abc import ABC, abstractmethod

from server.apps.activity.models import ActivityLog
from server.apps.notifications.activity import ObjectCreatedNotification, ObjectChangedNotification


class BaseActivity(ABC):
    """Base instance activity class."""

    notification_class = None

    def __init__(self, instance, created, signal_type):
        """Init with needed objects."""

        self.instance = instance
        self.created = created
        self.signal_type = signal_type

    def process(self):
        """Run validations, and start processing."""

        # validate processing
        if self.is_acceptable():
            # handle data and write log
            self.handle()

    @classmethod
    def write(cls, activity_type, actor, target, data):
        """Base write activity log implementation."""

        activity_log = ActivityLog.objects.create(
            activity_type=activity_type, actor=actor, target=target, data=data
        )
        cls.notify(activity_log)

    @abstractmethod
    def handle(self):
        """Prepare necessary data and write activity log."""

    @property
    @abstractmethod
    def action_type(self):
        """Relation to ActivityLog.Types attribute."""

    @abstractmethod
    def is_acceptable(self):
        """Needed validations before process will start."""

    @classmethod
    def notify(cls, obj):
        """Notify."""
        if cls.notification_class:
            cls.notification_class.send_notifications(obj)


class BaseActivityInstanceCreated(BaseActivity, ABC):
    """Basic implementation for created instances."""

    action_type = ActivityLog.Types.OBJECT_CREATED
    notification_class = ObjectCreatedNotification

    def is_acceptable(self):
        """Check if instance was created."""
        return self.created


class BaseActivityInstanceUpdated(BaseActivity, ABC):
    """Basic activity for updating instances."""

    action_type = ActivityLog.Types.OBJECT_CHANGED
    target_signal_type = "post_save"
    notification_class = ObjectChangedNotification

    def is_acceptable(self):
        """Check if instance was not created."""

        return not self.created and self.signal_type == self.target_signal_type


class BaseActivityInstanceDeleted(BaseActivity, ABC):
    """Basic activity for deleting instances."""

    action_type = ActivityLog.Types.OBJECT_DELETED
    target_signal_type = "post_delete"

    def is_acceptable(self):
        """Check if target signal is post_deleted."""

        return self.signal_type == self.target_signal_type
