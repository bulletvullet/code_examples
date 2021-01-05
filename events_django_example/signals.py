"""Signals for event app"""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from events.models import (Attendance, Event, EventComment, EventImage,
                           EventInvite, EventLike, Reminder)
from events.tasks import create_attendance_for_subscribers
from notifications.tasks import (create_event_invite_user_notification,
                                 create_event_like_notification,
                                 create_reminder_notification,
                                 remove_event_invite_user_notification,
                                 remove_event_like_notification,
                                 remove_reminder_notification)
from prism.utils.cache_utils import decr_in_cache, incr_in_cache

User = get_user_model()


@receiver(post_delete, sender=EventImage)
def auto_delete_file_on_delete(sender, instance, **kwargs) -> None:
    """Dropping all images saved to storage any sizes"""
    instance.drop_all_images()


@receiver(post_save, sender=Event)
def post_create_event_handler(sender, instance: Event, created, **kwargs) -> None:
    """Post save signal for adding event creator to created event attendees and update events counter for user"""
    if created:
        # add attendance for event
        Attendance.objects.create(event=instance, user=instance.user, status=Attendance.ATTENDING)
        # increment events counter for user if exist
        incr_in_cache(User, instance.user_id, 'events')
        # create attendance for subscribers
        if not instance.is_private and instance.user.subscribers.exists():
            create_attendance_for_subscribers(instance.id, instance.user_id)


@receiver(post_delete, sender=Event)
def post_delete_event_handler(sender, instance: Event, **kwargs) -> None:
    """Decrement events counter for user"""
    decr_in_cache(User, instance.user_id, 'events')


@receiver(pre_save, sender=EventInvite)
def pre_save_create_attendance_for_invite(sender, instance, **kwargs) -> None:
    """Pre save signal for adding event creator to created event attendees"""
    if not getattr(instance, 'invitee_attendance', None):
        instance.invitee_attendance = Attendance.objects.create(event=instance.event, user=instance.invitee,
                                                                status=Attendance.INVITE_PENDING)


@receiver(post_save, sender=EventInvite)
def post_save_event_invite_create_notification(sender, instance, created, **kwargs) -> None:
    """Create notification after creating invite"""
    if created:
        create_event_invite_user_notification.delay(target_id=instance.event_id, actor_id=instance.inviter_id,
                                                    recipient_id=instance.invitee_id)


@receiver(post_delete, sender=EventInvite)
def post_delete_drop_pending_invitee_attendance(sender, instance, **kwargs) -> None:
    """Post delete event invite"""
    # drop all pending attendances
    if instance.invitee_attendance.status == Attendance.INVITE_PENDING:
        instance.invitee_attendance.delete()
        # delete invite notification
        remove_event_invite_user_notification.delay(target_id=instance.event_id, actor_id=instance.inviter_id,
                                                    recipient_id=instance.invitee_id)


@receiver(post_save, sender=Attendance)
def post_save_attendance(sender: object, instance: Attendance, created: bool, *args, **kwargs) -> None:
    """Post save attendance status
        reminders trigger actions:
     - attendance was created and status not in (DECLINED, INVITE_PENDING) --- create reminder
     - attendance status was changed to ATTENDING or MAYBE --- check if exist / create
     - attendance status was changed to DECLINED --- remove reminder
    """
    # inc any of new statuses in cache
    incr_in_cache(Event, instance.event_id, instance.status_cache_key)
    # reminders part
    if created and instance.status not in (instance.DECLINED, instance.INVITE_PENDING):
        if instance.status == instance.ATTENDING and \
            instance.event.user_id == instance.user_id and \
                (instance.created - instance.event.created).seconds <= 5:
            pass  # Don't create for owner right after event create
        else:
            Reminder.objects.create(user_id=instance.user_id, event_id=instance.event_id)
    elif instance.status == instance.DECLINED:
        Reminder.objects.filter(user_id=instance.user_id, event_id=instance.event_id).delete()
    elif instance.status in (instance.ATTENDING, instance.MAYBE):
        Reminder.objects.get_or_create(user_id=instance.user_id, event_id=instance.event_id)


@receiver(pre_save, sender=Attendance)
def pre_save_attendance(sender: object, instance: Attendance, *args, **kwargs) -> None:
    """Downcount old attendance status in cache"""
    try:
        old_instance = Attendance.objects.get(pk=instance.pk)
        decr_in_cache(Event, old_instance.event_id, old_instance.status_cache_key)
    except Attendance.DoesNotExist:
        # if created old attendance status does not exist
        pass


@receiver(post_delete, sender=Attendance)
def post_delete_attendance_handler(sender, instance: Attendance, **kwargs) -> None:
    """Post delete attendance signal"""
    # downcount attendance in cache
    decr_in_cache(Event, instance.event_id, instance.status_cache_key)
    # remove reminder if exist
    Reminder.objects.filter(user_id=instance.user_id, event_id=instance.event_id).delete()


@receiver(post_save, sender=EventLike)
def post_save_like(sender: object, instance: EventLike, created: bool, *args, **kwargs) -> None:
    """Post create like signal"""
    if created:
        # upcount event like count in cache
        incr_in_cache(Event, instance.event_id, instance.CACHE_KEY)
        # create notification if it is not ownself like
        if instance.user_id != instance.event.user_id:
            create_event_like_notification.delay(actor_id=instance.user_id, target_id=instance.event_id,
                                                 recipient_id=instance.event.user_id)


@receiver(post_delete, sender=EventLike)
def post_delete_like(sender, instance: Attendance, **kwargs) -> None:
    # downcount likes in cache
    decr_in_cache(Event, instance.event_id, instance.CACHE_KEY)
    # remove like notification
    if instance.user_id != instance.event.user_id:
        remove_event_like_notification.delay(actor_id=instance.user_id, target_id=instance.event_id,
                                             recipient_id=instance.event.user_id)


@receiver(post_save, sender=Reminder)
def post_save_reminder(sender: object, instance: Reminder, *args, **kwargs) -> None:
    """Create or update reminder notification"""
    transaction.on_commit(
        lambda: create_reminder_notification.delay(
            recipient_id=instance.user_id, target_id=instance.event_id, reminder_offset=instance.offset
        )
    )


@receiver(post_delete, sender=Reminder)
def post_delete_reminder(sender: object, instance: Reminder, *args, **kwargs) -> None:
    """Delete active reminders from notifications"""
    remove_reminder_notification.delay(recipient_id=instance.user_id, target_id=instance.event_id)


@receiver(post_save, sender=EventComment)
def post_create_comment_handler(sender, instance, created, *args, **kwargs):
    if created:
        incr_in_cache(Event, instance.event_id, instance.CACHE_KEY)


@receiver(post_delete, sender=EventComment)
def post_delete_comment_handler(sender, instance, *args, **kwargs):
    decr_in_cache(Event, instance.event_id, instance.CACHE_KEY)
