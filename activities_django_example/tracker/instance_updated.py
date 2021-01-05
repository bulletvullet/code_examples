from server.apps.activity.tracker.base import BaseActivityInstanceUpdated


class ActivityInstanceUpdated(BaseActivityInstanceUpdated):
    """Basic activity for updating instance fields."""

    subscribed_fields = ("name", "description")

    def handle(self) -> None:
        """Basic handle for logging updated fields."""

        for field_name, old_val in self.instance.tracker.changed().items():
            if field_name in self.subscribed_fields:
                new_val = getattr(self.instance, field_name)
                self.write(
                    activity_type=self.action_type,
                    actor=getattr(self.instance, "updated_by", None),
                    target=self.instance,
                    data={"changes": {field_name: {"from": old_val, "to": new_val}}},
                )
                break
