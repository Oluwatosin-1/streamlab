from django.urls import path

from .views import analytics, video_storage
 
from .views import dashboard, dashboard_drafts, dashboard_scheduled, dashboard_settings, past_streams

app_name = "dashboard"

urlpatterns = [
    path("/", dashboard, name="index"),
    path("drafts/", dashboard_drafts, name="drafts"),
    path("scheduled/", dashboard_scheduled, name="scheduled"),
    path("past-streams/", past_streams, name="past_streams"),
    
    path("past-streams/", past_streams, name="past_streams"),
    path("video-storage/", video_storage, name="video_storage"),
    path("analytics/", analytics, name="analytics"),
    path("settings/", dashboard_settings, name="settings"),
]
