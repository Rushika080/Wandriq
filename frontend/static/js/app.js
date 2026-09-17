/* ══════════════════════════════════════════════
   Wandriq — Frontend App Logic
   ══════════════════════════════════════════════ */

const API = '';   // same-origin (FastAPI serves both)
let lastItinerary = null;
let lastReq       = null;
const CURRENCIES  = {};

// ── Bootstrap ─────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await loadCurrencies();
  checkApiKey();
  loadCache();
});

async function loadCurrencies() {
  try {
    const r = await fetch(`${API}/api/currencies`);
    const d = await r.json();
    const selectors = ['#f-currency','#m-currency'];
    selectors.forEach(sel => {
      const el = document.querySelector(sel);
      if (!el) return;
      el.innerHTML = '';
      d.currencies.forEach(c => {
        CURRENCIES[c.code] = c;
        const o = document.createElement('option');
        o.value = c.code;
        o.textContent = `${c.symbol} ${c.code} — ${c.name}`;
        if (c.code === 'USD') o.selected = true;
        el.appendChild(o);
      });
    });
  } catch(e) { console.warn('Currency load failed', e); }
}

function checkApiKey() {
  const stored = localStorage.getItem('wandriq_groq_key');
  if (!stored) {
    document.getElementById('api-banner').classList.remove('hidden');
  }
}

function saveKey() {
  const k = document.getElementById('api-key-input').value.trim();
  if (!k) return;
  localStorage.setItem('wandriq_groq_key', k);
  document.getElementById('api-banner').classList.add('hidden');
  // In a real deploy the key would be sent to the backend
  // For local use, the backend reads GROQ_API_KEY env var
  showToast('API key saved! Set GROQ_API_KEY env var before starting the server.');
}

function loadCache() {
  const cached = localStorage.getItem('wandriq_last');
  if (cached) {
    try {
      const d = JSON.parse(cached);
      lastItinerary = d.itinerary;
      lastReq       = d.req;
      // Don't auto-render; let user decide
    } catch(e) {}
  }
}

// ── Mode toggle ────────────────────────────────
function setMode(m) {
  document.getElementById('btn-plan').classList.toggle('active', m === 'plan');
  document.getElementById('btn-month').classList.toggle('active', m === 'month');
  document.getElementById('mode-plan').classList.toggle('hidden', m !== 'plan');
  document.getElementById('mode-month').classList.toggle('hidden', m !== 'month');
  document.getElementById('dest-results').classList.add('hidden');
  document.getElementById('result').classList.add('hidden');
}

// ── Tag toggle ─────────────────────────────────
function tog(el) { el.classList.toggle('on'); }

// ── Month picker ───────────────────────────────
function selM(el) {
  document.querySelectorAll('.mbtn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
}

function getSelectedMonth() {
  const m = document.querySelector('.mbtn.active');
  if (!m) return 'April';
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const full   = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  return full[months.indexOf(m.textContent)] || 'April';
}

function getSelectedInterests() {
  return [...document.querySelectorAll('#tags .itag.on')]
    .map(t => t.textContent.replace(/^[^\w]+/,'').trim());
}

// ── Loader ─────────────────────────────────────
const LOADER_MSGS = [
  'Analysing your wishlist…',
  'Checking local conditions…',
  'Curating hidden gems…',
  'Building your day-by-day plan…',
  'Sourcing the best eats…',
  'Calculating your budget…',
  'Almost ready to depart…'
];
let loaderTimer, loaderIdx = 0;

function showLoader(on) {
  const el = document.getElementById('loader');
  el.classList.toggle('hidden', !on);
  if (on) {
    loaderIdx = 0;
    document.getElementById('loader-msg').textContent = LOADER_MSGS[0];
    loaderTimer = setInterval(() => {
      loaderIdx = (loaderIdx + 1) % LOADER_MSGS.length;
      document.getElementById('loader-msg').textContent = LOADER_MSGS[loaderIdx];
    }, 1400);
  } else {
    clearInterval(loaderTimer);
  }
}

function showToast(msg) {
  const t = document.createElement('div');
  t.textContent = msg;
  Object.assign(t.style, {
    position:'fixed', bottom:'1.5rem', right:'1.5rem',
    background:'#1e1e28', border:'.5px solid rgba(201,168,76,.4)',
    color:'#f0ede8', padding:'.7rem 1.1rem', borderRadius:'10px',
    fontSize:'.82rem', zIndex:'999', maxWidth:'300px', lineHeight:'1.5'
  });
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// ── GENERATE ITINERARY ─────────────────────────
async function generate() {
  const dest     = document.getElementById('f-dest').value.trim();
  const budget   = parseFloat(document.getElementById('f-budget').value);
  const currency = document.getElementById('f-currency').value;
  const duration = parseInt(document.getElementById('f-dur').value) || 7;
  const month    = document.getElementById('f-month').value;
  const style    = document.getElementById('f-style').value;
  const wish     = document.getElementById('f-wish').value.trim();

  if (!dest) { showToast('Please enter a destination!'); return; }
  if (!budget || budget < 50) { showToast('Enter a valid budget.'); return; }

  const req = {
    destination: dest, budget, currency, duration,
    month, travel_style: style, wishlist: wish,
    interests: getSelectedInterests()
  };

  lastReq = req;
  document.getElementById('result').classList.add('hidden');
  showLoader(true);
  document.getElementById('planner').scrollIntoView({ behavior: 'smooth' });

  try {
    const r = await fetch(`${API}/api/generate-itinerary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req)
    });

    if (!r.ok) {
      const err = await r.json();
      throw new Error(err.detail || 'Server error');
    }

    const data = await r.json();
    lastItinerary = data;
    localStorage.setItem('wandriq_last', JSON.stringify({ itinerary: data, req }));
    showLoader(false);
    renderItinerary(data, req);
  } catch(e) {
    showLoader(false);
    showToast('Error: ' + e.message);
    // Demo mode fallback
    renderDemo(req);
  }
}

async function suggestDest() {
  const budget   = parseFloat(document.getElementById('m-budget').value) || 1500;
  const currency = document.getElementById('m-currency').value;
  const style    = document.getElementById('m-style').value;
  const month    = getSelectedMonth();

  showLoader(true);
  document.getElementById('dest-results').classList.add('hidden');
  document.getElementById('result').classList.add('hidden');

  try {
    const r = await fetch(`${API}/api/suggest-destinations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ month, budget, currency, travel_style: style, interests: [] })
    });
    if (!r.ok) throw new Error((await r.json()).detail);
    const data = await r.json();
    showLoader(false);
    renderDestinations(data.destinations || [], month, currency);
  } catch(e) {
    showLoader(false);
    showToast('Error: ' + e.message);
    renderDemoDestinations();
  }
}

// ── RENDER DESTINATIONS ────────────────────────
function renderDestinations(dests, month, currency) {
  const el = document.getElementById('dest-results');
  const sym = (CURRENCIES[currency] || {}).symbol || currency;

  el.innerHTML = `
    <h2 class="dest-results-title fade-up">Best places to visit in <span>${month}</span></h2>
    <div class="dest-cards-grid">
      ${dests.map((d, i) => `
        <div class="dest-card fade-up" style="animation-delay:${i*.08}s"
             onclick="pickDestination('${escHtml(d.city)}')">
          <div class="dest-card-emoji">${d.emoji || '🌍'}</div>
          <div class="dest-card-city">${escHtml(d.city)}</div>
          <div class="dest-card-tagline">${escHtml(d.tagline || '')}</div>
          <div class="dest-card-why">${escHtml(d.why_now || '')}</div>
          <div class="dest-card-meta">
            ${seasonPill(d.season)}
            ${crowdPill(d.crowd_level)}
            ${budgetFitPill(d.budget_fit)}
            ${d.avg_daily_usd ? `<span class="pill pill-gold">~${sym}${Math.round(d.avg_daily_usd)}/day</span>` : ''}
          </div>
        </div>
      `).join('')}
    </div>`;
  el.classList.remove('hidden');
  el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function pickDestination(city) {
  setMode('plan');
  document.getElementById('f-dest').value = city;
  document.getElementById('dest-results').classList.add('hidden');
  const activeMonth = getSelectedMonth();
  document.querySelectorAll('#f-month option').forEach(o => {
    if (o.value === activeMonth) o.selected = true;
  });
  document.getElementById('mode-plan').scrollIntoView({ behavior: 'smooth' });
  setTimeout(generate, 300);
}

// ── RENDER ITINERARY ───────────────────────────
function renderItinerary(d, req) {
  const el = document.getElementById('result');
  const sym = (CURRENCIES[req.currency] || {}).symbol || req.currency;
  const cb  = d.cost_breakdown || {};
  const total    = cb.total_usd || 0;
  const perDay   = total ? Math.round(total / req.duration) : 0;
  const under    = req.budget && req.currency === 'USD' ? Math.round(req.budget - total) : null;

  const fmtAmt = (usd) => `${sym}${Math.round(usd * (req.exchange_rate || 1)).toLocaleString()}`;

  el.innerHTML = `
    <!-- Header -->
    <div class="result-header fade-up">
      <div>
        <div class="result-dest">
          ${escHtml(d.destination)} <span style="font-size:1rem">✦</span>
          <span>${req.duration} days</span>
        </div>
        <div class="result-meta">
          ${d.safety_rating   ? `<span class="pill ${safetyColor(d.safety_rating)}">${d.safety_rating}</span>` : ''}
          ${d.crowd_level     ? `<span class="pill ${crowdColor(d.crowd_level)}">Crowds: ${d.crowd_level}</span>` : ''}
          ${d.visa_info       ? `<span class="pill pill-blue">${escHtml(d.visa_info)}</span>` : ''}
          ${d.weather_note    ? `<span class="pill pill-gold">${escHtml(d.weather_note)}</span>` : ''}
          ${(d.best_for||[]).map(b=>`<span class="pill pill-gold">${escHtml(b)}</span>`).join('')}
        </div>
      </div>
      <div class="result-actions">
        <button class="btn-sm" onclick="regenerate()">↺ Regenerate</button>
        <button class="btn-sm" onclick="window.print()">⎙ Print</button>
      </div>
    </div>

    ${d.overview ? `<p style="color:var(--text2);font-size:.9rem;margin-bottom:1.5rem;line-height:1.7;font-style:italic">${escHtml(d.overview)}</p>` : ''}

    <!-- Weather -->
    ${renderWeather(d)}

    <!-- Cost breakdown -->
    <div class="r-card fade-up-2">
      <div class="r-card-title">Cost breakdown</div>
      <div class="cost-summary">
        <div class="cost-stat"><div class="cost-val">${fmtAmt(total)}</div><div class="cost-lbl">Total est.</div></div>
        <div class="cost-stat"><div class="cost-val">${fmtAmt(perDay)}</div><div class="cost-lbl">Per day</div></div>
        ${under !== null ? `<div class="cost-stat"><div class="cost-val" style="color:var(--green)">${under >= 0 ? '+' : ''}${sym}${Math.abs(under).toLocaleString()}</div><div class="cost-lbl">${under >= 0 ? 'Under budget' : 'Over budget'}</div></div>` : ''}
        <div class="cost-stat"><div class="cost-val">${total && req.budget ? Math.round((total/(req.budget*(req.exchange_rate||1)))*100)+'%' : '—'}</div><div class="cost-lbl">Budget used</div></div>
      </div>
      <div class="bar-list">
        ${renderBar('Accommodation', cb.accommodation_usd, total, '#c9a84c', fmtAmt)}
        ${renderBar('Food', cb.food_usd, total, '#4caf82', fmtAmt)}
        ${renderBar('Transport', cb.transport_usd, total, '#5b9cf6', fmtAmt)}
        ${renderBar('Activities', cb.activities_usd, total, '#e8a030', fmtAmt)}
        ${renderBar('Misc', cb.misc_usd, total, '#9e9b94', fmtAmt)}
      </div>
    </div>

    <!-- Itinerary -->
    <div class="r-card fade-up-2">
      <div class="r-card-title">Day-by-day itinerary</div>
      ${(d.days || []).map(day => renderDay(day, fmtAmt)).join('')}
    </div>

    <!-- Hotels -->
    ${(d.hotels||[]).length ? `
    <div class="r-card fade-up-3">
      <div class="r-card-title">Recommended hotels</div>
      <div class="venue-list">
        ${d.hotels.map(h => `
          <div class="venue-row">
            <div class="venue-icon">${hotelIcon(h.type)}</div>
            <div>
              <div class="venue-name">${escHtml(h.name)} ${h.eco_certified ? '<span class="pill pill-green" style="font-size:.65rem">Eco</span>' : ''}</div>
              <div class="venue-meta">${escHtml(h.highlight || '')} · ${h.type}</div>
              <div class="venue-price">${fmtAmt(h.price_per_night_usd)}/night</div>
            </div>
            <div class="venue-right"><div class="rating">★ ${h.rating}</div></div>
          </div>`).join('')}
      </div>
    </div>` : ''}

    <!-- Restaurants -->
    ${(d.top_restaurants||[]).length ? `
    <div class="r-card fade-up-3">
      <div class="r-card-title">Top restaurants</div>
      <div class="venue-list">
        ${d.top_restaurants.map(r => `
          <div class="venue-row">
            <div class="venue-icon">🍽</div>
            <div>
              <div class="venue-name">${escHtml(r.name)} ${r.wishlist_match ? '<span class="pill pill-gold" style="font-size:.65rem">✦ wishlist</span>' : ''}</div>
              <div class="venue-meta">${escHtml(r.cuisine)} · Must try: ${escHtml(r.must_try||'')}</div>
              <div class="venue-price">~${fmtAmt(r.avg_cost_usd)} avg</div>
            </div>
            <div class="venue-right"><div class="rating">★ ${r.rating}</div></div>
          </div>`).join('')}
      </div>
    </div>` : ''}

    <!-- Eco tips -->
    ${(d.sustainable_tips||[]).length ? `
    <div class="r-card fade-up-3">
      <div class="r-card-title" style="color:var(--green)">Sustainable travel</div>
      <div class="eco-list">
        ${d.sustainable_tips.map(t => `
          <div class="eco-row">
            <div class="eco-icon">${t.icon}</div>
            <div>
              <div class="eco-title">${escHtml(t.title)}</div>
              <div class="eco-detail">${escHtml(t.detail)}</div>
            </div>
          </div>`).join('')}
      </div>
    </div>` : ''}

    <!-- Packing list -->
    ${(d.packing_list||[]).length ? `
    <div class="r-card fade-up-3">
      <div class="r-card-title">Packing checklist</div>
      <div class="pack-grid">
        ${d.packing_list.map(item => `
          <div class="pack-item">
            <div class="pack-check">✓</div>
            ${escHtml(item)}
          </div>`).join('')}
      </div>
    </div>` : ''}

    <!-- Phrases -->
    ${(d.phrases||[]).length ? `
    <div class="r-card fade-up-3">
      <div class="r-card-title">Useful phrases</div>
      <div class="phrase-list">
        ${d.phrases.map(p => `
          <div class="phrase-row">
            <div class="phrase-orig">${escHtml(p.original)}</div>
            <div class="phrase-tr">${escHtml(p.translation)}</div>
            <div class="phrase-pron">${escHtml(p.pronunciation||'')}</div>
          </div>`).join('')}
      </div>
    </div>` : ''}

    <!-- Quick actions -->
    <div class="quick-actions fade-up-3">
      <button class="q-btn" onclick="askMore('hidden local spots')">Hidden spots</button>
      <button class="q-btn" onclick="askMore('save money tips')">Cut costs</button>
      <button class="q-btn" onclick="askMore('photography locations')">Photo spots</button>
      <button class="q-btn" onclick="window.print()">Export / Print</button>
    </div>
  `;

  el.classList.remove('hidden');
  el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderWeather(d) {
  if (d.weather_forecast && d.weather_forecast.days && d.weather_forecast.days.length) {
    const days = d.weather_forecast.days;
    return `
      <div class="r-card fade-up-2">
        <div class="r-card-title">Live weather forecast</div>
        <div class="weather-row">
          ${days.map(day => {
            const dt   = new Date(day.date);
            const lbl  = dt.toLocaleDateString('en', { weekday: 'short' });
            const icon = weatherIcon(day.condition);
            return `<div class="w-day">
              <div class="w-lbl">${lbl}</div>
              <div class="w-icon">${icon}</div>
              <div class="w-temp">${day.max}°</div>
              <div class="w-low">${day.min}°</div>
            </div>`;
          }).join('')}
        </div>
      </div>`;
  }
  return '';
}

function renderBar(label, usd, total, color, fmtAmt) {
  if (!usd) return '';
  const pct = total ? Math.min(100, Math.round((usd / total) * 100)) : 0;
  return `
    <div class="bar-row">
      <span class="bar-cat">${label}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%;background:${color}"></div></div>
      <span class="bar-amt">${fmtAmt(usd)}</span>
    </div>`;
}

function renderDay(day, fmtAmt) {
  const slots = [
    { time: 'Morning',   data: day.morning },
    { time: 'Afternoon', data: day.afternoon },
    { time: 'Evening',   data: day.evening }
  ].filter(s => s.data && s.data.activity);

  return `
    <div class="day-block">
      <div class="day-header">
        <span class="day-num">Day ${day.day}</span>
        <div>
          <div class="day-title">${escHtml(day.title||'')}</div>
          ${day.theme ? `<div class="day-theme">${escHtml(day.theme)}</div>` : ''}
        </div>
      </div>
      <div class="day-body">
        ${slots.map(s => `
          <div class="day-slot">
            <div class="day-slot-time">${s.time}</div>
            <div class="day-slot-act">
              ${escHtml(s.data.activity||'')}
              ${s.data.wishlist_match ? '<span class="wish-badge">✦ wishlist</span>' : ''}
            </div>
            ${s.data.detail ? `<div class="day-slot-detail">${escHtml(s.data.detail)}</div>` : ''}
            ${s.data.cost_usd ? `<div class="day-slot-cost">${fmtAmt(s.data.cost_usd)}</div>` : ''}
          </div>`).join('')}
        <div class="day-dining">
          ${day.lunch_spot  ? `<div class="dining-pill">🍜 ${escHtml(day.lunch_spot.name)} (lunch · ${fmtAmt(day.lunch_spot.avg_cost_usd||0)})</div>` : ''}
          ${day.dinner_spot ? `<div class="dining-pill">🌙 ${escHtml(day.dinner_spot.name)} (dinner · ${fmtAmt(day.dinner_spot.avg_cost_usd||0)})</div>` : ''}
          ${day.transport   ? `<div class="dining-pill">🚌 ${escHtml(day.transport)}</div>` : ''}
        </div>
      </div>
    </div>`;
}

// ── Helpers ────────────────────────────────────
function escHtml(str) {
  return String(str||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function seasonPill(s) {
  const map = { peak:'pill-amber', shoulder:'pill-blue', 'off-peak':'pill-green' };
  return s ? `<span class="pill ${map[s]||'pill-gold'}">${s}</span>` : '';
}
function crowdPill(c) {
  const map = { low:'pill-green', medium:'pill-amber', high:'pill-red' };
  return c ? `<span class="pill ${map[c]||'pill-blue'}">Crowds: ${c}</span>` : '';
}
function budgetFitPill(b) {
  const map = { perfect:'pill-green', good:'pill-blue', stretch:'pill-amber' };
  return b ? `<span class="pill ${map[b]||'pill-blue'}">${b} fit</span>` : '';
}
function crowdColor(c) {
  return { low:'pill-green', medium:'pill-amber', high:'pill-red' }[c] || 'pill-blue';
}
function safetyColor(s) {
  if (s === 'safe') return 'pill-green';
  if (s === 'mostly safe') return 'pill-blue';
  return 'pill-amber';
}
function hotelIcon(type) {
  return { budget:'🏕', backpacker:'🎒', mid:'🏨', luxury:'🏰', 'mid-range':'🏨' }[type] || '🏨';
}
function weatherIcon(cond) {
  const c = (cond||'').toLowerCase();
  if (c.includes('sunny')) return '☀️';
  if (c.includes('cloudy') || c.includes('overcast')) return '☁️';
  if (c.includes('rain') || c.includes('drizzle') || c.includes('shower')) return '🌧️';
  if (c.includes('snow')) return '❄️';
  if (c.includes('thunder') || c.includes('storm')) return '⛈️';
  if (c.includes('fog')) return '🌫️';
  return '⛅';
}

async function regenerate() {
  if (!lastReq) return;
  document.getElementById('result').classList.add('hidden');
  await generate();
}

function askMore(topic) {
  const dest = lastReq?.destination || 'the destination';
  const url  = `https://claude.ai/new?q=${encodeURIComponent(`Tell me more about ${topic} in ${dest} for my ${lastReq?.duration || 7}-day trip`)}`;
  window.open(url, '_blank');
}

// ── DEMO mode (no API key) ─────────────────────
function renderDemo(req) {
  showToast('Running in demo mode — set GROQ_API_KEY to get real AI results!');
  const demo = {
    destination: req.destination,
    duration: req.duration,
    month: req.month,
    overview: `A curated ${req.duration}-day journey through ${req.destination}. This is a demo preview — connect your Groq API key for full AI-generated itineraries.`,
    weather_note: `${req.month} is a lovely time to visit`,
    visa_info: 'Check embassy website',
    safety_rating: 'mostly safe',
    crowd_level: 'medium',
    best_for: req.interests.slice(0,2),
    days: Array.from({length: Math.min(req.duration, 3)}, (_, i) => ({
      day: i+1,
      title: `Day ${i+1} Adventure`,
      theme: 'Explore & discover',
      morning:   { activity: 'Explore the old town', detail: 'Start early for the best light', cost_usd: 5 },
      afternoon: { activity: 'Local food market', detail: 'Sample street food', cost_usd: 15, wishlist_match: req.wishlist.length > 0 },
      evening:   { activity: 'Sunset viewpoint', detail: 'Golden hour photography', cost_usd: 0 },
      lunch_spot:  { name: 'Local bistro', cuisine: 'Local', avg_cost_usd: 12 },
      dinner_spot: { name: 'Rooftop restaurant', cuisine: 'Fusion', avg_cost_usd: 25 },
      transport: 'Walk or local bus'
    })),
    cost_breakdown: {
      accommodation_usd: Math.round(req.budget * 0.38),
      food_usd:          Math.round(req.budget * 0.22),
      transport_usd:     Math.round(req.budget * 0.14),
      activities_usd:    Math.round(req.budget * 0.12),
      misc_usd:          Math.round(req.budget * 0.06),
      total_usd:         Math.round(req.budget * 0.92),
    },
    hotels: [
      { name: 'Budget Hostel', type: 'budget', price_per_night_usd: 20, rating: 4.2, highlight: 'Social atmosphere', eco_certified: false },
      { name: 'City Hotel', type: 'mid', price_per_night_usd: 75, rating: 4.5, highlight: 'Central location', eco_certified: true },
      { name: 'Luxury Resort', type: 'luxury', price_per_night_usd: 200, rating: 4.9, highlight: 'Spa & rooftop pool', eco_certified: false },
    ],
    top_restaurants: [
      { name: 'Street Food Alley', cuisine: 'Local', avg_cost_usd: 8, rating: 4.6, must_try: 'House special', wishlist_match: false },
      { name: 'Fine Dining Co.', cuisine: 'Contemporary', avg_cost_usd: 45, rating: 4.8, must_try: 'Tasting menu', wishlist_match: false },
    ],
    sustainable_tips: [
      { icon: '🚌', title: 'Use public transport', detail: 'Local buses and trains cut your carbon footprint by up to 75%.' },
      { icon: '🏡', title: 'Stay local', detail: 'Locally-owned guesthouses keep money in the community.' },
      { icon: '🛍', title: 'Shop at markets', detail: 'Buy from street markets to support local artisans directly.' },
    ],
    packing_list: ['Comfortable walking shoes','Camera','Travel adapter','Light rain jacket','Reusable water bottle','Sunscreen','Portable charger','Cash (local currency)'],
    phrases: [
      { original: 'Hello', translation: '(local greeting)', pronunciation: '...' },
      { original: 'Thank you', translation: '(local thanks)', pronunciation: '...' },
      { original: 'How much?', translation: '(local phrase)', pronunciation: '...' },
    ]
  };
  renderItinerary(demo, req);
}

function renderDemoDestinations() {
  const dests = [
    { city: 'Kyoto, Japan', tagline: 'Sakura, temples & tranquility', why_now: 'Cherry blossom peak season', season: 'peak', crowd_level: 'high', budget_fit: 'good', avg_daily_usd: 130, emoji: '🌸' },
    { city: 'Lisbon, Portugal', tagline: 'Warm, vibrant & walkable', why_now: 'Spring bloom with fewer tourists', season: 'shoulder', crowd_level: 'medium', budget_fit: 'perfect', avg_daily_usd: 90, emoji: '🏛' },
    { city: 'Chiang Mai, Thailand', tagline: 'Temples, trekking & street food', why_now: 'Dry season ending — perfect weather', season: 'shoulder', crowd_level: 'low', budget_fit: 'perfect', avg_daily_usd: 60, emoji: '🐘' },
    { city: 'Medellín, Colombia', tagline: 'Eternal spring city', why_now: 'Flower Festival season nearby', season: 'off-peak', crowd_level: 'low', budget_fit: 'perfect', avg_daily_usd: 55, emoji: '🌺' },
    { city: 'Tokyo, Japan', tagline: 'Neon lights meet ancient culture', why_now: 'Cherry blossoms in full bloom', season: 'peak', crowd_level: 'high', budget_fit: 'stretch', avg_daily_usd: 160, emoji: '🗼' },
    { city: 'Tbilisi, Georgia', tagline: 'Wine, mountains & hidden gems', why_now: 'Spring warmth, minimal crowds', season: 'off-peak', crowd_level: 'low', budget_fit: 'perfect', avg_daily_usd: 50, emoji: '🍷' },
  ];
  renderDestinations(dests, 'April', 'USD');
}
