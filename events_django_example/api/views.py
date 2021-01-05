
from functools import reduce
from operator import and_, or_

from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.pagination import LimitOffsetPagination

from campaigns.api.serializers import CampaignEventSerializer
from campaigns.models import Campaign
from events.api.filters import (CategoriesCampaignsFilterSet,
                                CategoriesFilterSet)
from events.api.serializers import (EventCategorySerializer,
                                    EventDiscoveryPreviewSerializer)
from events.models import Event, EventCategory


class EventCategoryView(generics.ListAPIView):
    """Get all active event categories"""
    serializer_class = EventCategorySerializer
    queryset = EventCategory.objects.filter()


class DiscoveryView(generics.ListAPIView):
    """Get discovery based on regular events"""
    serializer_class = EventDiscoveryPreviewSerializer
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, )
    filter_class = CategoriesFilterSet

    def get_queryset(self):
        now = timezone.now()
        return Event.objects.filter(
            Q(is_private=False) & Q(end__gte=now) & (
                Q(campaigns__isnull=True) | (
                    Q(campaigns__is_active=False) | Q(campaigns__end__lte=now) | Q(campaigns__start__gt=now)
                )
            ) & ~Q(user_id=self.request.user.id)
        ).distinct()


class PromotedView(generics.ListAPIView):
    """Get promoted events"""
    serializer_class = CampaignEventSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_class = CategoriesCampaignsFilterSet
    pagination_class = LimitOffsetPagination

    def get_queryset(self):
        user = self.request.user
        now = timezone.now()
        # Event and campaign should ends after now, campaign start should be before now
        qs = Campaign.objects.filter(Q(event__is_private=False) & Q(start__lte=now) & Q(end__gte=now) & Q(is_active=True))
        # Add AND filter for any of audiences with "null" criteries
        a_q = (
            Q(audiences__isnull=True),
            Q(audiences__age_min__isnull=True), Q(audiences__age_max__isnull=True),
            Q(audiences__language__isnull=True), Q(audiences__gender__isnull=True))
        query = reduce(or_, (x for x in a_q))
        u_q = []
        if user.birth_date:
            age = user.calculate_age(now)
            u_q.append(Q(audiences__age_min__lte=age))
            u_q.append(Q(audiences__age_max__gte=age))
        if user.language:
            u_q.append(Q(audiences__language=user.language))
        if user.gender:
            u_q.append(Q(audiences__gender=user.gender))
        # Generate all users Q with AND statement
        user_query = reduce(and_, (x for x in u_q))
        # Add users Q with OR statement to audience main query
        query.add(user_query, Q.OR)
        return qs.filter(query).distinct()
