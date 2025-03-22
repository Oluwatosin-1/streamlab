# streaming/tasks.py
from celery import shared_task
from django.utils import timezone
from .models import StreamingSession, ScheduledVideo 
import subprocess 

@shared_task
def start_stream_task(session_id):
    try:
        session = StreamingSession.objects.get(id=session_id)
    except StreamingSession.DoesNotExist:
        return
    # Connect to external APIs, set session.status = 'live', etc.
    session.status = 'live'
    session.save()

@shared_task
def stop_stream_task(session_id):
    try:
        session = StreamingSession.objects.get(id=session_id)
    except StreamingSession.DoesNotExist:
        return
    # Stop the external stream
    session.status = 'ended'
    session.session_end = timezone.now()
    session.save()

@shared_task
def publish_scheduled_video_task(scheduled_id):
    try:
        scheduled_video = ScheduledVideo.objects.get(id=scheduled_id)
    except ScheduledVideo.DoesNotExist:
        return
    # Possibly upload or push to external RTMP
    scheduled_video.is_published = True
    scheduled_video.save()

@shared_task
def go_live_task(session_id):
    try:
        session = StreamingSession.objects.get(id=session_id)
    except StreamingSession.DoesNotExist:
        return "Session does not exist."

    # Example: Construct the command to relay the RTMP stream.
    # This is pseudo-code. In practice, you would construct your FFmpeg command
    # based on your streaming configuration and target platforms.
    rtmp_source = session.configuration.get_full_rtmp_url()
    external_rtmp_url = "rtmp://external.platform/live/streamkey"  # Replace with target endpoint
    
    # Construct FFmpeg command
    command = [
        "ffmpeg",
        "-i", rtmp_source,
        "-c", "copy",
        "-f", "flv",
        external_rtmp_url
    ]
    
    # Execute the command; note that for production you might want to manage the process differently
    subprocess.run(command)
    
    # Optionally update session or log the outcome
    session.status = "live"
    session.save()
    return "Streaming started."
