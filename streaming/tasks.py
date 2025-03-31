import subprocess
import logging
from celery import shared_task, group
from django.db import transaction
from django.utils import timezone
from .models import StreamingSession, StreamingPlatformAccount
from streaming.models import ScheduledVideo  # if needed

logger = logging.getLogger(__name__)

@shared_task
def relay_to_single_social(session_id, platform_rtmp, source_rtmp):
    """
    Relay the central RTMP stream (from source_rtmp) to one external social endpoint.
    """
    try:
        session = StreamingSession.objects.get(id=session_id)
    except StreamingSession.DoesNotExist:
        msg = f"Session {session_id} not found."
        logger.error(msg)
        return {"platform_rtmp": platform_rtmp, "status": "error", "message": msg}

    # Optionally look up the account for additional logging (adjust lookup as needed).
    account = StreamingPlatformAccount.objects.filter(
        user=session.configuration.user,
        rtmp_url__icontains=platform_rtmp.split("/")[0]  # simplistic check; adjust as needed
    ).first()

    # Build the source URL using the provided source_rtmp and append the stream key.
    # For example, if source_rtmp is "rtmp://SRS_HOST/live" and the stream key is stored in the configuration:
    source_url = f"{source_rtmp.rstrip('/')}/{session.configuration.stream_key}"

    command = [
        "ffmpeg",
        "-re",  # Read input at native frame rate.
        "-i", source_url,
        "-c:v", "copy",
        "-c:a", "copy",
        "-f", "flv",
        platform_rtmp,  # The external RTMP endpoint.
    ]
    
    logger.info("Executing FFmpeg command for endpoint %s: %s", platform_rtmp, " ".join(command))
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        log_output = result.stdout + "\n" + result.stderr
        status = "success"
    except subprocess.CalledProcessError as e:
        log_output = (e.stdout or "") + "\n" + (e.stderr or "") if (e.stdout or e.stderr) else str(e)
        status = "error"
        session.status = "error"
        session.save()
        logger.exception("FFmpeg relay command failed for endpoint %s: %s", platform_rtmp, e)

    if account:
        account.relay_status = status
        account.relay_log = log_output
        account.relay_last_updated = timezone.now()
        account.save()

    logger.info("Relay %s for endpoint %s", status, platform_rtmp)
    return {"platform_rtmp": platform_rtmp, "status": status, "log": log_output}


@shared_task
def relay_to_social_task(session_id, source_rtmp):
    """
    Relay the central RTMP stream to all connected social platforms.
    Accepts two arguments: session_id and the source RTMP URL (e.g. from config.get_full_rtmp_url()).
    """
    try:
        session = StreamingSession.objects.get(id=session_id)
    except StreamingSession.DoesNotExist:
        logger.error("relay_to_social_task: Session %s not found", session_id)
        return "Session not found."
    
    social_accounts = StreamingPlatformAccount.objects.filter(user=session.configuration.user)
    endpoints = []
    for account in social_accounts:
        if account.rtmp_url and account.stream_key:
            endpoint = f"{account.rtmp_url.rstrip('/')}/{account.stream_key}"
            endpoints.append(endpoint)
    
    if not endpoints:
        msg = "No social accounts with valid RTMP settings found."
        logger.warning(msg)
        return msg

    # Create a Celery group to relay to each endpoint concurrently.
    tasks = group(relay_to_single_social.s(session.id, endpoint, source_rtmp) for endpoint in endpoints)
    results = tasks.apply_async().get()  # Wait for all tasks to finish.
    
    errors = [r for r in results if r.get("status") != "success"]
    if errors:
        session.status = "error"
        session.save()
        logger.error("Some relays failed: %s", errors)
        return {"status": "error", "errors": errors}
    else:
        logger.info("All relays succeeded for session %s", session.session_uuid)
        return {"status": "success", "results": results}

@shared_task
def publish_scheduled_video_task(scheduled_id):
    """
    Task to start streaming for a scheduled video.
    This might call SRS's API to start the stream.
    """
    try:
        scheduled = ScheduledVideo.objects.get(id=scheduled_id)
    except ScheduledVideo.DoesNotExist:
        logger.error("publish_scheduled_video_task: Scheduled video %s not found", scheduled_id)
        return "Scheduled video not found."
    
    # Here you would trigger your SRS API to start streaming.
    # For example:
    # response = start_streaming_via_srs(app="live", stream_name=scheduled.stream_key)
    # For this example, we assume the stream starts successfully.
    logger.info("Publishing scheduled video %s for user %s", scheduled.id, scheduled.user)
    
    # Optionally, update additional fields (e.g., stream_start time).
    scheduled.scheduled_time = timezone.now()
    scheduled.save()
    return "Published successfully."

@shared_task
def unpublish_scheduled_video_task(scheduled_id):
    """
    Task to stop streaming for a scheduled video.
    This might call SRS's API to stop the stream.
    """
    try:
        scheduled = ScheduledVideo.objects.get(id=scheduled_id)
    except ScheduledVideo.DoesNotExist:
        logger.error("unpublish_scheduled_video_task: Scheduled video %s not found", scheduled_id)
        return "Scheduled video not found."
    
    # Here you would trigger your SRS API to stop streaming.
    # For example:
    # response = stop_streaming_via_srs(app="live", stream_name=scheduled.stream_key)
    logger.info("Unpublishing scheduled video %s for user %s", scheduled.id, scheduled.user)
    
    # Mark the video as unpublished (draft).
    scheduled.is_published = False
    scheduled.save()
    return "Unpublished successfully."
