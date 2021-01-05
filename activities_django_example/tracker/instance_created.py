from server.apps.activity.tracker.base import BaseActivityInstanceCreated


class ActivityInstanceCreated(BaseActivityInstanceCreated):
    """Basic activity for creating instance."""

    def handle(self) -> None:
        """Basic created handle implementation."""

        self.write(
            activity_type=self.action_type,
            actor=getattr(self.instance, "created_by", None),
            target=self.instance,
            data={},
        )
