const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const pad = number => String(number).padStart(2, '0');
const localDay = value => `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
const db = value => value == null ? '–' : `${Number(value).toFixed(1).replace('.', ',')} dB`;
let kind = 'day';
let selected = new Date();
let refreshSeconds = 5;
const LIVE_STATUS_INTERVAL_MS = 100;

function toast(message, error = false) {
  const box = $('#toast'); box.textContent = message; box.className = error ? 'show error' : 'show';
  clearTimeout(box.timer); box.timer = setTimeout(() => box.className = '', 4000);
}
async function api(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error((await response.text()) || 'Anfrage fehlgeschlagen');
  return response.headers.get('content-type')?.includes('json') ? response.json() : response;
}
function periodValue() {
  if (kind === 'day') return localDay(selected);
  if (kind === 'month') return `${selected.getFullYear()}-${pad(selected.getMonth() + 1)}`;
  if (kind === 'year') return String(selected.getFullYear());
  const current = new Date(selected); current.setDate(current.getDate() + 4 - (current.getDay() || 7));
  const first = new Date(current.getFullYear(), 0, 1);
  return `${current.getFullYear()}-W${pad(Math.ceil((((current - first) / 86400000) + 1) / 7))}`;
}
function setTitle() {
  $('#title').textContent = ({day:'Tagesübersicht', week:'Wochenübersicht', month:'Monatsübersicht', year:'Jahresübersicht'})[kind];
  $('#count-label').textContent = ({day:'Ereignisse am Tag', week:'Ereignisse der Woche', month:'Ereignisse des Monats', year:'Ereignisse des Jahres'})[kind];
  $('#date').value = localDay(selected); $('#pdf').href = `/report/${kind}/${periodValue()}.pdf`; $('#backup').href = `/backup/${kind}/${periodValue()}.zip`;
  $('#period-section').hidden = kind !== 'day';
  $$('[data-kind]').forEach(button => button.classList.toggle('active', button.dataset.kind === kind));
}
async function loadStatus() {
  try {
    const value = await api('/api/status');
    if (value.available && value.db != null) {
      $('#level').innerHTML = `${value.db.toFixed(1).replace('.', ',')} <small>dB</small>`;
      $('#uncalibrated-level').textContent = db(value.uncalibrated_db);
      $('#live-leq').textContent = db(value.leq_db);
      const mixer = value.input_gain?.channels?.length ? value.input_gain.channels.map(level => `${level} %`).join(' - ') : value.input_gain?.percent != null ? `${value.input_gain.percent} %` : 'nicht regelbar';
      $('#mixer-level').textContent = mixer;
      $('#level').hidden = false; $('#microphone-warning').hidden = true;
      $('#connection').textContent = '● Messung aktiv'; $('#connection').className = 'online';
    } else {
      $('#level').innerHTML = '0,0 <small>dB</small>'; $('#level').hidden = true;
      $('#uncalibrated-level').textContent = '–'; $('#live-leq').textContent = '–';
      $('#mixer-level').textContent = '–';
      $('#microphone-warning').hidden = false; $('#connection').textContent = '● Kein Messmikrofon'; $('#connection').className = 'offline';
    }
    $('#recording').hidden = !value.recording;
  } catch (_) { $('#connection').textContent = '● Keine Verbindung'; $('#connection').className = 'offline'; }
}
async function pollStatus() {
  await loadStatus();
  setTimeout(pollStatus, LIVE_STATUS_INTERVAL_MS);
}
function drawHistory(points) {
  const canvas = $('#history-chart'), width = canvas.clientWidth || 600, height = canvas.clientHeight || 150, ratio = devicePixelRatio || 1;
  canvas.width = width * ratio; canvas.height = height * ratio; const context = canvas.getContext('2d'); context.scale(ratio, ratio); context.clearRect(0, 0, width, height);
  if (!points.length) { context.fillStyle = '#9fc5d8'; context.font = '13px system-ui'; context.fillText('Noch keine gültigen Messwerte für diesen Tag', 12, height / 2); $('#chart-range').textContent = ''; return; }
  const values = points.flatMap(point => [point.db, point.leq_db]).filter(value => value != null), minimum = Math.floor(Math.min(...values) / 5) * 5 - 5, maximum = Math.ceil(Math.max(...values) / 5) * 5 + 5;
  const left = 42, right = 8, top = 8, bottom = 22, chartWidth = width - left - right, chartHeight = height - top - bottom, y = number => top + (maximum - number) / (maximum - minimum || 1) * chartHeight;
  context.strokeStyle = 'rgba(255,255,255,.22)'; context.fillStyle = '#d7e8f0'; context.font = '11px system-ui';
  [minimum, (minimum + maximum) / 2, maximum].forEach(number => { const yy = y(number); context.beginPath(); context.moveTo(left, yy); context.lineTo(width - right, yy); context.stroke(); context.fillText(`${Math.round(number)} dB`, 1, yy + 4); });
  const line = (field, color) => { context.strokeStyle = color; context.lineWidth = 2; context.beginPath(); let started = false; points.forEach((point, index) => { if (point[field] == null) return; const xx = left + index / Math.max(points.length - 1, 1) * chartWidth, yy = y(point[field]); started ? context.lineTo(xx, yy) : context.moveTo(xx, yy); started = true; }); context.stroke(); };
  line('db', '#fff'); line('leq_db', '#32e1f2');
  context.fillText(points[0].minute.slice(11, 16), left, height - 5); context.fillText(points.at(-1).minute.slice(11, 16), width - right - 30, height - 5); $('#chart-range').textContent = `${db(Math.min(...values))} – ${db(Math.max(...values))}`;
}
const dateFormat = value => new Intl.DateTimeFormat('de-DE', {weekday:'long', day:'numeric', month:'long', year:'numeric', hour:'2-digit', minute:'2-digit'}).format(new Date(value));
function eventRows(events) {
  $('#events').innerHTML = events.length ? events.map(event => {
    const severity = event.peak_db >= event.severe_db ? 'violet' : event.peak_db >= event.warning_db ? 'red' : 'orange';
    return `<tr class="event-${severity}"><td>${dateFormat(event.occurred_at)}</td><td>${db(event.peak_db)}</td><td>${db(event.leq_db)}</td><td>${db(event.threshold_db)}</td><td>${event.period_name}</td><td><audio controls preload="none" src="/audio/${encodeURI(event.filename)}"></audio></td></tr>`;
  }).join('') : '<tr><td colspan="6">Keine Ereignisse in diesem Zeitraum.</td></tr>';
}
async function loadPeriodStats() {
  if (kind !== 'day') return;
  const result = await api(`/api/period-statistics?date=${localDay(selected)}`);
  $('#period-stats').innerHTML = result.items.map(item => `<article><div class="period-title"><strong>${item.name}</strong><small>${item.start}–${item.end} Uhr</small></div><dl><div><dt>Ereignisse</dt><dd>${item.event_count}</dd></div><div><dt>Maximum</dt><dd>${db(item.maximum_db)}</dd></div><div><dt>Durchschnitt</dt><dd>${db(item.average_db)}</dd></div><div><dt>Leq</dt><dd>${db(item.leq_db)}</dd></div><div><dt>Minimum</dt><dd>${db(item.minimum_db)}</dd></div></dl>${item.measurement_count ? '' : '<p class="no-data">Keine gültigen Messwerte</p>'}</article>`).join('');
}
async function loadBreakdown() {
  const result = await api(`/api/breakdown?kind=${kind}&date=${periodValue()}`), names = {day:'Stundenauswertung', week:'Tagesauswertung', month:'Wochenauswertung', year:'Monatsauswertung'};
  $('#breakdown').innerHTML = `<h2>${names[kind]}</h2><div class="table-scroll"><table><thead><tr><th>Zeitraum</th><th>Maximalpegel</th><th>Durchschnittspegel</th><th>Leq</th></tr></thead><tbody>${result.items.map(item => `<tr><td>${item.label}</td><td>${db(item.maximum_db)}</td><td>${db(item.average_db)}</td><td>${db(item.leq_db)}</td></tr>`).join('') || '<tr><td colspan="4">Keine gültigen Messwerte.</td></tr>'}</tbody></table></div>`;
}
async function loadEvents() {
  setTitle();
  try {
    const result = await api(`/api/events?kind=${kind}&date=${periodValue()}`);
    $('#count').textContent = result.summary.event_count; $('#peak').textContent = db(result.summary.peak_db); $('#average').textContent = db(result.summary.average_db); $('#summary-leq').textContent = db(result.summary.leq_db); eventRows(result.events);
    const history = await api(`/api/history?date=${localDay(selected)}`); drawHistory(history.points);
    await Promise.all([loadBreakdown(), loadPeriodStats()]);
  } catch (error) { toast('Übersicht konnte nicht geladen werden.', true); }
}
async function loadCounts() { try { const result = await api('/api/event-counts'); ['day','week','month','year'].forEach(name => $(`#count-${name}`).textContent = result[name]); } catch (_) {} }
const bytes = number => { const units = ['B','KB','MB','GB','TB']; let index = 0; while (number >= 1024 && index < 4) { number /= 1024; index++; } return `${number.toFixed(index ? 1 : 0)} ${units[index]}`; };
async function loadSystem() { try { const value = await api('/api/system'); $('#cpu-temperature').textContent = value.cpu_temperature == null ? 'Nicht verfügbar' : `${value.cpu_temperature.toFixed(1)} °C`; $('#cpu-percent').textContent = value.cpu_percent == null ? 'Nicht verfügbar' : `${value.cpu_percent.toFixed(1)} %`; $('#disk-used').textContent = `${bytes(value.disk_used)} belegt`; $('#disk-free').textContent = `${bytes(value.disk_free)} frei von ${bytes(value.disk_total)}`; } catch (_) {} }
async function loadConfig() {
  const value = await api('/api/config'), site = value.site_data || {};
  refreshSeconds = value.web.refresh_seconds; $('#refresh-seconds').value = refreshSeconds;
  $('#period-form').innerHTML = value.periods.map((period, index) => `<div class="period-row"><input name="name${index}" value="${period.name}"><input name="start${index}" type="time" value="${period.start}"><input name="end${index}" type="time" value="${period.end}"><input name="threshold${index}" type="number" step=".1" value="${period.threshold_db}"><input name="warning${index}" type="number" step=".1" value="${period.warning_db ?? +period.threshold_db + 10}"><input name="severe${index}" type="number" step=".1" value="${period.severe_db ?? +period.threshold_db + 15}"><input name="enabled${index}" type="checkbox" ${period.enabled !== false ? 'checked' : ''}></div>`).join('');
  $('#bitrate').value = value.audio.mp3_bitrate_kbps; $('#retention').value = value.storage.retention_days; $('#pre-roll').value = value.audio.pre_roll_seconds; $('#post-roll').value = value.audio.post_roll_seconds;
  $('#weighting').value = value.audio.weighting; $('#time-weighting').value = value.audio.time_weighting; $('#manual-calibration').value = value.audio.manual_calibration_db; $('#calibration-file').textContent = value.audio.calibration_file ? `Aktiv: ${value.audio.calibration_file} (${value.audio.calibration_angle}°), ${value.calibration.points} Frequenzpunkte` : 'Keine Kalibrierdatei hinterlegt.';
  const gainValues = value.input_gain.channels?.length ? value.input_gain.channels : value.input_gain.percent == null ? [] : [value.input_gain.percent];
  $('#microphone-name').value = value.audio.microphone_name || ''; $('#site-name').value = value.site_name; $('#site-location').value = site.location || ''; $('#site-orientation').value = site.orientation || ''; $('#site-angle').value = value.audio.calibration_angle || '0'; $('#site-target').value = site.target_object || ''; $('#site-ground').value = site.ground_distance || ''; $('#site-wall').value = site.wall_distance || ''; $('#gain-status').textContent = gainValues.length ? `USB-Mixerpegel: ${gainValues.map(level => `${level} %`).join(' - ')}${value.input_gain.enforced ? ' (bei Programmstart automatisch auf Maximum gesetzt)' : ''}` : 'USB-Aufnahmepegel konnte noch nicht ermittelt werden.';
  $('#mqtt-enabled').checked = value.mqtt.enabled; $('#mqtt-host').value = value.mqtt.host; $('#mqtt-port').value = value.mqtt.port; $('#mqtt-user').value = value.mqtt.username; $('#mqtt-discovery').value = value.mqtt.discovery_prefix; $('#mqtt-topic').value = value.mqtt.base_topic;
  return value;
}
async function loadMicrophones() { const select = $('#microphone'); try { const result = await api('/api/audio-devices'); select.innerHTML = '<option value="">Systemstandard verwenden</option>' + result.devices.map(device => `<option value="${device.id}">${device.name} (${device.channels} Kanal/Kanäle)</option>`).join(''); select.value = result.selected ?? ''; } catch (_) { select.innerHTML = '<option value="">Kein Eingabegerät gefunden</option>'; } }
function openDialog(id, loader = loadConfig) { loader().then(() => $(id).showModal()).catch(() => toast('Einstellungen konnten nicht geladen werden.', true)); }
function json(method, body) { return {method, headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}; }

$('#configuration').onclick = () => $('#config-dialog').showModal();
$('#theme-toggle').onclick = () => { document.body.dataset.theme = document.body.dataset.theme === 'dark' ? 'light' : 'dark'; localStorage.setItem('noisemeter-theme', document.body.dataset.theme); $('#theme-toggle').textContent = document.body.dataset.theme === 'dark' ? '☀' : '☾'; };
[['open-periods','#settings'],['open-measurement','#measurement-dialog'],['open-audio','#audio-dialog'],['open-calibration','#calibration-dialog'],['open-refresh','#refresh-dialog'],['open-mqtt','#mqtt-dialog'],['open-site','#site-dialog'],['open-delete','#delete-dialog']].forEach(([button, dialog]) => { $(`#${button}`).onclick = event => { event.preventDefault(); $('#config-dialog').close(); openDialog(dialog); }; });
$('#open-microphone').onclick = event => { event.preventDefault(); $('#config-dialog').close(); Promise.all([loadConfig(), loadMicrophones()]).then(() => $('#microphone-dialog').showModal()); };
$('#save-microphone').onclick = async event => { event.preventDefault(); try { await api('/api/audio-device', json('PUT', {device:$('#microphone').value || null, microphone_name:$('#microphone-name').value})); $('#microphone-message').textContent = 'Messmikrofon übernommen.'; toast('Messmikrofon gespeichert.'); } catch (_) { $('#microphone-message').textContent = 'Wechsel nicht möglich.'; } };
$('#save-site').onclick = async event => { event.preventDefault(); try { await api('/api/config/site', json('PUT', {site_name:$('#site-name').value, location:$('#site-location').value, orientation:$('#site-orientation').value, microphone_angle:$('#site-angle').value, target_object:$('#site-target').value, ground_distance:$('#site-ground').value, wall_distance:$('#site-wall').value})); $('#site-dialog').close(); await loadConfig(); toast('Messstellendaten und passende Kalibrierung gespeichert.'); } catch (_) { toast('Messstellendaten sind ungültig.', true); } };
$('#save-periods').onclick = async event => { event.preventDefault(); const form = $('#settings form'), periods = [0,1,2].map(index => ({name:form[`name${index}`].value, start:form[`start${index}`].value, end:form[`end${index}`].value, threshold_db:+form[`threshold${index}`].value, warning_db:+form[`warning${index}`].value, severe_db:+form[`severe${index}`].value, enabled:form[`enabled${index}`].checked})); try { await api('/api/config/periods', json('PUT', periods)); $('#settings').close(); await loadEvents(); toast('Zeitbereiche gespeichert.'); } catch (_) { toast('Pegel müssen aufsteigend und vollständig sein.', true); } };
$('#save-audio').onclick = async event => { event.preventDefault(); try { await api('/api/config/audio-storage', json('PUT', {mp3_bitrate_kbps:+$('#bitrate').value, retention_days:+$('#retention').value, pre_roll_seconds:+$('#pre-roll').value, post_roll_seconds:+$('#post-roll').value})); $('#audio-dialog').close(); toast('Audioeinstellungen gespeichert.'); } catch (_) { toast('Audioeinstellungen sind ungültig.', true); } };
$('#save-measurement').onclick = async event => { event.preventDefault(); try { await api('/api/config/measurement', json('PUT', {weighting:$('#weighting').value, time_weighting:$('#time-weighting').value})); $('#measurement-dialog').close(); toast('Messart gespeichert.'); } catch (_) { toast('Messart konnte nicht gespeichert werden.', true); } };
$('#save-calibration').onclick = async event => { event.preventDefault(); try { await api('/api/config/calibration', json('PUT', {manual_calibration_db:+$('#manual-calibration').value})); toast('Kalibrierung gespeichert.'); } catch (_) { toast('Kalibrierung ist ungültig.', true); } };
$('#upload-calibration').onclick = async event => { event.preventDefault(); const file = $('#calibration-upload').files[0]; if (!file) return; const data = new FormData(); data.append('file', file); try { await api('/api/config/calibration-file', {method:'POST', body:data}); await loadConfig(); toast('Kalibrierpaket geladen und Winkelprofil aktiviert.'); } catch (error) { toast(`Kalibrierpaket ungültig: ${error.message}`, true); } };
$('#save-refresh').onclick = async event => { event.preventDefault(); try { await api('/api/config/refresh', json('PUT', {refresh_seconds:+$('#refresh-seconds').value})); refreshSeconds = +$('#refresh-seconds').value; $('#refresh-dialog').close(); toast('Aktualisierung gespeichert. Der Live-Pegel läuft unabhängig davon in Echtzeit.'); } catch (_) { toast('Intervall muss zwischen 5 und 3600 Sekunden liegen.', true); } };
$('#save-mqtt').onclick = async event => { event.preventDefault(); const body = {enabled:$('#mqtt-enabled').checked, host:$('#mqtt-host').value, port:+$('#mqtt-port').value, username:$('#mqtt-user').value, password:$('#mqtt-password').value, discovery_prefix:$('#mqtt-discovery').value, base_topic:$('#mqtt-topic').value}; try { await api('/api/config/mqtt', json('PUT', body)); $('#mqtt-dialog').close(); toast('MQTT-Einstellungen gespeichert.'); } catch (_) { toast('MQTT-Einstellungen sind ungültig.', true); } };
$('#delete-data').onclick = async event => { event.preventDefault(); const from = $('#delete-from').value, to = $('#delete-to').value; if (!from || !to || !$('#delete-confirm').checked) return toast('Bitte Zeitraum und Löschbestätigung angeben.', true); if (!confirm(`Alle Messdaten vom ${from} bis einschließlich ${to} dauerhaft löschen?`)) return; try { const result = await api('/api/data', json('DELETE', {from, to})); $('#delete-dialog').close(); $('#delete-confirm').checked = false; await Promise.all([loadEvents(), loadCounts()]); toast(`${result.measurements} Messwerte, ${result.events} Ereignisse und ${result.audio_files} Audiodateien gelöscht.`); } catch (_) { toast('Daten konnten nicht gelöscht werden.', true); } };
$$('[data-kind]').forEach(button => button.onclick = () => { kind = button.dataset.kind; loadEvents(); });
$('#date').onchange = event => { selected = new Date(`${event.target.value}T12:00:00`); loadEvents(); };
function move(direction) { if (kind === 'day') selected.setDate(selected.getDate() + direction); else if (kind === 'week') selected.setDate(selected.getDate() + 7 * direction); else if (kind === 'month') selected.setMonth(selected.getMonth() + direction); else selected.setFullYear(selected.getFullYear() + direction); loadEvents(); }
$('#previous').onclick = () => move(-1); $('#next').onclick = () => move(1);

const savedTheme = localStorage.getItem('noisemeter-theme'); document.body.dataset.theme = savedTheme || 'dark'; $('#theme-toggle').textContent = document.body.dataset.theme === 'dark' ? '☀' : '☾';
loadConfig();
loadEvents(); loadCounts(); loadSystem(); pollStatus(); setInterval(loadSystem, 10000); setInterval(loadCounts, 30000);
