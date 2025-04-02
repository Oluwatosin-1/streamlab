import json
import subprocess
import logging
from datetime import datetime, timezone
from streaming.srs_utils import get_stream_stats
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin

from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack

from streaming.models import (
    StreamingConfiguration,
    StreamingSession,
    ChatMessage,
    StreamingPlatformAccount,
)
from streaming.forms import (
    StreamingConfigurationForm,
    RecordingForm,
    SocialAccountForm,
    ChatMessageForm,
)
from streaming.srs_utils import start_streaming_via_srs
from users.models import SocialAccount
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

# ============================================================================
# WebRTC Offer Endpoint (Browser → Django → FFmpeg → SRS)
# ============================================================================
@property
def connection_status(self):
    return "Connected" if self.access_token or (self.rtmp_url and self.stream_key) else "Pending"

pcs = set()

@csrf_exempt
async def offer(request):
    """
    Receives a WebRTC offer from the browser, sets up an RTCPeerConnection,
    and pipes video frames via FFmpeg to the SRS RTMP endpoint.
    """
    params = json.loads(request.body)
    offer_obj = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("track")
    async def on_track(track: MediaStreamTrack):
        logger.info("WebRTC track received: %s", track.kind)
        if track.kind == 'video':
            ffmpeg_process = subprocess.Popen(
                [
                    'ffmpeg',
                    '-y',
                    '-f', 'rawvideo',
                    '-pix_fmt', 'yuv420p',
                    '-s', '640x480',  # Adjust as needed
                    '-r', '30',
                    '-i', '-',       # Read raw frames from stdin
                    '-c:v', 'libx264',
                    '-preset', 'veryfast',
                    '-f', 'flv',
                    'rtmp://localhost/live/' + request.GET.get("stream_key", "defaultStreamKey")
                ],
                stdin=subprocess.PIPE
            )
            while True:
                frame = await track.recv()
                img = frame.to_ndarray(format='yuv420p')
                ffmpeg_process.stdin.write(img.tobytes())

    await pc.setRemoteDescription(offer_obj)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return JsonResponse({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })


# ============================================================================
# Optional: Manual Social Connect (If You Still Want a Fallback)
# ============================================================================

@login_required
def connect_social(request, platform):
    valid_platforms = ["youtube", "facebook", "twitch", "instagram", "tiktok", "telegram"]
    if platform not in valid_platforms:
        messages.error(request, f"Invalid platform: {platform}.")
        return redirect("dashboard:index")
    
    if request.method == "POST":
        form = SocialAccountForm(request.POST)
        if form.is_valid():
            account, created = StreamingPlatformAccount.objects.get_or_create(
                user=request.user,
                platform=platform,
                defaults={'account_username': request.user.username}
            )
            account.display_name = form.cleaned_data.get("display_name")
            account.account_username = form.cleaned_data.get("account_username") or request.user.username
            account.rtmp_url = form.cleaned_data.get("rtmp_url")
            account.stream_key = form.cleaned_data.get("stream_key")
            # Mark account active if both RTMP URL and stream key are provided.
            if account.rtmp_url and account.stream_key:
                account.is_active = True
            else:
                account.is_active = False
            account.save()
            logger.info("Connected %s account for user %s successfully.", platform, request.user.username)
            messages.success(request, f"{platform.capitalize()} account connected successfully!")
            return redirect("streaming:manage_channels")
        else:
            messages.error(request, "Error connecting social account. Please correct the errors below.")
    else:
        form = SocialAccountForm(initial={"platform": platform})
    
    try:
        social_account = request.user.streaming_platform_accounts.get(platform=platform)
    except StreamingPlatformAccount.DoesNotExist:
        social_account = None

    context = {"form": form, "platform": platform, "social_account": social_account}
    return render(request, "streaming/connect.html", context)

# ============================================================================
# Streaming Configuration & Session Endpoints
# ============================================================================

class StreamingConfigurationListView(LoginRequiredMixin, ListView):
    model = StreamingConfiguration
    template_name = "streaming/config_list.html"
    context_object_name = "configurations"

    def get_queryset(self):
        return StreamingConfiguration.objects.filter(user=self.request.user)

class StreamingConfigurationCreateView(LoginRequiredMixin, CreateView):
    model = StreamingConfiguration
    form_class = StreamingConfigurationForm
    template_name = "streaming/create_rtmp_config.html"
    success_url = reverse_lazy("streaming:config_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class StreamingConfigurationUpdateView(LoginRequiredMixin, UpdateView):
    model = StreamingConfiguration
    form_class = StreamingConfigurationForm
    template_name = "streaming/update_config.html"
    success_url = reverse_lazy("streaming:config_list")

    def get_queryset(self):
        return StreamingConfiguration.objects.filter(user=self.request.user)

class StreamingConfigurationDeleteView(LoginRequiredMixin, DeleteView):
    model = StreamingConfiguration
    template_name = "streaming/delete_config.html"
    success_url = reverse_lazy("streaming:config_list")

    def get_queryset(self):
        return StreamingConfiguration.objects.filter(user=self.request.user)

class StreamingConfigurationDetailView(LoginRequiredMixin, DetailView):
    model = StreamingConfiguration
    template_name = "streaming/detail_config.html"
    context_object_name = "configuration"

    def get_queryset(self):
        return StreamingConfiguration.objects.filter(user=self.request.user)

@login_required
def start_streaming_session(request, config_id):
    config = get_object_or_404(StreamingConfiguration, pk=config_id, user=request.user)
    session = StreamingSession.objects.create(configuration=config, status="live")
    # Optionally trigger a Celery task to do something externally
    return redirect("streaming:session_detail", session_id=session.id)

@login_required
def end_streaming_session(request, session_id):
    session = get_object_or_404(StreamingSession, id=session_id, configuration__user=request.user)
    if session.status != "live":
        return redirect("streaming:session_detail", session_id=session.id)
    session.status = "ended"
    session.session_end = timezone.now()
    session.save()
    return redirect("streaming:session_detail", session_id=session.id)

class StreamingSessionDetailView(LoginRequiredMixin, DetailView):
    model = StreamingSession
    template_name = "streaming/session_detail.html"
    context_object_name = "session"
    pk_url_kwarg = "session_id"

    def get_queryset(self):
        return StreamingSession.objects.filter(configuration__user=self.request.user)

@login_required
def go_live(request, config_id, session_id=None):
    config = get_object_or_404(StreamingConfiguration, pk=config_id, user=request.user, is_active=True)
    if session_id:
        session = get_object_or_404(StreamingSession, id=session_id, configuration__user=request.user)
    else:
        session = StreamingSession.objects.create(configuration=config, status="live")

    # If you have a Celery task for relaying from SRS to social media, call it here:
    from streaming.tasks import relay_to_social_task
    relay_to_social_task.delay(session.id, config.get_full_rtmp_url())
    messages.info(request, f"Initiating live stream for session: {session.session_uuid}")
    return redirect(reverse("streaming:session_detail", kwargs={"session_id": session.id}))


# ============================================================================
# Chat Endpoints
# ============================================================================

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
def fetch_chat_messages(request):
    session_uuid = request.GET.get("session_uuid")
    if not session_uuid:
        return JsonResponse({"error": "Session ID is required."}, status=400)
    
    # Look up the session by its UUID
    session = get_object_or_404(StreamingSession, session_uuid=session_uuid, configuration__user=request.user)
    messages_qs = session.chat_messages.all().order_by("created_at").values("user__username", "text", "created_at")
    return JsonResponse({"status": "success", "messages": list(messages_qs)})

# ============================================================================
# Recording & Local Session Endpoints
# ============================================================================

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


# ============================================================================
# Additional Endpoints (Video Storage, Analytics, Manage Channels)
# ============================================================================

@login_required
def video_storage(request):
    from dashboard.models import DashboardSettings
    dashboard_settings, _ = DashboardSettings.objects.get_or_create(user=request.user)
    context = {'dashboard_settings': dashboard_settings}
    return render(request, "dashboard/video_storage.html", context)

@login_required
def analytics(request):
    from dashboard.models import DashboardSettings
    dashboard_settings, _ = DashboardSettings.objects.get_or_create(user=request.user)
    context = {
        'dashboard_settings': dashboard_settings,
        'some_analytics_data': {}  # Replace with actual analytics data
    }
    return render(request, "dashboard/analytics.html", context) 

@login_required
def manage_channels(request):
    platform_icons = {
        "youtube": "https://cdn-icons-png.flaticon.com/512/1384/1384060.png",
        "facebook": "https://cdn-icons-png.flaticon.com/512/1384/1384053.png",
        "twitch": "https://cdn-icons-png.flaticon.com/512/5968/5968819.png",
        "instagram": "https://cdn-icons-png.flaticon.com/512/1384/1384063.png",
        "tiktok": "https://cdn-icons-png.flaticon.com/512/3046/3046120.png",
        "telegram": "https://cdn-icons-png.flaticon.com/512/2111/2111646.png",
    }
    user_channels = StreamingPlatformAccount.objects.filter(user=request.user)
    user_channels_info = []
    for account in user_channels:
        icon_url = platform_icons.get(account.platform, "")
        status = "Active" if (account.rtmp_url and account.stream_key) else "Pending"
        user_channels_info.append({
            "channel": account,
            "icon_url": icon_url,
            "status": status,
        })

    if request.method == "POST":
        action = request.POST.get("action")
        channel_id = request.POST.get("channel_id")
        if action == "remove" and channel_id:
            try:
                account_to_delete = StreamingPlatformAccount.objects.get(id=channel_id, user=request.user)
                account_to_delete.delete()
                messages.success(request, "Channel removed successfully.")
            except StreamingPlatformAccount.DoesNotExist:
                messages.error(request, "Channel not found or not owned by user.")
            return redirect("streaming:manage_channels")

    context = {
        "user_channels_info": user_channels_info,
        "platform_icons": platform_icons,
    }
    return render(request, "streaming/manage_channels.html", context)

@login_required
def srs_console(request):
    """
    Provides a view where the user can see the SRS configuration.
    It renders an iframe pointing to the SRS console URL.
    """
    # You could also store this URL in settings or in your StreamingConfiguration model.
    srs_console_url = "http://185.113.249.211:8080/console/ng_index.html#/summaries?port=1985"
    context = {"srs_console_url": srs_console_url}
    return render(request, "streaming/srs_console.html", context)

@login_required
def studio_enter(request):
    """
    Renders the studio where users can preview their camera,
    push the stream live via WebRTC, record, and view chat.
    """
    # Get the active streaming configuration for the user.
    config = StreamingConfiguration.objects.filter(user=request.user, is_active=True).first()
    if not config:
        messages.error(request, "No active streaming configuration found. Please create one.")
        return redirect("streaming:config_create")

    # Create a new streaming session.
    session = StreamingSession.objects.create(configuration=config, status="live")

    # Retrieve any connected social accounts if needed.
    social_accounts = StreamingPlatformAccount.objects.filter(user=request.user)

    # Build the context for the studio.
    context = {
        "session_uuid": session.session_uuid,  # Unique session ID for the client.
        "config": config,
        "social_accounts": social_accounts,
        "record_mode": 'record' in request.GET,  # Use a GET param to toggle record mode.
        "session": session,
    }
    return render(request, "streaming/studio_enter.html", context)


def check_stream_status(request, stream_key):
    app = "live"
    stats = get_stream_stats(app, stream_key)
    return JsonResponse({"status": "ok", "srs_stats": stats})
