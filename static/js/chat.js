// static/js/chat.js

// ——— In‑memory state ——————————————————————————————————————
let _chatInterval = null;
const _chatHistory = [];    // [{ timestamp: ISOString, messages: [...] }, …]
const _subscribers = [];    // functions to call on each update

// ——— Public API ——————————————————————————————————————————

/**
 * Subscribe a callback to run after each chat fetch.
 * Callback receives ({ timestamp, messages }).
 */
export function onChatUpdate(callback) {
  if (typeof callback === 'function') _subscribers.push(callback);
}

/**
 * Unsubscribe a previously registered callback.
 */
export function offChatUpdate(callback) {
  const idx = _subscribers.indexOf(callback);
  if (idx !== -1) _subscribers.splice(idx, 1);
}

/**
 * Get a copy of the full chat history.
 */
export function getChatHistory() {
  return _chatHistory.map(entry => ({
    timestamp: entry.timestamp,
    messages: entry.messages.map(m => ({ ...m }))
  }));
}

/**
 * Clear the stored chat history.
 */
export function clearChatHistory() {
  _chatHistory.length = 0;
}

/**
 * Start polling chat at the given interval (ms).
 *
 * @param {string} fetchUrl       Django endpoint, e.g. "/streaming/fetch_chat_messages/"
 * @param {string} sessionUuid    Session UUID to pass as ?session_uuid=
 * @param {HTMLElement} containerEl  Where to render messages
 * @param {number} [intervalMs=3000] Poll interval
 */
export function startChatPolling(fetchUrl, sessionUuid, containerEl, intervalMs = 3000) {
  stopChatPolling();
  _fetchAndRender(fetchUrl, sessionUuid, containerEl);
  _chatInterval = setInterval(
    () => _fetchAndRender(fetchUrl, sessionUuid, containerEl),
    intervalMs
  );
}

/**
 * Stop polling chat.
 */
export function stopChatPolling() {
  if (_chatInterval) {
    clearInterval(_chatInterval);
    _chatInterval = null;
  }
}

/**
 * Send a single chat message.
 *
 * @param {string} sendUrl        Django endpoint, e.g. "/streaming/send_chat_message/<uuid>/"
 * @param {string} sessionUuid    Session UUID in URL or body
 * @param {string} text           Message text
 * @param {HTMLElement} containerEl  Chat area to re-render
 * @param {HTMLInputElement} inputEl Input box to clear/focus
 * @param {string} csrfToken      CSRF token for header
 */
export async function sendChat(sendUrl, sessionUuid, text, containerEl, inputEl, csrfToken) {
  if (!text.trim()) return;
  const sendBtn = inputEl.nextElementSibling;
  sendBtn.disabled = true;
  inputEl.disabled = true;

  try {
    const resp = await fetch(sendUrl, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({ session_uuid: sessionUuid, text: text.trim() })
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    // Clear input & re-fetch immediately
    inputEl.value = '';
    inputEl.focus();
    await _fetchAndRender(sendUrl.replace(/send\/?$/, 'fetch/'), sessionUuid, containerEl);
  } catch (err) {
    console.error('Error sending chat message:', err);
    alert(`Failed to send message: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
    inputEl.disabled = false;
  }
}

// ——— Private helper ——————————————————————————————————————————

/**
 * Internal: fetch & render into containerEl.
 */
async function _fetchAndRender(fetchUrl, sessionUuid, containerEl) {
  try {
    // Build URL with query param
    const url = new URL(fetchUrl, window.location.origin);
    url.searchParams.set('session_uuid', sessionUuid);

    const resp = await fetch(url.toString(), { credentials: 'same-origin' });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    if (!Array.isArray(data.messages)) throw new Error('Malformed response');

    // Record history
    const timestamp = new Date().toISOString();
    _chatHistory.push({ timestamp, messages: data.messages });

    // Notify subscribers
    for (const fn of _subscribers) {
      try { fn({ timestamp, messages: data.messages }); }
      catch (e) { console.error('Chat subscriber error:', e); }
    }

    // Render messages
    containerEl.innerHTML = '';
    if (data.messages.length === 0) {
      const p = document.createElement('p');
      p.className = 'text-muted';
      p.textContent = 'No messages yet.';
      containerEl.appendChild(p);
    } else {
      for (const msg of data.messages) {
        const div = document.createElement('div');
        div.className = 'chat-message mb-2';
        
        const strong = document.createElement('strong');
        strong.textContent = msg.user + ':';
        div.appendChild(strong);

        div.appendChild(document.createTextNode(' ' + msg.text));

        const small = document.createElement('small');
        small.className = 'text-muted d-block';
        small.textContent = new Date(msg.created_at).toLocaleTimeString();
        div.appendChild(small);

        containerEl.appendChild(div);
      }
    }
    containerEl.scrollTop = containerEl.scrollHeight;

  } catch (err) {
    console.error('Error fetching chat messages:', err);
    // Replace content with an error banner
    containerEl.innerHTML = '';
    const errDiv = document.createElement('div');
    errDiv.className = 'alert alert-danger';
    errDiv.textContent = `Failed to load chat: ${err.message}`;
    containerEl.appendChild(errDiv);
  }
}
