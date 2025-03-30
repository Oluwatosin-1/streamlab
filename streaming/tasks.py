# streaming/tasks.py
from celery import shared_task
import subprocess
import logging
from django.utils import timezone
from .models import StreamingSession

logger = logging.getLogger(__name__)

@shared_task
def relay_to_social_task(session_id, platform_rtmp):
    """
    Takes an RTMP stream from SRS and forwards it to the given social platform RTMP endpoint.
    """
    try:
        session = StreamingSession.objects.get(id=session_id)
    except StreamingSession.DoesNotExist:
        logger.error("relay_to_social_task: Session %s not found", session_id)
        return "Session not found."

    # Build the local RTMP source URL using the stream key stored in the configuration.
    # Make sure to update 'your_srs_server_ip' with the correct host or use a setting.
    local_rtmp_source = f"rtmp://185.113.249.211/live/{session.configuration.stream_key}"
    
    command = [
        "ffmpeg",
        "-re",  # read input at native frame rate
        "-i", local_rtmp_source,
        "-c:v", "copy",
        "-c:a", "copy",
        "-f", "flv",
        platform_rtmp  # e.g., rtmp://live-api-s.facebook.com:80/rtmp/...
    ]

    logger.info("[Celery] relay_to_social_task command: %s", " ".join(command))
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        logger.exception("relay_to_social_task: FFmpeg command failed: %s", e)
        session.status = "error"
        session.save()
        return "Relay failed."

    session.status = "live"
    session.save()
    logger.info("relay_to_social_task: Relay started for session %s", session_id)
    return "Relay started."
