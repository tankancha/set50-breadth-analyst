/* SET50 Options Breadth — vanilla JS + Plotly.
 * Loads manifest → fills series dropdown → on change fetches that series' latest/previous + analysis,
 * re-renders the active view (Volume / Open Interest / OI Change / Analytics).
 * All fetches are RELATIVE so the page works under a GitHub Pages project sub-path. */

(function () {
  'use strict';

  // ─── Palette (mirrors style.css) ─────────────────────────
  var C = {
    call: '#1A6FFF', put: '#F5A623',
    callLine: '#1256CC', putLine: '#C97E0E',
    up: '#0E9F6E', down: '#E0264A',
    ink: '#0C1A30', text1: '#33415A', text2: '#5B6B83', text3: '#93A1B5',
    border: '#E4EAF3', surface: '#FFFFFF',
    band25: 'rgba(26,111,255,0.10)', band25line: 'rgba(26,111,255,0.35)',
    band10: 'rgba(245,166,35,0.10)', band10line: 'rgba(245,166,35,0.35)',
    spot: '#0C1A30', maxpain: '#00A87E'
  };
  var FONT_SANS = "'Geist','SF Pro Display',system-ui,sans-serif";
  var FONT_MONO = "'JetBrains Mono',Consolas,monospace";
  var STRIKE_WINDOW = 15; // ±strikes around ATM for the default x-range

  // ─── State ───────────────────────────────────────────────
  var state = {
    manifest: null,
    analysis: null,
    series: null,          // selected symbol
    latest: {},            // cache: symbol -> latest.json
    previous: {},          // cache: symbol -> previous.json | null
    view: 'oi'             // default view = Open Interest
  };

  // ─── DOM refs ────────────────────────────────────────────
  var $panel = document.getElementById('panel');
  var $stats = document.getElementById('stats');
  var $select = document.getElementById('series-select');
  var $nav = document.getElementById('nav');
  var $footUpdated = document.getElementById('foot-updated');
  var navButtons = Array.prototype.slice.call($nav.querySelectorAll('.nav-item'));

  // ─── Helpers ─────────────────────────────────────────────
  function fetchJSON(url) {
    return fetch(url, { cache: 'no-store' }).then(function (r) {
      if (!r.ok) throw new Error(r.status + ' ' + url);
      return r.json();
    });
  }
  // optional fetch: resolves to null on any failure (missing previous.json etc.)
  function fetchJSONOptional(url) {
    return fetchJSON(url).catch(function () { return null; });
  }
  function num(v, digits) {
    if (v === null || v === undefined || isNaN(v)) return '—';
    return Number(v).toLocaleString('en-US', {
      minimumFractionDigits: digits || 0, maximumFractionDigits: digits === undefined ? 0 : digits
    });
  }
  function pct(v, digits) {
    if (v === null || v === undefined || isNaN(v)) return '—';
    return Number(v).toFixed(digits === undefined ? 1 : digits) + '%';
  }
  function signed(v, digits) {
    if (v === null || v === undefined || isNaN(v)) return '—';
    var s = Number(v).toFixed(digits === undefined ? 1 : digits);
    return (v > 0 ? '+' : '') + s;
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function el(html) { var d = document.createElement('div'); d.innerHTML = html; return d.firstElementChild; }

  // x-range = ±STRIKE_WINDOW strikes around the ATM strike, given sorted strikes
  function strikeRange(strikes, atm) {
    if (!strikes.length) return null;
    var step = strikes.length > 1 ? Math.abs(strikes[1] - strikes[0]) : 10;
    var center = (atm != null) ? atm : strikes[Math.floor(strikes.length / 2)];
    var lo = center - (STRIKE_WINDOW + 0.5) * step;
    var hi = center + (STRIKE_WINDOW + 0.5) * step;
    return [lo, hi];
  }

  // shared Plotly layout base
  function baseLayout(extra) {
    var lay = {
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: FONT_SANS, size: 12, color: C.text2 },
      margin: { l: 56, r: 56, t: 18, b: 46 },
      bargap: 0.28, bargroupgap: 0.12,
      hovermode: 'x unified',
      hoverlabel: { font: { family: FONT_MONO, size: 12 }, bgcolor: '#fff', bordercolor: C.border },
      showlegend: false,
      xaxis: {
        title: { text: 'Strike', font: { size: 11, color: C.text3 } },
        gridcolor: C.border, zeroline: false, tickfont: { family: FONT_MONO, size: 11, color: C.text2 },
        showspikes: true, spikemode: 'across', spikethickness: 1, spikecolor: C.text3, spikedash: 'dot'
      },
      yaxis: {
        gridcolor: C.border, zeroline: true, zerolinecolor: C.border,
        tickfont: { family: FONT_MONO, size: 11, color: C.text2 }
      }
    };
    if (extra) Object.keys(extra).forEach(function (k) { lay[k] = extra[k]; });
    return lay;
  }
  var PLOT_CONFIG = { responsive: true, displaylogo: false,
    modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'] };

  // ─── Boot ────────────────────────────────────────────────
  function boot() {
    Promise.all([
      fetchJSON('./data/manifest.json'),
      fetchJSONOptional('./data/analysis.json')
    ]).then(function (res) {
      state.manifest = res[0];
      state.analysis = res[1];

      var series = (state.manifest.active_series || []).slice();
      if (!series.length) { renderFatal('No active series in manifest.'); return; }

      // populate dropdown
      $select.innerHTML = '';
      series.forEach(function (sym) {
        var o = document.createElement('option');
        o.value = sym; o.textContent = sym;
        $select.appendChild(o);
      });
      state.series = series[0];
      $select.value = state.series;

      if (state.manifest.updated) {
        $footUpdated.textContent = 'updated ' + state.manifest.updated;
      }

      wireUI();
      setActiveView(state.view, true);
      loadSeries(state.series).then(reRender);
    }).catch(function (e) {
      renderFatal('Could not load manifest.json — ' + e.message);
    });
  }

  function loadSeries(sym) {
    if (state.latest[sym]) return Promise.resolve();
    return Promise.all([
      fetchJSON('./data/series/' + sym + '/latest.json'),
      fetchJSONOptional('./data/series/' + sym + '/previous.json')
    ]).then(function (res) {
      state.latest[sym] = res[0];
      state.previous[sym] = res[1]; // may be null
    });
  }

  // ─── UI wiring ───────────────────────────────────────────
  function wireUI() {
    navButtons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        setActiveView(btn.getAttribute('data-view'));
        reRender();
        closeDrawer();
      });
    });
    $select.addEventListener('change', function () {
      state.series = $select.value;
      $panel.innerHTML = '<div class="empty-state"><h3>Loading…</h3><p>Fetching ' + esc(state.series) + '.</p></div>';
      loadSeries(state.series).then(reRender).catch(function (e) {
        renderFatal('Could not load ' + esc(state.series) + ' — ' + e.message);
      });
    });

    // mobile drawer
    var toggle = document.getElementById('nav-toggle');
    var scrim = document.getElementById('scrim');
    if (toggle) toggle.addEventListener('click', function () {
      document.body.classList.toggle('nav-open');
      scrim.hidden = !document.body.classList.contains('nav-open');
    });
    if (scrim) scrim.addEventListener('click', closeDrawer);

    window.addEventListener('resize', function () {
      var p = document.querySelector('.plot');
      if (p && window.Plotly) Plotly.Plots.resize(p);
    });
  }
  function closeDrawer() {
    document.body.classList.remove('nav-open');
    var scrim = document.getElementById('scrim');
    if (scrim) scrim.hidden = true;
  }
  function setActiveView(view, silent) {
    state.view = view;
    navButtons.forEach(function (b) {
      b.setAttribute('aria-current', b.getAttribute('data-view') === view ? 'true' : 'false');
    });
    if (!silent) { /* reRender called by caller */ }
  }

  // ─── Render dispatch ─────────────────────────────────────
  function reRender() {
    renderStats();
    var d = state.latest[state.series];
    if (!d && state.view !== 'analytics') {
      renderFatal('No chain data for ' + esc(state.series) + '.');
      return;
    }
    if (state.view === 'volume') renderVolume(d);
    else if (state.view === 'oi') renderOI(d);
    else if (state.view === 'oichg') renderOIChange(d, state.previous[state.series]);
    else if (state.view === 'analytics') renderAnalytics();
  }

  // ─── Stat strip ──────────────────────────────────────────
  function renderStats() {
    var d = state.latest[state.series];
    if (!d) { $stats.innerHTML = ''; return; }
    var t = d.totals || {};
    var chg = d.future_chg;
    var chgCls = chg > 0 ? 'up' : (chg < 0 ? 'down' : '');
    var rows = [
      ['Trading date', esc(d.trading_date || '—')],
      ['Future last', num(d.future_last, 1) + (chg != null
        ? ' <span class="chg ' + chgCls + '">' + signed(chg, 1) + '</span>' : '')],
      ['ATM strike', num(d.atm_strike, 0)],
      ['ATM IV', pct(d.iv_atm, 1)],
      ['P/C OI', num(t.pc_oi_ratio, 2)],
      ['Max pain', num(d.max_pain, 0)]
    ];
    $stats.innerHTML = rows.map(function (r) {
      return '<div class="stat"><div class="sl">' + r[0] + '</div><div class="sv">' + r[1] + '</div></div>';
    }).join('');
  }

  // ─── Chart card scaffold ─────────────────────────────────
  function chartCard(title, sub, legendHTML, note) {
    $panel.innerHTML =
      '<div class="view-head"><span class="view-title">' + title + '</span>' +
      (sub ? '<span class="view-sub">' + sub + '</span>' : '') + '</div>' +
      '<div class="chart-card">' +
      (legendHTML ? '<div class="chart-legend">' + legendHTML + '</div>' : '') +
      '<div class="plot" id="plot"></div>' +
      (note ? '<div class="chart-note">' + note + '</div>' : '') +
      '</div>';
    return document.getElementById('plot');
  }

  function legendItem(swClass, label) {
    return '<span class="lg"><span class="sw ' + swClass + '"></span>' + label + '</span>';
  }

  // ─── View: Volume ────────────────────────────────────────
  function renderVolume(d) {
    var chain = d.chain || [];
    var callX = [], callY = [], putX = [], putY = [];
    chain.forEach(function (row) {
      if (row.call && row.call.vol != null) { callX.push(row.strike); callY.push(row.call.vol); }
      if (row.put && row.put.vol != null) { putX.push(row.strike); putY.push(row.put.vol); }
    });
    var node = chartCard('Volume', 'Traded contracts by strike',
      legendItem('call', 'Call volume') + legendItem('put', 'Put volume'),
      'Default window ±' + STRIKE_WINDOW + ' strikes around ATM ' + num(d.atm_strike, 0) +
      ' — scroll / drag to zoom the full chain.');

    var traces = [
      bar('Call', callX, callY, C.call),
      bar('Put', putX, putY, C.put)
    ];
    var strikes = chain.map(function (r) { return r.strike; }).sort(function (a, b) { return a - b; });
    var lay = baseLayout({
      barmode: 'group',
      yaxis: Object.assign(baseLayout().yaxis, { title: { text: 'Volume', font: { size: 11, color: C.text3 } } })
    });
    lay.xaxis.range = strikeRange(strikes, d.atm_strike);
    lay.shapes = spotMaxPainShapes(d);
    lay.annotations = spotMaxPainAnnotations(d);
    Plotly.newPlot(node, traces, lay, PLOT_CONFIG);
  }

  // ─── View: Open Interest (+ IV lines + delta bands) ──────
  function renderOI(d) {
    var chain = d.chain || [];
    var callX = [], callY = [], putX = [], putY = [];
    var civX = [], civY = [], pivX = [], pivY = [];
    chain.forEach(function (row) {
      if (row.call && row.call.oi != null) { callX.push(row.strike); callY.push(row.call.oi); }
      if (row.put && row.put.oi != null) { putX.push(row.strike); putY.push(row.put.oi); }
      if (row.call && row.call.iv != null) { civX.push(row.strike); civY.push(row.call.iv); }
      if (row.put && row.put.iv != null) { pivX.push(row.strike); pivY.push(row.put.iv); }
    });

    var node = chartCard('Open Interest', 'Open contracts by strike, with the IV smile',
      legendItem('call', 'Call OI') + legendItem('put', 'Put OI') +
      '<span class="lg" style="color:' + C.callLine + '"><span class="sw line"></span>Call IV</span>' +
      '<span class="lg" style="color:' + C.putLine + '"><span class="sw line"></span>Put IV</span>' +
      legendItem('band25', '25Δ zone') + legendItem('band10', '10Δ zone'),
      'IV on right axis (dashed). Shaded bands = delta zones; lines = Spot ' + num(d.atm_strike, 0) +
      ' & Max pain ' + num(d.max_pain, 0) + '. ±' + STRIKE_WINDOW + ' strikes shown — zoom for the rest.');

    var traces = [
      bar('Call', callX, callY, C.call),
      bar('Put', putX, putY, C.put),
      ivLine('Call IV', civX, civY, C.callLine),
      ivLine('Put IV', pivX, pivY, C.putLine)
    ];

    var strikes = chain.map(function (r) { return r.strike; }).sort(function (a, b) { return a - b; });
    // Cap the IV axis to a readable window. Deep ITM/OTM strikes carry garbage
    // IVs (100%+) on the TFEX feed; left unbounded they crush the ATM smile.
    var atmIV = d.iv_atm || 20;
    var ivCap = Math.max(40, Math.min(90, Math.ceil(atmIV * 3 / 10) * 10));
    var lay = baseLayout({
      barmode: 'group',
      yaxis: Object.assign(baseLayout().yaxis, { title: { text: 'Open interest', font: { size: 11, color: C.text3 } } }),
      yaxis2: {
        title: { text: 'IV (%)', font: { size: 11, color: C.text3 } },
        overlaying: 'y', side: 'right', showgrid: false, zeroline: false,
        tickfont: { family: FONT_MONO, size: 11, color: C.text2 }, range: [0, ivCap]
      }
    });
    lay.xaxis.range = strikeRange(strikes, d.atm_strike);

    // delta-band rectangles + spot/max-pain lines
    lay.shapes = deltaBandShapes(d).concat(spotMaxPainShapes(d));
    lay.annotations = spotMaxPainAnnotations(d);
    Plotly.newPlot(node, traces, lay, PLOT_CONFIG);
  }

  // ─── View: OI Change ─────────────────────────────────────
  function renderOIChange(d, prev) {
    if (!prev || !prev.chain) {
      $panel.innerHTML =
        '<div class="view-head"><span class="view-title">OI Change</span></div>' +
        '<div class="empty-state"><h3>Not enough history yet</h3>' +
        '<p>OI change appears after two sessions. Come back once a previous session is archived.</p></div>';
      return;
    }
    // index previous by strike
    var pmap = {};
    prev.chain.forEach(function (r) { pmap[r.strike] = r; });

    var callX = [], callY = [], putX = [], putY = [];
    (d.chain || []).forEach(function (row) {
      var p = pmap[row.strike];
      if (!p) return;
      if (row.call && row.call.oi != null && p.call && p.call.oi != null) {
        callX.push(row.strike); callY.push(row.call.oi - p.call.oi);
      }
      if (row.put && row.put.oi != null && p.put && p.put.oi != null) {
        putX.push(row.strike); putY.push(row.put.oi - p.put.oi);
      }
    });

    var node = chartCard('OI Change', 'latest − previous open interest, by strike',
      legendItem('call', 'Call ΔOI') + legendItem('put', 'Put ΔOI'),
      'Positive = build, negative = unwind vs ' + esc(prev.trading_date || 'prior session') +
      '. ±' + STRIKE_WINDOW + ' strikes shown — zoom for the rest.');

    var traces = [
      bar('Call ΔOI', callX, callY, C.call),
      bar('Put ΔOI', putX, putY, C.put)
    ];
    var strikes = (d.chain || []).map(function (r) { return r.strike; }).sort(function (a, b) { return a - b; });
    var lay = baseLayout({
      barmode: 'group',
      yaxis: Object.assign(baseLayout().yaxis, { title: { text: 'Δ open interest', font: { size: 11, color: C.text3 } } })
    });
    lay.xaxis.range = strikeRange(strikes, d.atm_strike);
    lay.shapes = spotMaxPainShapes(d);
    lay.annotations = spotMaxPainAnnotations(d);
    Plotly.newPlot(node, traces, lay, PLOT_CONFIG);
  }

  // ─── Trace builders ──────────────────────────────────────
  function bar(name, x, y, color) {
    return {
      type: 'bar', name: name, x: x, y: y,
      marker: { color: color, line: { width: 0 } },
      hovertemplate: name + '  %{y:,}<extra></extra>'
    };
  }
  function ivLine(name, x, y, color) {
    return {
      type: 'scatter', mode: 'lines+markers', name: name, x: x, y: y, yaxis: 'y2',
      line: { color: color, width: 1.6, dash: 'dash', shape: 'spline' },
      marker: { color: color, size: 4 },
      hovertemplate: name + '  %{y:.1f}%<extra></extra>'
    };
  }

  // ─── Shapes / annotations ────────────────────────────────
  function deltaBandShapes(d) {
    var b = d.delta_bands || {};
    var shapes = [];
    // 25Δ zone: put_25d -> call_25d
    if (b.put_25d != null && b.call_25d != null) {
      shapes.push(bandRect(Math.min(b.put_25d, b.call_25d), Math.max(b.put_25d, b.call_25d),
        C.band25, C.band25line));
    }
    // 10Δ zone: put_10d -> call_10d (lighter, drawn under)
    if (b.put_10d != null && b.call_10d != null) {
      shapes.unshift(bandRect(Math.min(b.put_10d, b.call_10d), Math.max(b.put_10d, b.call_10d),
        C.band10, C.band10line));
    }
    return shapes;
  }
  function bandRect(x0, x1, fill, lineCol) {
    return {
      type: 'rect', xref: 'x', yref: 'paper', x0: x0, x1: x1, y0: 0, y1: 1,
      fillcolor: fill, line: { color: lineCol, width: 1, dash: 'dot' }, layer: 'below'
    };
  }
  function vline(x, color, dash) {
    return {
      type: 'line', xref: 'x', yref: 'paper', x0: x, x1: x, y0: 0, y1: 1,
      line: { color: color, width: 1.5, dash: dash || 'solid' }, layer: 'below'
    };
  }
  function spotMaxPainShapes(d) {
    var s = [];
    if (d.atm_strike != null) s.push(vline(d.atm_strike, C.spot, 'solid'));
    if (d.max_pain != null) s.push(vline(d.max_pain, C.maxpain, 'dashdot'));
    return s;
  }
  function spotMaxPainAnnotations(d) {
    var a = [];
    if (d.atm_strike != null) a.push(vAnno(d.atm_strike, 'Spot ' + num(d.atm_strike, 0), C.spot));
    if (d.max_pain != null) a.push(vAnno(d.max_pain, 'Max pain ' + num(d.max_pain, 0), C.maxpain));
    return a;
  }
  function vAnno(x, text, color) {
    return {
      x: x, y: 1, xref: 'x', yref: 'paper', yanchor: 'bottom', xanchor: 'center',
      text: text, showarrow: false, font: { family: FONT_SANS, size: 10.5, color: color },
      bgcolor: 'rgba(255,255,255,0.78)', borderpad: 2
    };
  }

  // ─── View: Analytics ─────────────────────────────────────
  function renderAnalytics() {
    var an = state.analysis;
    if (!an) {
      $panel.innerHTML = '<div class="view-head"><span class="view-title">Analytics</span></div>' +
        '<div class="empty-state error-state"><h3>No analysis available</h3>' +
        '<p>analysis.json did not load.</p></div>';
      return;
    }
    var by = an.by_series || {};
    var a = by[state.series] || by[an.primary];
    if (!a) {
      $panel.innerHTML = '<div class="view-head"><span class="view-title">Analytics</span></div>' +
        '<div class="empty-state"><h3>No analysis for ' + esc(state.series) + '</h3>' +
        '<p>The skill has not written a regime read for this series yet.</p></div>';
      return;
    }

    var sample = an._sample
      ? '<span class="sample-badge" title="Placeholder data — the live skill overwrites this">● sample</span>' : '';
    var parts = [];

    // Header line
    parts.push('<div class="view-head"><span class="view-title">Analytics</span>' +
      '<span class="view-sub">' + esc(a.series_label || a.symbol) +
      (a.dte != null ? ' · ' + a.dte + ' DTE' : '') +
      (a.trading_date ? ' · ' + esc(a.trading_date) : '') + '</span>' + sample + '</div>');

    parts.push('<div class="analytics">');

    // Regime card
    var rg = a.regime || {};
    var chips = [
      rg.gamma_posture && chip('Gamma', rg.gamma_posture),
      rg.zone && chip('Zone', rg.zone),
      rg.iv_state && chip('IV', rg.iv_state),
      rg.skew && chip('Skew', rg.skew)
    ].filter(Boolean).join('');
    var evidence = (rg.evidence || []).map(function (e) { return '<li>' + esc(e) + '</li>'; }).join('');
    parts.push(
      '<div class="card regime">' +
      '<div class="card-eyebrow">Regime</div>' +
      '<div class="regime-label">' + esc(rg.label || '—') + '</div>' +
      (chips ? '<div class="chips">' + chips + '</div>' : '') +
      (evidence ? '<ul class="evidence">' + evidence + '</ul>' : '') +
      '</div>'
    );

    // Breadth grid
    var br = a.breadth || {};
    parts.push(
      '<div class="card"><div class="card-eyebrow">Breadth</div>' +
      '<div class="breadth-grid">' +
      bcell('P/C OI', num(br.pc_oi_ratio, 2)) +
      bcell('P/C Vol', num(br.pc_vol_ratio, 2)) +
      bcell('Max pain', num(br.max_pain, 0)) +
      bcell('Call wall', num(br.call_wall, 0), br.near_call_wall != null ? 'near ' + num(br.near_call_wall, 0) : '') +
      bcell('Put wall', num(br.put_wall, 0), br.near_put_wall != null ? 'near ' + num(br.near_put_wall, 0) : '') +
      bcell('Gamma flip', num(br.gamma_flip, 0)) +
      bcell('1σ move', num(br.one_sigma_move, 1)) +
      bcell('ATM IV', pct(br.iv_atm, 1)) +
      bcell('25Δ skew', signed(br.iv_skew_25d, 1)) +
      '</div></div>'
    );

    // Today summary
    if (a.today_summary) {
      parts.push('<div class="card"><div class="card-eyebrow">Today</div>' +
        '<div class="prose"><p>' + esc(a.today_summary) + '</p></div></div>');
    }

    // What changed
    if (a.what_changed && a.what_changed.length) {
      parts.push('<div class="card"><div class="card-eyebrow">What changed</div>' +
        '<ul class="bullets">' + a.what_changed.map(function (w) { return '<li>' + esc(w) + '</li>'; }).join('') +
        '</ul></div>');
    }

    // 5-day thesis
    if (a.five_day_thesis) {
      parts.push('<div class="card"><div class="card-eyebrow">5-day thesis</div>' +
        '<div class="prose"><p>' + esc(a.five_day_thesis) + '</p></div></div>');
    }

    // Strategies
    if (a.strategies && a.strategies.length) {
      var cards = a.strategies.map(strategyCard).join('');
      parts.push('<div class="card"><div class="card-eyebrow">Strategies</div>' +
        '<div class="strat-grid">' + cards + '</div></div>');
    }

    // Prediction
    if (a.prediction) {
      parts.push('<div class="card"><div class="card-eyebrow">Prediction</div>' +
        '<div class="prediction">' + esc(a.prediction) + '</div></div>');
    }

    // Risk note
    if (a.risk_note) {
      parts.push('<div class="card"><div class="card-eyebrow">Risk note</div>' +
        '<div class="risk-note"><svg class="ico" width="18" height="18" viewBox="0 0 18 18" fill="none">' +
        '<path d="M9 2L1 15h16L9 2z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>' +
        '<path d="M9 7v3.5M9 12.6v.1" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>' +
        '<span>' + esc(a.risk_note) + '</span></div></div>');
    }

    parts.push('</div>'); // .analytics
    $panel.innerHTML = parts.join('');
  }

  function chip(k, v) {
    return '<span class="chip"><span class="k">' + esc(k) + '</span><b>' + esc(v) + '</b></span>';
  }
  function bcell(label, value, sub) {
    return '<div class="bcell"><div class="bl">' + esc(label) + '</div>' +
      '<div class="bv">' + value + (sub ? '<small>' + esc(sub) + '</small>' : '') + '</div></div>';
  }
  function strategyCard(s) {
    var dir = s.dir_axis ? '<span class="axis-chip dir">' + esc(s.dir_axis) + '</span>' : '';
    var volCls = (s.vol_axis === 'short') ? 'vol-short' : (s.vol_axis === 'long' ? 'vol-long' : 'dir');
    var vol = s.vol_axis ? '<span class="axis-chip ' + volCls + '">vol: ' + esc(s.vol_axis) + '</span>' : '';
    var legs = (s.example_legs || []).map(function (l) { return '<span class="leg">' + esc(l) + '</span>'; }).join('');
    return '<div class="strat">' +
      '<div class="strat-name">' + esc(s.name) + '</div>' +
      '<div class="strat-axes">' + dir + vol + '</div>' +
      (s.rationale ? '<div class="strat-rationale">' + esc(s.rationale) + '</div>' : '') +
      (legs ? '<div class="strat-field"><span class="fl">Example legs</span><div class="legs">' + legs + '</div></div>' : '') +
      (s.defined_risk ? '<div class="strat-field"><span class="fl">Defined risk</span><span class="risk">' + esc(s.defined_risk) + '</span></div>' : '') +
      (s.invalidation ? '<div class="strat-field"><span class="fl">Invalidation</span><span class="inval">' + esc(s.invalidation) + '</span></div>' : '') +
      '</div>';
  }

  // ─── Fatal ───────────────────────────────────────────────
  function renderFatal(msg) {
    $panel.innerHTML = '<div class="empty-state error-state"><h3>Something went wrong</h3><p>' + esc(msg) + '</p></div>';
  }

  // Object.assign / Promise polyfill-free (modern browsers); guard just in case
  if (!Object.assign) {
    Object.assign = function (t) {
      for (var i = 1; i < arguments.length; i++) {
        var s = arguments[i];
        for (var k in s) if (Object.prototype.hasOwnProperty.call(s, k)) t[k] = s[k];
      }
      return t;
    };
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
