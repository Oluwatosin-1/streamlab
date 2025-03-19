# streaming/utils.py

import requests
from django.conf import settings
from urllib.parse import urlencode

def build_youtube_auth_url():
    """
    Build the Google OAuth URL for YouTube, using your client ID & redirect URI from settings.
    """
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": settings.YOUTUBE_CLIENT_ID,
        "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/youtube.force-ssl",
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{base_url}?{urlencode(params)}"

def exchange_youtube_code_for_token(auth_code):
    """
    Exchange an auth_code for tokens via Google's OAuth token endpoint.
    Returns a dict with access_token, refresh_token, etc. or None on failure.
    """
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": settings.YOUTUBE_CLIENT_ID,
        "client_secret": settings.YOUTUBE_CLIENT_SECRET,
        "code": auth_code,
        "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    r = requests.post(token_url, data=data)
    if r.status_code == 200:
        return r.json()
    return None

def build_facebook_auth_url():
    """
    Build the Facebook OAuth URL for your app, requesting 'publish_video' or needed scopes.
    """
    base_url = "https://www.facebook.com/v14.0/dialog/oauth"
    params = {
        "client_id": settings.FACEBOOK_APP_ID,
        "redirect_uri": settings.FACEBOOK_REDIRECT_URI,
        "response_type": "code",
        "scope": "publish_video",  # add any additional scopes if needed
    }
    return f"{base_url}?{urlencode(params)}"

def exchange_facebook_code_for_token(auth_code):
    """
    Exchange an auth_code for tokens from Facebook's OAuth endpoint.
    Returns a dict with access_token or None on failure.
    """
    token_url = "https://graph.facebook.com/v14.0/oauth/access_token"
    params = {
        "client_id": settings.FACEBOOK_APP_ID,
        "client_secret": settings.FACEBOOK_APP_SECRET,
        "code": auth_code,
        "redirect_uri": settings.FACEBOOK_REDIRECT_URI,
    }
    r = requests.get(token_url, params=params)
    if r.status_code == 200:
        return r.json()
    return None

def fetch_youtube_stream_key(access_token):
    """
    Fetch user's active live stream key from the YouTube Data API v3.
    Returns the 'streamName' if found, else None.
    """
    url = "https://www.googleapis.com/youtube/v3/liveStreams"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    # 'mine=true' fetches the user's streams
    r = requests.get(url, headers=headers, params={"part": "cdn", "mine": "true"})
    if r.status_code == 200:
        data = r.json()
        if data.get("items"):
            ingestion_info = data["items"][0]["cdn"]["ingestionInfo"]
            return ingestion_info.get("streamName")
    return None

def fetch_facebook_stream_key(access_token):
    """
    Attempt to retrieve a persistent or ephemeral RTMP URL from Facebook.
    Typically you need a page_id. For demonstration, we use a placeholder.
    """
    page_id = "123456789"  # Replace with real page logic
    url = f"https://graph.facebook.com/v14.0/{page_id}/live_videos"
    params = {
        "access_token": access_token,
        "status": "LIVE_NOW",
    }
    r = requests.post(url, params=params)
    if r.status_code == 200:
        data = r.json()
        return data.get("stream_url"), data.get("secure_stream_url")
    return None, None
