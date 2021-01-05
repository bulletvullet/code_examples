from django.contrib import admin
from django.utils.html import format_html

from events.models import (Attendance, Event, EventCategory,
                           EventCategoryImage, EventInvite, Reminder)


@admin.register(Event)
class EventsAdmin(admin.ModelAdmin):
    list_filter = ('provider',)
    list_display = ('title', 'user', 'start', 'start_timezone', 'end', 'end_timezone', 'created', 'updated',
                    'is_private', 'provider')
    search_fields = ('title', 'user__email', 'user__phone_number')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_filter = ('status',)
    list_display = ('user', 'event', 'status')
    search_fields = ('user__email', 'user__phone_number', 'event__title')


@admin.register(EventInvite)
class EventInviteAdmin(admin.ModelAdmin):
    list_filter = ('invitee_attendance__status',)
    list_display = ('event', 'invitee', 'inviter', 'invitee_attendance')
    search_fields = ('event__title', 'invitee__email', 'inviter__email')


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'offset')
    search_fields = ('user__email', 'user__phone_number', 'event__title')


@admin.register(EventCategory)
class EventCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_active', 'is_interest')


@admin.register(EventCategoryImage)
class EventCategoryImageAdmin(admin.ModelAdmin):
    def image_tag(self, obj):
        return format_html('<img src="{}" style="max-height:150px;max-width:600px;height:auto;width:auto;" />'.format(obj.image.url))

    image_tag.short_description = 'Image'

    list_display = ('id', 'category', 'image_tag', 'is_active')
