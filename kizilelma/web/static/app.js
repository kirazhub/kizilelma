/* ==========================================================================
   KIZILELMA TERMINAL — Canlı veri yükleyici
   ==========================================================================
   Akış:
     1. updateClock()      → saniye saniye IST saati
     2. loadSnapshot()     → /api/snapshot'tan tüm piyasa verisi
     3. renderAll()        → 4 paneli doldur (funds, top, repo, log)
     4. Keyboard shortcuts → 1-6 panel odak, / arama, r refresh
   ========================================================================== */

'use strict';

const state = {
  snapshot: null,
  fetchedAt: null,
  cached: false,
  source: null,          // "live" | "db" | "error"
  isHistorical: false,   // DB'den mi geldi?
  dataTimestamp: null,   // Verinin orijinal toplandığı an (snapshot.timestamp)
  liveError: null,       // Canlı hata mesajı (varsa)
  lastAttempt: null,
  error: null,
  activePanel: null,
  logs: [],
};

// ----------------------------------------------------------------------------
// Yardımcı fonksiyonlar
// ----------------------------------------------------------------------------

function $(sel, root = document) { return root.querySelector(sel); }
function $$(sel, root = document) { return Array.from(root.querySelectorAll(sel)); }

function num(v) {
  if (v === null || v === undefined || v === '') return null;
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : null;
}

function fmtPct(v, digits = 2) {
  const n = num(v);
  if (n === null) return '<span class="neutral">—</span>';
  const s = (n >= 0 ? '+' : '') + n.toFixed(digits) + '%';
  const cls = n > 0 ? 'positive' : n < 0 ? 'negative' : 'neutral';
  return `<span class="${cls}">${s}</span>`;
}

function fmtNum(v, digits = 4) {
  const n = num(v);
  if (n === null) return '—';
  return n.toFixed(digits);
}

function fmtRate(v, digits = 2) {
  const n = num(v);
  if (n === null) return '—';
  return n.toFixed(digits);
}

function truncate(s, n) {
  if (!s) return '';
  const str = String(s);
  return str.length > n ? str.slice(0, n - 1) + '…' : str;
}

function escapeHtml(s) {
  if (s === null || s === undefined) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function colorClass(v) {
  const n = num(v);
  if (n === null) return 'neutral';
  return n > 0 ? 'positive' : n < 0 ? 'negative' : 'neutral';
}

/**
 * Bir fonun "aktif" sayılıp gösterilmeye değer olup olmadığını döner.
 * Backend'deki filter_active_funds ile aynı mantık:
 *   - price > 0
 *   - 1A veya 1Y getirilerinden en az biri 0'dan farklı
 *   - 1Y varsa mutlak değeri en az %0.5 (yeni kurulan / durağan fonları eler)
 */
function isFundActive(f) {
  if (!f) return false;
  const price = num(f.price);
  if (price === null || price <= 0) return false;

  const r1m = num(f.return_1m);
  const r1y = num(f.return_1y);

  const has1m = r1m !== null && r1m !== 0;
  const has1y = r1y !== null && r1y !== 0;

  if (!has1m && !has1y) return false;
  if (has1y && Math.abs(r1y) < 0.5) return false;

  return true;
}

// ----------------------------------------------------------------------------
// Saat — saniye saniye güncellenir (İstanbul saati)
// ----------------------------------------------------------------------------

function updateClock() {
  try {
    const now = new Date();
    const ist = now.toLocaleTimeString('tr-TR', {
      timeZone: 'Europe/Istanbul',
      hour12: false,
    });
    $('#clock').textContent = ist;
  } catch (e) {
    // Fallback
    $('#clock').textContent = new Date().toLocaleTimeString('tr-TR', { hour12: false });
  }
}

// ----------------------------------------------------------------------------
// Canlı log
// ----------------------------------------------------------------------------

function log(level, msg) {
  const time = new Date().toLocaleTimeString('tr-TR', { hour12: false });
  state.logs.unshift({ time, level, msg });
  if (state.logs.length > 50) state.logs.pop();
  renderLog();
}

function renderLog() {
  const feed = $('#log-feed');
  if (!feed) return;
  feed.innerHTML = state.logs
    .slice(0, 30)
    .map(
      (l) => `
    <li class="log-item">
      <span class="log-time">${l.time}</span>
      <span class="log-level ${l.level}">${l.level.toUpperCase()}</span>
      <span class="log-msg">${escapeHtml(l.msg)}</span>
    </li>`,
    )
    .join('');
}

// ----------------------------------------------------------------------------
// Veri yükleme — /api/snapshot
// ----------------------------------------------------------------------------

async function loadSnapshot({ silent = false } = {}) {
  if (!silent) log('info', 'Snapshot isteği gönderiliyor…');
  state.lastAttempt = new Date();

  try {
    const res = await fetch('/api/snapshot');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const payload = await res.json();

    if (payload.error) throw new Error(payload.error);

    state.snapshot = payload.data;
    state.cached = !!payload.cached;
    state.fetchedAt = payload.fetched_at ? new Date(payload.fetched_at) : new Date();
    state.source = payload.source || 'unknown';
    state.liveError = payload.live_error || null;
    state.isHistorical = !!(payload.data && payload.data.is_historical);
    // Verinin orijinal zamanı (snapshot.timestamp) — DB'den geldiyse eski olabilir
    state.dataTimestamp = payload.data && payload.data.timestamp
      ? new Date(payload.data.timestamp)
      : state.fetchedAt;
    state.error = null;

    const fn = state.snapshot?.funds?.length || 0;
    const srcLabel = state.source === 'db'
      ? 'ARŞİV(DB)'
      : state.cached ? 'cache' : 'canlı';
    log('ok', `Snapshot alındı: ${fn} fon · ${srcLabel}`);

    if (state.source === 'db' && state.liveError) {
      log('err', `Canlı veri alınamadı, arşivden dönüldü: ${state.liveError}`);
    }

    renderAll();
    updateFreshnessBanner();
    flashAll();

    // Snapshot hazır — AI yorumu da yüklensin (bağımsız, hata kendi içinde yutulur)
    loadAICommentary();
  } catch (e) {
    state.error = e.message || String(e);
    state.source = 'error';
    log('err', `Snapshot hatası: ${state.error}`);
    setStatus('ERROR', false);
    updateFreshnessBanner();
    showErrors();
  }
}

// ----------------------------------------------------------------------------
// AI COMMENTARY — Claude ile üretilen 2-3 cümlelik piyasa özeti
// ----------------------------------------------------------------------------

/**
 * AI yorumunu /api/ai_commentary'den yükler ve banner'a yazar.
 * loadSnapshot başarılı olduktan sonra çağrılır. Hata durumunda
 * sessizce fallback metni gösterir — kullanıcı asla "bozuk" ekran görmez.
 */
async function loadAICommentary() {
  const textEl = document.getElementById('ai-commentary-text');
  const metaEl = document.getElementById('ai-commentary-meta');
  const banner = document.getElementById('ai-commentary');

  if (!textEl) return; // Banner sayfada yoksa sessizce çık

  // Loading state
  textEl.textContent = 'Günün analizi hazırlanıyor…';
  textEl.classList.add('loading');
  if (metaEl) metaEl.textContent = '';
  if (banner) banner.classList.remove('error');

  try {
    const res = await fetch('/api/ai_commentary');
    const data = await res.json();

    textEl.classList.remove('loading');

    if (data && data.commentary) {
      textEl.textContent = data.commentary;

      if (metaEl) {
        const gen = data.generated_at ? new Date(data.generated_at) : null;
        const ageMin = gen ? Math.floor((Date.now() - gen.getTime()) / 60000) : 0;
        let ageLabel;
        if (ageMin < 1) ageLabel = 'ŞİMDİ';
        else if (ageMin < 60) ageLabel = `${ageMin}DK ÖNCE`;
        else ageLabel = `${Math.floor(ageMin / 60)}S ÖNCE`;
        metaEl.textContent = data.cached ? `${ageLabel} · CACHED` : ageLabel;
      }
      log('ok', 'AI yorumu yüklendi');
    } else {
      // AI key yok veya üretim hatası — zarif fallback
      const errMsg = (data && data.error) || '';
      if (errMsg === 'AI key yok') {
        textEl.textContent = 'AI analiz servisi şu anda pasif.';
      } else if (errMsg) {
        textEl.textContent = 'Veri analizi şu an kullanılamıyor.';
      } else {
        textEl.textContent = 'AI yorumu mevcut değil.';
      }
      if (banner) banner.classList.add('error');
      if (metaEl) metaEl.textContent = 'OFFLINE';
    }
  } catch (e) {
    console.error('AI yorumu yüklenemedi:', e);
    textEl.classList.remove('loading');
    textEl.textContent = 'AI analizi alınamadı.';
    if (banner) banner.classList.add('error');
    if (metaEl) metaEl.textContent = 'ERROR';
  }
}

// ----------------------------------------------------------------------------
// DATA FRESHNESS BANNER — verinin ne zaman alındığını ve kaynağını gösterir
// ----------------------------------------------------------------------------

function updateFreshnessBanner() {
  // Banner yoksa oluştur, header'ın hemen altına koy
  let banner = document.getElementById('freshness-banner');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'freshness-banner';
    const header = document.querySelector('header');
    if (header && header.parentNode) {
      header.insertAdjacentElement('afterend', banner);
    } else {
      document.body.insertBefore(banner, document.body.firstChild);
    }
  }

  // Hata durumu — canlı da yok DB de yok
  if (state.source === 'error') {
    banner.className = 'freshness error';
    banner.innerHTML = `
      <span class="freshness-dot"></span>
      <strong>VERİ ÇEKİLEMEDİ</strong>
      <span class="sep">│</span>
      <span>${escapeHtml(state.error || 'bilinmeyen hata')}</span>
    `;
    return;
  }

  if (!state.dataTimestamp) {
    banner.className = 'freshness unknown';
    banner.innerHTML = '<span class="freshness-dot"></span> VERİ ZAMANI BİLİNMİYOR';
    return;
  }

  const dataTime = state.dataTimestamp;
  const now = new Date();
  const ageMs = now.getTime() - dataTime.getTime();
  const ageHours = ageMs / 1000 / 3600;

  // Tazelik sınıfı: yeşil <1h, amber <24h, kırmızı >24h
  let freshness, ageLabel;
  if (ageHours < 1) {
    freshness = 'fresh';
    ageLabel = '● CANLI';
  } else if (ageHours < 24) {
    freshness = 'recent';
    ageLabel = `◐ ${ageHours.toFixed(1)} SAAT ÖNCE`;
  } else {
    const days = Math.floor(ageHours / 24);
    freshness = 'stale';
    ageLabel = `◯ ${days} GÜN ÖNCE`;
  }

  // Tarih formatı (İstanbul saati)
  const formatted = dataTime.toLocaleString('tr-TR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
    timeZone: 'Europe/Istanbul',
    hour12: false,
  });

  const sourceLabel = state.source === 'db' ? 'ARŞİV (DB)' : 'CANLI';

  banner.className = `freshness ${freshness}`;
  banner.innerHTML = `
    <span class="freshness-dot"></span>
    <strong>DATA AS OF:</strong> ${escapeHtml(formatted)}
    <span class="sep">│</span>
    <span>KAYNAK: <strong>${sourceLabel}</strong></span>
    <span class="sep">│</span>
    <span>${ageLabel}</span>
    ${state.liveError ? `<span class="sep">│</span><span class="freshness-warn">CANLI HATA: ${escapeHtml(truncate(state.liveError, 60))}</span>` : ''}
  `;
}

function flashAll() {
  $$('.panel').forEach((p) => {
    p.classList.remove('flash');
    // reflow
    void p.offsetWidth;
    p.classList.add('flash');
  });
}

function showErrors() {
  const msg = `<div class="error-box">BAĞLANTI HATASI<br />${escapeHtml(state.error || '')}</div>`;
  ['funds', 'repo', 'top'].forEach((k) => {
    const el = $(`#panel-${k}-body`);
    if (el && !state.snapshot) el.innerHTML = msg;
  });
}

// ----------------------------------------------------------------------------
// Status / header güncellemeleri
// ----------------------------------------------------------------------------

function setStatus(text, live = true) {
  $('#status-text').textContent = text;
  $('#sb-status').textContent = text;
  $('#sb-status').className = 'status-val ' + (live ? 'live' : 'stale');
  const dot = $('.status-dot');
  if (dot) dot.classList.toggle('error', !live);
}

function updateStatusBar() {
  const fn = state.snapshot?.funds?.length || 0;
  const rn = state.snapshot?.repo_rates?.length || 0;

  $('#sb-data').textContent = `${fn} funds · ${rn} rates`;

  if (state.fetchedAt) {
    $('#sb-update').textContent = state.fetchedAt.toLocaleTimeString('tr-TR', {
      hour12: false,
    });
  }

  $('#sb-cache').textContent = state.cached ? 'HIT' : 'FRESH';
  $('#sb-cache').className = 'status-val ' + (state.cached ? 'stale' : 'fresh');

  // Kaynak türüne göre üst sağdaki status etiketi
  if (state.source === 'db') {
    setStatus('ARCHIVE', false);  // Kırmızı nokta: canlı değil
  } else {
    setStatus('LIVE', true);
  }
}

function updateTicker() {
  const s = state.snapshot;
  if (!s) return;

  // TCMB politika oranı
  const policy = (s.repo_rates || []).find((r) => /politika/i.test(r.type || ''))
    || (s.repo_rates || [])[0];
  $('#ticker-tcmb').textContent = policy ? '%' + fmtRate(policy.rate) : '—';

  // Repo ortalaması
  const repos = (s.repo_rates || []).filter((r) => /repo/i.test(r.type || '')).slice(0, 3);
  if (repos.length) {
    const avg = repos.reduce((a, r) => a + (num(r.rate) || 0), 0) / repos.length;
    $('#ticker-repo').textContent = '%' + avg.toFixed(2);
  }

  $('#ticker-funds').textContent = String(s.funds?.length || 0);

  // En iyi 1Y
  const best = [...(s.funds || [])]
    .filter(isFundActive)
    .filter((f) => num(f.return_1y) !== null)
    .sort((a, b) => (num(b.return_1y) || 0) - (num(a.return_1y) || 0))[0];
  if (best) {
    const r = num(best.return_1y);
    const el = $('#ticker-top');
    el.textContent = `${best.code} ${r >= 0 ? '+' : ''}${r.toFixed(1)}%`;
    el.className = 'ticker-value ' + (r > 0 ? 'positive' : 'negative');
  }
}

// ----------------------------------------------------------------------------
// PANEL 01 — TEFAS Fonları (tüm kategoriler, panel aşağı kadar dolu)
// Sol kolonun tamamını kaplar; kategorilere ayrılmış tablo.
// ----------------------------------------------------------------------------

function renderFunds() {
  const root = $('#panel-funds-body');
  const funds = state.snapshot?.funds || [];

  // Aktif fon filtresi: ölü/yeni kurulan/fiyatsız fonları ele
  const valid = funds.filter(isFundActive);

  if (!valid.length) {
    root.innerHTML = '<p class="empty">FON VERİSİ YOK</p>';
    return;
  }

  // Kategori tanımları — filtre fonksiyonu + görsel bilgi
  const categories = [
    {
      name: 'Para Piyasası Fonları',
      emoji: '📊',
      match: (f) => {
        const c = (f.category || '').toLowerCase();
        return c.includes('para piy') || c.includes('likit') || c.includes('kısa vade');
      },
      limit: 10,
    },
    {
      name: 'Hisse Senedi Fonları',
      emoji: '📈',
      match: (f) => {
        const c = (f.category || '').toLowerCase();
        return c.includes('hisse');
      },
      limit: 10,
    },
    {
      name: 'Karma / Değişken Fonlar',
      emoji: '🎯',
      match: (f) => {
        const c = (f.category || '').toLowerCase();
        return (
          c.includes('karma') ||
          c.includes('değişken') ||
          c.includes('degisken') ||
          c.includes('fon sepeti')
        );
      },
      limit: 10,
    },
    {
      name: 'Serbest Fonlar',
      emoji: '💎',
      match: (f) => {
        const c = (f.category || '').toLowerCase();
        return c.includes('serbest') || f.is_qualified_investor === true;
      },
      limit: 10,
    },
    {
      name: 'Katılım Fonları',
      emoji: '🕌',
      match: (f) => {
        const c = (f.category || '').toLowerCase();
        return c.includes('katılım') || c.includes('katilim');
      },
      limit: 10,
    },
    {
      name: 'Borçlanma / Tahvil Fonları',
      emoji: '📜',
      match: (f) => {
        const c = (f.category || '').toLowerCase();
        return c.includes('borçlan') || c.includes('borclan') || c.includes('tahvil');
      },
      limit: 10,
    },
    {
      name: 'Altın & Kıymetli Madenler',
      emoji: '🥇',
      match: (f) => {
        const c = (f.category || '').toLowerCase();
        return c.includes('altın') || c.includes('altin') || c.includes('kıymetli') || c.includes('kiymetli');
      },
      limit: 10,
    },
    {
      name: 'Endeks & Standart Fonlar',
      emoji: '📐',
      match: (f) => {
        const c = (f.category || '').toLowerCase();
        return c.includes('endeks') || c === 'standart fon' || c.includes('hedef') || c.includes('yaşam');
      },
      limit: 10,
    },
    {
      name: 'Diğer Yatırım Fonları',
      emoji: '🗂️',
      // Yukarıdaki hiçbir kategoriye girmeyen her şey (GYF, Girişim, BES vb.)
      match: () => true,
      limit: 10,
    },
  ];

  // Bir fon yalnızca ilk eşleşen kategoriye gitsin (kopyalama olmasın)
  const used = new Set();
  const buckets = categories.map((cat) => {
    const list = valid
      .filter((f) => {
        if (used.has(f.code)) return false;
        if (!cat.match(f)) return false;
        used.add(f.code);
        return true;
      })
      .sort((a, b) => (num(b.return_1y) || 0) - (num(a.return_1y) || 0))
      .slice(0, cat.limit);
    return { ...cat, list };
  });

  // Boş kategorileri at
  const filled = buckets.filter((b) => b.list.length > 0);

  if (!filled.length) {
    root.innerHTML = '<p class="empty">KATEGORİ EŞLEŞMESİ YOK</p>';
    return;
  }

  const tableFor = (list) => `
    <table class="data-table">
      <thead>
        <tr>
          <th>KOD</th>
          <th>AD</th>
          <th class="num">1G</th>
          <th class="num">1A</th>
          <th class="num">1Y</th>
          <th class="num">FİYAT</th>
        </tr>
      </thead>
      <tbody>
        ${list
          .map(
            (f) => `
          <tr>
            <td class="code">${escapeHtml(f.code)}</td>
            <td class="name">${escapeHtml(truncate(f.name, 50))}</td>
            <td class="num ${colorClass(f.return_1d)}" data-label="1G">${fmtPct(f.return_1d)}</td>
            <td class="num ${colorClass(f.return_1m)}" data-label="1A">${fmtPct(f.return_1m)}</td>
            <td class="num ${colorClass(f.return_1y)}" data-label="1Y">${fmtPct(f.return_1y)}</td>
            <td class="num" data-label="FİYAT">${fmtNum(f.price, 4)}</td>
          </tr>`,
          )
          .join('')}
      </tbody>
    </table>`;

  root.innerHTML = filled
    .map(
      (cat) => `
    <div class="fund-category">
      <h3 class="fund-category-title">
        <span class="cat-emoji">${cat.emoji}</span>
        <span>${escapeHtml(cat.name.toUpperCase())}</span>
        <span class="cat-count">TOP ${cat.list.length}</span>
      </h3>
      ${tableFor(cat.list)}
    </div>`,
    )
    .join('');
}

// ----------------------------------------------------------------------------
// PANEL 03 — TCMB Faiz (büyük rakamlar)
// ----------------------------------------------------------------------------

function renderRepo() {
  const root = $('#panel-repo-body');
  const rates = state.snapshot?.repo_rates || [];

  if (!rates.length) {
    root.innerHTML = '<p class="empty">TCMB ORAN VERİSİ YOK</p>';
    return;
  }

  // Öncelik sırası
  const typeOrder = { 'politika': 1, 'repo': 2, 'ters_repo': 3, 'ters repo': 3 };
  const sorted = [...rates].sort((a, b) => {
    const aKey = (a.type || '').toLowerCase();
    const bKey = (b.type || '').toLowerCase();
    return (typeOrder[aKey] || 99) - (typeOrder[bKey] || 99);
  });

  const typeLabel = (t) => {
    const k = (t || '').toLowerCase();
    if (k.includes('politika')) return 'POLİTİKA FAİZİ';
    if (k === 'repo') return 'REPO';
    if (k.includes('ters')) return 'TERS REPO';
    return (t || '—').toUpperCase();
  };

  root.innerHTML = `
    <div class="rate-list">
      ${sorted
        .slice(0, 8)
        .map(
          (r) => `
        <div class="rate-card">
          <div>
            <div class="rate-card-label">${escapeHtml(typeLabel(r.type))}</div>
            <div class="rate-card-sub">${escapeHtml(r.maturity || '')} · ${escapeHtml(r.date || '')}</div>
          </div>
          <div class="rate-card-value">
            ${fmtRate(r.rate)}<span class="unit">%</span>
          </div>
        </div>`,
        )
        .join('')}
    </div>
  `;
}

// ----------------------------------------------------------------------------
// PANEL 02 — Günün Zirveleri (tüm fonlar 1Y bazında, TOP 25)
// ----------------------------------------------------------------------------

function renderTopPicks() {
  const root = $('#panel-top-body');
  const funds = state.snapshot?.funds || [];

  const top = [...funds]
    .filter(isFundActive)
    .filter((f) => num(f.return_1y) !== null)
    .sort((a, b) => (num(b.return_1y) || 0) - (num(a.return_1y) || 0))
    .slice(0, 25);

  if (!top.length) {
    root.innerHTML = '<p class="empty">FON VERİSİ YOK</p>';
    return;
  }

  root.innerHTML = top
    .map(
      (f, i) => `
    <div class="top-pick">
      <div class="top-pick-rank">${String(i + 1).padStart(2, '0')}</div>
      <div class="top-pick-info">
        <div class="top-pick-code">${escapeHtml(f.code)}</div>
        <div class="top-pick-name">${escapeHtml(truncate(f.name, 60))}</div>
      </div>
      <div>
        <div class="top-pick-return ${colorClass(f.return_1y)}">
          ${num(f.return_1y) >= 0 ? '+' : ''}${num(f.return_1y).toFixed(1)}%
        </div>
        <div class="top-pick-return-sub">1Y</div>
      </div>
    </div>`,
    )
    .join('');
}

// ----------------------------------------------------------------------------
// Ana render — tümü
// ----------------------------------------------------------------------------

function renderAll() {
  try { renderFunds();     } catch (e) { console.error('funds:', e);     log('err', 'Fon render hatası'); }
  try { renderRepo();      } catch (e) { console.error('repo:', e);      log('err', 'Repo render hatası'); }
  try { renderTopPicks();  } catch (e) { console.error('top:', e);       log('err', 'Top picks render hatası'); }
  updateTicker();
  updateStatusBar();
}

// ----------------------------------------------------------------------------
// Keyboard shortcuts
// ----------------------------------------------------------------------------

function focusPanel(num) {
  $$('.panel').forEach((p) => p.classList.remove('active'));
  const panel = $(`.panel[data-key="${num}"]`);
  if (panel) {
    panel.classList.add('active');
    state.activePanel = num;
    log('info', `Panel ${num} odaklandı`);
  }
}

function openCommand() {
  const overlay = $('#command-overlay');
  overlay.hidden = false;
  $('#command-input').value = '';
  $('#command-results').innerHTML = '';
  $('#command-input').focus();
}

function closeCommand() {
  $('#command-overlay').hidden = true;
  $('#command-input').value = '';
}

function searchFunds(query) {
  const q = (query || '').trim().toLowerCase();
  if (!q || !state.snapshot?.funds) {
    $('#command-results').innerHTML = '';
    return;
  }
  const matches = state.snapshot.funds
    .filter(isFundActive)
    .filter(
      (f) =>
        (f.code || '').toLowerCase().includes(q) ||
        (f.name || '').toLowerCase().includes(q),
    )
    .slice(0, 20);

  $('#command-results').innerHTML = matches
    .map(
      (f) => `
    <div class="command-result">
      <span class="code">${escapeHtml(f.code)}</span>
      <span class="name">${escapeHtml(truncate(f.name, 50))}</span>
      <span class="${colorClass(f.return_1y)}">${fmtPct(f.return_1y, 1)}</span>
    </div>`,
    )
    .join('');
}

function setupKeyboard() {
  document.addEventListener('keydown', (e) => {
    // Input alanlarında klavye kısayollarını çalıştırma
    // INPUT, TEXTAREA, SELECT veya contenteditable
    const ae = document.activeElement;
    const isInput = ae && (
      ae.tagName === 'INPUT' ||
      ae.tagName === 'TEXTAREA' ||
      ae.tagName === 'SELECT' ||
      ae.isContentEditable
    );
    const cmdOpen = !$('#command-overlay').hidden;
    // Chat açıksa kısayolları devre dışı bırak (yazarken karışmasın)
    const chatOpen = chatState && chatState.open;

    // ESC — komut kutusu kapat / panel seçimi kaldır
    if (e.key === 'Escape') {
      if (cmdOpen) {
        closeCommand();
        e.preventDefault();
      } else {
        $$('.panel').forEach((p) => p.classList.remove('active'));
        state.activePanel = null;
      }
      return;
    }

    if (isInput) return; // input alanlarında kısayolları yakalama
    if (chatOpen) return; // chat açıkken kısayolları devre dışı bırak

    // / — arama
    if (e.key === '/') {
      e.preventDefault();
      openCommand();
      return;
    }

    // r — refresh
    if (e.key === 'r' || e.key === 'R') {
      e.preventDefault();
      log('info', 'Manuel refresh');
      loadSnapshot();
      return;
    }

    // 1-6 panel odak
    if (['1', '2', '3', '4', '5', '6'].includes(e.key)) {
      focusPanel(parseInt(e.key, 10));
      e.preventDefault();
    }
  });

  // Command input
  const inp = $('#command-input');
  inp.addEventListener('input', (e) => searchFunds(e.target.value));
  inp.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeCommand();
  });

  // Overlay dışına tıklayınca kapat
  $('#command-overlay').addEventListener('click', (e) => {
    if (e.target.id === 'command-overlay') closeCommand();
  });
}

// ----------------------------------------------------------------------------
// Başlangıç
// ----------------------------------------------------------------------------

function boot() {
  log('info', 'Terminal başlatılıyor…');

  // Saati hemen başlat, her saniye güncelle
  updateClock();
  setInterval(updateClock, 1000);

  // Keyboard
  setupKeyboard();

  // İlk veri çağrısı
  loadSnapshot();

  // 5 dakikada bir auto-refresh
  setInterval(() => {
    log('info', 'Otomatik yenileme başlıyor…');
    loadSnapshot({ silent: true });
  }, 5 * 60 * 1000);

  log('ok', 'Sistem hazır. Klavye: 1-6 panel, / arama, R yenile.');
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}

/* ========================================
   AI CHAT WIDGET — Claude Haiku SSE Client
   ======================================== */

const chatState = {
  open: false,
  sending: false,
  history: [],  // [{role, content}]
  currentAiMessage: null,
};

function initChat() {
  const toggle = document.getElementById('chat-toggle');
  const close = document.getElementById('chat-close');
  const panel = document.getElementById('chat-panel');
  const input = document.getElementById('chat-input');
  const send = document.getElementById('chat-send');
  const suggestions = document.querySelectorAll('.chat-suggestion-btn');

  if (!toggle || !panel) return;

  // Toggle açma/kapama
  toggle.addEventListener('click', () => openChat());
  close.addEventListener('click', () => closeChat());

  // Send button
  send.addEventListener('click', () => handleSend());

  // Enter ile gönder (Shift+Enter yeni satır)
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  // Otomatik textarea resize
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  });

  // Örnek sorular
  suggestions.forEach((btn) => {
    btn.addEventListener('click', () => {
      const question = btn.dataset.question;
      input.value = question;
      handleSend();
    });
  });

  // ESC ile kapat
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && chatState.open) {
      // Başka bir overlay yoksa kapat
      const cmdOverlay = document.getElementById('command-overlay');
      if (!cmdOverlay || cmdOverlay.hidden) {
        closeChat();
      }
    }
  });

  // Restore localStorage history
  try {
    const saved = localStorage.getItem('chat_history');
    if (saved) {
      const history = JSON.parse(saved);
      if (Array.isArray(history) && history.length > 0) {
        chatState.history = history.slice(-20);
      }
    }
  } catch (e) {
    console.warn('Chat history restore failed:', e);
  }
}

function openChat() {
  const panel = document.getElementById('chat-panel');
  const toggle = document.getElementById('chat-toggle');
  const input = document.getElementById('chat-input');

  panel.hidden = false;
  toggle.hidden = true;
  chatState.open = true;

  setTimeout(() => input?.focus(), 100);
}

function closeChat() {
  const panel = document.getElementById('chat-panel');
  const toggle = document.getElementById('chat-toggle');

  panel.hidden = true;
  toggle.hidden = false;
  chatState.open = false;
}

async function handleSend() {
  const input = document.getElementById('chat-input');
  const send = document.getElementById('chat-send');
  const message = input.value.trim();

  if (!message || chatState.sending) return;

  chatState.sending = true;
  send.disabled = true;

  // Örnek soruları gizle (ilk mesajdan sonra)
  const suggestions = document.getElementById('chat-suggestions');
  if (suggestions) suggestions.style.display = 'none';

  // User mesajını göster
  addMessage('user', message);

  // Input temizle
  input.value = '';
  input.style.height = 'auto';

  // Geçmişe ekle
  chatState.history.push({ role: 'user', content: message });
  saveHistory();

  // AI placeholder mesajı (streaming için)
  const aiMessageEl = addMessage('ai', '', true);
  chatState.currentAiMessage = aiMessageEl;

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: message,
        history: chatState.history.slice(-10),
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let aiContent = '';
    let hasError = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.chunk) {
              aiContent += data.chunk;
              updateAiMessage(aiMessageEl, aiContent, true);
            } else if (data.done) {
              updateAiMessage(aiMessageEl, aiContent, false);
            } else if (data.error) {
              updateAiMessage(aiMessageEl, `⚠️ ${data.error}`, false);
              aiMessageEl.classList.add('error');
              hasError = true;
            }
          } catch (e) {
            console.warn('SSE parse error:', e, line);
          }
        }
      }
    }

    // Final stop typing
    updateAiMessage(aiMessageEl, aiContent || 'Cevap alınamadı.', false);

    if (!hasError && aiContent) {
      chatState.history.push({ role: 'assistant', content: aiContent });
      saveHistory();
    }
  } catch (error) {
    console.error('Chat error:', error);
    updateAiMessage(aiMessageEl, `⚠️ Hata: ${error.message || 'Bağlantı kurulamadı'}`, false);
    aiMessageEl.classList.add('error');
  } finally {
    chatState.sending = false;
    send.disabled = false;
    chatState.currentAiMessage = null;
    input.focus();
  }
}

function addMessage(role, content, typing = false) {
  const container = document.getElementById('chat-messages');
  if (!container) return null;

  const messageEl = document.createElement('div');
  messageEl.className = `chat-message chat-message-${role}`;
  if (typing) messageEl.classList.add('typing');

  const bubbleEl = document.createElement('div');
  bubbleEl.className = 'chat-message-bubble';
  bubbleEl.textContent = content;

  messageEl.appendChild(bubbleEl);
  container.appendChild(messageEl);

  container.scrollTop = container.scrollHeight;

  return messageEl;
}

function updateAiMessage(messageEl, content, typing) {
  if (!messageEl) return;

  const bubble = messageEl.querySelector('.chat-message-bubble');
  if (bubble) bubble.textContent = content;

  if (typing) {
    messageEl.classList.add('typing');
  } else {
    messageEl.classList.remove('typing');
  }

  const container = document.getElementById('chat-messages');
  if (container) container.scrollTop = container.scrollHeight;
}

function saveHistory() {
  try {
    localStorage.setItem('chat_history', JSON.stringify(chatState.history.slice(-20)));
  } catch (e) {
    console.warn('Chat history save failed:', e);
  }
}

// Sayfa yüklendiğinde init
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initChat);
} else {
  initChat();
}
