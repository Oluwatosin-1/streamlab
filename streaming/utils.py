# streaming/utils.py
import requests
from django.conf import settings
from urllib.parse import urlencode, urlparse, parse_qs

def build_youtube_auth_url():
    """
    Build the Google OAuth URL for YouTube, using your client ID & redirect URI from settings.
    """
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": settings.YOUTUBE_CLIENT_ID,
        "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
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
    params = {"part": "cdn", "mine": "true"}
    r = requests.get(url, headers=headers, params=params)
    if r.status_code == 200:
        data = r.json()
        if data.get("items"):
            ingestion_info = data["items"][0]["cdn"]["ingestionInfo"]
            return ingestion_info.get("streamName")  # the actual "key"
    return None

def build_facebook_auth_url():
    """
    Build the Facebook OAuth URL for your app, requesting 'publish_video' or any needed scopes.
    """
    base_url = "https://www.facebook.com/v14.0/dialog/oauth"
    params = {
        "client_id": settings.FACEBOOK_APP_ID,
        "redirect_uri": settings.FACEBOOK_REDIRECT_URI,
        "response_type": "code",
        "scope": "publish_video",  # add other scopes if needed
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
        return r.json()  # includes 'access_token'
    return None

def fetch_facebook_stream_key(access_token):
    """
    Create (or retrieve) a live video on Facebook, returning the RTMP server + ephemeral key.

    By default, Facebook returns an entire 'stream_url' that includes the server, key, and query params.
    If you want them separately, you can parse out the 'server_url' vs. the 'stream_key'.
    
    For ephemeral streams, the 'stream_url' typically looks like:
      rtmps://live-api-s.facebook.com:443/rtmp/<FB-...>?ds=1&s_sw=0&s_vt=api-s...
    
    If you prefer to store them separately:
      server_url = "rtmps://live-api-s.facebook.com:443/rtmp/"
      stream_key = "FB-1086682360139355-0-Ab0PmF0mtUYdmjfFFvQxRUz5"
    """
    # Replace with your actual page ID logic, or if streaming to a user's profile, adjust accordingly.
    page_id = "123456789"
    url = f"https://graph.facebook.com/v14.0/{page_id}/live_videos"
    # 'status=LIVE_NOW' => ephemeral. For persistent, you might add "persistent_stream_key": True, etc.
    params = {
        "access_token": access_token,
        "status": "LIVE_NOW",
        # Optionally: "title": "My Awesome Stream", "description": "Testing ephemeral keys", ...
    }
    r = requests.post(url, params=params)
    if r.status_code == 200:
        data = r.json()
        # Typically returns 'id' (the live video ID), plus 'stream_url' containing the entire RTMP path + key
        stream_url  = data.get("stream_url")         # e.g. rtmps://live-api-s.facebook.com:443/rtmp/<FB-...>?ds=1...
        secure_url  = data.get("secure_stream_url")  # sometimes also included

        if stream_url:
            # If you want to separate the server from the key, parse the 'stream_url'
            parsed = urlparse(stream_url)
            # e.g. scheme=rtmps, netloc=live-api-s.facebook.com:443, path=/rtmp/FB-1086682..., query=ds=1&...
            server_url = f"{parsed.scheme}://{parsed.netloc}{'/rtmp/'}"
            # The path after '/rtmp/' is the ephemeral key (plus possible query in the URL)
            # but often includes ?ds=..., so we might parse out the query:
            raw_key = parsed.path.replace("/rtmp/", "")
            # If there's a query string after the key, you can ignore or keep it:
            # e.g. raw_key = "FB-1086682...someKey?ds=1"
            # We can also store the entire 'stream_url' if we prefer ephemeral
            return {
                "full_rtmp_url": stream_url,  # entire ephemeral RTMP
                "server_url": server_url,     # e.g. rtmps://live-api-s.facebook.com:443/rtmp/
                "stream_key": raw_key,        # e.g. FB-1086682360139355-0-Ab0PmF0mtUYdmjfFFvQxRUz5?ds=1...
            }
        else:
            # fallback if 'stream_url' wasn't returned
            return None
    return None
