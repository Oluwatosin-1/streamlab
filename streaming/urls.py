from django.urls import path
from django.views.generic import TemplateView

from streaming.views.views import (
    connect_facebook_oauth,
    connect_youtube_oauth,
    facebook_callback,
    studio_enter,
    youtube_callback,
    connect_social,  # new endpoint to support social connections (e.g., Instagram, Telegram)
    go_live,
    local_record_session,
    manage_channels,
    send_chat_message,
    stop_live,
    stream_stats,
    upload_recorded,
    fetch_chat_messages,
)
from streaming.views.streaming_views import (
    StreamingConfigurationListView,
    StreamingConfigurationCreateView,
    StreamingConfigurationUpdateView,
    StreamingConfigurationDeleteView,
    StreamingConfigurationDetailView,
    start_streaming_session,
    end_streaming_session,
    StreamingSessionDetailView,
)
from streaming.views.scheduling_views import (
    ScheduledVideoListView,
    ScheduledVideoCreateView,
    ScheduledVideoUpdateView,
    ScheduledVideoDeleteView,
    publish_scheduled_video,
)
from streaming.views.chat_views import chat_room

app_name = "streaming"

urlpatterns = [
    # OAuth endpoints
    path("oauth/youtube/connect/", connect_youtube_oauth, name="connect_youtube_oauth"),
    path("youtube/callback/", youtube_callback, name="youtube_callback"),
    path("oauth/facebook/connect/", connect_facebook_oauth, name="connect_facebook_oauth"),
    path("oauth/facebook/callback/", facebook_callback, name="facebook_callback"),
    
    # New endpoint for social connections (e.g., Instagram, Telegram)
    path("oauth/<str:platform>/connect/", connect_social, name="connect_social"),
     # New endpoint for stream selection modal
    path("new_stream/", TemplateView.as_view(template_name="streaming/new_stream.html"), name="new_stream"),
    
    # Streaming configuration endpoints
    path("configurations/", StreamingConfigurationListView.as_view(), name="config_list"),
    path("configuration/create/", StreamingConfigurationCreateView.as_view(), name="config_create"),
    path("configuration/<int:pk>/update/", StreamingConfigurationUpdateView.as_view(), name="config_update"),
    path("configuration/<int:pk>/delete/", StreamingConfigurationDeleteView.as_view(), name="config_delete"),
    path("configuration/<int:pk>/", StreamingConfigurationDetailView.as_view(), name="config_detail"),
    
    # Streaming session endpoints
    path("configuration/<int:pk>/start_session/", start_streaming_session, name="start_session"),
    path("session/<int:session_id>/end/", end_streaming_session, name="end_session"),
    path("channels/", manage_channels, name="manage_channels"),
    path("session/<int:session_id>/", StreamingSessionDetailView.as_view(), name="session_detail"),
    
    # Scheduled video endpoints
    path("scheduled_videos/", ScheduledVideoListView.as_view(), name="scheduled_video_list"),
    path("scheduled_videos/create/", ScheduledVideoCreateView.as_view(), name="scheduled_video_create"),
    path("scheduled_videos/<int:pk>/update/", ScheduledVideoUpdateView.as_view(), name="scheduled_video_update"),
    path("scheduled_videos/<int:pk>/delete/", ScheduledVideoDeleteView.as_view(), name="scheduled_video_delete"),
    path("scheduled_videos/<int:pk>/publish/", publish_scheduled_video, name="scheduled_video_publish"),
    
    # Chat endpoints
    path("session/<int:session_id>/chat/", chat_room, name="session_chat"),
    path("session/<int:session_id>/chat/send/", send_chat_message, name="send_chat_message"),
    path("session/<int:session_id>/chat/fetch/", fetch_chat_messages, name="fetch_chat_messages"),
    
    # Recording and additional live control endpoints
    path("record/local/", local_record_session, name="local_record_session"),
    path("record/upload/", upload_recorded, name="upload_recorded"),
    path("configuration/<int:config_id>/go_live/", go_live, name="go_live"),
    path("session/<int:session_id>/stop_live/", stop_live, name="stop_live"),
    path("session/<int:session_id>/stats/", stream_stats, name="stream_stats"),
    
    # **New Studio Endpoint:**
    path("studio/", studio_enter, name="studio"),
]
