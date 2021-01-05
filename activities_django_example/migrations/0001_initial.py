# Generated by Django 3.0.8 on 2020-11-24 08:36

from django.conf import settings
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('target_id', models.PositiveIntegerField()),
                ('data', django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict)),
                ('activity_type', models.CharField(choices=[('object_created', 'Object created'), ('object_changed', 'Object changed'), ('object_deleted', 'Object deleted')], max_length=30)),
                ('created_at', models.DateTimeField(auto_now=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('target_ct', models.ForeignKey(limit_choices_to={'model__in': ('Task', 'Subtask', 'Epic', 'Sprint', 'Project')}, on_delete=django.db.models.deletion.PROTECT, to='contenttypes.ContentType')),
            ],
            options={
                'verbose_name_plural': 'ActivityLogs',
            },
        ),
    ]
