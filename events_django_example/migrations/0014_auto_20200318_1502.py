# Generated by Django 2.2 on 2020-03-18 15:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0013_auto_20200305_1259'),
    ]

    operations = [
        migrations.RunSQL(
            (
                "UPDATE events_attendance SET status=1 where status = 'A';"
                "UPDATE events_attendance SET status=2 where status = 'M';"
                "UPDATE events_attendance SET status=3 where status = 'I';"
                "UPDATE events_attendance SET status=4 where status = 'D';"
            ), reverse_sql=(
                "UPDATE events_attendance SET status='A' where status = '1';"
                "UPDATE events_attendance SET status='M' where status = '2';"
                "UPDATE events_attendance SET status='I' where status = '3';"
                "UPDATE events_attendance SET status='D' where status = '4';"
            )
        ),
        migrations.AlterField(
            model_name='attendance',
            name='status',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Attending'), (2, 'Maybe'), (3, 'Invite pending'), (4, 'Declined')], default=1),
        ),
    ]
