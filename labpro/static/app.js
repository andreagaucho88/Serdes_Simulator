/* SerDes Optical Lab Pro — workbench a pannelli paralleli.
   Stato server-side (LiveBench) + WebSocket; i pannelli sono schede
   indipendenti che condividono la stessa configurazione versionata. */
"use strict";

/* ---------------- utilities ---------------- */
const $ = (sel, el = document) => el.querySelector(sel);
const CE = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
};
async function GET(url) { const r = await fetch(url); if (!r.ok) throw new Error((await r.json()).error || r.status); return r.json(); }
async function POST(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.status);
  return j;
}
const sci = (v, d = 2) => (v == null || !isFinite(v)) ? "—" : Number(v).toExponential(d).replace("e", "e");
const fix = (v, d = 2) => (v == null || !isFinite(v)) ? "—" : Number(v).toFixed(d);
const eng = (v) => {
  if (v == null || !isFinite(v)) return "—";
  const units = [[1e12, "T"], [1e9, "G"], [1e6, "M"], [1e3, "k"]];
  for (const [m, s] of units) if (Math.abs(v) >= m) return (v / m).toFixed(v / m >= 100 ? 0 : 2) + " " + s;
  return String(v);
};
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

const COL = { bg: "#0E141B", grid: "#1D2A36", ink: "#D7E1E8", muted: "#7E93A2",
  el: "#56C8E8", op: "#FF7A59", dg: "#B49CFF", am: "#E8C55A", ok: "#3ECF8E", fail: "#FF5470" };
const DOMC = { electrical: COL.el, optical: COL.op, digital: COL.dg };

function PL(overrides = {}) {
  return Object.assign({
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "#0B1117",
    font: { family: "IBM Plex Mono, monospace", size: 10.5, color: COL.ink },
    margin: { l: 48, r: 12, t: 26, b: 34 },
    xaxis: { gridcolor: COL.grid, zerolinecolor: COL.grid },
    yaxis: { gridcolor: COL.grid, zerolinecolor: COL.grid },
    showlegend: true, legend: { bgcolor: "rgba(0,0,0,0)", font: { size: 9.5 } },
    height: 260,
  }, overrides);
}
function mergeAxis(layout, key, extra) { layout[key] = Object.assign({}, layout[key], extra); return layout; }
function plot(el, traces, layout) { Plotly.react(el, traces, layout, { displayModeBar: false, responsive: true }); }
const vline = (x, color = COL.muted, dash = "dash") => ({ type: "line", x0: x, x1: x, yref: "paper", y0: 0, y1: 1, line: { color, dash, width: 1 } });
const hline = (y, color = COL.muted, dash = "dot") => ({ type: "line", y0: y, y1: y, xref: "paper", x0: 0, x1: 1, line: { color, dash, width: 1 } });

/* ---------------- stato globale ---------------- */
const S = { cfg: null, acc: null, running: false, presets: [], ws: null, panels: [] };

function cfgChips() {
  if (!S.cfg) return;
  const bps = S.cfg.modulation === "NRZ" ? 1 : 2;
  const gbs = bps * S.cfg.symbol_rate_hz / 1e9;
  // sottotitolo DINAMICO: mezzo e rate reali della configurazione corrente
  const medium = S.cfg.link_medium === "copper" ? "ELETTRICO (RAME)" : "ELETTRO-OTTICO";
  $("#brand-sub").textContent = `PRO · BANCO ${medium} · ${gbs.toFixed(gbs >= 100 ? 0 : 1)} Gb/s`;
  $("#chip-rate").textContent = (S.cfg.symbol_rate_hz / 1e9).toFixed(3) + " GBd · " + gbs.toFixed(1) + " Gb/s";
  const pat = S.cfg.pattern === "prbs" ? "PRBS" + S.cfg.prbs_order
    : (S.cfg.pattern === "eth" ? "ETH " + S.cfg.l2_frame_bytes + "B" : S.cfg.pattern);
  $("#chip-mod").textContent = S.cfg.modulation + (S.cfg.modulation === "PAM4" ? " " + S.cfg.pam4_mapping : "") + " · " + pat;
  const fecEl = $("#chip-fec");
  fecEl.textContent = S.cfg.fec_mode === "none" ? "FEC off" : "FEC " + S.cfg.fec_mode.toUpperCase() + " in-path";
  fecEl.classList.toggle("active", S.cfg.fec_mode !== "none");
  $("#sb-cfg-hash").textContent = "cfg#" + hashCfg(S.cfg) + (S.acc ? " · seed base 500000" : "");
}
function hashCfg(cfg) {
  const s = JSON.stringify(cfg); let h = 0;
  for (let i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) | 0; }
  return (h >>> 0).toString(16).slice(0, 8);
}

function tickTopbar() {
  const a = S.acc; if (!a) return;
  $("#tb-records").textContent = a.records;
  $("#tb-bits").textContent = eng(a.bits_total) + "b";
  const ci = a.ber_ci95 || [null, null];
  $("#tb-ber").textContent = a.bits_total ? sci(a.ber_cum) : "—";
  $("#tb-ber").title = "IC95% (iid): [" + sci(ci[0]) + ", " + sci(ci[1]) + "]";
  const f = a.fec || {};
  $("#tb-frames").textContent = f.frames_total ? `${f.frames_total} (${f.frames_lost} persi)` : "—";
  const cf = a.last ? a.last.checks_fail : 0;
  if (a.last && a.last.link_up === false) {
    $("#tb-checks").innerHTML = `<span class="fail">LINK DOWN</span>`;
  } else {
    $("#tb-checks").innerHTML = cf ? `<span class="fail">${cf} FAIL</span>` : `<span class="ok">PASS</span>`;
  }
  $("#led-run").classList.toggle("on", S.running);
  $("#btn-run").classList.toggle("running", S.running);
  $("#btn-run-label").textContent = S.running ? "STOP" : "RUN";
}

/* ---------------- WebSocket ---------------- */
function connectWS() {
  const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
  S.ws = ws;
  ws.onopen = () => $("#conn-banner").classList.add("hidden");
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.type === "hello") { S.cfg = m.cfg; S.running = m.running; S.acc = m.acc; cfgChips(); tickTopbar(); notify("config"); }
    if (m.type === "tick") { S.acc = m.acc; S.running = m.acc.running; tickTopbar(); notify("tick"); }
    if (m.type === "config") { S.cfg = m.cfg; cfgChips(); notify("config"); }
    if (m.type === "run") { S.running = m.running; tickTopbar(); }
  };
  ws.onclose = () => { $("#conn-banner").classList.remove("hidden"); setTimeout(connectWS, 1500); };
}
function notify(kind) {
  for (const p of S.panels) {
    try { if (kind === "config" && p.def.onConfig) p.def.onConfig(p); if (kind === "tick" && p.def.onTick) p.def.onTick(p); }
    catch (e) { console.warn("panel", p.type, e); }
  }
}

/* ---------------- parametri ---------------- */
const PARAMS = {
  symbol_rate_hz: { l: "Baud rate", u: "GBd", min: 20, max: 120, step: 0.125, scale: 1e9 },
  prbs_order: { l: "PRBS", type: "select", opts: [7, 9, 11, 13, 15, 23, 31] },
  modulation: { l: "Modulazione", type: "select", opts: ["PAM4", "NRZ"] },
  pam4_mapping: { l: "Mapping PAM4", type: "select", opts: ["gray", "binary"] },
  fec_mode: { l: "FEC nel percorso", type: "select", opts: ["none", "kp4", "kr4"],
    names: { none: "nessuno", kp4: "KP4 RS(544,514)", kr4: "KR4 RS(528,514)" } },
  tx_rj_rms_fs: { l: "RJ clock TX", u: "fs", min: 0, max: 1500, step: 25 },
  tx_pj_amp_ui: { l: "PJ ampiezza", u: "UI", min: 0, max: 0.3, step: 0.005 },
  tx_pj_freq_mhz: { l: "PJ frequenza", u: "MHz", min: 10, max: 3000, step: 10 },
  tx_dcd_pct: { l: "DCD", u: "%UI", min: 0, max: 25, step: 0.5 },
  dac_bits: { l: "Bit DAC", min: 4, max: 10, step: 1 },
  dac_bw_hz: { l: "Banda DAC", u: "GHz", min: 15, max: 60, step: 1, scale: 1e9 },
  dac_full_scale_vpp: { l: "FS DAC", u: "Vpp", min: 1, max: 4, step: 0.1 },
  driver_gain_v_per_unit: { l: "Gain driver", u: "V/u", min: 0.2, max: 1.5, step: 0.05 },
  driver_bw_hz: { l: "Banda driver", u: "GHz", min: 15, max: 60, step: 1, scale: 1e9 },
  driver_clip_v: { l: "Rail driver", u: "±V", min: 0.3, max: 1.5, step: 0.05 },
  channel_il_nyquist_db: { l: "IL @Nyquist", u: "dB", min: 2, max: 28, step: 0.5 },
  return_loss_db: { l: "Return loss", u: "dB", min: 6, max: 30, step: 1 },
  echo_delay_ui: { l: "Ritardo eco", u: "UI", min: 0.2, max: 4, step: 0.05 },
  group_delay_ripple_ps: { l: "Ripple GD", u: "ps", min: 0, max: 5, step: 0.1 },
  laser_dbm: { l: "P laser", u: "dBm", min: -6, max: 12, step: 0.5 },
  vpi_v: { l: "Vπ", u: "V", min: 1.5, max: 6, step: 0.1 },
  mzm_bias_rad: { l: "Bias MZM", u: "rad", min: 0.6, max: 2.6, step: 0.02 },
  mzm_bw_hz: { l: "Banda MZM", u: "GHz", min: 15, max: 60, step: 1, scale: 1e9 },
  mzm_il_db: { l: "IL MZM", u: "dB", min: 1, max: 9, step: 0.25 },
  chirp_alpha: { l: "Chirp α", min: -1.5, max: 1.5, step: 0.05 },
  coupling_il_db: { l: "Coupling IL", u: "dB", min: 0, max: 6, step: 0.25 },
  fiber_km: { l: "Fibra", u: "km", min: 0, max: 20, step: 0.25 },
  dispersion_ps_nm_km: { l: "D", u: "ps/nm·km", min: -25, max: 25, step: 0.5 },
  wavelength_nm: { l: "λ", u: "nm", min: 1260, max: 1610, step: 5 },
  fiber_loss_db_km: { l: "Loss fibra", u: "dB/km", min: 0.1, max: 0.6, step: 0.01 },
  n_symbols: { l: "Simboli/record", type: "select", opts: [4095, 6143, 8191, 12287, 16383] },
  pattern: { l: "Pattern (PPG)", type: "select", opts: ["prbs", "clock2", "clock8", "eth"],
    names: { prbs: "PRBS", clock2: "clock 0101", clock8: "clock 4+4", eth: "frame Ethernet (L2)" } },
  l2_frame_bytes: { l: "Frame size", u: "B", min: 64, max: 1024, step: 32 },
  link_medium: { l: "Mezzo del link", type: "select", opts: ["optical", "copper"],
    names: { optical: "ottico (MZM+fibra+PD)", copper: "rame (KR/CR/C2M)" } },
  pn_skew_ps: { l: "Skew P/N", u: "ps", min: 0, max: 10, step: 0.25 },
  pn_gain_mismatch_pct: { l: "Mismatch P/N", u: "%", min: 0, max: 30, step: 1 },
  vcm_offset_v: { l: "V_cm offset", u: "V", min: -0.3, max: 0.3, step: 0.01 },
  vcm_noise_mv: { l: "Rumore CM", u: "mVrms", min: 0, max: 200, step: 5 },
  xtalk_next_db: { l: "NEXT @Nyq", u: "dB", min: -60, max: 0, step: 1 },
  xtalk_fext_db: { l: "FEXT @Nyq", u: "dB", min: -60, max: 0, step: 1 },
  s4p_pairs: { l: "Porte s4p", type: "select", opts: ["13_24", "12_34"],
    names: { "13_24": "P/N = 1,3 → 2,4", "12_34": "P/N = 1,2 → 3,4" } },
  training_start: { l: "Inizio training", u: "simboli", min: 100, max: 2500, step: 50 },
  pd_dark_current_a: { l: "Dark current", u: "nA", min: 0, max: 100, step: 1, scale: 1e-9 },
  pd_saturation_a: { l: "Saturazione PD", u: "mA", min: 0.05, max: 3, step: 0.05, scale: 1e-3 },
  pd_responsivity_a_w: { l: "Responsivity", u: "A/W", min: 0.3, max: 1.1, step: 0.05 },
  pd_bw_hz: { l: "Banda PD", u: "GHz", min: 20, max: 70, step: 1, scale: 1e9 },
  rin_db_hz: { l: "RIN", u: "dB/Hz", min: -160, max: -125, step: 1 },
  tia_noise_a_rt_hz: { l: "Rumore TIA", u: "pA/√Hz", min: 5, max: 80, step: 1, scale: 1e-12 },
  tia_transimpedance_ohm: { l: "Z_T", u: "Ω", min: 500, max: 6000, step: 100 },
  tia_bw_hz: { l: "Banda TIA", u: "GHz", min: 15, max: 60, step: 1, scale: 1e9 },
  tia_clip_v: { l: "Clip TIA", u: "±V", min: 0.2, max: 1.5, step: 0.05 },
  agc_target_rms_v: { l: "Target AGC", u: "Vrms", min: 0.05, max: 0.5, step: 0.01 },
  ctle_zero_hz: { l: "Zero", u: "GHz", min: 2, max: 24, step: 0.5, scale: 1e9 },
  ctle_pole_hz: { l: "Polo", u: "GHz", min: 8, max: 45, step: 0.5, scale: 1e9 },
  ctle_hf_pole_hz: { l: "Polo alto", u: "GHz", min: 30, max: 90, step: 1, scale: 1e9 },
  ctle_dc_gain_db: { l: "Gain DC", u: "dB", min: -12, max: 6, step: 0.5 },
  adc_bits: { l: "Bit ADC", min: 4, max: 10, step: 1 },
  adc_full_scale_vpp: { l: "FS ADC", u: "Vpp", min: 0.6, max: 2.5, step: 0.05 },
  adc_jitter_rms_fs: { l: "Jitter apertura", u: "fs", min: 0, max: 400, step: 10 },
  adc_phase_ui: { l: "Fase camp.", u: "UI", min: -0.4, max: 0.4, step: 0.01 },
  adc_gain_mismatch_rms: { l: "Gain mism.", u: "%", min: 0, max: 3, step: 0.05, scale: 0.01 },
  adc_offset_mismatch_rms_v: { l: "Offset mism.", u: "mV", min: 0, max: 8, step: 0.1, scale: 1e-3 },
  adc_skew_mismatch_rms_fs: { l: "Skew mism.", u: "fs", min: 0, max: 200, step: 5 },
  cdr_mode: { l: "Modo CDR", type: "select", opts: ["gardner", "mm", "oracle"],
    names: { gardner: "Gardner (2 sps)", mm: "Mueller-Müller", oracle: "oracle (ideale)" } },
  cdr_bw: { l: "Banda loop", u: "·f_baud", min: 0.0002, max: 0.006, step: 0.0002 },
  cdr_damping: { l: "Damping ζ", min: 0.5, max: 2.0, step: 0.1 },
  rx_ppm_offset: { l: "Offset clock RX", u: "ppm", min: -300, max: 300, step: 10 },
  fse_taps: { l: "Tap FSE", min: 5, max: 31, step: 2 },
  dfe_taps: { l: "Tap DFE", min: 1, max: 12, step: 1 },
  training_stop: { l: "Fine training", u: "simboli", min: 600, max: 6000, step: 50 },
  causal_filters: { l: "Filtri causali", type: "select", opts: [false, true],
    names: { false: "fase zero (v7)", true: "Butterworth causale" } },
};
let _pendingCfg = {};
const _flushCfg = debounce(() => {
  const updates = _pendingCfg; _pendingCfg = {};
  POST("/api/config", { updates }).catch(e => toast(e.message));
}, 260);
function postConfig(updates) { Object.assign(_pendingCfg, updates); _flushCfg(); }

function mkParam(field) {
  const d = PARAMS[field];
  const wrap = CE("div", "param");
  wrap.dataset.field = field;
  if (d.type === "select") {
    const lab = CE("label", "", `<span>${d.l}</span>`);
    const sel = CE("select");
    for (const o of d.opts) {
      const opt = CE("option"); opt.value = String(o);
      opt.textContent = d.names ? d.names[o] : String(o);
      sel.appendChild(opt);
    }
    sel.value = String(S.cfg[field]);
    sel.onchange = () => {
      let v = sel.value;
      if (v === "true") v = true; else if (v === "false") v = false;
      else if (!isNaN(Number(v)) && typeof d.opts[0] === "number") v = Number(v);
      postConfig({ [field]: v });
    };
    wrap.append(lab, sel);
  } else {
    const scale = d.scale || 1;
    const cur = S.cfg[field] / scale;
    const lab = CE("label", "", `<span>${d.l}</span><b>${fix(cur, d.step < 0.1 ? 2 : (d.step < 1 ? 1 : 0))}${d.u ? " " + d.u : ""}</b>`);
    const rng = CE("input"); rng.type = "range"; rng.min = d.min; rng.max = d.max; rng.step = d.step; rng.value = cur;
    rng.oninput = () => {
      lab.querySelector("b").textContent = fix(Number(rng.value), d.step < 0.1 ? 2 : (d.step < 1 ? 1 : 0)) + (d.u ? " " + d.u : "");
      const v = Number(rng.value) * scale;
      postConfig({ [field]: d.step >= 1 && scale === 1 ? Math.round(v) : v });
    };
    wrap.append(lab, rng);
  }
  return wrap;
}
function syncParams(root) {
  for (const el of root.querySelectorAll(".param")) {
    const field = el.dataset.field, d = PARAMS[field];
    if (!d || S.cfg[field] === undefined) continue;
    if (d.type === "select") { el.querySelector("select").value = String(S.cfg[field]); }
    else {
      const scale = d.scale || 1, cur = S.cfg[field] / scale;
      const rng = el.querySelector("input"); if (document.activeElement === rng) continue;
      rng.value = cur;
      el.querySelector("label b").textContent = fix(cur, d.step < 0.1 ? 2 : (d.step < 1 ? 1 : 0)) + (d.u ? " " + d.u : "");
    }
  }
}
function paramsBlock(fields) { const g = CE("div", "params"); for (const f of fields) g.appendChild(mkParam(f)); return g; }
function toast(msg) { $("#sb-note").innerHTML = `<span class="fail">${msg}</span>`; setTimeout(() => { $("#sb-note").textContent = "Laboratorio didattico con proxy dichiarati."; }, 5000); }

/* ---------------- readout helper ---------------- */
function readout(items) {
  const g = CE("div", "readout");
  for (const it of items) {
    const ro = CE("div", "ro" + (it.big ? " big" : ""));
    ro.innerHTML = `<label>${it.l}</label><b class="${it.cls || ""}">${it.v}</b>` + (it.sub ? `<span class="sub">${it.sub}</span>` : "");
    if (it.title) ro.title = it.title;
    g.appendChild(ro);
  }
  return g;
}

/* ================= PANNELLI ================= */
const NODE_OPTS = {
  vctle: "Uscita CTLE", vtia: "Uscita TIA/AFE",
  pfiber: "P ottica al PD", pmzm: "P ottica MZM",
  chan: "Uscita canale", driver: "Driver (diff. ideale)",
  vp: "V_p (ramo P)", vn: "V_n (ramo N)", vdiff: "V_diff", vcm: "V_cm",
};
const OPTICAL_NODES = new Set(["pfiber", "pmzm"]);
function nodeSelect(panel, cb, def = "vctle") {
  const sel = CE("select");
  const fill = () => {
    const cur = sel.value || def;
    sel.innerHTML = "";
    for (const [k, v] of Object.entries(NODE_OPTS)) {
      if (S.cfg && S.cfg.link_medium === "copper" && OPTICAL_NODES.has(k)) continue;
      const o = CE("option"); o.value = k; o.textContent = v; sel.appendChild(o);
    }
    sel.value = [...sel.options].some(o => o.value === cur) ? cur : "vctle";
  };
  fill();
  sel.value = def; sel.onchange = cb; sel._refill = fill;
  const firstBtn = panel.head.querySelector(".icon-btn");
  panel.head.insertBefore(sel, firstBtn);
  return sel;
}

const PANEL_DEFS = {};

/* --- catena --- */
PANEL_DEFS.chain = {
  title: "Catena del segnale", domain: null, size: "s12",
  make(p) {
    p.body.innerHTML = "";
    p.svgHost = CE("div");
    p.body.appendChild(p.svgHost);
    p.body.appendChild(CE("div", "note", "Clicca un blocco per aprire il suo pannello. I blocchi FEC sono attivi solo con FEC in-path (pannello FEC live)."));
    this.onConfig(p);
  },
  onConfig(p) {
    const fecOn = S.cfg.fec_mode !== "none";
    const copper = S.cfg.link_medium === "copper";
    const jitOn = S.cfg.tx_rj_rms_fs > 0 || S.cfg.tx_pj_amp_ui > 0 || S.cfg.tx_dcd_pct > 0;
    const ethOn = S.cfg.pattern === "eth";
    const rows = [
      [["stim", ethOn ? "PPG·ETH" : "PPG", "dg", "stimulus"], ["fenc", "FEC enc", fecOn ? "dg" : "off", "feclive"], ["map", "Mapper", "dg", "stimulus"], ["ser", "SER (MUX)", "dg", "serpll"], ["ffe", "TX FFE", "dg", "tx"], ["dac", "DAC", "el", "tx"], ["drv", "Driver P/N", "el", "serpll"], ["ch", "Canale", "el", "channel"], ["mzm", "MZM", copper ? "off" : "op", "optical"], ["fib", "Fibra", copper ? "off" : "op", "optical"]],
      [["pd", "PD", copper ? "off" : "el", "scope"], ["tia", copper ? "AFE" : "TIA·AGC", "el", "scope"], ["ctle", "CTLE", "el", "ctle"], ["adc", "ADC", "dg", "adc"], ["cdr", "CDR", "ck", "timing"], ["fse", "FSE", "dg", "eq"], ["dfe", "DFE", "dg", "eq"], ["slc", "Slicer", "dg", "decisions"], ["dmx", "DEMUX", "dg", "decisions"], ["fdec", ethOn ? "FEC·L2" : "FEC dec", fecOn || ethOn ? "dg" : "off", ethOn ? "l2" : "feclive"]],
    ];
    const W = 98, H = 42, G = 13, X0 = 18, Y = [42, 130];
    const cmap = { el: COL.el, op: COL.op, dg: COL.dg, ck: COL.am, off: "#3A4854" };
    let svg = `<svg class="chain-svg" viewBox="0 0 ${X0 * 2 + 10 * W + 9 * G} 200" xmlns="http://www.w3.org/2000/svg" font-family="IBM Plex Mono, monospace">`;
    // TX PLL sopra il serializer (clock domain in ambra)
    const pllX = X0 + 3 * (W + G) + 8, pllC = jitOn ? COL.am : "#5A5142";
    svg += `<a data-target="serpll"><rect x="${pllX}" y="4" width="${W - 16}" height="26" rx="7" fill="rgba(232,197,90,0.06)" stroke="${pllC}" stroke-width="1.2"/>
      <text x="${pllX + (W - 16) / 2}" y="21" text-anchor="middle" fill="${pllC}" font-size="10">TX PLL${jitOn ? " ⚡" : ""}</text></a>
      <line x1="${X0 + 3 * (W + G) + W / 2}" y1="30" x2="${X0 + 3 * (W + G) + W / 2}" y2="${Y[0]}" stroke="${pllC}" stroke-width="1.2" stroke-dasharray="3 3"/>`;
    // clock CDR → ADC
    const cdrX = X0 + 4 * (W + G) + W / 2, adcX = X0 + 3 * (W + G) + W / 2;
    svg += `<path d="M ${cdrX} ${Y[1] + H} v 10 H ${adcX} v -10" fill="none" stroke="${COL.am}" stroke-width="1.1" stroke-dasharray="3 3"/>
      <text x="${(cdrX + adcX) / 2}" y="${Y[1] + H + 22}" text-anchor="middle" fill="${COL.am}" font-size="8.5">clock recuperato</text>`;
    rows.forEach((row, ri) => {
      row.forEach(([id, label, dom, target], i) => {
        const x = X0 + i * (W + G), y = Y[ri], c = cmap[dom];
        svg += `<a data-target="${target}"><g opacity="${dom === "off" ? 0.45 : 1}">
          <rect data-b="${id}" x="${x}" y="${y}" width="${W}" height="${H}" rx="8" fill="rgba(255,255,255,0.03)" stroke="${c}" stroke-width="1.3"><title></title></rect>
          <text x="${x + W / 2}" y="${y + H / 2 + 4}" text-anchor="middle" fill="${COL.ink}" font-size="11.5">${label}</text></g></a>`;
        if (i < row.length - 1) {
          const nc = cmap[row[i + 1][2]];
          svg += `<line x1="${x + W}" y1="${y + H / 2}" x2="${x + W + G}" y2="${y + H / 2}" stroke="${nc}" stroke-width="1.4"/>`;
        }
      });
    });
    const fx = X0 + 9 * (W + G) + W, fy = Y[0] + H / 2, px = X0, py = Y[1] + H / 2;
    svg += `<path d="M ${fx} ${fy} h 6 q 7 0 7 7 V ${(Y[0] + H + Y[1]) / 2} H ${px - 12} q -7 0 -7 7 V ${py - 7} q 0 7 7 7 h 10" fill="none" stroke="${COL.op}" stroke-width="1.5"/>`;
    // reference plane E/O (prima del MZM, idx 8) e A/D (all'ADC, riga 2 idx 3)
    const eoX = X0 + 8 * (W + G) - G / 2, adX = X0 + 3 * (W + G) - G / 2;
    svg += `<line x1="${eoX}" y1="${Y[0] - 6}" x2="${eoX}" y2="${Y[0] + H + 6}" stroke="${COL.muted}" stroke-dasharray="4 4" stroke-width="1"/>
      <text x="${eoX}" y="${Y[0] + H + 15}" text-anchor="middle" fill="${COL.muted}" font-size="9">E/O</text>
      <line x1="${adX}" y1="${Y[1] - 6}" x2="${adX}" y2="${Y[1] + H + 6}" stroke="${COL.muted}" stroke-dasharray="4 4" stroke-width="1"/>
      <text x="${adX - 14}" y="${Y[1] - 10}" text-anchor="middle" fill="${COL.muted}" font-size="9">A/D</text>`;
    svg += `</svg>`;
    p.svgHost.innerHTML = svg;
    for (const a of p.svgHost.querySelectorAll("a")) a.onclick = () => addPanel(a.dataset.target);
    this.health(p);
  },
  async health(p) {
    // salute dei blocchi: i checkpoint FAIL accendono in rosso il blocco
    // responsabile (l'effetto di ogni manopola diventa visibile in catena)
    const MAP = [["Driver non dominato", "drv"], ["Photodiode fuori", "pd"],
      ["TIA fuori overload", "tia"], ["ADC non dominato", "adc"],
      ["CDR ", "cdr"], ["Pattern lock", "cdr"], ["Occupazione", "stim"],
      ["FSE migliora", "fse"], ["DFE non degrada", "dfe"],
      ["nel percorso: post-FEC", "fdec"], ["LINK DOWN", "slc"],
      ["GMI", "slc"]];
    try {
      const d = await GET("/api/panel/checks");
      const bad = {};
      for (const c of d.checks) {
        if (c.status !== "FAIL") continue;
        for (const [pat, blk] of MAP) if (c.check.includes(pat)) {
          bad[blk] = (bad[blk] ? bad[blk] + " · " : "") + c.check;
        }
      }
      for (const r of p.svgHost.querySelectorAll("rect[data-b]")) {
        const msg = bad[r.dataset.b];
        if (msg) {
          r.setAttribute("stroke", COL.fail);
          r.setAttribute("stroke-width", "2.6");
          r.setAttribute("fill", "rgba(255,84,112,0.10)");
          r.querySelector("title").textContent = "CHECKPOINT FAIL: " + msg;
        }
      }
      let led = p.body.querySelector(".chain-led");
      if (!led) { led = CE("div", "chain-led scope-bar"); p.body.insertBefore(led, p.body.lastChild); }
      const n = Object.keys(bad).length;
      led.innerHTML = n
        ? `<span class="fail">● ${n} blocco/i con checkpoint FAIL (bordo rosso — passaci sopra per il dettaglio)</span>`
        : `<span class="ok">● tutti i checkpoint della catena PASS</span>`;
    } catch (e) { /* pannello checks non disponibile: nessun colore */ }
  },
};

/* --- scope DCA --- */
function hexToRgb(hex) { return [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)]; }
PANEL_DEFS.scope = {
  title: "Scope · DCA", size: "s8", multi: true,
  make(p) {
    p.node = "vctle"; p.persist = 8; p.rate = 12; p.idx = 0; p.count = 0; p.paused = false;
    p.mode = "densità"; p.cursorUi = null; p.maskOn = false; p.maskW = 30; p.maskH = 40;
    p.headSel = nodeSelect(p, () => { p.node = p.headSel.value; this.refetch(p); });
    p.body.innerHTML = "";
    p.canvas = CE("canvas", "scope"); p.canvas.width = 1000; p.canvas.height = 380;
    p.body.appendChild(p.canvas);
    p.acc = new Float32Array(p.canvas.width * p.canvas.height);
    const bar = CE("div", "scope-bar");
    bar.innerHTML = `
      <select data-k="mode"><option>densità</option><option>fosforo</option></select>
      <span>persist <input type="range" min="1" max="30" value="8" data-k="persist"></span>
      <span>rate <input type="range" min="1" max="40" value="12" data-k="rate"></span>
      <button class="icon-btn" data-k="pause">⏸</button>
      <label><input type="checkbox" data-k="overlay" checked> livelli/soglie</label>
      <label><input type="checkbox" data-k="cursor"> cursore</label>
      <input type="range" min="-90" max="90" value="0" data-k="curpos" style="width:90px" disabled>
      <label><input type="checkbox" data-k="mask"> mask</label>
      <input type="range" min="5" max="70" value="30" data-k="maskw" style="width:60px" title="larghezza mask %UI" disabled>
      <input type="range" min="5" max="80" value="40" data-k="maskh" style="width:60px" title="altezza mask %eye" disabled>
      <span data-k="readout"></span>`;
    const q = k => bar.querySelector(`[data-k=${k}]`);
    q("mode").onchange = e => { p.mode = e.target.value; p.acc.fill(0); };
    q("persist").oninput = e => p.persist = +e.target.value;
    q("rate").oninput = e => p.rate = +e.target.value;
    q("pause").onclick = e => { p.paused = !p.paused; e.target.textContent = p.paused ? "▶" : "⏸"; };
    p.overlayChk = q("overlay");
    q("cursor").onchange = e => { q("curpos").disabled = !e.target.checked; p.cursorUi = e.target.checked ? +q("curpos").value / 100 : null; };
    q("curpos").oninput = e => p.cursorUi = +e.target.value / 100;
    q("mask").onchange = e => { p.maskOn = e.target.checked; q("maskw").disabled = q("maskh").disabled = !p.maskOn; this.maskCount(p); };
    q("maskw").oninput = e => { p.maskW = +e.target.value; this.maskCount(p); };
    q("maskh").oninput = e => { p.maskH = +e.target.value; this.maskCount(p); };
    p.readoutEl = q("readout");
    p.body.appendChild(bar);
    p.measHost = CE("div"); p.body.appendChild(p.measHost);
    p.traces = []; p.lastFetch = 0;
    this.refetch(p);

    const cGrid = "rgba(126,147,162,.15)";
    const drawGrid = (ctx, W, H) => {
      ctx.strokeStyle = cGrid; ctx.setLineDash([2, 5]);
      for (let i = 1; i < 10; i++) { ctx.beginPath(); ctx.moveTo(W * i / 10, 0); ctx.lineTo(W * i / 10, H); ctx.stroke(); }
      for (let j = 1; j < 8; j++) { ctx.beginPath(); ctx.moveTo(0, H * j / 8); ctx.lineTo(W, H * j / 8); ctx.stroke(); }
      ctx.setLineDash([]);
    };
    const rasterize = (tr, W, H) => {  // accumula la polilinea nella density map
      const [vmin, vmax] = p.vrange, n = tr.length;
      let px = 0, py = H - (tr[0] - vmin) / (vmax - vmin) * H;
      for (let i = 1; i < n; i++) {
        const x = W * i / (n - 1), y = H - (tr[i] - vmin) / (vmax - vmin) * H;
        const steps = Math.max(Math.abs(x - px), Math.abs(y - py)) | 0;
        for (let s = 0; s <= steps; s++) {
          const xi = (px + (x - px) * s / (steps || 1)) | 0, yi = (py + (y - py) * s / (steps || 1)) | 0;
          if (xi >= 0 && xi < W && yi >= 0 && yi < H) p.acc[yi * W + xi] += 1;
        }
        px = x; py = y;
      }
    };
    const frame = () => {
      if (!p.el.isConnected) return;
      const ctx = p.canvas.getContext("2d"), W = p.canvas.width, H = p.canvas.height;
      if (p.traces.length && !p.paused) {
        const [vmin, vmax] = p.vrange;
        const yof = v => H - (v - vmin) / (vmax - vmin) * H;
        if (p.mode === "densità") {
          const decay = 1 - 0.35 / p.persist;
          for (let i = 0; i < p.acc.length; i++) p.acc[i] *= decay;
          for (let k = 0; k < p.rate; k++) { rasterize(p.traces[p.idx], W, H); p.idx = (p.idx + 1) % p.traces.length; p.count++; }
          if (!p.img) p.img = ctx.createImageData(W, H);
          const d = p.img.data, [cr, cg, cb] = hexToRgb(p.color || COL.el);
          let amax = 0; for (let i = 0; i < p.acc.length; i += 7) if (p.acc[i] > amax) amax = p.acc[i];
          const inv = amax > 0 ? 1 / Math.log1p(amax) : 0;
          for (let i = 0; i < p.acc.length; i++) {
            const t = Math.log1p(p.acc[i]) * inv;  // 0..1 log-compresso
            const j = i * 4;
            if (t <= 0.001) { d[j] = 4; d[j + 1] = 7; d[j + 2] = 10; d[j + 3] = 255; continue; }
            // colormap DCA: scuro → colore dominio → ambra → bianco
            let r, g, b;
            if (t < 0.5) { const u = t / 0.5; r = 4 + (cr - 4) * u; g = 7 + (cg - 7) * u; b = 10 + (cb - 10) * u; }
            else if (t < 0.8) { const u = (t - 0.5) / 0.3; r = cr + (232 - cr) * u; g = cg + (197 - cg) * u; b = cb + (90 - cb) * u; }
            else { const u = (t - 0.8) / 0.2; r = 232 + 23 * u; g = 197 + 58 * u; b = 90 + 165 * u; }
            d[j] = r; d[j + 1] = g; d[j + 2] = b; d[j + 3] = 255;
          }
          ctx.putImageData(p.img, 0, 0);
          drawGrid(ctx, W, H);
        } else {
          ctx.fillStyle = `rgba(4,7,10,${1.8 / p.persist})`; ctx.fillRect(0, 0, W, H);
          ctx.globalCompositeOperation = "lighter"; ctx.globalAlpha = 0.16;
          ctx.strokeStyle = p.color || COL.el; ctx.lineWidth = 1.1;
          for (let k = 0; k < p.rate; k++) {
            const tr = p.traces[p.idx]; p.idx = (p.idx + 1) % p.traces.length; p.count++;
            ctx.beginPath();
            for (let i = 0; i < tr.length; i++) { const x = W * i / (tr.length - 1); i ? ctx.lineTo(x, yof(tr[i])) : ctx.moveTo(x, yof(tr[i])); }
            ctx.stroke();
          }
          ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over";
        }
        // overlay livelli/soglie
        if (p.overlayChk.checked && p.meas) {
          ctx.setLineDash([5, 4]);
          for (const lv of p.meas.levels) { ctx.strokeStyle = "rgba(215,225,232,.35)"; ctx.beginPath(); ctx.moveTo(0, yof(lv.mean)); ctx.lineTo(W, yof(lv.mean)); ctx.stroke(); }
          for (const th of p.meas.thresholds) { ctx.strokeStyle = "rgba(62,207,142,.5)"; ctx.beginPath(); ctx.moveTo(0, yof(th)); ctx.lineTo(W, yof(th)); ctx.stroke(); }
          ctx.setLineDash([]);
        }
        // cursore + istogramma verticale
        if (p.cursorUi != null) {
          const col = Math.round((p.cursorUi + 1) / 2 * (p.traces[0].length - 1));
          const x = W * col / (p.traces[0].length - 1);
          ctx.strokeStyle = COL.am; ctx.setLineDash([6, 4]);
          ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); ctx.setLineDash([]);
          const bins = 60, hist = new Float32Array(bins);
          for (const tr of p.traces) {
            const b = Math.min(bins - 1, Math.max(0, ((tr[col] - vmin) / (vmax - vmin) * bins) | 0));
            hist[b]++;
          }
          const hmax = Math.max(...hist);
          ctx.fillStyle = "rgba(232,197,90,.55)";
          for (let b = 0; b < bins; b++) {
            const bw = hist[b] / hmax * 90;
            ctx.fillRect(W - bw - 4, H - (b + 1) / bins * H, bw, H / bins - 1);
          }
          ctx.fillStyle = COL.am; ctx.font = "10px IBM Plex Mono";
          ctx.fillText(`t = ${p.cursorUi.toFixed(2)} UI`, x + 6, 14);
        }
        // mask test
        if (p.maskOn && p.meas && p.maskRects) {
          for (const r of p.maskRects) {
            ctx.strokeStyle = p.maskHits > 0 ? COL.fail : COL.ok;
            ctx.setLineDash([3, 3]);
            ctx.strokeRect(W * r.x0, yof(r.v1), W * (r.x1 - r.x0), yof(r.v0) - yof(r.v1));
            ctx.setLineDash([]);
          }
          ctx.fillStyle = p.maskHits > 0 ? COL.fail : COL.ok;
          ctx.font = "11px IBM Plex Mono";
          ctx.fillText(`mask: ${p.maskHits} hit su ${p.traces.length} tracce`, 8, H - 8);
        }
        p.readoutEl.textContent = `redraw ${p.count} · buffer ${p.traces.length} tracce · 2 UI`;
      }
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  },
  maskCount(p) {
    if (!p.maskOn || !p.meas || !p.traces.length) { p.maskRects = null; return; }
    const n = p.traces[0].length, cc = (n - 1) / 2;
    const wpx = p.maskW / 100 * (n - 1) / 2;   // %UI → colonne (2 UI = n colonne)
    const c0 = Math.round(cc - wpx / 2), c1 = Math.round(cc + wpx / 2);
    const rects = [];
    const L = p.meas.levels;
    for (let i = 0; i < L.length - 1; i++) {
      const lo = L[i].mean, hi = L[i + 1].mean, mid = (lo + hi) / 2;
      const half = (hi - lo) * p.maskH / 100 / 2;
      rects.push({ c0, c1, v0: mid - half, v1: mid + half, x0: c0 / (n - 1), x1: c1 / (n - 1) });
    }
    let hits = 0;
    for (const tr of p.traces) {
      let hit = false;
      for (const r of rects) {
        for (let c = r.c0; c <= r.c1 && !hit; c++) if (tr[c] > r.v0 && tr[c] < r.v1) hit = true;
        if (hit) break;
      }
      if (hit) hits++;
    }
    p.maskRects = rects; p.maskHits = hits;
  },
  async refetch(p) {
    try {
      if (p.headSel && p.headSel._refill) { p.headSel._refill(); p.node = p.headSel.value; }
      const d = await GET(`/api/panel/eye?node=${p.node}&n=600&source=${S.running ? "live" : "auto"}`);
      // node o configurazione cambiati: azzera la density map (mai mescolare
      // acquisizioni con scale/configurazioni diverse)
      const key = p.node + "|" + hashCfg(S.cfg);
      if (key !== p.accKey) { p.acc.fill(0); p.accKey = key; }
      p.traces = d.traces; p.color = DOMC[d.domain]; p.unit = d.unit; p.meas = d.meas;
      let vmin = Infinity, vmax = -Infinity;
      for (const tr of d.traces) for (const v of tr) { if (v < vmin) vmin = v; if (v > vmax) vmax = v; }
      const pad = 0.12 * (vmax - vmin || 1); p.vrange = [vmin - pad, vmax + pad];
      this.maskCount(p);
      const m = d.meas, items = [];
      const eyes = ["basso", "medio", "alto"].slice(0, m.eye_heights.length);
      items.push({ l: "allineamento", v: d.align, sub: "centro strumento " + fix(m.center_offset_ui, 2) + " UI dal CDR", title: "il DCA autocentra la misura sulla massima apertura; l'offset mostra dove campiona il CDR rispetto all'ottimo" });
      m.eye_heights.forEach((h, i) => items.push({ l: `eye ${eyes[i]} H/W`, v: `${fix(h, 3)} / ${fix(m.eye_widths_ui[i], 2)} UI`, cls: h > 0 ? "" : "fail", title: "height p1–p99 al centro strumento / larghezza a p1-p99 (frazione UI)" }));
      items.push({ l: "Q per occhio", v: m.q_per_eye.map(q => fix(q, 1)).join(" · ") });
      if (m.t_rise_ps != null) items.push({ l: "rise/fall 20-80", v: `${fix(m.t_rise_ps, 1)} / ${fix(m.t_fall_ps, 1)} ps` });
      if (m.rlm_proxy != null) items.push({ l: "RLM proxy", v: fix(m.rlm_proxy, 3) });
      if (m.oma_outer_mw != null) { items.push({ l: "OMA outer", v: fix(m.oma_outer_mw, 3) + " mW", cls: "warn" }); items.push({ l: "ER", v: fix(m.er_db, 2) + " dB", cls: "warn" }); }
      p.measHost.innerHTML = ""; p.measHost.appendChild(readout(items));
    } catch (e) { p.measHost.innerHTML = `<div class="note w">${e.message}</div>`; }
  },
  onConfig(p) { this.refetch(p); },
  onTick(p) { const now = Date.now(); if (now - p.lastFetch > 1800) { p.lastFetch = now; this.refetch(p); } },
};

/* --- spettro --- */
PANEL_DEFS.spectrum = {
  title: "Spectrum analyzer", size: "s6",
  make(p) {
    p.node = "vtia";
    p.headSel = nodeSelect(p, () => { p.node = p.headSel.value; this.refetch(p); }, "vtia");
    p.body.innerHTML = ""; p.plotEl = CE("div", "plot"); p.body.appendChild(p.plotEl);
    p.info = CE("div", "scope-bar"); p.body.appendChild(p.info);
    p.lastFetch = 0; this.refetch(p);
  },
  async refetch(p) {
    if (p.headSel && p.headSel._refill) { p.headSel._refill(); p.node = p.headSel.value; }
    const d = await GET(`/api/panel/spectrum?node=${p.node}&source=${S.running ? "live" : "auto"}`);
    const traces = [{ x: d.f_ghz, y: d.psd_db, name: d.label, line: { color: COL.el, width: 1.2 } }];
    if (d.model_db) traces.push({ x: d.f_ghz, y: d.model_db, name: "floor noise budget", line: { color: COL.am, dash: "dash", width: 1.6 } });
    const layout = PL({ height: 280, shapes: [vline(d.nyquist_ghz)] });
    mergeAxis(layout, "xaxis", { title: { text: "GHz", font: { size: 10 } } });
    mergeAxis(layout, "yaxis", { title: { text: "dB rel 1 " + d.unit, font: { size: 10 } } });
    plot(p.plotEl, traces, layout);
    p.info.textContent = `Welch/Hann · RBW ${fix(d.rbw_mhz, 1)} MHz · PSD one-sided`;
  },
  onConfig(p) { this.refetch(p); },
  onTick(p) { const now = Date.now(); if (now - p.lastFetch > 2500) { p.lastFetch = now; this.refetch(p); } },
};

/* --- CTLE dedicato --- */
PANEL_DEFS.ctle = {
  title: "CTLE — equalizzatore lineare", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    p.body.appendChild(paramsBlock(["ctle_zero_hz", "ctle_pole_hz", "ctle_hf_pole_hz", "ctle_dc_gain_db"]));
    p.ro = CE("div"); p.body.appendChild(p.ro);
    p.plotMag = CE("div", "plot"); p.body.appendChild(p.plotMag);
    p.plotGd = CE("div", "plot"); p.body.appendChild(p.plotGd);
    p.body.appendChild(CE("div", "note", "L'ottimo non è 'canale piatto': è il compromesso fra ISI residua e noise enhancement. Vincolo fisico: f_zero < f_polo < f_polo alto."));
    this.refetch(p);
  },
  async refetch(p) {
    const d = await GET("/api/panel/ctle");
    p.ro.innerHTML = "";
    p.ro.appendChild(readout([
      { l: "peaking", v: fix(d.peaking_db, 1) + " dB", sub: "@ " + fix(d.f_peak_ghz, 0) + " GHz" },
      { l: "noise enh.", v: fix(d.noise_enh_db, 2) + " dB", cls: d.noise_enh_db > 3 ? "warn" : "" },
      { l: "zero/polo/alto", v: `${fix(d.zero_ghz, 1)}/${fix(d.pole_ghz, 0)}/${fix(d.hf_ghz, 0)}`, sub: "GHz" },
    ]));
    const lm = PL({ height: 210, shapes: [vline(d.nyquist_ghz)] });
    mergeAxis(lm, "xaxis", { title: { text: "GHz", font: { size: 10 } } });
    mergeAxis(lm, "yaxis", { title: { text: "dB", font: { size: 10 } } });
    plot(p.plotMag, [
      { x: d.f_ghz, y: d.mag_db, name: "CTLE", line: { color: COL.ok, width: 2 } },
      { x: d.fch_ghz, y: d.chan_db, name: "canale", line: { color: COL.muted, dash: "dot" } },
      { x: d.fch_ghz, y: d.combo_db, name: "canale × CTLE", line: { color: COL.el, width: 2 } },
    ], lm);
    const lg = PL({ height: 170, showlegend: false });
    mergeAxis(lg, "xaxis", { title: { text: "GHz", font: { size: 10 } } });
    mergeAxis(lg, "yaxis", { title: { text: "group delay [ps]", font: { size: 10 } } });
    plot(p.plotGd, [{ x: d.f_ghz, y: d.gd_ps, line: { color: COL.dg } }], lg);
  },
  onConfig(p) { syncParams(p.body); this.refetch(p); },
};

/* --- FEC live --- */
PANEL_DEFS.feclive = {
  title: "FEC live — accumulo", size: "s4",
  make(p) {
    p.body.innerHTML = "";
    p.body.appendChild(paramsBlock(["fec_mode"]));
    p.ro = CE("div"); p.body.appendChild(p.ro);
    p.hist = CE("div", "plot"); p.body.appendChild(p.hist);
    p.note = CE("div", "note", "I contatori si riempiono record dopo record (acquisizione continua). Cambiare configurazione azzera l'accumulo.");
    p.body.appendChild(p.note);
    this.onTick(p);
  },
  onTick(p) {
    const a = S.acc; if (!a) return;
    const f = a.fec;
    const post = f.postfec_ber;
    const postTxt = f.postfec_bits ? (post > 0 ? sci(post) : "< " + sci(3 / f.postfec_bits)) : "—";
    // etichetta onesta: senza FEC in-path è una what-if analysis sul pattern
    p.head.querySelector(".t").textContent = f.in_path
      ? `FEC live — ${f.codec} in-path`
      : "FEC what-if — analisi del pattern (nessun FEC nel percorso)";
    p.ro.innerHTML = "";
    if (a.last && a.last.link_up === false) {
      p.ro.appendChild(readout([{ l: "LINK", v: "DOWN", cls: "fail", big: true, sub: "nessun frame decodificabile" }]));
      return;
    }
    const items = [
      { l: "frame accumulati", v: String(f.frames_total), big: true, sub: "solo codeword interamente in validation" },
      { l: "clean / corretti / persi", v: `${f.frames_clean} / ${f.frames_corrected} / ${f.frames_lost}`, cls: f.frames_lost ? "fail" : "ok" },
    ];
    if (f.in_path) items.push(
      { l: "MISCORRETTI", v: String(f.frames_miscorrected || 0), cls: (f.frames_miscorrected || 0) > 0 ? "fail" : "ok", title: "il decoder ha 'corretto' verso un ALTRO codeword valido: su hardware reale sarebbe invisibile (undetected errors) — qui lo vediamo solo perché conosciamo il TX" },
      { l: "simboli corretti", v: String(f.symbols_corrected) },
      { l: "post-FEC BER", v: postTxt, cls: !(post > 0) ? "ok" : "", sub: eng(f.postfec_bits) + "b payload", title: "con zero errori: upper bound 95% ≈ 3/N" });
    items.push({ l: "FLR", v: sci(f.flr), cls: f.flr > 0 ? "fail" : "ok" });
    p.ro.appendChild(readout(items));
    // ISTOGRAMMA ACCUMULATO: distribuzione dei symbol errors per codeword,
    // cresce nel tempo (asse y log). La riga rossa è la capacità t.
    const hist = f.epf_hist || [];
    const maxBin = Math.max(f.t + 6, hist.reduce((m, v, i) => v ? i : m, 0) + 2);
    const xs = [], ys = [], colors = [];
    for (let i = 0; i <= Math.min(maxBin, 40); i++) {
      xs.push(i === 40 ? "≥40" : String(i)); ys.push(hist[i] || 0);
      colors.push(i > f.t ? COL.fail : (i ? COL.am : COL.ok));
    }
    const lay = PL({ height: 170, showlegend: false, shapes: [vline(f.t + 0.5, COL.fail, "dash")] });
    mergeAxis(lay, "xaxis", { title: { text: "symbol errors per codeword (t=" + f.t + ")", font: { size: 9 } }, type: "category" });
    mergeAxis(lay, "yaxis", { title: { text: "frame (cum.)", font: { size: 9 } }, type: "log" });
    plot(p.hist, [{ x: xs, y: ys, type: "bar", marker: { color: colors } }], lay);
  },
  onConfig(p) { syncParams(p.body); },
};

/* --- serializer + TX PLL (jitter injection) + coppia P/N --- */
PANEL_DEFS.serpll = {
  title: "Serializer · TX PLL · uscita P/N", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    p.body.appendChild(paramsBlock(["tx_rj_rms_fs", "tx_pj_amp_ui", "tx_pj_freq_mhz", "tx_dcd_pct",
      "pn_skew_ps", "pn_gain_mismatch_pct", "vcm_offset_v", "vcm_noise_mv"]));
    p.ro = CE("div"); p.body.appendChild(p.ro);
    p.body.appendChild(CE("div", "note", "Il jitter è iniettato sul time base del serializer/DAC (reference plane: clock TX), un offset per UI. Misuralo nel pannello <b>Jitter · TIE</b>: al driver vedi ciò che hai iniettato + il DDJ del pattern; al CTLE si somma tutto il canale."));
    this.onConfig(p);
  },
  onConfig(p) {
    syncParams(p.body);
    const ui_ps = 1e12 / S.cfg.symbol_rate_hz;
    p.ro.innerHTML = "";
    p.ro.appendChild(readout([
      { l: "RJ iniettato", v: fix(S.cfg.tx_rj_rms_fs / 1000, 2) + " ps", sub: fix(S.cfg.tx_rj_rms_fs * 1e-3 / ui_ps, 4) + " UI rms" },
      { l: "PJ iniettato", v: fix(S.cfg.tx_pj_amp_ui * ui_ps, 2) + " ps pk", sub: "@ " + fix(S.cfg.tx_pj_freq_mhz, 0) + " MHz" },
      { l: "DCD", v: fix(S.cfg.tx_dcd_pct / 100 * ui_ps, 2) + " ps pp", sub: fix(S.cfg.tx_dcd_pct, 1) + " %UI" },
      { l: "skew P/N", v: fix(S.cfg.pn_skew_ps, 2) + " ps", sub: "notch DM a " + (S.cfg.pn_skew_ps > 0 ? fix(500 / S.cfg.pn_skew_ps, 0) + " GHz" : "∞"), title: "lo skew fra i rami filtra il differenziale: notch a 1/(2τ)" },
      { l: "UI", v: fix(ui_ps, 2) + " ps" },
    ]));
    p.ro.appendChild(CE("div", "note", "Osserva V_p, V_n, V_diff e V_cm come nodi dello Scope: lo sbilanciamento P/N fa trapelare il common-mode nel differenziale."));
  },
};

/* --- jitter / TIE --- */
PANEL_DEFS.jitter = {
  title: "Jitter · TIE", size: "s6",
  make(p) {
    p.node = "driver";
    p.headSel = nodeSelect(p, () => { p.node = p.headSel.value; this.refetch(p); }, "driver");
    p.body.innerHTML = "";
    p.ro = CE("div"); p.body.appendChild(p.ro);
    p.plotH = CE("div", "plot"); p.body.appendChild(p.plotH);
    p.plotS = CE("div", "plot"); p.body.appendChild(p.plotS);
    p.note = CE("div", "note w"); p.body.appendChild(p.note);
    p.lastFetch = 0;
    this.refetch(p);
  },
  async refetch(p) {
    try {
      if (p.headSel && p.headSel._refill) { p.headSel._refill(); p.node = p.headSel.value; }
      const d = await GET(`/api/panel/jitter?node=${p.node}&source=${S.running ? "live" : "auto"}`);
      p.ro.innerHTML = "";
      p.ro.appendChild(readout([
        { l: "TIE rms", v: fix(d.tie_rms_ps, 2) + " ps", big: true, sub: d.n_edges + " crossing" },
        { l: "TIE pk-pk", v: fix(d.tie_pp_ps, 2) + " ps" },
        { l: "RJ est.", v: fix(d.rj_est_ps, 2) + " ps", sub: "iniettato " + fix(d.injected.rj_fs / 1000, 2) + " ps", title: "stima dual-Dirac grezza: include il DDJ del pattern" },
        { l: "DJ est.", v: fix(d.dj_est_ps, 2) + " ps pp", sub: "PJ inj " + fix(d.injected.pj_ui * d.ui_ps, 2) + " ps · DCD " + fix(d.injected.dcd_pct / 100 * d.ui_ps, 2) + " ps" },
      ]));
      const l1 = PL({ height: 170, showlegend: false });
      mergeAxis(l1, "xaxis", { title: { text: "TIE [UI] — istogramma dei crossing (soglia media)", font: { size: 9 } } });
      mergeAxis(l1, "yaxis", { type: "log", title: { text: "conteggio", font: { size: 9 } } });
      plot(p.plotH, [{ x: d.hist_x_ui, y: d.hist, type: "bar", marker: { color: COL.dg } }], l1);
      const shapes = [];
      if (d.injected.pj_ui > 0) shapes.push(vline(d.injected.pj_mhz, COL.am, "dash"));
      const l2 = PL({ height: 170, showlegend: false, shapes });
      mergeAxis(l2, "xaxis", { type: "log", title: { text: "frequenza [MHz] (ambra = PJ iniettato)", font: { size: 9 } } });
      mergeAxis(l2, "yaxis", { title: { text: "TIE [mUI]", font: { size: 9 } } });
      plot(p.plotS, [{ x: d.spec_f_mhz, y: d.spec_mag_mui, line: { color: COL.dg, width: 1 } }], l2);
      p.note.innerHTML = `Allineamento: ${d.align}. Su PAM4 i crossing della soglia centrale portano un <b>DDJ pattern-dependent</b> intrinseco: l'istogramma multimodale è fisica, non rumore. Le stime RJ/DJ sono un fit dual-Dirac dichiaratamente grezzo (risoluzione spettro ≈ ${fix(1e3 / (S.cfg.n_symbols / (S.cfg.symbol_rate_hz / 1e9)), 1)} MHz).`;
    } catch (e) { p.note.innerHTML = e.message; }
  },
  onConfig(p) { this.refetch(p); },
  onTick(p) { const now = Date.now(); if (now - p.lastFetch > 3000) { p.lastFetch = now; this.refetch(p); } },
};

/* --- BER live --- */
PANEL_DEFS.berlive = {
  title: "BER live — accumulo", size: "s4",
  make(p) { p.body.innerHTML = ""; p.ro = CE("div"); p.body.appendChild(p.ro); p.trend = CE("div", "plot"); p.body.appendChild(p.trend); this.onTick(p); },
  onTick(p) {
    const a = S.acc; if (!a) return;
    const ci = a.ber_ci95 || [];
    p.ro.innerHTML = "";
    if (a.last && a.last.link_up === false) {
      p.ro.appendChild(readout([
        { l: "LINK", v: "DOWN", cls: "fail", big: true, sub: "CDR o pattern lock non agganciano: nessun bit valido" },
        { l: "record scartati", v: String(a.link_down_records || 0), cls: "fail" },
      ]));
      plot(p.trend, [], PL({ height: 120, showlegend: false }));
      return;
    }
    p.ro.appendChild(readout([
      { l: "BER cumulativa", v: a.bit_errors_total ? sci(a.ber_cum) : (a.bits_total ? "< " + sci(ci[1]) : "—"), big: true, sub: `${eng(a.bit_errors_total)} err / ${eng(a.bits_total)}b`, title: "IC 95% con ipotesi IID: gli errori correlati dal DFE lo allargano" },
      { l: "ultimo record", v: sci(a.last.ber), sub: "GMI " + fix(a.last.gmi, 3) },
      { l: "SNR slicer", v: fix(a.last.snr_db, 1) + " dB", sub: "Q min " + fix(a.last.q_min, 2) },
      { l: "P @ PD", v: fix(a.last.p_pd_dbm, 2) + " dBm" },
    ]));
    const lay = PL({ height: 150, showlegend: false });
    mergeAxis(lay, "yaxis", { type: "log", title: { text: "BER cum.", font: { size: 9 } } });
    mergeAxis(lay, "xaxis", { title: { text: "record", font: { size: 9 } } });
    plot(p.trend, [{ y: a.ber_history, line: { color: COL.dg, width: 1.5 } }], lay);
  },
};

/* --- pannelli parametrici + plot --- */
PANEL_DEFS.stimulus = {
  title: "PPG — pattern e modulazione", size: "s6",
  make(p) { p.body.innerHTML = ""; p.body.appendChild(paramsBlock(["symbol_rate_hz", "pattern", "prbs_order", "modulation", "pam4_mapping", "l2_frame_bytes", "n_symbols"])); p.plotEl = CE("div", "plot"); p.body.appendChild(p.plotEl); this.refetch(p); },
  async refetch(p) {
    const d = await GET("/api/panel/stimulus");
    const lay = PL({ height: 210, showlegend: false });
    mergeAxis(lay, "xaxis", { title: { text: "simbolo", font: { size: 10 } } });
    plot(p.plotEl, [{ y: d.symbols, line: { shape: "hv", color: COL.dg } }], lay);
  },
  onConfig(p) { syncParams(p.body); this.refetch(p); },
};

PANEL_DEFS.tx = {
  title: "TX — FFE · DAC · driver", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    p.ffe = CE("div", "params");
    ["pre", "main", "post"].forEach((name, i) => {
      const w = CE("div", "param"); w.dataset.ffe = i;
      const lims = [[-0.35, 0], [0.5, 1.2], [-0.35, 0]][i];
      const lab = CE("label", "", `<span>FFE ${name}</span><b>${fix(S.cfg.tx_ffe_taps[i], 2)}</b>`);
      const rng = CE("input"); rng.type = "range"; rng.min = lims[0]; rng.max = lims[1]; rng.step = 0.01; rng.value = S.cfg.tx_ffe_taps[i];
      rng.oninput = () => { lab.querySelector("b").textContent = fix(+rng.value, 2);
        const taps = [...S.cfg.tx_ffe_taps]; taps[i] = +rng.value; postConfig({ tx_ffe_taps: taps }); };
      w.append(lab, rng); p.ffe.appendChild(w);
    });
    p.body.appendChild(p.ffe);
    p.body.appendChild(paramsBlock(["dac_bits", "dac_bw_hz", "dac_full_scale_vpp", "driver_gain_v_per_unit", "driver_bw_hz", "driver_clip_v", "causal_filters"]));
    p.body.appendChild(CE("div", "note w", "Il clipping del driver è non invertibile: nessun equalizzatore a valle ricostruisce i picchi tagliati."));
  },
  onConfig(p) { syncParams(p.body);
    for (const w of p.ffe.querySelectorAll("[data-ffe]")) { const i = +w.dataset.ffe; const r = w.querySelector("input");
      if (document.activeElement !== r) { r.value = S.cfg.tx_ffe_taps[i]; w.querySelector("label b").textContent = fix(S.cfg.tx_ffe_taps[i], 2); } } },
};

PANEL_DEFS.channel = {
  title: "Canale elettrico · mezzo · crosstalk", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    p.body.appendChild(paramsBlock(["link_medium", "channel_il_nyquist_db", "return_loss_db", "echo_delay_ui", "group_delay_ripple_ps", "xtalk_next_db", "xtalk_fext_db", "s4p_pairs"]));
    p.body.appendChild(CE("div", "note", "NEXT/FEXT a 0 dB = spenti; valori negativi = accoppiamento dell'aggressore (PRBS indipendente). In modalità <b>rame</b> la catena ottica è bypassata: canale → AFE (profili KR/CR/C2M)."));
    p.src = CE("div"); p.body.appendChild(p.src);
    p.plotS = CE("div", "plot"); p.body.appendChild(p.plotS);
    p.plotC = CE("div", "plot"); p.body.appendChild(p.plotC);
    const up = CE("div", "scope-bar");
    up.innerHTML = `<input type="file" accept=".s2p,.S2P,.txt" style="font-size:11px"> <button class="btn" style="padding:3px 9px">usa S2P nel percorso</button> <button class="btn" style="padding:3px 9px">torna al modello</button>`;
    const [fileEl, btnUse, btnBack] = up.querySelectorAll("input,button");
    btnUse.onclick = async () => {
      const f = fileEl.files[0]; if (!f) return toast("scegli un file .s2p");
      const text = await f.text();
      POST("/api/s2p", { text, name: f.name, apply: true }).catch(e => toast(e.message));
    };
    btnBack.onclick = () => postConfig({ use_s2p_channel: false });
    p.body.appendChild(up);
    this.refetch(p);
  },
  async refetch(p) {
    const d = await GET("/api/panel/channel");
    p.src.innerHTML = `<div class="note">Canale attivo: <b>${d.source}</b></div>`;
    const l1 = PL({ height: 190, showlegend: false, shapes: [vline(d.nyquist_ghz)] });
    mergeAxis(l1, "xaxis", { title: { text: "GHz", font: { size: 10 } } });
    mergeAxis(l1, "yaxis", { title: { text: "|S21| dB", font: { size: 10 } } });
    plot(p.plotS, [{ x: d.f_ghz, y: d.s21_db, line: { color: COL.el } }], l1);
    const l2 = PL({ height: 190, showlegend: false });
    mergeAxis(l2, "xaxis", { title: { text: "cursor [UI]", font: { size: 10 } } });
    mergeAxis(l2, "yaxis", { title: { text: "p[k]/p[0]", font: { size: 10 } } });
    plot(p.plotC, [{ x: d.cursor_ui, y: d.cursor_val, type: "bar", marker: { color: COL.el } }], l2);
  },
  onConfig(p) { syncParams(p.body); this.refetch(p); },
};

PANEL_DEFS.optical = {
  title: "Ottica — MZM · fibra", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    p.body.appendChild(paramsBlock(["laser_dbm", "vpi_v", "mzm_bias_rad", "mzm_bw_hz", "mzm_il_db", "chirp_alpha", "coupling_il_db", "fiber_km", "dispersion_ps_nm_km", "wavelength_nm", "fiber_loss_db_km"]));
    p.ro = CE("div"); p.body.appendChild(p.ro);
    p.plot1 = CE("div", "plot"); p.body.appendChild(p.plot1);
    p.plot2 = CE("div", "plot"); p.body.appendChild(p.plot2);
    this.refetch(p);
  },
  async refetch(p) {
    const d = await GET("/api/panel/optical");
    p.ro.innerHTML = "";
    p.ro.appendChild(readout([
      { l: "P @ PD", v: fix(d.budget["PD input"], 2) + " dBm" },
      { l: "drive picco", v: fix(d.drive_peak_v, 2) + " V", sub: fix(d.drive_peak_v / d.vpi, 2) + "·Vπ" },
      { l: "1º nullo IM/DD", v: d.f_null_ghz ? fix(d.f_null_ghz, 1) + " GHz" : "∞", cls: d.f_null_ghz && d.f_null_ghz < d.nyquist_ghz ? "fail" : "" },
    ]));
    const l1 = PL({ height: 180, showlegend: false });
    mergeAxis(l1, "xaxis", { title: { text: "drive [V]", font: { size: 10 } } });
    mergeAxis(l1, "yaxis", { title: { text: "P/P_in", font: { size: 10 } } });
    plot(p.plot1, [{ x: d.v_static, y: d.p_static, line: { color: COL.op, width: 2 } }], l1);
    const l2 = PL({ height: 180, showlegend: false, shapes: [vline(d.nyquist_ghz)] });
    mergeAxis(l2, "xaxis", { title: { text: "GHz", font: { size: 10 } } });
    mergeAxis(l2, "yaxis", { title: { text: "fading CD dB", font: { size: 10 } }, range: [-50, 5] });
    plot(p.plot2, [{ x: d.fade_f_ghz, y: d.fade_db, line: { color: COL.op } }], l2);
  },
  onConfig(p) { syncParams(p.body); this.refetch(p); },
};

PANEL_DEFS.adc = {
  title: "ADC interleaved", size: "s6",
  make(p) { p.body.innerHTML = ""; p.body.appendChild(paramsBlock(["adc_bits", "adc_full_scale_vpp", "adc_jitter_rms_fs", "adc_phase_ui", "adc_gain_mismatch_rms", "adc_offset_mismatch_rms_v", "adc_skew_mismatch_rms_fs"])); p.plotEl = CE("div", "plot"); p.body.appendChild(p.plotEl); p.tbl = CE("div"); p.body.appendChild(p.tbl); this.refetch(p); },
  async refetch(p) {
    const d = await GET("/api/panel/adc");
    if (d.tone_f_ghz) {
      const lay = PL({ height: 220, shapes: (d.lines_ghz || []).map(x => vline(x, COL.fail, "dot")) });
      mergeAxis(lay, "yaxis", { range: [-110, 5], title: { text: "dBFS", font: { size: 10 } } });
      mergeAxis(lay, "xaxis", { title: { text: "GHz", font: { size: 10 } } });
      plot(p.plotEl, [
        { x: d.tone_f_ghz, y: d.tone_ideal_db, name: "quantizzazione", line: { color: COL.muted, width: 1 } },
        { x: d.tone_f_ghz, y: d.tone_mm_db, name: "con mismatch", line: { color: COL.dg, width: 1 } }], lay);
      p.tbl.innerHTML = `<div class="readout">
        <div class="ro"><label>SNDR</label><b>${fix(d.sndr[1], 1)} dB</b><span class="sub">ideale ${fix(d.sndr[0], 1)}</span></div>
        <div class="ro"><label>ENOB</label><b>${fix(d.enob[1], 2)}</b><span class="sub">bit (tono, non PAM4)</span></div>
        <div class="ro"><label>LSB / clip</label><b>${fix(d.lsb_mv, 2)} mV</b><span class="sub">${fix(d.clip_pct, 3)}%</span></div></div>`;
    } else { p.plotEl.innerHTML = ""; p.tbl.innerHTML = `<div class="note">Tone-lab disponibile dopo la prima run full (attendi un attimo e ricambia un parametro).</div>`; }
  },
  onConfig(p) { syncParams(p.body); this.refetch(p); },
};

PANEL_DEFS.timing = {
  title: "Timing · CDR (nel datapath)", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    p.body.appendChild(paramsBlock(["cdr_mode", "cdr_bw", "cdr_damping", "rx_ppm_offset"]));
    p.ro = CE("div"); p.body.appendChild(p.ro);
    p.plot1 = CE("div", "plot"); p.body.appendChild(p.plot1);
    p.plot2 = CE("div", "plot"); p.body.appendChild(p.plot2);
    p.note = CE("div", "note"); p.body.appendChild(p.note);
    this.refetch(p);
  },
  async refetch(p) {
    const d = await GET("/api/panel/timing");
    p.ro.innerHTML = "";
    if (d.cdr) {
      const c = d.cdr;
      p.ro.appendChild(readout([
        { l: "CDR " + d.mode, v: c.locked ? "LOCKED" : "UNLOCKED", cls: c.locked ? "ok" : "fail", sub: c.locked ? `lock @ simbolo ${c.lock_symbol}` : c.detail, big: true },
        { l: "pattern lock (BERT)", v: c.pattern_locked ? "SYNC" : "NO SYNC", cls: c.pattern_locked ? "ok" : "fail", sub: c.pattern_lag != null ? `lag ${c.pattern_lag} · |corr| ${fix(Math.abs(c.pattern_corr), 2)}` : "—" },
        { l: "cycle slips", v: String(c.cycle_slips), cls: c.cycle_slips ? "fail" : "ok" },
        { l: "link", v: d.link_up ? "UP" : "DOWN", cls: d.link_up ? "ok" : "fail", sub: c.ppm_set ? `offset impostato ${c.ppm_set} ppm` : "" },
      ]));
      const l1 = PL({ height: 170, showlegend: false });
      mergeAxis(l1, "xaxis", { title: { text: "simbolo (×" + c.sub + ")", font: { size: 9 } } });
      mergeAxis(l1, "yaxis", { title: { text: "fase NCO [UI]", font: { size: 9 } } });
      plot(p.plot1, [{ y: c.tau, line: { color: COL.dg, width: 1.2 } }], l1);
      const shapes = c.ppm_set ? [hline(-c.ppm_set, COL.ok, "dash")] : [];
      const l2 = PL({ height: 170, showlegend: false, shapes });
      mergeAxis(l2, "xaxis", { title: { text: "simbolo (×" + c.sub + ")", font: { size: 9 } } });
      mergeAxis(l2, "yaxis", { title: { text: "registro freq [ppm]", font: { size: 9 } } });
      plot(p.plot2, [{ y: c.fppm, line: { color: COL.am, width: 1.2 } }], l2);
      p.note.innerHTML = "Loop PI del 2° ordine + NCO <b>nel datapath</b>: gli istanti di campionamento di FSE/DFE/BER sono quelli del loop; l'allineamento viene dal pattern lock, non da un oracle. Senza lock il link è DOWN e le metriche non esistono.";
    } else if (d.phase_ui) {
      p.ro.appendChild(readout([
        { l: "modalità", v: "ORACLE (ideale)", cls: "warn", sub: "riferimento dichiarato, non un ricevitore" },
        { l: "delay + fase", v: `${d.delay >= 0 ? "+" : ""}${d.delay} UI · ${fix(d.best_phase, 3)}` },
      ]));
      const l1 = PL({ height: 200, showlegend: false, shapes: [vline(d.best_phase, COL.ok)] });
      mergeAxis(l1, "xaxis", { title: { text: "fase [UI]", font: { size: 10 } } });
      mergeAxis(l1, "yaxis", { title: { text: "MSE rel [dB]", font: { size: 10 } } });
      plot(p.plot1, [{ x: d.phase_ui, y: d.mse_db, line: { color: COL.dg, width: 2 } }], l1);
      p.plot2.innerHTML = "";
      p.note.innerHTML = "Acquisition oracle: minimo MSE usando i simboli noti — utile come riferimento ideale.";
    }
  },
  onConfig(p) { syncParams(p.body); this.refetch(p); },
};

PANEL_DEFS.eq = {
  title: "Equalizzazione — FSE + DFE", size: "s6",
  make(p) { p.body.innerHTML = ""; p.body.appendChild(paramsBlock(["fse_taps", "dfe_taps", "training_start", "training_stop"])); p.plot1 = CE("div", "plot"); p.body.appendChild(p.plot1); p.plot2 = CE("div", "plot"); p.body.appendChild(p.plot2); this.refetch(p); },
  async refetch(p) {
    const d = await GET("/api/panel/eq");
    if (d.link_down) { p.plot1.innerHTML = `<div class="note w">LINK DOWN: nessun equalizzatore adattato.</div>`; p.plot2.innerHTML = ""; return; }
    const l1 = PL({ height: 190 });
    mergeAxis(l1, "xaxis", { title: { text: "posizione [UI]", font: { size: 10 } } });
    plot(p.plot1, [
      { x: d.fse_pos_ui, y: d.fse_taps, name: "FSE (0.5 UI)", type: "bar", marker: { color: COL.dg } },
      { x: d.dfe_taps.map((_, i) => i + 1), y: d.dfe_taps, name: "DFE postcursor", type: "bar", marker: { color: COL.am } }], l1);
    const rows = d.ber_rows.map(r => `<tr><td>${r.stage}</td><td>${sci(r.BER)}</td><td>${r.bit_errors}/${r.bits}</td></tr>`).join("");
    p.plot2.innerHTML = `<table class="mini"><tr><th>stadio</th><th>BER</th><th>errori</th></tr>${rows}</table>`;
  },
  onConfig(p) { syncParams(p.body); this.refetch(p); },
};

PANEL_DEFS.decisions = {
  title: "Decisioni — istogrammi e confusion", size: "s6",
  make(p) { p.body.innerHTML = ""; p.ro = CE("div"); p.body.appendChild(p.ro); p.plotH = CE("div", "plot"); p.body.appendChild(p.plotH); p.plotC = CE("div", "plot"); p.body.appendChild(p.plotC); this.refetch(p); },
  async refetch(p) {
    const d = await GET("/api/panel/decisions");
    if (d.link_down) { p.ro.innerHTML = ""; p.ro.appendChild(readout([{ l: "LINK", v: "DOWN", cls: "fail", big: true, sub: "nessuna decisione senza lock" }])); p.plotH.innerHTML = ""; p.plotC.innerHTML = ""; return; }
    p.ro.innerHTML = "";
    p.ro.appendChild(readout([
      { l: "SNR slicer", v: fix(d.snr_db, 2) + " dB" },
      { l: "Q min", v: fix(d.q_min, 2), sub: d.q_per_eye.map(q => fix(q, 1)).join(" · ") },
      { l: "GMI", v: fix(d.gmi, 3) + "/" + d.bps, sub: d.gmi_per_bit.map(g => fix(g, 3)).join(" · ") },
    ]));
    const colors = [COL.el, COL.ok, COL.am, COL.op];
    const traces = d.hists.map((h, i) => ({ x: h.x, y: h.h, name: "Tx " + fix(h.level, 2), line: { color: colors[i % 4], width: 1.5 } }));
    const l1 = PL({ height: 200, shapes: [...d.thr_mid.map(t => vline(t, COL.muted, "dot")), ...d.thr_cal.map(t => vline(t, COL.ok, "dash"))] });
    mergeAxis(l1, "xaxis", { title: { text: "uscita DFE (soglie: grigio=mid, verde=calibrata)", font: { size: 9 } } });
    plot(p.plotH, traces, l1);
    const l2 = PL({ height: 210, showlegend: false });
    mergeAxis(l2, "xaxis", { title: { text: "deciso", font: { size: 10 } } });
    mergeAxis(l2, "yaxis", { title: { text: "trasmesso", font: { size: 10 } } });
    plot(p.plotC, [{ z: d.confusion.map(r => r.map(v => Math.log10(Math.max(v, 0.5)))), x: d.levels.map(v => fix(v, 2)), y: d.levels.map(v => fix(v, 2)), type: "heatmap", colorscale: [[0, "#0B1117"], [1, COL.fail]], showscale: false }], l2);
  },
  onConfig(p) { this.refetch(p); },
};

PANEL_DEFS.standards = {
  title: "Standard IEEE / OIF", size: "s4",
  make(p) { p.body.innerHTML = ""; p.host = CE("div"); p.body.appendChild(p.host); this.refetch(p); },
  async refetch(p) {
    const d = await GET("/api/panel/standards");
    p.host.innerHTML = "";
    const items = [
      { l: "corsia", v: fix(d.gbd, 3) + " GBd", sub: d.modulation + " · " + fix(d.lane_gbs, 1) + " Gb/s" },
      { l: "famiglia più vicina", v: d.family ? d.family.split("—")[0] : "—", sub: d.deviation_pct != null ? fix(d.deviation_pct, 1) + "% dal nominale" : "" },
      { l: "modello FEC", v: d.fec_name, title: "in-path = il FEC che sta girando nella simulazione; what-if = il FEC tipico della famiglia, usato solo come modello" },
    ];
    if (!d.link_up) items.push({ l: "confronto", v: "LINK DOWN", cls: "fail", sub: "nessuna BER da confrontare" });
    else if (d.threshold) items.push(
      { l: "soglia pre-FEC (modello iid)", v: sci(d.threshold), sub: "BER contata " + sci(d.ber) },
      { l: "posizione", v: d.below ? "SOTTO la soglia del modello" : "SOPRA la soglia del modello", cls: d.below ? "ok" : "fail", sub: "rapporto log " + fix(d.ratio_db, 1) + " dB (non è un margine di conformità)", title: "indicazione dal modello binomiale iid del nostro codec: NON è una misura normativa (COM/TDECQ richiedono procedure di clause)" });
    p.host.appendChild(readout(items));
    p.host.appendChild(CE("div", "note", d.families.map(f => `${f.gbd} GBd ${f.mod} — ${f.name}`).join("<br>") + "<br><span style='color:var(--muted)'>Le architetture mostrate nel banco sono una reference implementation didattica: IEEE/OIF specificano le interfacce, non l'interno del SerDes.</span>"));
  },
  onConfig(p) { this.refetch(p); },
};

PANEL_DEFS.checks = {
  title: "Checkpoint & ledger", size: "s4",
  make(p) { p.body.innerHTML = ""; p.host = CE("div"); p.body.appendChild(p.host); this.refetch(p); },
  async refetch(p) {
    const d = await GET("/api/panel/checks");
    const rows = d.checks.map(c => `<tr><td><span class="badge ${c.status === "PASS" ? "ok" : "fail"}">${c.status === "PASS" ? "✓" : "✗"}</span></td><td>${c.check}<br><span style="color:var(--muted)">${c.detail || ""}</span></td></tr>`).join("");
    p.host.innerHTML = `<table class="mini">${rows}</table>`;
  },
  onConfig(p) { this.refetch(p); },
};

PANEL_DEFS.rxfe = {
  title: "RX front-end — PD · TIA · AGC", size: "s6",
  make(p) { p.body.innerHTML = ""; p.body.appendChild(paramsBlock(["pd_responsivity_a_w", "pd_dark_current_a", "pd_bw_hz", "pd_saturation_a", "rin_db_hz", "tia_noise_a_rt_hz", "tia_transimpedance_ohm", "tia_bw_hz", "tia_clip_v", "agc_target_rms_v"])); p.body.appendChild(CE("div", "note", "Il noise budget e l'ENBW sono nello Spectrum analyzer (nodo 'Uscita TIA') e nel pannello Checkpoint. PD o TIA in saturazione accendono il checkpoint (e il blocco in catena).")); },
  onConfig(p) { syncParams(p.body); },
};

/* --- BERT: error detector + error insertion --- */
PANEL_DEFS.bert = {
  title: "BERT — Error Detector", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    const bar = CE("div", "scope-bar");
    p.nIns = CE("input"); p.nIns.type = "number"; p.nIns.value = 10; p.nIns.min = 1; p.nIns.max = 200; p.nIns.style.width = "60px";
    const btn = CE("button", "btn btn-accent", "Inserisci errori");
    btn.onclick = () => POST("/api/inject", { bits: +p.nIns.value })
      .then(() => { p.note.innerHTML = `<span class="warn">${p.nIns.value} bit invertiti al TX sul prossimo record: guarda il picco nella mappa e (con FEC) le correzioni.</span>`; })
      .catch(e => toast(e.message));
    bar.append(CE("span", "", "bit da invertire:"), p.nIns, btn);
    p.body.appendChild(bar);
    p.ro = CE("div"); p.body.appendChild(p.ro);
    p.plotEl = CE("div", "plot"); p.body.appendChild(p.plotEl);
    p.note = CE("div", "note", "L'ED confronta le decisioni col pattern di riferimento pulito (le inserzioni corrompono solo il TX, come su un BERT reale). La mappa mostra DOVE cadono gli errori nel record.");
    p.body.appendChild(p.note);
    p.lastFetch = 0;
    this.refetch(p);
  },
  async refetch(p) {
    try {
      const d = await GET(`/api/panel/bert?source=${S.running ? "live" : "auto"}`);
      p.ro.innerHTML = "";
      if (d.link_down) { p.ro.appendChild(readout([{ l: "SYNC", v: "LOSS", cls: "fail", big: true, sub: "pattern lock perso: l'ED non conta" }])); return; }
      const a = S.acc || {};
      p.ro.appendChild(readout([
        { l: "sync pattern", v: d.sync ? "LOCK" : "LOSS", cls: d.sync ? "ok" : "fail" },
        { l: "errori (record)", v: String(d.n_errors), big: true, sub: "validation" },
        { l: "inseriti (record)", v: String(d.inserted.length), cls: d.inserted.length ? "warn" : "" },
        { l: "inseriti (totale)", v: String(a.injected_total || 0) },
      ]));
      const shapes = [vline(d.validation_start, COL.muted, "dot")];
      const lay = PL({ height: 190, showlegend: false, shapes });
      mergeAxis(lay, "xaxis", { title: { text: "posizione nel record [simboli] — mappa errori", font: { size: 9 } } });
      mergeAxis(lay, "yaxis", { title: { text: "err/bin", font: { size: 9 } } });
      const traces = [{ x: d.hist_x, y: d.hist, type: "bar", marker: { color: COL.fail } }];
      if (d.inserted.length) traces.push({ x: d.inserted, y: d.inserted.map(() => Math.max(...d.hist, 1)), mode: "markers", marker: { color: COL.am, symbol: "triangle-down", size: 9 }, name: "inseriti" });
      plot(p.plotEl, traces, lay);
    } catch (e) { p.note.innerHTML = `<span class="fail">${e.message}</span>`; }
  },
  onConfig(p) { this.refetch(p); },
  onTick(p) { const now = Date.now(); if (now - p.lastFetch > 1800) { p.lastFetch = now; this.refetch(p); } },
};

/* --- Ethernet L2 (traffic analyzer) --- */
PANEL_DEFS.l2 = {
  title: "Ethernet · Traffic L2-lite", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    p.body.appendChild(paramsBlock(["pattern", "l2_frame_bytes"]));
    p.ro = CE("div"); p.body.appendChild(p.ro);
    p.note = CE("div", "note", "Frame reali (preamble+SFD, header, seq, FCS CRC-32) nel payload del link → attraverso FEC e PHY → delineazione e conteggio all'RX. NON è uno stack di clause: niente 64b/66b, AM, AN/LT, RFC 2544 (roadmap).");
    p.body.appendChild(p.note);
    this.onTick(p);
  },
  onTick(p) {
    const a = S.acc; if (!a || !a.l2) return;
    const l = a.l2;
    p.ro.innerHTML = "";
    if (!l.active) {
      p.ro.appendChild(readout([{ l: "traffico", v: "OFF", sub: "imposta pattern = frame Ethernet (L2)" }]));
      return;
    }
    if (S.acc.last && S.acc.last.link_up === false) {
      p.ro.appendChild(readout([{ l: "LINK", v: "DOWN", cls: "fail", big: true }]));
      return;
    }
    p.ro.appendChild(readout([
      { l: "frame OK (cum.)", v: String(l.frames_ok), big: true, cls: "ok", sub: l.frame_bytes + "B/frame" },
      { l: "FCS errati", v: String(l.frames_fcs_bad), cls: l.frames_fcs_bad ? "fail" : "ok" },
      { l: "persi", v: String(l.frames_lost), cls: l.frames_lost ? "fail" : "ok", sub: isFinite(l.loss_pct) ? fix(l.loss_pct, 2) + " %" : "" },
      { l: "throughput utile", v: fix(l.throughput_gbps, 2) + " Gb/s", sub: "payload con FCS ok / tempo" },
    ]));
  },
  onConfig(p) { syncParams(p.body); },
};

/* --- Link training --- */
PANEL_DEFS.train = {
  title: "Link training (coordinate descent)", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    const bar = CE("div", "scope-bar");
    const btn = CE("button", "btn btn-accent", "Avvia training (~10 s)");
    btn.onclick = async () => {
      btn.disabled = true; btn.textContent = "training…";
      try {
        const d = await POST("/api/experiment/train", {});
        const rows = d.steps.map(s =>
          `<tr><td>${s.param}</td><td>${s.chosen == null ? "invariato" : (s.field.includes("hz") ? fix(s.chosen / 1e9, 1) + " GHz" : fix(s.chosen, 2))}</td><td>${sci(s.score_after)}</td></tr>`).join("");
        p.out.innerHTML = `<div class="readout">
          <div class="ro"><label>BER media prima</label><b>${sci(d.score_before)}</b><span class="sub">2 seed</span></div>
          <div class="ro"><label>BER media dopo</label><b class="${d.score_after < d.score_before ? "ok" : ""}">${sci(d.score_after)}</b><span class="sub">config applicata</span></div>
          </div><table class="mini"><tr><th>fase</th><th>scelta</th><th>score</th></tr>${rows}</table>`;
      } catch (e) { p.out.innerHTML = `<div class="note w">${e.message}</div>`; }
      btn.disabled = false; btn.textContent = "Avvia training (~10 s)";
    };
    bar.append(btn);
    p.body.appendChild(bar);
    p.out = CE("div"); p.body.appendChild(p.out);
    p.body.appendChild(CE("div", "note", "Fasi: CTLE zero → CTLE gain DC → TX FFE pre → TX FFE post, ognuna valutata end-to-end su 2 seed (i LINK DOWN contano 0.5). NON è l'AN/LT di clause (nessuno scambio di coefficienti col link partner): è un tuning locale onesto. La config migliore viene applicata al banco."));
  },
};

/* --- sweep parametrico integrato --- */
PANEL_DEFS.sweep = {
  title: "Sweep parametrico (end-to-end)", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    const bar = CE("div", "scope-bar");
    p.fieldSel = CE("select");
    for (const [k, v] of Object.entries(S.sweepable || {})) {
      const o = CE("option"); o.value = k; o.textContent = v.label; p.fieldSel.appendChild(o);
    }
    p.lo = CE("input"); p.lo.type = "number"; p.lo.style.width = "90px";
    p.hi = CE("input"); p.hi.type = "number"; p.hi.style.width = "90px";
    p.n = CE("input"); p.n.type = "number"; p.n.value = 9; p.n.min = 3; p.n.max = 15; p.n.style.width = "56px";
    const syncRange = () => { const d = S.sweepable[p.fieldSel.value]; p.lo.value = d.lo; p.hi.value = d.hi; };
    p.fieldSel.onchange = syncRange;
    if (S.sweepable && Object.keys(S.sweepable).length) syncRange();
    const btn = CE("button", "btn btn-accent", "Esegui");
    btn.onclick = async () => {
      btn.disabled = true; btn.textContent = "sweep…";
      try {
        const d = await POST("/api/experiment/sweep", { field: p.fieldSel.value, lo: +p.lo.value, hi: +p.hi.value, n: +p.n.value });
        const xs = d.rows.map(r => r[d.field]);
        const floor = 0.5 / Math.max(...d.rows.map(r => r.val_bits || 1), 1);
        const cl = v => (v == null || v <= 0) ? floor : v;
        const downs = d.rows.filter(r => !r.link_up);
        const traces = [
          { x: xs, y: d.rows.map(r => cl(r.BER_pre_EQ)), name: "pre-EQ", line: { color: COL.muted }, mode: "lines+markers" },
          { x: xs, y: d.rows.map(r => cl(r.BER_FSE_DFE)), name: "FSE+DFE", line: { color: COL.ok, width: 2 }, mode: "lines+markers" },
        ];
        if (downs.length) traces.push({ x: downs.map(r => r[d.field]), y: downs.map(() => 0.5), name: "LINK DOWN", mode: "markers", marker: { color: COL.fail, symbol: "x", size: 11 } });
        const lay = PL({ height: 280, shapes: [hline(floor, COL.muted, "dot")] });
        mergeAxis(lay, "xaxis", { title: { text: d.label, font: { size: 10 } } });
        mergeAxis(lay, "yaxis", { type: "log", title: { text: "BER (validation)", font: { size: 10 } } });
        plot(p.plotEl, traces, lay);
        p.note.innerHTML = `Ogni punto è una run end-to-end completa (nuovo canale/rumore ricalcolati). Le "✗" sono punti LINK DOWN: il CDR o il pattern lock non agganciano — su un banco reale il BERT mostrerebbe loss-of-sync, non una BER.`;
      } catch (e) { p.note.innerHTML = `<span class="fail">${e.message}</span>`; }
      btn.disabled = false; btn.textContent = "Esegui";
    };
    bar.append(p.fieldSel, CE("span", "", "da"), p.lo, CE("span", "", "a"), p.hi, CE("span", "", "punti"), p.n, btn);
    p.body.appendChild(bar);
    p.plotEl = CE("div", "plot"); p.body.appendChild(p.plotEl);
    p.note = CE("div", "note", "Scegli un parametro e lancia: vedi la BER end-to-end rispondere alla manopola, incluso il punto in cui il link smette di agganciare.");
    p.body.appendChild(p.note);
  },
};

/* --- JTOL-lite (tolleranza al jitter) --- */
PANEL_DEFS.jtol = {
  title: "JTOL-lite — tolleranza al PJ", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    const bar = CE("div", "scope-bar");
    p.freqs = CE("input"); p.freqs.type = "text"; p.freqs.value = "50, 200, 800, 2000"; p.freqs.style.width = "150px";
    p.target = CE("input"); p.target.type = "text"; p.target.value = "4e-2"; p.target.style.width = "70px";
    const btn = CE("button", "btn btn-accent", "Misura JTOL");
    btn.onclick = async () => {
      btn.disabled = true; btn.textContent = "bisezione… (~10 s)";
      try {
        const freqs = p.freqs.value.split(",").map(Number).filter(v => v > 0);
        const d = await POST("/api/experiment/jtol", { freqs_mhz: freqs, target_ber: Number(p.target.value) });
        const ok = d.points.filter(q => q.amp_ui != null);
        const traces = [{ x: ok.map(q => q.freq_mhz), y: ok.map(q => q.amp_ui), mode: "lines+markers", name: "tolleranza", line: { color: COL.dg, width: 2 }, marker: { size: 8, symbol: ok.map(q => q.capped ? "triangle-up" : "circle") } }];
        const lay = PL({ height: 270, showlegend: false });
        mergeAxis(lay, "xaxis", { type: "log", title: { text: "frequenza PJ [MHz]", font: { size: 10 } } });
        mergeAxis(lay, "yaxis", { title: { text: "ampiezza PJ tollerata [UI pk]", font: { size: 10 } }, range: [0, 0.4] });
        plot(p.plotEl, traces, lay);
        const rows = d.points.map(q => q.amp_ui == null ? `${q.freq_mhz} MHz: link già KO senza PJ` : `${fix(q.freq_mhz, 0)} MHz: ${fix(q.amp_ui, 3)} UI (${fix(q.amp_ps, 2)} ps)${q.capped ? " ≥cap" : ""}`).join(" · ");
        const fbw = S.cfg.cdr_bw * S.cfg.symbol_rate_hz / 1e6;
        p.note.innerHTML = `Target BER ${sci(d.target_ber)} — ${rows}.<br>Il <b>minimo vicino a ~${fix(fbw, 0)} MHz</b> (banda del loop) è il <b>jitter peaking</b> del CDR di 2° ordine: prova a cambiare cdr_bw/damping e rifai la misura. Il record (~${fix(S.cfg.n_symbols / (S.cfg.symbol_rate_hz / 1e9), 0)} ns) limita le basse frequenze a ≥3 cicli. <b>NON normativa</b>: le maschere JTOL di clause hanno pattern, durata e procedure prescritte.`;
      } catch (e) { p.note.innerHTML = `<span class="fail">${e.message}</span>`; }
      btn.disabled = false; btn.textContent = "Misura JTOL";
    };
    bar.append(CE("span", "", "freq [MHz]:"), p.freqs, CE("span", "", "target BER:"), p.target, btn);
    p.body.appendChild(bar);
    p.plotEl = CE("div", "plot"); p.body.appendChild(p.plotEl);
    p.note = CE("div", "note", "Bisezione sull'ampiezza del PJ iniettato al TX PLL, per frequenza: la curva che ne esce è la firma della banda del CDR.");
    p.body.appendChild(p.note);
  },
};

/* ---------------- workbench a sezioni (ordinato per flusso del segnale) --- */
const GROUPS = ["PANORAMICA", "SORGENTE · TX", "CANALE · OTTICA", "RX · DSP",
  "STRUMENTI · ANALISI LIVE"];
// [tipo, nome, dominio, gruppo, ordine nel gruppo]
const PALETTE = [
  ["chain", "Catena del segnale", null, 0, 0],
  ["stimulus", "Stimolo: PRBS · modulazione", "digital", 1, 0],
  ["serpll", "Serializer · TX PLL (jitter)", "digital", 1, 1],
  ["tx", "TX: FFE·DAC·driver", "electrical", 1, 2],
  ["channel", "Canale elettrico", "electrical", 2, 0],
  ["optical", "Ottica: MZM·fibra", "optical", 2, 1],
  ["rxfe", "RX front-end: PD·TIA·AGC", "electrical", 3, 0],
  ["ctle", "CTLE dedicato", "electrical", 3, 1],
  ["adc", "ADC interleaved", "digital", 3, 2],
  ["timing", "Timing · CDR", "digital", 3, 3],
  ["eq", "FSE + DFE", "digital", 3, 4],
  ["decisions", "Decisioni · slicer", "digital", 3, 5],
  ["scope", "Scope · DCA", "electrical", 4, 0],
  ["jitter", "Jitter · TIE", "digital", 4, 1],
  ["spectrum", "Spectrum analyzer", "electrical", 4, 2],
  ["berlive", "BER live (accumulo)", "digital", 4, 3],
  ["bert", "BERT · Error Detector", "digital", 4, 4],
  ["feclive", "FEC live (accumulo)", "digital", 4, 5],
  ["l2", "Ethernet · Traffic L2", "digital", 4, 6],
  ["sweep", "Sweep parametrico", null, 4, 7],
  ["jtol", "JTOL-lite (PJ)", "digital", 4, 8],
  ["train", "Link training", "digital", 4, 9],
  ["standards", "Standard IEEE/OIF", null, 4, 10],
  ["checks", "Checkpoint & ledger", null, 4, 11],
];
const VIEWS = {
  "Banco completo": ["chain", "scope", "jitter", "berlive", "feclive", "serpll", "tx", "channel", "optical", "ctle", "timing", "eq", "decisions", "spectrum", "sweep", "checks"],
  "Essenziale": ["chain", "scope", "berlive", "feclive"],
  "Sorgente e TX": ["chain", "stimulus", "serpll", "tx", "scope", "jitter"],
  "Canale e ottica": ["chain", "channel", "optical", "scope", "spectrum"],
  "RX e DSP": ["chain", "rxfe", "ctle", "adc", "timing", "eq", "decisions", "scope"],
  "Analisi live": ["scope", "jitter", "spectrum", "berlive", "feclive", "sweep", "jtol", "standards", "checks"],
  "BERT e traffico": ["chain", "stimulus", "bert", "l2", "feclive", "berlive", "train"],
};
let PANEL_SEQ = 0;
const SIZES = ["s4", "s6", "s8", "s12"];

function groupGrid(gi) {
  let g = $(`#wb-group-${gi} .wb-grid`);
  if (!g) {
    const sec = CE("div", "wb-group");
    sec.id = `wb-group-${gi}`;
    sec.innerHTML = `<h2 class="wb-title">${GROUPS[gi]}</h2>`;
    g = CE("div", "wb-grid");
    sec.appendChild(g);
    // inserisci la sezione nella posizione giusta rispetto alle altre
    const next = [...document.querySelectorAll(".wb-group")]
      .find(s => +s.id.split("-")[2] > gi);
    $("#workbench").insertBefore(sec, next || null);
  }
  return g;
}

function addPanel(type, size) {
  const def = PANEL_DEFS[type]; if (!def) return;
  const existing = S.panels.filter(p => p.type === type);
  // i pannelli "multi" (Scope) possono avere più istanze: canale A/B per
  // confrontare due nodi fianco a fianco
  if (existing.length && !def.multi) {
    existing[0].el.scrollIntoView({ behavior: "smooth", block: "center" });
    flash(existing[0].el); return existing[0];
  }
  if (def.multi && existing.length >= 2) { flash(existing[0].el); return existing[0]; }
  const pal = PALETTE.find(x => x[0] === type);
  const p = { id: ++PANEL_SEQ, type, def, size: size || def.size || "s6",
    group: pal ? pal[3] : 4, order: (pal ? pal[4] : 99) + existing.length * 0.1 };
  p.el = CE("section", "panel " + p.size);
  p.el.dataset.order = p.order;
  p.head = CE("div", "panel-head");
  const dot = pal && pal[2] ? `<span class="dom-dot" style="background:${DOMC[pal[2]]}"></span>` : "";
  const chLabel = def.multi && existing.length ? ` · CH${existing.length + 1}` : (def.multi ? " · CH1" : "");
  p.head.innerHTML = `${dot}<span class="t">${def.title}${chLabel}</span><span class="spacer"></span>`;
  const btnSize = CE("button", "icon-btn", "◱"); btnSize.title = "ridimensiona";
  btnSize.onclick = () => { const i = SIZES.indexOf(p.size); p.el.classList.remove(p.size); p.size = SIZES[(i + 1) % SIZES.length]; p.el.classList.add(p.size); saveLayout(); };
  const btnClose = CE("button", "icon-btn", "×"); btnClose.title = "chiudi";
  btnClose.onclick = () => {
    const grid = p.el.parentElement;
    p.el.remove(); S.panels = S.panels.filter(x => x !== p);
    if (grid && !grid.children.length) grid.parentElement.remove();
    saveLayout();
  };
  p.head.append(btnSize, btnClose);
  p.body = CE("div", "panel-body");
  p.el.append(p.head, p.body);
  // inserimento ordinato per flusso del segnale dentro il suo gruppo
  const grid = groupGrid(p.group);
  const next = [...grid.children].find(el => +el.dataset.order > p.order);
  grid.insertBefore(p.el, next || null);
  S.panels.push(p);
  try { def.make(p); } catch (e) { p.body.innerHTML = `<div class="note w">${e.message}</div>`; console.error(e); }
  // reset ai default: appare solo nei pannelli con manopole
  if (p.body.querySelector(".param, [data-ffe]")) {
    const btnReset = CE("button", "icon-btn", "↺");
    btnReset.title = "riporta le manopole di questo pannello ai valori default";
    btnReset.onclick = () => {
      const updates = {};
      for (const el of p.body.querySelectorAll(".param")) {
        const f = el.dataset.field;
        if (f && S.defaults[f] !== undefined) updates[f] = S.defaults[f];
      }
      if (p.body.querySelector("[data-ffe]") && S.defaults.tx_ffe_taps)
        updates.tx_ffe_taps = S.defaults.tx_ffe_taps;
      if (Object.keys(updates).length) postConfig(updates);
    };
    p.head.insertBefore(btnReset, btnSize);
  }
  saveLayout();
  return p;
}
function flash(el) { el.style.outline = "2px solid " + COL.op; setTimeout(() => el.style.outline = "", 900); }
function applyView(name) {
  for (const p of [...S.panels]) { p.el.remove(); }
  for (const sec of document.querySelectorAll(".wb-group")) sec.remove();
  S.panels = [];
  for (const t of (VIEWS[name] || VIEWS["Banco completo"])) addPanel(t);
  saveLayout();
}
function saveLayout() { localStorage.setItem("labpro_layout2", JSON.stringify(S.panels.map(p => [p.type, p.size]))); }
function loadLayout() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem("labpro_layout2")); } catch (e) { }
  if (saved && saved.length) { for (const [t, s] of saved) addPanel(t, s); }
  else applyView("Banco completo");
}

/* ---------------- avvio ---------------- */
async function boot() {
  const st = await GET("/api/state");
  S.cfg = st.cfg; S.acc = st.acc; S.running = st.running; S.presets = st.presets;
  S.defaults = st.defaults || {}; S.sweepable = st.sweepable || {};
  const ps = $("#preset-select");
  ps.innerHTML = `<option value="">— preset didattici —</option>`;
  for (const p of st.presets) { const o = CE("option"); o.value = p.name; o.textContent = p.name; o.title = p.desc; ps.appendChild(o); }
  ps.onchange = () => { if (ps.value) { POST("/api/preset", { name: ps.value }).catch(e => toast(e.message)); $("#profile-select").value = ""; } };
  const pf = $("#profile-select");
  pf.innerHTML = `<option value="">— profili standard IEEE/OIF —</option>`;
  for (const p of (st.profiles || [])) { const o = CE("option"); o.value = p.name; o.textContent = p.name; o.title = p.desc; pf.appendChild(o); }
  pf.onchange = () => { if (pf.value) { POST("/api/preset", { name: pf.value }).catch(e => toast(e.message)); ps.value = ""; } };
  $("#btn-run").onclick = () => POST("/api/run", { running: !S.running }).catch(e => toast(e.message));
  $("#btn-reset").onclick = () => POST("/api/reset").catch(e => toast(e.message));
  const vs = $("#view-select");
  for (const name of Object.keys(VIEWS)) { const o = CE("option"); o.value = o.textContent = name; vs.appendChild(o); }
  vs.onchange = () => applyView(vs.value);
  const dd = $(".dropdown");
  $("#btn-add").onclick = (e) => { e.stopPropagation(); dd.classList.toggle("open"); };
  document.addEventListener("click", () => dd.classList.remove("open"));
  const menu = $("#panel-menu");
  let lastGroup = -1;
  for (const [type, name, dom, group] of PALETTE) {
    if (group !== lastGroup) { menu.appendChild(CE("div", "menu-sec", GROUPS[group])); lastGroup = group; }
    const b = CE("button", "", `<span class="dom-dot" style="background:${dom ? DOMC[dom] : COL.muted}"></span>${name}`);
    b.onclick = () => addPanel(type);
    menu.appendChild(b);
  }
  cfgChips(); tickTopbar();
  loadLayout();
  connectWS();
}
boot().catch(e => { document.body.insertAdjacentHTML("afterbegin", `<div id="conn-banner">server non raggiungibile: ${e.message}</div>`); });
