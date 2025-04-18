# Generated by Django 5.1.2 on 2025-03-30 02:06

import django.core.validators
import streaming.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("streaming", "0002_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="streamingconfiguration",
            name="is_active",
            field=models.BooleanField(
                default=False, help_text="Is this configuration active?"
            ),
        ),
        migrations.AlterField(
            model_name="streamingconfiguration",
            name="rtmp_url",
            field=models.CharField(
                help_text="Primary RTMP endpoint",
                max_length=500,
                validators=[
                    django.core.validators.RegexValidator(
                        message="Enter a valid URL. It should start with http, https, rtmp or rtmps.",
                        regex="^(https?|rtmps?|ftp)://.+$",
                    )
                ],
            ),
        ),
        migrations.AlterField(
            model_name="streamingconfiguration",
            name="stream_key",
            field=models.CharField(
                default=streaming.models.generate_stream_key,
                help_text="Unique stream key",
                max_length=255,
            ),
        ),
    ]
