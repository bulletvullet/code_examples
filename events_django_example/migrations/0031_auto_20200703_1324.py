# Generated by Django 2.2 on 2020-07-03 13:24

from django.db import migrations, models
import django.db.models.deletion
import events.models
import prism.utils.mixins


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0030_auto_20200630_1033'),
    ]

    operations = [
        migrations.CreateModel(
            name='EventCategoryImage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to=events.models.EventCategoryImage.get_upload_path)),
                ('cropped_image', models.ImageField(upload_to=events.models.EventCategoryImage.get_upload_path)),
                ('is_active', models.BooleanField(default=True)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='events.EventCategory')),
            ],
            options={
                'verbose_name_plural': 'category images',
            },
            bases=(prism.utils.mixins.ImageHandlerMixin, models.Model),
        ),
        migrations.AddField(
            model_name='event',
            name='category_image',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='events.EventCategoryImage'),
        ),
    ]
