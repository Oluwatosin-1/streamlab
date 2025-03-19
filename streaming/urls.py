# streaming/urls.py

from django.urls import path
from . import views

app_name = "streaming"

urlpatterns = [
    # Social connect flow
    path("connect/<str:platform>/", views.connect_social_accounts, name="connect_social"),
    path("connect/youtube/oauth/", views.connect_youtube_oauth, name="connect_youtube_oauth"),
    path("connect/youtube/callback/", views.youtube_callback, name="youtube_callback"),
    path("connect/facebook/oauth/", views.connect_facebook_oauth, name="connect_facebook_oauth"),
    path("connect/facebook/callback/", views.facebook_callback, name="facebook_callback"),

    # Streaming configs
    path("configs/", views.streaming_config_list, name="config_list"),
    path("configs/new/", views.create_streaming_config, name="create_config"),
    path("rtmp/setup/", views.rtmp_setup, name="rtmp_setup"),
    path("rtmp/draft/", views.rtmp_draft, name="rtmp_draft"),
    path("settings/", views.stream_settings, name="stream_settings"),

    # Studio flows
    path("studio/", views.studio, name="studio"),
    path("studio/draft/", views.studio_draft, name="studio_draft"),
    path("studio/enter/", views.studio_enter, name="studio_enter"),
    path("studio/go_live/", views.go_live, name="go_live"),
    path("studio/stop_live/", views.stop_live, name="stop_live"),

    # Manage channels
    path("channels/", views.manage_channels, name="manage_channels"),

    # Video or playlist & local record endpoints
    path("schedule_video/", views.schedule_video_session, name="schedule_video_session"),
    path("local_record/", views.local_record_session, name="local_record_session"),

    # Upload local recordings
    path("upload_recorded/", views.upload_recorded, name="upload_recorded"),
]
