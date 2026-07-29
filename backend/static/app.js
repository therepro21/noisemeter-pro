const $ = selector => document.querySelector(selector);
let kind = 'day';
let selected = new Date();
const labels = { day: 'Ereignisse heute', week: 'Ereignisse diese Woche', month: 'Ereignisse diesen Monat' };
const pad = number => String(number).padStart(2, '0');
const day = value => `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;

function periodValue() {
  if (kind === 'day') return day(selected);
  if (kind === 'month') return `${selected.getFullYear()}-${pad(selected.getMonth() + 1)}`;
  const thursday = new Date(selected);
  thursday.setDate(thursday.getDate() + 4 - (thursday.getDay() || 7));
  const yearStart = new Date(thursday.getFullYear(), 0, 1);
  const week = Math.ceil((((thursday - yearStart) / 86400000) + 1) / 7);
  return `${thursday.getFullYear()}-W${pad(week)}`;
}

function setTitle() {
  $('#title').textContent = ({ day: 'Tagesübersicht', week: 'Wochenübersicht', month: 'Monatsübersicht' })[kind];
  $('#count-label').textContent = labels[kind];
  $('#date').value = day(selected);
  $('#pdf').hidden = kind === 'day';
  if (kind !== 'day') $('#pdf').href = `/report/${kind}/${periodValue()}.pdf`;
}

async function status() {
  try {
    const response = await fetch('/api/status');
    const data = await response.json();
    $('#level').innerHTML = `${data.db.toFixed(1).replace('.', ',')} <small>dB</small>`;
    $('#connection').textContent = '● Messung aktiv';
    $('#recording').hidden = !data.recording;
  } catch (_) { $('#connection').textContent = '● Keine Verbindung'; }
}

function rows(events) {
  $('#events').innerHTML = events.length ? events.map(event => `<tr><td>${event.occurred_at.replace('T', ' ')}</td><td>${event.peak_db.toFixed(1)} dB</td><td>${event.threshold_db.toFixed(1)} dB</td><td>${event.period_name}</td><td><audio controls preload="none" src="/audio/${encodeURI(event.filename)}"></audio></td></tr>`).join('') : '<tr><td colspan="5">Keine Ereignisse in diesem Zeitraum.</td></tr>';
}

function drawHistory(points) {
  const canvas = $('#history-chart');
  const width = canvas.clientWidth || 600;
  const height = canvas.clientHeight || 150;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio; canvas.height = height * ratio;
  const context = canvas.getContext('2d'); context.scale(ratio, ratio);
  context.clearRect(0, 0, width, height);
  if (!points.length) { context.fillStyle = '#d7e8f0'; context.font = '13px system-ui'; context.fillText('Noch keine Messwerte für diesen Tag', 12, height / 2); $('#chart-range').textContent = ''; return; }
  const values = points.map(point => point.db);
  const min = Math.floor(Math.min(...values) / 5) * 5 - 5;
  const max = Math.ceil(Math.max(...values) / 5) * 5 + 5;
  const padLeft = 42, padRight = 8, padTop = 8, padBottom = 22;
  const chartWidth = width - padLeft - padRight, chartHeight = height - padTop - padBottom;
  const scaleY = value => padTop + (max - value) / (max - min || 1) * chartHeight;
  context.strokeStyle = 'rgba(255,255,255,.22)'; context.fillStyle = '#d7e8f0'; context.font = '11px system-ui';
  [min, (min + max) / 2, max].forEach(value => { const y = scaleY(value); context.beginPath(); context.moveTo(padLeft, y); context.lineTo(width - padRight, y); context.stroke(); context.fillText(`${Math.round(value)} dB`, 1, y + 4); });
  context.strokeStyle = '#fff'; context.lineWidth = 2; context.beginPath();
  points.forEach((point, index) => { const x = padLeft + index / Math.max(points.length - 1, 1) * chartWidth; const y = scaleY(point.db); if (index) context.lineTo(x, y); else context.moveTo(x, y); }); context.stroke();
  context.fillStyle = '#d7e8f0'; context.fillText(points[0].minute.slice(11, 16), padLeft, height - 5); context.fillText(points.at(-1).minute.slice(11, 16), width - padRight - 30, height - 5);
  $('#chart-range').textContent = `${Math.min(...values).toFixed(1)}–${Math.max(...values).toFixed(1)} dB`;
}

async function loadHistory() {
  try { const data = await fetch(`/api/history?date=${day(selected)}`).then(response => response.json()); drawHistory(data.points); }
  catch (_) { drawHistory([]); }
}

async function loadEvents() {
  setTitle();
  const response = await fetch(`/api/events?kind=${kind}&date=${periodValue()}`);
  const data = await response.json();
  $('#count').textContent = data.summary.event_count;
  $('#peak').textContent = `${data.summary.peak_db.toFixed(1)} dB`;
  $('#average').textContent = `${data.summary.average_db.toFixed(1)} dB`;
  rows(data.events);
  loadHistory();
}

async function loadConfig() {
  const config = await fetch('/api/config').then(response => response.json());
  $('#periods').innerHTML = config.periods.map(period => `<div>${period.name}: ${period.start}–${period.end}, ab ${period.threshold_db} dB</div>`).join('');
  $('#period-form').innerHTML = config.periods.map((period, index) => `<div class="period-row"><input name="name${index}" value="${period.name}" aria-label="Name"><input name="start${index}" type="time" value="${period.start}"><input name="end${index}" type="time" value="${period.end}"><input name="threshold${index}" type="number" step="0.1" value="${period.threshold_db}" aria-label="dB"></div>`).join('');
  $('#bitrate').value = String(config.audio.mp3_bitrate_kbps);
  $('#retention').value = config.storage.retention_days;
}

async function showSettings() { await loadConfig(); $('#settings').showModal(); }

async function loadMicrophones() {
  const select = $('#microphone');
  try {
    const data = await fetch('/api/audio-devices').then(response => response.json());
    select.innerHTML = '<option value="">Systemstandard verwenden</option>' + data.devices.map(device => `<option value="${device.id}">${device.name} (${device.channels} Kanal/Kanäle)</option>`).join('');
    select.value = data.selected === null || data.selected === undefined ? '' : String(data.selected);
    $('#microphone-message').textContent = data.devices.length ? '' : 'Kein Eingabegerät gefunden.';
  } catch (_) { select.innerHTML = '<option>Geräte konnten nicht geladen werden</option>'; }
}

function bytes(value) {
  const units = ['B', 'KB', 'MB', 'GB', 'TB']; let index = 0;
  while (value >= 1024 && index < units.length - 1) { value /= 1024; index++; }
  return `${value.toFixed(index ? 1 : 0)} ${units[index]}`;
}

async function loadSystem() {
  try {
    const data = await fetch('/api/system').then(response => response.json());
    $('#cpu-temperature').textContent = data.cpu_temperature === null ? 'Nicht verfügbar' : `${data.cpu_temperature.toFixed(1)} °C`;
    $('#cpu-percent').textContent = data.cpu_percent === null ? 'Nicht verfügbar' : `${data.cpu_percent.toFixed(1)} %`;
    $('#disk-used').textContent = `${bytes(data.disk_used)} belegt`;
    $('#disk-free').textContent = `${bytes(data.disk_free)} frei von ${bytes(data.disk_total)}`;
  } catch (_) { $('#cpu-temperature').textContent = $('#cpu-percent').textContent = 'Nicht verfügbar'; }
}

$('#edit').onclick = showSettings;
$('#audio-settings').onclick = async () => { await loadConfig(); $('#audio-dialog').showModal(); };
$('#save').onclick = async event => {
  event.preventDefault();
  const form = $('#settings form');
  const periods = [0, 1, 2].map(index => ({ name: form[`name${index}`].value, start: form[`start${index}`].value, end: form[`end${index}`].value, threshold_db: +form[`threshold${index}`].value, enabled: true }));
  const response = await fetch('/api/config/periods', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(periods) });
  if (response.ok) { $('#settings').close(); loadConfig(); }
};
$('#save-microphone').onclick = async () => {
  const select = $('#microphone');
  const device = select.value === '' ? null : Number(select.value);
  $('#microphone-message').textContent = 'Wechsle Mikrofon ...';
  const response = await fetch('/api/audio-device', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ device }) });
  const data = await response.json();
  $('#microphone-message').textContent = response.ok ? 'Mikrofon aktiv.' : `Fehler: ${data.error || 'Wechsel nicht möglich'}`;
};
$('#save-audio').onclick = async event => {
  event.preventDefault();
  const response = await fetch('/api/config/audio-storage', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mp3_bitrate_kbps: Number($('#bitrate').value), retention_days: Number($('#retention').value) }) });
  if (response.ok) $('#audio-dialog').close();
  else alert('Einstellungen konnten nicht gespeichert werden.');
};
document.querySelectorAll('[data-kind]').forEach(button => button.onclick = () => { kind = button.dataset.kind; loadEvents(); });
$('#date').onchange = event => { selected = new Date(`${event.target.value}T12:00:00`); loadEvents(); };
$('#previous').onclick = () => { selected.setDate(selected.getDate() - (kind === 'day' ? 1 : kind === 'week' ? 7 : 30)); loadEvents(); };
$('#next').onclick = () => { selected.setDate(selected.getDate() + (kind === 'day' ? 1 : kind === 'week' ? 7 : 30)); loadEvents(); };

loadConfig();
loadMicrophones();
loadEvents();
status();
loadSystem();
setInterval(status, 1000);
setInterval(loadSystem, 10000);
