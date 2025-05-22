// static/js/recording.js

let mediaRecorder    = null;
let recordedChunks   = [];
let isRecording      = false;
let currentStream    = null;

/**
 * Internal helper: spins up a MediaRecorder on currentStream
 * and begins capturing. When it fires "stop" (e.g. on a stream swap),
 * we automatically restart a new segment if isRecording is still true.
 */
function _startSegment() {
  if (!currentStream) {
    console.error('Recording: no stream available');
    return;
  }

  // Preferred options; fallback if the browser doesn't support them
  const options = { mimeType: 'video/webm;codecs=vp9', bitsPerSecond: 2_500_000 };
  try {
    mediaRecorder = new MediaRecorder(currentStream, options);
  } catch (err) {
    console.warn('Recording: preferred options failed, trying default', err);
    try {
      mediaRecorder = new MediaRecorder(currentStream);
    } catch (err2) {
      console.error('Recording not supported by this browser', err2);
      return;
    }
  }

  mediaRecorder.ondataavailable = e => {
    if (e.data && e.data.size) {
      recordedChunks.push(e.data);
    }
  };

  mediaRecorder.onstop = () => {
    // If the user hasn't clicked Stop, this was triggered by a stream swap—
    // so we immediately start a new segment on the updated currentStream.
    if (isRecording) {
      _startSegment();
    }
  };

  // Start collecting data segments every 1 second
  mediaRecorder.start(1000);
}

/**
 * Begin recording the given MediaStream.
 * Disables the "Start" button and enables the "Stop" button.
 *
 * @param {MediaStream} stream   – the source to record
 * @param {HTMLButtonElement} startBtn
 * @param {HTMLButtonElement} stopBtn
 */
export function startRecording(stream, startBtn, stopBtn) {
  if (isRecording) return;
  if (!stream) {
    alert('No video source available to record.');
    return;
  }
  if (typeof MediaRecorder === 'undefined') {
    alert('Recording not supported in this browser.');
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
 * (e.g. on camera switch or screen‑share). This stops the
 * current segment, which triggers onstop → _startSegment()
 * on the new currentStream.
 *
 * @param {MediaStream} newStream
 */
export function switchStream(newStream) {
  if (!newStream) {
    console.warn('Recording.switchStream: no newStream provided');
    return;
  }

  currentStream = newStream;

  if (isRecording && mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
  }
}

/**
 * Stop the recording entirely and download a .webm file.
 * Re‑enables the "Start" button and disables the "Stop" button.
 *
 * @param {string} sessionUuid – used to name the downloaded file
 * @param {HTMLButtonElement} startBtn
 * @param {HTMLButtonElement} stopBtn
 */
export function stopRecording(sessionUuid, startBtn, stopBtn) {
  if (!isRecording) return;
  isRecording = false;

  startBtn.disabled = false;
  stopBtn.disabled  = true;

  if (!mediaRecorder || mediaRecorder.state !== 'recording') {
    console.warn('Recording.stopRecording: no active segment to stop');
    return;
  }

  // Once this final segment stops, download the result exactly once
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
