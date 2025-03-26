import json
import os
import requests
from django.conf import settings
from urllib.parse import urlencode, urlparse

def load_google_client_secrets():
    """
    Load the Google OAuth client secrets from a JSON file.
    The file path should be set in settings as GOOGLE_OAUTH_CLIENT_SECRETS_FILE.
    """
    secrets_file = settings.GOOGLE_OAUTH_CLIENT_SECRETS_FILE
    try:
        with open(secrets_file, 'r') as f:
            secrets = json.load(f)
        return secrets.get("web", {})
    except Exception as e:
        raise Exception(f"Failed to load Google client secrets: {e}")

def build_youtube_auth_url():
    """
    Build the Google OAuth URL for YouTube using the client secrets.
    """
    secrets = load_google_client_secrets()
    client_id = secrets.get("client_id")
    # Use the first redirect URI from the JSON file.
    redirect_uri = secrets.get("redirect_uris", [])[0]
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": (
            "https://www.googleapis.com/auth/youtube.readonly "
            "https://www.googleapis.com/auth/youtube.force-ssl"
        ),
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{base_url}?{urlencode(params)}"

def exchange_youtube_code_for_token(auth_code):
    """
    Exchange an auth_code for tokens via Google's OAuth token endpoint using secrets.
    Returns a dict with access_token, refresh_token, etc. or None on failure.
    """
    secrets = load_google_client_secrets()
    client_id = secrets.get("client_id")
    client_secret = secrets.get("client_secret")
    redirect_uri = secrets.get("redirect_uris", [])[0]
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": auth_code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    response = requests.post(token_url, data=data)
    if response.status_code == 200:
        return response.json()
    return None

def fetch_youtube_stream_key(access_token):
    """
    Fetch the user's active live stream key from YouTube.
    Returns the 'streamName' (the RTMP key) if found, else None.
    """
    url = "https://www.googleapis.com/youtube/v3/liveStreams"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    params = {"part": "cdn", "mine": "true"}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        if data.get("items"):
            ingestion_info = data["items"][0]["cdn"]["ingestionInfo"]
            return ingestion_info.get("streamName")
    return None

def build_facebook_auth_url():
    """
    Build the Facebook OAuth URL using your settings.
    """
    base_url = "https://www.facebook.com/v14.0/dialog/oauth"
    params = {
        "client_id": settings.FACEBOOK_APP_ID,
        "redirect_uri": settings.FACEBOOK_REDIRECT_URI,
        "response_type": "code",
        "scope": "publish_video",  # add additional scopes if needed
    }
    return f"{base_url}?{urlencode(params)}"

def exchange_facebook_code_for_token(auth_code):
    """
    Exchange an auth_code for a Facebook access token.
    Returns a dict with access_token or None on failure.
    """
    token_url = "https://graph.facebook.com/v14.0/oauth/access_token"
    params = {
        "client_id": settings.FACEBOOK_APP_ID,
        "client_secret": settings.FACEBOOK_APP_SECRET,
        "code": auth_code,
        "redirect_uri": settings.FACEBOOK_REDIRECT_URI,
    }
    response = requests.get(token_url, params=params)
    if response.status_code == 200:
        return response.json()
    return None

def fetch_facebook_stream_key(access_token):
    """
    Create (or retrieve) a live video on Facebook and return a dict with:
      - full_rtmp_url: the complete RTMP URL (server + key and parameters)
      - server_url: the RTMP server endpoint
      - stream_key: the extracted stream key
    """
    # Replace with your actual page ID logic (this is a placeholder)
    page_id = "123456789"
    url = f"https://graph.facebook.com/v14.0/{page_id}/live_videos"
    params = {
        "access_token": access_token,
        "status": "LIVE_NOW",
        # Optionally: "title": "My Awesome Stream", "description": "Live streaming", etc.
    }
    response = requests.post(url, params=params)
    if response.status_code == 200:
        data = response.json()
        stream_url = data.get("stream_url")
        if stream_url:
            parsed = urlparse(stream_url)
            server_url = f"{parsed.scheme}://{parsed.netloc}/rtmp/"
            raw_key = parsed.path.replace("/rtmp/", "")
            return {
                "full_rtmp_url": stream_url,
                "server_url": server_url,
                "stream_key": raw_key,
            }
    return None
