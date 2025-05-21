from django.urls import path
from django.views.generic import TemplateView

from streaming.views.srs_hooks import srs_on_publish, srs_on_unpublish
from streaming.views.streaming_views import (
    StreamingConfigurationListView,
    StreamingConfigurationCreateView,
    StreamingConfigurationUpdateView,
    StreamingConfigurationDeleteView,
    StreamingConfigurationDetailView,
    check_stream_status,
    connect_social,
    fetch_chat_messages,
    go_live,
    local_record_session,
    manage_channels,
    offer,
    send_chat_message,
    srs_console,
    start_streaming_session,
    end_streaming_session,
    StreamingSessionDetailView,
    studio_enter,
    upload_recorded,
    validate_social_accounts,
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
    # New endpoint for social connections (e.g., Instagram, Telegram)
    path("oauth/<str:platform>/connect/", connect_social, name="connect_social"),
    # New endpoint for stream selection modal
    path(
        "new_stream/",
        TemplateView.as_view(template_name="streaming/new_stream.html"),
        name="new_stream",
    ),
    # Streaming configuration endpoints
    path(
        "configurations/", StreamingConfigurationListView.as_view(), name="config_list"
    ),
    path(
        "configuration/create/",
        StreamingConfigurationCreateView.as_view(),
        name="config_create",
    ),
    path(
        "configuration/<int:pk>/update/",
        StreamingConfigurationUpdateView.as_view(),
        name="config_update",
    ),
    path(
        "configuration/<int:pk>/delete/",
        StreamingConfigurationDeleteView.as_view(),
        name="config_delete",
    ),
    path(
        "configuration/<int:pk>/",
        StreamingConfigurationDetailView.as_view(),
        name="config_detail",
    ),
    # Streaming session endpoints
    path(
        "configuration/<int:pk>/start_session/",
        start_streaming_session,
        name="start_session",
    ),
    path("session/<int:session_id>/end/", end_streaming_session, name="end_session"),
    path("channels/", manage_channels, name="manage_channels"),
    path(
        "session/<int:session_id>/",
        StreamingSessionDetailView.as_view(),
        name="session_detail",
    ),
    # Scheduled video endpoints
    path(
        "scheduled_videos/",
        ScheduledVideoListView.as_view(),
        name="scheduled_video_list",
    ),
    path(
        "scheduled_videos/create/",
        ScheduledVideoCreateView.as_view(),
        name="scheduled_video_create",
    ),
    path(
        "scheduled_videos/<int:pk>/update/",
        ScheduledVideoUpdateView.as_view(),
        name="scheduled_video_update",
    ),
    path(
        "scheduled_videos/<int:pk>/delete/",
        ScheduledVideoDeleteView.as_view(),
        name="scheduled_video_delete",
    ),
    path(
        "scheduled_videos/<int:pk>/publish/",
        publish_scheduled_video,
        name="scheduled_video_publish",
    ),
    # Chat endpoints
    path("session/<int:session_id>/chat/", chat_room, name="session_chat"),
    path(
        "session/<int:session_id>/chat/send/",
        send_chat_message,
        name="send_chat_message",
    ),
    path(
        "fetch_chat_messages/<uuid:session_id>/",
        fetch_chat_messages,
        name="fetch_chat_messages",
    ),
    # path("session/<int:session_id>/chat/fetch/", fetch_chat_messages, name="fetch_chat_messages"),
    path(
        "validate_social_accounts/",
        validate_social_accounts,
        name="validate_social_accounts",
    ),
    # Recording and additional live control endpoints
    path("record/local/", local_record_session, name="local_record_session"),
    path("record/upload/", upload_recorded, name="upload_recorded"),
    # path("session/<int:session_id>/stop_live/", stop_live, name="stop_live"),
    # path("session/<int:session_id>/stats/", stream_stats, name="stream_stats"),
    path(
        "check_stream_status/<str:stream_key>/",
        check_stream_status,
        name="check_stream_status",
    ),
    path("go-live/<int:config_id>/", go_live, name="go_live"),
    path("stop-live/<int:session_id>/", end_streaming_session, name="stop_live"),
    path("api/srs/on_publish/", srs_on_publish, name="srs_on_publish"),
    path("api/srs/on_unpublish/", srs_on_unpublish, name="srs_on_unpublish"),
    # **New Studio Endpoint:**
    path("studio/", studio_enter, name="studio"),
    path("console/", srs_console, name="srs_console"),
    path("offer/", offer, name="offer"),
]
