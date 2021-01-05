# Generated by Django 2.2.9 on 2020-02-18 10:38

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('events', '0005_auto_20200207_1535'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='event',
            unique_together={('user', 'provider', 'external_id')},
        ),
    ]
