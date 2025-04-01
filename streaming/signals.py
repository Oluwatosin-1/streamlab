import logging
import requests
from urllib.parse import urlparse
from django.dispatch import receiver
from django.conf import settings

from allauth.socialaccount.signals import social_account_added, social_account_updated
from streaming.models import StreamingPlatformAccount

logger = logging.getLogger(__name__)

@receiver(social_account_added)
def handle_social_account_added(request, sociallogin, **kwargs):
    """
    Triggered when a new social account is linked to a user.
    For some providers, we can immediately fetch or update token/stream key info here.
    Typically, the adapter will handle this logic; signals can be used as a fallback or
    to handle custom updates after the account is created.
    """
    user = sociallogin.user
    provider = sociallogin.account.provider
    extra_data = sociallogin.account.extra_data or {}
    access_token = extra_data.get("access_token")
    refresh_token = extra_data.get("refresh_token")

    # Get or create the StreamingPlatformAccount.
    account, created = StreamingPlatformAccount.objects.get_or_create(
        user=user, platform=provider
    )

    if access_token:
        account.access_token = access_token
    if refresh_token:
        account.refresh_token = refresh_token

    try:
        if provider in ["google", "youtube"]:
            # Example: fetch the stream key again or log an event
            _fetch_youtube_streamkey(access_token, account)

        elif provider == "facebook":
            _fetch_facebook_streamkey(access_token, account)

        elif provider == "instagram":
            logger.info("Instagram provider (signal): manual RTMP/stream key entry required.")

        elif provider == "twitter":
            logger.info("Twitter provider (signal): storing tokens; live streaming integration is custom.")

        elif provider == "telegram":
            logger.info("Telegram provider (signal): storing tokens; manual RTMP setup required.")

        else:
            logger.info("Provider '%s' not specifically handled in signal.", provider)
    except Exception as e:
        logger.exception("Error processing provider '%s' in social_account_added signal: %s", provider, e)

    account.save()

@receiver(social_account_updated)
def handle_social_account_updated(request, sociallogin, **kwargs):
    """
    Triggered when an existing social account is updated (e.g., token refresh).
    """
    user = sociallogin.user
    provider = sociallogin.account.provider
    logger.info("Social account updated for provider: %s (user: %s)", provider, user)

    try:
        account = StreamingPlatformAccount.objects.get(user=user, platform=provider)
        logger.info("Updated account found. Access Token: %s, Stream Key: %s", account.access_token, account.stream_key)
        # If needed, you can re-fetch or refresh the stream key here.
    except StreamingPlatformAccount.DoesNotExist:
        logger.error("No StreamingPlatformAccount found for provider '%s' and user %s", provider, user)


# Helper functions for signals (similar to the ones in the adapter)
def _fetch_youtube_streamkey(access_token, account):
    youtube_api_url = "https://www.googleapis.com/youtube/v3/liveStreams"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    params = {"part": "cdn", "mine": "true"}

    resp = requests.get(youtube_api_url, headers=headers, params=params)
    if resp.status_code == 200:
        data = resp.json()
        items = data.get("items", [])
        if items:
            ingestion_info = items[0].get("cdn", {}).get("ingestionInfo", {})
            stream_key = ingestion_info.get("streamName")
            if stream_key:
                account.stream_key = stream_key
                logger.info("Fetched YouTube stream key in signal for user %s", account.user)
    else:
        logger.warning("YouTube API call failed in signal with status %s", resp.status_code)

def _fetch_facebook_streamkey(access_token, account):
    page_id = getattr(settings, "SOCIAL_AUTH_FACEBOOK_PAGE_ID", None)
    if not page_id:
        logger.error("SOCIAL_AUTH_FACEBOOK_PAGE_ID is not set; cannot fetch FB stream key in signal.")
        return

    fb_api_url = f"https://graph.facebook.com/v14.0/{page_id}/live_videos"
    params = {
        "access_token": access_token,
        "status": "LIVE_NOW",
        "title": "Live Stream via Django Allauth",
        "description": "Streaming integration using django-allauth",
    }
    fb_resp = requests.post(fb_api_url, params=params)
    if fb_resp.status_code == 200:
        data = fb_resp.json()
        stream_url = data.get("stream_url")
        if stream_url:
            parsed = urlparse(stream_url)
            raw_key = parsed.path.replace("/rtmp/", "")
            account.rtmp_url = stream_url
            account.stream_key = raw_key
            logger.info("Fetched Facebook stream key in signal for user %s", account.user)
    else:
        logger.warning("Facebook API call failed in signal with status %s", fb_resp.status_code)
