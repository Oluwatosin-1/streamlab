// static/js/studio.js

import * as camera    from './camera.js';
import * as recording from './recording.js';
import * as relay     from './relay.js';
import * as chat      from './chat.js';
import * as streaming from './streaming.js';

// Read runtime config
const cfg = document.getElementById('studio-config');
if (!cfg) throw new Error('Missing #studio-config element');
const sessionUuid       = cfg.dataset.sessionUuid;
const sessionId         = cfg.dataset.sessionId;
const fetchChatUrl      = cfg.dataset.fetchChatUrl;      // e.g. "/streaming/fetch_chat_messages/"
const sendChatUrl       = cfg.dataset.sendChatUrl;       // "/streaming/send_chat_message/<uuid>/"
const relayStatusUrl    = cfg.dataset.relayStatusUrl;    // "/streaming/relay_status/<id>/"
const goLiveUrl         = cfg.dataset.goLiveUrl;
const stopLiveUrl       = cfg.dataset.stopLiveUrl;
const csrfToken         = cfg.dataset.csrfToken; 
const streamKey   = cfg.dataset.streamKey;
const configId    = cfg.dataset.configId; 
const recordMode  = cfg.dataset.recordMode === 'true';  
const fetchBase  = cfg.dataset.relayFetchUrlBase;    // ends with "/"
const restartBase= cfg.dataset.relayRestartUrlBase;  // ends with "/0/"  
const relayBody  = document.getElementById('relay-monitor-body');


document.addEventListener('DOMContentLoaded', async () => {
  // Local state
  let liveStream     = null;
  let previewStream  = null;
  let liveDeviceId   = null;
  let previewDeviceId= null;

  // Cache DOM elements
  const liveVideo        = document.getElementById('liveVideo');
  const previewVideo     = document.getElementById('previewVideo');
  const noLiveText       = document.getElementById('noLiveText');
  const noPreviewText    = document.getElementById('noPreviewText');
  const streamStatus     = document.getElementById('live-status');

  const startLiveBtn     = document.getElementById('startLiveBtn');
  const stopLiveBtn      = document.getElementById('stopLiveBtn');
  const switchPreviewBtn = document.getElementById('switchScreenBtn');
  const switchLiveBtn    = document.getElementById('switchScreenLiveBtn');
  const pushToLiveBtn    = document.getElementById('pushToLiveBtn');
  const goLiveBtn        = document.getElementById('goLiveBtn');
  const stopLiveFeedBtn  = document.getElementById('stopLiveFeedBtn');

  const startPreviewBtn  = document.getElementById('startPreviewBtn');
  const stopPreviewBtn   = document.getElementById('stopPreviewBtn');

  const startRecordBtn   = document.getElementById('startRecordBtn');
  const stopRecordBtn    = document.getElementById('stopRecordBtn');

  const liveSelect       = document.getElementById('liveCameraSelect');
  const previewSelect    = document.getElementById('previewCameraSelect');

  const chatContainer    = document.getElementById('chatContainer');
  const refreshChatBtn   = document.getElementById('refreshChatBtn');
  const sendChatBtn      = document.getElementById('sendChatBtn');
  const chatInput        = document.getElementById('chatMessage');
  const enableChatSwitch = document.getElementById('enableChatSwitch');

  const relayBody        = document.getElementById('relay-monitor-body');
  const refreshRelaysBtn = document.getElementById('refreshRelaysBtn');

  // 1️⃣ Enumerate cameras & populate selects
  const devices = await camera.getVideoDevices();
  camera.populateCameraSelect(liveSelect, devices, (dev, i) => {
    if (i === 0) liveDeviceId = dev.deviceId;
  });
  camera.populateCameraSelect(previewSelect, devices, (dev, i) => {
    if (devices.length > 1 && i === 1) previewDeviceId = dev.deviceId;
    else if (devices.length === 1 && i === 0) previewDeviceId = dev.deviceId;
  });

  // 2️⃣ Start initial preview
  try {
    previewStream = await camera.startCamera(previewVideo, previewDeviceId, false);
    noPreviewText.style.display = 'none';
  } catch {
    previewVideo.style.display = 'none';
    noPreviewText.style.display = 'block';
  }

  // 3️⃣ Start chat & relay polling
  if (!recordMode && enableChatSwitch.checked) {
    chat.startChatPolling(
      cfg.dataset.chatFetchUrl,
      chatContainer,
      3000
    );
  }
  relay.startRelayMonitoring(
   relayStatusUrl,            // url base, e.g. "/streaming/relay_status/"
   sessionId,                 // numeric/session UUID part
   relayBody,                 // <tbody> you’re filling
   path => `/static/${path}`, // maps "img/platforms/*.png" -> "/static/…"
   5000                       // poll interval (ms)
 );

  // 4️⃣ Warn on unload if still streaming
  window.addEventListener('beforeunload', e => {
    if (streaming.isStreaming) {
      e.returnValue = "You're live streaming—are you sure?";
      return e.returnValue;
    }
  });

  // 5️⃣ Event listeners

  // Camera selection changes
  liveSelect.addEventListener('change', async e => {
    liveDeviceId = e.target.value;
    try {
      liveStream = await camera.startCamera(liveVideo, liveDeviceId, true);
      streamStatus.textContent = 'Live Camera On';
      noLiveText.style.display = 'none';
    } catch {
      streamStatus.textContent = 'Live Camera Off';
      noLiveText.style.display = 'block';
    }
  });
  previewSelect.addEventListener('change', async e => {
    previewDeviceId = e.target.value;
    try {
      previewStream = await camera.startCamera(previewVideo, previewDeviceId, false);
      noPreviewText.style.display = 'none';
    } catch {
      previewVideo.style.display = 'none';
      noPreviewText.style.display = 'block';
    }
  });

  // Start/stop live camera
  startLiveBtn.addEventListener('click', async () => {
    try {
      liveStream = await camera.startCamera(liveVideo, liveDeviceId, true);
      streamStatus.textContent = 'Live Camera On';
      noLiveText.style.display = 'none';
    } catch {
      streamStatus.textContent = 'Live Camera Off';
      noLiveText.style.display = 'block';
    }
  });
  stopLiveBtn.addEventListener('click', () => {
    camera.stopCamera(liveVideo);
    streamStatus.textContent = 'Live Camera Off';
    noLiveText.style.display = 'block';
    liveStream = null;
  });

  // Start/stop preview camera
  startPreviewBtn.addEventListener('click', async () => {
    try {
      previewStream = await camera.startCamera(previewVideo, previewDeviceId, false);
      noPreviewText.style.display = 'none';
    } catch {
      previewVideo.style.display = 'none';
      noPreviewText.style.display = 'block';
    }
  });
  stopPreviewBtn.addEventListener('click', () => {
    camera.stopCamera(previewVideo);
    previewVideo.style.display = 'none';
    noPreviewText.style.display = 'block';
    previewStream = null;
  });

  // Switch to screen share (preview)
  switchPreviewBtn.addEventListener('click', async () => {
    try {
      previewStream = await camera.switchScreenPreview(previewVideo);
      noPreviewText.style.display = 'none';
    } catch { /* ignore */ }
  });

  // Switch to screen share (live)
  switchLiveBtn.addEventListener('click', async () => {
    const old = liveStream;
    try {
      liveStream = await camera.switchScreenLive(liveVideo, true);

      // Replace WebRTC senders
      streaming.replaceTracks(liveStream);

      // Keep recording
      recording.switchStream(liveStream);

      streamStatus.textContent = 'Screen Shared (Live)';
      noLiveText.style.display = 'none';
    } catch { /* ignore */ }
    old && old.getTracks().forEach(t => t.stop());
  });

  // Go Live / Push to Live
  pushToLiveBtn.addEventListener('click', () =>
    streaming.startStreaming(sessionUuid, streamKey, configId)
  );
  goLiveBtn.addEventListener('click', () =>
    streaming.startStreaming(sessionUuid, streamKey, configId)
  );
  stopLiveFeedBtn.addEventListener('click', () =>
    streaming.stopStreaming(sessionId)
  );

  // Relay manual refresh
  refreshRelaysBtn.addEventListener('click', () =>
    relay.updateRelayStatus(relayStatusUrl, sessionId, relayBody, path => `/static/${path}`)
  );

  // --- Recording controls ---------------------------------------------
  startRecordBtn.addEventListener('click', () => {
    // Pick whichever stream is actually available
    const streamToRecord = liveStream || previewStream;
    recording.startRecording(streamToRecord, startRecordBtn, stopRecordBtn);
  });

  stopRecordBtn.addEventListener('click', () =>
    recording.stopRecording(sessionUuid, startRecordBtn, stopRecordBtn)
  );


  // Chat controls
  if (refreshChatBtn) {
    refreshChatBtn.addEventListener('click', () =>
      chat.fetchChat(sessionUuid, chatContainer)
    );
  }
  if (sendChatBtn) {
    // On “Send”
  sendChatBtn.addEventListener('click', () =>
   chat.sendChat(sendChatUrl, sessionUuid, chatInput.value, chatContainer, chatInput, csrfToken)
 );
    chatInput.addEventListener('keypress', e => {
      if (e.key === 'Enter') sendChatBtn.click();
    });
  }

  // Restart relay buttons
  document.body.addEventListener('click', async e => {
  const btn = e.target.closest('.restart-relay-btn');
  if (!btn) return;
  const accId = btn.dataset.id;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
  try {
    await relay.restartRelay(restartBase, accId, csrfToken);
    await relay.updateRelayStatus(relayStatusUrl, sessionId, relayBody, path => `/static/${path}`);
  } catch (err) {
    console.error(err);
    alert('Failed to restart relay: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-arrow-repeat"></i>';
  }
});
});
