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

async function loadEvents() {
  setTitle();
  const response = await fetch(`/api/events?kind=${kind}&date=${periodValue()}`);
  const data = await response.json();
  $('#count').textContent = data.summary.event_count;
  $('#peak').textContent = `${data.summary.peak_db.toFixed(1)} dB`;
  $('#average').textContent = `${data.summary.average_db.toFixed(1)} dB`;
  rows(data.events);
}

async function loadConfig() {
  const config = await fetch('/api/config').then(response => response.json());
  $('#periods').innerHTML = config.periods.map(period => `<div>${period.name}: ${period.start}–${period.end}, ab ${period.threshold_db} dB</div>`).join('');
  $('#period-form').innerHTML = config.periods.map((period, index) => `<div class="period-row"><input name="name${index}" value="${period.name}" aria-label="Name"><input name="start${index}" type="time" value="${period.start}"><input name="end${index}" type="time" value="${period.end}"><input name="threshold${index}" type="number" step="0.1" value="${period.threshold_db}" aria-label="dB"></div>`).join('');
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

$('#edit').onclick = showSettings;
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
document.querySelectorAll('[data-kind]').forEach(button => button.onclick = () => { kind = button.dataset.kind; loadEvents(); });
$('#date').onchange = event => { selected = new Date(`${event.target.value}T12:00:00`); loadEvents(); };
$('#previous').onclick = () => { selected.setDate(selected.getDate() - (kind === 'day' ? 1 : kind === 'week' ? 7 : 30)); loadEvents(); };
$('#next').onclick = () => { selected.setDate(selected.getDate() + (kind === 'day' ? 1 : kind === 'week' ? 7 : 30)); loadEvents(); };

loadConfig();
loadMicrophones();
loadEvents();
status();
setInterval(status, 1000);
