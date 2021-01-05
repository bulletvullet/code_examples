import dateutil.parser
import pytz
from django_filters import NumberFilter
from django_filters.rest_framework import FilterSet
from django_filters.rest_framework.filters import BaseInFilter, ChoiceFilter
from drf_yasg import openapi
from rest_framework import filters
from rest_framework.exceptions import ValidationError

from campaigns.models import Campaign
from events.models import Attendance, Event


class ChoiceInFilter(BaseInFilter, ChoiceFilter):
    pass


class NumberInFilter(BaseInFilter, NumberFilter):
    pass


class EventDateTimeFilter(filters.BaseFilterBackend):
    """
    Filter event by datetime

    Filtering by datetime must catch following cases:
    Event 1                                        |------------|
    Event 2                             |------|
    Event 3            |------------|
    Event 4    |----------------------------------------------------------
    Event 5                                |------------------------------
    Range                      [________________________]
    Time    ==============================================================>
    """
    STARTS_BEFORE = 'starts_before'
    STARTS_AFTER = 'starts_after'
    ENDS_BEFORE = 'ends_before'
    ENDS_AFTER = 'ends_after'

    MAP_TO_LOOKUP = {
        STARTS_BEFORE: 'start__lte',
        STARTS_AFTER: 'start__gte',
        ENDS_BEFORE: 'end__lte',
        ENDS_AFTER: 'end__gte',
    }

    FILTER_KWARGS = [STARTS_BEFORE, STARTS_AFTER, ENDS_BEFORE, ENDS_AFTER]

    SWAGGER_PARAMS = [
        openapi.Parameter(
            kw, openapi.IN_QUERY, type=openapi.TYPE_STRING, description=(
                "Datetime in ISO format with optional UTC offset. "
                "E.g. '2020-01-01 20:30+02:00' or '2020-01-01 20:30'. "
                "If UTC offset is absent - we consider the datetime to be in UTC."
            )
        )
        for kw in FILTER_KWARGS
    ]

    def filter_queryset(self, request, qs, view):
        f = {}

        for kw in self.FILTER_KWARGS:
            kw_str = request.query_params.get(kw)
            if kw_str:
                try:
                    kw_val = dateutil.parser.isoparse(kw_str)
                except ValueError:
                    raise ValidationError({'invalid': f'Enter a valid ISO-formatted datetime ({kw}).'})
                kw_val = kw_val.astimezone(pytz.utc) if kw_val.tzinfo else pytz.timezone('UTC').localize(kw_val)
                f[self.MAP_TO_LOOKUP[kw]] = kw_val

        qs = qs.filter(**f)
        return qs


class AttendanceUserRelationFilter(filters.BaseFilterBackend):
    RELATION = 'relation'

    FOLLOWERS = 'followers'
    FOLLOWS = 'follows'
    FRIENDS = 'friends'

    EXCLUDE_PREFIX = '-'

    RELATION_CHOICES = (FOLLOWERS, FOLLOWS, FRIENDS)

    MAP_TO_USER_FIELDS = {
        FOLLOWERS: 'followers',
        FOLLOWS: 'follows',
        FRIENDS: 'friends',
    }

    SWAGGER_PARAMS = [
        openapi.Parameter(
            RELATION, openapi.IN_QUERY, type=openapi.TYPE_STRING, enum=RELATION_CHOICES, description=(
                f'Choice of relation to the current user. Add "{EXCLUDE_PREFIX}" as prefix to exclude.'
            )
        )
    ]

    def filter_queryset(self, request, qs, view):
        relation = request.query_params.get(self.RELATION, '')
        if not relation:
            return qs
        exclude = False
        if relation[0] == self.EXCLUDE_PREFIX:
            exclude = True
            relation = relation[1:]
        if relation in self.RELATION_CHOICES:
            user = request.user
            relation_qs = getattr(user, self.MAP_TO_USER_FIELDS[relation], None)
            if relation_qs is not None:
                if exclude:
                    qs = qs.exclude(user__in=relation_qs.all())
                else:
                    qs = qs.filter(user__in=relation_qs.all())
        else:
            raise ValidationError({'invalid_choice': f'Select a valid choice from {self.RELATION_CHOICES}. {relation} is not one of the available choices.'})

        return qs


class AttendanceFilterSet(FilterSet):
    status = ChoiceInFilter(field_name='status', lookup_expr='in', choices=Attendance.STATUS_CHOICES)

    class Meta:
        model = Attendance
        fields = ['status']


class NestedUserAttendanceInEventFilter(filters.BaseFilterBackend):
    ATTENDEES = 'attendees'

    ONLY = 'only'
    EXCLUDE = 'exclude'

    ATTENDEES_CHOICES = (ONLY, EXCLUDE)

    SWAGGER_PARAMS = [
        openapi.Parameter(
            ATTENDEES, openapi.IN_QUERY, type=openapi.TYPE_STRING, enum=ATTENDEES_CHOICES, description=(
                'Choice of attendance filtering for users.'
            )
        )
    ]

    def filter_queryset(self, request, qs, view):
        event = view.get_parent_object()
        attendees = request.query_params.get('attendees', '')
        if not event or not attendees:
            return qs

        if attendees in self.ATTENDEES_CHOICES:
            if attendees == self.EXCLUDE:
                qs = qs.exclude(attendance__event=event)
            elif attendees == self.ONLY:
                qs = qs.filter(attendance__event=event)
        else:
            raise ValidationError({'invalid_choice': f'Select a valid choice from {self.ATTENDEES_CHOICES}. {attendees} is not one of the available choices.'})

        return qs


class CategoriesFilterSet(FilterSet):
    category = NumberInFilter(field_name='category__id', lookup_expr='in')

    class Meta:
        model = Event
        fields = ['category__id']


class CategoriesCampaignsFilterSet(FilterSet):
    category = NumberInFilter(field_name='event__category__id', lookup_expr='in')

    class Meta:
        model = Campaign
        fields = ['event__category__id']
