from django.contrib import admin
from .models import (
    StreamingConfiguration,
    StreamingSession,
    ScheduledVideo,
    ChatMessage,
    StreamingPlatformAccount,
)


@admin.register(StreamingConfiguration)
class StreamingConfigurationAdmin(admin.ModelAdmin):
    list_display = ("stream_title", "user", "platform", "is_active", "created_at")
    search_fields = ("stream_title", "user__username")
    list_filter = ("platform", "is_active", "created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(StreamingSession)
class StreamingSessionAdmin(admin.ModelAdmin):
    list_display = (
        "configuration",
        "status",
        "session_start",
        "session_end",
        "viewers_count",
    )
    search_fields = ("configuration__stream_title", "configuration__user__username")
    list_filter = ("status", "session_start", "session_end")
    ordering = ("-session_start",)


@admin.register(ScheduledVideo)
class ScheduledVideoAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "scheduled_time", "is_published", "created_at")
    search_fields = ("title", "user__username")
    list_filter = ("is_published", "scheduled_time", "created_at")
    ordering = ("-scheduled_time",)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("user", "streaming_session", "created_at")
    search_fields = (
        "user__username",
        "streaming_session__configuration__stream_title",
        "text",
    )
    list_filter = ("created_at",)
    ordering = ("-created_at",)


@admin.register(StreamingPlatformAccount)
class StreamingPlatformAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "platform", "account_username", "created_at", "updated_at")
    search_fields = ("user__username", "account_username", "platform")
    list_filter = ("platform", "created_at")
    ordering = ("-created_at",)
