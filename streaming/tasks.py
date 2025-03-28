# streaming/tasks.py
import logging
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.db import transaction
from django.utils import timezone

from streaming.models import StreamingSession
from streaming.srs_utils import start_streaming_via_srs, stop_streaming_via_srs

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def relay_stream_task(self, session_id):
    """
    Example: sets up the relay to SRS or external platform.
    If needed, we can also call FFmpeg here to push from SRS to YouTube, etc.
    """
    try:
        with transaction.atomic():
            session = StreamingSession.objects.select_for_update().get(id=session_id)
            if session.status != "live":
                logger.warning("Session %s is not live. Cannot relay.", session.session_uuid)
                return

            app = "live"
            stream_key = session.configuration.stream_key or "mystream"
            # Possibly you do something with FFmpeg to relay from SRS to other platforms
            result = start_streaming_via_srs(app, stream_key, retries=1) 
            # If result is None, we raise to trigger Celery retry
            if not result:
                raise ValueError(f"Failed to start streaming for {stream_key}")

            logger.info("Relay stream initiated for session %s (%s).", session.session_uuid, stream_key)
    except StreamingSession.DoesNotExist:
        logger.error("relay_stream_task: Session %d does not exist.", session_id)
    except ValueError as exc:
        logger.warning("relay_stream_task encountered an error: %s. Retrying...", exc)
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error("Max retries exceeded in relay_stream_task for session %d", session_id)
            # Optionally mark session as error:
            session = StreamingSession.objects.get(id=session_id)
            session.end_session(mark_error=True, error_message=str(exc))
    except Exception as exc:
        logger.exception("relay_stream_task encountered unexpected error. Retrying...")
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error("Max retries exceeded in relay_stream_task for session %d", session_id)
            session = StreamingSession.objects.get(id=session_id)
            session.end_session(mark_error=True, error_message=str(exc))


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def stop_relay_task(self, session_id):
    """
    Example task to stop the SRS relay/stream.
    """
    try:
        with transaction.atomic():
            session = StreamingSession.objects.select_for_update().get(id=session_id)
            if session.status != "live":
                logger.warning("Session %s not in 'live' status. Nothing to stop.", session.session_uuid)
                return

            app = "live"
            stream_key = session.configuration.stream_key or "mystream"
            response = stop_streaming_via_srs(app, stream_key, retries=1)
            if not response:
                raise ValueError(f"Failed to stop streaming for {stream_key}")

            # Mark as ended in DB
            session.end_session()
            logger.info("Stopped relay for session %s", session.session_uuid)
    except StreamingSession.DoesNotExist:
        logger.error("stop_relay_task: Session %d does not exist.", session_id)
    except ValueError as exc:
        logger.warning("stop_relay_task encountered an error: %s. Retrying...", exc)
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error("Max retries exceeded in stop_relay_task for session %d", session_id)
            # Mark as error if needed
            session = StreamingSession.objects.get(id=session_id)
            session.end_session(mark_error=True, error_message=str(exc))
    except Exception as exc:
        logger.exception("stop_relay_task encountered unexpected error. Retrying...")
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error("Max retries exceeded in stop_relay_task for session %d", session_id)
            session = StreamingSession.objects.get(id=session_id)
            session.end_session(mark_error=True, error_message=str(exc))
