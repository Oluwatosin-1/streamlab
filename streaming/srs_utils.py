# streaming/srs_utils.py
import requests
from django.conf import settings

def start_streaming_via_srs(app, stream_name):
    """
    Call SRS REST API to start streaming.
    """
    url = f"http://{settings.SRS_SERVER_HOST}:{settings.SRS_API_PORT}/api/v1/streams/{app}/{stream_name}/start"
    try:
        response = requests.post(url, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            print("SRS start_streaming_via_srs error:", response.text)
            return None
    except Exception as e:
        print("Exception starting stream via SRS:", e)
        return None 

def stop_streaming_via_srs(app, stream_name):
    """
    Call SRS REST API to stop streaming.
    """
    url = f"http://{settings.SRS_SERVER_HOST}:{settings.SRS_API_PORT}/api/v1/streams/{app}/{stream_name}/stop"
    try:
        response = requests.post(url, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            print("SRS stop_streaming_via_srs error:", response.text)
            return None
    except Exception as e:
        print("Exception stopping stream via SRS:", e)
        return None

def get_stream_stats(app, stream_name):
    """
    Call SRS REST API to retrieve real-time stream statistics.
    """
    url = f"http://{settings.SRS_SERVER_HOST}:{settings.SRS_API_PORT}/api/v1/streams/{app}/{stream_name}/stat"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            print("SRS get_stream_stats error:", response.text)
            return None
    except Exception as e:
        print("Exception retrieving stream stats from SRS:", e)
        return None
