# streaming/srs_utils.py
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

def start_streaming_via_srs(app, stream_name, retries=3):
    """
    Call the SRS REST API to start streaming.
    Retries up to `retries` times if the request fails.
    """
    url = f"http://{settings.SRS_SERVER_HOST}:{settings.SRS_API_PORT}/api/v1/streams/{app}/{stream_name}/start"
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(url, timeout=5)
            if response.status_code == 200:
                logger.info("SRS streaming started for %s/%s (attempt %d)", app, stream_name, attempt)
                return response.json()
            else:
                logger.error("SRS start_streaming error (attempt %d): %s", attempt, response.text)
        except requests.RequestException as e:
            logger.exception("Exception starting stream via SRS on attempt %d: %s", attempt, e)
    logger.error("All attempts to start SRS stream for %s/%s failed.", app, stream_name)
    return None


def stop_streaming_via_srs(app, stream_name, retries=3):
    """
    Call the SRS REST API to stop streaming.
    Retries up to `retries` times if the request fails.
    """
    url = f"http://{settings.SRS_SERVER_HOST}:{settings.SRS_API_PORT}/api/v1/streams/{app}/{stream_name}/stop"
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(url, timeout=5)
            if response.status_code == 200:
                logger.info("SRS streaming stopped for %s/%s (attempt %d)", app, stream_name, attempt)
                return response.json()
            else:
                logger.error("SRS stop_streaming error (attempt %d): %s", attempt, response.text)
        except requests.RequestException as e:
            logger.exception("Exception stopping stream via SRS on attempt %d: %s", attempt, e)
    logger.error("All attempts to stop SRS stream for %s/%s failed.", app, stream_name)
    return None


def get_stream_stats(app, stream_name, retries=3):
    """
    Call the SRS REST API to retrieve real-time stream statistics.
    Retries up to `retries` times if the request fails.
    """
    url = f"http://{settings.SRS_SERVER_HOST}:{settings.SRS_API_PORT}/api/v1/streams/{app}/{stream_name}/stat"
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                logger.info("SRS stats retrieved for %s/%s (attempt %d)", app, stream_name, attempt)
                return response.json()
            else:
                logger.error("SRS get_stream_stats error (attempt %d): %s", attempt, response.text)
        except requests.RequestException as e:
            logger.exception("Exception retrieving stream stats on attempt %d: %s", attempt, e)
    logger.error("All attempts to get SRS stats for %s/%s failed.", app, stream_name)
    return None
