from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages

import requests
from urllib.parse import urlparse

def save_stream_info(strategy, details, response, user=None, *args, **kwargs):
    """
    Custom pipeline to extract additional streaming info from provider responses
    and store them in your StreamingPlatformAccount model.

    For each provider, we show how you might:
    1) Store tokens (access_token, refresh_token)
    2) Optionally make a second API call to retrieve the actual "stream key" or "RTMP URL"
    """

    if not user:
        return

    backend_name = kwargs.get("backend").name

    # Import inside function to avoid potential circular imports
    from streaming.models import StreamingPlatformAccount

    # ========================================================================
    # YOUTUBE - We do an additional call to YouTube Data API to fetch the live stream key
    # ========================================================================
    if backend_name in ["google-oauth2", "youtube-oauth2"]:
        # social_django typically returns 'access_token' in response['access_token']
        access_token = response.get("access_token")
        refresh_token = response.get("refresh_token")

        # 1) Store in StreamingPlatformAccount
        if access_token:
            account, _ = StreamingPlatformAccount.objects.get_or_create(
                user=user, platform="youtube"
            )
            account.access_token = access_token
            if refresh_token:
                account.refresh_token = refresh_token
            account.save()

            # 2) Optional: Retrieve the user’s "live stream key" from YouTube
            #    We'll do a separate API call. The user must have a live broadcast/stream configured.

            # For example:
            # https://developers.google.com/youtube/v3/docs/liveStreams/list
            # You might need these scopes: https://www.googleapis.com/auth/youtube.force-ssl
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
                    # Typically we take the first active liveStream
                    ingestion_info = items[0]["cdn"]["ingestionInfo"]
                    stream_key = ingestion_info.get("streamName")
                    if stream_key:
                        account.stream_key = stream_key
                        account.save()
            # else: handle error or no live stream found

    # ========================================================================
    # FACEBOOK - Optionally create a live_video and parse the returned RTMP URL
    # ========================================================================
    elif backend_name == "facebook":
        # The 'response' dict from social_django might contain 'access_token'
        access_token = response.get("access_token")
        if access_token:
            account, _ = StreamingPlatformAccount.objects.get_or_create(
                user=user, platform="facebook"
            )
            account.access_token = access_token
            account.save()

            # 2) Make an API call to create a new live video and retrieve the RTMP details
            #    This example uses the Graph API: https://developers.facebook.com/docs/live-video-api
            #    You need a page_id or user_id to create the live video. Example:
            #    POST /v14.0/{page_id}/live_videos?access_token={access_token}
            #    response -> "stream_url" with RTMP key included

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
                    # e.g. "rtmp://live-api-s.facebook.com:80/rtmp/123-abc" => parse that out
                    server_url = f"{parsed.scheme}://{parsed.netloc}/rtmp/"
                    raw_key = parsed.path.replace("/rtmp/", "")
                    # Save it
                    account.rtmp_url = stream_url  # full rtmp URL with key
                    account.stream_key = raw_key   # the portion after /rtmp/
                    account.save()

    # ========================================================================
    # TWITCH - Possibly need to call Helix API for a stream key
    # ========================================================================
    elif backend_name == "twitch":
        # social_django typically returns 'access_token', 'refresh_token'
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

            # 2) Retrieve the stream key from Twitch Helix API (if possible).
            #    Actually, Twitch does not always expose the user's streaming key via Helix.
            #    You might require a different approach or store the user's own "Stream Key" manually.

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

            # 2) Officially, Instagram doesn't provide an RTMP key in a standard manner.
            #    People typically rely on 3rd-party solutions or an ephemeral key from Instagram's API (unofficial).
            #    This is just a placeholder.

    # ========================================================================
    # TIKTOK, TELEGRAM, or CUSTOM
    # ========================================================================
    elif backend_name in ["tiktok", "telegram", "custom"]:
        # The actual response structure depends on your custom OAuth configuration.
        access_token = response.get("access_token")
        if access_token:
            account, _ = StreamingPlatformAccount.objects.get_or_create(
                user=user, platform=backend_name
            )
            account.access_token = access_token
            # Possibly do a second request to get a stream key.
            account.save()

    # For any final messages or redirections, do them here if needed.
    # Usually the pipeline returns control to social_django automatically.
