import datetime as dt
import tempfile
from unittest import skip

import pytz
from django.contrib.auth import get_user_model
from django.urls import reverse
from PIL import Image
from rest_framework.status import (HTTP_200_OK, HTTP_201_CREATED,
                                   HTTP_204_NO_CONTENT, HTTP_400_BAD_REQUEST,
                                   HTTP_404_NOT_FOUND)
from rest_framework.test import APITestCase

from system.timezones import TIMEZONES

from .models import Event, EventImage


class TestBasicEvents(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email='user@example.com', first_name='Test User',
                                                         password='12345678ABC')
        self.client.force_authenticate(user=self.user)
        self.event_data = {
            'title': 'Title',
            'description': 'Desc',
            'start_timezone': TIMEZONES[0],
            'start': dt.datetime.now(pytz.utc),
            'end_timezone': TIMEZONES[0],
            'end': dt.datetime.now(pytz.utc) + dt.timedelta(days=2),
            'user': self.user,
            'is_private': False,
        }

    def test_create_basic_event(self):
        # Substitute +00:00 > Z solely so we can directly compare intup to output
        self.event_data['start'] = self.event_data['start'].isoformat().replace('+00:00', 'Z')
        self.event_data['end'] = self.event_data['end'].isoformat().replace('+00:00', 'Z')
        self.event_data.pop('user')

        url = reverse('event-list')
        response = self.client.post(url, self.event_data)

        self.assertEqual(response.status_code, HTTP_201_CREATED)
        self.assertEqual(len(Event.objects.filter(pk=response.data['id'])), 1)
        self.assertEqual(response.data['user']['id'], self.user.id)
        for k, v in self.event_data.items():
            self.assertEqual(response.data[k], v)

    def test_view_event_detail(self):
        e1 = Event.objects.create(**self.event_data)

        url = reverse('event-detail', kwargs={'pk': e1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(response.data['id'], e1.id)
        self.assertEqual(response.data['user']['id'], self.user.id)

    def test_update_event(self):
        e1 = Event.objects.create(**self.event_data)

        update_data = {
            'title': 'Title Changed',
            'description': 'Desc Changed',
            'start_timezone': TIMEZONES[-1],
            'start': (self.event_data['start'] + dt.timedelta(days=10)).isoformat().replace('+00:00', 'Z'),
            'end_timezone': TIMEZONES[-1],
            'end': (self.event_data['end'] + dt.timedelta(days=10)).isoformat().replace('+00:00', 'Z'),
        }

        url = reverse('event-detail', kwargs={'pk': e1.id})
        response = self.client.patch(url, update_data)

        self.assertEqual(response.status_code, HTTP_200_OK)
        for k, v in update_data.items():
            self.assertEqual(response.data[k], v)

    def test_delete_event(self):
        e1 = Event.objects.create(**self.event_data)

        url = reverse('event-detail', kwargs={'pk': e1.id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, HTTP_204_NO_CONTENT)
        self.assertEqual(Event.objects.filter(pk=e1.id).count(), 0)


class TestPrivateEvents(APITestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(email='owner@example.com', first_name='Owner',
                                                          password='12345678ABC')
        self.schmuck = get_user_model().objects.create_user(email='schmuck@example.com', first_name='Schmuck',
                                                            password='12345678ABC')
        self.event_data = {
            'title': 'Title',
            'description': 'Desc',
            'start_timezone': TIMEZONES[0],
            'start': dt.datetime.now(pytz.utc),
            'end_timezone': TIMEZONES[0],
            'end': dt.datetime.now(pytz.utc) + dt.timedelta(days=2),
            'user': self.owner,
            'is_private': True
        }

    def test_create_private_event(self):
        self.event_data['start'] = self.event_data['start'].isoformat()
        self.event_data['end'] = self.event_data['end'].isoformat()
        self.event_data.pop('user')

        url = reverse('event-list')
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(url, self.event_data)

        self.assertEqual(response.status_code, HTTP_201_CREATED)
        self.assertEqual(len(Event.objects.filter(pk=response.data['id'])), 1)
        self.assertEqual(response.data['user']['id'], self.owner.id)
        self.assertEqual(response.data['is_private'], True)

    def test_view_private_event_detail(self):
        e1 = Event.objects.create(**self.event_data)

        url = reverse('event-detail', kwargs={'pk': e1.id})
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(response.data['id'], e1.id)
        self.assertEqual(response.data['is_private'], True)

        self.client.force_authenticate(user=self.schmuck)
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTP_404_NOT_FOUND)

    def test_edit_private_event(self):
        e1 = Event.objects.create(**self.event_data)

        update_data = {
            'title': 'Title Changed',
            'description': 'Desc Changed',
            'start_timezone': TIMEZONES[-1],
            'start': (self.event_data['start'] + dt.timedelta(days=10)).isoformat(),
            'end_timezone': TIMEZONES[-1],
            'end': (self.event_data['end'] + dt.timedelta(days=10)).isoformat(),
        }

        url = reverse('event-detail', kwargs={'pk': e1.id})
        self.client.force_authenticate(user=self.schmuck)
        response = self.client.patch(url, update_data)

        self.assertEqual(response.status_code, HTTP_404_NOT_FOUND)
        e1.refresh_from_db()
        self.assertNotEqual(e1.title, update_data['title'])

        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(url, update_data)

        self.assertEqual(response.status_code, HTTP_200_OK)
        e1.refresh_from_db()
        self.assertEqual(e1.title, update_data['title'])

    def test_delete_private_event(self):
        e1 = Event.objects.create(**self.event_data)

        url = reverse('event-detail', kwargs={'pk': e1.id})
        self.client.force_authenticate(user=self.schmuck)
        response = self.client.delete(url)

        self.assertEqual(response.status_code, HTTP_404_NOT_FOUND)
        self.assertEqual(Event.objects.filter(pk=e1.id).count(), 1)

        self.client.force_authenticate(user=self.owner)
        response = self.client.delete(url)

        self.assertEqual(response.status_code, HTTP_204_NO_CONTENT)
        self.assertEqual(Event.objects.filter(pk=e1.id).count(), 0)


class TestEventDateTime(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email='user@example.com', first_name='Test User',
                                                         password='12345678ABC')
        self.client.force_authenticate(user=self.user)
        self.event_data = {
            'title': 'Title',
            'description': 'Desc',
            'start_timezone': TIMEZONES[0],
            'start': dt.datetime.now(pytz.utc).isoformat(),
            'end_timezone': TIMEZONES[0],
            'end': (dt.datetime.now(pytz.utc) + dt.timedelta(days=2)).isoformat(),
            'is_private': False,
        }

    def test_create_event_with_bogus_timezone(self):
        self.event_data['start_timezone'] = 'Bogus/McBogusFace'

        url = reverse('event-list')
        response = self.client.post(url, self.event_data)

        self.assertEqual(response.status_code, HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['start_timezone'][0].code, 'invalid_choice')

    def test_create_event_with_start_later_then_end(self):
        self.event_data['start'] = dt.datetime.now(pytz.utc).isoformat()
        self.event_data['end'] = (dt.datetime.now(pytz.utc) - dt.timedelta(days=2)).isoformat()

        url = reverse('event-list')
        response = self.client.post(url, self.event_data)

        self.assertEqual(response.status_code, HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['non_field_errors'][0].code, 'invalid')

    def test_create_event_with_differing_timezones_for_start_and_end(self):
        tz1 = pytz.timezone('Europe/Kiev')  # UTC+02:00
        tz2 = pytz.timezone('America/New_York')  # UTC-05:00

        # Start > End if we don't account for timezone, but
        # Start < End if timezone is accounted for; should be valid
        self.event_data['start'] = dt.datetime.now(tz1).isoformat()
        self.event_data['end'] = (dt.datetime.now(tz2) + dt.timedelta(hours=1)).isoformat()

        url = reverse('event-list')
        response = self.client.post(url, self.event_data)

        self.assertEqual(response.status_code, HTTP_201_CREATED)
        self.assertEqual(len(Event.objects.filter(pk=response.data['id'])), 1)
        event = Event.objects.get(pk=response.data['id'])
        self.assertTrue(event.start < event.end)

    def test_create_event_with_differing_timezones_for_start_and_end_and_start_later_then_end(self):
        tz1 = pytz.timezone('America/New_York')  # UTC-05:00
        tz2 = pytz.timezone('Europe/Kiev')  # UTC+02:00

        # Start < End if we don't account for timezone, but
        # Start > End if timezone is accounted for; should be invalid
        self.event_data['start'] = dt.datetime.now(tz1).isoformat()
        self.event_data['end'] = (dt.datetime.now(tz2) - dt.timedelta(hours=1)).isoformat()

        url = reverse('event-list')
        response = self.client.post(url, self.event_data)

        self.assertEqual(response.status_code, HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['non_field_errors'][0].code, 'invalid')


class TestImagesEvents(APITestCase):
    def setUp(self) -> None:
        """Setup client, user and event data for tests"""
        self.user = get_user_model().objects.create_user(email='user@example.com', first_name='Test User',
                                                         password='12345678ABC')
        self.client.force_authenticate(user=self.user)

        event_data = {
            'title': 'Title',
            'description': 'Desc',
            'start_timezone': TIMEZONES[0],
            'start': dt.datetime.now(pytz.utc),
            'end_timezone': TIMEZONES[0],
            'end': dt.datetime.now(pytz.utc) + dt.timedelta(days=2),
            'user': self.user,
        }
        self.e1 = Event.objects.create(**event_data)

    def tearDown(self) -> None:
        """Dropping images from file storage"""
        event = getattr(self, 'e1', None)
        if event:
            for img in event.images.all():
                img.drop_all_images()

    @staticmethod
    def _create_temporary_image_file(resolution=(100, 100)):
        """Create temporary file"""
        image = Image.new('RGB', resolution)
        tmp_file = tempfile.NamedTemporaryFile(suffix='.jpg')
        image.save(tmp_file)
        tmp_file.seek(0)
        return tmp_file

    def create_image_via_api(self, image_resolution=(100, 100), position=0):
        """Create event, send create image request, return response data"""
        url = reverse('event-image-list', kwargs={'parent_lookup_event_id': self.e1.id})
        img_data = {
            'image': self.__class__._create_temporary_image_file(image_resolution),
            'position': position,
        }
        resp = self.client.post(url, img_data, format='multipart')
        self.assertEqual(resp.status_code, HTTP_201_CREATED)
        return resp.data

    def test_create_image(self):
        image_dict = self.create_image_via_api()

        self.assertTrue(image_dict.get('image'))
        self.assertEqual(self.e1.images.count(), 1)
        image_obj = self.e1.images.first()
        self.assertTrue(image_obj.id, image_dict['id'])
        self.assertTrue(image_obj.image.storage.exists(image_obj.image.name))

    def test_create_multiple_images_for_event(self):
        self.create_image_via_api(position=0)
        self.create_image_via_api(position=1)

        images = self.e1.images.all()
        self.assertEqual(images.count(), 2)
        for img in images:
            self.assertTrue(img.image.storage.exists(img.image.name))

    def test_view_event_images(self):
        image_dict = self.create_image_via_api()

        url_list = reverse('event-image-list', kwargs={'parent_lookup_event_id': self.e1.id})
        response = self.client.get(url_list)

        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], image_dict['id'])

    def test_view_event_image_detail(self):
        image_dict = self.create_image_via_api()

        url_detail = reverse('event-image-detail', kwargs={'parent_lookup_event_id': self.e1.id, 'pk': image_dict['id']})
        response = self.client.get(url_detail)
        self.assertEqual(response.status_code, HTTP_200_OK)

        self.assertEqual(self.e1.images.count(), 1)
        image_obj = self.e1.images.first()
        self.assertEqual(response.data['id'], image_obj.id)
        self.assertIn(image_obj.image.name, response.data['image'])

    def test_delete_event_image(self):
        image_dict = self.create_image_via_api()

        url_delete = reverse('event-image-detail', kwargs={'parent_lookup_event_id': self.e1.id, 'pk': image_dict['id']})
        response = self.client.delete(url_delete)

        self.assertEqual(response.status_code, HTTP_204_NO_CONTENT)
        self.assertEqual(self.e1.images.all().count(), 0)

    @skip
    def test_main_event_image_is_one_with_lowest_position(self):
        event_url = reverse('event-detail', kwargs={'pk': self.e1.id})

        image1 = self.create_image_via_api(position=1)
        response = self.client.get(event_url)
        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(response.data['main_image']['id'], image1['id'])

        image2 = self.create_image_via_api(position=2)
        response = self.client.get(event_url)
        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(response.data['main_image']['id'], image1['id'])

        image3 = self.create_image_via_api(position=0)
        response = self.client.get(event_url)
        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(response.data['main_image']['id'], image3['id'])

    def test_reorder_images(self):
        image1 = self.create_image_via_api(position=1)
        image2 = self.create_image_via_api(position=2)
        image3 = self.create_image_via_api(position=3)
        self.assertEqual(self.e1.images.count(), 3)
        self.assertEqual(
            list(self.e1.images.order_by('position').values_list('id', flat=True)),
            [image1['id'], image2['id'], image3['id']]
        )

        reorder_url = reverse('event-image-reorder', kwargs={'parent_lookup_event_id': self.e1.id})
        reorder_data = {'ids': [image3['id'], image1['id'], image2['id']]}
        resp = self.client.post(reorder_url, reorder_data)

        self.assertEqual(resp.status_code, HTTP_204_NO_CONTENT)
        self.assertEqual(
            list(self.e1.images.order_by('position').values_list('id', flat=True)),
            reorder_data['ids']
        )

    def test_check_changing_image_resolution(self):
        img_dict = self.create_image_via_api(image_resolution=(4000, 4000))

        img_obj = EventImage.objects.get(id=img_dict['id'])
        max_length_by_side = img_obj.SIZES['large']['resolution'][0]
        self.assertTrue(img_obj.image.width <= max_length_by_side and img_obj.image.height <= max_length_by_side)
