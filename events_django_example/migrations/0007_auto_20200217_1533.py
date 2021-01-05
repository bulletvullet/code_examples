# Generated by Django 2.2 on 2020-02-17 15:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0006_auto_20200218_1038'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='event',
            name='main_image',
        ),
        migrations.AddField(
            model_name='eventimage',
            name='position',
            field=models.PositiveSmallIntegerField(default=0),
            preserve_default=False,
        ),
    ]