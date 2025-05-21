import json
import logging
import subprocess
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.conf import settings
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DeleteView,
    DetailView,
    TemplateView,
)
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
from streaming.srs_utils import (
    get_stream_stats,
    start_streaming_via_srs,
    stop_streaming_via_srs,
)
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


class StreamingError(Exception):
    """Custom exception for streaming-related errors"""

    pass


# ============================================================================
# WebRTC Offer Endpoint (Browser → Django → FFmpeg → SRS)
# ============================================================================

pcs = set()


@csrf_exempt
async def offer(request):
    """
    Robust WebRTC offer handler with comprehensive error handling and logging
    """
    try:
        # Validate stream key
        stream_key = request.GET.get("stream_key")
        if not stream_key:
            logger.error("No stream key provided in WebRTC offer")
            return JsonResponse(
                {"status": "error", "message": "Stream key is required"}, status=400
            )

        # Parse and validate the WebRTC offer
        try:
            params = json.loads(request.body)
            if "sdp" not in params or "type" not in params:
                raise ValueError("Missing SDP or type in offer")
            offer_obj = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Invalid WebRTC offer format: {str(e)}")
            return JsonResponse(
                {"status": "error", "message": "Invalid offer format"}, status=400
            )

        # Create and configure peer connection
        pc = RTCPeerConnection()
        pcs.add(pc)

        # Track handler for incoming media streams
        @pc.on("track")
        async def on_track(track):
            logger.info(f"Received {track.kind} track")
            if track.kind == "video":
                try:
                    # Configure FFmpeg for RTMP streaming
                    ffmpeg_cmd = [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "rawvideo",
                        "-pix_fmt",
                        "yuv420p",
                        "-s",
                        "1280x720",  # HD resolution
                        "-r",
                        "30",  # 30 FPS
                        "-i",
                        "-",  # Pipe input
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-tune",
                        "zerolatency",
                        "-f",
                        "flv",
                        f"rtmp://{settings.SRS_SERVER_HOST}/live/{stream_key}",
                    ]

                    # Start FFmpeg process
                    ffmpeg_process = subprocess.Popen(
                        ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE
                    )

                    # Process video frames
                    while True:
                        try:
                            frame = await track.recv()
                            img = frame.to_ndarray(format="yuv420p")
                            ffmpeg_process.stdin.write(img.tobytes())
                        except Exception as e:
                            logger.error(f"Frame processing error: {str(e)}")
                            ffmpeg_process.terminate()
                            break

                except Exception as e:
                    logger.error(f"FFmpeg initialization failed: {str(e)}")
                    if "ffmpeg_process" in locals():
                        ffmpeg_process.terminate()

        # Handle connection state changes
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"Connection state changed to {pc.connectionState}")
            if pc.connectionState == "failed":
                logger.error("WebRTC connection failed")

        # Process the WebRTC offer
        await pc.setRemoteDescription(offer_obj)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return JsonResponse(
            {
                "status": "success",
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type,
            }
        )

    except Exception as e:
        logger.error(f"WebRTC offer processing failed: {str(e)}")
        return JsonResponse(
            {"status": "error", "message": "Internal server error"}, status=500
        )


# ============================================================================
# Social Account Management
# ============================================================================


@login_required
def connect_social(request, platform):
    """
    Robust social account connection with validation and error handling
    """
    valid_platforms = [
        "youtube",
        "facebook",
        "twitch",
        "instagram",
        "tiktok",
        "telegram",
    ]
    if platform not in valid_platforms:
        messages.error(request, f"Invalid platform: {platform}.")
        return redirect("streaming:manage_channels")

    try:
        if request.method == "POST":
            form = SocialAccountForm(request.POST)
            if form.is_valid():
                with transaction.atomic():
                    account, created = StreamingPlatformAccount.objects.get_or_create(
                        user=request.user,
                        platform=platform,
                        defaults={
                            "account_username": request.user.username,
                            "display_name": form.cleaned_data.get("display_name", ""),
                        },
                    )

                    # Update account details
                    account.rtmp_url = form.cleaned_data.get("rtmp_url")
                    account.stream_key = form.cleaned_data.get("stream_key")
                    account.is_active = bool(account.rtmp_url and account.stream_key)
                    account.save()

                    messages.success(
                        request,
                        f"{platform.capitalize()} account connected successfully!",
                    )
                    return redirect("streaming:manage_channels")
            else:
                messages.error(request, "Please correct the errors below.")
        else:
            form = SocialAccountForm(initial={"platform": platform})

        # Get existing account if any
        try:
            social_account = StreamingPlatformAccount.objects.get(
                user=request.user, platform=platform
            )
        except StreamingPlatformAccount.DoesNotExist:
            social_account = None

        return render(
            request,
            "streaming/connect.html",
            {"form": form, "platform": platform, "social_account": social_account},
        )

    except Exception as e:
        logger.error(f"Error in connect_social: {str(e)}")
        messages.error(request, "An error occurred while processing your request.")
        return redirect("streaming:manage_channels")


# ============================================================================
# Streaming Configuration Views
# ============================================================================


@login_required
def srs_console(request):
    """
    Provides a view where the user can see the SRS configuration.
    It renders an iframe pointing to the SRS console URL.
    """
    # You could also store this URL in settings or in your StreamingConfiguration model.
    srs_console_url = (
        "http://185.113.249.211:8080/console/ng_index.html#/summaries?port=1985"
    )
    context = {"srs_console_url": srs_console_url}
    return render(request, "streaming/srs_console.html", context)


class StreamingConfigurationListView(LoginRequiredMixin, ListView):
    """List all streaming configurations for the current user"""

    model = StreamingConfiguration
    template_name = "streaming/config_list.html"
    context_object_name = "configurations"

    def get_queryset(self):
        return StreamingConfiguration.objects.filter(user=self.request.user)


class StreamingConfigurationCreateView(LoginRequiredMixin, CreateView):
    """Create a new streaming configuration"""

    model = StreamingConfiguration
    form_class = StreamingConfigurationForm
    template_name = "streaming/create_rtmp_config.html"
    success_url = reverse_lazy("streaming:config_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class StreamingConfigurationUpdateView(LoginRequiredMixin, UpdateView):
    """Update an existing streaming configuration"""

    model = StreamingConfiguration
    form_class = StreamingConfigurationForm
    template_name = "streaming/update_config.html"
    success_url = reverse_lazy("streaming:config_list")

    def get_queryset(self):
        return StreamingConfiguration.objects.filter(user=self.request.user)


class StreamingConfigurationDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a streaming configuration"""

    model = StreamingConfiguration
    template_name = "streaming/delete_config.html"
    success_url = reverse_lazy("streaming:config_list")

    def get_queryset(self):
        return StreamingConfiguration.objects.filter(user=self.request.user)


class StreamingConfigurationDetailView(LoginRequiredMixin, DetailView):
    """View details of a streaming configuration"""

    model = StreamingConfiguration
    template_name = "streaming/detail_config.html"
    context_object_name = "configuration"

    def get_queryset(self):
        return StreamingConfiguration.objects.filter(user=self.request.user)


# ============================================================================
# Streaming Session Management
# ============================================================================


@login_required
def start_streaming_session(request, config_id):
    """
    Start a new streaming session with validation and error handling
    """
    try:
        config = get_object_or_404(
            StreamingConfiguration, pk=config_id, user=request.user
        )

        with transaction.atomic():
            session = StreamingSession.objects.create(
                configuration=config, status="starting"
            )

            # Start SRS stream if needed
            srs_response = start_streaming_via_srs("live", config.stream_key)

            if not srs_response or srs_response.get("code") != 0:
                session.status = "failed"
                session.save()
                messages.error(request, "Failed to initialize streaming server")
                return redirect("streaming:config_list")

            session.status = "live"
            session.save()

            return redirect("streaming:session_detail", session_id=session.id)

    except Exception as e:
        logger.error(f"Failed to start streaming session: {str(e)}")
        messages.error(request, "Failed to start streaming session")
        return redirect("streaming:config_list")


@login_required
def end_streaming_session(request, session_id):
    """
    Properly end a streaming session with cleanup
    """
    try:
        session = get_object_or_404(
            StreamingSession, id=session_id, configuration__user=request.user
        )

        if session.status == "ended":
            return redirect("streaming:session_detail", session_id=session.id)

        with transaction.atomic():
            # Stop SRS stream if needed
            stop_streaming_via_srs("live", session.configuration.stream_key)

            # Update session status
            session.status = "ended"
            session.session_end = timezone.now()
            session.save()

            return redirect("streaming:session_detail", session_id=session.id)

    except Exception as e:
        logger.error(f"Failed to end streaming session: {str(e)}")
        messages.error(request, "Failed to end streaming session")
        return redirect("streaming:session_detail", session_id=session_id)


class StreamingSessionDetailView(LoginRequiredMixin, DetailView):
    """View details of a streaming session"""

    model = StreamingSession
    template_name = "streaming/session_detail.html"
    context_object_name = "session"
    pk_url_kwarg = "session_id"

    def get_queryset(self):
        return StreamingSession.objects.filter(configuration__user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["stream_stats"] = get_stream_stats(
            "live", self.object.configuration.stream_key
        )
        return context


# ============================================================================
# Live Streaming Control
# ============================================================================


@login_required
def go_live(request, config_id, session_id=None):
    """
    Robust go_live implementation with proper validation and error handling
    """
    try:
        # Validate configuration
        config = get_object_or_404(
            StreamingConfiguration, pk=config_id, user=request.user, is_active=True
        )

        # Validate social accounts
        social_accounts = StreamingPlatformAccount.objects.filter(
            user=request.user,
            is_active=True,
            rtmp_url__isnull=False,
            stream_key__isnull=False,
        )

        if not social_accounts.exists():
            return JsonResponse(
                {
                    "status": "error",
                    "message": "No active social accounts with valid RTMP settings",
                },
                status=400,
            )

        # Get or create session
        with transaction.atomic():
            if session_id:
                session = get_object_or_404(
                    StreamingSession, id=session_id, configuration__user=request.user
                )
            else:
                session = StreamingSession.objects.create(
                    configuration=config, status="starting"
                )

            # Start SRS stream
            srs_response = start_streaming_via_srs("live", config.stream_key)

            if not srs_response or srs_response.get("code") != 0:
                session.status = "failed"
                session.save()
                return JsonResponse(
                    {
                        "status": "error",
                        "message": "Failed to initialize streaming server",
                    },
                    status=500,
                )

            # Start social relays
            from streaming.tasks import relay_to_social_task

            relay_task = relay_to_social_task.delay(
                session.id,
                f"rtmp://{settings.SRS_SERVER_HOST}/live/{config.stream_key}",
            )

            # Update session status
            session.status = "live"
            session.save()

            return JsonResponse(
                {
                    "status": "success",
                    "session_uuid": str(session.session_uuid),
                    "session_id": session.id,
                    "relay_task_id": str(relay_task.id),
                }
            )

    except Exception as e:
        logger.error(f"Failed to go live: {str(e)}")
        return JsonResponse(
            {"status": "error", "message": "Failed to start live streaming"}, status=500
        )


# ============================================================================
# Chat and Recording Functions
# ============================================================================


@login_required
@csrf_exempt
@require_POST
def send_chat_message(request, session_id):
    """Handle sending chat messages with validation"""
    try:
        session = get_object_or_404(
            StreamingSession, id=session_id, configuration__user=request.user
        )

        form = ChatMessageForm(request.POST)
        if not form.is_valid():
            return JsonResponse({"status": "error", "errors": form.errors}, status=400)

        with transaction.atomic():
            chat_message = form.save(commit=False)
            chat_message.user = request.user
            chat_message.streaming_session = session
            chat_message.save()

            return JsonResponse({"status": "success", "message_id": chat_message.id})

    except Exception as e:
        logger.error(f"Failed to send chat message: {str(e)}")
        return JsonResponse(
            {"status": "error", "message": "Failed to send message"}, status=500
        )


@login_required
def fetch_chat_messages(request):
    """Fetch chat messages for a session"""
    try:
        session_uuid = request.GET.get("session_uuid")
        if not session_uuid:
            return JsonResponse(
                {"status": "error", "message": "Session UUID is required"}, status=400
            )

        session = get_object_or_404(
            StreamingSession,
            session_uuid=session_uuid,
            configuration__user=request.user,
        )

        messages_qs = (
            session.chat_messages.all()
            .order_by("created_at")
            .values("user__username", "text", "created_at")
        )

        return JsonResponse({"status": "success", "messages": list(messages_qs)})

    except Exception as e:
        logger.error(f"Failed to fetch chat messages: {str(e)}")
        return JsonResponse(
            {"status": "error", "message": "Failed to fetch messages"}, status=500
        )


@login_required
def local_record_session(request):
    """Handle local recording sessions"""
    try:
        if request.method == "POST":
            form = RecordingForm(request.POST)
            if not form.is_valid():
                messages.error(request, "Please correct the errors below")
                return render(request, "streaming/record.html", {"form": form})

            title = form.cleaned_data["title"]
            messages.success(request, f"Recording session '{title}' started")
            return redirect("streaming:studio_enter")

        return render(request, "streaming/record.html", {"form": RecordingForm()})

    except Exception as e:
        logger.error(f"Failed to start recording session: {str(e)}")
        messages.error(request, "Failed to start recording")
        return redirect("streaming:studio_enter")


@login_required
@csrf_exempt
def upload_recorded(request):
    """Handle upload of recorded videos"""
    try:
        if request.method != "POST":
            return JsonResponse(
                {"status": "error", "message": "Only POST requests are allowed"},
                status=405,
            )

        video_file = request.FILES.get("video_file")
        if not video_file:
            return JsonResponse(
                {"status": "error", "message": "No video file provided"}, status=400
            )

        # Save the file with a timestamp
        filename = f"recordings/{timezone.now().timestamp()}_{video_file.name}"
        file_path = default_storage.save(filename, ContentFile(video_file.read()))

        return JsonResponse({"status": "success", "file_path": file_path})

    except Exception as e:
        logger.error(f"Failed to upload recording: {str(e)}")
        return JsonResponse(
            {"status": "error", "message": "Failed to upload recording"}, status=500
        )


# ============================================================================
# Additional Views
# ============================================================================


@login_required
def manage_channels(request):
    """Manage connected social platform accounts"""
    try:
        platform_icons = {
            "youtube": "https://cdn-icons-png.flaticon.com/512/1384/1384060.png",
            "facebook": "https://cdn-icons-png.flaticon.com/512/1384/1384053.png",
            "twitch": "https://cdn-icons-png.flaticon.com/512/5968/5968819.png",
            "instagram": "https://cdn-icons-png.flaticon.com/512/1384/1384063.png",
            "tiktok": "https://cdn-icons-png.flaticon.com/512/3046/3046120.png",
            "telegram": "https://cdn-icons-png.flaticon.com/512/2111/2111646.png",
        }

        if request.method == "POST" and request.POST.get("action") == "remove":
            channel_id = request.POST.get("channel_id")
            if not channel_id:
                messages.error(request, "No channel specified for removal")
                return redirect("streaming:manage_channels")

            try:
                with transaction.atomic():
                    account = StreamingPlatformAccount.objects.get(
                        id=channel_id, user=request.user
                    )
                    account.delete()
                    messages.success(request, "Channel removed successfully")
            except StreamingPlatformAccount.DoesNotExist:
                messages.error(request, "Channel not found or not owned by you")

            return redirect("streaming:manage_channels")

        # Get all user's social accounts
        user_channels = StreamingPlatformAccount.objects.filter(
            user=request.user
        ).order_by("platform")

        # Prepare channel info with status
        user_channels_info = []
        for account in user_channels:
            # Check if both rtmp_url and stream_key are non-empty after stripping whitespace
            if (
                account.rtmp_url
                and account.stream_key
                and account.rtmp_url.strip()
                and account.stream_key.strip()
            ):
                status = "Active"
            else:
                status = "Pending"
            user_channels_info.append(
                {
                    "channel": account,
                    "icon_url": platform_icons.get(account.platform, ""),
                    "status": status,
                }
            )

        return render(
            request,
            "streaming/manage_channels.html",
            {"user_channels_info": user_channels_info},
        )

    except Exception as e:
        logger.error(f"Failed to manage channels: {str(e)}")
        messages.error(request, "An error occurred while loading channels")
        return redirect("dashboard:index")


@login_required
def validate_social_accounts(request):
    """Validate that user has active social accounts for streaming"""
    try:
        accounts = StreamingPlatformAccount.objects.filter(
            user=request.user,
            is_active=True,
            rtmp_url__isnull=False,
            stream_key__isnull=False,
        )

        return JsonResponse(
            {"status": "success", "valid": accounts.exists(), "count": accounts.count()}
        )

    except Exception as e:
        logger.error(f"Failed to validate social accounts: {str(e)}")
        return JsonResponse(
            {"status": "error", "message": "Failed to validate accounts"}, status=500
        )


@login_required
def relay_status(request, session_id):
    """Get status of all relays for a session"""
    try:
        session = get_object_or_404(
            StreamingSession, id=session_id, configuration__user=request.user
        )

        accounts = StreamingPlatformAccount.objects.filter(user=request.user).values(
            "id",
            "platform",
            "rtmp_url",
            "stream_key",
            "relay_status",
            "relay_last_updated",
            "relay_log",
        )

        return JsonResponse(
            {
                "status": "success",
                "session_status": session.status,
                "relays": list(accounts),
            }
        )

    except Exception as e:
        logger.error(f"Failed to get relay status: {str(e)}")
        return JsonResponse(
            {"status": "error", "message": "Failed to get relay status"}, status=500
        )


@login_required
def restart_relay(request, account_id):
    """Restart a failed relay for a specific account"""
    try:
        account = get_object_or_404(
            StreamingPlatformAccount, id=account_id, user=request.user
        )

        # Get the most recent active session
        session = (
            StreamingSession.objects.filter(
                configuration__user=request.user, status__in=["live", "partial"]
            )
            .order_by("-session_start")
            .first()
        )

        if not session:
            return JsonResponse(
                {"status": "error", "message": "No active streaming session found"},
                status=400,
            )

        # Start the relay
        from streaming.tasks import relay_to_single_social

        relay_to_single_social.delay(
            session.id,
            f"{account.rtmp_url.rstrip('/')}/{account.stream_key}",
            f"rtmp://{settings.SRS_SERVER_HOST}/live/{session.configuration.stream_key}",
            account.id,
        )

        return JsonResponse({"status": "success", "message": "Relay restart initiated"})

    except Exception as e:
        logger.error(f"Failed to restart relay: {str(e)}")
        return JsonResponse(
            {"status": "error", "message": "Failed to restart relay"}, status=500
        )


@login_required
def studio_enter(request):
    try:
        # Get active configuration
        config = StreamingConfiguration.objects.filter(
            user=request.user, is_active=True
        ).first()

        if not config:
            messages.error(request, "No active streaming configuration found")
            return redirect("streaming:config_create")
        session = StreamingSession.objects.create(
            configuration=config, status="starting"
        )
        social_accounts = StreamingPlatformAccount.objects.filter(user=request.user)
        return render(
            request,
            "streaming/studio_enter.html",
            {
                "session_uuid": session.session_uuid,
                "config": config,
                "social_accounts": social_accounts,
                "record_mode": "record" in request.GET,
                "session": session,
            },
        )
    except Exception as e:
        logger.error(f"Failed to enter studio: {str(e)}")
        messages.error(request, "Failed to initialize streaming studio")
        return redirect("streaming:config_list")


class SRSConsoleView(LoginRequiredMixin, TemplateView):
    """View for the SRS console iframe"""

    template_name = "streaming/srs_console.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["srs_console_url"] = getattr(
            settings, "SRS_CONSOLE_URL", "http://localhost:8080/console/"
        )
        return context


# For backward compatibility with URL imports
def srs_console(request):
    """Legacy function view for SRS console"""
    return SRSConsoleView.as_view()(request)


# Utility function to be used in URLs
def check_stream_status(request, stream_key):
    """Check the status of a stream in SRS"""
    stats = get_stream_stats("live", stream_key)
    return JsonResponse({"status": "ok", "srs_stats": stats})
