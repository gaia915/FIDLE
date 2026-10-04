// FIDLE - Free Idol Event Finder App Logic
(function () {
  'use strict';

  // 状態管理
  let allEvents = [];
  let filteredEvents = [];
  let favorites = new Set(JSON.parse(localStorage.getItem('fidle_favs') || '[]'));
  let currentView = 'list'; // 'list' | 'calendar'
  let currentArea = 'all';
  let currentCondition = 'all';
  let searchQuery = '';

  // カレンダー状態
  let calendarYear = new Date().getFullYear();
  let calendarMonth = new Date().getMonth(); // 0-indexed
  let selectedCalendarDate = null;

  // DOM要素
  const searchInput = document.getElementById('searchInput');
  const clearSearch = document.getElementById('clearSearch');
  const areaChips = document.getElementById('areaChips');
  const conditionChips = document.getElementById('conditionChips');
  const viewButtons = document.querySelectorAll('.view-btn');
  const listView = document.getElementById('listView');
  const calendarView = document.getElementById('calendarView');
  const eventsList = document.getElementById('eventsList');
  const totalCountEl = document.getElementById('totalEventCount');
  const lastUpdatedEl = document.getElementById('lastUpdated');
  const themeToggle = document.getElementById('themeToggle');
  const themeIcon = document.getElementById('themeIcon');
  const prevMonthBtn = document.getElementById('prevMonth');
  const nextMonthBtn = document.getElementById('nextMonth');
  const currentMonthYearEl = document.getElementById('currentMonthYear');
  const calendarDaysEl = document.getElementById('calendarDays');
  const calendarDayEvents = document.getElementById('calendarDayEvents');
  const selectedDayTitle = document.getElementById('selectedDayTitle');
  const selectedDayList = document.getElementById('selectedDayList');

  // 初期化
  async function init() {
    initTheme();
    setupEventListeners();
    await loadData();
  }

  // テーマ設定
  function initTheme() {
    const saved = localStorage.getItem('fidle_theme') || 'theme-dark';
    document.body.className = saved;
    updateThemeIcon(saved);
  }

  function toggleTheme() {
    const isDark = document.body.classList.contains('theme-dark');
    const newTheme = isDark ? 'theme-light' : 'theme-dark';
    document.body.className = newTheme;
    localStorage.setItem('fidle_theme', newTheme);
    updateThemeIcon(newTheme);
  }

  function updateThemeIcon(theme) {
    if (themeIcon) {
      themeIcon.className = theme === 'theme-dark' ? 'ph ph-sun' : 'ph ph-moon';
    }
  }

  // データロード
  async function loadData() {
    try {
      const resp = await fetch('data/events.json');
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      allEvents = data.events || [];

      // カウント・更新時刻
      if (totalCountEl) totalCountEl.textContent = `${allEvents.length} 件`;
      if (lastUpdatedEl && data.last_updated) {
        const dt = new Date(data.last_updated);
        lastUpdatedEl.textContent = `${dt.getMonth() + 1}/${dt.getDate()} ${String(dt.getHours()).padStart(2, '0')}:${String(dt.getMinutes()).padStart(2, '0')}`;
      }

      applyFilters();
    } catch (err) {
      console.error('データ取得失敗:', err);
      eventsList.innerHTML = `
        <div class="empty-state">
          <i class="ph ph-warning-circle" style="font-size: 2.5rem; color: #ef4444; margin-bottom: 12px;"></i>
          <p>イベントデータの読み込みに失敗しました。</p>
          <p style="font-size: 0.85rem; margin-top: 6px;">ローカル実行の場合は <code>python run_scraper.py</code> を実行してください。</p>
        </div>
      `;
    }
  }

  // フィルタ適用
  function applyFilters() {
    const todayStr = getTodayString();
    const weekendDates = getUpcomingWeekendStrings();

    filteredEvents = allEvents.filter(ev => {
      // 検索ワード
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const matchTitle = (ev.title || '').toLowerCase().includes(q);
        const matchArtist = (ev.artist || '').toLowerCase().includes(q);
        const matchVenue = (ev.venue || '').toLowerCase().includes(q);
        const matchDesc = (ev.description || '').toLowerCase().includes(q);
        if (!matchTitle && !matchArtist && !matchVenue && !matchDesc) return false;
      }

      // エリア
      if (currentArea !== 'all') {
        if (currentArea === '川崎') {
          if (!ev.area.includes('川崎') && !ev.venue.includes('川崎') && !ev.venue.includes('海老名')) return false;
        } else if (currentArea === 'その他') {
          if (['渋谷', '池袋', '新宿', '錦糸町'].includes(ev.area)) return false;
        } else {
          if (!ev.area.includes(currentArea) && !ev.venue.includes(currentArea)) return false;
        }
      }

      // 条件
      if (currentCondition === 'today') {
        if (ev.date !== todayStr) return false;
      } else if (currentCondition === 'weekend') {
        if (!weekendDates.includes(ev.date)) return false;
      } else if (currentCondition === 'favorites') {
        if (!favorites.has(ev.id)) return false;
      }

      return true;
    });

    renderView();
  }

  // 表示切替レンダリング
  function renderView() {
    if (currentView === 'list') {
      renderListView();
    } else {
      renderCalendarView();
    }
  }

  // リストビューのレンダリング
  function renderListView() {
    if (filteredEvents.length === 0) {
      eventsList.innerHTML = `
        <div class="empty-state">
          <i class="ph ph-calendar-x" style="font-size: 2.5rem; margin-bottom: 12px;"></i>
          <p>該当するイベントが見つかりませんでした。</p>
          <p style="font-size: 0.85rem; margin-top: 6px;">検索条件やエリアの絞り込みを変更してみてください。</p>
        </div>
      `;
      return;
    }

    // 日付ごとにグループ化
    const groups = {};
    for (const ev of filteredEvents) {
      if (!groups[ev.date]) groups[ev.date] = [];
      groups[ev.date].push(ev);
    }

    const todayStr = getTodayString();
    const tomorrowStr = getTomorrowString();

    let html = '';
    const sortedDates = Object.keys(groups).sort();

    for (const dateStr of sortedDates) {
      const items = groups[dateStr];
      const dObj = new Date(dateStr);
      const weekDays = ['日', '月', '火', '水', '木', '金', '土'];
      const dayOfWeek = weekDays[dObj.getDay()];
      const isWeekend = dObj.getDay() === 0 || dObj.getDay() === 6;

      let badgeHtml = '';
      if (dateStr === todayStr) {
        badgeHtml = '<span class="date-section-badge badge-today">本日開催！</span>';
      } else if (dateStr === tomorrowStr) {
        badgeHtml = '<span class="date-section-badge badge-tomorrow">明日開催</span>';
      } else if (isWeekend) {
        badgeHtml = '<span class="date-section-badge badge-weekend">週末</span>';
      }

      html += `
        <div class="date-section">
          <div class="date-section-header">
            <span>📅 ${formatDateWithDay(dateStr, dayOfWeek)}</span>
            ${badgeHtml}
          </div>
          <div class="events-group">
            ${items.map(ev => renderEventCard(ev)).join('')}
          </div>
        </div>
      `;
    }

    eventsList.innerHTML = html;
    attachCardListeners();
  }

  // イベントカードHTML生成
  function renderEventCard(ev) {
    const isFav = favorites.has(ev.id);
    const googleCalUrl = createGoogleCalendarLink(ev);
    const timeDisplay = ev.start_time ? `${ev.start_time} 開演` : '開演時間 未定';

    return `
      <div class="event-card" data-id="${ev.id}">
        <div class="event-header">
          <div class="event-tags">
            <span class="tag tag-free"><i class="ph ph-ticket"></i> ${escapeHtml(ev.free_type)}</span>
            <span class="tag tag-area"><i class="ph ph-map-pin"></i> ${escapeHtml(ev.area)}</span>
            <span class="tag tag-time"><i class="ph ph-clock"></i> ${timeDisplay}</span>
          </div>
          <button class="btn-fav ${isFav ? 'active' : ''}" data-id="${ev.id}" title="${isFav ? 'お気に入り解除' : 'お気に入り登録'}">
            <i class="${isFav ? 'ph-fill ph-star text-gold' : 'ph ph-star'}"></i>
          </button>
        </div>

        <h3 class="event-title">
          <a href="${escapeHtml(ev.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(ev.title)}</a>
        </h3>

        <div class="event-meta">
          <div class="meta-item">
            <i class="ph ph-buildings"></i>
            <span>${escapeHtml(ev.venue)}</span>
          </div>
          <div class="meta-item">
            <i class="ph ph-users"></i>
            <span>出演: ${escapeHtml(ev.artist)}</span>
          </div>
        </div>

        ${ev.description ? `<div class="event-desc">${escapeHtml(ev.description)}</div>` : ''}

        <div class="event-actions">
          <a href="${escapeHtml(ev.url)}" target="_blank" rel="noopener noreferrer" class="btn-detail">
            <i class="ph ph-arrow-square-out"></i> 公式詳細を見る
          </a>
          <a href="${googleCalUrl}" target="_blank" rel="noopener noreferrer" class="btn-cal-add" title="Googleカレンダーに追加">
            <i class="ph ph-calendar-plus"></i> Googleカレンダーに追加
          </a>
        </div>
      </div>
    `;
  }

  // カード内イベントハンドラ（お気に入りボタン等）
  function attachCardListeners() {
    document.querySelectorAll('.btn-fav').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-id');
        toggleFavorite(id);
      });
    });
  }

  // お気に入りトグル
  function toggleFavorite(id) {
    if (favorites.has(id)) {
      favorites.delete(id);
    } else {
      favorites.add(id);
    }
    localStorage.setItem('fidle_favs', JSON.stringify([...favorites]));
    if (currentCondition === 'favorites') {
      applyFilters();
    } else {
      renderView();
    }
  }

  // カレンダー描画
  function renderCalendarView() {
    const year = calendarYear;
    const month = calendarMonth;
    currentMonthYearEl.textContent = `${year}年 ${month + 1}月`;

    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const prevLastDay = new Date(year, month, 0);

    const startDayOfWeek = firstDay.getDay(); // 0(日) - 6(土)
    const daysInMonth = lastDay.getDate();
    const daysInPrevMonth = prevLastDay.getDate();

    // イベントの日付マッピング
    const eventCountByDate = {};
    for (const ev of filteredEvents) {
      eventCountByDate[ev.date] = (eventCountByDate[ev.date] || 0) + 1;
    }

    const todayStr = getTodayString();
    let cellsHtml = '';

    // 前月の日付
    for (let i = startDayOfWeek - 1; i >= 0; i--) {
      const d = daysInPrevMonth - i;
      cellsHtml += `<div class="cal-day-cell other-month"><span class="cal-day-num">${d}</span></div>`;
    }

    // 当月の日付
    for (let day = 1; day <= daysInMonth; day++) {
      const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const isToday = dateStr === todayStr;
      const isSelected = dateStr === selectedCalendarDate;
      const count = eventCountByDate[dateStr] || 0;

      let badgeContent = '';
      if (count > 0) {
        badgeContent = `<div class="cal-badges"><span class="cal-event-dot">🎤 ${count}件</span></div>`;
      }

      cellsHtml += `
        <div class="cal-day-cell ${isToday ? 'today' : ''} ${isSelected ? 'selected' : ''}" data-date="${dateStr}">
          <span class="cal-day-num">${day}</span>
          ${badgeContent}
        </div>
      `;
    }

    calendarDaysEl.innerHTML = cellsHtml;

    // セルクリック
    calendarDaysEl.querySelectorAll('.cal-day-cell[data-date]').forEach(cell => {
      cell.addEventListener('click', () => {
        const d = cell.getAttribute('data-date');
        selectCalendarDate(d);
      });
    });

    if (selectedCalendarDate) {
      showSelectedCalendarDateEvents(selectedCalendarDate);
    } else {
      calendarDayEvents.style.display = 'none';
    }
  }

  function selectCalendarDate(dateStr) {
    selectedCalendarDate = dateStr;
    renderCalendarView();
    showSelectedCalendarDateEvents(dateStr);
  }

  function showSelectedCalendarDateEvents(dateStr) {
    const dayEvents = filteredEvents.filter(e => e.date === dateStr);
    calendarDayEvents.style.display = 'block';
    selectedDayTitle.textContent = `📅 ${dateStr} の開催イベント (${dayEvents.length}件)`;

    if (dayEvents.length === 0) {
      selectedDayList.innerHTML = `<p style="color: var(--text-muted); font-size: 0.9rem; padding: 12px 0;">この日の該当イベントはありません。</p>`;
    } else {
      selectedDayList.innerHTML = dayEvents.map(e => renderEventCard(e)).join('');
      attachCardListeners();
    }
  }

  // Googleカレンダー登録リンク生成
  function createGoogleCalendarLink(ev) {
    const title = encodeURIComponent(`【${ev.free_type}】${ev.title}`);
    const details = encodeURIComponent(`出演: ${ev.artist}\n種別: ${ev.free_type}\n会場: ${ev.venue}\nURL: ${ev.url}\n\n${ev.description}`);
    const location = encodeURIComponent(ev.venue);

    let dateParam = '';
    const dateClean = ev.date.replace(/-/g, '');
    if (ev.start_time && ev.start_time.includes(':')) {
      const timeClean = ev.start_time.replace(/:/g, '') + '00';
      // デフォルト1時間イベント
      const [h, m] = ev.start_time.split(':').map(Number);
      const endH = String((h + 1) % 24).padStart(2, '0');
      const endTimeClean = `${endH}${String(m).padStart(2, '0')}00`;
      dateParam = `${dateClean}T${timeClean}/${dateClean}T${endTimeClean}`;
    } else {
      dateParam = `${dateClean}/${dateClean}`;
    }

    return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${title}&dates=${dateParam}&details=${details}&location=${location}`;
  }

  // ユーティリティ
  function getTodayString() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }

  function getTomorrowString() {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }

  function getUpcomingWeekendStrings() {
    const res = [];
    const d = new Date();
    // 今週〜来週の日付で土日を探す
    for (let i = 0; i < 7; i++) {
      const cur = new Date();
      cur.setDate(d.getDate() + i);
      if (cur.getDay() === 0 || cur.getDay() === 6) {
        res.push(`${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, '0')}-${String(cur.getDate()).padStart(2, '0')}`);
      }
    }
    return res;
  }

  function formatDateWithDay(dateStr, dayOfWeek) {
    const parts = dateStr.split('-');
    return `${parts[0]}年${parseInt(parts[1], 10)}月${parseInt(parts[2], 10)}日 (${dayOfWeek})`;
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // イベントリスナー設定
  function setupEventListeners() {
    // 検索入力
    searchInput.addEventListener('input', (e) => {
      searchQuery = e.target.value.trim();
      clearSearch.style.display = searchQuery ? 'block' : 'none';
      applyFilters();
    });

    clearSearch.addEventListener('click', () => {
      searchInput.value = '';
      searchQuery = '';
      clearSearch.style.display = 'none';
      applyFilters();
    });

    // エリア切り替え
    areaChips.querySelectorAll('.chip').forEach(chip => {
      chip.addEventListener('click', () => {
        areaChips.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        currentArea = chip.getAttribute('data-area');
        applyFilters();
      });
    });

    // 条件切り替え
    conditionChips.querySelectorAll('.chip').forEach(chip => {
      chip.addEventListener('click', () => {
        conditionChips.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        currentCondition = chip.getAttribute('data-filter');
        applyFilters();
      });
    });

    // 表示切替 (リスト / カレンダー)
    viewButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        viewButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentView = btn.getAttribute('data-view');
        if (currentView === 'list') {
          listView.style.display = 'block';
          calendarView.style.display = 'none';
        } else {
          listView.style.display = 'none';
          calendarView.style.display = 'block';
        }
        renderView();
      });
    });

    // カレンダー月送り
    prevMonthBtn.addEventListener('click', () => {
      calendarMonth--;
      if (calendarMonth < 0) {
        calendarMonth = 11;
        calendarYear--;
      }
      renderCalendarView();
    });

    nextMonthBtn.addEventListener('click', () => {
      calendarMonth++;
      if (calendarMonth > 11) {
        calendarMonth = 0;
        calendarYear++;
      }
      renderCalendarView();
    });

    // テーマ切り替え
    themeToggle.addEventListener('click', toggleTheme);
  }

  // DOMロード時に開始
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
