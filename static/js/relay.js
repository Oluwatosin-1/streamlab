// static/js/relay.js

// ——— In‑memory state ——————————————————————————————————————
let _relayInterval = null;
const _relayHistory = [];   // [{ timestamp: ISOString, relays: [...] }, …]
const _subscribers  = [];   // functions to call on each update

// ——— Public API ——————————————————————————————————————————

/**
 * Subscribe a callback to run after each relay status update.
 * Callback receives the new history entry: { timestamp, relays }.
 */
export function onRelayUpdate(callback) {
  if (typeof callback === 'function') _subscribers.push(callback);
}

/**
 * Unsubscribe a previously registered callback.
 */
export function offRelayUpdate(callback) {
  const idx = _subscribers.indexOf(callback);
  if (idx !== -1) _subscribers.splice(idx, 1);
}

/**
 * Get a copy of the full relay history.
 */
export function getRelayHistory() {
  return _relayHistory.map(entry => ({
    timestamp: entry.timestamp,
    relays: entry.relays.map(r => ({ ...r }))
  }));
}

/**
 * Clear the stored relay history.
 */
export function clearRelayHistory() {
  _relayHistory.length = 0;
}

/**
 * Immediately fetch and render relay status.
 *
 * @param {string} fetchUrlBase      e.g. "/streaming/relay_status"
 * @param {string|number} sessionId  Session ID to append
 * @param {HTMLElement} containerEl  <tbody> or similar
 * @param {function(string):string} staticUrlFn builds URLs for static assets
 */
export async function updateRelayStatus(fetchUrlBase, sessionId, containerEl, staticUrlFn) {
  const timestamp = new Date().toISOString();
  let relays;

  // build e.g. "/streaming/relay_status/123/"
  const url = `${fetchUrlBase.replace(/\/+$/, '')}/${encodeURIComponent(sessionId)}/`;

  try {
    const resp = await fetch(url, { credentials: 'same-origin' });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const json = await resp.json();
    if (json.status !== 'success' || !Array.isArray(json.relays)) {
      throw new Error(json.message || 'Invalid response');
    }
    relays = json.relays;
  } catch (err) {
    console.error('Failed to fetch relay status:', err);
    // render single-error row
    containerEl.innerHTML = '';
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 6;
    td.className = 'text-danger text-center';
    td.textContent = `Error loading relay status: ${err.message}`;
    tr.appendChild(td);
    containerEl.appendChild(tr);
    return;
  }

  // record history & notify
  _relayHistory.push({ timestamp, relays: JSON.parse(JSON.stringify(relays)) });
  for (const fn of _subscribers) {
    try { fn(_relayHistory[_relayHistory.length - 1]); }
    catch (e) { console.error('Relay subscriber error:', e); }
  }

  // render table rows
  containerEl.innerHTML = '';
  for (const relay of relays) {
    const tr = document.createElement('tr');

    // Platform
    const tdPlat = document.createElement('td');
    const img    = document.createElement('img');
    img.src      = staticUrlFn(`img/platforms/${relay.platform}.png`);
    img.height   = 20;
    img.alt      = relay.platform;
    img.style.marginRight = '6px';
    tdPlat.appendChild(img);
    tdPlat.append(relay.platform);
    tr.appendChild(tdPlat);

    // RTMP URL
    const tdUrl = document.createElement('td');
    const code  = document.createElement('code');
    code.textContent = `${relay.rtmp_url}/${relay.stream_key}`;
    tdUrl.appendChild(code);
    tr.appendChild(tdUrl);

    // Status badge
    const tdStat = document.createElement('td');
    const span   = document.createElement('span');
    span.className = `badge ${
      relay.relay_status === 'active' ? 'bg-success' :
      relay.relay_status === 'failed' ? 'bg-danger'  :
      'bg-warning'
    }`;
    span.textContent = relay.relay_status || 'Pending';
    tdStat.appendChild(span);
    tr.appendChild(tdStat);

    // Last updated
    const tdUp = document.createElement('td');
    tdUp.textContent = relay.relay_last_updated || 'N/A';
    tr.appendChild(tdUp);

    // Log
    const tdLog = document.createElement('td');
    const pre   = document.createElement('pre');
    pre.style.maxHeight = '100px';
    pre.style.overflow  = 'auto';
    pre.style.margin    = '0';
    if (relay.relay_status === 'failed') pre.style.color = '#dc3545';
    pre.textContent = relay.relay_log || 'No logs available';
    tdLog.appendChild(pre);
    tr.appendChild(tdLog);

    // Actions
    const tdAct = document.createElement('td');
    const btn   = document.createElement('button');
    btn.className = 'btn btn-sm btn-outline-primary restart-relay-btn';
    btn.dataset.id = relay.id;
    btn.innerHTML  = '<i class="bi bi-arrow-repeat"></i>';
    tdAct.appendChild(btn);
    tr.appendChild(tdAct);

    containerEl.appendChild(tr);
  }
}

/**
 * Start polling relay status.
 *
 * @param {string} fetchUrlBase
 * @param {string|number} sessionId
 * @param {HTMLElement} containerEl
 * @param {function(string):string} staticUrlFn
 * @param {number} [intervalMs=5000]
 */
export function startRelayMonitoring(fetchUrlBase, sessionId, containerEl, staticUrlFn, intervalMs = 5000) {
  stopRelayMonitoring();
  // initial load
  updateRelayStatus(fetchUrlBase, sessionId, containerEl, staticUrlFn);
  _relayInterval = setInterval(
    () => updateRelayStatus(fetchUrlBase, sessionId, containerEl, staticUrlFn),
    intervalMs
  );
}

/**
 * Stop polling relay status.
 */
export function stopRelayMonitoring() {
  if (_relayInterval) {
    clearInterval(_relayInterval);
    _relayInterval = null;
  }
}

/**
 * Restart a single relay for a given account.
 *
 * @param {string} restartUrlBase e.g. "/streaming/restart_relay"
 * @param {string|number} accountId
 * @param {string} csrfToken
 * @returns {Promise<void>}
 */
export async function restartRelay(restartUrlBase, accountId, csrfToken) {
  const url = `${restartUrlBase.replace(/\/+$/, '')}/${encodeURIComponent(accountId)}/`;
  const resp = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'X-CSRFToken': csrfToken }
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const json = await resp.json();
  if (json.status !== 'success') throw new Error(json.message || 'Restart failed');
}
