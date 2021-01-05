from server.apps.activity.tracker.instance_updated import ActivityInstanceUpdated
from server.apps.activity.tracker.subscriber import SubscribeInstanceActivity
from server.apps.main import models

# Register project activity tracker
project_activity = SubscribeInstanceActivity(models.Project)
project_activity.connect(ActivityInstanceUpdated)

# Register sprint activity tracker
sprint_activity = SubscribeInstanceActivity(models.Sprint)
sprint_activity.connect(ActivityInstanceUpdated)

# Register epic activity tracker
epic_activity = SubscribeInstanceActivity(models.Epic)
epic_activity.connect(ActivityInstanceUpdated)

# Register task activity tracker
task_activity = SubscribeInstanceActivity(models.Task)
task_activity.connect(ActivityInstanceUpdated)

# Register subtask activity tracker
subtask_activity = SubscribeInstanceActivity(models.SubTask)
subtask_activity.connect()

subscribed_activity_models = (
    project_activity,
    sprint_activity,
    epic_activity,
    task_activity,
    subtask_activity,
)
