"""Serializers for event app"""

from django.contrib.auth import get_user_model
from django.utils import timezone
from drf_yasg.utils import swagger_serializer_method
from rest_framework import serializers

from campaigns.models import Campaign
from events.models import (Attendance, Event, EventCategory,
                           EventCategoryImage, EventComment, EventImage,
                           EventInvite, EventLike, Reminder)
from prism.utils.cache_utils import get_count_of
from prism.utils.doc_utils import EventCountersSwaggerSerializer
from prism.utils.drf_utils import check_if_request
from system.timezones import TIMEZONES
from users.api.serializers import UserPreviewSerializer

TIMEZONES_CHOICES = [(tz, tz) for tz in TIMEZONES]

User = get_user_model()


class EventImageSerializer(serializers.HyperlinkedModelSerializer):
    """EventImageSerializer class"""
    class Meta:
        """EventImageSerializer metaclass"""
        model = EventImage
        fields = ('id', 'image', 'position')


class ReminderSerializer(serializers.ModelSerializer):
    """Reminder serializer"""

    class Meta:
        model = Reminder
        fields = ('offset', )


class AttendancePreviewSerializer(serializers.ModelSerializer):
    user = UserPreviewSerializer(read_only=True)

    class Meta:
        model = Attendance
        fields = ('user', 'status')
        read_only_fields = fields


class EventViewerAttendanceStatusSerializerMixin(serializers.Serializer):
    viewer_attendance_status = serializers.SerializerMethodField()

    def get_viewer_attendance_status(self, obj) -> int:
        try:
            return Attendance.objects.get(event=obj, user=self.context['request'].user).status
        except Attendance.DoesNotExist:
            pass


class EventLikedByViewerSerializerMixin(serializers.Serializer):
    liked_by_viewer = serializers.SerializerMethodField()

    @check_if_request
    def get_liked_by_viewer(self, obj) -> bool:
        """Check if viewer liked this event"""
        try:
            return obj.likes.filter(user_id=self.context["request"].user.id).exists()
        except EventLike.DoesNotExist:
            return False


class EventPreviewSerializer(serializers.ModelSerializer):
    """Slim Event serializer class. Read only."""
    start_timezone = serializers.ChoiceField(choices=TIMEZONES_CHOICES)
    end_timezone = serializers.ChoiceField(choices=TIMEZONES_CHOICES)

    class Meta:
        """EventSearchSerializer metaclass"""
        model = Event
        fields = ('id', 'title', 'category', 'category_image',
                  'start', 'start_timezone', 'end', 'end_timezone', 'created',
                  'main_image', 'main_image_cropped')
        read_only_fields = fields


class EventPreviewWithUserSerializer(EventPreviewSerializer):
    """EventPreviewSerializer, but with user. Read only."""
    user = UserPreviewSerializer(read_only=True)

    class Meta:
        """EventSerializer metaclass"""
        model = Event
        fields = ('id', 'user', 'title', 'category', 'category_image',
                  'start', 'start_timezone', 'end', 'end_timezone', 'created',
                  'main_image', 'main_image_cropped')
        read_only_fields = fields


class EventDetailSerializer(EventViewerAttendanceStatusSerializerMixin,
                            EventLikedByViewerSerializerMixin,
                            EventPreviewWithUserSerializer):
    """
    Most complete Event serializer.
    Used for both detailed event representation and event creation/updates.
    """
    is_private = serializers.BooleanField(required=True)
    images = EventImageSerializer(many=True, required=False)
    viewer_reminder = serializers.SerializerMethodField(read_only=True)
    viewer_inviter = serializers.SerializerMethodField()
    counters = serializers.SerializerMethodField()

    attendance_preview = serializers.SerializerMethodField()
    ATTENDANCE_PREVIEW_MAX_COUNT = 8

    class Meta:
        """EventSerializer metaclass"""
        model = Event
        fields = ('id', 'user', 'title', 'description', 'category', 'category_image',
                  'is_private', 'allow_guests_to_invite',
                  'start', 'start_timezone', 'end', 'end_timezone', 'created',
                  'main_image', 'main_image_cropped', 'main_image_crop_points', 'images',
                  'location', 'latitude', 'longitude',
                  'is_online', 'website',
                  'viewer_reminder', 'viewer_inviter',
                  'viewer_attendance_status', 'liked_by_viewer',
                  'counters', 'attendance_preview')
        read_only_fields = ('main_image', 'main_image_cropped', 'images')

    def validate_end(self, end):
        if self.instance and end < self.instance.end:
            now = timezone.now()
            if Campaign.objects.filter(event=self.instance, end__gte=now, is_active=True).exists():
                raise serializers.ValidationError('Found a conflict with an active promo campaign.')
        return end

    def validate_category(self, category):
        if not category.is_active:
            raise serializers.ValidationError('Please provide an active category')
        return category

    def validate_category_image(self, category_image):
        if not category_image.is_active:
            raise serializers.ValidationError('Please provide an active category image')
        return category_image

    def validate(self, data):
        """Validate datetime"""
        start = data.get('start') or getattr(self.instance, 'start')
        end = data.get('end') or getattr(self.instance, 'end')
        if start > end:
            raise serializers.ValidationError('Event must end after it starts')

        location_field_names = ('location', 'latitude', 'longitude')
        location_field_values = [data.get(f) is not None for f in location_field_names]
        if any(location_field_values) and not all(location_field_values):
            raise serializers.ValidationError(
                f'You must specify all of {location_field_names} if you specify any of {location_field_names}')

        if not data.get('allow_guests_to_invite', getattr(self.instance, 'allow_guests_to_invite', True)):
            if not data.get('is_private', getattr(self.instance, 'is_private', None)):
                raise serializers.ValidationError({'allow_guests_to_invite': 'This field can not be False if the event is not private'})

        category = data.get('category', getattr(self.instance, 'category', None))
        category_image = data.get('category_image')
        if category_image:
            if category is None:
                raise serializers.ValidationError({'category_image': 'Select category first'})
            elif not category.images.filter(pk=category_image.id).exists():
                raise serializers.ValidationError({'category_image': 'Category image must be related to the selected category'})

        return data

    @swagger_serializer_method(serializer_or_field=ReminderSerializer)
    @check_if_request
    def get_viewer_reminder(self, obj) -> dict:
        try:
            return ReminderSerializer(
                Reminder.objects.get(event=obj, user=self.context['request'].user)
            ).data
        except Reminder.DoesNotExist:
            pass

    @swagger_serializer_method(serializer_or_field=UserPreviewSerializer)
    @check_if_request
    def get_viewer_inviter(self, obj):
        try:
            return UserPreviewSerializer(
                EventInvite.objects.get(event=obj, invitee=self.context['request'].user).inviter
            ).data
        except EventInvite.DoesNotExist:
            pass

    @check_if_request
    @swagger_serializer_method(AttendancePreviewSerializer)
    def get_attendance_preview(self, obj):
        """
        Return a few attendees for preview, sorted by status, viewer's friends first
        This makes a request to find all friends who attend and then another one if we got <5 friends
        You'd think you can do this with annotations, but you can't
        """
        user = self.context['request'].user
        base_att = Attendance.objects.select_related('user', 'event').filter(event=obj).order_by('status')
        att_max = self.ATTENDANCE_PREVIEW_MAX_COUNT
        res_att = list(base_att.filter(user__in=user.friends)[:att_max])
        if len(res_att) < att_max:
            n = att_max - len(res_att)
            res_att += list(base_att.exclude(user__in=user.friends)[:n])
        return AttendancePreviewSerializer(res_att, many=True, context=self.context).data

    @swagger_serializer_method(serializer_or_field=EventCountersSwaggerSerializer)
    @check_if_request
    def get_counters(self, obj: Event) -> dict:
        data = {x: get_count_of(obj, x) for x in Attendance.CACHE_STATUS_KEYS}
        data.update({
            EventLike.CACHE_KEY: get_count_of(obj, EventLike.CACHE_KEY),
            EventComment.CACHE_KEY: get_count_of(obj, EventComment.CACHE_KEY),
            'viewer_attending_friends_count': get_count_of(
                obj, 'user_attending_friends', method_kwargs={'user': self.context['request'].user}),
        })
        return data


class AttendanceSerializer(AttendancePreviewSerializer):
    """Attendance serializer with user. Read only."""
    viewer_can_uninvite = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = ('user', 'status', 'viewer_can_uninvite')
        read_only_fields = fields

    @check_if_request
    def get_viewer_can_uninvite(self, obj) -> bool:
        user = self.context['request'].user
        if obj.status == Attendance.INVITE_PENDING:
            invite = getattr(obj, 'invite', None)
            if invite:
                return user.id == obj.event.user_id or invite.inviter_id == user.id
        return False


class UserAttendanceSerializer(serializers.ModelSerializer):
    """
    Attendance serializer based on the User model
    Use for when you need both attendees and non-attendees of an event
    You have to provide a bunch of additional stuff though
    Read only
    """
    user = UserPreviewSerializer(read_only=True, source='*')
    status = serializers.SerializerMethodField()
    viewer_can_uninvite = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('user', 'status', 'viewer_can_uninvite')
        read_only_fields = fields

    @swagger_serializer_method(serializer_or_field=serializers.ChoiceField(choices=Attendance.STATUS_CHOICES))
    def get_status(self, obj) -> int:
        statuses_map = self.context.get('statuses_map')
        return statuses_map.get(obj.id)

    @check_if_request
    def get_viewer_can_uninvite(self, obj) -> bool:
        viewer = self.context['request'].user
        event = self.context.get('event')
        statuses_map = self.context.get('statuses_map')
        invited_by_viewer_map = self.context.get('invited_by_viewer_map')

        status = statuses_map.get(obj.id)
        if status:
            if status == Attendance.INVITE_PENDING:
                return viewer == event.user or invited_by_viewer_map.get(obj.id, False)
            return False


class IncomingEventInviteSerializer(serializers.ModelSerializer):
    """Incoming invite to event serializer (for viewing logged in user's invites). Read-only."""
    event = EventPreviewWithUserSerializer(read_only=True)
    inviter = UserPreviewSerializer(read_only=True)
    invitee_status = serializers.ReadOnlyField(source='invitee_attendance.status')

    class Meta:
        model = EventInvite
        fields = ('event', 'inviter', 'invitee_status', 'created')
        read_only_fields = fields


class EventCategoryImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventCategoryImage
        fields = ('id', 'image', 'cropped_image', 'is_active')
        read_only_fields = fields


class EventCategorySerializer(serializers.ModelSerializer):
    images = EventCategoryImageSerializer(many=True)

    class Meta:
        model = EventCategory
        fields = ('id', 'name', 'images', 'badge_color', 'icon', 'is_interest', 'is_active')
        read_only_fields = fields


class EventNotificationWithLikesSerializer(serializers.ModelSerializer):
    counters = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = ('id', 'title', 'category', 'category_image', 'start', 'start_timezone', 'main_image', 'counters')
        read_only_fields = fields

    @staticmethod
    @swagger_serializer_method(serializer_or_field=EventCountersSwaggerSerializer)
    def get_counters(obj: Event) -> dict:
        return {EventLike.CACHE_KEY: get_count_of(obj, EventLike.CACHE_KEY)}


class EventNotificationWithAttendanceStatusSerializer(EventViewerAttendanceStatusSerializerMixin,
                                                      serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ('id', 'title', 'category', 'category_image', 'start', 'start_timezone', 'main_image', 'viewer_attendance_status')
        read_only_fields = fields


class EventNotificationWithAttendanceStatusAndUserSerializer(EventViewerAttendanceStatusSerializerMixin,
                                                             EventPreviewWithUserSerializer,
                                                             serializers.ModelSerializer):
    class Meta:

        model = Event
        fields = ('id', 'title', 'category', 'category_image', 'start', 'start_timezone', 'main_image', 'user', 'viewer_attendance_status')
        read_only_fields = fields


class SwaggerEventNotificationSerializer(EventNotificationWithLikesSerializer,
                                         EventNotificationWithAttendanceStatusSerializer):

    class Meta:
        model = Event
        fields = ('id', 'title', 'category', 'category_image', 'start', 'start_timezone', 'main_image', 'counters', 'viewer_attendance_status')
        read_only_fields = fields


class EventCommentSerializer(serializers.ModelSerializer):
    user = UserPreviewSerializer(read_only=True)
    user_status = serializers.SerializerMethodField()

    class Meta:
        model = EventComment
        fields = ('id', 'user', 'user_status', 'body', 'created')

    @check_if_request
    @swagger_serializer_method(serializer_or_field=serializers.ChoiceField(choices=Attendance.STATUS_CHOICES))
    def get_user_status(self, obj) -> int:
        statuses_map = self.context.get('statuses_map')
        if statuses_map is not None:
            # For list
            return statuses_map.get(obj.user_id)
        else:
            # For create, update, etc.
            try:
                return Attendance.objects.get(event=obj.event, user=obj.user).status
            except Attendance.DoesNotExist:
                pass


class EventFeedSerializer(EventViewerAttendanceStatusSerializerMixin,
                          EventLikedByViewerSerializerMixin,
                          EventPreviewWithUserSerializer):
    """Feed-specific Event serializer. Read only."""
    comments_preview = serializers.SerializerMethodField()
    counters = serializers.SerializerMethodField()
    images = EventImageSerializer(many=True)

    class Meta:
        model = Event
        fields = ('id', 'user', 'title', 'description', 'category', 'category_image',
                  'start', 'start_timezone', 'end', 'end_timezone', 'created',
                  'images',
                  'viewer_attendance_status', 'liked_by_viewer', 'counters', 'comments_preview')
        read_only_fields = fields

    def get_comments_preview(self, obj):
        qs = obj.comments.select_related('user').order_by('-id')[:2]
        statuses_map = dict(
            Attendance.objects.filter(
                event=obj, user__in=[c.user for c in qs]).values_list('user_id', 'status')
        )
        serializer_context = self.context.copy()
        serializer_context.update({'statuses_map': statuses_map})
        return EventCommentSerializer(qs, many=True, context=serializer_context).data

    @swagger_serializer_method(serializer_or_field=EventCountersSwaggerSerializer)
    @check_if_request
    def get_counters(self, obj: Event) -> dict:
        return {
            EventLike.CACHE_KEY: get_count_of(obj, EventLike.CACHE_KEY),
            EventComment.CACHE_KEY: get_count_of(obj, EventComment.CACHE_KEY),
            'viewer_attending_friends_count': get_count_of(
                obj, 'user_attending_friends', method_kwargs={'user': self.context['request'].user})
        }


class TaggedEventSerialzier(EventViewerAttendanceStatusSerializerMixin,
                            EventPreviewSerializer):
    """Related event data to display in posts and stories"""
    counters = serializers.SerializerMethodField()

    class Meta:
        """TaggedEventSerialzier metaclass"""
        model = Event
        fields = ('id', 'title', 'category',
                  'start', 'start_timezone', 'end', 'end_timezone',
                  'viewer_attendance_status', 'counters')
        read_only_fields = fields

    @check_if_request
    @swagger_serializer_method(EventCountersSwaggerSerializer)
    def get_counters(self, obj: Event) -> dict:
        return {
            'viewer_attending_friends_count': get_count_of(
                obj, 'user_attending_friends', method_kwargs={'user': self.context['request'].user})
        }


class EventDiscoveryPreviewSerializer(serializers.ModelSerializer):
    event = EventPreviewSerializer(source='*', read_only=True)

    class Meta:
        model = Event
        fields = ('event',)
