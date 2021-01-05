# Generated by Django 2.2 on 2020-03-31 13:11

from django.db import migrations, models
import events.models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0018_eventcategory_icon'),
    ]

    operations = [
        migrations.AlterField(
            model_name='eventcategory',
            name='icon',
            field=models.ImageField(upload_to=events.models.EventCategory.get_upload_path),
        ),
    ]