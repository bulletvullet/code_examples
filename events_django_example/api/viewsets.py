"""Viewsets for event app"""
from datetime import datetime

import pytz
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import BooleanField, Case, F, Q, When
from django.db.models.functions import Concat
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import no_body, swagger_auto_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import (HTTP_200_OK, HTTP_204_NO_CONTENT,
                                   HTTP_400_BAD_REQUEST)

from events.api.filters import (AttendanceFilterSet,
                                AttendanceUserRelationFilter,
                                EventDateTimeFilter,
                                NestedUserAttendanceInEventFilter)
from events.api.permissions import (IsOwnerOrReadOnly,
                                    RelatedEventObjectPermission,
                                    RelatedEventOwner)
from events.api.serializers import (AttendanceSerializer,
                                    EventCommentSerializer,
                                    EventDetailSerializer,
                                    EventImageSerializer,
                                    EventPreviewSerializer, ReminderSerializer,
                                    UserAttendanceSerializer)
from events.models import (Attendance, Event, EventComment, EventImage,
                           EventInvite, EventLike, Reminder)
from notifications.models import Notification
from notifications.tasks import create_event_change_notification
from posts.api.serializers import PostPreviewSerializer
from posts.models import Post
from prism.utils.drf_utils import ExtendedNestedViewSetMixin
from users.api.filters import UserRelationFilter
from users.api.serializers import IdsListUniqueOrderdSerializer

User = get_user_model()


class ExtendedNestedEventViewSetMixin(ExtendedNestedViewSetMixin):
    parent_object_class = Event
    parent_object_id_kwarg = 'event_id'


@method_decorator(name='list', decorator=swagger_auto_schema(
    manual_parameters=[*EventDateTimeFilter.SWAGGER_PARAMS],
    responses={HTTP_200_OK: EventPreviewSerializer}))
class EventViewSet(viewsets.ModelViewSet):
    """Basic event viewset"""
    queryset = Event.objects.all()
    permission_classes = (IsAuthenticated, IsOwnerOrReadOnly)
    http_method_names = ('get', 'post', 'patch', 'delete')
    pagination_class = LimitOffsetPagination
    filter_backends = (EventDateTimeFilter, SearchFilter, DjangoFilterBackend)
    filterset_fields = ('category',)
    search_fields = ('title',)

    def perform_create(self, serializer):
        """Perform create for current user"""
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.validated_data.get('main_image_crop_points'):
            main_img = self.get_object().images.order_by('position').first()
            if main_img:
                try:
                    crop_points = serializer.validated_data['main_image_crop_points'].split(',')
                    crop_points = [int(i) for i in crop_points]
                    cropped_image = main_img.crop(main_img.image, crop_points)
                    serializer.save(main_image=main_img.image, main_image_cropped=cropped_image)
                except ValueError:
                    raise ValidationError({'main_image_crop_points': ["Invalid crop points."]})
        else:
            serializer.save()
            if any(x in serializer.validated_data for x in Notification.EVENT_CHANGE_FIELDS):
                # send task for updating event in notification service
                # also check if start time was updated for updating all of the reminders
                create_event_change_notification.delay(
                    actor_id=self.request.user.id, target_id=serializer.data['id'],
                    update_reminders=Notification.REMINDER_UPDATE_EVENT_FIELD in serializer.validated_data
                )

    def get_serializer_class(self):
        """Changing serializer for list action"""
        if self.action == 'list':
            return EventPreviewSerializer
        return EventDetailSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            # queryset just for schema generation metadata
            return Event.objects.none()
        return Event.objects.filter(
            Q(user=self.request.user) | Q(is_private=False) | Q(attendance__user=self.request.user)
        ).distinct()

    @swagger_auto_schema(
        operation_description="Invite users to this event by list of their ids",
        request_body=IdsListUniqueOrderdSerializer,
        responses={HTTP_204_NO_CONTENT: 'Invited successfully',
                   HTTP_400_BAD_REQUEST: 'Serializer or validation errors'})
    @action(detail=True, methods=['post'])
    def invite(self, request, pk=None):
        this_event = self.get_object()
        if this_event.end < datetime.now(pytz.utc):
            return Response({'message': 'Can not invite people to an event that has already ended'})

        if this_event.is_private and request.user != this_event.user and not this_event.allow_guests_to_invite:
            return Response({'message': 'You are not allowed to invite to this event'})

        lookup_serializer = IdsListUniqueOrderdSerializer(data=request.data)
        lookup_serializer.is_valid(raise_exception=True)
        user_ids = lookup_serializer.validated_data.get('ids')

        users = User.objects.filter(id__in=user_ids)
        invitable_users = users.exclude(attends=this_event).exclude(pk=request.user.id)
        if not invitable_users.exists():
            return Response({'message': 'No invitable users were passed'})

        for u in invitable_users:
            EventInvite.objects.create(event=this_event, inviter=request.user, invitee=u)

        return Response(status=HTTP_204_NO_CONTENT)

    @swagger_auto_schema(
        operation_description="Retract your invite to this event by list of user ids",
        request_body=IdsListUniqueOrderdSerializer,
        responses={HTTP_204_NO_CONTENT: 'Uninvited successfully',
                   HTTP_400_BAD_REQUEST: 'Serializer errors'})
    @action(detail=True, methods=['post'])
    def uninvite(self, request, pk=None):
        lookup_serializer = IdsListUniqueOrderdSerializer(data=request.data)
        lookup_serializer.is_valid(raise_exception=True)
        user_ids = lookup_serializer.validated_data.get('ids')

        event = self.get_object()
        qs = Attendance.objects.filter(event=event, user__id__in=user_ids, status=Attendance.INVITE_PENDING)
        if event.user != request.user:
            qs = qs.filter(invite__inviter=request.user)
        qs.delete()

        return Response(status=HTTP_204_NO_CONTENT)

    @swagger_auto_schema(
        operation_description="Like an event",
        request_body=no_body,
        responses={HTTP_204_NO_CONTENT: 'Liked successfully'})
    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        EventLike.objects.get_or_create(event=self.get_object(), user=request.user)
        return Response(status=HTTP_204_NO_CONTENT)

    @swagger_auto_schema(
        operation_description="Remove your like from an event",
        request_body=no_body,
        responses={HTTP_204_NO_CONTENT: 'Removed like successfully'})
    @like.mapping.delete
    def delete_like(self, request, pk=None):
        try:
            EventLike.objects.get(event=self.get_object(), user=request.user).delete()
        except EventLike.DoesNotExist:
            pass
        return Response(status=HTTP_204_NO_CONTENT)


class EventImageViewSet(ExtendedNestedEventViewSetMixin,
                        mixins.CreateModelMixin,
                        mixins.RetrieveModelMixin,
                        mixins.DestroyModelMixin,
                        mixins.ListModelMixin,
                        viewsets.GenericViewSet):
    """Basic eventImage viewset"""
    queryset = EventImage.objects.all()
    serializer_class = EventImageSerializer
    permission_classes = (IsAuthenticated, RelatedEventObjectPermission, RelatedEventOwner)
    parent_object_class = Event
    parent_object_id_kwarg = 'event_id'

    def perform_create(self, serializer):
        """Create event image by parent event_id"""
        event = self.get_parent_object()
        if event.images.filter(position=serializer.validated_data['position']).exists():
            raise ValidationError({'position': 'Image position must be unique within event'})
        serializer.save(event_id=event.id)

    @swagger_auto_schema(
        operation_description="Reorder images for this event",
        request_body=IdsListUniqueOrderdSerializer,
        responses={HTTP_204_NO_CONTENT: 'Reordered images successfully',
                   HTTP_400_BAD_REQUEST: 'Serializer, validation or db errors'})
    @action(detail=False, methods=['post'], name='reorder')
    def reorder(self, request, parent_lookup_event_id=None):
        lookup_serializer = IdsListUniqueOrderdSerializer(data=request.data)
        lookup_serializer.is_valid(raise_exception=True)
        image_ids = lookup_serializer.validated_data.get('ids')

        images_old_ord = self.get_parent_object().images.filter(id__in=image_ids).order_by('position')

        if images_old_ord.count() != len(image_ids):
            return Response({'message': 'Number of passed image ids must correspond to '
                                        'the number of images in this event'},
                            status=HTTP_400_BAD_REQUEST)

        images_new_ord = [next(img for img in images_old_ord if img.id == iid) for iid in image_ids]

        try:
            with transaction.atomic():
                for i, img in enumerate(images_new_ord):
                    if img.position != i:
                        img.position = i
                        img.save()
        except Exception:
            return Response({'message': 'A database error occured'}, status=HTTP_400_BAD_REQUEST)

        return Response(status=HTTP_204_NO_CONTENT)


class InviteUsersViewSet(ExtendedNestedEventViewSetMixin,
                         mixins.ListModelMixin,
                         viewsets.GenericViewSet):
    """I fear no man. But this thing... it scares me."""
    queryset = User.objects.all()
    serializer_class = UserAttendanceSerializer
    pagination_class = LimitOffsetPagination
    filter_backends = [SearchFilter, UserRelationFilter, NestedUserAttendanceInEventFilter]
    search_fields = ['brand_name', 'first_name', 'middle_name', 'last_name']

    def get_queryset(self):
        return User.objects.order_by_true_name().exclude(pk=self.request.user.id)

    @swagger_auto_schema(
        manual_parameters=[
            *UserRelationFilter.SWAGGER_PARAMS,
            *NestedUserAttendanceInEventFilter.SWAGGER_PARAMS],
        responses={HTTP_200_OK: UserAttendanceSerializer})
    def list(self, request, *args, **kwargs):
        event = self.get_parent_object()

        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        qs_to_serialize = page if page is not None else queryset

        statuses_map = dict(
            Attendance.objects.filter(
                event=event, user__in=qs_to_serialize).values_list('user_id', 'status')
        )

        invited_by_viewer_map = dict(
            EventInvite.objects.filter(
                event=event, invitee__in=qs_to_serialize
            ).values_list('invitee_id').annotate(
                invited_by_viewer=Case(
                    When(inviter=request.user, then=True),
                    default=False, output_field=BooleanField()
                )
            )
        )

        serializer_class = self.get_serializer_class()
        serializer_context = self.get_serializer_context()
        serializer_context.update({'event': event, 'statuses_map': statuses_map, 'invited_by_viewer_map': invited_by_viewer_map})
        serializer = serializer_class(qs_to_serialize, many=True, context=serializer_context)

        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


@method_decorator(name='list', decorator=swagger_auto_schema(
    manual_parameters=[*AttendanceUserRelationFilter.SWAGGER_PARAMS],
    responses={HTTP_200_OK: AttendanceSerializer}))
class AttendanceViewSet(ExtendedNestedEventViewSetMixin,
                        mixins.ListModelMixin,
                        viewsets.GenericViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = (IsAuthenticated, RelatedEventObjectPermission)
    http_method_names = ['get', 'post', 'delete']
    pagination_class = LimitOffsetPagination
    filter_backends = [SearchFilter, DjangoFilterBackend, AttendanceUserRelationFilter]
    search_fields = ['user__brand_name', 'user__first_name', 'user__middle_name', 'user__last_name']
    filterset_class = AttendanceFilterSet

    def get_queryset(self):
        return self.filter_queryset_by_parents_lookups(
            Attendance.objects.select_related('user', 'event').prefetch_related('invite').annotate(
                true_user_name=Case(
                    When(user__profile_type=User.BUSINESS_PROFILE, then=F('user__brand_name')),
                    default=Concat(F('user__first_name'), F('user__middle_name'), F('user__last_name'))
                )
            ).order_by('status', 'true_user_name')
        )

    def _set_attendance(self, status):
        """
        Create or update Attendance for currently logged in user, for this event with @status or
        If @status is None - remove Attendance for this event for currently logged in user.
        """
        user = self.request.user
        event = self.get_parent_object()

        if event.start < datetime.now(pytz.utc):
            raise ValidationError({'message': 'You can not change your attendance status after event has started.'})

        if not status:
            Attendance.objects.filter(user=user, event=event).delete()
        else:
            try:
                attendance = Attendance.objects.get(user=user, event=event)
                attendance.status = status
                attendance.save()
            except Attendance.DoesNotExist:
                Attendance.objects.create(user=user, event=event, status=status)

    @swagger_auto_schema(
        operation_description="Set your attendance status to 'attending'",
        request_body=no_body,
        responses={HTTP_204_NO_CONTENT: 'Attendance status set successfully'})
    @action(detail=False, methods=['post'], name='set-attending')
    def attending(self, request, parent_lookup_event_id=None):
        self._set_attendance(Attendance.ATTENDING)
        return Response(status=HTTP_204_NO_CONTENT)

    @swagger_auto_schema(
        operation_description="Set your attendance status to 'declined'",
        request_body=no_body,
        responses={HTTP_204_NO_CONTENT: 'Attendance status set successfully'})
    @action(detail=False, methods=['post'], name='set-declined')
    def declined(self, request, parent_lookup_event_id=None):
        self._set_attendance(Attendance.DECLINED)
        return Response(status=HTTP_204_NO_CONTENT)

    @swagger_auto_schema(
        operation_description="Set your attendance status to 'maybe'",
        request_body=no_body,
        responses={HTTP_204_NO_CONTENT: 'Attendance status set successfully'})
    @action(detail=False, methods=['post'], name='set-maybe')
    def maybe(self, request, parent_lookup_event_id=None):
        self._set_attendance(Attendance.MAYBE)
        return Response(status=HTTP_204_NO_CONTENT)

    @swagger_auto_schema(
        operation_description="Erase your attendance status",
        request_body=no_body,
        responses={HTTP_204_NO_CONTENT: 'Attendance status set successfully'})
    @action(detail=False, methods=['post'])
    def leave(self, request, parent_lookup_event_id=None):
        self._set_attendance(status=None)
        return Response(status=HTTP_204_NO_CONTENT)


class ReminderViewSet(ExtendedNestedEventViewSetMixin,
                      mixins.CreateModelMixin,
                      viewsets.GenericViewSet):
    queryset = Reminder.objects.all()
    serializer_class = ReminderSerializer
    permission_classes = (IsAuthenticated, RelatedEventObjectPermission)
    http_method_names = ['get', 'post', 'delete', 'patch']

    def get_object(self):
        event = self.get_parent_object()
        return get_object_or_404(Reminder, event=event, user=self.request.user)

    def perform_create(self, serializer):
        """Perform create for current user"""
        event = self.get_parent_object()
        try:
            Reminder.objects.get(user=self.request.user, event=event)
            raise ValidationError('Reminder for event already exist')
        except Reminder.DoesNotExist:
            serializer.save(user=self.request.user, event=event)

    @action(detail=False, methods=['delete'])
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['patch'], url_path='update')
    def update_offset(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class EventCommentsViewSet(ExtendedNestedEventViewSetMixin, viewsets.ModelViewSet):
    serializer_class = EventCommentSerializer
    permission_classes = (IsAuthenticated, RelatedEventObjectPermission, IsOwnerOrReadOnly)
    http_method_names = ['get', 'post', 'delete', 'patch']
    pagination_class = LimitOffsetPagination

    def get_queryset(self):
        return self.filter_queryset_by_parents_lookups(
            EventComment.objects.select_related('user').order_by('-id')
        )

    def list(self, request, *args, **kwargs):
        event = self.get_parent_object()

        queryset = self.filter_queryset(self.get_queryset())
        paginated_queryset = self.paginate_queryset(queryset)

        statuses_map = dict(
            Attendance.objects.filter(
                event=event, user__in=[c.user for c in paginated_queryset]).values_list('user_id', 'status')
        )

        serializer_class = self.get_serializer_class()
        serializer_context = self.get_serializer_context()
        serializer_context.update({'statuses_map': statuses_map})
        serializer = serializer_class(paginated_queryset, many=True, context=serializer_context)

        return self.get_paginated_response(serializer.data)

    def perform_create(self, serializer):
        event = self.get_parent_object()
        serializer.save(user=self.request.user, event=event)


class EventPostsViewSet(ExtendedNestedEventViewSetMixin,
                        mixins.ListModelMixin,
                        viewsets.GenericViewSet):
    serializer_class = PostPreviewSerializer
    permission_classes = (IsAuthenticated, RelatedEventObjectPermission)
    pagination_class = LimitOffsetPagination

    def get_queryset(self):
        return self.filter_queryset_by_parents_lookups(
            Post.objects.select_related('user', 'event').order_by('-id')
        )
