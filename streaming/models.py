from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator
import uuid

# Define a regex that accepts URLs starting with http, https, rtmp, or rtmps.
rtmp_url_regex = r'^(https?|rtmps?|ftp)://.+$'
rtmp_url_validator = RegexValidator(
    regex=rtmp_url_regex,
    message="Enter a valid URL. It should start with http, https, rtmp or rtmps."
)

PLATFORM_CHOICES = [
    ('youtube', 'YouTube'),
    ('facebook', 'Facebook'),
    ('twitch', 'Twitch'),
    ('instagram', 'Instagram'),
    ('tiktok', 'TikTok'),
    ('telegram', 'Telegram'),
    ('custom', 'Custom'),
]

class StreamingConfiguration(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='streaming_configurations'
    )
    stream_title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    
    # Tie the configuration to a specific platform
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES, default='custom')
    
    # Primary RTMP Info
    rtmp_url = models.CharField(
        max_length=500,
        help_text="RTMP endpoint (primary)",
        validators=[rtmp_url_validator]
    )
    stream_key = models.CharField(max_length=255, help_text="Unique stream key")

    # Backup Stream (optional)
    backup_rtmp_url = models.CharField(
        max_length=500,
        blank=True, 
        null=True, 
        help_text="Backup RTMP endpoint",
        validators=[rtmp_url_validator]
    )
    backup_stream_key = models.CharField(max_length=255, blank=True, null=True, help_text="Backup stream key")

    # Pull Links (as plain text)
    pull_links = models.TextField(
        blank=True, 
        null=True, 
        help_text="Comma-separated or multi-line list of pull links"
    )

    # Embeds for web player and multi-platform chat
    embed_player_url = models.CharField(
        max_length=500,
        blank=True, 
        null=True, 
        help_text="URL to embed the web player",
        validators=[rtmp_url_validator]
    )
    embed_chat_url = models.CharField(
        max_length=500,
        blank=True, 
        null=True, 
        help_text="URL to embed multi-platform chat",
        validators=[rtmp_url_validator]
    )

    # Additional common fields
    resolution = models.CharField(max_length=50, default='1080p')
    bitrate = models.CharField(max_length=50, default='4500kbps')
    is_active = models.BooleanField(default=False, help_text="Is this config currently active?")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.stream_title} ({self.user.username}) - {self.platform}"

    def get_full_rtmp_url(self):
        """
        Helper method to get the full RTMP URL (including the stream key).
        """
        return f"{self.rtmp_url}/{self.stream_key}"


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
    
    # Optionally, you can add a field for storing error messages or logs
    error_message = models.TextField(blank=True, null=True, help_text="Error details if session encounters issues")

    def __str__(self):
        return f"Session for {self.configuration.stream_title} - {self.status}"


class ScheduledVideo(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    video_file = models.FileField(upload_to='scheduled_videos/', blank=True, null=True)
    scheduled_time = models.DateTimeField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Optionally, add a field to track if the video has been published/live
    is_published = models.BooleanField(default=False)

    def __str__(self):
        return self.title


class ChatMessage(models.Model):
    streaming_session = models.ForeignKey(
        StreamingSession,
        on_delete=models.CASCADE,
        related_name="chat_messages",
        null=True,  # allow null values
        blank=True  # optional: allow blank in forms
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="chat_messages"
    )
    text = models.TextField(help_text="The content of the chat message")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Time when the message was created")

    def __str__(self):
        return f"{self.user.username}: {self.text[:30]}"


class StreamingPlatformAccount(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="streaming_platform_accounts"
    )
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES)
    account_username = models.CharField(max_length=255, help_text="Username or channel name on the platform")
    
    # New fields added:
    rtmp_url = models.CharField(max_length=500, blank=True, null=True, help_text="RTMP URL for the account")
    stream_key = models.CharField(max_length=255, blank=True, null=True, help_text="Stream key for the account")
    display_name = models.CharField(max_length=255, blank=True, null=True, help_text="Display name for the account")
    
    access_token = models.CharField(max_length=500, blank=True, null=True)
    refresh_token = models.CharField(max_length=500, blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.platform} ({self.account_username})"