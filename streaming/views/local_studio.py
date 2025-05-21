# streaming/views/local_studio.py

import uuid
import os
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.http import JsonResponse, HttpResponseBadRequest 
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from streaming.models import StreamingConfiguration, StreamingSession



@login_required
def studio_local(request):
    """
    A local‑only recording “studio” (no live → social relays).
    """
    # pick your active config or redirect
    config = StreamingConfiguration.objects.filter(
        user=request.user, is_active=True
    ).first()
    if not config:
        return redirect("streaming:config_create")

    # create a one‑off session (for session_uuid)
    session = StreamingSession.objects.create(
        configuration=config, status="starting"
    )

    return render(request, "streaming/studio_enter.html", {
        "session_uuid": session.session_uuid,
        "config": config,
        "record_mode": True,       # means “local only”
        "session": session,
    })


@login_required
def list_local_recordings(request):
    """
    Returns JSON list of all files saved under MEDIA_ROOT/recordings/,
    so you can list previously recorded clips.
    """
    prefix = "recordings/"
    try:
        # default_storage.listdir returns (dirs, files)
        _, files = default_storage.listdir(prefix)
    except Exception:
        files = []

    recordings = []
    for fname in files:
        # build a public URL: MEDIA_URL + recordings/<fname>
        url = os.path.join(settings.MEDIA_URL, prefix, fname)
        recordings.append({"name": fname, "url": url})
    return JsonResponse({"recordings": recordings})


@login_required
def upload_recorded(request):
    """
    Called by the client after stopRecording() to POST the .webm blob.
    Saves under MEDIA_ROOT/recordings/<timestamp>_<orig>.webm
    """
    if request.method != "POST":
        return HttpResponseBadRequest("Only POST allowed")

    video = request.FILES.get("video_file")
    if not video:
        return HttpResponseBadRequest("Missing 'video_file' upload")

    timestamp = int(timezone.now().timestamp())
    filename = f"recordings/{timestamp}_{video.name}"
    file_path = default_storage.save(filename, ContentFile(video.read()))
    url = default_storage.url(file_path)

    return JsonResponse({
        "status": "success",
        "file_path": file_path,
        "url": url,
    })
