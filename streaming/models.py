import uuid
from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator

# Regex to validate URLs starting with http, https, rtmp, rtmps or ftp.
rtmp_url_regex = r'^(https?|rtmps?|ftp)://.+$'
rtmp_url_validator = RegexValidator(
    regex=rtmp_url_regex,
    message="Enter a valid URL. It should start with http, https, rtmp or rtmps."
)

def generate_stream_key():
    """Generates a unique stream key (32-character hex)."""
    return uuid.uuid4().hex

# Streaming platform choices.
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
    """
    Stores configuration details for a single streaming setup.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='streaming_configurations'
    )
    stream_title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES, default='custom')
    rtmp_url = models.CharField(
        max_length=500,
        help_text="Primary RTMP endpoint",
        validators=[rtmp_url_validator]
    )
    stream_key = models.CharField(
        max_length=255,
        help_text="Unique stream key",
        default=generate_stream_key
    )
    backup_rtmp_url = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Backup RTMP endpoint",
        validators=[rtmp_url_validator]
    )
    backup_stream_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Backup stream key"
    )
    pull_links = models.TextField(
        blank=True,
        null=True,
        help_text="Comma-separated or multi-line list of pull links"
    )
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
    resolution = models.CharField(max_length=50, default='1080p')
    bitrate = models.CharField(max_length=50, default='4500kbps')
    is_active = models.BooleanField(
        default=False,
        help_text="Is this configuration active?"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.stream_title} ({self.user.username}) - {self.platform}"

    def get_full_rtmp_url(self):
        """Returns the complete RTMP URL by appending the stream key."""
        return f"{self.rtmp_url}/{self.stream_key}"


class StreamingSession(models.Model):
    """
    Represents a live or ended streaming session linked to a StreamingConfiguration.
    """
    STATUS_CHOICES = [
        ('live', 'Live'),
        ('ended', 'Ended'),
        ('error', 'Error'),
    ]

    configuration = models.ForeignKey(
        StreamingConfiguration,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    session_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    session_start = models.DateTimeField(auto_now_add=True)
    session_end = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='live')
    viewers_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error details if session encounters issues"
    )

    def __str__(self):
        return f"Session {self.session_uuid} for {self.configuration.stream_title} - {self.status}"

    def end_session(self, mark_error=False, error_message=None):
        """Mark the session as ended (or errored) and set the end time."""
        if mark_error:
            self.status = "error"
            if error_message:
                self.error_message = error_message
        else:
            self.status = "ended"
        # Use the current time for session_end
        self.session_end = timezone.now()
        self.save()


class ScheduledVideo(models.Model):
    """
    Used for scheduling a video to be streamed or uploaded later.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    video_file = models.FileField(upload_to='scheduled_videos/', blank=True, null=True)
    scheduled_time = models.DateTimeField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=False)

    def __str__(self):
        return self.title


class ChatMessage(models.Model):
    """
    Represents a chat message in a live streaming session.
    """
    streaming_session = models.ForeignKey(
        StreamingSession,
        on_delete=models.CASCADE,
        related_name="chat_messages",
        blank=True,
        null=True
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
    """
    Stores OAuth tokens and RTMP details for a user's streaming platform account.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="streaming_platform_accounts"
    )
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES)
    account_username = models.CharField(
        max_length=255,
        help_text="Username or channel name on the platform"
    )
    rtmp_url = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="RTMP URL for the account"
    )
    stream_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Stream key for the account"
    )
    display_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Display name for the account"
    )
    access_token = models.CharField(max_length=500, blank=True, null=True)
    refresh_token = models.CharField(max_length=500, blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.platform} ({self.account_username})"
    
class StreamingRelayStatus(models.Model):
    session = models.ForeignKey(StreamingSession, on_delete=models.CASCADE, related_name="relay_statuses")
    platform = models.CharField(max_length=100)
    rtmp_url = models.URLField()
    status = models.CharField(max_length=20, choices=[("pending", "Pending"), ("success", "Success"), ("error", "Error")], default="pending")
    last_attempted = models.DateTimeField(auto_now=True)
    log_summary = models.TextField(blank=True, null=True)
