'use strict';
(function (global) {

// ─── Constants ────────────────────────────────────────────────────────────────

const C = {
  high: '#FF8C00',
  low:  '#3A8FD4',
  grid: '#D0D0D0',
  text: '#444444',
  zero: '#222222',
};

const PAD = { left: 78, right: 22, top: 22, bottom: 42 };

const PERIOD_MS = {
  '1h':  3_600_000,
  '6h':  21_600_000,
  '1d':  86_400_000,
  '1mo': 30 * 86_400_000,
  '1y':  365 * 86_400_000,
};

const AVG_MS = {
  '1m':  60_000,
  '5m':  300_000,
  '15m': 900_000,
  '1h':  3_600_000,
  '3h':  10_800_000,
  '1d':  86_400_000,
};

// Minimum avg window key for each source type
const SRC_MIN_AVG = { latest: '1m', '5min': '5m', '1h': '1h' };

const X_IVLS = [
  2_592_000_000, 604_800_000, 86_400_000, 43_200_000,
  21_600_000, 10_800_000, 3_600_000, 1_800_000,
  900_000, 300_000, 60_000,
];

// ─── Base ─────────────────────────────────────────────────────────────────────

class OSRSGraphBase {
  constructor(containerId, itemId, defaults) {
    this._cid        = containerId;
    this.itemId      = parseInt(itemId, 10);
    this._noControls = defaults.noControls || false;
    this.tableType   = defaults.tableType  || '5min';
    this.timePeriod  = defaults.timePeriod || '1d';
    this.avgKey      = defaults.avgKey     || '1h';

    this._customStart = null;
    this._customEnd   = null;
    this._records     = [];
    this._pts         = [];
    this._startMs = 0;
    this._endMs   = 0;
    this._abort   = null;

    // set during _draw()
    this._toX = null;
    this._toY = null;
    this._gx = this._gy = this._gw = this._gh = 0;

    this._hoverTip    = null;
    this._pinnedTips  = [];
    this._resizeTimer = null;

    this._el = document.getElementById(containerId);
    if (!this._el) throw new Error('[OSRSGraphs] container #' + containerId + ' not found');

    this._build();
  }

  // ── DOM ──────────────────────────────────────────────────────────────────

  _build() {
    this._el.innerHTML = '';
    this._el.classList.add('osrs-graph-container');

    if (!this._noControls) {
      this._ctrlsEl = document.createElement('div');
      this._ctrlsEl.className = 'osrs-graph-ctrls';
      this._el.appendChild(this._ctrlsEl);
      this._buildControls();
    }

    this._wrap = document.createElement('div');
    this._wrap.className = 'osrs-graph-wrap';
    this._el.appendChild(this._wrap);

    this._canvas = document.createElement('canvas');
    this._canvas.className = 'osrs-graph-canvas';
    this._wrap.appendChild(this._canvas);

    this._bindMouse();
    this._bindResize();
  }

  _buildControls() { /* subclass */ }

  _row(labelText, btns, activeKey, onPick) {
    const row = document.createElement('div');
    row.className = 'osrs-graph-ctrl-row';

    const lbl = document.createElement('span');
    lbl.className = 'osrs-graph-ctrl-lbl';
    lbl.textContent = labelText;
    row.appendChild(lbl);

    const grp = document.createElement('div');
    grp.className = 'osrs-graph-ctrl-grp';

    for (const { key, label } of btns) {
      const btn = document.createElement('button');
      btn.className   = 'w98-button osrs-ctrl-btn';
      btn.textContent = label;
      btn.dataset.key = key;
      if (key === activeKey) btn.classList.add('w98-button-active');
      btn.addEventListener('click', () => {
        if (btn.disabled) return;
        grp.querySelectorAll('.osrs-ctrl-btn').forEach(b => b.classList.remove('w98-button-active'));
        btn.classList.add('w98-button-active');
        onPick(key);
      });
      grp.appendChild(btn);
    }

    row.appendChild(grp);
    return { row, grp };
  }

  _setActive(grp, key) {
    grp.querySelectorAll('.osrs-ctrl-btn').forEach(b =>
      b.classList.toggle('w98-button-active', b.dataset.key === key));
  }

  _updateAvgBtns(tableType) {
    if (!this._avgGrp) return;
    const minMs = AVG_MS[SRC_MIN_AVG[tableType] || '1h'];
    this._avgGrp.querySelectorAll('.osrs-ctrl-btn').forEach(btn => {
      btn.disabled = AVG_MS[btn.dataset.key] < minMs;
    });
  }

  _buildCustomRow() {
    const row = document.createElement('div');
    row.className = 'osrs-graph-ctrl-row osrs-custom-row';
    row.style.display = 'none';

    const now  = new Date();
    const prev = new Date(now.getTime() - 86_400_000);
    const fmt  = d => {
      const p = n => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
    };

    const mkInput = val => {
      const el = document.createElement('input');
      el.type = 'datetime-local'; el.className = 'w98-input osrs-dt-in'; el.value = val;
      return el;
    };

    const sIn = mkInput(fmt(prev));
    const eIn = mkInput(fmt(now));
    const applyBtn = document.createElement('button');
    applyBtn.className = 'w98-button'; applyBtn.textContent = 'Apply';
    applyBtn.addEventListener('click', () => {
      if (sIn.value && eIn.value) {
        this._customStart = new Date(sIn.value).getTime();
        this._customEnd   = new Date(eIn.value).getTime();
        this.render();
      }
    });

    const wrapLabel = (text, inp) => {
      const lbl = document.createElement('label');
      lbl.className = 'osrs-dt-lbl'; lbl.textContent = text;
      lbl.appendChild(inp); return lbl;
    };

    row.appendChild(wrapLabel('Start: ', sIn));
    row.appendChild(wrapLabel('End: ', eIn));
    row.appendChild(applyBtn);
    return row;
  }

  // ── Canvas helpers ────────────────────────────────────────────────────────

  _canvasW() {
    return Math.max(this._wrap.clientWidth || this._el.clientWidth || 0, 400);
  }

  _msg(text, color) {
    const dpr = devicePixelRatio || 1;
    const w = this._canvasW();
    const h = this._graphH();
    this._canvas.width  = w * dpr;
    this._canvas.height = h * dpr;
    this._canvas.style.height = h + 'px';
    const ctx = this._canvas.getContext('2d');
    ctx.scale(dpr, dpr); ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = color || '#666'; ctx.font = '13px sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(text, w / 2, h / 2);
  }

  _initCtx() {
    const dpr = devicePixelRatio || 1;
    const w   = this._canvasW();
    const h   = this._graphH();
    this._canvas.width  = w * dpr;
    this._canvas.height = h * dpr;
    this._canvas.style.height = h + 'px';
    const ctx = this._canvas.getContext('2d');
    ctx.scale(dpr, dpr); ctx.clearRect(0, 0, w, h);
    return { ctx, w, h };
  }

  _coords(gx, gy, gw, gh, yMin, yMax) {
    this._gx = gx; this._gy = gy; this._gw = gw; this._gh = gh;
    this._toX = ms  => gx + (ms  - this._startMs) / (this._endMs  - this._startMs) * gw;
    this._toY = val => gy + gh - (val - yMin) / (yMax - yMin) * gh;
  }

  // ── Grid / labels ─────────────────────────────────────────────────────────

  _drawGrid(ctx, yLines, ticks) {
    const { _gx: gx, _gy: gy, _gw: gw, _gh: gh } = this;
    ctx.save();
    ctx.strokeStyle = C.grid; ctx.lineWidth = 1; ctx.setLineDash([4, 4]);
    for (const y of yLines) {
      const cy = this._toY(y);
      ctx.beginPath(); ctx.moveTo(gx, cy); ctx.lineTo(gx + gw, cy); ctx.stroke();
    }
    for (const t of ticks) {
      const cx = this._toX(t);
      if (cx < gx - 1 || cx > gx + gw + 1) continue;
      ctx.beginPath(); ctx.moveTo(cx, gy); ctx.lineTo(cx, gy + gh); ctx.stroke();
    }
    ctx.setLineDash([]); ctx.restore();
  }

  _drawYLbls(ctx, yLines, fmt) {
    ctx.save();
    ctx.fillStyle = C.text; ctx.font = '11px sans-serif';
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    for (const y of yLines) ctx.fillText(fmt(y), this._gx - 5, this._toY(y));
    ctx.restore();
  }

  _drawXLbls(ctx, ticks, interval) {
    const { _gx: gx, _gy: gy, _gw: gw, _gh: gh } = this;
    ctx.save();
    ctx.fillStyle = C.text; ctx.font = '11px sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    for (const t of ticks) {
      const cx = this._toX(t);
      if (cx < gx - 1 || cx > gx + gw + 1) continue;
      const lines = this._xLbl(t, interval).split('\n');
      lines.forEach((line, i) => ctx.fillText(line, cx, gy + gh + 5 + i * 13));
    }
    ctx.restore();
  }

  _drawLine(ctx, pts, getX, getY, color) {
    ctx.save();
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 2;
    ctx.beginPath();
    let first = true;
    for (const p of pts) {
      const y = getY(p); if (y == null || isNaN(y)) continue;
      const x = getX(p); first ? ctx.moveTo(x, y) : ctx.lineTo(x, y); first = false;
    }
    ctx.stroke();
    for (const p of pts) {
      const y = getY(p); if (y == null || isNaN(y)) continue;
      ctx.beginPath(); ctx.arc(getX(p), y, 4, 0, 2 * Math.PI); ctx.fill();
    }
    ctx.restore();
  }

  // ── Axis math ─────────────────────────────────────────────────────────────

  _yLines(minVal, maxVal) {
    if (maxVal <= minVal) maxVal = minVal + 1;
    const lo = Math.floor(minVal), hi = Math.ceil(maxVal);
    const step = (hi - lo) / 5;
    return Array.from({ length: 6 }, (_, i) => Math.round(lo + step * i));
  }

  _xTicks(startMs, endMs) {
    const dur = endMs - startMs;
    let chosen = X_IVLS[X_IVLS.length - 1], bestDiff = Infinity;
    for (const iv of X_IVLS) {
      const d = Math.floor(dur / iv);
      if (d >= 4 && d <= 7) { chosen = iv; break; }
      const diff = Math.abs(d - 5);
      if (diff < bestDiff) { bestDiff = diff; chosen = iv; }
    }
    const first = Math.ceil(startMs / chosen) * chosen;
    const ticks = [];
    for (let t = first; t <= endMs; t += chosen) ticks.push(t);
    return { ticks, interval: chosen };
  }

  _xLbl(ms, interval) {
    const d  = new Date(ms);
    const s  = new Date(this._startMs), e = new Date(this._endMs);
    const crossDay = s.toDateString() !== e.toDateString();
    if (interval < 86_400_000) {
      const t = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
      if (!crossDay) return t;
      return d.toLocaleDateString('en-GB', { month: 'short', day: 'numeric' }) + '\n' + t;
    }
    if (interval < 2_592_000_000)
      return d.toLocaleDateString('en-GB', { month: 'short', day: 'numeric' });
    return d.toLocaleDateString('en-GB', { month: 'short', year: 'numeric' });
  }

  // ── Date range ────────────────────────────────────────────────────────────

  _dateRange() {
    if (this.timePeriod === 'custom' && this._customStart && this._customEnd)
      return { startMs: this._customStart, endMs: this._customEnd };
    const now = Date.now();
    return { startMs: now - (PERIOD_MS[this.timePeriod] || PERIOD_MS['1d']), endMs: now };
  }

  // ── Averaging ─────────────────────────────────────────────────────────────

  _tsMs(iso) { return new Date(iso).getTime(); }

  _wAvg(prices, vols) {
    const pairs = prices.map((p, i) => ({ p: p || 0, v: vols[i] || 0 })).filter(x => x.p > 0);
    if (!pairs.length) return 0;
    const tv = pairs.reduce((s, x) => s + x.v, 0);
    if (tv > 0) return Math.round(pairs.reduce((s, x) => s + x.p * x.v, 0) / tv);
    return Math.round(pairs.reduce((s, x) => s + x.p, 0) / pairs.length);
  }

  _average(records, windowMs) {
    if (!records || !records.length) return [];
    const buckets = new Map();
    for (const rec of records) {
      const ms  = this._tsMs(rec.timestamp);
      const key = Math.floor(ms / windowMs) * windowMs;
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key).push({ ...rec, _ms: ms });
    }
    return [...buckets.entries()].sort((a, b) => a[0] - b[0]).map(([key, recs]) => ({
      timestampMs: key,
      high:    this._wAvg(recs.map(r => r.high || 0), recs.map(r => r.highVol || 0)),
      low:     this._wAvg(recs.map(r => r.low  || 0), recs.map(r => r.lowVol  || 0)),
      highVol: recs.reduce((s, r) => s + (r.highVol || 0), 0),
      lowVol:  recs.reduce((s, r) => s + (r.lowVol  || 0), 0),
      rawRecords: recs,
    }));
  }

  // ── Fetch / render ────────────────────────────────────────────────────────

  async render() {
    const { startMs, endMs } = this._dateRange();
    this._startMs = startMs; this._endMs = endMs;
    if (this._abort) this._abort.abort();
    this._abort = new AbortController();
    this._canvas.style.height = this._graphH() + 'px';
    this._msg('Loading…');
    try {
      const tok = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
      const hdrs = { 'Content-Type': 'application/json' };
      if (tok) hdrs['X-CSRFToken'] = tok;
      const resp = await fetch('/osrs/item-graph-data', {
        method: 'POST', headers: hdrs,
        body: JSON.stringify({
          item_id: this.itemId,
          start_date: new Date(startMs).toISOString(),
          end_date:   new Date(endMs).toISOString(),
          table_type: this.tableType,
        }),
        signal: this._abort.signal,
      });
      const data = await resp.json();
      if (data.status !== 'success') { this._msg(data.message || 'No data.', '#c00'); return; }
      this._records = data.records || [];
      if (!this._records.length) { this._msg('No data for this range.', '#c00'); return; }
      this._pts = this._average(this._records, AVG_MS[this.avgKey]);
      this._draw();
    } catch (e) {
      if (e.name !== 'AbortError') { this._msg('Failed to load data.', '#c00'); console.error('[OSRSGraphs]', e); }
    }
  }

  _redraw() {
    this._pts = this._average(this._records, AVG_MS[this.avgKey]);
    this._draw();
  }

  _graphH() { return 300; }
  _draw()   { /* subclass */ }

  // ── Mouse / tooltip ───────────────────────────────────────────────────────

  _bindMouse() {
    this._canvas.addEventListener('mousemove',  e => this._onMove(e));
    this._canvas.addEventListener('mouseleave', () => this._hideHover());
    this._canvas.addEventListener('click',      e => this._onClick(e));
  }

  _cpos(e) {
    const r = this._canvas.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }

  _nearest(mx) {
    if (!this._pts.length || !this._toX) return null;
    let best = null, bestD = 12;
    for (const p of this._pts) {
      const px = this._toX(p.timestampMs), d = Math.abs(mx - px);
      if (d < bestD) { bestD = d; best = { p, px }; }
    }
    return best;
  }

  _onMove(e) {
    const { x, y } = this._cpos(e);
    const hit = this._nearest(x);
    this._canvas.style.cursor = hit ? 'pointer' : 'default';
    hit ? this._showHover(hit.p, hit.px, y) : this._hideHover();
  }

  _onClick(e) {
    const { x, y } = this._cpos(e);
    const hit = this._nearest(x);
    if (hit) { this._hideHover(); this._pin(hit.p, hit.px, y); }
  }

  _showHover(point, px, py) {
    if (!this._hoverTip) {
      this._hoverTip = document.createElement('div');
      this._hoverTip.className = 'osrs-tip';
      this._wrap.appendChild(this._hoverTip);
    }
    this._renderTip(this._hoverTip, point, false);
    this._placeTip(this._hoverTip, px, py);
    this._hoverTip.style.display = 'block';
  }

  _hideHover() { if (this._hoverTip) this._hoverTip.style.display = 'none'; }

  _pin(point, px, py) {
    const el = document.createElement('div');
    el.className = 'osrs-tip pinned'; el._pt = point; el._sort = 'time';
    this._wrap.appendChild(el);
    this._pinnedTips.push(el);
    this._renderTip(el, point, true);
    this._placeTip(el, px, py);
  }

  _sortRows(point, sortKey) {
    const rows = [...point.rawRecords];
    return sortKey === 'time' ? rows.sort((a, b) => a._ms - b._ms) : rows.sort((a, b) => (b.high || 0) - (a.high || 0));
  }

  _tipBucketLabel(point) {
    return new Date(point.timestampMs).toLocaleString('en-GB',
      { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  _renderTip(el, point, pinned) {
    const sort = el._sort || 'time';
    const rows = this._sortRows(point, sort);
    const bucket = this._tipBucketLabel(point);

    let h = `<div class="osrs-tip-hdr"><span class="osrs-tip-bucket">${bucket}</span>`;
    if (pinned) h += `<button class="osrs-tip-x">✕</button>`;
    h += `</div>`;
    if (pinned) h += `<div class="osrs-tip-sorts">
      <button class="osrs-tip-sort ${sort==='time'?'active':''}" data-s="time">Time ↑</button>
      <button class="osrs-tip-sort ${sort==='price'?'active':''}" data-s="price">Price ↓</button>
    </div>`;
    h += `<div class="osrs-tip-body">
      <div class="osrs-tip-row-hdr"><span>High</span><span>Low</span><span>Time</span></div>`;
    for (const r of rows) {
      const t = new Date(r._ms).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      h += `<div class="osrs-tip-row">
        <span style="color:${C.high}">${(r.high||0).toLocaleString()}</span>
        <span style="color:${C.low}">${(r.low||0).toLocaleString()}</span>
        <span>${t}</span>
      </div>`;
    }
    h += `</div>`;
    el.innerHTML = h;

    if (pinned) {
      el.querySelector('.osrs-tip-x').addEventListener('click', () => {
        el.remove(); this._pinnedTips = this._pinnedTips.filter(t => t !== el);
      });
      el.querySelectorAll('.osrs-tip-sort').forEach(btn => {
        btn.addEventListener('click', () => { el._sort = btn.dataset.s; this._renderTip(el, el._pt, true); });
      });
    }
  }

  _placeTip(el, px, py) {
    el.style.left = '0'; el.style.top = '0'; el.style.display = 'block';
    const ww = this._wrap.offsetWidth, wh = this._wrap.offsetHeight;
    const tw = el.offsetWidth,         th = el.offsetHeight;
    let left = px + 14, top = py - 20;
    if (left + tw > ww) left = px - tw - 14;
    if (top  + th > wh) top  = wh - th - 4;
    if (top  < 0) top  = 4;
    if (left < 0) left = 4;
    el.style.left = left + 'px'; el.style.top = top + 'px';
  }

  // ── Resize ────────────────────────────────────────────────────────────────

  _bindResize() {
    this._resizeObs = new ResizeObserver(() => {
      clearTimeout(this._resizeTimer);
      this._resizeTimer = setTimeout(() => { if (this._pts.length) this._draw(); }, 120);
    });
    this._resizeObs.observe(this._el);
  }

  // ── Public ────────────────────────────────────────────────────────────────

  destroy() {
    if (this._abort) this._abort.abort();
    if (this._resizeObs) this._resizeObs.disconnect();
    clearTimeout(this._resizeTimer);
    this._pinnedTips.forEach(t => t.remove());
    this._el.innerHTML = '';
    this._el.classList.remove('osrs-graph-container');
  }
}

// ─── Price Line Graph ─────────────────────────────────────────────────────────

class OSRSPriceLineGraph extends OSRSGraphBase {
  constructor(containerId, itemId, opts = {}) {
    super(containerId, itemId, {
      tableType:  opts.tableType  || '5min',
      timePeriod: opts.timePeriod || '1d',
      avgKey:     opts.avgKey     || '1h',
    });
    this.render();
  }

  _graphH() { return 300; }

  _buildControls() {
    // Row 1 – source
    const { row: r1, grp: sg } = this._row('Source:', [
      { key: 'latest', label: 'Latest' },
      { key: '5min',   label: '5 min'  },
      { key: '1h',     label: '1 hr'   },
    ], this.tableType, key => {
      this.tableType = key;
      this._updateAvgBtns(key);
      const minMs = AVG_MS[SRC_MIN_AVG[key]];
      if (AVG_MS[this.avgKey] < minMs) {
        this.avgKey = SRC_MIN_AVG[key];
        this._setActive(this._avgGrp, this.avgKey);
      }
      this.render();
    });
    this._ctrlsEl.appendChild(r1);

    // Row 2 – time period
    const { row: r2 } = this._row('Period:', [
      { key: '1h',  label: '1 hr'    }, { key: '6h',     label: '6 hr'    },
      { key: '1d',  label: '1 day'   }, { key: '1mo',    label: '1 month' },
      { key: '1y',  label: '1 year'  }, { key: 'custom', label: 'Custom…' },
    ], this.timePeriod, key => {
      this.timePeriod = key;
      this._customRow.style.display = key === 'custom' ? 'flex' : 'none';
      if (key !== 'custom') this.render();
    });
    this._ctrlsEl.appendChild(r2);

    this._customRow = this._buildCustomRow();
    this._ctrlsEl.appendChild(this._customRow);

    // Row 3 – averaging
    const { row: r3, grp: ag } = this._row('Avg:', [
      { key: '1m',  label: '1 min'  }, { key: '5m',  label: '5 min'  },
      { key: '15m', label: '15 min' }, { key: '1h',  label: '1 hr'   },
      { key: '3h',  label: '3 hr'   }, { key: '1d',  label: '1 day'  },
    ], this.avgKey, key => { this.avgKey = key; this._redraw(); });
    this._avgGrp = ag;
    this._updateAvgBtns(this.tableType);
    this._ctrlsEl.appendChild(r3);
  }

  _draw() {
    const { ctx, w, h } = this._initCtx();
    const pts = this._pts;

    if (!pts.length) {
      this._msg('No data available for this time range.', '#c00'); return;
    }

    const gx = PAD.left, gy = PAD.top;
    const gw = w - PAD.left - PAD.right, gh = h - PAD.top - PAD.bottom;

    const allVals = pts.flatMap(p => [p.high || 0, p.low || 0]).filter(v => v > 0);
    if (!allVals.length) { this._msg('No price data for this range.', '#888'); return; }

    const yLines = this._yLines(Math.min(...allVals), Math.max(...allVals));
    const { ticks, interval } = this._xTicks(this._startMs, this._endMs);

    this._coords(gx, gy, gw, gh, yLines[0], yLines[5]);

    this._drawGrid(ctx, yLines, ticks);
    this._drawYLbls(ctx, yLines, v => v.toLocaleString() + ' gp');
    this._drawXLbls(ctx, ticks, interval);
    this._drawLine(ctx, pts, p => this._toX(p.timestampMs), p => this._toY(p.high), C.high);
    this._drawLine(ctx, pts, p => this._toX(p.timestampMs), p => this._toY(p.low),  C.low);
  }
}

// ─── Volume Bar Graph ─────────────────────────────────────────────────────────

class OSRSVolumeBarGraph extends OSRSGraphBase {
  constructor(containerId, itemId, opts = {}) {
    const ttype = opts.tableType === 'latest' ? '5min' : (opts.tableType || '5min');
    super(containerId, itemId, {
      tableType:  ttype,
      timePeriod: opts.timePeriod || '1d',
      avgKey:     opts.avgKey     || '1h',
    });
    this.render();
  }

  _graphH() { return 260; }

  _buildControls() {
    // Row 1 – source (no 'latest')
    const { row: r1 } = this._row('Source:', [
      { key: '5min', label: '5 min' },
      { key: '1h',   label: '1 hr'  },
    ], this.tableType, key => {
      this.tableType = key;
      this._updateAvgBtns(key);
      const minMs = AVG_MS[SRC_MIN_AVG[key]];
      if (AVG_MS[this.avgKey] < minMs) {
        this.avgKey = SRC_MIN_AVG[key];
        this._setActive(this._avgGrp, this.avgKey);
      }
      this.render();
    });
    this._ctrlsEl.appendChild(r1);

    // Row 2 – time period
    const { row: r2 } = this._row('Period:', [
      { key: '1h',  label: '1 hr'    }, { key: '6h',     label: '6 hr'    },
      { key: '1d',  label: '1 day'   }, { key: '1mo',    label: '1 month' },
      { key: '1y',  label: '1 year'  }, { key: 'custom', label: 'Custom…' },
    ], this.timePeriod, key => {
      this.timePeriod = key;
      this._customRow.style.display = key === 'custom' ? 'flex' : 'none';
      if (key !== 'custom') this.render();
    });
    this._ctrlsEl.appendChild(r2);

    this._customRow = this._buildCustomRow();
    this._ctrlsEl.appendChild(this._customRow);

    // Row 3 – averaging (no '1m')
    const { row: r3, grp: ag } = this._row('Avg:', [
      { key: '5m',  label: '5 min'  }, { key: '15m', label: '15 min' },
      { key: '1h',  label: '1 hr'   }, { key: '3h',  label: '3 hr'   },
      { key: '1d',  label: '1 day'  },
    ], this.avgKey, key => { this.avgKey = key; this._redraw(); });
    this._avgGrp = ag;
    this._updateAvgBtns(this.tableType);
    this._ctrlsEl.appendChild(r3);
  }

  _draw() {
    const { ctx, w, h } = this._initCtx();
    const pts = this._pts;

    if (!pts.length) { this._msg('No data available for this time range.', '#c00'); return; }

    const maxHi = Math.max(...pts.map(p => p.highVol || 0));
    const maxLo = Math.max(...pts.map(p => p.lowVol  || 0));
    if (maxHi === 0 && maxLo === 0) { this._msg('No volume data available.', '#888'); return; }

    const gx = PAD.left, gy = PAD.top;
    const gw = w - PAD.left - PAD.right, gh = h - PAD.top - PAD.bottom;

    const yMax   = Math.ceil(maxHi * 1.1) || 1;
    const yMin   = -(Math.ceil(maxLo * 1.1) || 1);
    const yLines = this._yLines(yMin, yMax);
    const { ticks, interval } = this._xTicks(this._startMs, this._endMs);

    this._coords(gx, gy, gw, gh, yLines[0], yLines[5]);

    this._drawGrid(ctx, yLines, ticks);
    this._drawYLbls(ctx, yLines, v => Math.abs(v).toLocaleString());
    this._drawXLbls(ctx, ticks, interval);

    // Zero line
    const zeroY = this._toY(0);
    ctx.save();
    ctx.strokeStyle = C.zero; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(gx, zeroY); ctx.lineTo(gx + gw, zeroY); ctx.stroke();
    ctx.restore();

    // Bars
    const barW = pts.length > 1
      ? Math.max(2, Math.abs(this._toX(pts[1].timestampMs) - this._toX(pts[0].timestampMs)) * 0.8)
      : 20;
    const hw = barW / 2;

    for (const p of pts) {
      const cx = this._toX(p.timestampMs);
      if (p.highVol > 0) { const t = this._toY(p.highVol);   ctx.fillStyle = C.high; ctx.fillRect(cx - hw, t,     barW, zeroY - t);    }
      if (p.lowVol  > 0) { const b = this._toY(-p.lowVol);   ctx.fillStyle = C.low;  ctx.fillRect(cx - hw, zeroY, barW, b - zeroY); }
    }
  }

  // Volume tooltip sorts by vol, not price
  _sortRows(point, sortKey) {
    const rows = [...point.rawRecords];
    return sortKey === 'time'
      ? rows.sort((a, b) => a._ms - b._ms)
      : rows.sort((a, b) => (b.highVol || 0) - (a.highVol || 0));
  }

  _renderTip(el, point, pinned) {
    const sort   = el._sort || 'time';
    const rows   = this._sortRows(point, sort);
    const bucket = this._tipBucketLabel(point);

    let h = `<div class="osrs-tip-hdr"><span class="osrs-tip-bucket">${bucket}</span>`;
    if (pinned) h += `<button class="osrs-tip-x">✕</button>`;
    h += `</div>`;
    if (pinned) h += `<div class="osrs-tip-sorts">
      <button class="osrs-tip-sort ${sort==='time'?'active':''}"  data-s="time">Time ↑</button>
      <button class="osrs-tip-sort ${sort==='price'?'active':''}" data-s="price">Vol ↓</button>
    </div>`;
    h += `<div class="osrs-tip-body">
      <div class="osrs-tip-row-hdr"><span>High Vol</span><span>Low Vol</span><span>Time</span></div>`;
    for (const r of rows) {
      const t = new Date(r._ms).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      h += `<div class="osrs-tip-row">
        <span style="color:${C.high}">${(r.highVol||0).toLocaleString()}</span>
        <span style="color:${C.low}">${(r.lowVol||0).toLocaleString()}</span>
        <span>${t}</span>
      </div>`;
    }
    h += `</div>`;
    el.innerHTML = h;

    if (pinned) {
      el.querySelector('.osrs-tip-x').addEventListener('click', () => {
        el.remove(); this._pinnedTips = this._pinnedTips.filter(t => t !== el);
      });
      el.querySelectorAll('.osrs-tip-sort').forEach(btn => {
        btn.addEventListener('click', () => { el._sort = btn.dataset.s; this._renderTip(el, el._pt, true); });
      });
    }
  }
}

// ─── Graph Pair (shared controls for price + volume) ─────────────────────────

class OSRSGraphPair {
  constructor(ctrlsCid, priceCid, volumeCid, itemId) {
    this._ctrlsEl  = document.getElementById(ctrlsCid);
    this._volumeEl = document.getElementById(volumeCid);

    this.tableType    = '5min';
    this.timePeriod   = '1d';
    this.avgKey       = '1h';
    this._customStart = null;
    this._customEnd   = null;

    this._buildControls();

    const opts = { noControls: true, tableType: this.tableType, timePeriod: this.timePeriod, avgKey: this.avgKey };
    this._price  = new OSRSPriceLineGraph(priceCid,  itemId, opts);
    this._volume = new OSRSVolumeBarGraph(volumeCid, itemId, opts);

    this._syncVolume();
  }

  _syncVolume() {
    if (this._volumeEl) this._volumeEl.style.display = (this.tableType === 'latest') ? 'none' : '';
  }

  _sync(action) {
    this._price.tableType    = this.tableType;
    this._price.timePeriod   = this.timePeriod;
    this._price.avgKey       = this.avgKey;
    this._price._customStart = this._customStart;
    this._price._customEnd   = this._customEnd;

    // volume graph cannot use 'latest' — fall back to 5min
    this._volume.tableType    = (this.tableType === 'latest') ? '5min' : this.tableType;
    this._volume.timePeriod   = this.timePeriod;
    this._volume.avgKey       = this.avgKey;
    this._volume._customStart = this._customStart;
    this._volume._customEnd   = this._customEnd;

    this._syncVolume();

    if (action === 'render') {
      this._price.render();
      if (this.tableType !== 'latest') this._volume.render();
    } else if (action === 'redraw') {
      this._price._redraw();
      if (this.tableType !== 'latest') this._volume._redraw();
    }
  }

  // ── Control helpers (mirrors OSRSGraphBase) ───────────────────────────────

  _row(labelText, btns, activeKey, onPick) {
    const row = document.createElement('div');
    row.className = 'osrs-graph-ctrl-row';
    const lbl = document.createElement('span');
    lbl.className = 'osrs-graph-ctrl-lbl';
    lbl.textContent = labelText;
    row.appendChild(lbl);
    const grp = document.createElement('div');
    grp.className = 'osrs-graph-ctrl-grp';
    for (const { key, label } of btns) {
      const btn = document.createElement('button');
      btn.className   = 'w98-button osrs-ctrl-btn';
      btn.textContent = label;
      btn.dataset.key = key;
      if (key === activeKey) btn.classList.add('w98-button-active');
      btn.addEventListener('click', () => {
        if (btn.disabled) return;
        grp.querySelectorAll('.osrs-ctrl-btn').forEach(b => b.classList.remove('w98-button-active'));
        btn.classList.add('w98-button-active');
        onPick(key);
      });
      grp.appendChild(btn);
    }
    row.appendChild(grp);
    return { row, grp };
  }

  _setActive(grp, key) {
    grp.querySelectorAll('.osrs-ctrl-btn').forEach(b =>
      b.classList.toggle('w98-button-active', b.dataset.key === key));
  }

  _updateAvgBtns(tableType) {
    if (!this._avgGrp) return;
    const minMs = AVG_MS[SRC_MIN_AVG[tableType] || '1h'];
    this._avgGrp.querySelectorAll('.osrs-ctrl-btn').forEach(btn => {
      btn.disabled = AVG_MS[btn.dataset.key] < minMs;
    });
  }

  _buildControls() {
    if (!this._ctrlsEl) return;
    this._ctrlsEl.innerHTML = '';
    this._ctrlsEl.className = 'osrs-graph-ctrls';

    const { row: r1 } = this._row('Source:', [
      { key: 'latest', label: 'Latest' },
      { key: '5min',   label: '5 min'  },
      { key: '1h',     label: '1 hr'   },
    ], this.tableType, key => {
      this.tableType = key;
      this._updateAvgBtns(key);
      const minMs = AVG_MS[SRC_MIN_AVG[key]];
      if (AVG_MS[this.avgKey] < minMs) {
        this.avgKey = SRC_MIN_AVG[key];
        this._setActive(this._avgGrp, this.avgKey);
      }
      this._sync('render');
    });
    this._ctrlsEl.appendChild(r1);

    const { row: r2 } = this._row('Period:', [
      { key: '1h',  label: '1 hr'    }, { key: '6h',     label: '6 hr'    },
      { key: '1d',  label: '1 day'   }, { key: '1mo',    label: '1 month' },
      { key: '1y',  label: '1 year'  }, { key: 'custom', label: 'Custom…' },
    ], this.timePeriod, key => {
      this.timePeriod = key;
      this._customRow.style.display = key === 'custom' ? 'flex' : 'none';
      if (key !== 'custom') this._sync('render');
    });
    this._ctrlsEl.appendChild(r2);

    this._customRow = this._buildCustomRow();
    this._ctrlsEl.appendChild(this._customRow);

    const { row: r3, grp: ag } = this._row('Avg:', [
      { key: '1m',  label: '1 min'  }, { key: '5m',  label: '5 min'  },
      { key: '15m', label: '15 min' }, { key: '1h',  label: '1 hr'   },
      { key: '3h',  label: '3 hr'   }, { key: '1d',  label: '1 day'  },
    ], this.avgKey, key => { this.avgKey = key; this._sync('redraw'); });
    this._avgGrp = ag;
    this._updateAvgBtns(this.tableType);
    this._ctrlsEl.appendChild(r3);
  }

  _buildCustomRow() {
    const row = document.createElement('div');
    row.className = 'osrs-graph-ctrl-row osrs-custom-row';
    row.style.display = 'none';
    const now  = new Date();
    const prev = new Date(now.getTime() - 86_400_000);
    const fmt  = d => {
      const p = n => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
    };
    const mkInput = val => {
      const el = document.createElement('input');
      el.type = 'datetime-local'; el.className = 'w98-input osrs-dt-in'; el.value = val;
      return el;
    };
    const sIn = mkInput(fmt(prev));
    const eIn = mkInput(fmt(now));
    const applyBtn = document.createElement('button');
    applyBtn.className = 'w98-button'; applyBtn.textContent = 'Apply';
    applyBtn.addEventListener('click', () => {
      if (sIn.value && eIn.value) {
        this._customStart = new Date(sIn.value).getTime();
        this._customEnd   = new Date(eIn.value).getTime();
        this._sync('render');
      }
    });
    const wrapLabel = (text, inp) => {
      const lbl = document.createElement('label');
      lbl.className = 'osrs-dt-lbl'; lbl.textContent = text;
      lbl.appendChild(inp); return lbl;
    };
    row.appendChild(wrapLabel('Start: ', sIn));
    row.appendChild(wrapLabel('End: ', eIn));
    row.appendChild(applyBtn);
    return row;
  }

  destroy() {
    if (this._price)  this._price.destroy();
    if (this._volume) this._volume.destroy();
  }
}

// ─── Export ────────────────────────────────────────────────────────────────────

global.OSRSPriceLineGraph = OSRSPriceLineGraph;
global.OSRSVolumeBarGraph = OSRSVolumeBarGraph;
global.OSRSGraphPair      = OSRSGraphPair;

})(window);
