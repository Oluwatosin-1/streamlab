from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages

import requests
from urllib.parse import urlparse


def save_stream_info(strategy, details, response, user=None, *args, **kwargs):
    if not user:
        return

    backend_name = kwargs.get("backend").name 
    from streaming.models import StreamingPlatformAccount 
    if backend_name in ["google-oauth2", "youtube-oauth2"]:
        access_token = response.get("access_token")
        refresh_token = response.get("refresh_token")

        if access_token:
            account, _ = StreamingPlatformAccount.objects.get_or_create(
                user=user, platform="youtube"
            )
            account.access_token = access_token
            if refresh_token:
                account.refresh_token = refresh_token
            account.save() 
            youtube_api_url = "https://www.googleapis.com/youtube/v3/liveStreams"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            }
            params = {"part": "cdn", "mine": "true"}
            youtube_resp = requests.get(youtube_api_url, headers=headers, params=params)

            if youtube_resp.status_code == 200:
                data = youtube_resp.json()
                items = data.get("items")
                if items:
                    ingestion_info = items[0]["cdn"]["ingestionInfo"]
                    stream_key = ingestion_info.get("streamName")
                    if stream_key:
                        account.stream_key = stream_key
                        account.save()

    # ========================================================================
    # FACEBOOK - Optionally create a live_video and parse the returned RTMP URL
    # ========================================================================
    elif backend_name == "facebook":
        access_token = response.get("access_token")
        if access_token:
            account, _ = StreamingPlatformAccount.objects.get_or_create(
                user=user, platform="facebook"
            )
            account.access_token = access_token
            account.save() 
            page_id = "YOUR_PAGE_ID"
            fb_api_url = f"https://graph.facebook.com/v14.0/{page_id}/live_videos"
            params = {
                "access_token": access_token,
                "status": "LIVE_NOW",
                "title": "My Facebook Live Stream",
                "description": "Streaming via social_django pipeline",
            }
            fb_resp = requests.post(fb_api_url, params=params)
            if fb_resp.status_code == 200:
                data = fb_resp.json()
                stream_url = data.get("stream_url")
                if stream_url:
                    parsed = urlparse(stream_url)
                    server_url = f"{parsed.scheme}://{parsed.netloc}/rtmp/"
                    raw_key = parsed.path.replace("/rtmp/", "")
                    # Save it
                    account.rtmp_url = stream_url  # full rtmp URL with key
                    account.stream_key = raw_key  # the portion after /rtmp/
                    account.save()

    # ========================================================================
    # TWITCH - Possibly need to call Helix API for a stream key
    # ========================================================================
    elif backend_name == "twitch":
        access_token = response.get("access_token")
        refresh_token = response.get("refresh_token")
        if access_token:
            account, _ = StreamingPlatformAccount.objects.get_or_create(
                user=user, platform="twitch"
            )
            account.access_token = access_token
            if refresh_token:
                account.refresh_token = refresh_token
            account.save() 
    # ========================================================================
    # INSTAGRAM
    # ========================================================================
    elif backend_name == "instagram":
        access_token = response.get("access_token")
        if access_token:
            account, _ = StreamingPlatformAccount.objects.get_or_create(
                user=user, platform="instagram"
            )
            account.access_token = access_token
            account.save() 
    # ========================================================================
    # TIKTOK, TELEGRAM, or CUSTOM
    # ========================================================================
    elif backend_name in ["tiktok", "telegram", "custom"]:
        access_token = response.get("access_token")
        if access_token:
            account, _ = StreamingPlatformAccount.objects.get_or_create(
                user=user, platform=backend_name
            )
            account.access_token = access_token
            account.save() 