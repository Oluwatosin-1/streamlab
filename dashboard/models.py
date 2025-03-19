# dashboard/models.py

from django.db import models
from django.conf import settings

class DashboardSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='dashboard_settings'
    )
    default_streaming_quality = models.CharField(
        max_length=50, 
        default='1080p', 
        help_text="Default quality for streaming sessions"
    )
    theme = models.CharField(
        max_length=20, 
        choices=[('light', 'Light'), ('dark', 'Dark')],
        default='light'
    )
    notifications_enabled = models.BooleanField(default=True)
    language_preference = models.CharField(max_length=10, default='en')
    # Optional: store any additional customization as JSON
    custom_layout = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Dashboard Settings"
