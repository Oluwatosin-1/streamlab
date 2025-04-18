# Generated by Django 5.1.2 on 2025-04-01 21:12

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("streaming", "0003_alter_streamingconfiguration_is_active_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="StreamingRelayStatus",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("platform", models.CharField(max_length=100)),
                ("rtmp_url", models.URLField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("success", "Success"),
                            ("error", "Error"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("last_attempted", models.DateTimeField(auto_now=True)),
                ("log_summary", models.TextField(blank=True, null=True)),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="relay_statuses",
                        to="streaming.streamingsession",
                    ),
                ),
            ],
        ),
    ]
