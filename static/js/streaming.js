// static/js/streaming.js

import * as camera from './camera.js';

export let peerConnection = null;
export let isStreaming = false;

/** Show a Bootstrap‑style alert at the top of the page */
function showAlert(message, type) {
  const alertDiv = document.createElement('div');
  alertDiv.className = `alert alert-${type} alert-dismissible fade show mt-3`;
  alertDiv.role = 'alert';
  alertDiv.innerHTML = `
    ${message}
    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
  `;
  document.querySelector('.container-fluid').prepend(alertDiv);
  setTimeout(() => new bootstrap.Alert(alertDiv).close(), 5000);
}

/**
 * Start live streaming via WebRTC → your Django offer endpoint.
 * Applies camera.currentLiveStream’s tracks, then notifies your backend to “go live”.
 */
export async function startStreaming(sessionUuid, streamKey, configId) {
  const stream = camera.currentLiveStream;
  if (!stream) {
    showAlert('Please start your camera or screen share first', 'warning');
    return;
  }

  const goLiveBtn     = document.getElementById('goLiveBtn');
  const goLiveSpinner = document.getElementById('goLiveSpinner');
  goLiveBtn.disabled = true;
  goLiveSpinner.classList.remove('d-none');

  try {
    // 1️⃣ Create PC
    peerConnection = new RTCPeerConnection({
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' }
      ]
    });

    // Track connection state
    peerConnection.onconnectionstatechange = () => {
      const statusEl = document.getElementById('connection-status');
      if (!statusEl) return;
      const state = peerConnection.connectionState;
      statusEl.textContent = state === 'connected' ? 'Connected' : 'Disconnected';
      statusEl.className = `badge ${state==='connected'?'bg-success':'bg-danger'}`;
      statusEl.style.display = (state==='closed'? 'none':'inline-block');
    };

    // 2️⃣ Add tracks
    stream.getTracks().forEach(track => {
      peerConnection.addTrack(track, stream);
    });

    // 3️⃣ Exchange offer/answer
    await peerConnection.setLocalDescription(await peerConnection.createOffer({
      offerToReceiveAudio: true,
      offerToReceiveVideo: true
    }));

    // POST to Django /offer/?stream_key=…
    let answer;
    for (let i=0; i<3; i++) {
      const resp = await fetch(
        `/streaming/offer/?stream_key=${encodeURIComponent(streamKey)}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': cfg.dataset.csrfToken
          },
          body: JSON.stringify({
            sdp: peerConnection.localDescription.sdp,
            type: peerConnection.localDescription.type,
            session_uuid: sessionUuid
          })
        }
      );
      if (resp.ok) {
        answer = await resp.json();
        break;
      }
      if (i===2) throw new Error('Failed to negotiate WebRTC offer');
      await new Promise(r => setTimeout(r, 1000 * (i+1)));
    }

    await peerConnection.setRemoteDescription(
      new RTCSessionDescription(answer)
    );

    // 4️⃣ Tell Django to go_live
    const liveResp = await fetch(`/streaming/go_live/${configId}/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': cfg.dataset.csrfToken
      },
      body: JSON.stringify({
        session_uuid: sessionUuid,
        title: document.getElementById('streamTitleInput').value,
        description: document.getElementById('streamDescriptionInput').value
      })
    });
    if (!liveResp.ok) {
      const err = await liveResp.json();
      throw new Error(err.message || 'Failed to start live session');
    }

    // Update UI
    isStreaming = true;
    document.getElementById('live-status').textContent = 'Live Streaming';
    showAlert('Live stream started successfully!', 'success');

  } catch (err) {
    console.error('startStreaming error:', err);
    showAlert(`Failed to start stream: ${err.message}`, 'danger');
  } finally {
    goLiveBtn.disabled = false;
    goLiveSpinner.classList.add('d-none');
  }
}

/**
 * Stop the live stream session on the server and close the PeerConnection.
 */
export async function stopStreaming(sessionId) {
  if (peerConnection) {
    peerConnection.close();
    peerConnection = null;
  }

  try {
    const resp = await fetch(`/streaming/stop_live/${sessionId}/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': cfg.dataset.csrfToken }
    });
    const data = await resp.json();
    if (data.status !== 'ok') throw new Error(data.error || 'Stop failed');

    isStreaming = false;
    document.getElementById('live-status').textContent = 'Stream Ended';
    document.getElementById('connection-status').style.display = 'none';
    showAlert('Live stream stopped successfully', 'success');

  } catch (err) {
    console.error('stopStreaming error:', err);
    showAlert(`Failed to stop stream: ${err.message}`, 'danger');
  }
}

/**
 * Replace the outgoing video/audio tracks on an existing RTCPeerConnection.
 * Used when the user switches to screen‑share.
 */
export function replaceTracks(newStream) {
  if (!peerConnection) return;
  const senders = peerConnection.getSenders();
  const videoSender = senders.find(s => s.track.kind === 'video');
  const audioSender = senders.find(s => s.track.kind === 'audio');

  if (videoSender && newStream.getVideoTracks().length) {
    videoSender.replaceTrack(newStream.getVideoTracks()[0]);
  }
  if (audioSender && newStream.getAudioTracks().length) {
    audioSender.replaceTrack(newStream.getAudioTracks()[0]);
  }
}

/**
 * Poll the SRS /check_stream_status endpoint and update the status badge.
 */
export function pollStreamStatus(streamKey) {
  if (!isStreaming) return;
  fetch(`/check_stream_status/${encodeURIComponent(streamKey)}`)
    .then(r => r.json())
    .then(data => {
      if (data.srs_stats) {
        let text = 'Live Streaming';
        const { clients, video, audio } = data.srs_stats;
        if (clients) text += ` (${clients} viewer${clients!==1?'s':''})`;
        if (video && audio) text += ' - Video & Audio OK';
        else if (video) text += ' - Video Only';
        else if (audio) text += ' - Audio Only';
        document.getElementById('live-status').textContent = text;
      }
    })
    .catch(err => console.error('pollStreamStatus error:', err));
}
