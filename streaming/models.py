# streaming/models.py

from django.db import models
from django.conf import settings 

class StreamingConfiguration(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='streaming_configurations'
    )
    stream_title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    
    # Primary RTMP Info
    rtmp_url = models.URLField(help_text="RTMP endpoint (primary)")
    stream_key = models.CharField(max_length=255, help_text="Unique stream key")

    # Backup Stream
    backup_rtmp_url = models.URLField(blank=True, null=True, help_text="Backup RTMP endpoint")
    backup_stream_key = models.CharField(max_length=255, blank=True, null=True, help_text="Backup stream key")

    # Pull Links
    pull_links = models.TextField(
        blank=True, 
        null=True, 
        help_text="Comma-separated or multi-line list of pull links"
    )

    # Embeds
    embed_player_url = models.URLField(blank=True, null=True, help_text="URL to embed the web player")
    embed_chat_url = models.URLField(blank=True, null=True, help_text="URL to embed multi-platform chat")

    # Additional common fields
    resolution = models.CharField(max_length=50, default='1080p')
    bitrate = models.CharField(max_length=50, default='4500kbps')
    is_active = models.BooleanField(default=False, help_text="Is this config currently active?")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.stream_title} ({self.user.username})"

class StreamingSession(models.Model):
    configuration = models.ForeignKey(
        StreamingConfiguration, 
        on_delete=models.CASCADE, 
        related_name='sessions'
    )
    session_start = models.DateTimeField(auto_now_add=True)
    session_end = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=50,
        choices=[
            ('live', 'Live'),
            ('ended', 'Ended'),
            ('error', 'Error'),
        ],
        default='live'
    )
    viewers_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Session for {self.configuration.stream_title} - {self.status}"

# streaming/models.py (partially)
class ScheduledVideo(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    video_file = models.FileField(upload_to='scheduled_videos/', blank=True, null=True)
    scheduled_time = models.DateTimeField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
