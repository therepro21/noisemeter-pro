const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
let language = localStorage.getItem('noisemeter-language') || 'en';
const locale = () => language === 'de' ? 'de-DE' : 'en-GB';
const I18N = {
  connecting:['Connecting …','Verbinde …'], active:['● Measurement active','● Messung aktiv'], noMic:['● No measurement microphone','● Kein Messmikrofon'], noConnection:['● No connection','● Keine Verbindung'],
  dayOverview:['Daily overview','Tagesübersicht'], weekOverview:['Weekly overview','Wochenübersicht'], monthOverview:['Monthly overview','Monatsübersicht'], yearOverview:['Yearly overview','Jahresübersicht'],
  dayEvents:['Events on this day','Ereignisse am Tag'], weekEvents:['Events this week','Ereignisse der Woche'], monthEvents:['Events this month','Ereignisse des Monats'], yearEvents:['Events this year','Ereignisse des Jahres'],
  loading:['Loading …','Wird geladen …'], loadFailed:['Loading failed','Laden fehlgeschlagen'], noDayValues:['No valid measurements for this day','Noch keine gültigen Messwerte für diesen Tag'], noSignal:['No measurement signal','Kein Messsignal'], waitSignal:['Waiting for measurement signal …','Warte auf Messsignal …'],
  dominant:['Dominant','Dominant'], eventDuration:['Event duration','Ereignisdauer'], part:['Part','Teil'], noEvents:['No events in this period.','Keine Ereignisse in diesem Zeitraum.'], events:['Events','Ereignisse'], maximum:['Maximum','Maximum'], average:['Average','Durchschnitt'], minimum:['Minimum','Minimum'], noValues:['No valid measurements','Keine gültigen Messwerte'],
  hourAnalysis:['Hourly analysis','Stundenauswertung'], dayAnalysis:['Daily analysis','Tagesauswertung'], weekAnalysis:['Weekly analysis','Wochenauswertung'], monthAnalysis:['Monthly analysis','Monatsauswertung'], period:['Period','Zeitraum'], maximumLevel:['Maximum level','Maximalpegel'], averageLevel:['Average level','Durchschnittspegel'],
  unavailable:['Unavailable','Nicht verfügbar'], used:['used','belegt'], freeOf:['free of','frei von'], unchanged:['100% / unchanged','100 % / unverändert'],
  day:['Day','Tag'], evening:['Evening','Abend'], night:['Night','Nacht']
};
const t = key => I18N[key]?.[language === 'de' ? 1 : 0] ?? key;
const ui = (german, english) => language === 'de' ? german : english;
const STATIC_EN = {
  'Schallpegelüberwachung · Version 3.0':'Sound level monitoring · Version 3.0','Einstellungen':'Settings','AKTUELLER PEGEL':'CURRENT LEVEL','Unkalibriert:':'Uncalibrated:','Kein Messmikrofon gefunden':'No measurement microphone found','● Ereignisaufnahme läuft':'● Event recording active','Frequenzspektrum · letzte 30 Sekunden':'Frequency spectrum · last 30 seconds','Dominante Frequenz:':'Dominant frequency:','Pegelverlauf für':'Level history for','Weiß: Pegel · Cyan: Leq':'White: level · cyan: Leq','Ereignisse auf einen Blick':'Events at a glance','Heute':'Today','Woche':'Week','Monat':'Month','Jahr':'Year','Aktuell':'Current','Tag':'Day','Höchster Ereignispegel':'Highest event level','Ø Ereignispegel':'Average event level','Heutige Ereignisse':'Today’s events','Zeitpunkt':'Time','Grenzwert':'Threshold','Bereich':'Period','Aufnahme':'Recording','Temperatur':'Temperature','NoiseMeter-Pro-Daten':'NoiseMeter Pro data','Messmikrofon':'Measurement microphone','Messstellendaten':'Measurement site data','Zeitbereiche':'Time periods','Messart (dBA/dBC)':'Measurement type (dBA/dBC)','Audio & Speicher':'Audio & storage','Kalibrierung':'Calibration','Live-Aktualisierung':'Live refresh','Messdaten löschen':'Delete measurement data','Schließen':'Close','Abbrechen':'Cancel','Speichern':'Save','Übernehmen':'Apply','USB-Eingabegerät':'USB input device','Eigener Mikrofonname':'Custom microphone name','Dieser Name wird im Webinterface und in PDF-Berichten verwendet.':'This name is used in the web interface and PDF reports.','Name der Messstelle':'Measurement site name','Aufstellort':'Installation location','Ausrichtung':'Orientation','Mikrofonwinkel zur Schallquelle':'Microphone angle to sound source','Zielobjekt':'Target object','Abstand zum Boden':'Distance from ground','Abstand zur Wand':'Distance from wall','Die drei Zeitbereiche':'The three time periods','Name':'Name','Von':'From','Bis':'To','Grenze':'Threshold','Warnung':'Warning','Kritisch':'Critical','Aktiv':'Active','Änderungen gelten ab dem nächsten Ereignis.':'Changes apply from the next event.','Aufbewahrungsdauer in Tagen':'Retention period in days','Vorlaufzeit (s)':'Pre-roll (s)','Nachlaufzeit (s)':'Post-roll (s)','Abgelaufene MP3-Dateien und Ereignisse werden automatisch gelöscht.':'Expired MP3 files and events are deleted automatically.','Messart':'Measurement type','Frequenzbewertung':'Frequency weighting','Zeitbewertung':'Time weighting','Mikrofonkalibrierung':'Microphone calibration','Kalibrierpaket hochladen':'Upload calibration package','Manuelle Korrektur in dB':'Manual correction in dB','Korrektur speichern':'Save correction','Intervall in Sekunden':'Interval in seconds','Messdaten vollständig löschen':'Permanently delete measurement data','Dieser Vorgang entfernt Messwerte, Ereigniseinträge und zugehörige MP3-Dateien dauerhaft.':'This permanently removes measurements, event records and associated MP3 files.','Bis einschließlich':'Through','Ich bestätige das dauerhafte Löschen.':'I confirm permanent deletion.','Ausgewählte Daten löschen':'Delete selected data','MQTT aktivieren':'Enable MQTT','Broker-Adresse':'Broker address','Benutzername':'Username','Passwort':'Password','Leer lassen, um beizubehalten':'Leave blank to keep unchanged','Basistopic':'Base topic'
};
const originalText = new WeakMap();
function applyStaticLanguage() {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode; if (!originalText.has(node)) originalText.set(node, node.nodeValue);
    const source = originalText.get(node), trimmed = source.trim(); if (!trimmed) continue;
    const translated = language === 'en' ? (STATIC_EN[trimmed] || trimmed) : trimmed;
    node.nodeValue = source.replace(trimmed, translated);
  }
  document.documentElement.lang = language; $('#language-select').value = language;
  $('#theme-toggle').title = language === 'de' ? 'Farbschema wechseln' : 'Change colour theme';
  $('#theme-toggle').setAttribute('aria-label', $('#theme-toggle').title);
  $('.brand').setAttribute('aria-label', ui('NoiseMeter Pro Startseite','NoiseMeter Pro home'));
  $('#date').setAttribute('aria-label', ui('Datum','Date')); $('#previous').setAttribute('aria-label', ui('Zurück','Previous')); $('#next').setAttribute('aria-label', ui('Weiter','Next'));
  $('#current').title = ui('Zum heutigen Tagesverlauf','Return to today’s history');
  $('#history-chart').setAttribute('aria-label', ui('Pegel- und Leq-Verlauf des ausgewählten Tages','Level and Leq history for the selected day'));
}
const setText = (selector, value) => { const element = $(selector), text = String(value); if (element.textContent !== text) element.textContent = text; };
const setHtml = (selector, value) => { const element = $(selector); if (element.innerHTML !== value) element.innerHTML = value; };
const pad = number => String(number).padStart(2, '0');
const localDay = value => `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
const db = value => value == null ? '–' : `${Number(value).toLocaleString(locale(), {minimumFractionDigits:1, maximumFractionDigits:1})} dB`;
let kind = 'day';
let selected = new Date();
let refreshSeconds = 5;
let overviewLoadId = 0;
let spectrumRows = [], spectrumFrequencies = [], lastSpectrumSequence = null, spectrumRowLimit = 120;
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
  const isToday = localDay(selected) === localDay(new Date());
  $('#title').textContent = ({day:t('dayOverview'), week:t('weekOverview'), month:t('monthOverview'), year:t('yearOverview')})[kind];
  $('#count-label').textContent = ({day:t('dayEvents'), week:t('weekEvents'), month:t('monthEvents'), year:t('yearEvents')})[kind];
  $('#date').value = localDay(selected); $('#pdf').href = `/report/${kind}/${periodValue()}.pdf?lang=${language}`; $('#backup').href = `/backup/${kind}/${periodValue()}.zip`;
  $('#history-date').textContent = new Intl.DateTimeFormat(locale(), { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' }).format(selected);
  $('#history-panel').classList.toggle('historical', !isToday);
  $('#current').classList.toggle('is-current', isToday && kind === 'day');
  $('#period-section').hidden = kind !== 'day';
  $$('[data-kind]').forEach(button => button.classList.toggle('active', button.dataset.kind === kind));
}
async function loadStatus() {
  try {
    const value = await api('/api/status');
    if (value.available && value.db != null) {
      setHtml('#level', `${value.db.toFixed(1).replace('.', ',')} <small>dB</small>`);
      setText('#uncalibrated-level', db(value.uncalibrated_db));
      setText('#live-leq', db(value.leq_db));
      const mixer = value.input_gain?.channels?.length ? value.input_gain.channels.map(level => `${level} %`).join(' - ') : value.input_gain?.percent != null ? `${value.input_gain.percent} %` : t('unchanged');
      setText('#mixer-level', mixer);
      if (value.spectrum && value.spectrum.sequence !== lastSpectrumSequence) {
        lastSpectrumSequence = value.spectrum.sequence;
        spectrumFrequencies = value.spectrum.frequencies;
        spectrumRowLimit = Math.max(1, Math.round(30 / (value.spectrum.interval_seconds || .25)));
        spectrumRows.unshift(value.spectrum.levels_db); spectrumRows.length = Math.min(spectrumRows.length, spectrumRowLimit);
        setText('#dominant-frequency', formatFrequency(value.spectrum.dominant_hz));
        drawSpectrum();
      }
      $('#level').hidden = false; $('#microphone-warning').hidden = true;
      $('#connection').textContent = t('active'); $('#connection').className = 'online';
    } else {
      $('#level').innerHTML = '0,0 <small>dB</small>'; $('#level').hidden = true;
      $('#uncalibrated-level').textContent = '–'; $('#live-leq').textContent = '–';
      $('#mixer-level').textContent = '–';
      if (lastSpectrumSequence !== null || spectrumRows.length) resetSpectrum(t('noSignal'));
      $('#microphone-warning').hidden = false; $('#connection').textContent = t('noMic'); $('#connection').className = 'offline';
    }
    $('#recording').hidden = !value.recording;
  } catch (_) { $('#connection').textContent = t('noConnection'); $('#connection').className = 'offline'; }
}
async function pollStatus() {
  await loadStatus();
  setTimeout(pollStatus, LIVE_STATUS_INTERVAL_MS);
}
function drawHistory(points) {
  const canvas = $('#history-chart'), width = canvas.clientWidth || 600, height = canvas.clientHeight || 150, ratio = devicePixelRatio || 1;
  canvas.width = width * ratio; canvas.height = height * ratio; const context = canvas.getContext('2d'); context.scale(ratio, ratio); context.clearRect(0, 0, width, height);
  if (!points.length) { context.fillStyle = '#9fc5d8'; context.font = '13px system-ui'; context.fillText(t('noDayValues'), 12, height / 2); $('#chart-range').textContent = ''; return; }
  const values = points.flatMap(point => [point.db, point.leq_db]).filter(value => value != null), minimum = Math.floor(Math.min(...values) / 5) * 5 - 5, maximum = Math.ceil(Math.max(...values) / 5) * 5 + 5;
  const left = 42, right = 8, top = 8, bottom = 22, chartWidth = width - left - right, chartHeight = height - top - bottom, y = number => top + (maximum - number) / (maximum - minimum || 1) * chartHeight;
  context.strokeStyle = 'rgba(255,255,255,.22)'; context.fillStyle = '#d7e8f0'; context.font = '11px system-ui';
  [minimum, (minimum + maximum) / 2, maximum].forEach(number => { const yy = y(number); context.beginPath(); context.moveTo(left, yy); context.lineTo(width - right, yy); context.stroke(); context.fillText(`${Math.round(number)} dB`, 1, yy + 4); });
  const line = (field, color) => { context.strokeStyle = color; context.lineWidth = 2; context.beginPath(); let started = false; points.forEach((point, index) => { if (point[field] == null) return; const xx = left + index / Math.max(points.length - 1, 1) * chartWidth, yy = y(point[field]); started ? context.lineTo(xx, yy) : context.moveTo(xx, yy); started = true; }); context.stroke(); };
  line('db', '#fff'); line('leq_db', '#32e1f2');
  context.fillText(points[0].minute.slice(11, 16), left, height - 5); context.fillText(points.at(-1).minute.slice(11, 16), width - right - 30, height - 5); $('#chart-range').textContent = `${db(Math.min(...values))} – ${db(Math.max(...values))}`;
}
function formatFrequency(value) {
  if (value == null) return '–';
  return value >= 1000 ? `${(value / 1000).toFixed(value >= 10000 ? 0 : 1).replace('.', ',')} kHz` : `${Math.round(value)} Hz`;
}
function spectrumColor(level) {
  const stops = [[7,25,39],[12,91,130],[22,188,195],[242,209,75],[239,81,60]], position = Math.max(0, Math.min(1, (level - 20) / 80)) * (stops.length - 1);
  const index = Math.min(stops.length - 2, Math.floor(position)), mix = position - index;
  return `rgb(${stops[index].map((value, channel) => Math.round(value + (stops[index + 1][channel] - value) * mix)).join(',')})`;
}
function drawSpectrum(message = null) {
  const canvas = $('#spectrum-chart'), width = canvas.clientWidth || 480, height = canvas.clientHeight || 142, ratio = devicePixelRatio || 1;
  canvas.width = width * ratio; canvas.height = height * ratio; const context = canvas.getContext('2d'); context.scale(ratio, ratio);
  context.fillStyle = '#071925'; context.fillRect(0, 0, width, height);
  if (message || !spectrumRows.length) {
    context.fillStyle = '#9fc5d8'; context.font = '12px system-ui'; context.fillText(message || t('waitSignal'), 10, height / 2);
    return;
  }
  const axisHeight = 18, plotHeight = height - axisHeight, bandWidth = width / spectrumRows[0].length, rowHeight = plotHeight / spectrumRowLimit;
  spectrumRows.forEach((levels, row) => levels.forEach((level, band) => { context.fillStyle = spectrumColor(level); context.fillRect(band * bandWidth, row * rowHeight, Math.ceil(bandWidth) + .5, Math.ceil(rowHeight) + .5); }));
  context.fillStyle = '#071925'; context.fillRect(0, plotHeight, width, axisHeight);
  context.fillStyle = '#b9d8e6'; context.font = '10px system-ui'; context.textAlign = 'center';
  [31.5,125,500,2000,8000,16000].forEach(target => {
    const index = spectrumFrequencies.reduce((best, value, current) => Math.abs(value - target) < Math.abs(spectrumFrequencies[best] - target) ? current : best, 0);
    const x = Math.max(15, Math.min(width - 18, (index + .5) * bandWidth)); context.fillText(formatFrequency(target), x, height - 4);
  });
  canvas.setAttribute('aria-label', `Wasserfall-Frequenzspektrum der letzten 30 Sekunden; dominante Frequenz ${$('#dominant-frequency').textContent}`);
}
function resetSpectrum(message = t('waitSignal')) {
  spectrumRows = []; spectrumFrequencies = []; lastSpectrumSequence = null; setText('#dominant-frequency', '–'); drawSpectrum(message);
}
function setHistoryLoading(message = t('loading')) {
  const panel = $('#history-panel'), loading = $('#history-loading'), canvas = $('#history-chart');
  panel.classList.add('loading'); loading.hidden = false; loading.textContent = message; $('#chart-range').textContent = '';
  const context = canvas.getContext('2d'); context.clearRect(0, 0, canvas.width, canvas.height);
}
function finishHistoryLoading() { $('#history-panel').classList.remove('loading'); $('#history-loading').hidden = true; }
const dateFormat = value => new Intl.DateTimeFormat(locale(), {weekday:'long', day:'numeric', month:'long', year:'numeric', hour:'2-digit', minute:'2-digit'}).format(new Date(value));
function eventRows(events) {
  $('#events').innerHTML = events.length ? events.map(event => {
    const severity = event.peak_db >= event.severe_db ? 'violet' : event.peak_db >= event.warning_db ? 'red' : 'orange';
    const frequency = event.dominant_frequency_hz == null ? '' : `<small class="event-frequency">${t('dominant')}: ${formatFrequency(event.dominant_frequency_hz)}</small>`;
    const duration = `<small class="event-frequency">${t('eventDuration')}: ${Math.round(event.duration_seconds)} s</small>`;
    const audio = (event.audio_files?.length ? event.audio_files : [event.filename]).map((filename, index, files) => `<div class="event-audio">${files.length > 1 ? `<small>${t('part')} ${index + 1}/${files.length}</small>` : ''}<audio controls preload="none" src="/audio/${encodeURI(filename)}"></audio></div>`).join('');
    const period = ({Tag:t('day'), Abend:t('evening'), Nacht:t('night')})[event.period_name] || event.period_name;
    return `<tr class="event-${severity}"><td>${dateFormat(event.occurred_at)}${duration}</td><td>${db(event.peak_db)}${frequency}</td><td>${db(event.leq_db)}</td><td>${db(event.threshold_db)}</td><td>${period}</td><td>${audio}</td></tr>`;
  }).join('') : `<tr><td colspan="6">${t('noEvents')}</td></tr>`;
}
function renderPeriodStats(result) {
  $('#period-stats').innerHTML = result.items.map(item => `<article><div class="period-title"><strong>${({Tag:t('day'),Abend:t('evening'),Nacht:t('night')})[item.name] || item.name}</strong><small>${item.start}–${item.end}</small></div><dl><div><dt>${t('events')}</dt><dd>${item.event_count}</dd></div><div><dt>${t('maximum')}</dt><dd>${db(item.maximum_db)}</dd></div><div><dt>${t('average')}</dt><dd>${db(item.average_db)}</dd></div><div><dt>Leq</dt><dd>${db(item.leq_db)}</dd></div><div><dt>${t('minimum')}</dt><dd>${db(item.minimum_db)}</dd></div></dl>${item.measurement_count ? '' : `<p class="no-data">${t('noValues')}</p>`}</article>`).join('');
}
function renderBreakdown(result, selectedKind) {
  const names = {day:t('hourAnalysis'), week:t('dayAnalysis'), month:t('weekAnalysis'), year:t('monthAnalysis')};
  $('#breakdown').innerHTML = `<h2>${names[selectedKind]}</h2><div class="table-scroll"><table><thead><tr><th>${t('period')}</th><th>${t('maximumLevel')}</th><th>${t('averageLevel')}</th><th>Leq</th></tr></thead><tbody>${result.items.map(item => `<tr><td>${item.label}</td><td>${db(item.maximum_db)}</td><td>${db(item.average_db)}</td><td>${db(item.leq_db)}</td></tr>`).join('') || `<tr><td colspan="4">${t('noValues')}</td></tr>`}</tbody></table></div>`;
}
async function loadEvents() {
  const loadId = ++overviewLoadId;
  setTitle();
  setHistoryLoading();
  const selectedKind = kind, selectedDay = localDay(selected), selectedPeriod = periodValue();
  try {
    const [result, history, breakdown, periodStats] = await Promise.all([
      api(`/api/events?kind=${selectedKind}&date=${selectedPeriod}`),
      api(`/api/history?date=${selectedDay}`),
      api(`/api/breakdown?kind=${selectedKind}&date=${selectedPeriod}`),
      selectedKind === 'day' ? api(`/api/period-statistics?date=${selectedDay}`) : Promise.resolve(null),
    ]);
    if (loadId !== overviewLoadId) return;
    $('#count').textContent = result.summary.event_count; $('#peak').textContent = db(result.summary.peak_db); $('#average').textContent = db(result.summary.average_db); $('#summary-leq').textContent = db(result.summary.leq_db); eventRows(result.events);
    renderBreakdown(breakdown, selectedKind); if (periodStats) renderPeriodStats(periodStats);
    finishHistoryLoading(); drawHistory(history.points);
  } catch (error) { if (loadId === overviewLoadId) { setHistoryLoading(t('loadFailed')); toast(language === 'de' ? 'Übersicht konnte nicht geladen werden.' : 'Overview could not be loaded.', true); } }
}
async function loadCounts() { try { const result = await api('/api/event-counts'); ['day','week','month','year'].forEach(name => $(`#count-${name}`).textContent = result[name]); } catch (_) {} }
const bytes = number => { const units = ['B','KB','MB','GB','TB']; let index = 0; while (number >= 1024 && index < 4) { number /= 1024; index++; } return `${number.toFixed(index ? 1 : 0)} ${units[index]}`; };
async function loadSystem() { try { const value = await api('/api/system'); $('#cpu-temperature').textContent = value.cpu_temperature == null ? t('unavailable') : `${value.cpu_temperature.toFixed(1)} °C`; $('#cpu-percent').textContent = value.cpu_percent == null ? t('unavailable') : `${value.cpu_percent.toFixed(1)} %`; $('#disk-used').textContent = `${bytes(value.disk_used)} ${t('used')}`; $('#disk-free').textContent = `${bytes(value.disk_free)} ${t('freeOf')} ${bytes(value.disk_total)}`; } catch (_) {} }
async function loadConfig() {
  const value = await api('/api/config'), site = value.site_data || {};
  refreshSeconds = value.web.refresh_seconds; $('#refresh-seconds').value = refreshSeconds;
  $('#period-form').innerHTML = value.periods.map((period, index) => `<div class="period-row"><input name="name${index}" value="${period.name}"><input name="start${index}" type="time" value="${period.start}"><input name="end${index}" type="time" value="${period.end}"><input name="threshold${index}" type="number" step=".1" value="${period.threshold_db}"><input name="warning${index}" type="number" step=".1" value="${period.warning_db ?? +period.threshold_db + 10}"><input name="severe${index}" type="number" step=".1" value="${period.severe_db ?? +period.threshold_db + 15}"><input name="enabled${index}" type="checkbox" ${period.enabled !== false ? 'checked' : ''}></div>`).join('');
  $('#bitrate').value = value.audio.mp3_bitrate_kbps; $('#retention').value = value.storage.retention_days; $('#pre-roll').value = value.audio.pre_roll_seconds; $('#post-roll').value = value.audio.post_roll_seconds;
  $('#weighting').value = value.audio.weighting; $('#time-weighting').value = value.audio.time_weighting; $('#manual-calibration').value = value.audio.manual_calibration_db; $('#calibration-file').textContent = value.audio.calibration_file ? ui(`Aktiv: ${value.audio.calibration_file} (${value.audio.calibration_angle}°), ${value.calibration.points} Frequenzpunkte`, `Active: ${value.audio.calibration_file} (${value.audio.calibration_angle}°), ${value.calibration.points} frequency points`) : ui('Keine Kalibrierdatei hinterlegt.','No calibration file stored.');
  const gainValues = value.input_gain.channels?.length ? value.input_gain.channels : value.input_gain.percent == null ? [] : [value.input_gain.percent];
  $('#microphone-name').value = value.audio.microphone_name || ''; $('#site-name').value = value.site_name; $('#site-location').value = site.location || ''; $('#site-orientation').value = site.orientation || ''; $('#site-angle').value = value.audio.calibration_angle || '0'; $('#site-target').value = site.target_object || ''; $('#site-ground').value = site.ground_distance || ''; $('#site-wall').value = site.wall_distance || ''; $('#gain-status').textContent = gainValues.length ? `${ui('USB-Mixerpegel','USB mixer level')}: ${gainValues.map(level => `${level} %`).join(' - ')}${value.input_gain.enforced ? ui(' (bei Programmstart automatisch auf Maximum gesetzt)',' (automatically set to maximum at startup)') : ''}` : ui('USB-Mixerpegel: 100 % / unverändert (nicht auslesbar)','USB mixer level: 100% / unchanged (not readable)');
  $('#mqtt-enabled').checked = value.mqtt.enabled; $('#mqtt-host').value = value.mqtt.host; $('#mqtt-port').value = value.mqtt.port; $('#mqtt-user').value = value.mqtt.username; $('#mqtt-discovery').value = value.mqtt.discovery_prefix; $('#mqtt-topic').value = value.mqtt.base_topic;
  return value;
}
async function loadMicrophones() { const select = $('#microphone'); try { const result = await api('/api/audio-devices'); select.innerHTML = `<option value="">${ui('Systemstandard verwenden','Use system default')}</option>` + result.devices.map(device => `<option value="${device.id}">${device.name} (${device.channels} ${ui('Kanal/Kanäle','channel(s)')})</option>`).join(''); select.value = result.selected ?? ''; } catch (_) { select.innerHTML = `<option value="">${ui('Kein Eingabegerät gefunden','No input device found')}</option>`; } }
function openDialog(id, loader = loadConfig) { loader().then(() => $(id).showModal()).catch(() => toast(ui('Einstellungen konnten nicht geladen werden.','Settings could not be loaded.'), true)); }
function json(method, body) { return {method, headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}; }

$('#configuration').onclick = () => $('#config-dialog').showModal();
$('#language-select').onchange = event => {
  language = event.target.value === 'de' ? 'de' : 'en'; localStorage.setItem('noisemeter-language', language);
  applyStaticLanguage(); resetSpectrum(); loadConfig(); loadEvents(); loadSystem(); loadStatus();
};
$('#theme-toggle').onclick = () => { document.body.dataset.theme = document.body.dataset.theme === 'dark' ? 'light' : 'dark'; localStorage.setItem('noisemeter-theme', document.body.dataset.theme); $('#theme-toggle').textContent = document.body.dataset.theme === 'dark' ? '☀' : '☾'; };
[['open-periods','#settings'],['open-measurement','#measurement-dialog'],['open-audio','#audio-dialog'],['open-calibration','#calibration-dialog'],['open-refresh','#refresh-dialog'],['open-mqtt','#mqtt-dialog'],['open-site','#site-dialog'],['open-delete','#delete-dialog']].forEach(([button, dialog]) => { $(`#${button}`).onclick = event => { event.preventDefault(); $('#config-dialog').close(); openDialog(dialog); }; });
$('#open-microphone').onclick = event => { event.preventDefault(); $('#config-dialog').close(); Promise.all([loadConfig(), loadMicrophones()]).then(() => $('#microphone-dialog').showModal()); };
$('#save-microphone').onclick = async event => { event.preventDefault(); try { await api('/api/audio-device', json('PUT', {device:$('#microphone').value || null, microphone_name:$('#microphone-name').value})); $('#microphone-message').textContent = ui('Messmikrofon übernommen.','Measurement microphone applied.'); toast(ui('Messmikrofon gespeichert.','Measurement microphone saved.')); } catch (_) { $('#microphone-message').textContent = ui('Wechsel nicht möglich.','Switch not possible.'); } };
$('#save-site').onclick = async event => { event.preventDefault(); try { await api('/api/config/site', json('PUT', {site_name:$('#site-name').value, location:$('#site-location').value, orientation:$('#site-orientation').value, microphone_angle:$('#site-angle').value, target_object:$('#site-target').value, ground_distance:$('#site-ground').value, wall_distance:$('#site-wall').value})); $('#site-dialog').close(); await loadConfig(); toast(ui('Messstellendaten und passende Kalibrierung gespeichert.','Measurement-site data and matching calibration saved.')); } catch (_) { toast(ui('Messstellendaten sind ungültig.','Measurement-site data is invalid.'), true); } };
$('#save-periods').onclick = async event => { event.preventDefault(); const form = $('#settings form'), periods = [0,1,2].map(index => ({name:form[`name${index}`].value, start:form[`start${index}`].value, end:form[`end${index}`].value, threshold_db:+form[`threshold${index}`].value, warning_db:+form[`warning${index}`].value, severe_db:+form[`severe${index}`].value, enabled:form[`enabled${index}`].checked})); try { await api('/api/config/periods', json('PUT', periods)); $('#settings').close(); await loadEvents(); toast(ui('Zeitbereiche gespeichert.','Time periods saved.')); } catch (_) { toast(ui('Pegel müssen aufsteigend und vollständig sein.','Levels must be complete and in ascending order.'), true); } };
$('#save-audio').onclick = async event => { event.preventDefault(); try { await api('/api/config/audio-storage', json('PUT', {mp3_bitrate_kbps:+$('#bitrate').value, retention_days:+$('#retention').value, pre_roll_seconds:+$('#pre-roll').value, post_roll_seconds:+$('#post-roll').value})); $('#audio-dialog').close(); toast(ui('Audioeinstellungen gespeichert.','Audio settings saved.')); } catch (_) { toast(ui('Audioeinstellungen sind ungültig.','Audio settings are invalid.'), true); } };
$('#save-measurement').onclick = async event => { event.preventDefault(); try { await api('/api/config/measurement', json('PUT', {weighting:$('#weighting').value, time_weighting:$('#time-weighting').value})); $('#measurement-dialog').close(); toast(ui('Messart gespeichert.','Measurement type saved.')); } catch (_) { toast(ui('Messart konnte nicht gespeichert werden.','Measurement type could not be saved.'), true); } };
$('#save-calibration').onclick = async event => { event.preventDefault(); try { await api('/api/config/calibration', json('PUT', {manual_calibration_db:+$('#manual-calibration').value})); toast('Kalibrierung gespeichert.'); } catch (_) { toast('Kalibrierung ist ungültig.', true); } };
$('#upload-calibration').onclick = async event => { event.preventDefault(); const file = $('#calibration-upload').files[0]; if (!file) return; const data = new FormData(); data.append('file', file); try { await api('/api/config/calibration-file', {method:'POST', body:data}); await loadConfig(); toast('Kalibrierpaket geladen und Winkelprofil aktiviert.'); } catch (error) { toast(`Kalibrierpaket ungültig: ${error.message}`, true); } };
$('#save-refresh').onclick = async event => { event.preventDefault(); try { await api('/api/config/refresh', json('PUT', {refresh_seconds:+$('#refresh-seconds').value})); refreshSeconds = +$('#refresh-seconds').value; $('#refresh-dialog').close(); toast('Aktualisierung gespeichert. Der Live-Pegel läuft unabhängig davon in Echtzeit.'); } catch (_) { toast('Intervall muss zwischen 5 und 3600 Sekunden liegen.', true); } };
$('#save-mqtt').onclick = async event => { event.preventDefault(); const body = {enabled:$('#mqtt-enabled').checked, host:$('#mqtt-host').value, port:+$('#mqtt-port').value, username:$('#mqtt-user').value, password:$('#mqtt-password').value, discovery_prefix:$('#mqtt-discovery').value, base_topic:$('#mqtt-topic').value}; try { await api('/api/config/mqtt', json('PUT', body)); $('#mqtt-dialog').close(); toast('MQTT-Einstellungen gespeichert.'); } catch (_) { toast('MQTT-Einstellungen sind ungültig.', true); } };
$('#delete-data').onclick = async event => { event.preventDefault(); const from = $('#delete-from').value, to = $('#delete-to').value; if (!from || !to || !$('#delete-confirm').checked) return toast('Bitte Zeitraum und Löschbestätigung angeben.', true); if (!confirm(`Alle Messdaten vom ${from} bis einschließlich ${to} dauerhaft löschen?`)) return; try { const result = await api('/api/data', json('DELETE', {from, to})); $('#delete-dialog').close(); $('#delete-confirm').checked = false; await Promise.all([loadEvents(), loadCounts()]); toast(`${result.measurements} Messwerte, ${result.events} Ereignisse und ${result.audio_files} Audiodateien gelöscht.`); } catch (_) { toast('Daten konnten nicht gelöscht werden.', true); } };
$$('[data-kind]').forEach(button => button.onclick = () => { kind = button.dataset.kind; loadEvents(); });
$('#current').onclick = () => { selected = new Date(); kind = 'day'; loadEvents(); };
$('#date').onchange = event => { selected = new Date(`${event.target.value}T12:00:00`); loadEvents(); };
function move(direction) { if (kind === 'day') selected.setDate(selected.getDate() + direction); else if (kind === 'week') selected.setDate(selected.getDate() + 7 * direction); else if (kind === 'month') selected.setMonth(selected.getMonth() + direction); else selected.setFullYear(selected.getFullYear() + direction); loadEvents(); }
$('#previous').onclick = () => move(-1); $('#next').onclick = () => move(1);

const savedTheme = localStorage.getItem('noisemeter-theme'); document.body.dataset.theme = savedTheme || 'dark'; $('#theme-toggle').textContent = document.body.dataset.theme === 'dark' ? '☀' : '☾';
let spectrumResizeTimer; window.addEventListener('resize', () => { clearTimeout(spectrumResizeTimer); spectrumResizeTimer = setTimeout(() => drawSpectrum(), 120); });
applyStaticLanguage();
drawSpectrum();
loadConfig();
loadEvents(); loadCounts(); loadSystem(); pollStatus(); setInterval(loadSystem, 10000); setInterval(loadCounts, 30000);
