const statusCard = document.getElementById('statusCard');
const statusTitle = document.getElementById('statusTitle');
const statusUntil = document.getElementById('statusUntil');
const statusDescription = document.getElementById('statusDescription');
const scheduleDate = document.getElementById('scheduleDate');
const periodsEl = document.getElementById('periods');
const dayBar = document.getElementById('dayBar');
const updatedEl = document.getElementById('updated');
const refreshButton = document.getElementById('refreshButton');

const labels = { on: 'Світло є', off: 'Немає світла', unknown: 'Невідомо' };

function statusText(status) {
  if (status === 'on') return 'Світло є';
  if (status === 'off') return 'Світла немає';
  return 'Немає даних';
}

function minutes(value) {
  if (!value) return 0;
  if (value === '24:00') return 1440;
  const [hour, minute] = value.split(':').map(Number);
  return hour * 60 + minute;
}

function describeNow(data) {
  if (data.currentStatus === 'on') {
    return data.nextChange
      ? `Наступне відключення о ${data.nextChange.time}.`
      : 'До кінця доби відключення не позначене.';
  }
  if (data.currentStatus === 'off') {
    return data.nextChange
      ? `За графіком світло повернеться о ${data.nextChange.time}.`
      : 'Час завершення відключення не визначено.';
  }
  return 'Кольори графіка не вдалося прочитати. Перевірте офіційний сайт.';
}

function untilText(data) {
  if (!data.nextChange) {
    return data.currentStatus === 'on' ? 'До кінця доби' : '';
  }
  return data.currentStatus === 'off'
    ? `Світло о ${data.nextChange.time}`
    : `До ${data.nextChange.time}`;
}

function renderTimeline(periods, nowMinutes) {
  dayBar.innerHTML = '';
  for (const period of periods) {
    const length = Math.max(minutes(period.end) - minutes(period.start), 1);
    const seg = document.createElement('div');
    seg.className = `seg ${period.status || 'unknown'}`;
    seg.style.flex = String(length);
    dayBar.append(seg);
  }
  if (nowMinutes == null) return;
  const marker = document.createElement('div');
  marker.className = 'now-marker';
  marker.style.left = `${Math.min(Math.max(nowMinutes / 1440, 0), 1) * 100}%`;
  dayBar.append(marker);
}

function render(data) {
  const status = data.currentStatus || 'unknown';
  const nowMinutes = data.checkedAt ? minutes(data.checkedAt) : null;
  statusCard.className = `status-card ${status}`;
  statusTitle.textContent = statusText(status);
  statusDescription.textContent = describeNow(data);
  const until = untilText(data);
  statusUntil.hidden = !until;
  statusUntil.textContent = until;
  scheduleDate.textContent = data.date || 'Дата невідома';
  updatedEl.textContent = `На сайті оновлено: ${data.updated || 'час не визначено'} · перевірено о ${data.checkedAt || '—'}`;

  const periods = data.periods || [];
  renderTimeline(periods, nowMinutes);
  periodsEl.innerHTML = '';
  if (!data.isToday) {
    const warning = document.createElement('div');
    warning.className = 'error';
    warning.textContent = 'Увага: дата графіка на сайті не збігається із сьогоднішньою. Перевірте офіційне джерело.';
    periodsEl.append(warning);
  }
  for (const period of periods) {
    const start = minutes(period.start);
    const end = minutes(period.end);
    const isNow = nowMinutes != null && nowMinutes >= start && nowMinutes < end;
    const item = document.createElement('div');
    item.className = `period ${period.status || 'unknown'}${isNow ? ' is-now' : ''}`;
    const timeWrap = document.createElement('div');
    if (isNow) {
      const tag = document.createElement('div');
      tag.className = 'now-tag';
      tag.textContent = 'Зараз';
      timeWrap.append(tag);
    }
    const time = document.createElement('div');
    time.className = 'period-time';
    time.textContent = `${period.start}–${period.end}`;
    timeWrap.append(time);
    const state = document.createElement('div');
    state.className = 'period-status';
    state.textContent = labels[period.status] || labels.unknown;
    item.append(timeWrap, state);
    periodsEl.append(item);
  }
}

async function loadSchedule() {
  refreshButton.disabled = true;
  refreshButton.textContent = 'Оновлюємо…';
  try {
    const response = await fetch(`schedule.json?t=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) throw new Error('schedule.json missing');
    const data = await response.json();
    if (!data || !data.periods) throw new Error('bad schedule');
    render(data);
  } catch (error) {
    statusCard.className = 'status-card unknown';
    statusTitle.textContent = 'Графік недоступний';
    statusUntil.hidden = true;
    statusDescription.textContent = 'Час відключень не вгадано. Спробуйте оновити або відкрийте офіційний сайт.';
    dayBar.innerHTML = '';
    periodsEl.innerHTML = '<div class="error">Актуальні дані не завантажилися. Натисніть «Оновити графік» або перевірте сайт Житомиробленерго.</div>';
    updatedEl.textContent = 'Остання спроба перевірки: ' + new Date().toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' });
  } finally {
    refreshButton.disabled = false;
    refreshButton.textContent = 'Оновити графік';
  }
}

refreshButton.addEventListener('click', loadSchedule);
loadSchedule();
setInterval(loadSchedule, 5 * 60 * 1000);