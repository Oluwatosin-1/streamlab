import logging
import requests
from urllib.parse import urlparse
from django.conf import settings
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from streaming.models import StreamingPlatformAccount

logger = logging.getLogger(__name__)

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Adapter to handle user creation/updates, token storage, and
    fetching RTMP/stream keys when a user connects via social login.
    """

    def save_user(self, request, sociallogin, form=None):
        """
        Overrides DefaultSocialAccountAdapter to store tokens and
        fetch additional streaming details where possible.
        """
        # 1) Let allauth handle creating/updating the user model.
        user = super().save_user(request, sociallogin, form)

        # 2) Extract provider (e.g., 'google', 'facebook', 'instagram', etc.) and OAuth tokens.
        provider = sociallogin.account.provider
        extra_data = sociallogin.account.extra_data or {}

        # some providers store tokens in extra_data, others in sociallogin.token
        access_token = extra_data.get("access_token") or (
            sociallogin.token.token if sociallogin.token else None
        )
        refresh_token = extra_data.get("refresh_token") or (
            sociallogin.token.token_secret if sociallogin.token else None
        )

        # 3) Store / update the tokens in StreamingPlatformAccount
        account, created = StreamingPlatformAccount.objects.get_or_create(
            user=user, platform=provider
        )
        if access_token:
            account.access_token = access_token
        if refresh_token:
            account.refresh_token = refresh_token

        # 4) Provider-specific logic to fetch or store RTMP/stream keys
        try:
            if provider in ["google", "youtube"]:
                self._fetch_youtube_streamkey(access_token, account)

            elif provider == "facebook":
                self._fetch_facebook_streamkey(access_token, account)

            elif provider == "instagram":
                # No official live API. Tokens stored; user must add RTMP & stream key manually.
                logger.info("Instagram provider: storing tokens; manual RTMP/stream key entry required.")

            elif provider == "twitter":
                # No official streaming API. Just store tokens.
                logger.info("Twitter provider: storing tokens only; manual or custom integration required.")

            elif provider == "telegram":
                # Telegram requires manual RTMP/stream key entry.
                logger.info("Telegram provider: storing tokens; manual RTMP/stream key setup required.")

            else:
                logger.info("Provider '%s' not specifically handled in adapter.", provider)
        except Exception as e:
            logger.exception("Error processing provider '%s' in adapter: %s", provider, str(e))

        account.save()
        return user

    def _fetch_youtube_streamkey(self, access_token, account):
        """
        Fetch the user's YouTube live stream key using the YouTube Data API.
        """
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
                    logger.info("Fetched YouTube stream key for user %s", account.user)
        else:
            logger.warning("YouTube API call failed with status %s", resp.status_code)

    def _fetch_facebook_streamkey(self, access_token, account):
        """
        Use the Facebook Live Video API to create a new live video and retrieve
        the RTMP URL and stream key.
        """
        page_id = getattr(settings, "SOCIAL_AUTH_FACEBOOK_PAGE_ID", None)
        if not page_id:
            logger.error("SOCIAL_AUTH_FACEBOOK_PAGE_ID is not set in settings; cannot fetch FB stream key.")
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
                logger.info("Fetched Facebook stream key for user %s", account.user)
        else:
            logger.warning("Facebook API call failed with status %s", fb_resp.status_code)
