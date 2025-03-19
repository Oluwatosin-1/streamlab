from django.contrib.auth.models import AbstractUser
from django.db import models

from streamlab import settings

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)

    subscription_plan = models.CharField(
        max_length=50,
        choices=[("free", "Free"), ("basic", "Basic"), ("pro", "Pro")],
        default="free",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.username 
    
class SocialAccount(models.Model):
    PLATFORM_CHOICES = [
        ("youtube", "YouTube"),
        ("facebook", "Facebook"),
        ("twitch", "Twitch"),
        ("instagram", "Instagram"),
        ("tiktok", "Tiktok"),
        ("telegram", "Telegram"), 
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='social_accounts')
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES)

    # Generic tokens
    access_token = models.CharField(max_length=255, blank=True, null=True)
    refresh_token = models.CharField(max_length=255, blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)  # <— Add this

    # If each platform can store a distinct RTMP URL or stream key
    rtmp_url = models.URLField(blank=True, null=True)
    stream_key = models.CharField(max_length=255, blank=True, null=True)

    # Optional display name for UI
    display_name = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.get_platform_display()}"
