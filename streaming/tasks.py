from celery import shared_task
from django.utils import timezone
from .models import StreamingSession, ScheduledVideo
import subprocess
import logging

logger = logging.getLogger(__name__)

@shared_task
def start_stream_task(session_id):
    try:
        session = StreamingSession.objects.get(id=session_id)
    except StreamingSession.DoesNotExist:
        logger.error("start_stream_task: Session %s does not exist", session_id)
        return
    session.status = 'live'
    session.save()
    logger.info("start_stream_task: Session %s is now live", session_id)

@shared_task
def stop_stream_task(session_id):
    try:
        session = StreamingSession.objects.get(id=session_id)
    except StreamingSession.DoesNotExist:
        logger.error("stop_stream_task: Session %s does not exist", session_id)
        return
    session.status = 'ended'
    session.session_end = timezone.now()
    session.save()
    logger.info("stop_stream_task: Session %s has ended", session_id)

@shared_task
def publish_scheduled_video_task(scheduled_id):
    try:
        scheduled_video = ScheduledVideo.objects.get(id=scheduled_id)
    except ScheduledVideo.DoesNotExist:
        logger.error("publish_scheduled_video_task: Scheduled video %s does not exist", scheduled_id)
        return
    scheduled_video.is_published = True
    scheduled_video.save()
    logger.info("publish_scheduled_video_task: Scheduled video %s published", scheduled_id)

@shared_task
def go_live_task(session_id):
    try:
        session = StreamingSession.objects.get(id=session_id)
    except StreamingSession.DoesNotExist:
        logger.error("go_live_task: Session %s does not exist", session_id)
        return "Session does not exist."
    
    rtmp_source = session.configuration.get_full_rtmp_url()
    external_rtmp_url = "rtmp://external.platform/live/streamkey"  # Replace with your target endpoint

    command = [
        "ffmpeg",
        "-i", rtmp_source,
        "-c", "copy",
        "-f", "flv",
        external_rtmp_url
    ]
    logger.info("go_live_task: Running command: %s", " ".join(command))
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        logger.exception("go_live_task: FFmpeg command failed: %s", e)
        session.error_message = str(e)
        session.status = 'error'
        session.save()
        return "Streaming failed."
    
    session.status = "live"
    session.save()
    logger.info("go_live_task: Session %s is now live", session_id)
    return "Streaming started."

@shared_task
def relay_stream_task(session_id):
    try:
        session = StreamingSession.objects.get(id=session_id)
    except StreamingSession.DoesNotExist:
        logger.error("relay_stream_task: Session %s not found", session_id)
        return "Session not found"

    rtmp_source = session.configuration.get_full_rtmp_url()
    external_rtmp_url = "rtmp://external.platform/live/streamkey"  # Replace as needed

    command = [
        "ffmpeg",
        "-i", rtmp_source,
        "-c", "copy",
        "-f", "flv",
        external_rtmp_url
    ]
    logger.info("relay_stream_task: Running command: %s", " ".join(command))
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        logger.exception("relay_stream_task: FFmpeg command failed: %s", e)
        session.error_message = str(e)
        session.status = 'error'
        session.save()
        return "Relay failed."
    
    session.status = "live"
    session.save()
    logger.info("relay_stream_task: Relay started for session %s", session_id)
    return "Relay started"
