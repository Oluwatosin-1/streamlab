import subprocess
import logging
from celery import shared_task, group, chain
from django.db import transaction
from django.utils import timezone
from django.conf import settings
import requests

from .models import StreamingSession, StreamingPlatformAccount, ScheduledVideo
from .srs_utils import start_streaming_via_srs, stop_streaming_via_srs, get_stream_stats

logger = logging.getLogger(__name__)

class StreamingError(Exception):
    """Custom exception for streaming-related errors"""
    pass

@shared_task(bind=True, max_retries=3)
def relay_to_single_social(self, session_id, platform_rtmp, source_rtmp, account_id=None):
    """
    Relay the central RTMP stream to one external social endpoint with robust error handling
    """
    try:
        with transaction.atomic():
            # Get session and validate
            session = StreamingSession.objects.select_for_update().get(id=session_id)
            account = None
            
            if account_id:
                account = StreamingPlatformAccount.objects.select_for_update().get(
                    id=account_id,
                    user=session.configuration.user
                )

            # Build the FFmpeg command
            command = [
                'ffmpeg',
                '-loglevel', 'info',
                '-re',  # Read input at native frame rate
                '-i', source_rtmp,
                '-c:v', 'copy',  # Stream copy (no re-encoding)
                '-c:a', 'copy',
                '-f', 'flv',
                '-flvflags', 'no_duration_filesize',
                platform_rtmp
            ]

            logger.info(
                "Starting relay for session %s to %s (Account: %s)",
                session_id, platform_rtmp, account_id or "unknown"
            )

            # Start the process
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            # Update status
            if account:
                account.relay_status = "active"
                account.relay_last_updated = timezone.now()
                account.save()

            # Wait for process to complete (with timeout)
            try:
                stdout, stderr = process.communicate(timeout=10)
                if process.returncode != 0:
                    raise StreamingError(f"FFmpeg failed with code {process.returncode}: {stderr}")
            except subprocess.TimeoutExpired:
                # If we get here, the process is running successfully
                logger.info("Relay to %s established successfully", platform_rtmp)
                return {
                    "status": "success",
                    "platform_rtmp": platform_rtmp,
                    "process_pid": process.pid
                }

    except StreamingSession.DoesNotExist as e:
        logger.error("Session %s not found: %s", session_id, str(e))
        raise self.retry(exc=e, countdown=60)
    except StreamingPlatformAccount.DoesNotExist as e:
        logger.error("Account %s not found: %s", account_id, str(e))
        raise self.retry(exc=e, countdown=60)
    except Exception as e:
        logger.error("Error in relay_to_single_social: %s", str(e))
        
        if account:
            account.relay_status = "failed"
            account.relay_log = str(e)
            account.relay_last_updated = timezone.now()
            account.save()

        raise self.retry(exc=e, countdown=60)

@shared_task(bind=True, max_retries=3)
def relay_to_social_task(self, session_id, source_rtmp):
    """
    Main task to relay stream to all connected social platforms with comprehensive error handling
    """
    try:
        with transaction.atomic():
            # Get session with lock to prevent race conditions
            session = StreamingSession.objects.select_for_update().get(id=session_id)
            
            # Get all active social accounts with valid RTMP settings
            social_accounts = StreamingPlatformAccount.objects.filter(
                user=session.configuration.user,
                is_active=True,
                rtmp_url__isnull=False,
                stream_key__isnull=False
            )
            
            if not social_accounts.exists():
                logger.warning("No valid social accounts for session %s", session_id)
                session.status = "failed"
                session.save()
                raise StreamingError("No active social accounts with valid RTMP settings")

            # Prepare tasks for each platform
            tasks = []
            for account in social_accounts:
                endpoint = f"{account.rtmp_url.rstrip('/')}/{account.stream_key}"
                tasks.append(
                    relay_to_single_social.s(
                        session_id,
                        endpoint,
                        source_rtmp,
                        account.id
                    ).set(
                        queue=f'relay_{account.platform}'
                    )
                )

            # Execute tasks in parallel
            job = group(tasks)
            results = job.apply_async().get(disable_sync_subtasks=False)

            # Check results
            failed_relays = [r for r in results if r.get('status') != 'success']
            
            if failed_relays:
                session.status = "partial"
                session.save()
                logger.error("Some relays failed: %s", failed_relays)
                return {
                    "status": "partial",
                    "success_count": len(results) - len(failed_relays),
                    "failed_count": len(failed_relays),
                    "failed_relays": failed_relays
                }
            else:
                session.status = "live"
                session.save()
                logger.info("All %d relays started successfully", len(results))
                return {
                    "status": "success",
                    "relay_count": len(results)
                }

    except StreamingSession.DoesNotExist as e:
        logger.error("Session %s not found: %s", session_id, str(e))
        raise self.retry(exc=e, countdown=60)
    except Exception as e:
        logger.error("Error in relay_to_social_task: %s", str(e))
        session.status = "failed"
        session.save()
        raise self.retry(exc=e, countdown=60)

@shared_task(bind=True, max_retries=3)
def publish_scheduled_video_task(self, scheduled_id):
    """
    Task to start streaming for a scheduled video with SRS API integration
    """
    try:
        with transaction.atomic():
            scheduled = ScheduledVideo.objects.select_for_update().get(id=scheduled_id)
            
            # Start stream via SRS API
            srs_response = start_streaming_via_srs(
                app="live",
                stream_name=scheduled.stream_key
            )
            
            if not srs_response or srs_response.get('code') != 0:
                raise StreamingError("Failed to start SRS stream")
            
            # Start social relays
            source_rtmp = f"rtmp://{settings.SRS_SERVER_HOST}/live/{scheduled.stream_key}"
            relay_task = relay_to_social_task.s(
                scheduled.session.id,
                source_rtmp
            )
            
            # Update scheduled video
            scheduled.scheduled_time = timezone.now()
            scheduled.is_published = True
            scheduled.save()
            
            return {
                "status": "success",
                "srs_response": srs_response,
                "relay_task_id": relay_task.id
            }

    except ScheduledVideo.DoesNotExist as e:
        logger.error("Scheduled video %s not found: %s", scheduled_id, str(e))
        raise self.retry(exc=e, countdown=60)
    except Exception as e:
        logger.error("Error in publish_scheduled_video_task: %s", str(e))
        raise self.retry(exc=e, countdown=60)

@shared_task(bind=True, max_retries=3)
def unpublish_scheduled_video_task(self, scheduled_id):
    """
    Task to stop streaming for a scheduled video with SRS API integration
    """
    try:
        with transaction.atomic():
            scheduled = ScheduledVideo.objects.select_for_update().get(id=scheduled_id)
            
            # Stop stream via SRS API
            srs_response = stop_streaming_via_srs(
                app="live",
                stream_name=scheduled.stream_key
            )
            
            # Update scheduled video
            scheduled.is_published = False
            scheduled.save()
            
            return {
                "status": "success",
                "srs_response": srs_response
            }

    except ScheduledVideo.DoesNotExist as e:
        logger.error("Scheduled video %s not found: %s", scheduled_id, str(e))
        raise self.retry(exc=e, countdown=60)
    except Exception as e:
        logger.error("Error in unpublish_scheduled_video_task: %s", str(e))
        raise self.retry(exc=e, countdown=60)

@shared_task
def monitor_stream_health(session_id):
    """
    Periodic task to monitor stream health and restart failed relays
    """
    try:
        session = StreamingSession.objects.get(id=session_id)
        if session.status not in ["live", "partial"]:
            return  # Only monitor active sessions

        # Check SRS stream status
        stats = get_stream_stats("live", session.configuration.stream_key)
        if not stats or stats.get('code') != 0:
            logger.warning("Stream %s not found in SRS", session.configuration.stream_key)
            return

        # Check and restart failed relays
        failed_accounts = StreamingPlatformAccount.objects.filter(
            user=session.configuration.user,
            relay_status="failed"
        )
        
        if failed_accounts.exists():
            logger.info("Found %d failed relays, attempting to restart", failed_accounts.count())
            source_rtmp = session.configuration.get_full_rtmp_url()
            for account in failed_accounts:
                relay_to_single_social.delay(
                    session_id,
                    f"{account.rtmp_url.rstrip('/')}/{account.stream_key}",
                    source_rtmp,
                    account.id
                )

    except Exception as e:
        logger.error("Error in monitor_stream_health: %s", str(e))