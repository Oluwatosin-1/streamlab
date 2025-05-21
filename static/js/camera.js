// static/js/camera.js

// ——— Exports for recording.js to hook into ———————————————————————
export let currentLiveStream    = null;
export let currentPreviewStream = null;

// ——— Internal vars for captions & overlay ———————————————————————
let recognizer        = null;
let captionsOn        = false;
let overlayContainer  = null;
let isDragging        = false;
let dragOffset        = { x: 0, y: 0 };
let isResizing        = false;
let resizeStart       = { x: 0, y: 0, w: 0, h: 0 };

/**
 * List all available video input devices.
 */
export async function getVideoDevices() {
  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices.filter(d => d.kind === 'videoinput');
}

/**
 * Fill a <select> with camera options.
 * callback(device, index) lets you pick default device IDs.
 */
export function populateCameraSelect(selectEl, devices, callback) {
  selectEl.innerHTML = '';
  devices.forEach((device, idx) => {
    const opt = document.createElement('option');
    opt.value = device.deviceId;
    opt.text  = device.label || `Camera ${idx+1}`;
    selectEl.append(opt);
    callback(device, idx);
  });
}

/**
 * Start a camera stream (live or preview) into the given video element.
 * withAudio=true for live cameras (so captions can hear the mic).
 */
export async function startCamera(videoEl, deviceId, withAudio=false) {
  // stop any existing tracks
  if (videoEl.srcObject) {
    videoEl.srcObject.getTracks().forEach(t => t.stop());
  }
  const stream = await navigator.mediaDevices.getUserMedia({
    video: deviceId ? { deviceId: { exact: deviceId } } : true,
    audio: withAudio
  });
  videoEl.srcObject = stream;
  if (withAudio) currentLiveStream = stream;
  else          currentPreviewStream = stream;
  return stream;
}

/**
 * Stop a camera stream on the given video element.
 */
export function stopCamera(videoEl) {
  if (videoEl.srcObject) {
    videoEl.srcObject.getTracks().forEach(t => t.stop());
    videoEl.srcObject = null;
  }
}

/**
 * Switch the live stream to a displayMedia (screen share).
 * recording.js should call switchLiveStream() after to keep recording.
 */
export async function switchScreenLive(videoEl) {
  const old = currentLiveStream;
  const displayStream = await navigator.mediaDevices.getDisplayMedia({
    video: { frameRate: 30 }, audio: true
  });
  // replace tracks & update element
  if (videoEl.srcObject) videoEl.srcObject.getTracks().forEach(t => t.stop());
  videoEl.srcObject = displayStream;
  currentLiveStream = displayStream;
  return displayStream;
}

/**
 * Switch the preview stream to a displayMedia (screen share preview).
 */
export async function switchScreenPreview(videoEl) {
  const old = currentPreviewStream;
  const displayStream = await navigator.mediaDevices.getDisplayMedia({
    video: { frameRate: 30 }
  });
  if (videoEl.srcObject) videoEl.srcObject.getTracks().forEach(t => t.stop());
  videoEl.srcObject = displayStream;
  currentPreviewStream = displayStream;
  return displayStream;
}

/**
 * Notify recording.js that the live stream has changed.
 */
export function switchLiveStream(newStream) {
  currentLiveStream = newStream;
}

/**
 * Notify recording.js that the preview stream has changed.
 */
export function switchPreviewStream(newStream) {
  currentPreviewStream = newStream;
}

// ——— Overlay (camera‑in‑corner) support ———————————————————————————

/**
 * Attach a draggable, resizable overlay to containerEl.
 * videoEl is your <video> element (e.g. liveVideo).
 */
export function enableCameraOverlay(containerEl, videoEl) {
  overlayContainer = containerEl;
  containerEl.style.position = 'absolute';
  containerEl.style.top      = '10px';
  containerEl.style.left     = '10px';
  containerEl.style.width    = '200px';
  containerEl.style.height   = '150px';
  containerEl.style.zIndex   = '1000';
  containerEl.style.cursor   = 'move';

  // video inside
  videoEl.style.width  = '100%';
  videoEl.style.height = '100%';
  videoEl.style.objectFit = 'cover';
  containerEl.appendChild(videoEl);

  // resizer handle
  const resizer = document.createElement('div');
  resizer.style.width    = '12px';
  resizer.style.height   = '12px';
  resizer.style.background = '#fff';
  resizer.style.border   = '1px solid #000';
  resizer.style.position = 'absolute';
  resizer.style.right    = '0';
  resizer.style.bottom   = '0';
  resizer.style.cursor   = 'nwse-resize';
  containerEl.appendChild(resizer);

  // Dragging
  containerEl.addEventListener('mousedown', e => {
    if (e.target === resizer) return;
    isDragging = true;
    dragOffset.x = e.clientX - containerEl.offsetLeft;
    dragOffset.y = e.clientY - containerEl.offsetTop;
    e.preventDefault();
  });
  document.addEventListener('mousemove', e => {
    if (!isDragging) return;
    containerEl.style.left = (e.clientX - dragOffset.x) + 'px';
    containerEl.style.top  = (e.clientY - dragOffset.y) + 'px';
  });
  document.addEventListener('mouseup', () => isDragging = false);

  // Resizing
  resizer.addEventListener('mousedown', e => {
    isResizing = true;
    resizeStart.x = e.clientX;
    resizeStart.y = e.clientY;
    resizeStart.w = containerEl.offsetWidth;
    resizeStart.h = containerEl.offsetHeight;
    e.stopPropagation();
  });
  document.addEventListener('mousemove', e => {
    if (!isResizing) return;
    const dx = e.clientX - resizeStart.x;
    const dy = e.clientY - resizeStart.y;
    containerEl.style.width  = Math.max(100, resizeStart.w + dx) + 'px';
    containerEl.style.height = Math.max(75, resizeStart.h + dy) + 'px';
  });
  document.addEventListener('mouseup', () => isResizing = false);
}

/**
 * Remove the overlay entirely.
 */
export function disableCameraOverlay(containerEl, videoEl) {
  if (!containerEl.contains(videoEl)) return;
  containerEl.innerHTML = '';
}

// ——— Live captions via Web Speech API ——————————————————————————

/**
 * Start live speech recognition on the currentLiveStream’s audio
 * and render captions inside captionEl (a <div> overlay).
 */
export function startCaptions(captionEl, lang = 'en-US') {
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRec || !currentLiveStream) return;
  recognizer = new SpeechRec();
  recognizer.continuous   = true;
  recognizer.interimResults= true;
  recognizer.lang         = lang;

  recognizer.onresult = e => {
    let transcript = '';
    for (let i = e.resultIndex; i < e.results.length; ++i) {
      transcript += e.results[i][0].transcript;
    }
    captionEl.innerText = transcript;
  };
  recognizer.onerror = console.error;
  recognizer.onend   = () => {
    if (captionsOn) recognizer.start();
  };

  // Pipe audio tracks into a MediaStreamAudioSourceNode if needed
  // (Some browsers require feed from mic, but SpeechRecognition picks up default mic)
  captionsOn = true;
  recognizer.start();
}

/**
 * Stop live captions.
 */
export function stopCaptions() {
  captionsOn = false;
  if (recognizer) recognizer.stop();
}
