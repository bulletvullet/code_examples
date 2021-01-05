# Generated by Django 2.2.9 on 2020-02-04 16:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0002_auto_20200131_1519'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='external_id',
            field=models.CharField(db_index=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='event',
            name='provider',
            field=models.CharField(max_length=32, null=True),
        ),
        migrations.AlterField(
            model_name='event',
            name='is_private',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterUniqueTogether(
            name='event',
            unique_together={('provider', 'external_id')},
        ),
    ]