"""Event models"""

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models
from django.template.defaultfilters import truncatechars

from prism.utils.mixins import ImageHandlerMixin


class EventCategory(ImageHandlerMixin, models.Model):
    UPLOAD_IMAGE_PREFIX = 'e_c'  # event category

    def get_upload_path(self, filename: str) -> str:
        """Generate image uuid with original image format png/jpg"""
        ext = filename.split('.')[-1]
        return f"{self.UPLOAD_IMAGE_PREFIX}/{self.generate_name()}.{ext}"

    name = models.CharField(max_length=45)
    image = models.ImageField(upload_to=get_upload_path)
    cropped_image = models.ImageField(upload_to=get_upload_path)
    icon = models.ImageField(upload_to=get_upload_path)
    badge_color = models.CharField(max_length=7)
    is_interest = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    # percent value of regular events out of 100 totally
    regular_events_percentage = models.SmallIntegerField(default=80)

    def save(self, *args, **kwargs) -> None:
        """Compress images"""
        self.image = self.compress(self.image, 'large')
        self.cropped_image = self.compress(self.cropped_image, 'large')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "categories"


class EventCategoryImage(ImageHandlerMixin, models.Model):
    UPLOAD_IMAGE_PREFIX = 'e_c'  # event category

    def get_upload_path(self, filename: str) -> str:
        """Generate image uuid with original image format png/jpg"""
        ext = filename.split('.')[-1]
        return f"{self.UPLOAD_IMAGE_PREFIX}/{self.generate_name()}.{ext}"

    category = models.ForeignKey(EventCategory, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=get_upload_path)
    cropped_image = models.ImageField(upload_to=get_upload_path)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs) -> None:
        """Compress images"""
        self.image = self.compress(self.image, 'large')
        self.cropped_image = self.compress(self.cropped_image, 'large')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.category} category image ({self.id})"

    class Meta:
        verbose_name_plural = "category images"


class Event(ImageHandlerMixin, models.Model):
    """Basic event model"""

    UPLOAD_IMAGE_PREFIX = 'e'  # event

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='events', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    is_private = models.BooleanField(default=True)
    allow_guests_to_invite = models.BooleanField(default=True)

    category = models.ForeignKey(EventCategory, default=1, on_delete=models.PROTECT)
    category_image = models.ForeignKey(EventCategoryImage, null=True, blank=True, on_delete=models.PROTECT)

    start = models.DateTimeField()
    start_timezone = models.CharField(max_length=50)
    end = models.DateTimeField()
    end_timezone = models.CharField(max_length=50)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    provider = models.CharField(max_length=32, null=True, blank=True)
    external_id = models.CharField(max_length=255, null=True, db_index=True, blank=True)

    attendees = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='attends', through='Attendance',
                                       through_fields=('event', 'user'))

    main_image = models.ImageField(upload_to=ImageHandlerMixin.get_upload_path, null=True, blank=True)
    main_image_cropped = models.ImageField(upload_to=ImageHandlerMixin.get_upload_path, null=True, blank=True)
    main_image_crop_points = models.CharField(max_length=45, blank=True)

    location = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.DecimalField(max_digits=22, decimal_places=16, null=True, blank=True)
    longitude = models.DecimalField(max_digits=22, decimal_places=16, null=True, blank=True)

    is_online = models.BooleanField(default=False)
    website = models.URLField(max_length=255, null=True, blank=True)

    liked = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='liked_events', through='EventLike',
                                   through_fields=('event', 'user'))

    class Meta:
        unique_together = (
            ('user', 'provider', 'external_id'),
        )

    def __str__(self):
        return self.title

    @property
    def attending(self):
        return Attendance.objects.filter(event_id=self.id, status=Attendance.ATTENDING)

    @property
    def maybe(self):
        return Attendance.objects.filter(event_id=self.id, status=Attendance.MAYBE)

    @property
    def declined(self):
        return Attendance.objects.filter(event_id=self.id, status=Attendance.DECLINED)

    @property
    def pending(self):
        return Attendance.objects.filter(event_id=self.id, status=Attendance.INVITE_PENDING)

    def user_attending_friends(self, user):
        """Get attending friends for user"""
        return Attendance.objects.filter(event=self, user__in=user.friends, status=Attendance.ATTENDING)


class Attendance(models.Model):
    """Model for event attendance by users"""
    event = models.ForeignKey('Event', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    ATTENDING = 1
    MAYBE = 2
    INVITE_PENDING = 3
    DECLINED = 4
    STATUS_CHOICES = [
        (ATTENDING, 'Attending'),
        (MAYBE, 'Maybe'),
        (INVITE_PENDING, 'Invite pending'),
        (DECLINED, 'Declined'),
    ]

    CACHE_STATUS_KEY_MAP = {
        ATTENDING: 'attending',
        DECLINED: 'declined',
        MAYBE: 'maybe',
        INVITE_PENDING: 'pending',
    }
    CACHE_STATUS_KEYS = CACHE_STATUS_KEY_MAP.values()

    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES, default=ATTENDING)

    is_from_subscription = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (('event', 'user'), )

    @property
    def status_cache_key(self):
        """Get cache key by current status"""
        return self.CACHE_STATUS_KEY_MAP[self.status]

    def __str__(self):
        return f'Attendance of {self.user} to {self.event.title} ({self.status})'


class EventInvite(models.Model):
    """Model for invites to an event"""
    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='invites')
    invitee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='incoming_invites')
    inviter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='outgoing_invites')
    invitee_attendance = models.OneToOneField('Attendance', on_delete=models.CASCADE, related_name='invite')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (('event', 'invitee'), )

    def __str__(self):
        return f'Invite of {self.invitee} ' \
               f'by {self.inviter} ' \
               f'to {self.event.title} ({self.invitee_attendance.status})'


class EventImage(ImageHandlerMixin, models.Model):
    """Images for event model"""

    def get_upload_path(self, filename: str) -> str:
        """Generate image uuid"""
        return f"{Event.UPLOAD_IMAGE_PREFIX}/{self.event_id}/{self.generate_name()}.jpg"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=get_upload_path)
    # lowest position - main image for event
    position = models.PositiveSmallIntegerField()

    def drop_all_images(self) -> None:
        """Dropping all images"""
        default_storage.delete(self.image.name)

    def save(self, *args, **kwargs) -> None:
        """Compress image"""
        self.image = self.compress(self.image, 'large')
        super().save(*args, **kwargs)


class Reminder(models.Model):
    """Model for event attendance by users"""
    event = models.ForeignKey('Event', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # remind time in seconds before event starts
    offset = models.PositiveIntegerField(default=10)

    class Meta:
        unique_together = (('event', 'user'),)

    def __str__(self):
        return f'Reminder for {self.user} to event {self.event.title}'


class EventLike(models.Model):
    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='likes')

    CACHE_KEY = 'liked'

    class Meta:
        unique_together = (('event', 'user'),)

    def __str__(self):
        return f'Like of {self.user} to event {self.event.title}'


class EventComment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comments')
    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='comments')

    body = models.TextField(max_length=220)

    created = models.DateTimeField(auto_now_add=True)

    CACHE_KEY = 'comments'

    def __str__(self):
        return f'{self.user} in {self.event}: {truncatechars(self.body, 50)}'
