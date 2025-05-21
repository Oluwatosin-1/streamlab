# streaming/views/srs_hooks.py
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, redirect
from streaming.models import (
    StreamingConfiguration,
    StreamingSession,
    StreamingPlatformAccount,
)
from streaming.tasks import relay_to_social_task
from django.contrib.auth.decorators import login_required

logger = logging.getLogger(__name__)


@csrf_exempt
def srs_on_publish(request):
    """
    This view is called by SRS when a stream is published.
    It should:
      - Parse the incoming JSON (which includes the stream key and app)
      - Look up the active streaming configuration by stream key
      - Create a new streaming session
      - Trigger a background task to relay the stream to all connected social platforms
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    stream_key = data.get("stream")
    app = data.get("app")

    # Look up the configuration using the provided stream key
    try:
        config = StreamingConfiguration.objects.get(
            stream_key=stream_key, is_active=True
        )
    except StreamingConfiguration.DoesNotExist:
        logger.error("Stream key not found: %s", stream_key)
        return JsonResponse({"error": "Stream key not found."}, status=404)

    # Create a new streaming session
    session = StreamingSession.objects.create(configuration=config, status="live")

    # Retrieve connected social accounts for the user
    social_accounts = StreamingPlatformAccount.objects.filter(user=config.user)

    # For each connected social account with valid RTMP details, trigger a relay task
    for account in social_accounts:
        if account.rtmp_url and account.stream_key:
            rtmp_target = f"{account.rtmp_url.rstrip('/')}/{account.stream_key}"
            relay_to_social_task.delay(session.id, rtmp_target)

    logger.info("SRS on_publish processed for stream key: %s", stream_key)
    return JsonResponse({"status": "ok", "session_uuid": str(session.session_uuid)})


@csrf_exempt
def srs_on_unpublish(request):
    """
    This view is called by SRS when a stream ends.
    You can use it to mark the streaming session as ended.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    stream_key = data.get("stream")

    try:
        config = StreamingConfiguration.objects.get(
            stream_key=stream_key, is_active=True
        )
    except StreamingConfiguration.DoesNotExist:
        logger.error("Stream key not found on unpublish: %s", stream_key)
        return JsonResponse({"error": "Stream key not found."}, status=404)

    # Mark the last live session for this config as ended
    session = config.sessions.filter(status="live").last()
    if session:
        session.status = "ended"
        session.session_end = timezone.now()
        session.save()
        logger.info("Session %s marked as ended on unpublish.", session.session_uuid)
    return JsonResponse({"status": "ok"})
