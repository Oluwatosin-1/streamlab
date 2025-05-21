// static/js/recording.js

let mediaRecorder    = null;
let recordedChunks   = [];
let isRecording      = false;
let currentStream    = null;

/**
 * Internal: create a MediaRecorder on `currentStream` and begin capturing.
 * If it later stops due to a stream switch, we auto‑restart as long as isRecording==true.
 */
function _startSegment() {
  if (!currentStream) {
    console.error('No stream available for recording');
    return;
  }

  let options = { mimeType: 'video/webm;codecs=vp9', bitsPerSecond: 2_500_000 };
  try {
    mediaRecorder = new MediaRecorder(currentStream, options);
  } catch (err) {
    console.error('Failed to create MediaRecorder:', err);
    try {
      // Fallback without explicit options
      mediaRecorder = new MediaRecorder(currentStream);
    } catch (err2) {
      console.error('MediaRecorder not supported:', err2);
      return;
    }
  }

  mediaRecorder.ondataavailable = e => {
    if (e.data && e.data.size) {
      recordedChunks.push(e.data);
    }
  };

  mediaRecorder.onstop = () => {
    // If we're still in “recording” mode, that means we triggered this stop
    // to swap streams → start a new segment automatically.
    if (isRecording) {
      _startSegment();
    }
  };

  // Begin segment; collects data every 1 second
  mediaRecorder.start(1000);
}

/**
 * Begin recording the provided MediaStream.
 * Disables the “Start” button and enables the “Stop” button.
 *
 * @param {MediaStream} stream   – the video/audio source to record
 * @param {HTMLButtonElement} startBtn
 * @param {HTMLButtonElement} stopBtn
 */
export function startRecording(stream, startBtn, stopBtn) {
  if (isRecording) return;
  if (!stream) {
    console.warn('startRecording: no stream provided');
    alert('No video source available to record.');
    return;
  }
  if (typeof MediaRecorder === 'undefined') {
    console.error('MediaRecorder API is not available');
    alert('Your browser does not support recording.');
    return;
  }

  currentStream  = stream;
  recordedChunks = [];
  isRecording    = true;

  startBtn.disabled = true;
  stopBtn.disabled  = false;

  _startSegment();
}

/**
 * Notify the recorder that the underlying stream has changed
 * (e.g. on camera switch or screen‑share).
 * Stops the current segment, which triggers onstop→_startSegment()
 * with the new `currentStream`.
 *
 * @param {MediaStream} newStream
 */
export function switchStream(newStream) {
  if (!isRecording) {
    currentStream = newStream;
    return;
  }
  if (!newStream) {
    console.warn('switchStream: no newStream provided');
    return;
  }

  currentStream = newStream;
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
  }
}

/**
 * Stop the recording entirely and trigger a download of the .webm file.
 * Re‑enables the “Start” button, disables the “Stop” button.
 *
 * @param {string} sessionUuid  – used to name the downloaded file
 * @param {HTMLButtonElement} startBtn
 * @param {HTMLButtonElement} stopBtn
 */
export function stopRecording(sessionUuid, startBtn, stopBtn) {
  if (!isRecording) return;
  isRecording = false;

  startBtn.disabled = false;
  stopBtn.disabled  = true;

  if (!mediaRecorder || mediaRecorder.state !== 'recording') {
    console.warn('stopRecording: no active MediaRecorder segment');
    return;
  }

  // Once this final segment stops, download exactly once.
  mediaRecorder.addEventListener('stop', () => {
    const blob = new Blob(recordedChunks, { type: 'video/webm' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.style.display = 'none';
    a.href        = url;
    a.download    = `recording_${sessionUuid}.webm`;

    document.body.appendChild(a);
    a.click();

    setTimeout(() => {
      URL.revokeObjectURL(url);
      document.body.removeChild(a);
    }, 100);
  }, { once: true });

  mediaRecorder.stop();
}
