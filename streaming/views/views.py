from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib import messages

from dashboard.models import DashboardSettings
from payments.models import UserSubscription
from streaming.forms import ChatMessageForm
from streaming.models import StreamingConfiguration, StreamingSession
from users.models import SocialAccount
  
# OAuth endpoints for YouTube and Facebook
@login_required
def connect_youtube_oauth(request):
    # Initiate OAuth for YouTube. Construct the authorization URL.
    authorization_url = (
        "https://accounts.google.com/o/oauth2/auth?"
        "client_id=YOUR_CLIENT_ID&"
        "redirect_uri=" + request.build_absolute_uri(reverse("streaming:youtube_callback")) + "&"
        "response_type=code&"
        "scope=https://www.googleapis.com/auth/youtube.force-ssl"
    )
    return redirect(authorization_url)


@login_required
def youtube_callback(request):
    # Handle YouTube OAuth callback.
    code = request.GET.get("code")
    if not code:
        return HttpResponse("Error: No code returned", status=400)
    # Here, exchange the code for an access token and save credentials.
    return HttpResponse("YouTube OAuth successful.")


@login_required
def connect_facebook_oauth(request):
    # Initiate OAuth for Facebook.
    authorization_url = (
        "https://www.facebook.com/v9.0/dialog/oauth?"
        "client_id=YOUR_FACEBOOK_CLIENT_ID&"
        "redirect_uri=" + request.build_absolute_uri(reverse("streaming:facebook_callback")) + "&"
        "response_type=code&"
        "scope=public_profile,live_video"
    )
    return redirect(authorization_url)


@login_required
def facebook_callback(request):
    # Handle Facebook OAuth callback.
    code = request.GET.get("code")
    if not code:
        return HttpResponse("Error: No code returned", status=400)
    # Here, exchange the code for an access token and save credentials.
    return HttpResponse("Facebook OAuth successful.")


# Recording and additional live controls

@login_required
def local_record_session(request):
    # Display a page for starting a local recording session.
    return render(request, "streaming/local_record.html")


@login_required
@require_http_methods(["POST"])
def upload_recorded(request):
    # Handle the uploaded recorded file.
    if "recorded_file" not in request.FILES:
        return HttpResponse("No file uploaded", status=400)
    recorded_file = request.FILES["recorded_file"]
    # In a real implementation, save the file (e.g., in a Recording model).
    return HttpResponse("Recorded file uploaded successfully.")


@login_required
def go_live(request, config_id):
    # Trigger a live session based on a given configuration.
    config = get_object_or_404(StreamingConfiguration, pk=config_id, user=request.user)
    session = StreamingSession.objects.create(configuration=config, status="live")
    # Optionally, trigger an asynchronous task to go live on external platforms.
    # from .tasks import go_live_task
    # go_live_task.delay(session.id)
    return redirect(reverse("streaming:session_detail", kwargs={"session_id": session.id}))


@login_required
def stop_live(request, session_id):
    # Stop an active live session.
    session = get_object_or_404(StreamingSession, id=session_id, configuration__user=request.user)
    if session.status != "live":
        return HttpResponse("Session is not live", status=400)
    session.status = "ended"
    session.session_end = timezone.now()
    session.save()
    # Optionally, trigger an asynchronous task to stop external streaming.
    # from .tasks import stop_live_task
    # stop_live_task.delay(session.id)
    return redirect(reverse("streaming:session_detail", kwargs={"session_id": session.id}))


@login_required
def stream_stats(request, session_id):
    # Return streaming session statistics as JSON.
    session = get_object_or_404(StreamingSession, id=session_id, configuration__user=request.user)
    stats = {
        "viewers_count": session.viewers_count,
        "session_start": session.session_start.isoformat(),
        "session_end": session.session_end.isoformat() if session.session_end else None,
        "status": session.status,
    }
    return JsonResponse(stats)


# Chat endpoints for AJAX
@login_required
@csrf_exempt
@require_http_methods(["POST"])
def send_chat_message(request, session_id):
    # API endpoint to send a chat message via AJAX.
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
    # API endpoint to fetch chat messages via AJAX.
    session = get_object_or_404(StreamingSession, id=session_id, configuration__user=request.user)
    messages = session.chat_messages.all().order_by("created_at").values("user__username", "text", "created_at")
    return JsonResponse({"status": "success", "messages": list(messages)})


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
def connect_social(request, platform):
    # For now, simply return a placeholder response.
    return HttpResponse(f"Connect {platform.capitalize()} account - placeholder page.")


@login_required
def studio(request):
    # Optionally, load the active configuration or session if it exists.
    config = StreamingConfiguration.objects.filter(user=request.user).first()
    session = None
    if config:
        session = config.sessions.filter(status="live").first()
    # You might also pass overlay settings, chat history, etc.
    context = {
        "configuration": config,
        "session": session,
        "record_mode": False,  # or set based on your logic
    }
    return render(request, "streaming/studio.html", context)