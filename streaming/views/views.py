import uuid
import json
import requests
from datetime import datetime, timezone
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt

from dashboard.models import DashboardSettings
from payments.models import UserSubscription
from streaming.models import ChatMessage, StreamingConfiguration, StreamingSession
from streaming.forms import (
    RecordingForm,
    SocialAccountForm,
    StreamingConfigurationForm, 
    ChatMessageForm,
    # Assume SocialConnectionForm is defined for manual entry.
)
from streaming.utils import (
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

### OAUTH ENDPOINTS FOR YOUTUBE & FACEBOOK ###

@login_required
def connect_youtube_oauth(request):
    """Initiate OAuth for YouTube using client secrets from a JSON file."""
    auth_url = build_youtube_auth_url()
    return redirect(auth_url)

@login_required
def youtube_callback(request):
    """Callback endpoint for YouTube OAuth.
       Attempts to exchange the code for tokens and fetch the stream key.
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
    social_account, _ = SocialAccount.objects.get_or_create(user=request.user, platform="youtube")
    social_account.access_token = access_token
    social_account.refresh_token = refresh_token
    # Try to automatically retrieve the stream key via YouTube’s API.
    stream_key = fetch_youtube_stream_key(access_token)
    if stream_key:
        social_account.stream_key = stream_key
        messages.success(request, "YouTube account connected & stream key retrieved automatically!")
    else:
        messages.warning(
            request,
            "YouTube account connected, but automatic stream key retrieval failed. "
            "Please provide your stream key manually (via your account settings)."
        )
    social_account.save()
    return redirect("studio_enter")

@login_required
def connect_facebook_oauth(request):
    """Initiate OAuth for Facebook."""
    auth_url = build_facebook_auth_url()
    return redirect(auth_url)

@login_required
def facebook_callback(request):
    """Callback endpoint for Facebook OAuth.
       Exchanges the code for a token and attempts to retrieve the RTMP stream URL.
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
    social_account, _ = SocialAccount.objects.get_or_create(user=request.user, platform="facebook")
    social_account.access_token = access_token
    key_data = fetch_facebook_stream_key(access_token)
    if key_data:
        social_account.rtmp_url = key_data.get("full_rtmp_url")
        social_account.stream_key = key_data.get("stream_key")
        messages.success(request, "Facebook account connected & stream URL retrieved!")
    else:
        messages.warning(
            request,
            "Facebook connected, but automatic stream key retrieval failed. "
            "Please provide your stream key manually (via your account settings)."
        )
    social_account.save()
    return redirect("studio_enter")

### MANUAL / GENERIC SOCIAL CONNECT ENDPOINT ###
@login_required
def connect_social(request, platform):
    """
    A generic endpoint to connect or update a social account for platforms that
    do not have a full OAuth flow (e.g., Instagram, TikTok, Twitch, Telegram).
    Users can manually provide the stream key, RTMP URL, and other settings.
    After successful submission, the user is redirected to the channel management page.
    """
    valid_platforms = ["youtube", "facebook", "twitch", "instagram", "tiktok", "telegram"]
    if platform not in valid_platforms:
        messages.error(request, f"Invalid platform: {platform}.")
        return redirect("dashboard:index")
    # For YouTube and Facebook, if the OAuth token is missing, redirect to their OAuth flows.
    if request.method == "GET":
        if platform == "youtube":
            sa, _ = SocialAccount.objects.get_or_create(user=request.user, platform="youtube")
            if not sa.access_token:
                return redirect("streaming:connect_youtube_oauth")
        elif platform == "facebook":
            sa, _ = SocialAccount.objects.get_or_create(user=request.user, platform="facebook")
            if not sa.access_token:
                return redirect("streaming:connect_facebook_oauth")
    # For manual entry, display the form.
    if request.method == "POST":
        form = SocialAccountForm(request.POST)
        if form.is_valid():
            social_account, _ = SocialAccount.objects.get_or_create(user=request.user, platform=platform)
            social_account.display_name = form.cleaned_data.get("display_name")
            social_account.access_token = form.cleaned_data.get("access_token")
            social_account.refresh_token = form.cleaned_data.get("refresh_token")
            social_account.rtmp_url = form.cleaned_data.get("rtmp_url")
            social_account.stream_key = form.cleaned_data.get("stream_key")
            social_account.save()
            messages.success(request, f"{platform.capitalize()} account connected successfully via manual entry.")
            # Redirect to the manage channels page showing the list of connected channels.
            return redirect("streaming:manage_channels")
        else:
            messages.error(request, "Error connecting social account. Please correct the errors below.")
    else:
        form = SocialAccountForm(initial={"platform": platform})
    return render(request, "streaming/connect.html", {"form": form, "platform": platform})

### STREAMING CONFIGURATION & SESSIONS ###

@login_required
def streaming_config_list(request):
    configs = StreamingConfiguration.objects.filter(user=request.user)
    return render(request, "streaming/config_list.html", {"configs": configs})

@login_required
def create_streaming_config(request):
    """
    Allows the user to create a new streaming configuration.
    If the stream title includes 'rtmp', the user will be redirected to the RTMP setup page.
    Otherwise, they are directed to the studio.
    """
    if request.method == "POST":
        form = StreamingConfigurationForm(request.POST)
        if form.is_valid():
            config = form.save(commit=False)
            config.user = request.user
            config.save()
            messages.success(request, "Streaming configuration created successfully.")
            if "rtmp" in config.stream_title.lower():
                return redirect("streaming:rtmp_setup")
            else:
                return redirect("studio_enter")
        else:
            messages.error(request, "Error creating streaming configuration. Please correct the errors below.")
    else:
        form = StreamingConfigurationForm()
    return render(request, "streaming/create_config.html", {"form": form})

@login_required
def studio_enter(request):
    """
    The main studio page where users preview and control their stream.
    Generates a unique session UUID for this streaming session.
    """
    social_accounts = SocialAccount.objects.filter(user=request.user)
    config = StreamingConfiguration.objects.filter(user=request.user, is_active=True).first()
    record_mode = ('record' in request.GET)
    session_uuid = uuid.uuid4()
    context = {
        "social_accounts": social_accounts,
        "config": config,
        "record_mode": record_mode,
        "session_uuid": session_uuid,
    }
    return render(request, "streaming/studio_enter.html", context)

@login_required
def go_live(request, session_id=None):
    """
    Trigger a live session based on the active configuration.
    If session_id is provided, update that session; otherwise, create a new one.
    """
    config = StreamingConfiguration.objects.filter(user=request.user, is_active=True).first()
    if not config:
        messages.error(request, "No active streaming configuration found.")
        return redirect("streaming:create_config")
    if session_id:
        session = get_object_or_404(StreamingSession, id=session_id, configuration__user=request.user)
    else:
        session = StreamingSession.objects.create(configuration=config, status="live")
    messages.success(request, "You are now live!")
    return redirect(reverse("streaming:session_detail", kwargs={"session_id": session.id}))

@login_required
def stop_live(request, session_id):
    session = get_object_or_404(StreamingSession, id=session_id, configuration__user=request.user)
    if session.status != "live":
        messages.error(request, "Session is not live.")
        return redirect(reverse("streaming:session_detail", kwargs={"session_id": session.id}))
    session.status = "ended"
    session.session_end = datetime.now(timezone.utc)
    session.save()
    messages.info(request, "Live session has been stopped.")
    return redirect(reverse("streaming:session_detail", kwargs={"session_id": session.id}))

@login_required
def stream_stats(request, session_id):
    session = get_object_or_404(StreamingSession, id=session_id, configuration__user=request.user)
    stats = {
        "viewers_count": session.viewers_count,
        "session_start": session.session_start.isoformat(),
        "session_end": session.session_end.isoformat() if session.session_end else None,
        "status": session.status,
    }
    return JsonResponse(stats)

### CHAT ENDPOINTS ###

@login_required
@csrf_exempt
@require_POST
def send_chat_message(request, session_id):
    session = get_object_or_404(StreamingSession, id=session_id, configuration__user=request.user)
    form = ChatMessageForm(request.POST)
    if form.is_valid():
        chat_message = form.save(commit=False)
        chat_message.user = request.user
        chat_message.streaming_session = session
        chat_message.save()
        return JsonResponse({"status": "success", "message": "Message sent."})
    return JsonResponse({"status": "error", "errors": form.errors}, status=400)

@login_required
def fetch_chat_messages(request, session_id):
    session = get_object_or_404(StreamingSession, id=session_id, configuration__user=request.user)
    messages_qs = session.chat_messages.all().order_by("created_at").values("user__username", "text", "created_at")
    return JsonResponse({"status": "success", "messages": list(messages_qs)})

### RECORDING & LOCAL SESSIONS ###

@login_required
def local_record_session(request):
    if request.method == "POST":
        form = RecordingForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data['title']
            notes = form.cleaned_data['notes']
            messages.success(request, f"Local recording session '{title}' started!")
            return redirect("studio_enter")
        else:
            messages.error(request, "Error starting recording session.")
    else:
        form = RecordingForm()
    return render(request, "streaming/record.html", {"form": form})

@login_required
@csrf_exempt
def upload_recorded(request):
    if request.method == "POST":
        video_file = request.FILES.get("video_file")
        if not video_file:
            return JsonResponse({"error": "No video file in request"}, status=400)
        file_path = default_storage.save(f"recorded_videos/{video_file.name}", ContentFile(video_file.read()))
        return JsonResponse({"message": "Upload success", "file_path": file_path}, status=200)
    return JsonResponse({"error": "Only POST allowed"}, status=405)

### ADDITIONAL ENDPOINTS (Video Storage, Analytics) ###

@login_required
def video_storage(request):
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

@login_required
def analytics(request):
    dashboard_settings, _ = DashboardSettings.objects.get_or_create(user=request.user)
    try:
        user_subscription = request.user.subscription
    except UserSubscription.DoesNotExist:
        user_subscription = None
    context = {
        'dashboard_settings': dashboard_settings,
        'user_subscription': user_subscription,
        'some_analytics_data': {}  # Replace with actual analytics data
    }
    return render(request, "dashboard/analytics.html", context)

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
