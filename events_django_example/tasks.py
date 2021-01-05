import logging
from datetime import datetime, timedelta
from uuid import uuid4

import pytz
import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import reverse
from rest_framework import status
from social_django.utils import load_strategy
from tzlocal.windows_tz import win_tz

from celery_logs.utils import CeleryDatabaseLogger
from events.models import Attendance, Event
from prism.celery import app
from prism.utils.time_utils import milliseconds
from users.models import Subscription, UserSocialAuth

UserModel = get_user_model()
logger = logging.getLogger('django')

MS_TO_PYTZ_TZ_MAP = win_tz.copy()
MS_TO_PYTZ_TZ_MAP.update({
    'tzone://Microsoft/Utc': 'UTC',
})


@app.task(bind=True)
def subscribe_to_google(self, social_id: int):
    with CeleryDatabaseLogger(self) as celery_logger:
        social = UserSocialAuth.objects.get(pk=social_id)
        access_token = social.get_access_token(load_strategy())
        headers = {"Authorization": f"Bearer {access_token}"}

        watch_url = 'https://www.googleapis.com/calendar/v3/calendars/primary/events/watch'

        channel_id = str(uuid4())

        subscription_time = milliseconds()

        data = {
            'id': channel_id,
            "type": "web_hook",
            "address": settings.BASE_URL + reverse('google_webhook'),
            "expiration": subscription_time + UserSocialAuth.SUBSCRIPTION_DURATION
        }

        try:
            response = requests.post(watch_url, headers=headers, json=data)
        except Exception as e:
            celery_logger.log({'error': str(e), 'social_id': social_id})
            raise
        else:
            if response.status_code == status.HTTP_200_OK:
                result = response.json()
                with transaction.atomic():
                    social = UserSocialAuth.objects.select_for_update().get(pk=social_id)
                    social.subscription_id = result['id']
                    calendar_data = social.calendar_data
                    calendar_data['resource_id'] = result['resourceId']
                    calendar_data['sub_time'] = subscription_time
                    social.calendar_data = calendar_data
                    social.save(update_fields=['subscription_id', 'calendar_data'])
                    celery_logger.log({'social_id': social_id})
            else:
                celery_logger.log({
                    'social_id': social_id,
                    'status_code': response.status_code,
                    'response': response.text
                })


def unsubscribe_from_google(social_id: int):
    social = UserSocialAuth.objects.get(pk=social_id)
    access_token = social.get_access_token(load_strategy())
    headers = {"Authorization": f"Bearer {access_token}"}

    if not social.subscription_id and social.provider != 'google-oauth2':
        return

    stop_url = 'https://www.googleapis.com/calendar/v3/channels/stop'

    channel_id = social.subscription_id
    resource_id = social.calendar_data.get('resource_id')

    data = {
        'id': channel_id,
        'resourceId': resource_id,
    }

    try:
        response = requests.post(stop_url, headers=headers, json=data)
    except Exception:
        print("EXCEPTION DURING CANCELLING SUBSCRIPTION")
    else:
        if response.status_code == status.HTTP_200_OK:
            print("SUBSCRIPTION CANCELED")
            Event.objects.filter(user=social.user, provider=social.provider).delete()
        else:
            print("CANCELLING SUBSCRIPTION FAILED")
            print(response.status_code, response.content)


def sync_google_event(google_event: dict, user: UserModel, user_timezone: str):
    if google_event.get('status') == 'cancelled':
        try:
            Event.objects.get(user=user, provider='google-oauth2', external_id=google_event.get('id')).delete()
        except Event.DoesNotExist:
            pass

        return

    start = google_event['start'].get('dateTime')
    start_timezone = google_event['start'].get('timeZone', user_timezone)

    if not start:
        start = google_event['start'].get('date')
        start = datetime.fromisoformat(start)

        if not start.tzinfo:
            start = pytz.timezone(start_timezone).localize(start)
        start = start.astimezone(pytz.utc)

    end = google_event['end'].get('dateTime')
    end_timezone = google_event['end'].get('timeZone', user_timezone)

    if not end:
        end = google_event['end'].get('date')
        end = datetime.fromisoformat(end)

        if not end.tzinfo:
            end = pytz.timezone(end_timezone).localize(end)
        end = end.astimezone(pytz.utc)

    description = BeautifulSoup(google_event.get('description', ''), 'lxml').get_text().strip()

    defaults = {
        'title': google_event.get('summary', ''),
        'description': description,
        'start': start,
        'end': end,
        'start_timezone': start_timezone,
        'end_timezone': end_timezone,
    }

    Event.objects.update_or_create(
        external_id=google_event.get('id'),
        provider='google-oauth2',
        user=user,
        defaults=defaults
    )


@app.task(bind=True)
def sync_google_events(self, social_id: int):
    with CeleryDatabaseLogger(self) as celery_logger:
        social = UserSocialAuth.objects.get(pk=social_id)
        access_token = social.get_access_token(load_strategy())
        headers = {"Authorization": f"Bearer {access_token}"}
        url = 'https://www.googleapis.com/calendar/v3/calendars/primary/events'

        sync_token = social.calendar_data.get('sync_token')
        query_params = {
            'timeZone': 'utc'
        }

        if not sync_token:
            query_params['timeMin'], query_params['timeMax'] = UserSocialAuth.get_sync_bounds()

        if sync_token:
            query_params['syncToken'] = sync_token

        page_token = None

        while True:
            if page_token:
                query_params['pageToken'] = page_token

            try:
                response = requests.get(url, headers=headers, params=query_params)
            except Exception as e:
                celery_logger.log({'social_id': social_id, 'error': str(e)})
                raise
            else:
                if response.status_code == status.HTTP_200_OK:
                    result = response.json()

                    events = result['items']
                    for google_event in events:
                        sync_google_event(google_event, user=social.user, user_timezone=result['timeZone'])

                    page_token = result.get('nextPageToken')
                    sync_token = result.get('nextSyncToken')

                    if not page_token:
                        break
                elif response.status_code == status.HTTP_410_GONE and \
                        response.json()['error']['errors'][0]['reason'] == 'fullSyncRequired':
                    query_params.pop('syncToken')
                    query_params.pop('pageToken', None)
                    query_params['timeMin'], query_params['timeMax'] = UserSocialAuth.get_sync_bounds()
                    continue
                else:
                    celery_logger.log({
                        'social_id': social_id,
                        'status_code': response.status_code,
                        'response': response.text
                    })
                    return

        with transaction.atomic():
            social = UserSocialAuth.objects.select_for_update().get(pk=social_id)
            calendar_data = social.calendar_data
            calendar_data['sync_token'] = sync_token
            social.calendar_data = calendar_data
            social.save(update_fields=['calendar_data'])
            celery_logger.log({'social_id': social_id})


@app.task(bind=True)
def subscribe_to_outlook(self, social_id: int):
    with CeleryDatabaseLogger(self) as celery_logger:
        social = UserSocialAuth.objects.get(pk=social_id)
        access_token = social.get_access_token(load_strategy())
        headers = {"Authorization": f"Bearer {access_token}"}

        watch_url = 'https://graph.microsoft.com/v1.0/subscriptions'

        dt_utc = datetime.utcnow()
        expiration_date_time = dt_utc + timedelta(milliseconds=UserSocialAuth.SUBSCRIPTION_DURATION)

        data = {
            "resource": "me/events",
            "notificationUrl": settings.BASE_URL + reverse('outlook_webhook'),
            "changeType": "created,deleted,updated",
            "expirationDateTime": f"{expiration_date_time.isoformat()}Z"
        }

        try:
            response = requests.post(watch_url, headers=headers, json=data)
        except Exception as e:
            celery_logger.log({'social_id': social_id, 'error': str(e)})
            raise
        else:
            if response.status_code == status.HTTP_201_CREATED:
                result = response.json()
                with transaction.atomic():
                    social = UserSocialAuth.objects.select_for_update().get(pk=social_id)
                    social.subscription_id = result['id']
                    calendar_data = social.calendar_data
                    calendar_data['sub_time'] = milliseconds(datetime.timestamp(dt_utc))
                    social.calendar_data = calendar_data
                    social.save(update_fields=['subscription_id', 'calendar_data'])
                    celery_logger.log({'social_id': social_id})
            else:
                celery_logger.log({
                    'social_id': social_id,
                    'status_code': response.status_code,
                    'response': response.text
                })


def sync_outlook_event(outlook_event: dict, user: UserModel):
    if outlook_event.get('seriesMasterId'):
        # Skip recurring event, we are saving only the main recurring event
        return

    if outlook_event.get('@removed'):
        try:
            Event.objects.get(user=user, provider='microsoft-graph', external_id=outlook_event.get('id')).delete()
        except Event.DoesNotExist:
            pass
        return

    start = outlook_event['start'].get('dateTime')
    start_timezone = MS_TO_PYTZ_TZ_MAP.get(outlook_event['originalStartTimeZone'], outlook_event['originalStartTimeZone'])
    start = datetime.strptime(start, '%Y-%m-%dT%H:%M:%S.%f0')
    start = start.astimezone(pytz.utc)

    end = outlook_event['end'].get('dateTime')
    end_timezone = MS_TO_PYTZ_TZ_MAP.get(outlook_event['originalEndTimeZone'], outlook_event['originalEndTimeZone'])
    end = datetime.strptime(end, '%Y-%m-%dT%H:%M:%S.%f0')
    end = end.astimezone(pytz.utc)

    if outlook_event['body']['contentType'] == 'html':
        bs = BeautifulSoup(outlook_event['body']['content'], 'lxml')
        body = bs.find('body')
        description = (body if body else bs).get_text().strip()
    else:
        description = outlook_event['body']['content']

    defaults = {
        'title': outlook_event.get('subject', ''),
        'description': description,
        'start': start,
        'end': end,
        'start_timezone': start_timezone,
        'end_timezone': end_timezone,
    }

    Event.objects.update_or_create(
        external_id=outlook_event.get('id'),
        provider='microsoft-graph',
        user=user,
        defaults=defaults
    )


@app.task(bind=True)
def sync_outlook_events(self, social_id: int):
    with CeleryDatabaseLogger(self) as celery_logger:
        social = UserSocialAuth.objects.get(pk=social_id)
        access_token = social.get_access_token(load_strategy())
        headers = {
            "Authorization": f"Bearer {access_token}",
        }

        delta_link = social.calendar_data.get('delta_link')

        query_params = dict()

        url = 'https://graph.microsoft.com/v1.0/me/calendarView/delta'

        if not delta_link:
            query_params['startDateTime'], query_params['endDateTime'] = UserSocialAuth.get_sync_bounds()
        else:
            url = delta_link

        while True:
            try:
                response = requests.get(url, headers=headers, params=query_params)
            except Exception as e:
                celery_logger.log({'social_id': social_id, 'error': str(e)})
                raise
            else:
                if response.status_code == status.HTTP_200_OK:
                    result = response.json()

                    events = result['value']
                    for outlook_event in events:
                        sync_outlook_event(outlook_event, user=social.user)

                    delta_link = result.get('@odata.deltaLink')
                    next_link = result.get('@odata.nextLink')

                    url = delta_link or next_link
                    query_params = dict()

                    if not events:
                        break
                else:
                    celery_logger.log({
                        'social_id': social_id,
                        'status_code': response.status_code,
                        'response': response.text
                    })
                    return

        with transaction.atomic():
            social = UserSocialAuth.objects.select_for_update().get(pk=social_id)
            calendar_data = social.calendar_data
            calendar_data['delta_link'] = delta_link
            social.calendar_data = calendar_data
            social.save(update_fields=['calendar_data'])
            celery_logger.log({'social_id': social_id})


def unsubscribe_from_outlook(social_id: int):
    social = UserSocialAuth.objects.get(pk=social_id)
    access_token = social.get_access_token(load_strategy())
    headers = {"Authorization": f"Bearer {access_token}"}

    if not social.subscription_id and social.provider != 'microsoft-graph':
        return

    stop_url = f'https://graph.microsoft.com/v1.0/subscriptions/{social.subscription_id}'

    try:
        response = requests.delete(stop_url, headers=headers)
    except Exception as ex:
        raise ex
    else:
        if response.status_code == status.HTTP_204_NO_CONTENT:
            print("SUBSCRIPTION CANCELED")
            Event.objects.filter(user=social.user, provider=social.provider).delete()
        else:
            print(response.content)
            print("CANCELLING SUBSCRIPTION FAILED")


@app.task(bind=True)
def create_attendance_for_subscribers(self, event_id, user_id):
    with CeleryDatabaseLogger(self):
        subscriber_ids = list(Subscription.objects.filter(target_id=user_id).values_list('user_id', flat=True))
        # we want a bunch of signals to trigger on attendance creation, so no bulk create
        for sub_id in subscriber_ids:
            Attendance.objects.create(
                user_id=sub_id,
                event_id=event_id,
                status=Attendance.ATTENDING,
                is_from_subscription=True)
