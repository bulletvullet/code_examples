# Generated by Django 2.2 on 2020-05-14 15:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0025_auto_20200507_1358'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventcategory',
            name='regular_events_percentage',
            field=models.SmallIntegerField(default=80),
        ),
    ]
