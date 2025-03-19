# streaming/views.py

import uuid
import requests
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required 

from dashboard.models import DashboardSettings
from payments.models import UserSubscription

from .models import StreamingConfiguration
from .forms import (
    RecordingForm, 
    StreamingConfigurationForm, 
    VideoPlaylistForm
)
from .utils import (
    build_youtube_auth_url, 
    exchange_youtube_code_for_token, 
    fetch_youtube_stream_key,
    build_facebook_auth_url,
    exchange_facebook_code_for_token,
    fetch_facebook_stream_key
)
from users.models import SocialAccount
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


@login_required
def connect_youtube_oauth(request):
    """
    Step 1: Redirect user to Google's OAuth screen using the client ID from settings.
    """
    auth_url = build_youtube_auth_url()
    return redirect(auth_url)


@login_required
def youtube_callback(request):
    """
    Step 2: Google sends `code` to this callback. We exchange it for tokens,
    then fetch the user's YouTube stream key.
    """
    code = request.GET.get("code")
    if not code:
        messages.error(request, "No OAuth code returned from YouTube.")
        return redirect("dashboard:index")

    token_data = exchange_youtube_code_for_token(code)
    if not token_data:
        messages.error(request, "Failed to exchange code for token with YouTube.")
        return redirect("dashboard:index")

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    social_account, _ = SocialAccount.objects.get_or_create(
        user=request.user,
        platform="youtube"
    )
    social_account.access_token = access_token
    social_account.refresh_token = refresh_token

    # Attempt to fetch the user's actual stream key from the YT API
    real_stream_key = fetch_youtube_stream_key(access_token)
    if real_stream_key:
        social_account.stream_key = real_stream_key
        messages.success(request, "YouTube account connected & stream key fetched!")
    else:
        messages.warning(request, "YouTube account connected, but could not fetch stream key automatically.")

    social_account.save()
    return redirect("streaming:studio_enter")


@login_required
def connect_facebook_oauth(request):
    """
    Step 1: Redirect user to Facebook's OAuth screen using the client ID from settings.
    """
    auth_url = build_facebook_auth_url()
    return redirect(auth_url)


@login_required
def facebook_callback(request):
    """
    Step 2: Facebook returns a code. We exchange it for an access token,
    then fetch a persistent or ephemeral RTMP key.
    """
    code = request.GET.get("code")
    if not code:
        messages.error(request, "No OAuth code returned from Facebook.")
        return redirect("dashboard:index")

    token_data = exchange_facebook_code_for_token(code)
    if not token_data:
        messages.error(request, "Failed to exchange code for token with Facebook.")
        return redirect("dashboard:index")

    access_token = token_data.get("access_token")
    if not access_token:
        messages.error(request, "No access token returned by Facebook.")
        return redirect("dashboard:index")

    social_account, _ = SocialAccount.objects.get_or_create(
        user=request.user,
        platform="facebook"
    )
    social_account.access_token = access_token

    # Attempt to fetch the user's FB live RTMP key or URL
    stream_url, secure_url = fetch_facebook_stream_key(access_token)
    if stream_url:
        # Typically FB returns an entire RTMP URL (not just a key)
        social_account.rtmp_url = stream_url
        messages.success(request, "Facebook account connected & stream URL fetched!")
    else:
        messages.warning(request, "Facebook connected, but could not fetch stream key automatically.")

    social_account.save()
    return redirect("streaming:studio_enter")


@login_required
def streaming_config_list(request):
    """Lists all streaming configurations for the current user."""
    configs = StreamingConfiguration.objects.filter(user=request.user)
    return render(request, "streaming/config_list.html", {"configs": configs})


@login_required
def create_streaming_config(request):
    """
    Shows a 'modal-like' page to choose streaming type (Studio, RTMP, etc.).
    Also supports POST for advanced form usage if you want direct config creation.
    """
    if request.method == "POST":
        form = StreamingConfigurationForm(request.POST)
        if form.is_valid():
            config = form.save(commit=False)
            config.user = request.user
            config.save()
            messages.success(request, "Streaming configuration created successfully.")
            return redirect("streaming:config_list")
        else:
            messages.error(request, "Error creating streaming configuration. Please correct the errors below.")
    else:
        form = StreamingConfigurationForm()
    return render(request, "streaming/create_config.html", {"form": form})


@login_required
def connect_social_accounts(request, platform):
    """
    Connect or update a social account for a specific platform.
    If the user hasn't done OAuth yet (for FB/YT), we redirect them.
    Otherwise, if we have valid tokens, we proceed to the studio.
    """
    platform_icons = {
        "youtube": "https://cdn-icons-png.flaticon.com/512/1384/1384060.png",
        "facebook": "https://cdn-icons-png.flaticon.com/512/1384/1384053.png",
        "twitch": "https://cdn-icons-png.flaticon.com/512/5968/5968819.png",
        "instagram": "https://cdn-icons-png.flaticon.com/512/1384/1384063.png",
        "tiktok": "https://cdn-icons-png.flaticon.com/512/3046/3046120.png",
        "telegram": "https://cdn-icons-png.flaticon.com/512/2111/2111646.png",
    }
    platform_docs = {
        "youtube": "https://support.google.com/youtube/answer/2474026",
        "facebook": "https://www.facebook.com/help/587160588142067",
        "twitch": "https://help.twitch.tv/s/article/twitch-stream-key-faq",
        "instagram": "https://help.instagram.com/292478487812558",
        "tiktok": "https://support.tiktok.com/en/using-tiktok/live/setting-up-live-streaming",
        "telegram": "https://core.telegram.org/live#rtmp",
    }

    valid_platforms = ["youtube", "facebook", "twitch", "instagram", "tiktok", "telegram"]
    if platform not in valid_platforms:
        messages.error(request, f"Invalid platform: {platform}.")
        return redirect("dashboard:index")

    icon_url = platform_icons.get(platform, "")
    doc_url = platform_docs.get(platform, "")

    # Retrieve or create the SocialAccount record
    social_account, _ = SocialAccount.objects.get_or_create(user=request.user, platform=platform)

    # If the platform is YouTube or Facebook and no tokens exist, do OAuth
    if request.method == "GET":
        if platform == "youtube" and not social_account.access_token:
            return redirect("streaming:connect_youtube_oauth")
        elif platform == "facebook" and not social_account.access_token:
            return redirect("streaming:connect_facebook_oauth")

    if request.method == "POST":
        # Manually updating with an auth_code or RTMP if the user chooses
        display_name = request.POST.get("display_name", "")
        social_account.display_name = display_name

        # If user sets tokens or stream_key directly
        if platform == "twitch":
            social_account.access_token = "twitch_example_token"
            social_account.stream_key = "twitch_stream_key_xyz"
        elif platform == "telegram":
            social_account.rtmp_url = "rtmps://dc4-1.rtmp.t.me:443/s"
            social_account.stream_key = request.POST.get("stream_key", "")
        elif platform == "instagram":
            social_account.stream_key = request.POST.get("stream_key", "")
        elif platform == "tiktok":
            social_account.rtmp_url = request.POST.get("rtmp_url", "")
            social_account.stream_key = request.POST.get("stream_key", "")
        # (YouTube / Facebook handled by OAuth above, unless you're letting them do partial tokens here)

        social_account.save()
        messages.success(request, f"{platform.capitalize()} account connected/updated successfully.")
        return redirect("streaming:studio_enter")

    # If user already has tokens -> skip form -> studio
    if social_account.access_token:
        messages.info(request, f"{platform.capitalize()} is already connected. Entering Studio.")
        return redirect("streaming:studio_enter")

    # Otherwise show connect form
    context = {
        "social_account": social_account,
        "platform": platform,
        "icon_url": icon_url,
        "doc_url": doc_url,
    }
    return render(request, "streaming/connect.html", context)


@login_required
def rtmp_setup(request):
    """Displays the most recent active RTMP configuration for the user."""
    config = StreamingConfiguration.objects.filter(user=request.user, is_active=True).order_by('-created_at').first()
    if not config:
        messages.warning(request, "No active RTMP configuration found. Please create one.")
        return redirect("streaming:create_config")

    if request.method == "POST":
        form = StreamingConfigurationForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "RTMP configuration updated.")
            return redirect("dashboard:index")
        else:
            messages.error(request, "Error updating RTMP configuration.")
    else:
        form = StreamingConfigurationForm(instance=config)

    return render(request, "streaming/rtmp_setup.html", {"form": form, "config": config})


@login_required
def rtmp_draft(request):
    """
    Creates an RTMP draft (not active) on POST.
    On GET, shows 'drafts' on the dashboard.
    """
    if request.method == "POST":
        form = StreamingConfigurationForm(request.POST)
        if form.is_valid():
            config = form.save(commit=False)
            config.user = request.user
            config.is_active = False
            config.save()
            messages.success(request, "RTMP draft created successfully.")
            return redirect("dashboard:drafts")
        else:
            messages.error(request, "Error creating RTMP draft.")
            return redirect("dashboard:drafts")

    context = {
        "active_tab": "drafts",
        "draft_type": "rtmp",
    }
    return render(request, "dashboard/index.html", context)


@login_required
def studio(request):
    """
    Basic page for a 'Studio' environment or additional settings (legacy).
    If not used, you can remove.
    """
    return render(request, "streaming/studio.html")


@login_required
def studio_draft(request):
    """
    Creates a Studio draft (not active) on POST.
    On GET, displays 'drafts' in dashboard.
    """
    if request.method == "POST":
        form = StreamingConfigurationForm(request.POST)
        if form.is_valid():
            config = form.save(commit=False)
            config.user = request.user
            config.rtmp_url = ""
            config.stream_key = ""
            config.is_active = False
            config.save()
            messages.success(request, "Studio draft created successfully.")
            return redirect("dashboard:drafts")
        else:
            messages.error(request, "Error creating Studio draft.")
            return redirect("dashboard:drafts")

    context = {
        "active_tab": "drafts",
        "draft_type": "studio",
    }
    return render(request, "dashboard/index.html", context)


@login_required
def studio_enter(request):
    """
    Single advanced studio that can handle local record or live streaming.
    If ?record in GET, we hide chat, etc.
    """
    social_accounts = SocialAccount.objects.filter(user=request.user)
    config = StreamingConfiguration.objects.filter(user=request.user, is_active=True).first()

    # record_mode if "record" param is present
    record_mode = ('record' in request.GET)

    # Unique session reference
    session_uuid = uuid.uuid4()

    context = {
        "social_accounts": social_accounts,
        "config": config,
        "record_mode": record_mode,
        "session_uuid": session_uuid
    }
    return render(request, "streaming/studio_enter.html", context)


@login_required
def go_live(request):
    """Example endpoint for starting the live stream."""
    if request.method == "POST":
        messages.success(request, "You are now live!")
    return redirect("streaming:studio_enter")


@login_required
def stop_live(request):
    """Example endpoint for stopping the live stream."""
    if request.method == "POST":
        messages.info(request, "Stream has been stopped.")
    return redirect("streaming:studio_enter")


@login_required
def stream_settings(request):
    """
    A page for advanced streaming config: backup RTMP, pull links, chat embed, etc.
    """
    config = StreamingConfiguration.objects.filter(user=request.user, is_active=True).order_by('-created_at').first()
    if not config:
        messages.warning(request, "No active streaming configuration found. Please create one.")
        return redirect("streaming:create_config")

    if request.method == "POST":
        form = StreamingConfigurationForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "Streaming configuration updated.")
            return redirect("streaming:stream_settings")
        else:
            messages.error(request, "Error updating streaming configuration. Please check the fields.")
    else:
        form = StreamingConfigurationForm(instance=config)

    return render(request, "streaming/settings.html", {
        "form": form,
        "config": config,
    })


@login_required
def manage_channels(request):
    """
    Displays & manages the user's connected social accounts in a modal-based UI.
    """
    platform_icons = {
        "youtube": "https://cdn-icons-png.flaticon.com/512/1384/1384060.png",
        "facebook": "https://cdn-icons-png.flaticon.com/512/1384/1384053.png",
        "twitch": "https://cdn-icons-png.flaticon.com/512/5968/5968819.png",
        "instagram": "https://cdn-icons-png.flaticon.com/512/1384/1384063.png",
        "tiktok": "https://cdn-icons-png.flaticon.com/512/3046/3046120.png",
        "telegram": "https://cdn-icons-png.flaticon.com/512/2111/2111646.png",
    }

    user_channels = SocialAccount.objects.filter(user=request.user)

    user_channels_info = []
    for channel in user_channels:
        icon_url = platform_icons.get(channel.platform, "")
        user_channels_info.append({
            "channel": channel,
            "icon_url": icon_url,
        })

    if request.method == "POST":
        action = request.POST.get("action")
        channel_id = request.POST.get("channel_id")
        if action == "remove" and channel_id:
            try:
                channel_to_delete = SocialAccount.objects.get(id=channel_id, user=request.user)
                channel_to_delete.delete()
                messages.success(request, "Channel removed successfully.")
            except SocialAccount.DoesNotExist:
                messages.error(request, "Channel not found or not owned by user.")
            return redirect("streaming:manage_channels")

    context = {
        "user_channels_info": user_channels_info,
    }
    return render(request, "streaming/manage_channels.html", context)


@login_required
def schedule_video_session(request):
    """
    Schedules a video or playlist. No social connection or config needed.
    """
    if request.method == "POST":
        form = VideoPlaylistForm(request.POST, request.FILES)
        if form.is_valid():
            scheduled_video = form.save(commit=False)
            scheduled_video.user = request.user
            scheduled_video.save()
            messages.success(request, "Video/Playlist scheduled successfully!")
            return redirect("streaming:studio_enter")
        else:
            messages.error(request, "Error scheduling video/playlist. Please check the fields.")
    else:
        form = VideoPlaylistForm()

    return render(request, "streaming/video_playlist.html", {"form": form})


@login_required
@csrf_exempt
def upload_recorded(request):
    """
    Receives a POST with 'video_file' for local recordings, storing on the server.
    """
    if request.method == "POST":
        video_file = request.FILES.get("video_file")
        if not video_file:
            return JsonResponse({"error": "No video file in request"}, status=400)

        file_path = default_storage.save(f"recorded_videos/{video_file.name}", ContentFile(video_file.read()))
        # Possibly create a DB record referencing file_path
        # e.g. RecordedVideo.objects.create(user=request.user, file_path=file_path, session_uuid=?)
        return JsonResponse({"message": "Upload success", "file_path": file_path}, status=200)

    return JsonResponse({"error": "Only POST allowed"}, status=405)


@login_required
def local_record_session(request):
    """
    A purely local record session, skipping config or social connections.
    """
    if request.method == "POST":
        form = RecordingForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data['title']
            notes = form.cleaned_data['notes']
            # Possibly store or track a "RecordingSession"
            messages.success(request, f"Local recording session '{title}' started!")
            return redirect("streaming:studio_enter")
        else:
            messages.error(request, "Error starting recording session.")
    else:
        form = RecordingForm()

    return render(request, "streaming/record.html", {"form": form})


# NEW: Video Storage
@login_required
def video_storage(request):
    """
    Example placeholder for 'Video Storage' page. 
    You might list user-uploaded or recorded videos stored on your platform.
    """
    dashboard_settings, _ = DashboardSettings.objects.get_or_create(user=request.user)
    try:
        user_subscription = request.user.subscription
    except UserSubscription.DoesNotExist:
        user_subscription = None

    context = {
        'dashboard_settings': dashboard_settings,
        'user_subscription': user_subscription,
    }
    return render(request, "dashboard/video_storage.html", context)

# NEW: Analytics
@login_required
def analytics(request):
    """
    Example 'Analytics' page. Replace with real logic if you track viewer metrics, etc.
    """
    dashboard_settings, _ = DashboardSettings.objects.get_or_create(user=request.user)
    try:
        user_subscription = request.user.subscription
    except UserSubscription.DoesNotExist:
        user_subscription = None

    # Example metrics
    context = {
        'dashboard_settings': dashboard_settings,
        'user_subscription': user_subscription,
        'some_analytics_data': {...}  # Replace with real data
    }
    return render(request, "dashboard/analytics.html", context)

@login_required
@csrf_exempt
@require_POST
def send_chat_message(request):
    """
    Accepts a POST request with JSON data containing a session_uuid and text.
    Creates a new ChatMessage and returns its info as JSON.
    """
    try:
        data = json.loads(request.body)
        session_uuid = data.get("session_uuid")
        text = data.get("text")
        if not text:
            return JsonResponse({"error": "Message text cannot be empty."}, status=400)

        # Create the chat message
        chat = ChatMessage.objects.create(
            session_uuid=session_uuid,
            user=request.user,
            text=text
        )
        return JsonResponse({
            "message": "Chat message sent successfully.",
            "chat": {
                "id": chat.id,
                "user": chat.user.username,
                "text": chat.text,
                "created_at": chat.created_at.isoformat()
            }
        }, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@login_required
def fetch_chat_messages(request):
    """
    Accepts a GET request with a 'session_uuid' parameter.
    Returns a JSON list of chat messages for that session ordered by creation time.
    """
    session_uuid = request.GET.get("session_uuid")
    if not session_uuid:
        return JsonResponse({"error": "Missing 'session_uuid' parameter."}, status=400)

    try:
        messages_qs = ChatMessage.objects.filter(session_uuid=session_uuid).order_by("created_at")
        messages_list = [{
            "id": msg.id,
            "user": msg.user.username,
            "text": msg.text,
            "created_at": msg.created_at.isoformat()
        } for msg in messages_qs]
        return JsonResponse(messages_list, safe=False, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)