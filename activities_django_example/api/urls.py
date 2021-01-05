from server.apps.activity.api.views import ActivityViewSet


def register_urls(router, urls):
    router.register("activity_log", ActivityViewSet)
