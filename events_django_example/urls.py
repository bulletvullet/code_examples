from django.conf import settings
from django.urls import include, path
from django.views.decorators.cache import cache_page
from rest_framework_extensions.routers import ExtendedSimpleRouter

from campaigns.api.viewsets import EventCampaignViewSet
from events.api.views import DiscoveryView, EventCategoryView, PromotedView
from events.api.viewsets import (AttendanceViewSet, EventCommentsViewSet,
                                 EventImageViewSet, EventPostsViewSet,
                                 EventViewSet, InviteUsersViewSet,
                                 ReminderViewSet)

router = ExtendedSimpleRouter()
router.register(r'events', EventViewSet, basename='event')\
    .register(r'images', EventImageViewSet, basename='event-image', parents_query_lookups=['event_id'])
router.register(r'events', EventViewSet, basename='event')\
    .register(r'attendance', AttendanceViewSet, basename='event-attendance', parents_query_lookups=['event_id'])
router.register(r'events', EventViewSet, basename='event')\
    .register(r'reminder', ReminderViewSet, basename='event-reminder', parents_query_lookups=['event_id'])
router.register(r'events', EventViewSet, basename='event')\
    .register(r'invite_users', InviteUsersViewSet, basename='event-invite-users', parents_query_lookups=['event_id'])
router.register(r'events', EventViewSet, basename='event')\
    .register(r'comments', EventCommentsViewSet, basename='event-comment', parents_query_lookups=['event_id'])
router.register(r'events', EventViewSet, basename='event')\
    .register(r'posts', EventPostsViewSet, basename='event-post', parents_query_lookups=['event_id'])
router.register(r'events', EventViewSet, basename='event')\
    .register(r'campaigns', EventCampaignViewSet, basename='event-campaigns', parents_query_lookups=['event_id'])


urlpatterns = [
    path('discovery/promoted/', PromotedView.as_view(), name='discovery-promoted'),
    path('discovery/', DiscoveryView.as_view(), name='discovery'),
    path('event_categories/', cache_page(settings.CACHE_TIMEOUTS['5_minutes'])(EventCategoryView.as_view()), name='event_categories'),
    path('', include(router.urls)),
]
