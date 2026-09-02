/* SerDes Optical Lab Pro — workbench a pannelli paralleli.
   Stato server-side (LiveBench) + WebSocket; i pannelli sono schede
   indipendenti che condividono la stessa configurazione versionata. */
"use strict";

const LANG = localStorage.getItem("labpro_lang") === "en" ? "en" : "it";
const L = (it, en) => LANG === "en" ? (en || it) : it;
const TT = (it, en) => `IT: ${it}\nEN: ${en}`;

/* Traduzione delle stringhe generate dal server (check, sorgenti, align…):
   frammenti IT→EN applicati solo in modalità EN. */
const TR_FRAGMENTS = [
  ["Procedura e target versionati", "Versioned procedure and target"],
  ["Pattern completo bit-exact", "Complete bit-exact pattern"],
  ["Rate e modulazione per lane", "Per-lane rate and modulation"],
  ["Due estremi del canale di dispersione", "Both channel CD endpoints"],
  ["Perdita del canale ottico", "Optical-channel insertion loss"],
  ["DGD del canale di test", "Test-channel DGD"],
  ["Reference receiver e TDECQ", "Reference receiver and TDECQ"],
  ["Calibrazione del ricevitore numerico", "Numerical receiver calibration"],
  ["Convergenza della griglia numerica", "Numerical-grid convergence"],
  ["Limite TDECQ del modello", "Model TDECQ limit"],
  ["Chiusura fisica TX→fibra→RX→DSP", "Physical TX→fiber→RX→DSP closure"],
  ["Return-loss e polarizzazione worst-case", "Worst-case return loss and polarization"],
  ["Sistematiche metrologiche esterne", "External metrology systematics"],
  ["Golden instrument correlation", "Golden-instrument correlation"],
  ["riflettore ottico/feedback laser non ancora nel modello", "optical reflector/laser feedback not yet modeled"],
  ["pattern finito eliminato; sistematiche di O/E, scope e fixture non quantificate", "finite-pattern error removed; O/E, scope, and fixture systematics remain unquantified"],
  ["manca un dataset ufficiale con risultato TDECQ pubblicato", "an official dataset with a published TDECQ result is missing"],
  ["lock CDR, BER valida, checkpoint fisici senza FAIL", "CDR lock, valid BER, physical checkpoints without FAIL"],
  ["Table 124-11: −0,93/+0,80 ps/nm totali", "Table 124-11: −0.93/+0.80 ps/nm total"],
  ["coupling 2.825 dB + fibra 0.175 dB = 3.000 dB", "coupling 2.825 dB + fiber 0.175 dB = 3.000 dB"],
  ["ORL canale ≥37 dB; tolleranza TX 21.4 dB; massima RIN", "channel ORL ≥37 dB; TX tolerance 21.4 dB; maximum RIN"],
  ["Table 121-11, min e max alla λ del DUT", "Table 121-11, min and max at DUT λ"],
  ["finestre 0.45/0.55 UI × 0.04 UI", "0.45/0.55 UI windows × 0.04 UI"],
  ["ORL 21.4 dB, massima RIN", "21.4 dB ORL, maximum RIN"],
  ["budget numerico + strumentale tracciabile", "traceable numerical + instrument budget"],
  ["waveform/reference result indipendente", "independent waveform/reference result"],
  ["65,535 simboli", "65,535 symbols"],
  ["σS con ingresso ottico nullo e identiche impostazioni", "σS with zero optical input and identical settings"],
  ["σS=0 W RMS: O/E e scope numerici ideali, valore esplicito", "σS=0 W RMS: ideal numerical O/E and scope, explicit value"],
  ["O/E, scope e fixture con taratura tracciabile", "O/E, scope, and fixture with traceable calibration"],
  ["convergenza numerica quantificata; sistematiche strumentali non disponibili", "numerical convergence quantified; instrument systematics unavailable"],
  ["griglia ridge", "ridge grid"],
  ["interfaccia elettrica long reach", "long-reach electrical interface"],
  ["interfaccia elettrica", "electrical interface"],
  ["modulo elettrico", "electrical module"],
  ["backplane elettrico", "electrical backplane"],
  ["elettrico corto", "short electrical"],
  ["elettrico C2C", "C2C electrical"],
  ["PMD ottico", "optical PMD"],
  ["λ ottico", "λ optical"],
  ["G ottico", "G optical"],
  ["112G didattico — 2 km @1550 nm", "112G educational — 2 km @1550 nm"],
  ["Back-to-back (senza fibra)", "Back-to-back (no fiber)"],
  ["Stress 10 km — fading CD", "10 km stress — CD fading"],
  ["Canale elettrico severo — 20 dB @Nyquist", "Harsh electrical channel — 20 dB @Nyquist"],
  ["RX rumoroso — TIA economico", "Noisy RX — cheap TIA"],
  ["Link con margine — FEC al lavoro", "Link with margin — FEC at work"],
  ["iniettato", "injected"],
  ["(adiacente)", "(adjacent)"],
  ["simboli PAM4", "PAM4 symbols"],
  ["simboli (clause 120D)", "symbols (clause 120D)"],
  ["simboli (firma DFE)", "symbols (DFE signature)"],
  ["~23k simboli", "~23k symbols"],
  ["simbolo RS", "RS symbol"],
  ["bit/errore simbolo", "bits/symbol error"],
  ["tap tipici 802.3ck", "typical 802.3ck taps"],
  ["architettura tipica", "typical architecture"],
  ["banda DCA reale", "real DCA bandwidth"],
  ["banda tipica", "typical bandwidth"],
  ["peaking tipico", "typical peaking"],
  ["sensibilità tipica", "typical sensitivity"],
  ["RLM minimo tipico", "typical minimum RLM"],
  ["minimo tipico", "typical minimum"],
  ["tipico conn.", "typical (connector)"],
  ["tipico DR/FR", "typical DR/FR"],
  ["tipica", "typical"],
  ["tipico", "typical"],
  ["soglia pre-FEC KP4", "KP4 pre-FEC threshold"],
  ["t / soglia", "t / threshold"],
  ["(stessi livelli di picco)", "(same peak levels)"],
  ["(per 1e-13 post)", "(for 1e-13 post-FEC)"],
  ["per lane", "per lane"],
  ["codici CTLE reali", "real CTLE codes"],
  ["righe interleave", "interleave spurs"],
  ["potenza ADC 112G", "112G ADC power"],
  ["occhio", "eye"],
  ["indip., Derickson", "indep., Derickson"],
  ["utilizzo max 64B", "max utilization 64B"],
  ["overhead minimo", "minimum overhead"],
  ["offset clock max", "max clock offset"],
  ["latency FEC (store)", "FEC latency (store)"],
  ["legge quadratica", "square law"],
  ["1 dB opt = 2 dB el", "1 dB opt = 2 dB el"],
  ["gestione", "management"],
  ["soglie DOM", "DOM thresholds"],
  ["pagine CMIS", "CMIS pages"],
  ["form factor", "form factor"],
  ["burst gap ED", "ED burst gap"],
  ["zero errori", "zero errors"],
  ["persistenza", "persistence"],
  ["variabile / infinita", "variable / infinite"],
  ["Lunghezza fibra [km]", "Fiber length [km]"],
  ["Potenza laser [dBm]", "Laser power [dBm]"],
  ["IL canale @Nyquist [dB]", "Channel IL @Nyquist [dB]"],
  ["Zero CTLE [Hz]", "CTLE zero [Hz]"],
  ["Rumore TIA [A/√Hz]", "TIA noise [A/√Hz]"],
  ["Bit ADC", "ADC bits"],
  ["PJ TX ampiezza [UI pk]", "TX PJ amplitude [UI pk]"],
  ["RJ TX [fs rms]", "TX RJ [fs rms]"],
  ["Banda loop CDR [·f_baud]", "CDR loop bandwidth [·f_baud]"],
  ["Offset clock RX [ppm]", "RX clock offset [ppm]"],
  ["Fase di campionamento ADC [UI]", "ADC sampling phase [UI]"],
  ["Temperatura die RX [°C]", "RX die temperature [°C]"],
  ["Supply RX [Δ%]", "RX supply [Δ%]"],
  ["Uscita driver (diff. ideale)", "Driver output (ideal diff.)"],
  ["V_p (ramo positivo)", "V_p (positive leg)"],
  ["V_n (ramo negativo)", "V_n (negative leg)"],
  ["Ingresso canale selezionato", "Selected channel input"],
  ["Uscita canale", "Channel output"],
  ["P ottica MZM", "MZM optical power"],
  ["P ottica al PD", "Optical power at PD"],
  ["Uscita TIA/AFE", "TIA/AFE output"],
  ["Uscita AGC", "AGC output"],
  ["Uscita CTLE", "CTLE output"],
  ["ritardo CDR", "CDR delay"],
  ["centro nominale TX", "TX nominal center"],
  ["fase acquisita", "acquired phase"],
  ["finestra troppo corta", "window too short"],
  ["lock al simbolo", "lock at symbol"],
  ["lock sul fronte: dati a +0.5 UI (pattern sync)", "edge lock: data at +0.5 UI (pattern sync)"],
  ["std fase coda=", "tail phase std="],
  ["correlazione insufficiente", "insufficient correlation"],
  ["senza lock del CDR e del pattern non esistono BER/GMI/FEC: questo è il comportamento di un ricevitore reale", "without CDR and pattern lock there is no BER/GMI/FEC: this is how a real receiver behaves"],
  ["RS(544,514) obbligatorio", "RS(544,514) mandatory"],
  ["RS(528,514) obbligatorio", "RS(528,514) mandatory"],
  ["RS-FEC richiesto via F2", "RS-FEC requested via F2"],
  ["richiesto via F3", "requested via F3"],
  ["nessuno (né F2 né F3 richiesti)", "none (neither F2 nor F3 requested)"],
  ["nessuna abilità comune → AN fallisce (in un PHY reale si resta in ABILITY_DETECT)", "no common ability → AN fails (a real PHY stays in ABILITY_DETECT)"],
  ["AN abilitato, DME sul lane 0", "AN enabled, DME on lane 0"],
  ["break_link_timer scaduto (60–75 ms)", "break_link_timer expired (60–75 ms)"],
  ["3 base page identiche ricevute → ability_match", "3 identical base pages received → ability_match"],
  ["pagina con Ack=1 ed echoed nonce corretto", "page with Ack=1 and correct echoed nonce"],
  ["ack_finished (nessuna next page in questo modello)", "ack_finished (no next page in this model)"],
  ["nessuna HCD → si resta in negoziazione", "no HCD → negotiation continues"],
  ["; parte il PMD control (link training) se previsto", "; PMD control (link training) starts if required"],
  ["HCD = ", "HCD = "],
  ["link_status=OK entro il link_fail_inhibit_timer (510 ms)", "link_status=OK within the link_fail_inhibit_timer (510 ms)"],
  ["link_medium = optical: Clause 73 AN NON esiste sull'ottica (gestione via CMIS); sessione mostrata a scopo didattico come se il lane fosse KR/CR.", "link_medium = optical: Clause 73 AN does NOT exist on optics (managed via CMIS); session shown didactically as if the lane were KR/CR."],
  ["link_medium = copper: contesto KR/CR corretto per Clause 73.", "link_medium = copper: correct KR/CR context for Clause 73."],
  ["serializzazione frame", "frame serialization"],
  ["FEC store&forward (enc+dec)", "FEC store&forward (enc+dec)"],
  ["propagazione fibra", "fiber propagation"],
  ["pipeline DSP (FSE+DFE)", "DSP pipeline (FSE+DFE)"],
  [" bit a ", " bits at "],
  ["Occupazione PRBS13Q-style 2047/2048", "PRBS13Q-style occupancy 2047/2048"],
  ["Occupazione dei livelli bilanciata", "Balanced level occupancy"],
  ["La pre-enfasi consuma headroom", "Pre-emphasis costs headroom"],
  ["Driver non dominato dal clipping", "Driver not clipping-dominated"],
  ["Main cursor normalizzato", "Main cursor normalized"],
  ["Loss campo/potenza coerente", "Field/power loss consistent"],
  ["Photodiode fuori saturazione", "Photodiode below saturation"],
  ["TIA fuori overload", "TIA below overload"],
  ["AFE fuori overload", "AFE below overload"],
  ["ADC non dominato dal clipping", "ADC not clipping-dominated"],
  ["in lock", "locked"],
  ["Pattern lock (BERT-style)", "Pattern lock (BERT-style)"],
  ["FSE migliora (o eguaglia) la BER di validation", "FSE improves (or matches) validation BER"],
  ["DFE non degrada la BER di validation", "DFE does not degrade validation BER"],
  ["GMI numericamente valida", "GMI numerically valid"],
  ["nel percorso: post-FEC ≤ pre-FEC", "in-path: post-FEC ≤ pre-FEC"],
  ["Analyzer L2: frame delineati", "L2 analyzer: frames delineated"],
  ["LINK DOWN — metriche soppresse", "LINK DOWN — metrics suppressed"],
  ["Acquisition oracle (modalità idealizzata dichiarata)", "Oracle acquisition (declared idealized mode)"],
  ["Equalizzazione dopo il lock", "Equalization after lock"],
  ["senza lock del CDR e del pattern non esistono BER/GMI/FEC: questo è il comportamento di un ricevitore reale", "without CDR and pattern lock there is no BER/GMI/FEC: this is how a real receiver behaves"],
  ["correzioni", "corrections"], ["corretti", "corrected"], ["persi", "lost"],
  ["miscorretti", "miscorrected"], ["fase", "phase"], ["coda", "tail"],
  ["simbolo", "symbol"], ["ritardo CDR", "CDR delay"],
  ["centro nominale TX", "TX nominal center"],
  ["modello analitico", "analytic model"],
  ["S2P misurato", "measured S2P"],
  ["aggressore al piano RX/driver", "aggressor at RX/driver plane"],
  ["Temperatura modulo", "Module temperature"],
  ["frame persi", "frames lost"],
  ["clip=", "clip="], ["sat=", "sat="],
  ["peak ratio=", "peak ratio="],
];
// memoizzata: 190 split/join per stringa dentro i loop di rendering delle
// tabelle (checks: ~40 righe × 2 chiamate ogni 2.5 s) erano puro spreco
const _trCache = new Map();
const tr = (txt) => {
  if (LANG !== "en" || typeof txt !== "string") return txt;
  let out = _trCache.get(txt);
  if (out === undefined) {
    out = txt;
    for (const [it, en] of TR_FRAGMENTS) out = out.split(it).join(en);
    if (_trCache.size > 1000) _trCache.clear();
    _trCache.set(txt, out);
  }
  return out;
};

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
async function loadNamedConfig(name, otherSelect, sourceSelect) {
  const controls = [sourceSelect, otherSelect].filter(Boolean);
  controls.forEach(el => { el.disabled = true; });
  toast(L("Applicazione e verifica del profilo…", "Applying and checking profile…"));
  try {
    const d = await POST("/api/preset", { name });
    // The WebSocket broadcast normally arrives first, but it can be missed while
    // the page is still connecting.  Reconcile the POST response so config-only
    // panels (COM, standards, education) never keep the previous profile.
    const changed = d.cfg && hashCfg(S.cfg) !== hashCfg(d.cfg);
    if (d.cfg) {
      S.cfg = d.cfg;
      cfgChips();
      if (changed) notify("config");
    }
    const st = await GET("/api/state");
    S.acc = st.acc;
    S.running = st.running;
    tickTopbar();
    if (otherSelect) otherSelect.value = "";
    // La configurazione è già applicata; questa seconda lettura produce un
    // riscontro end-to-end sul detector, non una conferma basata sui soli knob.
    try {
      const h = await GET("/api/panel/decisions");
      toast(h.link_down
        ? `${name}: LINK DOWN`
        : `${name}: LINK UP · Qmin ${fix(h.q_min, 2)} · BER ${sci(h.ber_counted)}` +
          (h.post_fec_ber != null ? ` · post-FEC ${sci(h.post_fec_ber)}` : ""));
    } catch (e) {
      toast(`${name}: ${L("configurazione applicata; verifica detector non disponibile", "configuration applied; detector check unavailable")} · ${e.message}`);
    }
  } catch (e) { toast(e.message); }
  finally { controls.forEach(el => { el.disabled = false; }); }
}
const sci = (v, d = 2) => (v == null || !isFinite(v)) ? "—" : Number(v).toExponential(d);
const fix = (v, d = 2) => (v == null || !isFinite(v)) ? "—" : Number(v).toFixed(d);
const eng = (v) => {
  if (v == null || !isFinite(v)) return "—";
  const units = [[1e12, "T"], [1e9, "G"], [1e6, "M"], [1e3, "k"]];
  for (const [m, s] of units) if (Math.abs(v) >= m) return (v / m).toFixed(v / m >= 100 ? 0 : 2) + " " + s;
  return String(v);
};
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

// palette letta dai token CSS: style.css è l'UNICA sorgente di verità dei
// colori (prima gli stessi esadecimali vivevano anche qui e potevano divergere)
const _rootCss = getComputedStyle(document.documentElement);
const cssVar = (name, fallback) => (_rootCss.getPropertyValue(name) || fallback).trim();
const COL = {
  bg: cssVar("--panel", "#0E141B"), grid: cssVar("--grid", "#1D2A36"),
  ink: cssVar("--ink", "#D7E1E8"), muted: cssVar("--muted", "#7E93A2"),
  el: cssVar("--electrical", "#56C8E8"), op: cssVar("--optical", "#FF7A59"),
  dg: cssVar("--digital", "#B49CFF"), am: cssVar("--amber", "#E8C55A"),
  ok: cssVar("--ok", "#3ECF8E"), fail: cssVar("--fail", "#FF5470") };
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
const S = { cfg: null, acc: null, running: false, presets: [], ws: null,
  panels: [], controlHelp: {}, actionHelp: {} };

function cfgChips() {
  if (!S.cfg) return;
  const bps = S.cfg.modulation === "NRZ" ? 1 : 2;
  const gbs = bps * S.cfg.symbol_rate_hz / 1e9;
  // sottotitolo DINAMICO: mezzo e rate reali della configurazione corrente
  const medium = S.cfg.link_medium === "copper" ? L("ELETTRICO (RAME)", "ELECTRICAL (COPPER)") : L("ELETTRO-OTTICO", "ELECTRO-OPTICAL");
  $("#brand-sub").textContent = `PRO · ${L("BANCO", "BENCH")} ${medium} · ${gbs.toFixed(gbs >= 100 ? 0 : 1)} Gb/s`;
  $("#chip-rate").textContent = (S.cfg.symbol_rate_hz / 1e9).toFixed(3) + " GBd · " + gbs.toFixed(1) + " Gb/s";
  const pat = S.cfg.pattern === "prbs" ? "PRBS" + S.cfg.prbs_order
    : (S.cfg.pattern === "eth" ? "ETH " + S.cfg.l2_frame_bytes + "B"
      : (S.cfg.pattern === "custom_hex" ? "USER HEX " + Math.floor((S.cfg.custom_pattern_hex || "").replace(/[^0-9a-f]/gi, "").length / 2) + "B"
        : S.cfg.pattern.toUpperCase()));
  $("#chip-mod").textContent = S.cfg.modulation + (S.cfg.modulation === "PAM4" ? " " + S.cfg.pam4_mapping : "") + " · " + pat;
  const fecEl = $("#chip-fec");
  fecEl.textContent = S.cfg.fec_mode === "none" ? "FEC off" : "FEC " + S.cfg.fec_mode.toUpperCase() + " in-path";
  fecEl.classList.toggle("active", S.cfg.fec_mode !== "none");
  $("#sb-cfg-hash").textContent = "cfg#" + hashCfg(S.cfg) + (S.acc ? " · seed base 500000" : "");
}
function hashCfg(cfg) {
  // s2p_text può essere un Touchstone da centinaia di KB e questo hash gira
  // a ogni broadcast di config: nel digest le stringhe enormi entrano come
  // lunghezza + estremi (bastano a distinguere due upload diversi)
  const s = JSON.stringify(cfg, (k, v) =>
    (typeof v === "string" && v.length > 512)
      ? `len${v.length}:${v.slice(0, 64)}${v.slice(-64)}` : v);
  let h = 0;
  for (let i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) | 0; }
  return (h >>> 0).toString(16).slice(0, 8);
}

function tickTopbar() {
  const a = S.acc; if (!a) return;
  $("#tb-records").textContent = a.records + (S.running && a.records_per_s ? " · " + fix(a.records_per_s, 1) + "/s" : "");
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

// chip "esperimento in corso" nella topbar: durante sweep/JTOL/AN-LT/DR4 il
// bench si ferma davvero (BENCH.stop() lato server) — prima la UI non lo
// comunicava e i pannelli sembravano solo "fermi". Il bottone ANNULLA invoca
// la cancellazione cooperativa.
function expBadge(m) {
  const chip = $("#exp-chip");
  if (!chip) return;
  if (m && m.state === "start" && m.name) {
    $("#exp-name").textContent = "⏳ " + m.name;
    chip.classList.remove("hidden");
  } else {
    chip.classList.add("hidden");
  }
}

/* ---------------- WebSocket ---------------- */
let _wsRetry = 0;
function connectWS() {
  const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
  S.ws = ws;
  ws.onopen = () => { _wsRetry = 0; S._wsLast = Date.now(); $("#conn-banner").classList.add("hidden"); };
  ws.onmessage = (ev) => {
    S._wsLast = Date.now();
    const m = JSON.parse(ev.data);
    if (m.type === "hello") { S.cfg = m.cfg; S.running = m.running; S.acc = m.acc; cfgChips(); tickTopbar(); notify("config"); expBadge(m.experiment ? { state: "start", name: m.experiment } : { state: "end" }); }
    if (m.type === "tick") { S.acc = m.acc; S.running = m.acc.running; tickTopbar(); notify("tick"); }
    if (m.type === "config") { S.cfg = m.cfg; cfgChips(); notify("config"); }
    if (m.type === "run") { S.running = m.running; tickTopbar(); }
    if (m.type === "experiment") expBadge(m);
  };
  // riconnessione con backoff esponenziale (prima: retry fisso 1.5 s per sempre)
  ws.onclose = () => {
    $("#conn-banner").classList.remove("hidden");
    const delay = Math.min(1500 * Math.pow(1.6, _wsRetry++), 15000);
    setTimeout(connectWS, delay + Math.random() * 400);
  };
}
// watchdog: in RUN i tick arrivano a cadenza record; una connessione TCP
// morta in silenzio (sleep del laptop) lasciava la UI "connessa" con dati
// fermi e nessun banner — qui la chiudiamo per forzare la riconnessione
setInterval(() => {
  if (!S.ws || S.ws.readyState !== WebSocket.OPEN) return;
  if (S.running && Date.now() - (S._wsLast || 0) > 20000) {
    try { S.ws.close(); } catch (e) { /* già chiusa */ }
  }
}, 10000);
// in RUN i pannelli si aggiornano a cadenza record (~0.9 s), da fermi
// restano alla cadenza lenta originale (nessun lavoro inutile)
let _inflight = 0;
function throttled(p, ms) {
  // La workspace a tab mantiene aperti molti strumenti ma soltanto quello
  // visibile deve acquisire: un tab nascosto non consuma rete/main thread.
  if (_activePanelId != null && p.id !== _activePanelId) return false;
  const now = Date.now();
  // Cadenza adattiva: con pochi pannelli si segue il record (~0.9 s), con
  // un banco pieno l'intervallo cresce col numero di pannelli — 20 pannelli
  // che rifetchano tutti insieme a 1 Hz saturavano il main thread (pagina
  // inchiodata). Jitter per de-sincronizzare + budget di fetch in volo.
  const n = 1;
  if (!p._jit) p._jit = Math.random() * 700;
  const lim = S.running
    ? Math.max(900, Math.min(ms, 900) + Math.max(0, n - 6) * 350) + p._jit
    : ms + p._jit;
  if (now - (p.lastFetch || 0) > lim && _inflight < 4) {
    p.lastFetch = now;
    return true;
  }
  return false;
}
// contabilizza i fetch dei pannelli per il budget _inflight
const _rawGET = GET;
GET = (url) => {
  if (url.startsWith("/api/panel/") || url.startsWith("/api/scope")) {
    _inflight++;
    return _rawGET(url).finally(() => { _inflight = Math.max(0, _inflight - 1); });
  }
  return _rawGET(url);
};
// badge LIVE/REF nell'header del pannello: dichiara da quale record arrivano i dati
// scala/offset verticale per canale (semantica da strumento: × amplifica
// attorno al centro, offset trasla; il deskew sposta in tempo i CH overlay)
function chAdjRange(raw, adj) {
  const [lo, hi] = raw, c = (lo + hi) / 2, hr = (hi - lo) / 2 / (adj.scale || 1);
  return [c - hr - (adj.off || 0), c + hr - (adj.off || 0)];
}
function acqBadge(p, d) {
  const a2 = d && d._acquisition; if (!a2 || !p.head) return;
  if (!p.acqEl) {
    p.acqEl = CE("span", "acq-badge");
    const sp = p.head.querySelector(".spacer");
    if (sp) p.head.insertBefore(p.acqEl, sp); else p.head.appendChild(p.acqEl);
  }
  const live = a2.source === "live", injected = a2.source === "injection";
  p.acqEl.textContent = live ? `LIVE #${a2.records}`
    : (injected ? `INJECTION #${a2.record}` : (a2.source === "static" ? "" : "REF"));
  p.acqEl.classList.toggle("on", live || injected);
}
// --- coalescing dei refresh da config -------------------------------------
// Un drag di slider produce ~4 broadcast "config" al secondo e OGNI pannello
// con onConfig rifetchava subito: ~20 richieste simultanee per step, fuori
// dal budget di throttled(). Qui la raffica diventa una passata scaglionata
// (4 pannelli per frame) con intervallo minimo per pannello; i dirty rimasti
// generano sempre una passata di coda: l'ULTIMA config vince comunque.
const _cfgDirty = new Set();
let _cfgPassActive = false, _cfgPassTimer = null;
function _scheduleCfgPass(delay = 120) {
  if (_cfgPassActive || _cfgPassTimer || !_cfgDirty.size) return;
  _cfgPassTimer = setTimeout(_runCfgPass, delay);
}
function _runCfgPass() {
  _cfgPassTimer = null; _cfgPassActive = true;
  const now = Date.now(), batch = [];
  for (const p of _cfgDirty) {
    if (!S.panels.includes(p)) { _cfgDirty.delete(p); continue; }
    if (!p._mounted || p.id !== _activePanelId) { _cfgDirty.delete(p); continue; }
    if (now - (p._cfgLast || 0) < 600) continue;   // resta dirty → passata di coda
    _cfgDirty.delete(p); p._cfgLast = now; p._needsConfig = false; batch.push(p);
  }
  let i = 0;
  const step = () => {
    const stop = Math.min(i + 4, batch.length);
    for (; i < stop; i++) {
      try { batch[i].def.onConfig(batch[i]); }
      catch (e) { console.warn("panel", batch[i].type, e); }
    }
    if (i < batch.length) { setTimeout(() => requestAnimationFrame(step), 90); return; }
    _cfgPassActive = false;
    _scheduleCfgPass(320);
  };
  step();
}
function notify(kind) {
  if (kind === "config") {
    for (const p of S.panels) if (p.def.onConfig) {
      p._needsConfig = true;
      if (p.id === _activePanelId && p._mounted) _cfgDirty.add(p);
      // Le card mantengono volutamente l'ultimo grafico durante il calcolo,
      // ma ora lo dichiarano come stale invece di farlo passare per il
      // risultato della nuova configurazione.
      if (p.id === _activePanelId && p._mounted && p.def.refetch) {
        p._cfgVersion = (p._cfgVersion || 0) + 1;
        panelLoading(p, true);
      }
    }
    _scheduleCfgPass();
    return;
  }
  const p = S.panels.find(x => x.id === _activePanelId);
  if (p && p._mounted) try { if (p.def.onTick) p.def.onTick(p); }
  catch (e) { console.warn("panel", p.type, e); }
}

/* ---------------- parametri ---------------- */
const PARAMS = {
  symbol_rate_hz: { l: "Baud rate", u: "GBd", min: 20, max: 120, step: 0.125, scale: 1e9 },
  prbs_order: { l: "PRBS", type: "select", opts: [7, 9, 11, 13, 15, 23, 31] },
  modulation: { l: "Modulazione", type: "select", opts: ["PAM4", "NRZ"] },
  pam4_mapping: { l: "Mapping PAM4", type: "select", opts: ["gray", "binary"] },
  fec_mode: { l: "FEC nel percorso", type: "select", opts: ["none", "kp4", "kr4"],
    names: { none: L("nessuno", "none"), kp4: "KP4 RS(544,514)", kr4: "KR4 RS(528,514)" } },
  tx_rj_rms_fs: { l: "RJ clock TX", u: "fs", min: 0, max: 1500, step: 25 },
  tx_pj_amp_ui: { l: "PJ ampiezza", u: "UI", min: 0, max: 0.3, step: 0.005 },
  tx_pj_freq_mhz: { l: "PJ frequenza", u: "MHz", min: 10, max: 3000, step: 10 },
  tx_dcd_pct: { l: "DCD", u: "%UI", min: 0, max: 25, step: 0.5 },
  tx_buj_amp_ui: { l: "BUJ ampiezza", u: "UI", min: 0, max: 0.25, step: 0.005 },
  tx_ssc_ppm: { l: "SSC down-spread", u: "ppm", min: 0, max: 5000, step: 100 },
  tx_ssc_khz: { l: "SSC freq", u: "kHz", min: 30, max: 33, step: 0.5 },
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
  optical_modulator: { l: "Architettura ottica", type: "select", opts: ["mzm", "eml", "dml", "vcsel"],
    names: { mzm: "MZM push-pull", eml: "EML integrated", dml: "DFB-DML direct", vcsel: "VCSEL direct" } },
  laser_type: { l: "Sorgente laser", type: "select", opts: ["cw_dfb_external", "dfb_eml_integrated", "dfb_direct", "vcsel_direct"],
    names: { cw_dfb_external: "CW DFB + MZM", dfb_eml_integrated: "DFB+EAM (EML)", dfb_direct: "DFB direct (DML)", vcsel_direct: "VCSEL direct" } },
  laser_dbm: { l: "P laser", u: "dBm", min: -6, max: 12, step: 0.5 },
  laser_linewidth_mhz: { l: "Linewidth laser", u: "MHz", min: 0, max: 500, step: 1 },
  vpi_v: { l: "Vπ", u: "V", min: 1.5, max: 6, step: 0.1 },
  mzm_bias_rad: { l: "Bias MZM", u: "rad", min: 0.6, max: 2.6, step: 0.02 },
  mzm_bw_hz: { l: "Banda MZM", u: "GHz", min: 15, max: 60, step: 1, scale: 1e9 },
  mzm_il_db: { l: "IL MZM", u: "dB", min: 1, max: 9, step: 0.25 },
  chirp_alpha: { l: "Chirp α", min: -1.5, max: 1.5, step: 0.05 },
  eml_bw_hz: { l: "Banda EML", u: "GHz", min: 15, max: 80, step: 1, scale: 1e9 },
  eml_er_db: { l: "ER EML", u: "dB", min: 1, max: 15, step: 0.25 },
  eml_il_db: { l: "IL EML", u: "dB", min: 0, max: 10, step: 0.25 },
  eml_chirp_alpha: { l: "Chirp EML αH", min: -2, max: 6, step: 0.1 },
  direct_laser_bw_hz: { l: "Banda DML/VCSEL", u: "GHz", min: 8, max: 80, step: 1, scale: 1e9 },
  direct_laser_er_db: { l: "ER DML/VCSEL", u: "dB", min: 1, max: 15, step: 0.25 },
  direct_laser_chirp_alpha: { l: "Chirp direct αH", min: -2, max: 8, step: 0.1 },
  coupling_il_db: { l: "Coupling IL", u: "dB", min: 0, max: 6, step: 0.25 },
  fiber_km: { l: "Fibra", u: "km", min: 0, max: 20, step: 0.25 },
  dispersion_ps_nm_km: { l: "D", u: "ps/nm·km", min: -25, max: 25, step: 0.5 },
  dispersion_slope_ps_nm2_km: { l: "Slope D", u: "ps/nm²·km", min: -0.2, max: 0.2, step: 0.005 },
  pmd_ps_sqrt_km: { l: "PMD coeff.", u: "ps/√km", min: 0, max: 3, step: 0.01 },
  pmd_power_split: { l: "PMD power split", min: 0, max: 1, step: 0.01 },
  fiber_gamma_w_inv_km: { l: "Kerr γ", u: "W⁻¹km⁻¹", min: 0, max: 20, step: 0.1 },
  wavelength_nm: { l: "λ", u: "nm", min: 1260, max: 1610, step: 5 },
  fiber_loss_db_km: { l: "Loss fibra", u: "dB/km", min: 0.1, max: 0.6, step: 0.01 },
  fiber_type: { l: "Tipo fibra", type: "select", opts: ["smf", "mmf"], names: { smf: "SMF", mmf: "MMF" } },
  mmf_modal_bw_mhz_km: { l: "BW·km MMF", u: "MHz·km", min: 500, max: 10000, step: 100 },
  n_symbols: { l: "Simboli/record", type: "select", opts: [4095, 6143, 8191, 12287, 16383] },
  pattern: { l: "Pattern (PPG)", type: "select", opts: ["prbs", "ssprq", "custom_hex", "ssprq_like", "clock2", "clock8", "eth"],
    names: { prbs: "PRBS (PRBSnQ per PAM4)", ssprq: "SSPRQ Clause 120 (bit-exact)", custom_hex: "HEX utente (MSB-first)", ssprq_like: "SSPRQ-like legacy (proxy)", clock2: "clock 0101", clock8: "clock 4+4", eth: "Ethernet frames (L2)" } },
  l2_frame_bytes: { l: "Frame size", u: "B", min: 64, max: 1024, step: 32 },
  l2_ipg_bytes: { l: "IPG (rate control)", u: "B", min: 8, max: 2000, step: 4 },
  l2_streams: { l: "Stream (Xena)", type: "select", opts: [1, 2, 3, 4] },
  link_medium: { l: "Mezzo del link", type: "select", opts: ["optical", "copper"],
    names: { optical: L("ottico (MZM+fibra+PD)", "optical (MZM+fiber+PD)"), copper: L("rame (KR/CR/C2M)", "copper (KR/CR/C2M)") } },
  pn_skew_ps: { l: "Skew P/N", u: "ps", min: 0, max: 10, step: 0.25 },
  pn_gain_mismatch_pct: { l: "Mismatch P/N", u: "%", min: 0, max: 30, step: 1 },
  vcm_offset_v: { l: "V_cm offset", u: "V", min: -0.3, max: 0.3, step: 0.01 },
  vcm_noise_mv: { l: "Rumore CM", u: "mVrms", min: 0, max: 200, step: 5 },
  tx_diff_noise_mv: { l: "Rumore diff. TX", u: "mVrms", min: 0, max: 200, step: 5 },
  electrical_drive_mode: { l: "Piano drive", type: "select", opts: ["differential", "single_ended_p", "single_ended_n"],
    names: { differential: L("differenziale Vp−Vn", "differential Vp−Vn"), single_ended_p: "single-ended P", single_ended_n: "single-ended N" } },
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
  tia_vga_range_db: { l: "Range VGA TIA", u: "dB", min: 0, max: 20, step: 0.5 },
  tia_headroom_ratio: { l: "Headroom TIA", u: "×rail", min: 0.3, max: 0.9, step: 0.05 },
  tia_bw_hz: { l: "Banda TIA", u: "GHz", min: 15, max: 60, step: 1, scale: 1e9 },
  tia_clip_v: { l: "Clip TIA", u: "±V", min: 0.2, max: 1.5, step: 0.05 },
  agc_target_rms_v: { l: "Target AGC", u: "Vrms", min: 0.05, max: 0.5, step: 0.01 },
  pvt_process: { l: "Process corner", type: "select", opts: ["tt", "ss", "ff"],
    names: { tt: L("TT (tipico)", "TT (typical)"), ss: "SS (slow)", ff: "FF (fast)" } },
  pvt_vdd_pct: { l: "Supply RX", u: "Δ%", min: -10, max: 10, step: 0.5 },
  pvt_temp_c: { l: "Temperatura die", u: "°C", min: -40, max: 125, step: 5 },
  agc_min_gain_db: { l: "Gain AGC min", u: "dB", min: -24, max: 6, step: 1 },
  agc_max_gain_db: { l: "Gain AGC max", u: "dB", min: 0, max: 40, step: 1 },
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
  adc_interleaves: { l: "Vie interleave", type: "select", opts: [4, 8, 16, 32, 64] },
  adc_ranks: { l: "Rank T/H", type: "select", opts: [1, 2, 4, 8] },
  adc_frontend_bw_hz: { l: "Banda T/H", u: "GHz", min: 0, max: 60, step: 1, scale: 1e9 },
  adc_bw_mismatch_pct: { l: "BW mism. rank", u: "%", min: 0, max: 15, step: 0.5 },
  adc_cal_mode: { l: "Calibrazione", type: "select", opts: ["background", "foreground", "off"],
    names: { background: "background (insegue PVT)", foreground: "foreground (residui statici)", off: "off (SAR grezzo)" } },
  adc_noise_rms_mv: { l: "Rumore ADC", u: "mV", min: 0, max: 10, step: 0.1 },
  cdr_mode: { l: "Modo CDR", type: "select", opts: ["gardner", "mm", "oracle"],
    names: { gardner: "Gardner (2 sps)", mm: "Mueller-Müller", oracle: "oracle (ideale)" } },
  cdr_bw: { l: "Banda loop", u: "·f_baud", min: 0.0002, max: 0.006, step: 0.0002 },
  cdr_damping: { l: "Damping ζ", min: 0.5, max: 2.0, step: 0.1 },
  rx_ppm_offset: { l: "Offset clock RX", u: "ppm", min: -300, max: 300, step: 10 },
  fse_taps: { l: "Tap FSE", min: 5, max: 31, step: 2 },
  dfe_taps: { l: "Tap DFE", min: 1, max: 12, step: 1 },
  training_stop: { l: "Fine training", u: "simboli", min: 600, max: 6000, step: 50 },
  causal_filters: { l: "Filtri causali", type: "select", opts: [false, true],
    names: { false: L("fase zero (v7)", "zero phase (v7)"), true: L("Butterworth causale", "causal Butterworth") } },
};
const PARAM_EN = {
  symbol_rate_hz: "Baud rate", prbs_order: "PRBS", modulation: "Modulation",
  pam4_mapping: "PAM4 mapping", fec_mode: "In-path FEC",
  tx_rj_rms_fs: "TX clock RJ", tx_pj_amp_ui: "PJ amplitude",
  tx_pj_freq_mhz: "PJ frequency", tx_dcd_pct: "DCD", dac_bits: "DAC bits",
  dac_bw_hz: "DAC bandwidth", dac_full_scale_vpp: "DAC full scale",
  driver_gain_v_per_unit: "Driver gain", driver_bw_hz: "Driver bandwidth",
  driver_clip_v: "Driver rails", channel_il_nyquist_db: "IL @ Nyquist",
  return_loss_db: "Return loss", echo_delay_ui: "Echo delay",
  group_delay_ripple_ps: "Group-delay ripple", laser_dbm: "Laser power",
  laser_linewidth_mhz: "Laser linewidth",
  optical_modulator: "Optical architecture", laser_type: "Laser source",
  vpi_v: "Vpi", mzm_bias_rad: "MZM bias", mzm_bw_hz: "MZM bandwidth",
  mzm_il_db: "MZM IL", chirp_alpha: "Chirp alpha", coupling_il_db: "Coupling IL",
  eml_bw_hz: "EML bandwidth", eml_er_db: "EML ER", eml_il_db: "EML IL",
  eml_chirp_alpha: "EML chirp alpha-Henry",
  direct_laser_bw_hz: "DML/VCSEL bandwidth", direct_laser_er_db: "DML/VCSEL ER",
  direct_laser_chirp_alpha: "Direct laser chirp alpha-Henry",
  fiber_km: "Fiber", dispersion_ps_nm_km: "Dispersion",
  dispersion_slope_ps_nm2_km: "Dispersion slope", pmd_ps_sqrt_km: "PMD coefficient",
  pmd_power_split: "PMD power split", fiber_gamma_w_inv_km: "Kerr gamma",
  wavelength_nm: "Wavelength",
  fiber_loss_db_km: "Fiber loss", fiber_type: "Fiber type",
  mmf_modal_bw_mhz_km: "MMF bandwidth-distance product", n_symbols: "Symbols/record", pattern: "PPG pattern",
  l2_frame_bytes: "Frame size", link_medium: "Link medium", pn_skew_ps: "P/N skew",
  pn_gain_mismatch_pct: "P/N mismatch", vcm_offset_v: "Common-mode offset",
  electrical_drive_mode: "Electrical drive plane",
  vcm_noise_mv: "Common-mode noise", xtalk_next_db: "NEXT @ Nyquist",
  tx_diff_noise_mv: "TX differential white noise",
  xtalk_fext_db: "FEXT @ Nyquist", s4p_pairs: "S4P port pairs",
  training_start: "Training start", training_stop: "Training end",
  pd_dark_current_a: "Dark current", pd_saturation_a: "PD saturation",
  pd_responsivity_a_w: "Responsivity", pd_bw_hz: "PD bandwidth",
  rin_db_hz: "RIN", tia_noise_a_rt_hz: "TIA noise", tia_transimpedance_ohm: "Transimpedance",
  tia_vga_range_db: "TIA VGA range", tia_headroom_ratio: "TIA headroom",
  tia_bw_hz: "TIA bandwidth", tia_clip_v: "TIA clip", agc_target_rms_v: "AGC target",
  agc_min_gain_db: "AGC minimum gain", agc_max_gain_db: "AGC maximum gain",
  ctle_zero_hz: "Zero", ctle_pole_hz: "Pole", ctle_hf_pole_hz: "High pole",
  ctle_dc_gain_db: "DC gain", adc_bits: "ADC bits", adc_full_scale_vpp: "ADC full scale",
  adc_jitter_rms_fs: "Aperture jitter", adc_phase_ui: "Sample phase",
  adc_gain_mismatch_rms: "Gain mismatch", adc_offset_mismatch_rms_v: "Offset mismatch",
  adc_interleaves: "Interleave lanes", adc_ranks: "T/H ranks",
  adc_frontend_bw_hz: "T/H bandwidth", adc_bw_mismatch_pct: "Rank BW mismatch",
  adc_cal_mode: "Calibration", adc_noise_rms_mv: "ADC noise",
  adc_skew_mismatch_rms_fs: "Skew mismatch", cdr_mode: "CDR mode",
  cdr_bw: "Loop bandwidth", cdr_damping: "Damping", rx_ppm_offset: "RX clock offset",
  fse_taps: "FSE taps", dfe_taps: "DFE taps", causal_filters: "Causal filters",
};
const OPTION_EN = {
  nessuno: "none", "ottico (MZM+fibra+PD)": "optical (MZM+fiber+PD)",
  "rame (KR/CR/C2M)": "copper (KR/CR/C2M)", "fase zero (v7)": "zero phase (v7)",
  "Butterworth causale": "causal Butterworth", "Gardner (2 sps)": "Gardner (2 sps)",
  "Mueller-Müller": "Mueller-Mueller", "oracle (ideale)": "oracle (ideal)",
  "clock 0101": "0101 clock", "clock 4+4": "4+4 clock",
  "frame Ethernet (L2)": "Ethernet frames (L2)",
  "background (insegue PVT)": "background (tracks PVT)",
  "foreground (residui statici)": "foreground (static residuals)",
  "off (SAR grezzo)": "off (raw SAR array)",
  "differenziale Vp−Vn": "differential Vp−Vn", "single-ended P": "single-ended P",
  "single-ended N": "single-ended N", "MZM push-pull": "push-pull MZM",
  "EML integrated": "integrated EML", "DFB-DML direct": "direct DFB-DML",
  "VCSEL direct": "direct VCSEL",
  "HEX utente (MSB-first)": "user HEX (MSB first)",
  "SSPRQ-like legacy (proxy)": "legacy SSPRQ-like (proxy)",
};
const PARAMS_EN = {"symbol_rate_hz": "Baud rate", "prbs_order": "PRBS", "modulation": "Modulation", "pam4_mapping": "PAM4 mapping", "fec_mode": "In-path FEC", "pattern": "Pattern (PPG)", "custom_pattern_hex": "User HEX pattern", "l2_frame_bytes": "Frame size", "n_symbols": "Symbols/record", "training_start": "Training start", "training_stop": "Training end", "link_medium": "Link medium", "pn_skew_ps": "P/N skew", "pn_gain_mismatch_pct": "P/N mismatch", "vcm_offset_v": "V_cm offset", "vcm_noise_mv": "CM noise", "xtalk_next_db": "NEXT @Nyq", "xtalk_fext_db": "FEXT @Nyq", "s4p_pairs": "s4p ports", "tx_rj_rms_fs": "TX clock RJ", "tx_pj_amp_ui": "PJ amplitude", "tx_pj_freq_mhz": "PJ frequency", "tx_dcd_pct": "DCD", "tx_buj_amp_ui": "BUJ amplitude", "tx_ssc_ppm": "SSC down-spread", "tx_ssc_khz": "SSC frequency", "dac_bits": "DAC bits", "dac_bw_hz": "DAC bandwidth", "dac_full_scale_vpp": "DAC full scale", "driver_gain_v_per_unit": "Driver gain", "driver_bw_hz": "Driver bandwidth", "driver_clip_v": "Driver rails", "channel_il_nyquist_db": "IL @ Nyquist", "return_loss_db": "Return loss", "echo_delay_ui": "Echo delay", "group_delay_ripple_ps": "GD ripple", "laser_dbm": "Laser power", "vpi_v": "Vπ", "mzm_bias_rad": "MZM bias", "mzm_bw_hz": "Modulator bandwidth", "mzm_il_db": "Modulator IL", "chirp_alpha": "Chirp α", "coupling_il_db": "Coupling IL", "fiber_km": "Fiber length", "dispersion_ps_nm_km": "D", "wavelength_nm": "λ", "fiber_loss_db_km": "Fiber loss", "pd_responsivity_a_w": "Responsivity", "pd_dark_current_a": "Dark current", "pd_bw_hz": "PD bandwidth", "pd_saturation_a": "PD saturation", "rin_db_hz": "RIN", "tia_noise_a_rt_hz": "TIA noise", "tia_transimpedance_ohm": "Z_T", "tia_bw_hz": "TIA bandwidth", "tia_clip_v": "TIA clip", "agc_target_rms_v": "AGC target", "pvt_process": "Process corner", "pvt_vdd_pct": "RX supply", "pvt_temp_c": "Die temperature", "ctle_zero_hz": "Zero", "ctle_pole_hz": "Pole", "ctle_hf_pole_hz": "High pole", "ctle_dc_gain_db": "DC gain", "adc_bits": "ADC bits", "adc_full_scale_vpp": "ADC full scale", "adc_jitter_rms_fs": "Aperture jitter", "adc_phase_ui": "Sampling phase", "adc_gain_mismatch_rms": "Gain mismatch", "adc_offset_mismatch_rms_v": "Offset mismatch", "adc_skew_mismatch_rms_fs": "Skew mismatch", "cdr_mode": "CDR mode", "cdr_bw": "Loop bandwidth", "cdr_damping": "Damping ζ", "rx_ppm_offset": "RX clock offset", "fse_taps": "FSE taps", "dfe_taps": "DFE taps", "causal_filters": "Causal filters", "l2_ipg_bytes": "IPG (rate control)", "l2_streams": "Streams (Xena)"};
Object.assign(PARAM_EN, PARAMS_EN);   // un solo dizionario effettivo per le label EN
let _pendingCfg = {};
let _cfgWaiters = [];
const _flushCfg = debounce(async () => {
  const updates = _pendingCfg, waiters = _cfgWaiters;
  _pendingCfg = {}; _cfgWaiters = [];
  try {
    const result = await POST("/api/config", { updates });
    waiters.forEach(w => w.resolve(result));
  } catch (e) {
    if (!waiters.length) toast(e.message);
    waiters.forEach(w => w.reject(e));
  }
}, 260);
function postConfig(updates) { Object.assign(_pendingCfg, updates); _flushCfg(); }
function postConfigAndWait(updates) {
  return new Promise((resolve, reject) => {
    _cfgWaiters.push({ resolve, reject });
    postConfig(updates);
  });
}

function controlHelpDetails(field, h) {
  return {
    observe_it: `Osserva ${h.plane}: waveform, metrica primaria e checkpoint a valle devono reagire; i piani a monte devono restare invariati.`,
    observe_en: `Observe ${h.plane}: waveform, primary metric, and downstream checkpoints must react; upstream planes must remain unchanged.`,
    verify_it: `Confronto paired: stesso seed e stessi prerequisiti, varia solo ${field}; ripeti vicino al default e a un valore di stress.`,
    verify_en: `Paired check: same seed and prerequisites, vary only ${field}; repeat near default and at a stress value.`,
    boundary_it: "Il risultato è del modello system-level; un limite di standard vale solo dentro una procedura versionata.",
    boundary_en: "This is a system-level model result; a standard limit applies only inside a versioned procedure.",
  };
}

function showHelpRecord(h, title) {
  if (!h) return toast(L("Spiegazione mancante", "Missing help"));
  let dlg = $("#control-help-dialog");
  if (!dlg) {
    dlg = CE("dialog", "control-help-dialog"); dlg.id = "control-help-dialog";
    document.body.appendChild(dlg);
  }
  dlg.innerHTML = `<button class="icon-btn help-close" aria-label="close">×</button>
    <div class="help-kicker">${h.block} · ${h.plane}</div>
    <h3>${title}</h3>
    <div class="help-lang"><b>IT</b><p>${h.it}</p></div>
    <div class="help-lang"><b>EN</b><p>${h.en}</p></div>
    ${h.formula ? `<div class="help-formula">${h.formula}</div>` : ""}
    ${h.observe_it ? `<div class="help-detail"><b>${L("COSA OSSERVARE", "WHAT TO OBSERVE")}</b><p>${L(h.observe_it, h.observe_en)}</p></div>` : ""}
    ${h.verify_it ? `<div class="help-detail"><b>${L("VALIDAZIONE PAIRED", "PAIRED VALIDATION")}</b><p>${L(h.verify_it, h.verify_en)}</p></div>` : ""}
    ${h.boundary_it ? `<div class="help-detail warn"><b>${L("CONFINE E CAUTELA", "BOUNDARY AND CAUTION")}</b><p>${L(h.boundary_it, h.boundary_en)}</p></div>` : ""}
    ${h.endpoint ? `<div class="help-meta"><b>API</b> ${h.endpoint}</div>` : ""}
    ${h.mutates ? `<div class="help-meta"><b>${L("STATO MODIFICATO", "STATE MUTATED")}</b> ${h.mutates}</div>` : ""}
    ${h.active ? `<div class="sub">${L("Attivo quando", "Active when")}: ${h.active}</div>` : ""}`;
  dlg.querySelector(".help-close").onclick = () => dlg.close();
  dlg.onclick = e => { if (e.target === dlg) dlg.close(); };
  dlg.showModal();
}
function showControlHelp(field) {
  const h = S.controlHelp[field];
  if (!h) return toast(L(`Spiegazione mancante per ${field}`, `Missing help for ${field}`));
  showHelpRecord({ ...h, ...controlHelpDetails(field, h) },
    L(PARAMS[field]?.l || field, PARAM_EN[field]));
}
function showActionHelp(action) {
  const h = S.actionHelp[action];
  if (!h) return toast(L(`Azione non documentata: ${action}`, `Undocumented action: ${action}`));
  showHelpRecord(h, L(h.title_it, h.title_en));
}
function helpButton(key, h, action = false) {
  const b = CE("button", `control-help-btn${action ? " action-help-btn" : ""}`, "?");
  b.type = "button";
  if (action) b.dataset.helpFor = key;
  b.title = h ? TT(h.it, h.en) : L(
    action ? "contratto dell'azione" : "spiegazione fisica del controllo",
    action ? "action contract" : "physical control explanation");
  b.setAttribute("aria-label", `${action ? "action help" : "help"} ${key}`);
  b.onclick = e => {
    e.preventDefault(); e.stopPropagation();
    if (action) showActionHelp(key); else showControlHelp(key);
  };
  return b;
}
function controlHelpButton(field) { return helpButton(field, S.controlHelp[field]); }
function actionHelpButton(action) {
  return helpButton(action, S.actionHelp[action], true);
}
function decorateControls(root) {
  for (const b of root.querySelectorAll("button")) {
    const h = b.dataset.action ? S.actionHelp[b.dataset.action] : null;
    if (!b.title) {
      const action = (b.textContent || b.dataset.k || "action").trim();
      b.title = h ? TT(h.it, h.en) : TT(
        `esegue “${action}” sul banco condiviso; verifica il readout del pannello.`,
        `runs “${action}” on the shared bench; verify the panel readout.`);
    }
  }
  for (const b of root.querySelectorAll("button[data-action]")) {
    if (b.nextElementSibling?.dataset?.helpFor === b.dataset.action) continue;
    b.after(actionHelpButton(b.dataset.action));
  }
  for (const e of root.querySelectorAll("select,input")) {
    if (!e.title && !e.closest(".param")) e.title = L(
      "controllo locale del pannello; non modifica la fisica salvo indicazione esplicita",
      "local panel control; does not alter link physics unless explicitly stated");
  }
}

function mkParam(field) {
  const d = PARAMS[field];
  const wrap = CE("div", "param");
  wrap.dataset.field = field;
  if (d.type === "select") {
    const lab = CE("label", "", `<span>${L(d.l, PARAM_EN[field])}</span>`);
    const sel = CE("select");
    for (const o of d.opts) {
      const opt = CE("option"); opt.value = String(o);
      const raw = d.names ? d.names[o] : String(o);
      opt.textContent = LANG === "en" ? (OPTION_EN[raw] || raw) : raw;
      sel.appendChild(opt);
    }
    sel.value = String(S.cfg[field]);
    sel.onchange = () => {
      let v = sel.value;
      if (v === "true") v = true; else if (v === "false") v = false;
      else if (!isNaN(Number(v)) && typeof d.opts[0] === "number") v = Number(v);
      if (field === "optical_modulator") {
        const laser = { mzm: "cw_dfb_external", eml: "dfb_eml_integrated", dml: "dfb_direct", vcsel: "vcsel_direct" }[v];
        postConfig(Object.assign({ optical_modulator: v, laser_type: laser }, v === "vcsel" ? { fiber_type: "mmf", wavelength_nm: 850 } : {}));
      } else if (field === "laser_type") {
        const arch = { cw_dfb_external: "mzm", dfb_eml_integrated: "eml", dfb_direct: "dml", vcsel_direct: "vcsel" }[v];
        postConfig(Object.assign({ laser_type: v, optical_modulator: arch }, arch === "vcsel" ? { fiber_type: "mmf", wavelength_nm: 850 } : {}));
      } else postConfig({ [field]: v });
    };
    wrap.append(lab, sel);
  } else {
    const scale = d.scale || 1;
    const cur = S.cfg[field] / scale;
    const lab = CE("label", "", `<span>${L(d.l, PARAM_EN[field])}</span><b>${fix(cur, d.step < 0.1 ? 2 : (d.step < 1 ? 1 : 0))}${d.u ? " " + d.u : ""}</b>`);
    const rng = CE("input"); rng.type = "range"; rng.min = d.min; rng.max = d.max; rng.step = d.step; rng.value = cur;
    rng.oninput = () => {
      lab.querySelector("b").textContent = fix(Number(rng.value), d.step < 0.1 ? 2 : (d.step < 1 ? 1 : 0)) + (d.u ? " " + d.u : "");
      const v = Number(rng.value) * scale;
      postConfig({ [field]: d.step >= 1 && scale === 1 ? Math.round(v) : v });
    };
    wrap.append(lab, rng);
  }
  wrap.appendChild(controlHelpButton(field));
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
// toast flottante in basso a destra: prima scriveva nel footer, fuori dallo
// scroll con 21 card aperte — l'unico canale d'errore dell'app era invisibile
let _toastTimer = null;
function toast(msg) {
  let el = $("#toast");
  if (!el) {
    el = CE("div"); el.id = "toast";
    el.setAttribute("role", "status"); el.setAttribute("aria-live", "polite");
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove("show"), 5000);
}

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
  vctle: ["Uscita CTLE", "CTLE output"], vtia: ["Uscita TIA/AFE", "TIA/AFE output"],
  pfiber: ["P ottica al PD", "Optical power at PD"], pmzm: ["P ottica al modulatore", "Optical power at modulator"],
  chan: ["Uscita canale", "Channel output"], driver: ["Driver (diff. ideale)", "Driver (ideal diff.)"],
  vp: ["V_p (ramo P)", "V_p (P leg)"], vn: ["V_n (ramo N)", "V_n (N leg)"],
  vdiff: ["V_diff", "V_diff"], vcm: ["V_cm", "V_cm"],
};
const OPTICAL_NODES = new Set(["pfiber", "pmzm"]);
const NODE_BLOCK = { driver: "drv", vp: "drv", vn: "drv", vdiff: "drv", vcm: "drv",
  chan: "ch", pmzm: "mzm", pfiber: "fib", vtia: "tia", vagc: "agc", vctle: "ctle" };
function activeDcaProbes() {
  const out = [];
  S.panels.filter(p => p.type === "scope").forEach((p, si) => {
    [p.node, ...(p.auxNodes || [])].forEach((node, ci) => {
      if (node && NODE_BLOCK[node]) out.push({ node, block: NODE_BLOCK[node],
        label: `DCA${si + 1}:${String.fromCharCode(65 + ci)}` });
    });
  });
  return out;
}
function refreshDcaProbes() {
  for (const p of S.panels.filter(p => p.type === "chain")) {
    p._needsConfig = true;
    if (p._mounted && p.id === _activePanelId) {
      p._needsConfig = false; PANEL_DEFS.chain.onConfig(p);
    }
  }
}
function nodeSelect(panel, cb, def = "vctle") {
  const sel = CE("select");
  sel.title = TT("piano fisico acquisito dallo strumento", "physical plane acquired by the instrument");
  const fill = () => {
    const cur = sel.value || def;
    sel.innerHTML = "";
    for (const [k, v] of Object.entries(NODE_OPTS)) {
      if (S.cfg && S.cfg.link_medium === "copper" && OPTICAL_NODES.has(k)) continue;
      const o = CE("option"); o.value = k; o.textContent = Array.isArray(v) ? L(v[0], v[1]) : v; sel.appendChild(o);
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
    p.body.appendChild(CE("div", "note", L("UN SOLO RX FISICO: PD/TIA/ADC/CDR/FSE/DFE/Slicer ricevono davvero il segnale. Il BERT PPG inietta a TX; l'ED è un checker digitale collegato ai tap pre-FEC e post-FEC, non un secondo ricevitore analogico. I triangoli ambra DCA mostrano i reference plane degli Scope.", "ONE PHYSICAL RX: PD/TIA/ADC/CDR/FSE/DFE/Slicer actually receive the signal. The BERT PPG injects at TX; the ED is a digital checker connected to pre-FEC and post-FEC taps, not a second analog receiver. Amber DCA triangles show Scope reference planes.")));
    this.onConfig(p);
  },
  onConfig(p) {
    const fecOn = S.cfg.fec_mode !== "none";
    const copper = S.cfg.link_medium === "copper";
    const jitOn = S.cfg.tx_rj_rms_fs > 0 || S.cfg.tx_pj_amp_ui > 0 || S.cfg.tx_dcd_pct > 0;
    const ethOn = S.cfg.pattern === "eth";
    const rows = [
      [["stim", ethOn ? "PPG·ETH" : "PPG", "dg", "stimulus"], ["fenc", "FEC enc", fecOn ? "dg" : "off", "feclive"], ["err", "ERR ADD", "dg", "bertcheck"], ["map", "Mapper", "dg", "stimulus"], ["ser", "SER (MUX)", "dg", "serpll"], ["ffe", "TX FIR", "dg", "tx"], ["dac", "DAC", "el", "tx"], ["drv", "Driver P/N", "el", "serpll"], ["ch", "Canale", "el", "channel"], ["mzm", (S.cfg.optical_modulator || "mzm").toUpperCase(), copper ? "off" : "op", "optical"], ["fib", "Fibra", copper ? "off" : "op", "optical"]],
      [["pd", "PD", copper ? "off" : "el", "pd"], ["tia", copper ? "AFE" : "TIA", "el", "tia"], ["agc", "AGC", "el", "agc"], ["ctle", "CTLE", "el", "ctle"], ["adc", "ADC", "dg", "adc"], ["cdr", "CDR·TED", "ck", "timing"], ["fse", "FSE", "dg", "eq"], ["dfe", "DFE", "dg", "eq"], ["slc", "Slicer", "dg", "decisions"], ["dmx", "DEMUX", "dg", "decisions"], ["fdec", ethOn ? "FEC·L2" : "FEC dec", fecOn || ethOn ? "dg" : "off", ethOn ? "l2" : "feclive"]],
    ];
    const W = 98, H = 42, G = 13, X0 = 18, Y = [42, 130];
    const cmap = { el: COL.el, op: COL.op, dg: COL.dg, ck: COL.am, off: "#3A4854" };
    const maxBlocks = Math.max(...rows.map(r => r.length));
    let svg = `<svg class="chain-svg" viewBox="0 0 ${X0 * 2 + maxBlocks * W + (maxBlocks - 1) * G} 200" xmlns="http://www.w3.org/2000/svg" font-family="IBM Plex Mono, monospace">`;
    // TX PLL sopra il serializer (clock domain in ambra)
    const pllX = X0 + 4 * (W + G) + 8, pllC = jitOn ? COL.am : "#5A5142";
    svg += `<a data-target="serpll"><rect x="${pllX}" y="4" width="${W - 16}" height="26" rx="7" fill="rgba(232,197,90,0.06)" stroke="${pllC}" stroke-width="1.2"/>
      <text x="${pllX + (W - 16) / 2}" y="21" text-anchor="middle" fill="${pllC}" font-size="10">TX PLL${jitOn ? " ⚡" : ""}</text></a>
      <line x1="${X0 + 4 * (W + G) + W / 2}" y1="30" x2="${X0 + 4 * (W + G) + W / 2}" y2="${Y[0]}" stroke="${pllC}" stroke-width="1.2" stroke-dasharray="3 3"/>`;
    // clock CDR → ADC
    const cdrI = rows[1].findIndex(b => b[0] === "cdr"), adcI = rows[1].findIndex(b => b[0] === "adc");
    const cdrX = X0 + cdrI * (W + G) + W / 2, adcX = X0 + adcI * (W + G) + W / 2;
    svg += `<path d="M ${cdrX} ${Y[1] + H} v 10 H ${adcX} v -10" fill="none" stroke="${COL.am}" stroke-width="1.1" stroke-dasharray="3 3"/>
      <text x="${(cdrX + adcX) / 2}" y="${Y[1] + H + 22}" text-anchor="middle" fill="${COL.am}" font-size="8.5">${L("clock recuperato", "recovered clock")}</text>`;
    rows.forEach((row, ri) => {
      row.forEach(([id, label, dom, target], i) => {
        const x = X0 + i * (W + G), y = Y[ri], c = cmap[dom];
        svg += `<a data-target="${target}"><g opacity="${dom === "off" ? 0.45 : 1}">
          <rect data-b="${id}" data-c="${c}" x="${x}" y="${y}" width="${W}" height="${H}" rx="8" fill="rgba(255,255,255,0.03)" stroke="${c}" stroke-width="1.3"><title></title></rect>
          <text x="${x + W / 2}" y="${y + H / 2 + 4}" text-anchor="middle" fill="${COL.ink}" font-size="11.5">${label}</text></g></a>`;
        if (i < row.length - 1) {
          const nc = cmap[row[i + 1][2]];
          svg += `<line x1="${x + W}" y1="${y + H / 2}" x2="${x + W + G}" y2="${y + H / 2}" stroke="${nc}" stroke-width="1.4"/>`;
        }
      });
    });
    // Sonde DCA: il marker è sul blocco che produce il reference plane
    // selezionato. Più canali sullo stesso piano vengono impilati.
    const blockPos = {};
    rows.forEach((row, ri) => row.forEach(([id], i) => {
      blockPos[id] = { x: X0 + i * (W + G) + W / 2, y: Y[ri], row: ri };
    }));
    // Un solo RX fisico. ERR ADD è nel flusso TX dopo l'encoder; i due marker
    // ED sono tap digitali di misura prima e dopo il decoder, non altri AFE.
    const bertTx = blockPos.stim, errAdd = blockPos.err;
    const edPre = blockPos.dmx, edPost = blockPos.fdec;
    svg += `<g class="bert-endpoint"><path d="M ${bertTx.x - 5} ${bertTx.y - 5} h 10 l -5 6 z" fill="${COL.am}"/>
      <text x="${bertTx.x + 8}" y="${bertTx.y - 8}" fill="${COL.am}" font-size="8">BERT TX/PPG</text></g>
      <g class="bert-endpoint"><path d="M ${errAdd.x - 5} ${errAdd.y - 5} h 10 l -5 6 z" fill="${COL.am}"/>
      <text x="${errAdd.x + 8}" y="${errAdd.y - 8}" fill="${COL.am}" font-size="8">ERROR INJECTION</text></g>
      <g class="bert-endpoint"><path d="M ${edPre.x - 5} ${edPre.y - 5} h 10 l -5 6 z" fill="${COL.am}"/>
      <text x="${edPre.x + 8}" y="${edPre.y - 8}" fill="${COL.am}" font-size="8">ED PRE-FEC</text></g>
      <g class="bert-endpoint"><path d="M ${edPost.x - 5} ${edPost.y + H + 5} h 10 l -5 -6 z" fill="${fecOn ? COL.am : COL.muted}"/>
      <text x="${edPost.x - 8}" y="${edPost.y + H + 14}" text-anchor="end" fill="${fecOn ? COL.am : COL.muted}" font-size="8">ED POST-FEC${fecOn ? "" : " · BYPASS"}</text></g>`;
    const stack = {};
    for (const probe of activeDcaProbes()) {
      const pos = blockPos[probe.block]; if (!pos) continue;
      const n = stack[probe.block] || 0; stack[probe.block] = n + 1;
      const y = pos.y - 4 - n * 10;
      svg += `<g class="dca-probe" data-node="${probe.node}">
        <path d="M ${pos.x - 4} ${y - 4} h 8 l -4 5 z" fill="${COL.am}"/>
        <text x="${pos.x + 7}" y="${y}" fill="${COL.am}" font-size="7.5">${probe.label}</text>
        <title>${probe.label} · ${probe.node}</title></g>`;
    }
    const fx = X0 + (rows[0].length - 1) * (W + G) + W, fy = Y[0] + H / 2, px = X0, py = Y[1] + H / 2;
    svg += `<path d="M ${fx} ${fy} h 6 q 7 0 7 7 V ${(Y[0] + H + Y[1]) / 2} H ${px - 12} q -7 0 -7 7 V ${py - 7} q 0 7 7 7 h 10" fill="none" stroke="${COL.op}" stroke-width="1.5"/>`;
    // reference plane E/O (prima del MZM, idx 8) e A/D (all'ADC, riga 2 idx 3)
    const eoI = rows[0].findIndex(b => b[0] === "mzm");
    const eoX = X0 + eoI * (W + G) - G / 2, adX = X0 + adcI * (W + G) - G / 2;
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
      const d = await GET("/api/panel/checks"); acqBadge(p, d);
      const bad = {};
      for (const c of d.checks) {
        if (c.status !== "FAIL") continue;
        for (const [pat, blk] of MAP) if (c.check.includes(pat)) {
          bad[blk] = (bad[blk] ? bad[blk] + " · " : "") + c.check;
        }
      }
      for (const r of p.svgHost.querySelectorAll("rect[data-b]")) {
        r.setAttribute("stroke", r.dataset.c);
        r.setAttribute("stroke-width", "1.3");
        r.setAttribute("fill", "rgba(255,255,255,0.03)");
        r.querySelector("title").textContent = "";
        const msg = bad[r.dataset.b];
        if (msg) {
          r.setAttribute("stroke", COL.fail);
          r.setAttribute("stroke-width", "2.6");
          r.setAttribute("fill", "rgba(255,84,112,0.10)");
          r.querySelector("title").textContent = "CHECKPOINT FAIL: " + tr(msg);
        }
      }
      let led = p.body.querySelector(".chain-led");
      if (!led) { led = CE("div", "chain-led scope-bar"); p.body.insertBefore(led, p.body.lastChild); }
      const n = Object.keys(bad).length;
      led.innerHTML = n
        ? `<span class="fail">● ${n} ${L("blocco/i con checkpoint FAIL (bordo rosso — passaci sopra per il dettaglio)", "block(s) with FAILED checkpoints (red border — hover for details)")}</span>`
        : `<span class="ok">● ${L("tutti i checkpoint della catena PASS", "all chain checkpoints PASS")}</span>`;
    } catch (e) { /* pannello checks non disponibile: nessun colore */ }
  },
  onTick(p) { if (throttled(p, 2000)) this.health(p); },
};

/* --- scope DCA --- */
function hexToRgb(hex) { return [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)]; }
PANEL_DEFS.scope = {
  title: "Scope · DCA", size: "s8", multi: true,
  make(p) {
    p.node = p.initialNode || "vctle"; p.persist = 8; p.rate = 12; p.idx = 0; p.count = 0; p.paused = false;
    p.auxNodes = ["", "", ""]; p.auxData = [];
    p.mode = "densità"; p.cursorUi = null; p.maskOn = false; p.maskW = 30; p.maskH = 40;
    // vista FlexDCA: eye (default) o wave = Oscilloscope mode del N1000A
    p.view = "eye"; p.waveData = null; p.waveSpan = 64; p.waveStart = 100;
    p.headSel = nodeSelect(p, () => { p.node = p.headSel.value; refreshDcaProbes(); this.refetch(p); }, p.node);
    p.body.innerHTML = "";
    p.canvas = CE("canvas", "scope"); p.canvas.width = 1000; p.canvas.height = 380;
    p.body.appendChild(p.canvas);
    p.acc = new Float32Array(p.canvas.width * p.canvas.height);
    const bar = CE("div", "scope-bar");
    bar.innerHTML = `
      <b class="sec-tag">${L("ACQUISIZIONE · MISURA", "ACQUIRE · MEASURE")}</b>
      <select data-k="view"><option value="eye">EYE / MASK</option><option value="wave">WAVE (oscilloscope)</option></select>
      <select data-k="wspan" hidden><option>16</option><option>32</option><option selected>64</option><option>128</option><option>256</option></select>
      <input type="number" data-k="wstart" value="100" min="0" step="16" style="width:74px" hidden>
      <select data-k="mode"><option>densità</option><option>fosforo</option></select>
      <span>persist <input type="range" min="1" max="30" value="8" data-k="persist"></span>
      <span>rate <input type="range" min="1" max="40" value="12" data-k="rate"></span>
      <button class="icon-btn" data-k="pause" data-action="scope_pause">⏸</button>
      <label><input type="checkbox" data-k="overlay" checked> livelli/soglie</label>
      <label><input type="checkbox" data-k="cursor"> cursore</label>
      <input type="range" min="-90" max="90" value="0" data-k="curpos" style="width:90px" disabled>
      <select data-k="rf" title="Filtro di misura Bessel-Thomson 4° ordine (ricevitore di riferimento 802.3; TDECQ usa 0.5·Bd)"><option value="">Ref RX off</option><option value="bt4_075">BT4 0.75·Bd</option><option value="bt4_05">BT4 0.5·Bd</option></select>
      <label><input type="checkbox" data-k="mask"> mask</label>
      <input type="range" min="5" max="70" value="30" data-k="maskw" style="width:60px" title="larghezza mask %UI" disabled>
      <input type="range" min="5" max="80" value="40" data-k="maskh" style="width:60px" title="altezza mask %eye" disabled>
      <span data-k="readout"></span>`;
    const q = k => bar.querySelector(`[data-k=${k}]`);
    const scopeHelp = {
      view: TT("EYE ripiega le tracce su 2 UI (eye/mask mode); WAVE mostra la forma d'onda continua del record come l'Oscilloscope mode di un N1000A", "EYE folds traces onto 2 UI (eye/mask mode); WAVE shows the record's continuous waveform like an N1000A's Oscilloscope mode"),
      wspan: TT("ampiezza della finestra temporale in UI (10 divisioni orizzontali)", "time window span in UI (10 horizontal divisions)"),
      wstart: TT("posizione di inizio della finestra nel record [UI]", "window start position within the record [UI]"),
      mode: TT("sceglie color-grade a densità o persistenza fosforo", "selects density color-grade or phosphor persistence"),
      persist: TT("costante di decadimento dell'accumulo visuale; non cambia i dati acquisiti", "visual accumulation decay; does not change acquired data"),
      rate: TT("waveform disegnate per frame browser; non cambia il rate del simulatore", "waveforms drawn per browser frame; does not change simulation rate"),
      pause: TT("congela solo il display mantenendo intatto il banco", "freezes display only while leaving the bench untouched"),
      overlay: TT("mostra medie dei livelli e soglie di decisione misurate", "shows measured level means and decision thresholds"),
      cursor: TT("abilita cursore temporale e istogramma verticale al tempo scelto", "enables time cursor and vertical histogram at the selected time"),
      curpos: TT("posizione del cursore in UI rispetto al centro dell'occhio", "cursor position in UI relative to eye center"),
      rf: TT("applica il ricevitore di riferimento BT4 a tracce e misure, non al datapath", "applies the BT4 reference receiver to traces and measurements, not the datapath"),
      mask: TT("abilita una mask didattica scalabile e conta le waveform che la violano", "enables a scalable educational mask and counts violating waveforms"),
      maskw: TT("larghezza orizzontale della mask in percentuale di UI", "horizontal mask width as a percentage of UI"),
      maskh: TT("altezza verticale della mask rispetto alla separazione dei livelli", "vertical mask height relative to level separation"),
    };
    for (const [k, title] of Object.entries(scopeHelp)) q(k).title = title;
    q("view").onchange = e => {
      p.view = e.target.value;
      const w = p.view === "wave";
      q("wspan").hidden = q("wstart").hidden = !w;
      // i controlli dell'occhio non hanno senso in waveform mode
      for (const k of ["mode", "persist", "cursor", "curpos", "mask", "maskw", "maskh", "overlay"]) q(k).disabled = w;
      p.measHost.hidden = w;      // le misure sono dell'eye mode
      p.acc.fill(0); p._waveDirty = true;
      this.refetch(p);
    };
    q("wspan").onchange = e => { p.waveSpan = +e.target.value; this.refetch(p); };
    q("wstart").onchange = e => { p.waveStart = Math.max(0, +e.target.value || 0); this.refetch(p); };
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
    q("rf").onchange = e => { p.refFilter = e.target.value; p.acc.fill(0); this.refetch(p); };
    p.readoutEl = q("readout");
    p.body.appendChild(bar);
    const multi = CE("div", "scope-bar scope-channels");
    multi.appendChild(CE("b", "", L("ACQUISIZIONE COERENTE", "COHERENT ACQUISITION")));
    p.auxSels = [];
    p.fillAux = () => {
      p.auxSels.forEach((sel, slot) => {
        const cur = p.auxNodes[slot] || ""; sel.innerHTML = `<option value="">CH${String.fromCharCode(66 + slot)} off</option>`;
        for (const [k, v] of Object.entries(NODE_OPTS)) {
          if (S.cfg && S.cfg.link_medium === "copper" && OPTICAL_NODES.has(k)) continue;
          const o = CE("option"); o.value = k;
          o.textContent = `CH${String.fromCharCode(66 + slot)} · ${Array.isArray(v) ? L(v[0], v[1]) : v}`;
          sel.appendChild(o);
        }
        sel.value = [...sel.options].some(o => o.value === cur) ? cur : "";
        p.auxNodes[slot] = sel.value;
      });
    };
    for (let slot = 0; slot < 3; slot++) {
      const sel = CE("select");
      sel.title = TT("canale ausiliario acquisito nello stesso record coerente del CH A", "auxiliary channel acquired from the same coherent record as CH A");
      p.auxSels.push(sel); multi.appendChild(sel);
      sel.onchange = () => { p.auxNodes[slot] = sel.value; p.acc.fill(0); refreshDcaProbes(); this.refetch(p); };
    }
    p.fillAux();
    // scala/offset/deskew per canale (come i controlli verticali di un DCA)
    p.chAdj = { scale: 1, off: 0 };
    p.auxAdj = [{ scale: 1, off: 0, skew: 0 }, { scale: 1, off: 0, skew: 0 }, { scale: 1, off: 0, skew: 0 }];
    const vbar = CE("div", "scope-bar");
    const mkNum = (val, step, w2, title, on) => {
      const el = CE("input"); el.type = "number"; el.value = val; el.step = step;
      el.style.width = w2; el.title = title; el.oninput = () => on(+el.value || 0);
      return el;
    };
    vbar.appendChild(CE("b", "", L("VERTICALE/SKEW", "VERTICAL/SKEW")));
    vbar.appendChild(CE("span", "", "A ×"));
    vbar.appendChild(mkNum(1, 0.1, "52px", L("scala verticale CH A", "CH A vertical scale"), v => { p.chAdj.scale = Math.max(v, 0.05); p.vrange = chAdjRange(p.vrangeRaw || p.vrange, p.chAdj); p.acc.fill(0); }));
    vbar.appendChild(CE("span", "", "off"));
    vbar.appendChild(mkNum(0, 0.01, "58px", L("offset verticale CH A [unità del nodo]", "CH A vertical offset [node units]"), v => { p.chAdj.off = v; p.vrange = chAdjRange(p.vrangeRaw || p.vrange, p.chAdj); p.acc.fill(0); }));
    for (let slot = 0; slot < 3; slot++) {
      vbar.appendChild(CE("span", "", `${String.fromCharCode(66 + slot)} ×`));
      vbar.appendChild(mkNum(1, 0.1, "48px", L("scala CH", "CH scale"), v => { p.auxAdj[slot].scale = Math.max(v, 0.05); this.refetch(p); }));
      vbar.appendChild(mkNum(0, 0.01, "54px", "offset", v => { p.auxAdj[slot].off = v; this.refetch(p); }));
      vbar.appendChild(mkNum(0, 0.05, "50px", L("deskew [UI]", "deskew [UI]"), v => { p.auxAdj[slot].skew = v; this.refetch(p); }));
    }
    multi.after(vbar);
    const pn4 = CE("button", "btn", "P/N · Diff · CM");
    pn4.dataset.action = "scope_coherent";
    pn4.title = L("mostra i quattro reference plane dallo stesso record", "show all four reference planes from the same record");
    pn4.onclick = () => {
      p.node = "vp"; p.headSel.value = "vp";
      p.auxNodes = ["vn", "vdiff", "vcm"]; p.fillAux(); p.acc.fill(0); refreshDcaProbes(); this.refetch(p);
    };
    multi.appendChild(pn4);
    multi.appendChild(CE("span", "sub", L("stesso seed/record; densità su CH A, overlay B–D", "same seed/record; density on CH A, B–D overlays")));
    p.body.appendChild(multi);
    const cbar = CE("div", "scope-bar");
    const btnCont = CE("button", "btn", L("Contour BER 2D (~2 s)", "2D BER contour (~2 s)"));
    btnCont.dataset.action = "eye_contour";
    btnCont.onclick = async () => {
      btnCont.disabled = true;
      try {
        const d = await GET(`/api/panel/eyecontour?node=${p.node}&source=${S.running ? "live" : "auto"}`);
        const lay = PL({ height: 260, showlegend: false });
        mergeAxis(lay, "xaxis", { title: { text: L("fase [UI]", "phase [UI]"), font: { size: 9 } } });
        mergeAxis(lay, "yaxis", { title: { text: `${tr(d.label)} [${d.unit}]`, font: { size: 9 } } });
        plot(p.contourEl, [{
          x: d.phases_ui, y: d.y, z: d.logber, type: "contour",
          contours: { start: -12, end: -1, size: 1, coloring: "heatmap", showlabels: true, labelfont: { size: 8, color: "#d7e1e8" } },
          colorscale: [[0, "#0a2a18"], [0.5, "#155e38"], [0.8, "#3ecf8e"], [1, "#e8c55a"]],
          colorbar: { title: { text: "log₁₀BER", font: { size: 8 } }, thickness: 8, tickfont: { size: 8 } },
        }], lay);
        p.contourEl.insertAdjacentHTML("beforeend", `<div class="note">${L("Contour BER come l'eye mode di un DCA: per ogni (fase, ampiezza) la BER estrapolata Q-scale dai cluster μ/σ. Le curve chiuse più interne sono l'occhio ai BER più bassi. DICHIARATO: code gaussiane.", "BER contour like a DCA eye mode: for each (phase, amplitude) the Q-scale extrapolated BER from the μ/σ clusters. The innermost closed curves are the eye at the lowest BER. DECLARED: Gaussian tails.")}</div>`);
      } catch (e) { toast(e.message); }
      btnCont.disabled = false;
    };
    cbar.append(btnCont, CE("span", "", L("CH A — al cambio nodo rilancia", "CH A — rerun after changing node")));
    p.body.appendChild(cbar);
    p.contourEl = CE("div"); p.body.appendChild(p.contourEl);
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
    // Oscilloscope mode (WAVE): forma d'onda continua del record, disegnata
    // solo quando i dati cambiano — è un'immagine statica fra un refetch e
    // l'altro, niente lavoro per frame come il fosforo
    const drawWave = (ctx, W, H) => {
      ctx.fillStyle = "#04070A"; ctx.fillRect(0, 0, W, H);
      drawGrid(ctx, W, H);
      const chans = p.waveData || [];
      const colors = [p.color || COL.el, COL.op, COL.dg, COL.am];
      const adjs = [p.chAdj, ...(p.auxAdj || [])];
      const info = [];
      chans.forEach((ch, ci) => {
        if (!ch || !ch.v || ch.v.length < 2) return;
        let lo = Infinity, hi = -Infinity;
        for (const v of ch.v) { if (v < lo) lo = v; if (v > hi) hi = v; }
        if (hi - lo < 1e-12) hi = lo + 1;
        const pad = 0.1 * (hi - lo);
        const [vmin, vmax] = chAdjRange([lo - pad, hi + pad], adjs[ci] || {});
        const t0 = ch.t_ui[0], t1 = ch.t_ui[ch.t_ui.length - 1];
        const sk = (adjs[ci] && adjs[ci].skew) || 0;
        ctx.strokeStyle = colors[ci]; ctx.lineWidth = ci ? 1.1 : 1.5;
        ctx.globalAlpha = ci ? 0.75 : 1;
        ctx.beginPath();
        for (let i = 0; i < ch.v.length; i++) {
          const x = W * (ch.t_ui[i] + sk - t0) / (t1 - t0);
          const y = H - (ch.v[i] - vmin) / (vmax - vmin) * H;
          i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
        }
        ctx.stroke(); ctx.globalAlpha = 1;
        ctx.font = "10px IBM Plex Mono"; ctx.fillStyle = colors[ci];
        ctx.fillText(`CH${String.fromCharCode(65 + ci)} ${tr(ch.label)} [${ch.unit}]${ch.ref_note ? " · " + ch.ref_note : ""}`, 8, 16 + ci * 13);
        info.push(`CH${String.fromCharCode(65 + ci)} ${fix((vmax - vmin) / 8, 3)} ${ch.unit}/div`);
      });
      const c0 = chans[0];
      if (c0) {
        // barra di scala stile FlexDCA: timebase + posizione nel record
        ctx.fillStyle = COL.muted; ctx.font = "10px IBM Plex Mono";
        ctx.fillText(`${fix(c0.span_ui / 10, 1)} UI/div · start ${fix(c0.start_ui, 0)} UI · record ${fix(c0.record_ui, 0)} UI`, 8, H - 8);
        p.readoutEl.textContent = `WAVE · ${info.join(" · ")}${p.acqText ? " · " + p.acqText : ""}`;
      }
    };
    const frame = () => {
      if (!p.el.isConnected) return;
      if (p.id !== _activePanelId) { requestAnimationFrame(frame); return; }
      // 30 fps: il fosforo a 60 fps saturava il main thread (UX: pagina
      // che non risponde); ogni 2° frame basta e avanza per l'occhio umano
      p._f = (p._f || 0) + 1;
      if (p._f & 1) { requestAnimationFrame(frame); return; }
      if (p.view === "wave") {
        if (p._waveDirty && p.waveData && !document.hidden) {
          const ctx = p.canvas.getContext("2d");
          drawWave(ctx, p.canvas.width, p.canvas.height);
          p._waveDirty = false;
        }
        requestAnimationFrame(frame); return;
      }
      // niente lavoro se il canvas è fuori viewport o il tab è nascosto
      if (document.hidden) { requestAnimationFrame(frame); return; }
      if (p._f % 30 === 2) {
        const r = p.canvas.getBoundingClientRect();
        p._offscreen = r.bottom < 0 || r.top > innerHeight;
      }
      if (p._offscreen) { requestAnimationFrame(frame); return; }
      const ctx = p.canvas.getContext("2d"), W = p.canvas.width, H = p.canvas.height;
      if (p.traces.length && !p.paused) {
        const [vmin, vmax] = p.vrange;
        const yof = v => H - (v - vmin) / (vmax - vmin) * H;
        if (p.mode === "densità") {
          const decay = 1 - 0.35 / p.persist;
          for (let i = 0; i < p.acc.length; i++) p.acc[i] *= decay;
          for (let k = 0; k < p.rate; k++) { rasterize(p.traces[p.idx], W, H); p.idx = (p.idx + 1) % p.traces.length; p.count++; }
          if (!p.img) { p.img = ctx.createImageData(W, H); p.img32 = new Uint32Array(p.img.data.buffer); }
          // LUT del colormap (1024 voci, ricalcolata solo al cambio colore):
          // il loop per-pixel fa una sola lookup e una scrittura a 32 bit
          if (p.lutColor !== (p.color || COL.el)) {
            p.lutColor = p.color || COL.el;
            const [cr, cg, cb] = hexToRgb(p.lutColor);
            p.lut = new Uint32Array(1024);
            for (let li = 0; li < 1024; li++) {
              const t = li / 1023;
              let r, g, b;
              if (t <= 0.001) { r = 4; g = 7; b = 10; }
              else if (t < 0.5) { const u = t / 0.5; r = 4 + (cr - 4) * u; g = 7 + (cg - 7) * u; b = 10 + (cb - 10) * u; }
              else if (t < 0.8) { const u = (t - 0.5) / 0.3; r = cr + (232 - cr) * u; g = cg + (197 - cg) * u; b = cb + (90 - cb) * u; }
              else { const u = (t - 0.8) / 0.2; r = 232 + 23 * u; g = 197 + 58 * u; b = 90 + 165 * u; }
              p.lut[li] = (255 << 24) | (b << 16) | (g << 8) | r;
            }
          }
          let amax = 0; for (let i = 0; i < p.acc.length; i += 13) if (p.acc[i] > amax) amax = p.acc[i];
          const inv = amax > 0 ? 1023 / Math.log1p(amax) : 0;
          const d32 = p.img32, lut = p.lut, accA = p.acc;
          for (let i = 0; i < accA.length; i++) {
            d32[i] = lut[(Math.log1p(accA[i]) * inv) | 0] || lut[1023];
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
        // Canali B-D: tutte le waveform provengono dallo stesso SimResult.
        // Se le unità differiscono ogni canale usa la propria scala verticale,
        // dichiarata come overlay normalizzato (come tracce con scale separate).
        if (p.auxData && p.auxData.length) {
          const auxColors = [COL.op, COL.dg, COL.am];
          ctx.globalCompositeOperation = "lighter"; ctx.lineWidth = 1.2;
          p.auxData.forEach((ch, ai) => {
            if (!ch.traces.length) return;
            const [amin, amax] = ch.vrange;
            const ay = v => H - (v - amin) / (amax - amin) * H;
            ctx.strokeStyle = auxColors[ai]; ctx.globalAlpha = 0.34;
            const sk = ((ch.adj || {}).skew || 0) * ch.traces[0].length / 2;  // UI → colonne
            for (let k = 0; k < Math.min(4, p.rate); k++) {
              const tr = ch.traces[(p.idx + k) % ch.traces.length]; ctx.beginPath();
              for (let i = 0; i < tr.length; i++) { const x = W * (i + sk) / (tr.length - 1); i ? ctx.lineTo(x, ay(tr[i])) : ctx.moveTo(x, ay(tr[i])); }
              ctx.stroke();
            }
          });
          ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over";
          ctx.font = "10px IBM Plex Mono";
          p.auxData.forEach((ch, ai) => { ctx.fillStyle = auxColors[ai]; ctx.fillText(`CH${String.fromCharCode(66 + ai)} ${tr(ch.label)} [${ch.unit}]`, 8, 16 + ai * 13); });
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
          ctx.fillText(`mask: ${p.maskHits} ${L("hit su", "hits over")} ${p.traces.length} ${L("tracce", "traces")}`, 8, H - 8);
        }
        p.readoutEl.textContent = `redraw ${p.count} · buffer ${p.traces.length} ${L("tracce", "traces")} · 2 UI${p.acqText ? " · " + p.acqText : ""}`;
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
      const requestSeq = (p.fetchSeq || 0) + 1; p.fetchSeq = requestSeq;
      if (p.headSel && p.headSel._refill) { p.headSel._refill(); p.node = p.headSel.value; }
      const nodes = [p.node, ...(p.auxNodes || []).filter(Boolean)];
      if (p.view === "wave") {
        // Oscilloscope mode: finestra continua coerente, stessi canali
        const pack = await GET(`/api/scope?view=wave&nodes=${encodeURIComponent(nodes.join(","))}&start=${p.waveStart}&span=${p.waveSpan}&source=${S.running ? "live" : "auto"}&rf=${p.refFilter || ""}`);
        if (requestSeq !== p.fetchSeq || !p.el.isConnected || p.view !== "wave") return;
        const aq2 = pack._acquisition || {};
        p.acqText = `${aq2.source || "—"} #${aq2.records ?? "—"} seed ${aq2.seed ?? "—"}`;
        p.color = DOMC[pack.channels[0] && pack.channels[0].domain] || COL.el;
        p.waveData = pack.channels;
        p._waveDirty = true;
        return;
      }
      const pack = await GET(`/api/scope?nodes=${encodeURIComponent(nodes.join(","))}&n=600&source=${S.running ? "live" : "auto"}&rf=${p.refFilter || ""}&_=${Date.now()}`);
      if (requestSeq !== p.fetchSeq || !p.el.isConnected) return;
      const d = pack.channels[0], aq = pack._acquisition || {};
      p.acqText = `${aq.source || "—"} #${aq.records ?? "—"} seed ${aq.seed ?? "—"} · ${pack.coherent ? "COHERENT" : ""}`;
      // node o configurazione cambiati: azzera la density map (mai mescolare
      // acquisizioni con scale/configurazioni diverse)
      const key = nodes.join(",") + "|" + hashCfg(S.cfg);
      if (key !== p.accKey) { p.acc.fill(0); p.accKey = key; }
      p.traces = d.traces; p.color = DOMC[d.domain]; p.unit = d.unit; p.meas = d.meas;
      let vmin = Infinity, vmax = -Infinity;
      for (const tr of d.traces) for (const v of tr) { if (v < vmin) vmin = v; if (v > vmax) vmax = v; }
      const pad = 0.12 * (vmax - vmin || 1); p.vrangeRaw = [vmin - pad, vmax + pad];
      p.vrange = chAdjRange(p.vrangeRaw, p.chAdj || {});
      p.auxData = pack.channels.slice(1).map((ch, ai) => {
        let lo = Infinity, hi = -Infinity;
        for (const tr of ch.traces) for (const v of tr) { if (v < lo) lo = v; if (v > hi) hi = v; }
        const pd = 0.12 * (hi - lo || 1);
        const adj = (p.auxAdj || [])[ai] || {};
        return Object.assign({}, ch, { vrangeRaw: [lo - pd, hi + pd], vrange: chAdjRange([lo - pd, hi + pd], adj), adj });
      });
      this.maskCount(p);
      const m = d.meas, link = pack.link || {}, items = [];
      const eyes = ["basso", "medio", "alto"].slice(0, m.eye_heights.length);
      items.push({ l: L("piano visualizzato", "displayed plane"), v: tr(d.label), sub: L("forma d'onda analogica prima di ADC/FSE/DFE", "analog waveform before ADC/FSE/DFE"), title: L("lo Scope non disegna decisioni già equalizzate: quelle sono nel pannello Decisioni", "the Scope does not draw already-equalized decisions: those are in the Decisions panel") });
      items.push(link.link_up
        ? { l: L("uscita chain FSE+DFE", "FSE+DFE chain output"), v: `LINK UP · Q ${fix(link.q_min, 2)}`, cls: link.q_min >= 3 ? "ok" : "warn", sub: `BER ${sci(link.ber_counted)}` + (link.post_fec_ber != null ? ` · post-FEC ${sci(link.post_fec_ber)}` : ""), title: L("risultato contato allo slicer sullo stesso record; il FEC, se presente, è successivo", "counted slicer result on the same record; FEC, when present, follows it") }
        : { l: L("uscita chain FSE+DFE", "FSE+DFE chain output"), v: "LINK DOWN", cls: "fail", sub: `CDR ${link.cdr_locked ? "LOCK" : "NO LOCK"} · pattern ${link.pattern_locked ? "SYNC" : "NO SYNC"}` });
      items.push({ l: L("allineamento", "alignment"), v: tr(d.align), sub: "centro strumento " + fix(m.center_offset_ui, 2) + " UI dal CDR · " + nodes.length + " CH / stesso record", title: L("il DCA autocentra la misura sulla massima apertura; l'offset mostra dove campiona il CDR rispetto all'ottimo", "the DCA auto-centers on maximum opening; the offset shows where the CDR samples relative to the optimum") });
      m.eye_heights.forEach((h, i) => items.push({ l: `eye ${eyes[i]} H/W`, v: `${fix(h, 3)} / ${fix(m.eye_widths_ui[i], 2)} UI`, cls: h > 0 ? "" : "fail", title: L("height p1–p99 al centro strumento / larghezza a p1-p99 (frazione UI)", "p1–p99 height at instrument center / p1–p99 width (UI fraction)") }));
      const preEqClosed = Math.min(...m.eye_heights) < 0;
      if (preEqClosed) items.push(link.link_up
        ? { l: L("occhio al piano analogico", "eye at analog plane"), v: L("CHIUSO → RECUPERATO DAL DSP", "CLOSED → RECOVERED BY DSP"), cls: "warn", sub: L("il link finale è UP: confronta gli istogrammi post-DFE", "the final link is UP: compare the post-DFE histograms"), title: L("l'ISI può chiudere il piano pre-equalizzazione; FSE/DFE recuperano i livelli prima dello slicer", "ISI can close the pre-equalization plane; FSE/DFE recover the levels before the slicer") }
        : { l: L("occhio al piano analogico", "eye at analog plane"), v: L("CHIUSO · LINK DOWN", "CLOSED · LINK DOWN"), cls: "fail", sub: L("il DSP non ha recuperato il link", "DSP did not recover the link") });
      if (m.eh_at_ber) items.push({ l: "EH@2.4e-4", v: m.eh_at_ber["2.4e-4"].map(h => fix(h, 3)).join(" · "), cls: Math.min(...m.eh_at_ber["2.4e-4"]) > 0 ? "" : "fail", sub: `EH@1e-6 ${m.eh_at_ber["1e-6"].map(h => fix(h, 3)).join(" · ")}`, title: L("eye height estrapolata a BER target con code gaussiane (Q-scale, come l'eye mode di un DCA); l'ISI multimodale può chiudere prima", "eye height extrapolated to target BER with Gaussian tails (Q-scale, like a DCA eye mode); multimodal ISI may close earlier") });
      items.push({ l: "Q per occhio", v: m.q_per_eye.map(q => fix(q, 1)).join(" · ") });
      if (m.t_rise_ps != null) items.push({ l: "rise/fall 20-80", v: `${fix(m.t_rise_ps, 1)} / ${fix(m.t_fall_ps, 1)} ps` });
      if (m.rlm_proxy != null) items.push({ l: "RLM proxy", v: fix(m.rlm_proxy, 3) });
      if (m.sndr_db != null) items.push({ l: "SNDR", v: fix(m.sndr_db, 1) + " dB", sub: L("fit lineare del pulse (stile 120D/162)", "linear pulse fit (120D/162-style)"), title: L("SNDR = p_max²/σ²residuo dopo fit lineare ai centri simbolo: esclude l'ISI lineare come la procedura di clause (spec TX ck ≈ 32.5 dB al driver)", "SNDR = p_max²/σ²residual after a linear fit at symbol centers: excludes linear ISI like the clause procedure (ck TX spec ≈ 32.5 dB at the driver)") });
      if (m.p_levels_dbm) items.push({ l: "P0..P3", v: m.p_levels_dbm.map(v => fix(v, 1)).join(" · ") + " dBm", sub: `avg ${fix(m.p_avg_dbm, 2)} dBm` });
      if (m.tdecq && m.tdecq.tdecq_db != null) items.push({ l: "TDECQ", v: fix(m.tdecq.tdecq_db, 2) + " dB", cls: m.tdecq.tdecq_db <= 3.4 ? "ok" : "fail", sub: `Ceq ${fix(m.tdecq.ceq_db, 1)} dB · OMA ${fix(m.tdecq.oma_outer, 3)}`, title: L("TDECQ con la struttura di IEEE 802.3 clause 121.8.5.3: BT4 0.5·Bd, FFE riferimento 5 tap T scelto per minimizzare il TDECQ, doppia fase ±0.05 UI, SER target 4.8e-4, Qt=3.414. Limite DR4/FR4: ≤3.4 dB. DICHIARATO: BT4 zero-fase, adattamento con simboli noti — non certificato.", "TDECQ with the IEEE 802.3 clause 121.8.5.3 structure: BT4 0.5·Bd, 5-tap T reference FFE chosen to minimize TDECQ, dual phase ±0.05 UI, target SER 4.8e-4, Qt=3.414. DR4/FR4 limit: ≤3.4 dB. DECLARED: zero-phase BT4, known-symbol adaptation — not certified.") });
      else if (m.tdecq && m.tdecq.tdecq_db == null) items.push({ l: "TDECQ", v: "FAIL", cls: "fail", sub: L("SER oltre il target già senza rumore aggiunto", "SER above target even with no added noise") });
      if (m.oma_outer_mw != null) { items.push({ l: "OMA outer", v: fix(m.oma_outer_mw, 3) + " mW", cls: "warn" }); items.push({ l: "ER", v: fix(m.er_db, 2) + " dB", cls: "warn" }); }
      // statistiche di misura per acquisizione, stile DCA reale
      const skey = p.node + "|" + hashCfg(S.cfg);
      if (p.statsKey !== skey) { p.stats = {}; p.statsKey = skey; }
      const track = (name, val) => {
        if (val == null || !isFinite(val)) return;
        const st = p.stats[name] || { min: val, max: val, sum: 0, sum2: 0, n: 0 };
        st.cur = val; st.min = Math.min(st.min, val); st.max = Math.max(st.max, val);
        st.sum += val; st.sum2 += val * val; st.n++;
        p.stats[name] = st;
      };
      const eyesN = ["low", "mid", "up"].slice(0, m.eye_heights.length);
      m.eye_heights.forEach((h, i) => track("H " + eyesN[i], h));
      m.eye_widths_ui.forEach((w2, i) => track("W " + eyesN[i], w2));
      m.q_per_eye.forEach((q, i) => track("Q " + eyesN[i], q));
      if (m.t_rise_ps != null) { track("rise ps", m.t_rise_ps); track("fall ps", m.t_fall_ps); }
      if (m.eh_at_ber) m.eh_at_ber["2.4e-4"].forEach((h, i) => track("EH@2.4e-4 " + eyesN[i], h));
      if (m.sndr_db != null) track("SNDR dB", m.sndr_db);
      const srows = Object.entries(p.stats).map(([k2, st]) => {
        const mean = st.sum / st.n, sd = Math.sqrt(Math.max(st.sum2 / st.n - mean * mean, 0));
        return `<tr><td>${k2}</td><td>${fix(st.cur, 3)}</td><td>${fix(st.min, 3)}</td><td>${fix(st.max, 3)}</td><td>${fix(mean, 3)}</td><td>${fix(sd, 4)}</td><td>${st.n}</td></tr>`;
      }).join("");
      p.measHost.innerHTML = ""; p.measHost.appendChild(readout(items));
      if (preEqClosed && link.link_up) {
        const recovered = CE("div", "note w");
        recovered.appendChild(document.createTextNode(L(
          "Questa è una misura pre-DSP. Per vedere l'occhio numerico realmente consegnato al detector: ",
          "This is a pre-DSP measurement. To inspect the numerical eye actually delivered to the detector: ")));
        const openDecisions = CE("button", "btn", L("Apri decisioni post-DFE", "Open post-DFE decisions"));
        openDecisions.title = TT("apre istogrammi, soglie, confusion matrix, Q e BER dopo FSE/DFE", "opens histograms, thresholds, confusion matrix, Q, and BER after FSE/DFE");
        openDecisions.onclick = () => addPanel("decisions");
        recovered.appendChild(openDecisions); p.measHost.appendChild(recovered);
      }
      p.measHost.insertAdjacentHTML("beforeend",
        `<table class="mini"><tr><th>${L("misura", "measure")}</th><th>cur</th><th>min</th><th>max</th><th>mean</th><th>σ</th><th>N</th></tr>${srows}</table>`);
    } catch (e) { p.measHost.innerHTML = `<div class="note w">${e.message}</div>`; }
  },
  onConfig(p) { if (p.fillAux) p.fillAux(); this.refetch(p); },
  onTick(p) { if (throttled(p, 1800)) this.refetch(p); },
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
    const d = await GET(`/api/panel/spectrum?node=${p.node}&source=${S.running ? "live" : "auto"}`); acqBadge(p, d);
    const traces = [{ x: d.f_ghz, y: d.psd_db, name: tr(d.label), line: { color: COL.el, width: 1.2 } }];
    if (d.model_db) traces.push({ x: d.f_ghz, y: d.model_db, name: "floor noise budget", line: { color: COL.am, dash: "dash", width: 1.6 } });
    const layout = PL({ height: 280, shapes: [vline(d.nyquist_ghz)] });
    mergeAxis(layout, "xaxis", { title: { text: "GHz", font: { size: 10 } } });
    mergeAxis(layout, "yaxis", { title: { text: "dB rel 1 " + d.unit, font: { size: 10 } } });
    plot(p.plotEl, traces, layout);
    p.info.textContent = `Welch/Hann · RBW ${fix(d.rbw_mhz, 1)} MHz · PSD one-sided`;
  },
  onConfig(p) { this.refetch(p); },
  onTick(p) { if (throttled(p, 2500)) this.refetch(p); },
};

/* --- CTLE dedicato --- */
PANEL_DEFS.ctle = {
  title: "CTLE — equalizzatore lineare", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    const editor = CE("div", "ctle-editor");
    editor.innerHTML = `<div class="scope-bar"><b>${L("TOPOLOGIA", "TOPOLOGY")}</b>
      <button class="btn" data-preset="1z1p" data-action="ctle_preset">1Z / 1P</button>
      <button class="btn" data-preset="1z2p" data-action="ctle_preset">1Z / 2P</button>
      <button class="btn" data-preset="2z3p" data-action="ctle_preset">2Z / 3P</button>
      <span>${L("zeri", "zeros")} [GHz] <input data-k="zeros" type="text" style="width:150px"></span>
      <span>${L("poli", "poles")} [GHz] <input data-k="poles" type="text" style="width:180px"></span>
      <button class="btn btn-accent" data-k="apply" data-action="ctle_apply">${L("APPLICA", "APPLY")}</button></div>`;
    p.body.appendChild(editor);
    p.zInput = editor.querySelector("[data-k=zeros]");
    p.pInput = editor.querySelector("[data-k=poles]");
    const applyTopology = (z, q) => POST("/api/config", { updates: {
      ctle_zeros_hz: z.map(v => v * 1e9), ctle_poles_hz: q.map(v => v * 1e9)
    }}).catch(e => toast(e.message));
    const presets = { "1z1p": [[9], [40]], "1z2p": [[9], [28, 55]],
      "2z3p": [[6, 16], [24, 45, 75]] };
    for (const b of editor.querySelectorAll("[data-preset]")) b.title = TT(
      "carica questa topologia nel CTLE realmente usato dal datapath",
      "loads this topology into the CTLE actually used by the datapath");
    editor.querySelector("[data-k=apply]").title = TT(
      "valida e applica tutti gli zeri/poli elencati al datapath",
      "validates and applies every listed zero/pole to the datapath");
    for (const b of editor.querySelectorAll("[data-preset]")) b.onclick = () => {
      const [z, q] = presets[b.dataset.preset]; p.zInput.value = z.join(", ");
      p.pInput.value = q.join(", "); applyTopology(z, q);
    };
    editor.querySelector("[data-k=apply]").onclick = () => {
      const parse = el => el.value.split(/[,; ]+/).filter(Boolean).map(Number);
      const z = parse(p.zInput), q = parse(p.pInput);
      if (!z.length || !q.length || [...z, ...q].some(v => !isFinite(v) || v <= 0))
        return toast(L("Inserisci frequenze positive separate da virgole", "Enter positive comma-separated frequencies"));
      applyTopology(z, q);
    };
    p.body.appendChild(paramsBlock(["ctle_dc_gain_db"]));
    p.ro = CE("div"); p.body.appendChild(p.ro);
    p.plotMag = CE("div", "plot"); p.body.appendChild(p.plotMag);
    p.plotGd = CE("div", "plot"); p.body.appendChild(p.plotGd);
    p.body.appendChild(CE("div", "note", L(
      "Ogni zero/polo inserito entra davvero nel percorso. L'ottimo non è il canale piatto: è il compromesso fra ISI, group delay e noise enhancement. Frequenze in ordine crescente, fino a 4 zeri e 5 poli.",
      "Every entered zero/pole is used in the real datapath. The optimum is not a flat channel: it trades ISI, group delay, and noise enhancement. Frequencies must be increasing; up to 4 zeros and 5 poles.")));
    this.refetch(p);
  },
  async refetch(p) {
    const d = await GET("/api/panel/ctle"); acqBadge(p, d);
    p.ro.innerHTML = "";
    p.ro.appendChild(readout([
      { l: "peaking", v: fix(d.peaking_db, 1) + " dB", sub: "@ " + fix(d.f_peak_ghz, 0) + " GHz" },
      { l: "noise enh.", v: fix(d.noise_enh_db, 2) + " dB", cls: d.noise_enh_db > 3 ? "warn" : "" },
      { l: L("topologia", "topology"), v: d.topology, sub: `${d.zeros_ghz.map(x => fix(x, 1)).join(" · ")} Z / ${d.poles_ghz.map(x => fix(x, 1)).join(" · ")} P [GHz]` },
    ]));
    if (document.activeElement !== p.zInput) p.zInput.value = d.zeros_ghz.map(x => fix(x, 2)).join(", ");
    if (document.activeElement !== p.pInput) p.pInput.value = d.poles_ghz.map(x => fix(x, 2)).join(", ");
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
    p.note = CE("div", "note", L("I contatori si riempiono record dopo record (acquisizione continua). Cambiare configurazione azzera l'accumulo.", "Counters fill record after record (continuous acquisition). Changing configuration resets the accumulation."));
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
      ? `${L("FEC live", "Live FEC")} — ${f.codec} in-path`
      : L("FEC what-if — analisi del pattern (nessun FEC nel percorso)", "FEC what-if — pattern analysis (no in-path FEC)");
    p.ro.innerHTML = "";
    if (a.last && a.last.link_up === false) {
      p.ro.appendChild(readout([{ l: "LINK", v: "DOWN", cls: "fail", big: true, sub: "nessun frame decodificabile" }]));
      return;
    }
    const items = [
      { l: L("frame accumulati", "accumulated frames"), v: String(f.frames_total), big: true, sub: L("solo codeword interamente in validation", "only codewords fully inside validation") },
      { l: L("clean / corretti / persi", "clean / corrected / lost"), v: `${f.frames_clean} / ${f.frames_corrected} / ${f.frames_lost}`, cls: f.frames_lost ? "fail" : "ok" },
    ];
    if (f.in_path) items.push(
      { l: "MISCORRETTI", v: String(f.frames_miscorrected || 0), cls: (f.frames_miscorrected || 0) > 0 ? "fail" : "ok", title: L("il decoder ha 'corretto' verso un ALTRO codeword valido: su hardware reale sarebbe invisibile (undetected errors) — qui lo vediamo solo perché conosciamo il TX", "the decoder 'corrected' toward ANOTHER valid codeword: on real hardware this is invisible (undetected errors) — we only see it because the TX is known") },
      { l: L("simboli corretti", "symbols corrected"), v: String(f.symbols_corrected) },
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
  onConfig(p) { syncParams(p.body); this.onTick(p); },
};

/* --- serializer + TX PLL (jitter injection) + coppia P/N --- */
PANEL_DEFS.serpll = {
  title: "Serializer · TX PLL · uscita P/N", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    p.body.appendChild(paramsBlock(["tx_rj_rms_fs", "tx_pj_amp_ui", "tx_pj_freq_mhz", "tx_dcd_pct", "tx_buj_amp_ui", "tx_ssc_ppm", "tx_ssc_khz",
      "pn_skew_ps", "pn_gain_mismatch_pct", "vcm_offset_v", "vcm_noise_mv", "tx_diff_noise_mv"]));
    p.ro = CE("div"); p.body.appendChild(p.ro);
    p.body.appendChild(CE("div", "note", L("Il jitter è iniettato sul time base del serializer/DAC (reference plane: clock TX), un offset per UI. Misuralo nel pannello <b>Jitter · TIE</b>: al driver vedi ciò che hai iniettato + il DDJ del pattern; al CTLE si somma tutto il canale.", "Jitter is injected on the serializer/DAC time base (reference plane: TX clock), one offset per UI. Measure it in the <b>Jitter · TIE</b> panel: at the driver you see what you injected + pattern DDJ; at the CTLE the whole channel adds up.")));
    this.onConfig(p);
  },
  onConfig(p) {
    syncParams(p.body);
    const ui_ps = 1e12 / S.cfg.symbol_rate_hz;
    p.ro.innerHTML = "";
    p.ro.appendChild(readout([
      { l: L("RJ iniettato", "injected RJ"), v: fix(S.cfg.tx_rj_rms_fs / 1000, 2) + " ps", sub: fix(S.cfg.tx_rj_rms_fs * 1e-3 / ui_ps, 4) + " UI rms" },
      { l: L("PJ iniettato", "injected PJ"), v: fix(S.cfg.tx_pj_amp_ui * ui_ps, 2) + " ps pk", sub: "@ " + fix(S.cfg.tx_pj_freq_mhz, 0) + " MHz" },
      { l: "DCD", v: fix(S.cfg.tx_dcd_pct / 100 * ui_ps, 2) + " ps pp", sub: fix(S.cfg.tx_dcd_pct, 1) + " %UI" },
      { l: L("skew P/N", "P/N skew"), v: fix(S.cfg.pn_skew_ps, 2) + " ps", sub: L("notch DM a ", "DM notch at ") + (S.cfg.pn_skew_ps > 0 ? fix(500 / S.cfg.pn_skew_ps, 0) + " GHz" : "∞"), title: L("lo skew fra i rami filtra il differenziale: notch a 1/(2τ)", "leg-to-leg skew filters the differential: notch at 1/(2τ)") },
      { l: "UI", v: fix(ui_ps, 2) + " ps" },
    ]));
    p.ro.appendChild(CE("div", "note", L("Osserva V_p, V_n, V_diff e V_cm come nodi dello Scope: lo sbilanciamento P/N fa trapelare il common-mode nel differenziale.", "Watch V_p, V_n, V_diff, and V_cm as Scope nodes: P/N imbalance leaks common-mode into the differential.")));
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
    p.live = CE("div", "scope-bar"); p.body.appendChild(p.live);
    p.plotW = CE("div", "plot"); p.body.appendChild(p.plotW);
    p.plotT = CE("div", "plot"); p.body.appendChild(p.plotT);
    p.plotH = CE("div", "plot"); p.body.appendChild(p.plotH);
    p.plotS = CE("div", "plot"); p.body.appendChild(p.plotS);
    p.plotB = CE("div", "plot"); p.body.appendChild(p.plotB);
    p.note = CE("div", "note w"); p.body.appendChild(p.note);
    p.lastFetch = 0; p.fetchSeq = 0; p.history = []; p.lastSeed = null;
    this.refetch(p);
  },
  async refetch(p) {
    try {
      if (p.headSel && p.headSel._refill) { p.headSel._refill(); p.node = p.headSel.value; }
      const requestSeq = ++p.fetchSeq;
      const d = await GET(`/api/panel/jitter?node=${p.node}&source=${S.running ? "live" : "auto"}&_=${Date.now()}`); acqBadge(p, d);
      if (requestSeq !== p.fetchSeq || !p.el.isConnected) return;
      const aq = d._acquisition || {};
      if (aq.seed !== p.lastSeed) {
        p.lastSeed = aq.seed;
        p.history.push({ seed: aq.seed, rms: d.tie_rms_ps, pp: d.tie_pp_ps });
        if (p.history.length > 80) p.history.shift();
      }
      const deterministic = p.node === "driver" && S.cfg.tx_rj_rms_fs === 0;
      p.live.innerHTML = `<span class="badge ${aq.source === "live" ? "ok" : "warn"}">${aq.source || "—"}</span>
        <span>${L("acquisizione", "acquisition")} #${aq.records ?? "—"} · seed ${aq.seed ?? "—"}</span>
        <span>${deterministic ? L("driver deterministico: i record coincidono finché RJ=0", "deterministic driver: records match while RJ=0") : L("nuovo rumore/TIE per record", "new noise/TIE each record")}</span>`;
      p.ro.innerHTML = "";
      p.ro.appendChild(readout([
        { l: "TIE rms", v: fix(d.tie_rms_ps, 2) + " ps", big: true, sub: d.n_edges + " crossing" },
        { l: "TIE pk-pk", v: fix(d.tie_pp_ps, 2) + " ps" },
        { l: "RJ est.", v: fix(d.rj_est_ps, 2) + " ps", sub: L("iniettato ", "injected ") + fix(d.injected.rj_fs / 1000, 2) + " ps", title: "stima dual-Dirac grezza: include il DDJ del pattern" },
        { l: "DJ est.", v: fix(d.dj_est_ps, 2) + " ps pp", sub: "PJ inj " + fix(d.injected.pj_ui * d.ui_ps, 2) + " ps · DCD " + fix(d.injected.dcd_pct / 100 * d.ui_ps, 2) + " ps" },
        ...(d.tail_fit ? [
          { l: "RJ tail-fit", v: fix(d.tail_fit.rj_ps, 3) + " ps", sub: `σL ${fix(d.tail_fit.sigma_left_ps, 3)} · σR ${fix(d.tail_fit.sigma_right_ps, 3)}`, title: L("fit Q-scale delle code della CDF del TIE (dual-Dirac, Derickson §2.5.4): pendenza asintotica = σ del RJ; ATTENZIONE, fit vicino al centro sovrastima RJ", "Q-scale fit of the TIE CDF tails (dual-Dirac, Derickson §2.5.4): asymptotic slope = RJ σ; BEWARE, fitting near the center overestimates RJ") },
          { l: "DJ(δδ)", v: fix(d.tail_fit.dj_dd_ps, 2) + " ps", sub: "dual-Dirac", title: L("distanza fra le intercette a Q=0 (Derickson eq. 2-41); per costruzione DJ(δδ) ≤ DJ(pp)", "distance between the Q=0 intercepts (Derickson eq. 2-41); by construction DJ(δδ) ≤ DJ(pp)") },
          { l: "TJ@1e-12", v: fix(d.tail_fit.tj_1e12_ps, 2) + " ps", sub: `TJ@2.4e-4 ${fix(d.tail_fit.tj_2p4e4_ps, 2)} ps`, title: "TJ(p) = 2·Q_p·σ + DJ(δδ) — Derickson & Müller eq. 2-41" },
          { l: "EW@2.4e-4", v: fix(d.tail_fit.ew_2p4e4_ui, 3) + " UI", cls: d.tail_fit.ew_2p4e4_ui > 0 ? "" : "fail", sub: L("apertura orizzontale alla soglia FEC", "horizontal opening at the FEC threshold") },
        ] : []),
      ]));
      const lw = PL({ height: 145, showlegend: false });
      mergeAxis(lw, "xaxis", { title: { text: L("posizione crossing [UI]", "crossing position [UI]"), font: { size: 9 } } });
      mergeAxis(lw, "yaxis", { title: { text: "TIE [mUI]", font: { size: 9 } } });
      plot(p.plotW, [{ x: d.edge_sym, y: d.tie_ui.map(v => 1e3 * v), mode: "markers",
        marker: { color: COL.dg, size: 2.5, opacity: 0.55 } }], lw);
      const lt = PL({ height: 145, showlegend: true });
      mergeAxis(lt, "xaxis", { title: { text: L("acquisizioni live", "live acquisitions"), font: { size: 9 } } });
      mergeAxis(lt, "yaxis", { title: { text: "ps", font: { size: 9 } } });
      plot(p.plotT, [
        { x: p.history.map((_, i) => i + 1), y: p.history.map(v => v.rms), name: "RMS", line: { color: COL.dg } },
        { x: p.history.map((_, i) => i + 1), y: p.history.map(v => v.pp), name: "pk-pk", line: { color: COL.am } },
      ], lt);
      const l1 = PL({ height: 170, showlegend: false });
      mergeAxis(l1, "xaxis", { title: { text: L("TIE [UI] — istogramma dei crossing (soglia media)", "TIE [UI] — crossing histogram (mid threshold)"), font: { size: 9 } } });
      mergeAxis(l1, "yaxis", { type: "log", title: { text: L("conteggio", "count"), font: { size: 9 } } });
      plot(p.plotH, [{ x: d.hist_x_ui, y: d.hist, type: "bar", marker: { color: COL.dg } }], l1);
      const shapes = [];
      if (d.injected.pj_ui > 0) shapes.push(vline(d.injected.pj_mhz, COL.am, "dash"));
      const l2 = PL({ height: 170, showlegend: false, shapes });
      mergeAxis(l2, "xaxis", { type: "log", title: { text: L("frequenza [MHz] (ambra = PJ iniettato)", "frequency [MHz] (amber = injected PJ)"), font: { size: 9 } } });
      mergeAxis(l2, "yaxis", { title: { text: "TIE [mUI]", font: { size: 9 } } });
      plot(p.plotS, [{ x: d.spec_f_mhz, y: d.spec_mag_mui, line: { color: COL.dg, width: 1 } }], l2);
      const lb = PL({ height: 165, showlegend: false, shapes: [vline(0, COL.muted, "dot")] });
      mergeAxis(lb, "xaxis", { title: { text: L("fase di campionamento [UI]", "sampling phase [UI]"), font: { size: 9 } } });
      mergeAxis(lb, "yaxis", { type: "log", title: { text: L("BER da crossing (proxy)", "crossing-derived BER (proxy)"), font: { size: 9 } } });
      plot(p.plotB, [{ x: d.bathtub_x_ui, y: d.bathtub_ber_proxy, line: { color: COL.ok, width: 1.6 } }], lb);
      const alignText = LANG === "en" ? (d.align === "fase acquisita" ? "acquired phase" : "nominal TX center") : d.align;
      p.note.innerHTML = LANG === "en"
        ? `Alignment: ${alignText}. <b>Dual-Dirac model</b> (Derickson &amp; Müller, <i>Digital Communications T&amp;M</i>, §2.5): the tails of ANY jitter distribution with a Gaussian RJ component approach straight asymptotes on the Q scale Q(x)=√2·erf⁻¹(2CDF−1); their slope gives σ (RJ), their Q=0 intersections give DJ(δδ), and <b>TJ(p) = 2·Q_p·σ + DJ(δδ)</b> extrapolates total jitter to any BER. Two honest caveats from the book: DJ(δδ) ≤ DJ(pp) by construction (convolution pulls the edges inward), and fitting tails that have not yet reached the asymptotes OVERESTIMATES RJ (~15% in the book's example) — this bench fits at p&lt;0.08/p&gt;0.92, so treat TJ@1e-12 as a ≥6-orders extrapolation, not a measurement. PAM4 central-threshold crossings carry intrinsic pattern-dependent DDJ; none of this is a compliance result.`
        : `Allineamento: ${d.align}. <b>Modello dual-Dirac</b> (Derickson &amp; Müller, <i>Digital Communications T&amp;M</i>, §2.5): le code di QUALUNQUE distribuzione di jitter con una componente RJ gaussiana tendono a rette sul Q-scale Q(x)=√2·erf⁻¹(2CDF−1); la pendenza dà σ (RJ), le intersezioni a Q=0 danno il DJ(δδ), e <b>TJ(p) = 2·Q_p·σ + DJ(δδ)</b> estrapola il jitter totale a qualunque BER. Due avvertenze oneste dal libro: DJ(δδ) ≤ DJ(pp) per costruzione (la convoluzione "smussa" i bordi tirandoli verso l'interno), e fittare code che non hanno ancora raggiunto gli asintoti SOVRASTIMA l'RJ (~15% nell'esempio del libro) — questo banco fitta a p&lt;0.08/p&gt;0.92: il TJ@1e-12 è un'estrapolazione di ≥6 ordini di grandezza, non una misura. I crossing della soglia centrale PAM4 portano DDJ pattern-dependent intrinseco; niente di tutto questo è una misura di conformità.`;
    } catch (e) { p.note.innerHTML = e.message; }
  },
  onConfig(p) { p.history = []; p.lastSeed = null; this.refetch(p); },
  onTick(p) { if (throttled(p, 1200)) this.refetch(p); },
};

/* --- BER live --- */
PANEL_DEFS.berlive = {
  title: "BER live — accumulo", size: "s4",
  onConfig(p) { this.onTick(p); },
  make(p) { p.body.innerHTML = ""; p.ro = CE("div"); p.body.appendChild(p.ro); p.trend = CE("div", "plot"); p.body.appendChild(p.trend); this.onTick(p); },
  onTick(p) {
    const a = S.acc; if (!a) return;
    const ci = a.ber_ci95 || [];
    p.ro.innerHTML = "";
    if (a.last && a.last.link_up === false) {
      p.ro.appendChild(readout([
        { l: "LINK", v: "DOWN", cls: "fail", big: true, sub: "CDR o pattern lock non agganciano: nessun bit valido" },
        { l: L("record scartati", "discarded records"), v: String(a.link_down_records || 0), cls: "fail" },
      ]));
      plot(p.trend, [], PL({ height: 120, showlegend: false }));
      return;
    }
    p.ro.appendChild(readout([
      { l: "BER cumulativa", v: a.bit_errors_total ? sci(a.ber_cum) : (a.bits_total ? "< " + sci(ci[1]) : "—"), big: true, sub: `${eng(a.bit_errors_total)} err / ${eng(a.bits_total)}b`, title: "IC 95% con ipotesi IID: gli errori correlati dal DFE lo allargano" },
      { l: L("ultimo record", "last record"), v: sci(a.last.ber), sub: "GMI " + fix(a.last.gmi, 3) },
      { l: "SNR slicer", v: fix(a.last.snr_db, 1) + " dB", sub: "Q min " + fix(a.last.q_min, 2) },
      { l: L("BER gaussiana", "Gaussian BER"), v: sci(a.last.ber_levels_gaussian), sub: `Qmin PAM${S.cfg.modulation === "NRZ" ? 2 : 4}: ${sci(a.last.ber_qmin_gaussian)}`, title: L("modello completo per livello con soglie calibrate e distanza di Hamming; Qmin è il proxy worst-eye", "full per-level model with calibrated thresholds and Hamming distance; Qmin is the worst-eye proxy") },
      { l: "P @ PD", v: fix(a.last.p_pd_dbm, 2) + " dBm" },
    ]));
    const lay = PL({ height: 150, showlegend: false });
    mergeAxis(lay, "yaxis", { type: "log", title: { text: "BER cum.", font: { size: 9 } } });
    mergeAxis(lay, "xaxis", { title: { text: "record", font: { size: 9 } } });
    const hb = (a.hist && a.hist.ber) || [];
    plot(p.trend, [
      { y: a.ber_history, name: "cum", line: { color: COL.dg, width: 1.5 } },
      { y: hb, name: "inst", mode: "markers", marker: { color: COL.am, size: 3 } },
    ], lay);
  },
};

/* --- pannelli parametrici + plot --- */
PANEL_DEFS.stimulus = {
  title: "PPG — Pulse Pattern Generator", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    p.body.appendChild(paramsBlock(["symbol_rate_hz", "pattern", "prbs_order", "modulation", "pam4_mapping", "l2_frame_bytes", "n_symbols"]));
    p.editor = CE("div", "pattern-editor");
    const editorHead = CE("div", "pattern-editor-head", `<label>${L("Pattern HEX utente · byte MSB-first", "User HEX pattern · MSB-first bytes")}</label>`);
    const help = controlHelpButton("custom_pattern_hex"); help.style.position = "static"; editorHead.appendChild(help);
    p.hexInput = CE("input"); p.hexInput.type = "text"; p.hexInput.maxLength = 12288;
    p.hexInput.spellcheck = false; p.hexInput.placeholder = "A5 C3 F0 0F";
    p.hexApply = CE("button", "btn btn-accent", L("APPLICA HEX", "APPLY HEX"));
    p.hexApply.dataset.action = "pattern_apply";
    p.hexStatus = CE("span", "sub");
    const applyHex = async () => {
      try {
        const out = await POST("/api/config", {
          updates: { pattern: "custom_hex", custom_pattern_hex: p.hexInput.value },
        });
        S.cfg = out.cfg; cfgChips(); notify("config");
        p.hexStatus.textContent = L("applicato · ripetizione ciclica", "applied · cyclic repeat");
      } catch (e) { toast(e.message); }
    };
    p.hexApply.onclick = applyHex;
    p.hexInput.onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); applyHex(); } };
    p.editor.append(editorHead, p.hexInput, p.hexApply, p.hexStatus);
    p.body.appendChild(p.editor);
    p.ro = CE("div"); p.body.appendChild(p.ro);
    p.plotEl = CE("div", "plot"); p.body.appendChild(p.plotEl);
    p.syncEditor = () => {
      p.editor.hidden = S.cfg.pattern !== "custom_hex";
      if (document.activeElement !== p.hexInput) p.hexInput.value = S.cfg.custom_pattern_hex || "";
    };
    p.syncEditor(); this.refetch(p);
  },
  async refetch(p) {
    const d = await GET("/api/panel/stimulus"); acqBadge(p, d);
    p.ro.innerHTML = "";
    const info = d.pattern_info || {};
    const clauseName = (() => {
      if (S.cfg.pattern === "ssprq") return ["SSPRQ", "IEEE 802.3 Clause 120.5.11.2.3"];
      if (S.cfg.pattern === "custom_hex") return ["USER HEX", L("sequenza PPG di laboratorio · non-clause", "lab PPG sequence · non-clause")];
      if (S.cfg.pattern === "ssprq_like") return ["SSPRQ-like", L("meccanismo di stress, NON lo SSPRQ di clause (seed/segmenti prescritti mancanti)", "stress mechanism, NOT clause SSPRQ (prescribed seeds/segments missing)")];
      if (S.cfg.pattern !== "prbs") return null;
      if (S.cfg.modulation === "PAM4" && +S.cfg.prbs_order === 13) return ["PRBS13Q = QPRBS13", "IEEE 802.3 Clause 120.5.11.2.1"];
      if (S.cfg.modulation === "PAM4" && +S.cfg.prbs_order === 31) return ["PRBS31Q", "IEEE 802.3 Clause 120.5.11.2.2"];
      return [`PRBS${S.cfg.prbs_order}`, "ITU-T O.150 / " + L("uso comune", "common use")];
    })();
    const rows = [];
    if (clauseName) rows.push({ l: S.cfg.pattern === "custom_hex" ? L("pattern PPG", "PPG pattern") : L("pattern di clause", "clause pattern"), v: clauseName[0], cls: (S.cfg.pattern === "ssprq_like" || S.cfg.pattern === "custom_hex") ? "warn" : "ok", sub: clauseName[1], title: L("SSPRQ usa l'intero vettore machine-readable IEEE; PRBS13Q/31Q usano polinomio e mapping Gray. L'esattezza del pattern non implica conformità della misura.", "SSPRQ uses the complete IEEE machine-readable vector; PRBS13Q/31Q use the clause polynomial and Gray mapping. Pattern exactness does not imply measurement compliance.") });
    if (S.cfg.pattern === "ssprq") {
      rows.push({ l: L("periodo ufficiale", "official period"), v: Number(info.period_symbols).toLocaleString() + " sym", sub: Number(info.period_bits).toLocaleString() + " bit" });
      rows.push({ l: "SHA-256", v: (info.sha256 || "").slice(0, 16) + "…", sub: L("65.535 indici simbolo verificati", "65,535 verified symbol indices"), title: info.source || "" });
    } else if (S.cfg.pattern === "custom_hex") {
      rows.push({ l: L("periodo utente", "user period"), v: `${info.period_bytes || 0} B`, sub: `${info.period_bits || 0} bit · ${info.period_symbols || 0} sym` });
      rows.push({ l: "SHA-256", v: (info.sha256 || "").slice(0, 16) + "…", sub: L("byte normalizzati, MSB-first", "normalized bytes, MSB first") });
    } else if (S.cfg.pattern === "prbs") {
      rows.push({ l: `PRBS${d.prbs} ${L("periodo", "period")}`, v: Number(d.prbs_period).toLocaleString(), sub: d.prbs_poly });
      rows.push({ l: L("bilanciamento su un periodo", "full-period balance"), v: `${Number(d.prbs_ones).toLocaleString()} / ${Number(d.prbs_zeros).toLocaleString()}`, sub: L("uno / zero (differenza esatta: 1)", "ones / zeros (exact difference: 1)") });
    }
    p.ro.appendChild(readout(rows));
    const lay = PL({ height: 210, showlegend: false });
    mergeAxis(lay, "xaxis", { title: { text: "simbolo", font: { size: 10 } } });
    plot(p.plotEl, [{ y: d.symbols, line: { shape: "hv", color: COL.dg } }], lay);
  },
  onConfig(p) { syncParams(p.body); p.syncEditor(); this.refetch(p); },
};

PANEL_DEFS.tx = {
  title: "TX — FIR · DAC · driver", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    p.ffe = CE("div", "params");
    // FIR TX a N tap (3/5/7, main al centro): la stessa struttura che il
    // link training negozia via richieste inc/dec (Clause 72/136)
    p.buildFfe = () => {
      p.ffe.innerHTML = "";
      const taps = S.cfg.tx_ffe_taps, main = (taps.length - 1) / 2;
      taps.forEach((v, i) => {
        const w = CE("div", "param"); w.dataset.ffe = i;
        const name = i === main ? "c(0) main" : `c(${i - main > 0 ? "+" : ""}${i - main})`;
        const lims = i === main ? [0.5, 1.2] : [-0.35, 0.15];
        const lab = CE("label", "", `<span>TX FIR ${name}</span><b>${fix(v, 2)}</b>`);
        const rng = CE("input"); rng.type = "range"; rng.min = lims[0]; rng.max = lims[1]; rng.step = 0.01; rng.value = v;
        rng.oninput = () => { lab.querySelector("b").textContent = fix(+rng.value, 2);
          const t2 = [...S.cfg.tx_ffe_taps]; t2[i] = +rng.value; postConfig({ tx_ffe_taps: t2 }); };
        w.append(lab, rng, controlHelpButton("tx_ffe_taps")); p.ffe.appendChild(w);
      });
      const w2 = CE("div", "param");
      const tog = CE("button", "btn", taps.length === 3 ? "3 → 5 tap (c±2)" : "5 → 3 tap");
      tog.dataset.action = "tx_tap_count";
      tog.title = L("numero di tap del FIR TX: a 5 tap l'LT può equalizzare canali più duri", "TX FIR tap count: with 5 taps LT can equalize harder channels");
      tog.onclick = () => {
        const t2 = [...S.cfg.tx_ffe_taps];
        postConfig({ tx_ffe_taps: t2.length === 3 ? [0, t2[0], t2[1], t2[2], 0] : [t2[1], t2[2], t2[3]] });
      };
      w2.appendChild(tog); p.ffe.appendChild(w2);
      decorateControls(p.ffe);
    };
    p.buildFfe();
    p.body.appendChild(p.ffe);
    p.body.appendChild(paramsBlock(["dac_bits", "dac_bw_hz", "dac_full_scale_vpp", "driver_gain_v_per_unit", "driver_bw_hz", "driver_clip_v", "causal_filters"]));
    p.ro = CE("div"); p.body.appendChild(p.ro);
    p.plotH = CE("div", "plot"); p.body.appendChild(p.plotH);
    p.plotW = CE("div", "plot"); p.body.appendChild(p.plotW);
    p.body.appendChild(CE("div", "note w", L("Il clipping del driver è non invertibile: nessun equalizzatore a valle ricostruisce i picchi tagliati.", "Driver clipping is non-invertible: no downstream equalizer can rebuild the clipped peaks.")));
    this.refetch(p);
  },
  async refetch(p) {
    const d = await GET(`/api/panel/tx?source=${S.running ? "live" : "auto"}`); acqBadge(p, d);
    p.ro.innerHTML = "";
    p.ro.appendChild(readout([
      { l: "TX FIR H(0)", v: fix(d.h0, 4), sub: "Σc[k]" },
      { l: "TX FIR H(Nyq)", v: fix(d.hnyquist, 4), sub: "Σ(−1)ᵏc[k]" },
      { l: L("costo swing", "swing cost"), v: "×" + fix(d.swing_cost, 3), sub: `DAC LSB ${fix(1e3 * d.dac_lsb_v, 2)} mV` },
      { l: "clip DAC / driver", v: `${fix(d.dac_clip_pct, 3)} / ${fix(d.driver_clip_pct, 3)} %`, cls: d.driver_clip_pct > 0.1 ? "fail" : "ok" },
    ]));
    const lh = PL({ height: 205 });
    mergeAxis(lh, "xaxis", { title: { text: "f / Nyquist", font: { size: 10 } } });
    mergeAxis(lh, "yaxis", { title: { text: "dB", font: { size: 10 } } });
    plot(p.plotH, [
      { x: d.f_norm, y: d.ffe_db, name: "TX FIR", line: { color: COL.dg } },
      { x: d.f_norm, y: d.analog_db, name: "DAC×driver", line: { color: COL.el } },
      { x: d.f_norm, y: d.combined_db, name: L("totale TX", "TX total"), line: { color: COL.am, width: 2 } }], lh);
    const lw = PL({ height: 160, showlegend: false });
    mergeAxis(lw, "xaxis", { title: { text: "time [UI]", font: { size: 9 } } });
    mergeAxis(lw, "yaxis", { title: { text: "driver [V]", font: { size: 9 } } });
    plot(p.plotW, [{ x: d.t_ui, y: d.driver_v, line: { color: COL.el, width: 1 } }], lw);
  },
  onConfig(p) { syncParams(p.body);
    if (p.ffe.querySelectorAll("[data-ffe]").length !== S.cfg.tx_ffe_taps.length) p.buildFfe();
    for (const w of p.ffe.querySelectorAll("[data-ffe]")) { const i = +w.dataset.ffe; const r = w.querySelector("input");
      if (document.activeElement !== r) { r.value = S.cfg.tx_ffe_taps[i]; w.querySelector("label b").textContent = fix(S.cfg.tx_ffe_taps[i], 2); } }
    this.refetch(p); },
  onTick(p) { if (throttled(p, 1800)) this.refetch(p); },
};

PANEL_DEFS.channel = {
  title: "Canale elettrico · mezzo · crosstalk", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    p.body.appendChild(paramsBlock(["link_medium", "channel_il_nyquist_db", "return_loss_db", "echo_delay_ui", "group_delay_ripple_ps", "xtalk_next_db", "xtalk_fext_db", "s4p_pairs"]));
    p.body.appendChild(CE("div", "note", L("NEXT/FEXT a 0 dB = spenti; valori negativi = accoppiamento dell'aggressore (PRBS indipendente). In modalità <b>rame</b> la catena ottica è bypassata: canale → AFE (profili KR/CR/C2M).", "NEXT/FEXT at 0 dB = off; negative values = aggressor coupling (independent PRBS). In <b>copper</b> mode the optical chain is bypassed: channel → AFE (KR/CR/C2M profiles).")));
    p.src = CE("div"); p.body.appendChild(p.src);
    p.plotS = CE("div", "plot"); p.body.appendChild(p.plotS);
    p.plotP = CE("div", "plot"); p.body.appendChild(p.plotP);
    p.plotI = CE("div", "plot"); p.body.appendChild(p.plotI);
    p.plotC = CE("div", "plot"); p.body.appendChild(p.plotC);
    const up = CE("div", "scope-bar");
    up.innerHTML = `<input type="file" accept=".s2p,.S2P,.txt" style="font-size:11px"> <button class="btn" style="padding:3px 9px">usa S2P nel percorso</button> <button class="btn" style="padding:3px 9px">torna al modello</button>`;
    const [fileEl, btnUse, btnBack] = up.querySelectorAll("input,button");
    btnUse.dataset.action = "s2p_use"; btnBack.dataset.action = "s2p_model";
    btnUse.title = TT("carica S21/SDD21 dal file e lo inserisce nel datapath", "loads S21/SDD21 from file and inserts it in the datapath");
    btnBack.title = TT("bypassa il file e ripristina il modello analitico", "bypasses the file and restores the analytic model");
    btnUse.onclick = async () => {
      const f = fileEl.files[0]; if (!f) return toast(L("scegli un file .s2p", "choose an .s2p file"));
      const text = await f.text();
      POST("/api/s2p", { text, name: f.name, apply: true }).catch(e => toast(e.message));
    };
    btnBack.onclick = () => postConfig({ use_s2p_channel: false });
    p.body.appendChild(up);
    this.refetch(p);
  },
  async refetch(p) {
    const d = await GET("/api/panel/channel"); acqBadge(p, d);
    p.src.innerHTML = `<div class="note">Canale attivo: <b>${d.source}</b></div>`;
    const l1 = PL({ height: 190, showlegend: false, shapes: [vline(d.nyquist_ghz)] });
    mergeAxis(l1, "xaxis", { title: { text: "GHz", font: { size: 10 } } });
    mergeAxis(l1, "yaxis", { title: { text: "|S21| dB", font: { size: 10 } } });
    plot(p.plotS, [{ x: d.f_ghz, y: d.s21_db, line: { color: COL.el } }], l1);
    const lp = PL({ height: 210 });
    mergeAxis(lp, "xaxis", { title: { text: "tempo rispetto al main cursor [UI]", font: { size: 10 } } });
    mergeAxis(lp, "yaxis", { title: { text: "pulse normalizzata", font: { size: 10 } } });
    plot(p.plotP, [
      { x: d.pulse_t_ui, y: d.pulse, name: L("solo canale", "channel only"), line: { color: COL.el, width: 1.6 } },
      { x: d.pulse_t_ui, y: d.pulse_combo, name: L("canale × CTLE", "channel × CTLE"), line: { color: COL.ok, width: 1.6 } }], lp);
    const li = PL({ height: 190 });
    mergeAxis(li, "xaxis", { title: { text: L("tempo impulso [UI]", "impulse time [UI]"), font: { size: 10 } } });
    mergeAxis(li, "yaxis", { title: { text: L("impulse normalizzata", "normalized impulse"), font: { size: 10 } } });
    plot(p.plotI, [
      { x: d.impulse_t_ui, y: d.impulse, name: L("solo canale", "channel only"), line: { color: COL.el, width: 1.4 } },
      { x: d.impulse_t_ui, y: d.impulse_combo, name: L("canale × CTLE", "channel × CTLE"), line: { color: COL.ok, width: 1.4 } }], li);
    const l2 = PL({ height: 190, showlegend: false });
    mergeAxis(l2, "xaxis", { title: { text: "cursor [UI]", font: { size: 10 } } });
    mergeAxis(l2, "yaxis", { title: { text: "p[k]/p[0]", font: { size: 10 } } });
    plot(p.plotC, [
      { x: d.cursor_ui, y: d.cursor_val, type: "bar", name: L("canale", "channel"), marker: { color: COL.el } },
      { x: d.cursor_ui, y: d.cursor_combo, type: "bar", name: "channel×CTLE", marker: { color: COL.ok } }], Object.assign(l2, { barmode: "group", showlegend: true }));
    p.src.innerHTML += `<div class="note">${L("Pulse response", "Pulse response")}: <b>${d.pulse_plane}</b> · ISI RMS cursor = ${fix(d.isi_rms_combo, 3)}.</div>`;
  },
  onConfig(p) { syncParams(p.body); this.refetch(p); },
};

PANEL_DEFS.com = {
  title: "COM · IEEE 802.3 Annex 93A", size: "s8",
  make(p) {
    p.body.innerHTML = "";
    p.ro = CE("div"); p.body.appendChild(p.ro);
    p.table = CE("div", "standard-table"); p.body.appendChild(p.table);
    const grid = CE("div", "grid2");
    p.plotGrid = grid;
    p.plotP = CE("div", "plot"); p.plotN = CE("div", "plot"); grid.append(p.plotP, p.plotN);
    p.body.appendChild(grid);
    p.note = CE("div", "note w"); p.body.appendChild(p.note);
    this.refetch(p);
  },
  async refetch(p) {
    const requestId = (p.requestId || 0) + 1;
    p.requestId = requestId;
    const d = await GET("/api/panel/com");
    if (requestId !== p.requestId) return;
    acqBadge(p, d);
    if (!d.applicable) {
      p.ro.innerHTML = `<div class="note w"><b>${d.standard} · ${d.clause}</b><br>${L("Non applicabile alla configurazione attiva.", "Not applicable to the active configuration.")} ${d.reason || ""}</div>`;
      p.table.innerHTML = p.note.innerHTML = "";
      p.plotGrid.style.display = "none";
      return;
    }
    p.plotGrid.style.display = "grid";
    const w = d.worst_case;
    p.ro.innerHTML = "";
    p.ro.appendChild(readout([
      { l: "COM", v: fix(d.com_db, 2) + " dB", cls: d.com_db >= d.threshold_db ? "ok" : "fail", sub: `${d.model_result} · ${L("soglia modello", "model threshold")} ${fix(d.threshold_db, 1)} dB`, title: L("COM = 20·log10(A_s/A_ni), con A_ni dalla PDF cumulativa al DER₀. Il colore confronta il modello con la soglia, non certifica il canale.", "COM = 20·log10(A_s/A_ni), with A_ni from the cumulative PDF at DER₀. The color compares the model with the threshold; it does not certify the channel.") },
      { l: "FOM", v: fix(d.fom_db, 2) + " dB", sub: L("ottimizzazione RMS prima della PDF", "RMS optimization before the PDF") },
      { l: "A_s / A_ni", v: `${fix(w.a_s_mv, 2)} / ${fix(w.a_ni_mv, 2)} mV`, sub: `DER₀ ${sci(d.parameters.der0)}` },
      { l: L("conformità", "compliance"), v: d.compliance_result, cls: "warn", sub: L("nessun claim IEEE", "no IEEE claim") },
      { l: "CTLE / TX FFE", v: `${fix(w.ctle_gdc_db, 0)} dB`, sub: `[${w.tx_ffe.map(v => fix(v, 2)).join(", ")}]` },
      { l: L("ingresso", "input"), v: d.input_kind, sub: `${d.standard} · ${d.clause}` },
    ]));
    const rows = d.package_cases.map(r => r.com_db == null ? `<tr><td>${r.case.name}</td><td colspan="6">${r.error}</td></tr>` : `<tr>
      <td>${r.case.name}<br><span class="sub">TX ${r.case.tx_mm} / RX ${r.case.rx_mm} mm · ${r.case.zc_ohm} Ω</span></td>
      <td><b>${fix(r.com_db, 2)} dB</b></td><td>${fix(r.fom_db, 2)} dB</td>
      <td>${fix(r.peak_isi_at_der_mv, 2)} mV</td><td>${fix(r.peak_xtalk_at_der_mv, 2)} mV</td>
      <td>${fix(r.gaussian_at_der_mv, 2)} mV</td><td>${fix(r.ctle_gdc_db, 0)} dB</td></tr>`).join("");
    p.table.innerHTML = `<table class="mini"><tr><th>package case</th><th>COM</th><th>FOM</th><th>ISI@DER₀</th><th>XT@DER₀</th><th>Gaussian@DER₀</th><th>CTLE</th></tr>${rows}</table>`;
    const lp = PL({ height: 210, showlegend: false });
    mergeAxis(lp, "xaxis", { title: { text: "time [UI]", font: { size: 10 } } });
    mergeAxis(lp, "yaxis", { title: { text: L("pulse equalizzata [V]", "equalized pulse [V]"), font: { size: 10 } } });
    requestAnimationFrame(() => {
      if (requestId === p.requestId) plot(p.plotP, [{ x: w.pulse_t_ui, y: w.pulse_v, line: { color: COL.el, width: 1.5 } }], lp);
    });
    const ln = PL({ height: 210, showlegend: false });
    mergeAxis(ln, "xaxis", { title: { text: L("contributo", "contribution"), font: { size: 10 } } });
    mergeAxis(ln, "yaxis", { title: { text: "mV @ DER₀", font: { size: 10 } } });
    requestAnimationFrame(() => {
      if (requestId === p.requestId) plot(p.plotN, [{ x: ["ISI", "NEXT/FEXT", "Gaussian"], y: [w.peak_isi_at_der_mv, w.peak_xtalk_at_der_mv, w.gaussian_at_der_mv], type: "bar", marker: { color: [COL.am, COL.fail, COL.dg] } }], ln);
    });
    p.note.innerHTML = `<b>${L("Confine del risultato", "Result boundary")}</b> · ${d.deviations.map(x => `• ${x}`).join("<br>")}<br><b>${L("Piano", "Plane")}</b>: ${d.reference_plane}.`;
  },
  onConfig(p) { this.refetch(p); },
};

PANEL_DEFS.optical = {
  title: "Optical TX · fiber · levels", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    p.body.appendChild(paramsBlock(["optical_modulator", "laser_type", "electrical_drive_mode", "laser_dbm", "laser_linewidth_mhz", "vpi_v", "mzm_bias_rad", "mzm_bw_hz", "mzm_il_db", "chirp_alpha", "eml_bw_hz", "eml_er_db", "eml_il_db", "eml_chirp_alpha", "direct_laser_bw_hz", "direct_laser_er_db", "direct_laser_chirp_alpha", "coupling_il_db", "fiber_type", "fiber_km", "dispersion_ps_nm_km", "dispersion_slope_ps_nm2_km", "pmd_ps_sqrt_km", "pmd_power_split", "fiber_gamma_w_inv_km", "mmf_modal_bw_mhz_km", "wavelength_nm", "fiber_loss_db_km"]));
    p.ro = CE("div"); p.body.appendChild(p.ro);
    const grid = CE("div", "grid2");
    p.plot1 = CE("div", "plot"); p.plot2 = CE("div", "plot");
    p.plot3 = CE("div", "plot"); p.plot4 = CE("div", "plot");
    grid.append(p.plot1, p.plot2, p.plot3, p.plot4);
    p.body.appendChild(grid);
    p.note = CE("div", "note"); p.body.appendChild(p.note);
    this.refetch(p);
  },
  async refetch(p) {
    const d = await GET(`/api/panel/optical?source=${S.running ? "live" : "auto"}`); acqBadge(p, d);
    if (d.inactive) { p.ro.innerHTML = `<div class="note w">${d.reason}</div>`; p.plot1.innerHTML = p.plot2.innerHTML = p.plot3.innerHTML = p.plot4.innerHTML = ""; p.note.innerHTML = ""; return; }
    p.ro.innerHTML = "";
    p.ro.appendChild(readout([
      { l: L("architettura", "architecture"), v: d.modulator.toUpperCase(), sub: `${d.laser_type} · ${S.cfg.electrical_drive_mode}` },
      { l: "P @ PD", v: fix(d.budget["PD input"], 2) + " dBm" },
      { l: L("drive picco", "peak drive"), v: fix(d.drive_peak_v, 2) + " V", sub: d.vpi ? fix(d.drive_peak_v / d.vpi, 2) + "·Vπ" : "ER set " + fix(d.er_set_db, 1) + " dB" },
      { l: "1º nullo IM/DD", v: d.f_null_ghz ? fix(d.f_null_ghz, 1) + " GHz" : "∞", cls: d.f_null_ghz && d.f_null_ghz < d.nyquist_ghz ? "fail" : "" },
      ...(d.tdecq ? [{ l: "TDECQ", v: d.tdecq.tdecq_db == null ? "FAIL" : fix(d.tdecq.tdecq_db, 2) + " dB", cls: d.tdecq.tdecq_db != null && d.tdecq.tdecq_db <= 3.4 ? "ok" : "fail", sub: d.tdecq.tdecq_db != null ? `limite DR/FR ≤ 3.4 dB · Ceq ${fix(d.tdecq.ceq_db, 1)} dB` : L("occhio oltre il target SER", "eye beyond SER target"), title: L("IEEE 802.3 clause 121.8.5.3 (struttura): BT4 0.5·Bd + FFE 5 tap min-TDECQ + doppia fase ±0.05 UI + SER 4.8e-4; dichiarato non certificato", "IEEE 802.3 clause 121.8.5.3 (structure): BT4 0.5·Bd + min-TDECQ 5-tap FFE + dual phase ±0.05 UI + SER 4.8e-4; declared not certified") }] : []),
      { l: L("propagazione", "propagation"), v: d.fiber_type.toUpperCase(), sub: d.modal_bw_ghz ? `modal BW ${fix(d.modal_bw_ghz, 1)} GHz` : `β₂ ${sci(d.beta2_s2_m)} · β₃ ${sci(d.beta3_s3_m)}` },
      { l: "PMD / Kerr", v: `${fix(d.pmd_dgd_ps, 3)} ps / ${sci(d.nonlinear_phase_peak_rad)} rad`, sub: `linewidth ${fix(d.laser_linewidth_mhz, 1)} MHz` },
    ]));
    // 1) transfer del modulatore + istogramma di pilotaggio: DOVE lavora
    const l1 = PL({ height: 200 });
    mergeAxis(l1, "xaxis", { title: { text: d.modulator === "mzm" ? L("drive [V]", "drive [V]") : L("drive normalizzato", "normalized drive"), font: { size: 9 } } });
    mergeAxis(l1, "yaxis", { title: { text: "P/P_in", font: { size: 9 } } });
    const tr1 = [{ x: d.v_static, y: d.p_static, name: "transfer", line: { color: COL.op, width: 2 } }];
    if (d.drive_hist) tr1.push({ x: d.drive_hist.x, y: d.drive_hist.h.map(v => v * Math.max(...d.p_static) * 0.5), name: L("dove pilota il segnale", "drive occupancy"), type: "bar", marker: { color: "rgba(86,200,232,0.35)" } });
    plot(p.plot1, tr1, l1);
    // 2) link budget waterfall
    if (d.budget_steps) {
      const l2 = PL({ height: 200, showlegend: false });
      mergeAxis(l2, "yaxis", { title: { text: "dBm", font: { size: 9 } } });
      plot(p.plot2, [{
        x: d.budget_steps.map(b => tr(b.plane)), y: d.budget_steps.map(b => b.dbm),
        type: "bar", marker: { color: COL.op },
        text: d.budget_steps.map(b => (b.delta_db ? fix(b.delta_db, 1) + " dB" : fix(b.dbm, 1))),
        textposition: "outside", textfont: { size: 9 },
      }], l2);
    }
    // 3) livelli ottici P0..P3 al PD (le grandezze delle spec ottiche)
    if (d.p_levels) {
      const pl = d.p_levels;
      const l3 = PL({ height: 200, showlegend: false });
      mergeAxis(l3, "xaxis", { title: { text: L("livello ottico al PD", "optical level at PD"), font: { size: 9 } } });
      mergeAxis(l3, "yaxis", { title: { text: "dBm", font: { size: 9 } } });
      plot(p.plot3, [{
        x: pl.p_dbm.map((_, i) => "P" + i), y: pl.p_dbm, type: "bar",
        marker: { color: [COL.el, COL.ok, COL.am, COL.op].slice(0, pl.p_dbm.length) },
        text: pl.p_dbm.map(v => fix(v, 2)), textposition: "outside", textfont: { size: 9 },
      }], l3);
      p.note.innerHTML = `OMA<sub>outer</sub> ${fix(pl.oma_outer_mw, 3)} mW` +
        (pl.oma_inner_mw != null ? ` · OMA<sub>inner</sub> ${fix(pl.oma_inner_mw, 3)} mW` : "") +
        ` · ER ${fix(pl.er_db, 2)} dB · RLM ${fix(pl.rlm_proxy, 3)} — ` +
        L("misure proxy al centro strumento (niente reference receiver di clause: non è TDECQ)",
          "proxy measurements at instrument center (no clause reference receiver: this is not TDECQ)");
    } else {
      p.plot3.innerHTML = ""; p.note.innerHTML = L("livelli ottici non stimabili su questo record", "optical levels not estimable on this record");
    }
    // 4) fading CD + chirp istantaneo
    const l4 = PL({ height: 200, shapes: [vline(d.nyquist_ghz)] });
    mergeAxis(l4, "xaxis", { title: { text: "GHz", font: { size: 9 } } });
    mergeAxis(l4, "yaxis", { title: { text: L("fading CD [dB]", "CD fading [dB]"), font: { size: 9 } }, range: [-50, 5] });
    const tr4 = [{ x: d.fade_f_ghz, y: d.fade_db, name: "IM/DD", line: { color: COL.op } }];
    if (d.f_null_ghz) l4.shapes.push(vline(d.f_null_ghz, COL.fail, "dot"));
    plot(p.plot4, tr4, l4);
  },
  onConfig(p) { syncParams(p.body); this.refetch(p); },
  onTick(p) { if (throttled(p, 1600)) this.refetch(p); },
};

PANEL_DEFS.adc = {
  title: "ADC interleaved · sampling & decisioni", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    p.body.appendChild(paramsBlock(["adc_bits", "adc_full_scale_vpp", "adc_jitter_rms_fs", "adc_phase_ui", "adc_gain_mismatch_rms", "adc_offset_mismatch_rms_v", "adc_skew_mismatch_rms_fs",
      "adc_interleaves", "adc_ranks", "adc_cal_mode", "adc_frontend_bw_hz", "adc_bw_mismatch_pct", "adc_noise_rms_mv"]));
    const g = CE("div", "grid2");
    p.plotHist = CE("div", "plot"); p.plotScat = CE("div", "plot");
    g.append(p.plotHist, p.plotScat); p.body.appendChild(g);
    p.plotEl = CE("div", "plot"); p.body.appendChild(p.plotEl);
    p.tbl = CE("div"); p.body.appendChild(p.tbl);
    this.refetch(p);
  },
  async refetch(p) {
    const d = await GET("/api/panel/adc"); acqBadge(p, d);
    if (d.sampling) {
      const sm = d.sampling;
      // istogrammi data vs edge: i 4 modi PAM4 sui campioni DATA, le
      // transizioni sugli EDGE — il plot classico del front-end 2 sps
      const l1 = PL({ height: 200, shapes: sm.thresholds_v.map(t2 => vline(t2, COL.ok, "dot")), barmode: "overlay" });
      mergeAxis(l1, "xaxis", { title: { text: "V @ ADC", font: { size: 9 } } });
      mergeAxis(l1, "yaxis", { type: "log", title: { text: "count", font: { size: 9 } } });
      plot(p.plotHist, [
        { x: sm.hist_x, y: sm.data_hist.map(v => Math.max(v, 0.5)), type: "bar", name: "DATA", marker: { color: COL.dg }, opacity: 0.75 },
        { x: sm.hist_x, y: sm.edge_hist.map(v => Math.max(v, 0.5)), type: "bar", name: "EDGE", marker: { color: COL.am }, opacity: 0.55 },
      ], l1);
      // hard decision al piano ADC: campioni colorati per livello deciso
      const colors = [COL.fail, COL.am, COL.el, COL.ok];
      const l2 = PL({ height: 200, showlegend: false, shapes: sm.thresholds_v.map(t2 => hline(t2, COL.muted, "dot")) });
      mergeAxis(l2, "xaxis", { title: { text: L("simbolo (dal lock)", "symbol (from lock)"), font: { size: 9 } } });
      mergeAxis(l2, "yaxis", { title: { text: L("campione DATA [V]", "DATA sample [V]"), font: { size: 9 } } });
      const traces = [0, 1, 2, 3].map(lv => ({
        x: sm.scatter_y.map((_, i) => i).filter(i => sm.scatter_dec[i] === lv),
        y: sm.scatter_y.filter((_, i) => sm.scatter_dec[i] === lv),
        mode: "markers", marker: { color: colors[lv], size: 2.5 },
      })).filter(t2 => t2.y.length);
      plot(p.plotScat, traces, l2);
    } else {
      p.plotHist.innerHTML = `<div class="note w">${L("CDR non agganciato: nessun istante di campionamento deciso — i plot DATA/EDGE esistono solo col lock.", "CDR not locked: no decided sampling instants — DATA/EDGE plots only exist with lock.")}</div>`;
      p.plotScat.innerHTML = "";
    }
    if (d.tone_f_ghz) {
      const lay = PL({ height: 190, shapes: (d.lines_ghz || []).map(x => vline(x, COL.fail, "dot")) });
      mergeAxis(lay, "yaxis", { range: [-110, 5], title: { text: "dBFS", font: { size: 10 } } });
      mergeAxis(lay, "xaxis", { title: { text: "GHz", font: { size: 10 } } });
      plot(p.plotEl, [
        { x: d.tone_f_ghz, y: d.tone_ideal_db, name: L("quantizzazione", "quantization"), line: { color: COL.muted, width: 1 } },
        { x: d.tone_f_ghz, y: d.tone_mm_db, name: L("effettivo (mism.+jitter+rumore)", "effective (mism.+jitter+noise)"), line: { color: COL.dg, width: 1 } }], lay);
      const ar = d.arch || {};
      p.tbl.innerHTML = `<div class="readout">
        <div class="ro"><label>SNDR / ENOB</label><b>${fix(d.sndr[1], 1)} dB · ${fix(d.enob[1], 2)} b</b><span class="sub">${L("tono basso", "low tone")} ${d.tone_low_ghz ? fix(d.tone_low_ghz, 1) + " GHz" : ""} · ${L("ideale", "ideal")} ${fix(d.sndr[0], 1)} dB</span></div>
        <div class="ro"><label>ENOB @ Nyq</label><b>${d.enob_nyq ? fix(d.enob_nyq[1], 2) + " b" : "—"}</b><span class="sub">${d.sndr_nyq ? "SNDR " + fix(d.sndr_nyq[1], 1) + " dB · spur " + fix(d.spur_nyq_dbfs, 0) + " dBFS @ " + fix(d.tone_nyq_ghz, 1) + " GHz" : ""}</span></div>
        <div class="ro"><label>${L("architettura", "architecture")}</label><b>${ar.interleaves || "—"}×${ar.ranks || 1}R</b><span class="sub">cal ${ar.cal_mode || "—"} ×${fix(ar.cal_effective, 2)}${ar.frontend_bw_ghz ? " · T/H " + fix(ar.frontend_bw_ghz, 0) + " GHz" : ""}${ar.rank_bw_ghz ? " (" + ar.rank_bw_ghz.map(b => fix(b, 0)).join("/") + ")" : ""}</span></div>
        <div class="ro"><label>LSB / clip</label><b>${fix(d.lsb_mv, 2)} mV</b><span class="sub">${fix(d.clip_pct, 3)}%${ar.noise_rms_mv ? " · " + L("rumore", "noise") + " " + fix(ar.noise_rms_mv, 1) + " mV" : ""}</span></div></div>`;
    } else {
      plot(p.plotEl, [{ x: d.code_hist.x, y: d.code_hist.h.map(v => Math.max(v, 0.5)), type: "bar", marker: { color: COL.el } }],
        (() => { const l3 = PL({ height: 150, showlegend: false, shapes: [vline(-d.fs_v, COL.fail, "dash"), vline(d.fs_v, COL.fail, "dash")] });
          mergeAxis(l3, "xaxis", { title: { text: L("occupazione codici su full-scale (clip = righe rosse)", "code occupancy over full scale (clip = red lines)"), font: { size: 9 } } });
          mergeAxis(l3, "yaxis", { type: "log" }); return l3; })());
      p.tbl.innerHTML = `<div class="readout"><div class="ro"><label>LSB / clip</label><b>${fix(d.lsb_mv, 2)} mV</b><span class="sub">${fix(d.clip_pct, 3)}%</span></div></div>` +
        `<div class="note">${L("Tone-lab SNDR/ENOB dopo la prima run full; i plot sopra sono live per record.", "Tone-lab SNDR/ENOB after the first full run; the plots above are live per record.")}</div>`;
    }
  },
  onConfig(p) { syncParams(p.body); this.refetch(p); },
  onTick(p) { if (throttled(p, 1600)) this.refetch(p); },
};

PANEL_DEFS.timing = {
  title: "Timing · CDR (nel datapath)", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    p.body.appendChild(paramsBlock(["cdr_mode", "cdr_bw", "cdr_damping", "rx_ppm_offset"]));
    p.ro = CE("div"); p.body.appendChild(p.ro);
    const g = CE("div", "grid2");
    p.plot1 = CE("div", "plot"); p.plot2 = CE("div", "plot");
    p.plot3 = CE("div", "plot"); p.plot4 = CE("div", "plot");
    g.append(p.plot1, p.plot2, p.plot3, p.plot4);
    p.body.appendChild(g);
    p.strip = CE("div", "plot"); p.body.appendChild(p.strip);
    const bar = CE("div", "scope-bar");
    const btnJtf = CE("button", "btn btn-accent", L("Misura jitter transfer (~3 s)", "Measure jitter transfer (~3 s)"));
    btnJtf.dataset.action = "jtf";
    btnJtf.onclick = async () => {
      btnJtf.disabled = true;
      try {
        const d2 = await POST("/api/experiment/jtf", {});
        const ok = d2.points.filter(q => q.jtf_db != null);
        const lay = PL({ height: 190, showlegend: false, shapes: [hline(-3, COL.muted, "dash"), vline(d2.loop_bw_mhz, COL.ok, "dot")] });
        mergeAxis(lay, "xaxis", { type: "log", title: { text: "PJ [MHz]", font: { size: 9 } } });
        mergeAxis(lay, "yaxis", { title: { text: L("OJTF misurata [dB]", "measured OJTF [dB]"), font: { size: 9 } }, range: [-30, 6] });
        plot(p.plot4, ok.length ? [{ x: ok.map(q => q.freq_mhz), y: ok.map(q => q.jtf_db), mode: "lines+markers", line: { color: COL.am, width: 2 } }] : [], lay);
        p.jtfDone = true;
      } catch (e) { toast(e.message); }
      btnJtf.disabled = false;
    };
    bar.append(btnJtf, CE("span", "", L("OJTF: 0 dB = il loop insegue il PJ; il picco vicino al corner è il jitter peaking; il −3 dB è la banda REALE del loop (verde = banda impostata).", "OJTF: 0 dB = the loop tracks the PJ; the peak near the corner is jitter peaking; the −3 dB crossing is the ACTUAL loop bandwidth (green = configured).")));
    p.body.appendChild(bar);
    p.note = CE("div", "note"); p.body.appendChild(p.note);
    this.refetch(p);
  },
  async refetch(p) {
    const d = await GET("/api/panel/timing"); acqBadge(p, d);
    p.ro.innerHTML = "";
    if (d.cdr) {
      const c = d.cdr;
      p.ro.appendChild(readout([
        { l: "CDR " + d.mode, v: c.locked ? "LOCKED" : "UNLOCKED", cls: c.locked ? "ok" : "fail", sub: c.locked ? `${L("lock @ simbolo", "lock @ symbol")} ${c.lock_symbol}` : c.detail, big: true },
        // il TED è il cuore del loop: errore di fase per simbolo dalle
        // decisioni (Gardner/M&M), guadagno stimato con probe cieco S-curve
        { l: "TED " + (d.mode === "mm" ? "Mueller-Müller" : d.mode === "gardner" ? "Gardner" : d.mode), v: c.ted_gain != null ? fix(c.ted_gain, 2) + " /UI" : "—", sub: L("guadagno S-curve (probe cieco) · TED → filtro PI → NCO", "S-curve gain (blind probe) · TED → PI filter → NCO"), title: L("l'errore di fase per simbolo viene dal TED sulle decisioni; il loop PI lo integra e muove l'NCO", "the per-symbol phase error comes from the decision-based TED; the PI loop integrates it and steers the NCO") },
        { l: "pattern lock (BERT)", v: c.pattern_locked ? "SYNC" : "NO SYNC", cls: c.pattern_locked ? "ok" : "fail", sub: c.pattern_lag != null ? `lag ${c.pattern_lag} · |corr| ${fix(Math.abs(c.pattern_corr), 2)}` : "—" },
        { l: "cycle slips", v: String(c.cycle_slips), cls: c.cycle_slips ? "fail" : "ok" },
        { l: "link", v: d.link_up ? "UP" : "DOWN", cls: d.link_up ? "ok" : "fail", sub: c.ppm_set ? `${L("offset impostato", "set offset")} ${c.ppm_set} ppm` : "" },
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
      // istogramma dell'errore di fase del loop (tau detrended, log-y)
      {
        const n = c.tau.length, mx = (n - 1) / 2;
        let num = 0, den = 0; const my = c.tau.reduce((x, y) => x + y, 0) / n;
        for (let i = 0; i < n; i++) { num += (i - mx) * (c.tau[i] - my); den += (i - mx) ** 2; }
        const b = num / den;
        const resid = c.tau.map((v, i) => v - (my + b * (i - mx)));
        const bins = 60, hmin = Math.min(...resid), hmax = Math.max(...resid);
        const hh = new Array(bins).fill(0);
        for (const v of resid) hh[Math.min(bins - 1, Math.max(0, Math.floor((v - hmin) / (hmax - hmin || 1) * bins)))]++;
        const l3 = PL({ height: 190, showlegend: false });
        mergeAxis(l3, "xaxis", { title: { text: L("errore di fase del loop [UI]", "loop phase error [UI]"), font: { size: 9 } } });
        mergeAxis(l3, "yaxis", { type: "log", title: { text: "count", font: { size: 9 } } });
        plot(p.plot3, [{ x: hh.map((_, i) => hmin + (i + 0.5) * (hmax - hmin) / bins), y: hh.map(v => Math.max(v, 0.5)), type: "bar", marker: { color: COL.dg } }], l3);
      }
      // S-curve dei TED dal riferimento full (finché non c'è una JTF misurata)
      if (d.gardner && !p.jtfDone) {
        const ls = PL({ height: 190 });
        mergeAxis(ls, "xaxis", { title: { text: L("fase [UI] — S-curve TED", "phase [UI] — TED S-curve"), font: { size: 9 } } });
        plot(p.plot4, [
          { x: d.phase_ui, y: d.gardner, name: "Gardner", line: { color: COL.dg } },
          { x: d.phase_ui, y: d.mm, name: "MM", line: { color: COL.am } }], ls);
      }
      p.note.innerHTML = L("Loop PI del 2° ordine + NCO <b>nel datapath</b>: gli istanti di campionamento di FSE/DFE/BER sono quelli del loop; l'allineamento viene dal pattern lock, non da un oracle. Senza lock il link è DOWN e le metriche non esistono.", "2nd-order PI loop + NCO <b>in the datapath</b>: FSE/DFE/BER sampling instants come from the loop; alignment comes from pattern lock, not from an oracle. Without lock the link is DOWN and metrics do not exist.");
    } else if (d.phase_ui) {
      p.ro.appendChild(readout([
        { l: "modalità", v: "ORACLE (ideale)", cls: "warn", sub: L("riferimento dichiarato, non un ricevitore", "declared reference, not a receiver") },
        { l: L("delay + fase", "delay + phase"), v: `${d.delay >= 0 ? "+" : ""}${d.delay} UI · ${fix(d.best_phase, 3)}` },
      ]));
      const l1 = PL({ height: 200, showlegend: false, shapes: [vline(d.best_phase, COL.ok)] });
      mergeAxis(l1, "xaxis", { title: { text: "fase [UI]", font: { size: 10 } } });
      mergeAxis(l1, "yaxis", { title: { text: "MSE rel [dB]", font: { size: 10 } } });
      plot(p.plot1, [{ x: d.phase_ui, y: d.mse_db, line: { color: COL.dg, width: 2 } }], l1);
      p.plot2.innerHTML = "";
      p.note.innerHTML = L("Acquisition oracle: minimo MSE usando i simboli noti — utile come riferimento ideale.", "Oracle acquisition: MSE minimum using known symbols — useful as an ideal reference.");
    }
  },
  onConfig(p) { syncParams(p.body); this.refetch(p); },
  drawStrip(p) {
    const a = S.acc; if (!a || !a.hist || !p.strip) return;
    const lay = PL({ height: 130, showlegend: false, yaxis2: { overlaying: "y", side: "right", title: { text: "\u03c3(\u03c4) [mUI]", font: { size: 9 } }, gridcolor: "rgba(0,0,0,0)" } });
    mergeAxis(lay, "xaxis", { title: { text: L("record \u2014 CDR nel tempo (acquisizione)", "record \u2014 CDR over time (acquisition)"), font: { size: 9 } } });
    mergeAxis(lay, "yaxis", { title: { text: "\u0394f [ppm]", font: { size: 9 } } });
    plot(p.strip, [
      { y: a.hist.f_ppm, name: "\u0394f", line: { color: COL.am, width: 1.2 } },
      { y: a.hist.tau_rms_ui.map(v => v == null ? null : v * 1000), name: "\u03c3(\u03c4)", yaxis: "y2", line: { color: COL.dg, width: 1.2 } },
    ], lay);
  },
  onTick(p) { this.drawStrip(p); if (throttled(p, 1600)) this.refetch(p); },
};

PANEL_DEFS.eq = {
  title: "Equalizzazione — RX FFE (FSE T/2) + DFE", size: "s6",
  make(p) { p.body.innerHTML = ""; p.body.appendChild(paramsBlock(["fse_taps", "dfe_taps", "training_start", "training_stop"])); p.plot1 = CE("div", "plot"); p.body.appendChild(p.plot1); p.plot2 = CE("div", "plot"); p.body.appendChild(p.plot2); this.refetch(p); },
  async refetch(p) {
    const d = await GET("/api/panel/eq"); acqBadge(p, d);
    if (d.link_down) { p.plot1.innerHTML = `<div class="note w">${L("LINK DOWN: nessun equalizzatore adattato.", "LINK DOWN: no equalizer adapted.")}</div>`; p.plot2.innerHTML = ""; return; }
    const l1 = PL({ height: 190 });
    mergeAxis(l1, "xaxis", { title: { text: "posizione [UI]", font: { size: 10 } } });
    plot(p.plot1, [
      { x: d.fse_pos_ui, y: d.fse_taps, name: "RX FFE · FSE T/2", type: "bar", marker: { color: COL.dg } },
      { x: d.dfe_taps.map((_, i) => i + 1), y: d.dfe_taps, name: "DFE postcursor", type: "bar", marker: { color: COL.am } }], l1);
    const rows = d.ber_rows.map(r => `<tr><td>${r.stage}</td><td>${sci(r.BER)}</td><td>${r.bit_errors}/${r.bits}</td></tr>`).join("");
    p.plot2.innerHTML = `<table class="mini"><tr><th>stadio</th><th>BER</th><th>errori</th></tr>${rows}</table>` +
      `<div class="note">${L("Partizione classica dell'equalizzazione SerDes: <b>TX FIR</b> (pre-enfasi, negoziata dall'LT) → CTLE analogica → <b>RX FFE</b> = questo FSE T/2 adattato NLMS (ISI pre-cursore, amplifica anche il rumore) → <b>DFE</b> (post-cursore dai simboli decisi, senza noise enhancement ma con error propagation).", "The classic SerDes equalization split: <b>TX FIR</b> (pre-emphasis, negotiated by LT) → analog CTLE → <b>RX FFE</b> = this NLMS-adapted T/2 FSE (pre-cursor ISI, also amplifies noise) → <b>DFE</b> (post-cursor from decided symbols, no noise enhancement but error propagation).")}</div>`;
  },
  onConfig(p) { syncParams(p.body); this.refetch(p); },
  onTick(p) { if (throttled(p, 1600)) this.refetch(p); },
};

PANEL_DEFS.decisions = {
  title: "Decisioni — istogrammi e confusion", size: "s6",
  make(p) { p.body.innerHTML = ""; p.ro = CE("div"); p.body.appendChild(p.ro); p.strip = CE("div", "plot"); p.body.appendChild(p.strip); p.plotH = CE("div", "plot"); p.body.appendChild(p.plotH); p.plotC = CE("div", "plot"); p.body.appendChild(p.plotC); this.refetch(p); },
  async refetch(p) {
    const d = await GET("/api/panel/decisions"); acqBadge(p, d);
    if (d.link_down) { p.ro.innerHTML = ""; p.ro.appendChild(readout([{ l: "LINK", v: "DOWN", cls: "fail", big: true, sub: "nessuna decisione senza lock" }])); p.plotH.innerHTML = ""; p.plotC.innerHTML = ""; return; }
    p.ro.innerHTML = "";
    p.ro.appendChild(readout([
      { l: "SNR slicer", v: fix(d.snr_db, 2) + " dB" },
      { l: "Q min", v: fix(d.q_min, 2), sub: d.q_per_eye.map(q => fix(q, 1)).join(" · ") },
      { l: L("BER contata DFE", "counted DFE BER"), v: sci(d.ber_counted), cls: d.ber_counted <= 5e-3 ? "ok" : "fail", sub: d.post_fec_ber != null ? `post-FEC ${sci(d.post_fec_ber)} · ${d.fec_frames_uncorrectable} ${L("frame persi", "lost frames")}` : L("nessun FEC nel percorso", "no in-path FEC"), title: L("errori realmente contati nella finestra di validation; il post-FEC è il risultato del decoder RS nel percorso", "errors actually counted in the validation window; post-FEC is the in-path RS decoder result") },
      { l: L("BER gaussiana livelli / Qmin", "Gaussian level / Qmin BER"), v: `${sci(d.ber_levels_gaussian)} / ${sci(d.ber_qmin_gaussian)}`, title: L("la prima integra le gaussiane di ogni livello e la distanza Hamming; la seconda usa il solo occhio peggiore con il fattore PAMn corretto", "the first integrates each level Gaussian and Hamming distance; the second uses only the worst eye with the correct PAMn factor") },
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
  drawStrip(p) {
    const a = S.acc; if (!a || !a.hist || !p.strip) return;
    const lay = PL({ height: 130, showlegend: false, yaxis2: { overlaying: "y", side: "right", title: { text: "Q min", font: { size: 9 } }, gridcolor: "rgba(0,0,0,0)" } });
    mergeAxis(lay, "xaxis", { title: { text: L("record \u2014 SNR nel tempo (acquisizione)", "record \u2014 SNR over time (acquisition)"), font: { size: 9 } } });
    mergeAxis(lay, "yaxis", { title: { text: "SNR slicer [dB]", font: { size: 9 } } });
    plot(p.strip, [
      { y: a.hist.snr_db, name: "SNR", line: { color: COL.dg, width: 1.2 } },
      { y: a.hist.q_min, name: "Q min", yaxis: "y2", line: { color: COL.am, width: 1.2 } },
    ], lay);
  },
  onTick(p) { this.drawStrip(p); if (throttled(p, 1600)) this.refetch(p); },
};

PANEL_DEFS.standards = {
  title: "Standard IEEE / OIF", size: "s8",
  make(p) { p.body.innerHTML = ""; p.host = CE("div"); p.body.appendChild(p.host); this.refetch(p); },
  async refetch(p) {
    const d = await GET("/api/panel/standards"); acqBadge(p, d);
    p.host.innerHTML = "";
    const items = [
      { l: L("corsia", "lane"), v: fix(d.gbd, 3) + " GBd", sub: d.modulation + " · " + fix(d.lane_gbs, 1) + " Gb/s" },
      { l: L("famiglia più vicina", "closest family"), v: d.family ? d.family.split("—")[0] : "—", sub: d.deviation_pct != null ? fix(d.deviation_pct, 1) + "%" : "" },
      { l: L("modello FEC", "FEC model"), v: d.fec_name },
    ];
    if (!d.link_up) items.push({ l: "confronto", v: "LINK DOWN", cls: "fail", sub: L("nessuna BER da confrontare", "no BER to compare") });
    else if (d.threshold) items.push(
      { l: L("soglia pre-FEC (modello iid)", "pre-FEC threshold (iid model)"), v: sci(d.threshold), sub: "BER contata " + sci(d.ber) },
      { l: "posizione", v: d.below ? L("SOTTO la soglia del modello", "BELOW the model threshold") : L("SOPRA la soglia del modello", "ABOVE the model threshold"), cls: d.below ? "ok" : "fail", sub: "rapporto log " + fix(d.ratio_db, 1) + L(" dB (non è un margine di conformità)", " dB (not a compliance margin)"), title: "indicazione dal modello binomiale iid del nostro codec: NON è una misura normativa (COM/TDECQ richiedono procedure di clause)" });
    p.host.appendChild(readout(items));
    const manifest = (d.manifest || []).map(r => `<tr>
      <td><b>${r.block}</b></td><td>${r.value}</td>
      <td><span class="badge ${r.basis === "standard" || r.basis === "standard-context" ? "ok" : (r.basis === "custom" ? "warn" : "")}">${r.basis}</span><br><span class="sub">${r.note}</span></td></tr>`).join("");
    p.host.appendChild(CE("div", "standard-table", `<h3>${L("Manifest del preset attivo", "Active preset manifest")}: ${d.active_profile || L("configurazione modificata/custom", "modified/custom configuration")}</h3>
      <table class="mini"><tr><th>${L("blocco", "block")}</th><th>${L("valore applicato", "applied value")}</th><th>${L("origine del valore", "value provenance")}</th></tr>${manifest}</table></div>`));
    const rows = d.profiles.map(x => `<tr class="${x.compatible ? "profile-hit" : ""}">
      <td>${x.compatible ? "● " : ""}<a href="${x.source}" target="_blank" rel="noreferrer">${x.interface || x.name}</a><br><span class="sub">${x.standard || ""}</span></td>
      <td>${x.lanes || "—"}<br><span class="sub">${x.plane || ""}</span></td>
      <td>${x.medium || "—"} · ${x.reach || "—"}</td><td>${x.fec || "—"}</td>
      <td><span class="badge ${x.status === "draft" ? "warn" : "ok"}">${x.status || "—"}</span><br><span class="sub">${x.claim === "context" ? L("solo contesto", "context only") : L("contesto draft", "draft context")}</span></td></tr>`).join("");
    p.host.appendChild(CE("div", "standard-table", `<table class="mini"><tr><th>${L("interfaccia", "interface")}</th><th>${L("corsie / piano", "lanes / plane")}</th><th>${L("mezzo / reach", "medium / reach")}</th><th>FEC</th><th>${L("stato / claim", "status / claim")}</th></tr>${rows}</table>`));
    const mrows = (d.measurement_contracts || []).map(m => `<tr>
      <td><b>${m.measure}</b><br><span class="sub">${m.reference_plane}</span></td>
      <td><a href="${m.source}" target="_blank" rel="noreferrer">${m.standard}</a><br><span class="sub">${m.clause}</span></td>
      <td><span class="badge ${m.applicable ? (["annex-subset", "clause-structured", "versioned-procedure"].includes(m.implementation) ? "warn" : "") : ""}">${m.applicable ? m.implementation : L("non applicabile", "not applicable")}</span></td>
      <td><span class="badge warn">${m.compliance}</span><br><span class="sub">${m.note}</span></td></tr>`).join("");
    p.host.appendChild(CE("div", "standard-table", `<h3>${L("Contratto normativo delle misure", "Measurement standards contract")}</h3><table class="mini"><tr><th>${L("misura / piano", "measure / plane")}</th><th>IEEE 802.3 / clause</th><th>${L("implementazione", "implementation")}</th><th>${L("claim consentito", "allowed claim")}</th></tr>${mrows}</table>`));
    p.host.appendChild(CE("div", "note w", L(
      "Il preset applica l'intera LinkConfig, quindi ogni blocco riceve un valore. Il manifest separa però ciò che deriva dall'interfaccia pubblica da ciò che è una scelta architetturale rappresentativa di LabPro: IEEE/OIF normalmente non prescrivono DAC, CTLE, ADC, CDR, numero di tap o MZM contro EML. PASS indica checkpoint del modello, non conformità.",
      "The preset applies the full LinkConfig, so every block receives a value. The manifest still separates public-interface context from LabPro's representative architecture choices: IEEE/OIF normally do not mandate the DAC, CTLE, ADC, CDR, tap count, or MZM versus EML. PASS means model checkpoints, never compliance.")));
  },
  onConfig(p) { this.refetch(p); },
};

PANEL_DEFS.dr4proc = {
  title: "DR4 · procedura fisica end-to-end", size: "s8",
  make(p) {
    p.body.innerHTML = "";
    const bar = CE("div", "scope-bar");
    p.run = CE("button", "btn btn-accent", L("ESEGUI DR4 COMPLETA (~7 s)", "RUN FULL DR4 (~7 s)"));
    p.run.dataset.action = "dr4";
    p.run.title = TT("usa tutti i 65.535 simboli SSPRQ e i due estremi di dispersione; non modifica il banco", "uses all 65,535 SSPRQ symbols and both dispersion endpoints; does not modify the bench");
    p.seed = CE("input"); p.seed.type = "number"; p.seed.min = "0"; p.seed.max = "4294967295"; p.seed.value = "500283"; p.seed.style.width = "110px";
    bar.append(p.run, CE("span", "", "seed"), p.seed);
    p.body.appendChild(bar);
    p.host = CE("div"); p.body.appendChild(p.host);
    p.host.innerHTML = `<div class="note">${L(
      "Procedura LabPro versionata sul target DR4 per-lane: SSPRQ pubblico completo → TX → due canali di dispersione → reference RX TDECQ → PD/TIA/ADC/CDR/DSP. Il verdetto del modello resta separato dalla conformità IEEE.",
      "Versioned LabPro procedure for the per-lane DR4 target: full public SSPRQ → TX → two dispersion channels → TDECQ reference RX → PD/TIA/ADC/CDR/DSP. The model verdict remains separate from IEEE compliance.")}</div>`;
    p.run.onclick = () => this.runProcedure(p);
  },
  async runProcedure(p) {
    p.run.disabled = true;
    p.run.textContent = L("MISURA IN CORSO…", "MEASURING…");
    try {
      const out = await POST("/api/experiment/dr4-tdecq", { seed: +p.seed.value });
      this.render(p, out.report);
    } catch (e) { toast(e.message); }
    p.run.disabled = false;
    p.run.textContent = L("ESEGUI DR4 COMPLETA (~7 s)", "RUN FULL DR4 (~7 s)");
  },
  render(p, d) {
    p.host.innerHTML = "";
    const modelOk = d.model_status === "PASS";
    p.host.appendChild(readout([
      { l: L("procedura", "procedure"), v: `${d.procedure.procedure_id} v${d.procedure.version}`, sub: d.procedure.target },
      { l: L("verdetto modello", "model verdict"), v: d.model_status, cls: modelOk ? "ok" : "fail", big: true, sub: L("non è un verdetto IEEE", "not an IEEE verdict") },
      { l: "TDECQ worst", v: d.worst_tdecq_db == null ? "FAIL" : fix(d.worst_tdecq_db, 3) + " dB", cls: modelOk ? "ok" : "fail", sub: `u_grid ${fix(d.numerical_uncertainty_db, 3)} → ${fix(d.guarded_tdecq_db, 3)} dB · limit ≤ ${fix(d.tdecq_limit_db, 1)} dB` },
      { l: L("conformità", "compliance"), v: d.compliance_status, cls: "warn", sub: L("blocchi metrologici espliciti", "explicit metrology blockers") },
      { l: L("durata", "elapsed"), v: fix(d.elapsed_s, 2) + " s", sub: `${d.procedure.pattern_symbols.toLocaleString()} sym` },
    ]));
    const cases = d.cases.map(c => `<tr>
      <td><b>${c.name}</b></td><td>${c.total_dispersion_ps_nm >= 0 ? "+" : ""}${fix(c.total_dispersion_ps_nm, 4)} ps/nm<br><span class="sub">DGD ${fix(c.dgd_ps, 3)} ps</span></td>
      <td><span class="badge ${c.tdecq_model_pass ? "ok" : "fail"}">${c.tdecq.tdecq_db == null ? "FAIL" : fix(c.tdecq.tdecq_db, 3) + " dB"}</span><br><span class="sub">Ceq ${fix(c.tdecq.ceq_db, 2)} dB · Σc ${fix(c.tdecq.tap_sum, 6)} · Δgrid ${fix(c.numeric_grid_delta_db, 3)} dB</span></td>
      <td><span class="badge ${c.link_up ? "ok" : "fail"}">${c.link_up ? "UP" : "DOWN"}</span><br><span class="sub">BER ${c.ber_post_dfe == null ? "—" : sci(c.ber_post_dfe)}</span></td>
      <td><span class="badge ${c.pattern_exact && c.physical_checks_pass ? "ok" : "fail"}">${c.pattern_exact ? "SSPRQ exact" : "pattern FAIL"}</span></td></tr>`).join("");
    p.host.appendChild(CE("div", "standard-table", `<h3>${L("Casi fisici end-to-end", "End-to-end physical cases")}</h3><table class="mini"><tr><th>${L("estremo", "endpoint")}</th><th>${L("canale", "channel")}</th><th>TDECQ</th><th>RX/DSP</th><th>PPG</th></tr>${cases}</table></div>`));
    const steps = d.steps.map(s => `<tr><td><span class="badge ${s.status === "PASS" ? "ok" : s.status === "FAIL" ? "fail" : "warn"}">${s.status}</span></td><td><b>${tr(s.label)}</b><br><span class="sub">${tr(s.requirement)}</span></td><td>${tr(s.evidence)}</td></tr>`).join("");
    p.host.appendChild(CE("div", "standard-table", `<h3>${L("Checklist procedurale", "Procedure checklist")}</h3><table class="mini"><tr><th>status</th><th>${L("passo / requisito", "step / requirement")}</th><th>${L("evidenza", "evidence")}</th></tr>${steps}</table></div>`));
    p.host.appendChild(CE("div", "note w", L(
      "Il link può essere UP e avere BER zero sul record pur fallendo TDECQ: interoperabilità del modello e qualità normativa del trasmettitore sono criteri diversi. Reflection/polarization stress, uncertainty tracciabile e golden-instrument correlation mantengono correttamente il claim a NOT ASSESSED.",
      "The link can be UP with zero BER in the record while failing TDECQ: model interoperability and normative transmitter quality are different criteria. Reflection/polarization stress, traceable uncertainty, and golden-instrument correlation correctly keep the claim at NOT ASSESSED.")));
  },
};

PANEL_DEFS.instruments = {
  title: "Instrument alignment · DCA / BERT / Traffic", size: "s8",
  make(p) {
    const rows = [
      ["Keysight FlexDCA", "SE P/N + differential/common-mode, simultaneous waveforms", L("implementato: CH A-D coerenti; quick-set P/N/Diff/CM; marker DCA dinamici sui reference plane della catena", "implemented: coherent CH A-D; P/N/Diff/CM quick-set; dynamic DCA markers on chain reference planes"), "ok", "https://helpfiles.keysight.com/scopes/FlexDCA-UG/Content/Topics/Channels/channel-elect-diff-setup.htm"],
      ["Keysight FlexDCA", "color-grade eye, mask, levels, rise/fall", L("implementato come misura/proxy LabPro", "implemented as a LabPro measurement/proxy"), "ok", "https://helpfiles.keysight.com/scopes/FlexDCA-UG/Content/Topics/Eye-Mask-Mode/Advanced-Eye/a_adv_eye_toolbar.htm"],
      ["Keysight FlexDCA", "RJ/DJ/TJ, Jn, interference, BER contours", L("tail-fit dual-Dirac RJ/DJ(δδ)/TJ@BER, EH@BER Q-scale, contour BER 2D, statistiche per acquisizione, scale/offset/deskew per canale, Ref RX BT4; mancano Jn (J2/J9), decomposizione interferenze e de-embedding", "dual-Dirac tail-fit RJ/DJ(δδ)/TJ@BER, Q-scale EH@BER, 2D BER contours, per-acquisition statistics, per-channel scale/offset/deskew, BT4 Ref RX; missing Jn (J2/J9), interference decomposition, de-embedding"), "warn", "https://helpfiles.keysight.com/scopes/FlexDCA-UG/Content/Topics/Jitter-Mode/a_jitter_mode.htm"],
      ["Anritsu MP1900A", "PPG/ED, PAM4 MSB/LSB/symbol, error insertion", L("PPG/ED nel path con MSB/LSB, inserzione singola/burst, gating Start/Stop con CL95, auto-search della fase, editor HEX MSB-first, SSPRQ ufficiale verificato ed error analysis burst/EFI; manca la calibrazione completa dello stressed eye", "in-path PPG/ED with MSB/LSB, single/burst insertion, Start/Stop gating with CL95, phase auto-search, MSB-first HEX editor, verified official SSPRQ, and burst/EFI error analysis; complete stressed-eye calibration is missing"), "warn", "https://www.anritsu.com/en-us/test-measurement/products/mp1900a"],
      ["Anritsu MP1900A", "RJ/SJ/BUJ/SSC + common/differential/white noise", L("RJ/PJ(SJ)/DCD, BUJ (PRBS filtrata) e SSC triangolare implementati e verificati (audit sul time-base: RJ 1006/1000 fs; SSC −24.1/−24.1 ppm); la misura ai crossing include correttamente anche DDJ", "RJ/PJ(SJ)/DCD, BUJ (filtered PRBS), and triangular SSC implemented and verified (time-base audit: RJ 1006/1000 fs; SSC −24.1/−24.1 ppm); crossing measurements correctly include DDJ too"), "warn", "https://www.anritsu.com/en-us/test-measurement/products/mp1900a"],
      ["MathWorks SerDes Designer", "auto-analyze, pulse/impulse, statistical eye, contours, bathtub, COM", L("auto-update condiviso, pulse + impulse + cursor, eye/contour/bathtub implementati; COM Annex 93A subset con PDF@DER e package dichiarato; PAM3/8/16 ed export IBIS-AMI completo restano fuori", "shared auto-update, pulse + impulse + cursors, eye/contour/bathtub implemented; Annex 93A COM subset with PDF@DER and declared package; PAM3/8/16 and full IBIS-AMI export remain outside"), "warn", "https://www.mathworks.com/help/serdes/ref/serdesdesigner-app.html"],
      ["Xena Ethernet Test Platform", "streams, rate, size distributions, throughput/loss/latency/jitter", L("frame/FCS/sequence reali con ispettore byte, size sweep, load ramp via IPG, latency budget per blocco, throughput/loss; mancano multi-stream, scheduler/modifier per stream, impairment drop/misorder/duplicate e latenza con timestamp nel payload", "real frame/FCS/sequence with byte inspector, size sweep, IPG load ramp, per-block latency budget, throughput/loss; missing multi-stream, per-stream scheduler/modifiers, drop/misorder/duplicate impairments, and payload-timestamped latency"), "warn", "https://docs.xenanetworks.com/projects/xenamanager-manual/en/latest/overview.html"],
      ["IEEE/OIF", "compliance reference receiver / masks / procedures", L("Ref RX BT4, EH/EW@BER e SNDR hanno confini dichiarati; COM segue un subset Annex 93A. La procedura DR4 v1 esegue SSPRQ completo, estremi di dispersione e catena RX/DSP, ma reflection/polarization stress, uncertainty e golden correlation mantengono la conformità a NOT ASSESSED.", "BT4 Ref RX, EH/EW@BER, and SNDR have declared boundaries; COM follows an Annex 93A subset. DR4 procedure v1 runs the full SSPRQ period, both dispersion endpoints, and the RX/DSP chain, but reflection/polarization stress, uncertainty, and golden correlation keep compliance at NOT ASSESSED."), "warn", "https://www.ieee802.org/3/"],
    ];
    p.body.innerHTML = `<div class="note">${L("Matrice derivata dalla documentazione ufficiale. 'Implementato' significa workflow equivalente nel modello LabPro, non emulazione del firmware o certificazione dello strumento.", "Matrix derived from official documentation. 'Implemented' means an equivalent LabPro model workflow, not firmware emulation or instrument certification.")}</div>
      <table class="mini"><tr><th>${L("riferimento", "reference")}</th><th>${L("funzione manuale", "manual workflow")}</th><th>LabPro</th></tr>
      ${rows.map(r => `<tr><td><a href="${r[4]}" target="_blank" rel="noreferrer">${r[0]}</a></td><td>${r[1]}</td><td><span class="badge ${r[3]}">${r[3] === "ok" ? "implemented" : r[3] === "warn" ? "partial" : "missing"}</span><br>${r[2]}</td></tr>`).join("")}</table>`;
  },
};

PANEL_DEFS.education = {
  title: "Academy · guida ai blocchi e agli standard", size: "s8",
  make(p) {
    p.body.innerHTML = "";
    const bar = CE("div", "scope-bar");
    bar.appendChild(CE("b", "", L("SCHEDA DIDATTICA", "LEARNING CARD")));
    p.sel = CE("select"); bar.appendChild(p.sel); p.body.appendChild(bar);
    p.host = CE("div"); p.body.appendChild(p.host);
    p.sel.onchange = () => this.render(p, p.sel.value);
    this.refetch(p);
  },
  async refetch(p) {
    const d = await GET("/api/panel/education"); acqBadge(p, d);
    p.topics = d.topics || [];
    p.sel.innerHTML = "";
    for (const t of p.topics) { const o = CE("option"); o.value = t.id; o.textContent = t.title[LANG] || t.title.it; p.sel.appendChild(o); }
    const wanted = p.requestedTopic || p.topics[0]?.id;
    p.sel.value = p.topics.some(t => t.id === wanted) ? wanted : p.topics[0]?.id;
    this.render(p, p.sel.value);
  },
  render(p, id) {
    const t = (p.topics || []).find(v => v.id === id); if (!t) return;
    const g = key => (t[key] && (t[key][LANG] || t[key].it)) || "";
    const nums = (t.numbers || []).map(n => `<tr><td>${tr(n.l)}</td><td><b>${tr(n.v)}</b></td></tr>`).join("");
    const acts = (t.actions || []).map(a2 => `<div class="lesson-act"><span class="do">▸ ${a2.do[LANG] || a2.do.it}</span><span class="see">→ ${a2.see[LANG] || a2.see.it}</span></div>`).join("");
    const opensBert = ["stimulus", "serpll", "bert", "bertcheck", "bertproc"].includes(t.panel);
    p.host.innerHTML = `<article class="lesson lesson-grid">
      <div class="lesson-main">
        <header><span class="badge warn">${t.course}</span><h3>${g("title")}</h3></header>
        <section><label>${L("IDEA FISICA", "PHYSICAL IDEA")}</label><p class="lead">${g("idea")}</p></section>
        ${g("deep") ? `<section><label>${L("IN PROFONDITÀ", "IN DEPTH")}</label><p>${g("deep")}</p></section>` : ""}
        <section><label>${L("COSA MISURARE QUI", "WHAT TO MEASURE HERE")}</label><p>${g("observe")}</p></section>
        <section><label>${L("ESPERIMENTO", "EXPERIMENT")}</label><p>${g("experiment")}</p></section>
        <section class="limit"><label>${L("CONFINE DEL MODELLO", "MODEL BOUNDARY")}</label><p>${g("limits")}</p></section>
      </div>
      <aside class="lesson-side">
        <section class="formula"><label>${L("FORMULA-GUIDA", "GUIDING FORMULA")}</label><code>${t.formula}</code></section>
        ${nums ? `<section><label>${L("NUMERI DEL MONDO REALE", "REAL-WORLD NUMBERS")}</label><table class="mini lesson-nums">${nums}</table></section>` : ""}
        ${acts ? `<section><label>${L("PROVA SUL BANCO", "TRY ON THE BENCH")}</label>${acts}</section>` : ""}
        <button class="btn btn-accent" data-open="${t.panel}">${opensBert ? L("Apri nella console BERT", "Open in the BERT console") : L("Apri il pannello", "Open the panel")} →</button>
      </aside>
    </article>`;
    const ob = p.host.querySelector("[data-open]");
    if (ob) { ob.dataset.action = "academy_open"; ob.onclick = () => addPanel(ob.dataset.open); }
    decorateControls(p.host);
  },
};

function openEducation(topic) {
  const p = addPanel("education");
  p.requestedTopic = topic;
  if (p.sel && p.topics) { p.sel.value = topic; PANEL_DEFS.education.render(p, topic); }
  p.el.scrollIntoView({ behavior: "smooth", block: "center" });
}

PANEL_DEFS.checks = {
  title: "Checkpoint & ledger", size: "s4",
  make(p) { p.body.innerHTML = ""; p.host = CE("div"); p.body.appendChild(p.host); this.refetch(p); },
  async refetch(p) {
    const d = await GET("/api/panel/checks"); acqBadge(p, d);
    const rows = d.checks.map(c => `<tr><td><span class="badge ${c.status === "PASS" ? "ok" : "fail"}">${c.status === "PASS" ? "✓" : "✗"}</span></td><td>${tr(c.check)}<br><span style="color:var(--muted)">${tr(c.detail || "")}</span></td></tr>`).join("");
    p.host.innerHTML = `<table class="mini">${rows}</table>`;
  },
  onConfig(p) { this.refetch(p); },
  onTick(p) { if (throttled(p, 2500)) this.refetch(p); },
};

PANEL_DEFS.physics = {
  title: "Audit fisico · invarianti", size: "s8",
  make(p) {
    p.body.innerHTML = ""; p.host = CE("div"); p.body.appendChild(p.host);
    p.body.appendChild(CE("div", "note", L(
      "Queste righe chiudono equazioni sul record corrente. Un PASS non è un claim di compliance IEEE/OIF: dimostra che i blocchi condividono grandezze e unità coerenti.",
      "These rows close equations on the current record. PASS is not an IEEE/OIF compliance claim: it proves blocks share consistent quantities and units.")));
    this.refetch(p);
  },
  async refetch(p) {
    const d = await GET(`/api/panel/physics?source=${S.running ? "live" : "auto"}`); acqBadge(p, d);
    const rows = d.rows.map(r => `<tr>
      <td><span class="badge ${r.status === "PASS" ? "ok" : (r.status === "WARN" ? "warn" : "fail")}">${r.status}</span></td>
      <td><b>${r.name}</b><br><span class="sub">${LANG === "en" ? r.en : r.it}</span></td>
      <td>${r.value}</td><td>${r.expected}</td><td>${r.tolerance}</td></tr>`).join("");
    p.host.innerHTML = `<div class="scope-bar"><b class="${d.failed ? "fail" : "ok"}">${d.passed} PASS · ${d.warnings || 0} WARN · ${d.failed} FAIL</b></div>
      <table class="mini"><tr><th>status</th><th>${L("invariante", "invariant")}</th><th>${L("misurato", "measured")}</th><th>${L("atteso", "expected")}</th><th>${L("tolleranza/nota", "tolerance/note")}</th></tr>${rows}</table>`;
  },
  onConfig(p) { this.refetch(p); },
  onTick(p) { if (throttled(p, 2500)) this.refetch(p); },
};

PANEL_DEFS.rxfe = {
  title: "RX front-end — PD · TIA · AGC", size: "s6",
  make(p) { p.body.innerHTML = ""; p.body.appendChild(paramsBlock(["pd_responsivity_a_w", "pd_dark_current_a", "pd_bw_hz", "pd_saturation_a", "rin_db_hz", "tia_noise_a_rt_hz", "tia_transimpedance_ohm", "tia_vga_range_db", "tia_headroom_ratio", "tia_bw_hz", "tia_clip_v", "agc_target_rms_v", "agc_min_gain_db", "agc_max_gain_db"]));
    p.body.appendChild(CE("div", "note", L("<b>PVT del ricevitore</b>: corner di processo, supply e temperatura scalano banda TIA/CTLE, rumore (∝√T), mismatch ADC e guadagno del loop CDR — sensibilità del primo ordine dichiarate. Prova lo sweep di pvt_temp_c: la BER vs temperatura è la curva di qualifica di un RX vero.", "<b>Receiver PVT</b>: process corner, supply, and temperature scale TIA/CTLE bandwidth, noise (∝√T), ADC mismatch, and CDR loop gain — declared first-order sensitivities. Try sweeping pvt_temp_c: BER vs temperature is a real RX qualification curve.")));
    p.body.appendChild(paramsBlock(["pvt_process", "pvt_vdd_pct", "pvt_temp_c"]));
    // camera climatica: profilo di temperatura del RX nel tempo
    const cbar = CE("div", "scope-bar");
    p.chOn = CE("input"); p.chOn.type = "checkbox";
    const lab = CE("label", "", ""); lab.append(p.chOn, document.createTextNode(" " + L("camera climatica", "thermal chamber")));
    p.chMode = CE("select");
    [["cycle", L("ciclo △", "cycle △")], ["ramp", L("rampa", "ramp")], ["soak", "soak"]].forEach(([v2, t2]) => { const o = CE("option"); o.value = v2; o.textContent = t2; p.chMode.appendChild(o); });
    const mkN = (val, w2, title) => { const el = CE("input"); el.type = "number"; el.value = val; el.style.width = w2; el.title = title; return el; };
    p.chMin = mkN(-10, "56px", "T min [°C]"); p.chMax = mkN(85, "56px", "T max [°C]");
    p.chPer = mkN(180, "60px", L("periodo [s]", "period [s]")); p.chTau = mkN(10, "50px", L("tau termico die [s]", "die thermal tau [s]"));
    const push = () => POST("/api/chamber", { on: p.chOn.checked, mode: p.chMode.value, t_min: +p.chMin.value, t_max: +p.chMax.value, period_s: +p.chPer.value, tau_s: +p.chTau.value }).catch(e => toast(e.message));
    [p.chOn, p.chMode, p.chMin, p.chMax, p.chPer, p.chTau].forEach(el => el.onchange = push);
    p.chDie = CE("span", "", "");
    cbar.append(lab, p.chMode, CE("span", "", "T"), p.chMin, "…", p.chMax, CE("span", "", "°C ·"), p.chPer, CE("span", "", "s · τ"), p.chTau, CE("span", "", "s"), p.chDie);
    p.body.appendChild(cbar);
    p.body.appendChild(CE("div", "note", L("Come in una camera climatica reale: la camera segue il profilo scelto e il die la insegue con un lag termico del 1° ordine (τ). Con RUN attivo BER, SNR e i parametri del RX si muovono record per record — la strip sotto mostra T e BER insieme: è la curva di qualifica in temperatura, dal vivo.", "As in a real thermal chamber: the chamber follows the chosen profile and the die tracks it with a first-order thermal lag (τ). With RUN active, BER, SNR, and the RX parameters move record by record — the strip below shows T and BER together: the live temperature qualification curve.")));
    p.chStrip = CE("div", "plot"); p.body.appendChild(p.chStrip); p.body.appendChild(CE("div", "note", L("Il noise budget e l'ENBW sono nello Spectrum analyzer (nodo 'Uscita TIA') e nel pannello Checkpoint. PD o TIA in saturazione accendono il checkpoint (e il blocco in catena).", "The noise budget and ENBW live in the Spectrum analyzer ('TIA output' node) and in the Checkpoint panel. A saturated PD or TIA lights up the checkpoint (and the chain block)."))); },
  onConfig(p) { syncParams(p.body); },
  onTick(p) {
    const a = S.acc; if (!a) return;
    if (p.chDie && a.chamber) {
      p.chDie.textContent = a.chamber.on ? ` · die ${fix(a.chamber.die_t, 1)} °C` : "";
      if (document.activeElement !== p.chOn) p.chOn.checked = !!a.chamber.on;
    }
    if (!p.chStrip || !a.hist || !a.hist.temp_c) return;
    const now = Date.now(); if (now - (p.stripT || 0) < 1500) return; p.stripT = now;
    const lay = PL({ height: 150, showlegend: false, yaxis2: { overlaying: "y", side: "right", type: "log", title: { text: "BER", font: { size: 9 } }, gridcolor: "rgba(0,0,0,0)" } });
    mergeAxis(lay, "xaxis", { title: { text: L("record — qualifica in temperatura", "record — temperature qualification"), font: { size: 9 } } });
    mergeAxis(lay, "yaxis", { title: { text: "T die [°C]", font: { size: 9 } } });
    plot(p.chStrip, [
      { y: a.hist.temp_c, name: "T", line: { color: COL.am, width: 1.5 } },
      { y: a.hist.ber.map(v => v == null || v <= 0 ? null : v), name: "BER", yaxis: "y2", mode: "markers", marker: { color: COL.fail, size: 3 } },
    ], lay);
  },
};

PANEL_DEFS.pd = {
  title: "Photodiode · PD", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    p.body.appendChild(paramsBlock(["pd_responsivity_a_w", "pd_dark_current_a", "pd_bw_hz", "pd_saturation_a", "rin_db_hz"]));
    p.ro = CE("div"); p.plotEl = CE("div", "plot"); p.body.append(p.ro, p.plotEl); this.refetch(p);
  },
  async refetch(p) {
    const d = await GET(`/api/panel/pd?source=${S.running ? "live" : "auto"}`); acqBadge(p, d); p.ro.innerHTML = "";
    if (d.inactive) { p.ro.appendChild(CE("div", "note w", d.reason)); p.plotEl.innerHTML = ""; return; }
    p.ro.appendChild(readout([
      { l: "P input", v: fix(d.input_dbm, 2) + " dBm" },
      { l: "I mean / AC rms", v: `${fix(d.mean_ma, 3)} / ${fix(d.rms_ac_ma, 3)} mA` },
      { l: L("saturazione", "saturation"), v: fix(d.sat_pct, 4) + "%", cls: d.sat_pct > 0 ? "fail" : "ok", sub: `limit ${fix(d.saturation_ma, 2)} mA` },
      { l: "shot / RIN PSD", v: `${sci(d.noise_psd.shot)} / ${sci(d.noise_psd.RIN)} A²/Hz` },
    ]));
    const lay = PL({ height: 240 });
    mergeAxis(lay, "xaxis", { title: { text: "tempo [UI]", font: { size: 10 } } });
    mergeAxis(lay, "yaxis", { title: { text: "photocurrent [mA]", font: { size: 10 } } });
    plot(p.plotEl, [
      { x: d.t_ui, y: d.clean_ma, name: L("segnale", "signal"), line: { color: COL.op, width: 1.4 } },
      { x: d.t_ui, y: d.noisy_ma, name: L("segnale + rumore", "signal + noise"), line: { color: COL.el, width: 1 } }], lay);
  },
  onConfig(p) { syncParams(p.body); this.refetch(p); },
  onTick(p) { if (throttled(p, 1600)) this.refetch(p); },
};

PANEL_DEFS.tia = {
  title: "TIA / electrical AFE", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    p.body.appendChild(paramsBlock(["tia_noise_a_rt_hz", "tia_transimpedance_ohm", "tia_vga_range_db", "tia_headroom_ratio", "tia_bw_hz", "tia_clip_v"]));
    p.ro = CE("div"); p.plotT = CE("div", "plot"); p.plotH = CE("div", "plot"); p.body.append(p.ro, p.plotT, p.plotH); this.refetch(p);
  },
  async refetch(p) {
    const d = await GET(`/api/panel/tia?source=${S.running ? "live" : "auto"}`); acqBadge(p, d); p.ro.innerHTML = "";
    p.ro.appendChild(readout([
      { l: d.medium === "optical" ? "TIA ZT max → eff." : "AFE", v: d.transimpedance_ohm ? `${eng(d.transimpedance_ohm)}Ω → ${eng(d.effective_transimpedance_ohm)}Ω` : L("voltage input", "voltage input"), sub: d.medium === "optical" ? `${fix(d.vga_atten_db, 2)} dB · range ${fix(d.vga_range_db, 1)} dB` : "" },
      { l: "BW / ENBW", v: `${fix(d.bandwidth_ghz, 1)} / ${fix(d.enbw_ghz, 1)} GHz` },
      { l: "output RMS", v: fix(d.out_rms_v, 3) + " V" },
      { l: "overload", v: fix(d.clip_pct, 4) + "%", cls: d.clip_pct > 0.1 ? "fail" : "ok", sub: `rail ±${fix(d.clip_v, 2)} V` },
    ]));
    const lt = PL({ height: 210, showlegend: false });
    mergeAxis(lt, "xaxis", { title: { text: "tempo [UI]", font: { size: 10 } } });
    mergeAxis(lt, "yaxis", { title: { text: "Vout [V]", font: { size: 10 } } });
    plot(p.plotT, [{ x: d.t_ui, y: d.vout, line: { color: COL.el } }], lt);
    const lh = PL({ height: 180, showlegend: false, shapes: [vline(S.cfg.nyquist_hz || S.cfg.symbol_rate_hz / 2e9)] });
    mergeAxis(lh, "xaxis", { title: { text: "GHz", font: { size: 10 } } });
    mergeAxis(lh, "yaxis", { title: { text: "|H| dB", font: { size: 10 } } });
    plot(p.plotH, [{ x: d.f_ghz, y: d.response_db, line: { color: COL.am } }], lh);
  },
  onConfig(p) { syncParams(p.body); this.refetch(p); },
  onTick(p) { if (throttled(p, 1600)) this.refetch(p); },
};

PANEL_DEFS.agc = {
  title: "AGC · gain & headroom", size: "s6",
  make(p) {
    p.body.innerHTML = ""; p.body.appendChild(paramsBlock(["agc_target_rms_v", "agc_min_gain_db", "agc_max_gain_db"]));
    p.ro = CE("div"); p.plotEl = CE("div", "plot"); p.body.append(p.ro, p.plotEl); this.refetch(p);
  },
  async refetch(p) {
    const d = await GET(`/api/panel/agc?source=${S.running ? "live" : "auto"}`); acqBadge(p, d); p.ro.innerHTML = "";
    p.ro.appendChild(readout([
      { l: "gain", v: fix(d.gain_db, 2) + " dB", cls: d.at_limit ? "warn" : "", sub: d.at_limit ? `${L("LIMITATO", "LIMITED")} · request ${fix(d.unconstrained_gain_db, 2)} dB` : "×" + fix(d.gain, 2), title: `${L("range VGA", "VGA range")} ${fix(d.min_gain_db, 1)}…${fix(d.max_gain_db, 1)} dB` },
      { l: "RMS in → out", v: `${fix(d.input_rms_v, 3)} → ${fix(d.output_rms_v, 3)} V`, sub: `target ${fix(d.target_rms_v, 3)} V` },
      { l: "ADC headroom", v: fix(d.headroom_to_adc_v, 3) + " V", cls: d.headroom_to_adc_v < 0 ? "fail" : "ok" },
    ]));
    const lay = PL({ height: 240 });
    mergeAxis(lay, "xaxis", { title: { text: "tempo [UI]", font: { size: 10 } } });
    mergeAxis(lay, "yaxis", { title: { text: "V", font: { size: 10 } } });
    plot(p.plotEl, [
      { x: d.t_ui, y: d.vin, name: L("ingresso AC", "AC input"), line: { color: COL.muted } },
      { x: d.t_ui, y: d.vout, name: L("uscita AGC", "AGC output"), line: { color: COL.ok } }], lay);
  },
  onConfig(p) { syncParams(p.body); this.refetch(p); },
  onTick(p) { if (throttled(p, 1600)) this.refetch(p); },
};

/* --- BERT unico: generatore TX + checker digitali dopo l'unico RX fisico --- */
PANEL_DEFS.bert = {
  title: L("BERT · generatore TX + analizzatore errori", "BERT · TX generator + error analyzer"), size: "s8",
  make(p) {
    p.body.innerHTML = "";
    p.body.appendChild(CE("div", "scope-bar", `<b>MP1900A-STYLE MAINFRAME</b><span class="badge ok">${L("UNA CHAIN · UN RX", "ONE CHAIN · ONE RX")}</span>`));
    p.body.appendChild(CE("div", "note", L(
      "UN SOLO STRUMENTO E UN SOLO RX FISICO. Le quattro viste sotto separano le funzioni, non creano altre schede: il generatore TX (PPG) pilota la chain; il checker RX confronta i tap PRE-FEC e POST-FEC dopo AFE/ADC/CDR/FSE/DFE.",
      "ONE INSTRUMENT AND ONE PHYSICAL RX. The four views below separate functions without creating other cards: the TX generator (PPG) drives the chain; the RX checker compares PRE-FEC and POST-FEC taps after AFE/ADC/CDR/FSE/DFE.")));
    p.route = CE("div", "bert-route"); p.body.appendChild(p.route);

    p.tabBar = CE("div", "instrument-tabs");
    p.tabBar.setAttribute("role", "tablist");
    p.tabButtons = {}; p.tabPanes = {};
    for (const [key, label] of [
      ["source", L("1 · SORGENTE TX", "1 · TX SOURCE")],
      ["stress", L("2 · STRESS TX", "2 · TX STRESS")],
      ["checker", L("3 · CHECKER RX/FEC", "3 · RX/FEC CHECKER")],
      ["procedures", L("4 · PROCEDURE RX", "4 · RX PROCEDURES")],
    ]) {
      const tab = CE("button", "instrument-tab", label);
      tab.type = "button"; tab.setAttribute("role", "tab");
      tab.dataset.bertTab = key; tab.onclick = () => this.showTab(p, key);
      const pane = CE("section", "instrument-pane");
      pane.setAttribute("role", "tabpanel"); pane.dataset.bertPane = key;
      p.tabButtons[key] = tab; p.tabPanes[key] = pane;
      p.tabBar.appendChild(tab);
    }
    p.body.append(p.tabBar, ...Object.values(p.tabPanes));

    const sourcePane = p.tabPanes.source;
    sourcePane.appendChild(CE("div", "module-head", L(
      "SORGENTE TX · PPG, mapping e FEC encoder",
      "TX SOURCE · PPG, mapping and FEC encoder")));
    // OUTPUT enable dello stadio TX, come il tasto Output di un PPG reale
    const obar = CE("div", "scope-bar");
    p.outBtn = CE("button", "btn btn-out", "");
    p.outBtn.dataset.action = "tx_output";
    p.outBtn.onclick = () => postConfig({ tx_output_on: S.cfg.tx_output_on === false });
    obar.append(p.outBtn, CE("span", "", L(
      "mute elettrico dello stadio d'uscita — la sorgente ottica resta accesa",
      "output-stage electrical mute — the optical source stays on")));
    sourcePane.append(obar, paramsBlock(["symbol_rate_hz", "pattern", "prbs_order", "modulation", "pam4_mapping", "n_symbols", "fec_mode"]));
    p.ppgEditor = CE("div", "pattern-editor");
    const editorHead = CE("div", "pattern-editor-head", `<label>${L("Pattern HEX utente · byte MSB-first", "User HEX pattern · MSB-first bytes")}</label>`);
    const hexHelp = controlHelpButton("custom_pattern_hex"); hexHelp.style.position = "static"; editorHead.appendChild(hexHelp);
    p.hexInput = CE("input"); p.hexInput.type = "text"; p.hexInput.maxLength = 12288;
    p.hexInput.spellcheck = false; p.hexInput.placeholder = "A5 C3 F0 0F";
    p.hexApply = CE("button", "btn btn-accent", L("APPLICA HEX", "APPLY HEX"));
    p.hexApply.dataset.action = "pattern_apply"; p.hexStatus = CE("span", "sub");
    const applyHex = async () => {
      try {
        const out = await POST("/api/config", { updates: { pattern: "custom_hex", custom_pattern_hex: p.hexInput.value } });
        S.cfg = out.cfg; cfgChips(); notify("config");
        p.hexStatus.textContent = L("applicato · ripetizione ciclica", "applied · cyclic repeat");
      } catch (e) { toast(e.message); }
    };
    p.hexApply.onclick = applyHex;
    p.hexInput.onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); applyHex(); } };
    p.ppgEditor.append(editorHead, p.hexInput, p.hexApply, p.hexStatus);
    sourcePane.appendChild(p.ppgEditor);
    p.sourceSummary = CE("div"); sourcePane.appendChild(p.sourceSummary);

    const stressPane = p.tabPanes.stress;
    stressPane.appendChild(CE("div", "module-head", L(
      "STRESS TX · serializer, clock, jitter, rumore e uscita P/N",
      "TX STRESS · serializer, clock, jitter, noise and P/N output")));
    stressPane.appendChild(paramsBlock(["tx_rj_rms_fs", "tx_pj_amp_ui", "tx_pj_freq_mhz", "tx_dcd_pct", "tx_buj_amp_ui", "tx_ssc_ppm", "tx_ssc_khz",
      "pn_skew_ps", "pn_gain_mismatch_pct", "vcm_offset_v", "vcm_noise_mv", "tx_diff_noise_mv", "electrical_drive_mode"]));
    p.txSummary = CE("div"); stressPane.appendChild(p.txSummary);

    const checkerPane = p.tabPanes.checker;
    checkerPane.appendChild(CE("div", "module-head", L(
      "CHECKER RX · dopo l'unico RX fisico, prima e dopo il decoder FEC",
      "RX CHECKER · after the single physical RX, before and after the FEC decoder")));
    p.edDisplay = CE("div", "ed-display"); checkerPane.appendChild(p.edDisplay);
    const bar = CE("div", "scope-bar");
    p.nIns = CE("input"); p.nIns.type = "number"; p.nIns.value = 10; p.nIns.min = 1; p.nIns.max = 200; p.nIns.style.width = "60px";
    const btn = CE("button", "btn btn-accent", L("Inserisci errori", "Insert errors"));
    p.injectBtn = btn; btn.dataset.action = "bert_inject";
    // target dell'inserzione: dove cadono i bit invertiti (mirata iter. 29)
    p.insTarget = CE("select");
    for (const [v, lab] of [["random", L("posizioni random", "random positions")],
                            ["msb", L("solo lane MSB", "MSB lane only")],
                            ["lsb", L("solo lane LSB", "LSB lane only")],
                            ["rs_symbol", L("simboli RS interi", "whole RS symbols")]]) {
      const o = CE("option"); o.value = v; o.textContent = lab; p.insTarget.appendChild(o);
    }
    btn.onclick = async () => {
      const bits = Number(p.nIns.value);
      if (!Number.isInteger(bits) || bits < 1 || bits > 200)
        return toast(L("bit da inserire: intero 1…200", "bits to insert: integer 1…200"));
      btn.disabled = true; btn.textContent = L("in attesa del RX…", "waiting for RX…");
      try {
        const d = await POST("/api/inject", { bits, burst: p.burstChk.checked, target: p.insTarget.value });
        p.pendingInjectionId = d.request.id;
        this.renderInjection(p, { ...d.request, status: "queued" });
        this.updateInjectionState(p);
      } catch (e) {
        btn.disabled = false; btn.textContent = L("Inserisci errori", "Insert errors");
        toast(e.message);
      }
    };
    btn.textContent = L("Inserisci errori", "Insert errors");
    p.burstChk = CE("input"); p.burstChk.type = "checkbox";
    const burstLab = CE("label", "", ""); burstLab.append(p.burstChk, document.createTextNode(" burst"));
    bar.append(CE("span", "", L("bit da invertire:", "bits to flip:")), p.nIns, p.insTarget, burstLab, btn);
    // gating stile BERT: Start/Stop su finestra dei contatori cumulativi
    const gbar = CE("div", "scope-bar");
    p.gateBtn = CE("button", "btn", L("Gate START", "Gate START"));
    p.gateBtn.dataset.action = "bert_gate";
    p.gateInfo = CE("span", "", "");
    p.targetBer = CE("input"); p.targetBer.type = "text"; p.targetBer.value = "1e-3"; p.targetBer.style.width = "64px";
    p.gateBtn.onclick = () => {
      if (!p.gate) {
        p.gate = { bits: S.acc.bits_total, errs: S.acc.bit_errors_total, t: Date.now() };
        p.gateBtn.textContent = "Gate STOP"; p.gateBtn.classList.add("btn-accent");
      } else {
        p.gateFrozen = this.gateSnapshot(p); p.gate = null;
        p.gateBtn.textContent = L("Gate START", "Gate START"); p.gateBtn.classList.remove("btn-accent");
      }
    };
    gbar.append(p.gateBtn, CE("span", "", L("target BER:", "target BER:")), p.targetBer, p.gateInfo);
    // auto-search stile MP1900A: trova la fase di campionamento a BER minima
    p.autoBtn = CE("button", "btn", L("Auto search fase (~5 s)", "Phase auto search (~5 s)"));
    p.autoBtn.dataset.action = "bert_phase";
    p.autoBtn.onclick = async () => {
      p.autoBtn.disabled = true; p.autoBtn.textContent = L("ricerca…", "searching…");
      try {
        const d = await POST("/api/experiment/sweep", { field: "adc_phase_ui", lo: -0.3, hi: 0.3, n: 9 });
        const ok = d.rows.filter(r => r.link_up);
        if (!ok.length) throw new Error(L("nessuna fase con link UP", "no phase with link UP"));
        const best = ok.reduce((a2, b) => (b.BER_FSE_DFE < a2.BER_FSE_DFE ? b : a2));
        await postConfigAndWait({ adc_phase_ui: best.adc_phase_ui });
        toast(`${L("fase ottima", "best phase")}: ${fix(best.adc_phase_ui, 2)} UI · BER ${sci(best.BER_FSE_DFE)}`);
      } catch (e) { toast(e.message); }
      p.autoBtn.disabled = false; p.autoBtn.textContent = L("Auto search fase (~5 s)", "Phase auto search (~5 s)");
    };
    gbar.appendChild(p.autoBtn);
    checkerPane.appendChild(gbar);

    p.errAn = CE("div"); checkerPane.appendChild(p.errAn);
    checkerPane.appendChild(bar);
    p.injectionOut = CE("div", "injection-result"); checkerPane.appendChild(p.injectionOut);
    p.ro = CE("div"); checkerPane.appendChild(p.ro);
    p.plotEl = CE("div", "plot"); checkerPane.appendChild(p.plotEl);
    p.note = CE("div", "note", L(
      "Il checker usa il pattern di riferimento del generatore TX ma misura soltanto i bit recuperati dall'unico RX fisico.",
      "The checker uses the TX generator reference pattern but measures only bits recovered by the single physical RX."));
    checkerPane.appendChild(p.note);

    const proceduresPane = p.tabPanes.procedures;
    proceduresPane.appendChild(CE("div", "module-head", L(
      "PROCEDURE RX · ricerche che fermano temporaneamente il live bench",
      "RX PROCEDURES · searches that temporarily stop the live bench")));
    // --- RX sensitivity search: bisezione sulla potenza lanciata ---------
    proceduresPane.appendChild(CE("div", "sec-tag", "RX · SENSITIVITY SEARCH"));
    const sbar = CE("div", "scope-bar");
    p.sensTarget = CE("input"); p.sensTarget.type = "text";
    p.sensTarget.style.width = "110px";
    p.sensTarget.placeholder = L("auto (soglia pre-FEC)", "auto (pre-FEC threshold)");
    p.sensBtn = CE("button", "btn btn-accent", L("Misura sensitivity (~10 s)", "Measure sensitivity (~10 s)"));
    p.sensBtn.dataset.action = "bert_sensitivity";
    p.sensBtn.onclick = async () => {
      p.sensBtn.disabled = true; const prev = p.sensBtn.textContent;
      p.sensBtn.textContent = L("bisezione…", "bisecting…");
      try {
        const body = {};
        const t = Number(p.sensTarget.value);
        if (p.sensTarget.value.trim() && isFinite(t) && t > 0) body.target_ber = t;
        const d = await POST("/api/experiment/sensitivity", body);
        this.drawSensitivity(p, d);
      } catch (e) { toast(e.message); }
      p.sensBtn.disabled = false; p.sensBtn.textContent = prev;
    };
    sbar.append(CE("span", "", "target BER:"), p.sensTarget, p.sensBtn);
    proceduresPane.appendChild(sbar);
    p.sensOut = CE("div"); proceduresPane.appendChild(p.sensOut);
    p.sensPlot = CE("div", "plot"); proceduresPane.appendChild(p.sensPlot);
    // --- stressed-eye calibration: PJ calibrato su un target di apertura --
    proceduresPane.appendChild(CE("div", "sec-tag", "RX · STRESSED EYE CAL"));
    const stbar = CE("div", "scope-bar");
    p.stressQ = CE("input"); p.stressQ.type = "text"; p.stressQ.value = "3.0";
    p.stressQ.style.width = "55px";
    p.stressApply = CE("input"); p.stressApply.type = "checkbox";
    const stLab = CE("label", "", "");
    stLab.append(p.stressApply, document.createTextNode(" " + L("applica ricetta", "apply recipe")));
    p.stressBtn = CE("button", "btn btn-accent", L("Calibra stress (~10 s)", "Calibrate stress (~10 s)"));
    p.stressBtn.dataset.action = "bert_stress_cal";
    p.stressBtn.onclick = async () => {
      p.stressBtn.disabled = true; const prev = p.stressBtn.textContent;
      p.stressBtn.textContent = L("calibrazione…", "calibrating…");
      try {
        const d = await POST("/api/experiment/stresscal", { target_q: Number(p.stressQ.value) || 3.0 });
        this.drawStressCal(p, d);
        if (p.stressApply.checked && d.status === "ok" && d.recipe) {
          await postConfigAndWait({ tx_pj_amp_ui: d.recipe.tx_pj_amp_ui });
          toast(L(`ricetta applicata: PJ ${fix(d.recipe.tx_pj_amp_ui, 3)} UI @ ${fix(d.pj_freq_mhz, 0)} MHz`,
                  `recipe applied: PJ ${fix(d.recipe.tx_pj_amp_ui, 3)} UI @ ${fix(d.pj_freq_mhz, 0)} MHz`));
        }
      } catch (e) { toast(e.message); }
      p.stressBtn.disabled = false; p.stressBtn.textContent = prev;
    };
    stbar.append(CE("span", "", "target Q [σ]:"), p.stressQ, stLab, p.stressBtn);
    proceduresPane.appendChild(stbar);
    p.stressOut = CE("div"); proceduresPane.appendChild(p.stressOut);
    proceduresPane.appendChild(CE("div", "note", L(
      "Sensitivity e stressed-eye sono procedure del ricevitore della stessa chain; non aggiungono un secondo RX e non sono procedure normative complete.",
      "Sensitivity and stressed-eye are procedures on the same chain receiver; they add no second RX and are not complete normative procedures.")));
    p.lastFetch = 0;
    this.showTab(p, p.requestedBertTab || "checker");
    this.syncRoute(p);
    this.updateSourceSummary(p);
    this.updateTxSummary(p);
    this.syncOutput(p);
    this.updateInjectionState(p);
    this.refetch(p);
  },
  showTab(p, key) {
    if (!p.tabPanes || !p.tabPanes[key]) return;
    p.activeBertTab = key;
    for (const [name, pane] of Object.entries(p.tabPanes)) {
      const active = name === key;
      pane.hidden = !active;
      p.tabButtons[name].classList.toggle("active", active);
      p.tabButtons[name].setAttribute("aria-selected", active ? "true" : "false");
      p.tabButtons[name].tabIndex = active ? 0 : -1;
    }
    if (key === "checker" && window.Plotly && p.plotEl?.data)
      requestAnimationFrame(() => Plotly.Plots.resize(p.plotEl));
    if (key === "procedures" && window.Plotly) requestAnimationFrame(() => {
      if (p.sensPlot?.data) Plotly.Plots.resize(p.sensPlot);
    });
  },
  updateSourceSummary(p) {
    if (!p.sourceSummary || !S.cfg) return;
    const bps = S.cfg.modulation === "NRZ" ? 1 : 2;
    const pattern = S.cfg.pattern === "prbs" ? `PRBS${S.cfg.prbs_order}` : String(S.cfg.pattern).toUpperCase();
    p.sourceSummary.innerHTML = "";
    p.sourceSummary.appendChild(readout([
      { l: L("pattern generato", "generated pattern"), v: pattern, cls: "ok", sub: `${S.cfg.modulation} · ${S.cfg.pam4_mapping}` },
      { l: L("rate di linea", "line rate"), v: eng(S.cfg.symbol_rate_hz * bps) + "b/s", sub: `${eng(S.cfg.symbol_rate_hz)}Bd` },
      { l: L("finestra record", "record window"), v: eng(S.cfg.n_symbols) + "sym", sub: eng(S.cfg.n_symbols * bps) + "bit" },
      { l: "FEC TX/RX", v: S.cfg.fec_mode === "none" ? "BYPASS" : S.cfg.fec_mode.toUpperCase(), cls: S.cfg.fec_mode === "none" ? "warn" : "ok" },
    ]));
    p.ppgEditor.hidden = S.cfg.pattern !== "custom_hex";
    if (document.activeElement !== p.hexInput) p.hexInput.value = S.cfg.custom_pattern_hex || "";
  },
  syncRoute(p) {
    if (!p.route || !S.cfg) return;
    const fecOn = S.cfg.fec_mode !== "none";
    p.route.innerHTML = `<span>PPG</span><i>→</i><span class="warn">ERR ADD · TX</span><i>→</i>` +
      `<span>TX + ${S.cfg.link_medium === "optical" ? "OPTICAL CHANNEL" : "COPPER CHANNEL"}</span><i>→</i>` +
      `<span class="ok">${L("RX FISICO", "PHYSICAL RX")}<br><small>AFE · ADC · CDR · FSE · DFE</small></span><i>→</i>` +
      `<span>ED PRE-FEC</span><i>→</i><span class="${fecOn ? "ok" : "off"}">FEC ${fecOn ? S.cfg.fec_mode.toUpperCase() : "BYPASS"}</span><i>→</i>` +
      `<span class="${fecOn ? "" : "off"}">ED POST-FEC</span>`;
    const rs = p.insTarget && [...p.insTarget.options].find(o => o.value === "rs_symbol");
    if (rs) {
      rs.disabled = !fecOn;
      rs.textContent = fecOn ? L("simboli RS interi", "whole RS symbols")
        : L("simboli RS interi (richiede FEC)", "whole RS symbols (FEC required)");
      if (!fecOn && p.insTarget.value === "rs_symbol") p.insTarget.value = "random";
    }
  },
  renderInjection(p, r) {
    if (!p.injectionOut) return;
    p.injectionOut.innerHTML = "";
    if (!r) {
      const fecOn = S.cfg && S.cfg.fec_mode !== "none";
      p.injectionOut.appendChild(CE("div", "note", fecOn ? L(
        `Nessuna transazione latched. Premi Inserisci errori per misurare RX fisico → ED pre-FEC → ${S.cfg.fec_mode.toUpperCase()} → ED post-FEC.`,
        `No latched transaction. Press Insert errors to measure physical RX → pre-FEC ED → ${S.cfg.fec_mode.toUpperCase()} → post-FEC ED.`) : L(
        "Nessuna transazione latched. Il checker POST-FEC è in BYPASS; seleziona KP4/KR4 per verificare la correzione.",
        "No latched transaction. The POST-FEC checker is bypassed; select KP4/KR4 to verify correction.")));
      return;
    }
    if (r.status === "queued" || r.status === "active") {
      p.injectionOut.appendChild(readout([
        { l: `ERROR ADD #${r.id}`, v: `${r.bits} bit`, cls: "warn", sub: L("attesa del record attraverso il RX fisico", "waiting for the record through the physical RX") },
      ]));
      return;
    }
    if (r.status === "discarded_config_change" || r.status === "discarded" || r.status === "simulation_error") {
      const configChange = r.status === "discarded_config_change";
      p.injectionOut.appendChild(readout([
        { l: `ERROR ADD #${r.id}`, v: L("ANNULLATA", "CANCELLED"), cls: "fail", sub: configChange ? L("configurazione cambiata prima della misura", "configuration changed before measurement") : r.status },
        { l: L("RX fisico", "physical RX"), v: "NOT MEASURED", cls: "fail", sub: L("nessun risultato attribuito a questa transazione", "no result assigned to this transaction") },
      ]));
      return;
    }
    const measured = r.status === "measured";
    const fecOn = r.fec_mode && r.fec_mode !== "none";
    p.injectionOut.appendChild(readout([
      { l: `TX ERROR ADD #${r.id}`, v: `${r.tx_inserted ?? r.bits} bit`, cls: measured ? "warn" : "fail", sub: `${r.target}${r.burst ? " · burst" : ""} · seed ${r.seed ?? "—"}` },
      { l: L("RX fisico", "physical RX"), v: measured ? "CDR + PATTERN LOCK" : "SYNC LOSS", cls: measured ? "ok" : "fail", sub: L("unico AFE/ADC/FSE/DFE della chain", "the chain's only AFE/ADC/FSE/DFE") },
      { l: "ED PRE-FEC", v: measured ? `${r.pre_fec_errors} err` : "NOT MEASURED", cls: measured ? (r.pre_fec_errors ? "warn" : "ok") : "fail", sub: measured ? `BER ${sci(r.pre_fec_ber)} / ${eng(r.pre_fec_bits)}b` : L("nessun bit valido dal RX", "no valid bits from RX") },
      fecOn
        ? { l: `FEC ${String(r.fec_mode).toUpperCase()}`, v: measured ? `${r.fec_frames_corrected ?? 0} ${L("frame corretti", "frames corrected")}` : "NOT REACHED", cls: measured && !(r.fec_frames_uncorrectable || r.fec_frames_miscorrected) ? "ok" : "fail", sub: measured ? `${r.fec_input_errors ?? 0} err input · ${r.fec_frames_uncorrectable ?? 0} ${L("persi", "lost")} · ${r.fec_symbols_corrected ?? 0} ${L("simboli corretti", "symbols corrected")}` : "—" }
        : { l: "FEC", v: "BYPASS", cls: "warn", sub: L("seleziona KP4/KR4 per osservare la correzione", "select KP4/KR4 to observe correction") },
      fecOn
        ? { l: "ED POST-FEC", v: measured ? `${r.post_fec_errors ?? 0} err` : "NOT MEASURED", cls: measured && !(r.post_fec_errors) ? "ok" : "fail", sub: measured ? `BER ${sci(r.post_fec_ber)} / ${eng(r.post_fec_bits)}b` : "—" }
        : { l: "ED POST-FEC", v: "N/A", cls: "warn", sub: "FEC BYPASS" },
    ]));
    p.injectionOut.appendChild(CE("div", "note", `${L("RISULTATO BLOCCATO sul record", "RESULT LATCHED on record")} #${r.record ?? "—"}: ` + L("non viene sostituito dai record live successivi.", "it is not replaced by later live records.")));
  },
  updateInjectionState(p, explicit) {
    const state = (S.acc && S.acc.injection) || {};
    const last = explicit || state.last || null;
    const active = state.active || state.pending || null;
    this.renderInjection(p, last || (active ? { ...active, status: "active" } : null));
    if (!p.injectBtn) return;
    const completed = p.pendingInjectionId && last && last.id === p.pendingInjectionId;
    if (completed) {
      const id = p.pendingInjectionId; p.pendingInjectionId = null;
      p.injectBtn.disabled = false;
      p.injectBtn.textContent = L("Inserisci errori", "Insert errors");
      if (p.lastInjectionFetched !== id) {
        p.lastInjectionFetched = id;
        this.refetch(p);  // carica la mappa del record latched, non `latest`
        toast(last.status === "measured"
          ? `${L("iniezione misurata dal RX fisico", "injection measured by physical RX")}: ${last.pre_fec_errors} err pre-FEC${last.fec_mode !== "none" ? ` → ${last.post_fec_errors} post-FEC` : " · FEC BYPASS"}`
          : last.status === "discarded_config_change" || last.status === "discarded"
            ? L("iniezione annullata: la configurazione della chain è cambiata", "injection cancelled: the chain configuration changed")
            : L("iniezione trasmessa ma RX senza lock: ED/FEC non hanno bit validi", "injection transmitted but RX is unlocked: ED/FEC have no valid bits"));
      }
    } else {
      const busy = !!active || !!p.pendingInjectionId;
      p.injectBtn.disabled = busy;
      p.injectBtn.textContent = busy ? L("in attesa del RX…", "waiting for RX…") : L("Inserisci errori", "Insert errors");
    }
  },
  syncOutput(p) {
    if (!p.outBtn || !S.cfg) return;
    const on = S.cfg.tx_output_on !== false;
    p.outBtn.textContent = on ? "TX OUTPUT: ON" : "TX OUTPUT: OFF";
    p.outBtn.classList.toggle("on", on);
    p.outBtn.classList.toggle("off", !on);
  },
  drawStressCal(p, d) {
    p.stressOut.innerHTML = "";
    if (d.status === "already_below") {
      p.stressOut.appendChild(CE("div", "note w", L(
        `l'occhio è già a Q ${d.q_unstressed == null ? "—" : fix(d.q_unstressed, 2)} σ ≤ target ${fix(d.target_q, 2)} σ senza stress aggiunto: niente da calibrare (link già al/oltre il livello di stress richiesto).`,
        `the eye is already at Q ${d.q_unstressed == null ? "—" : fix(d.q_unstressed, 2)} σ ≤ the ${fix(d.target_q, 2)} σ target with no added stress: nothing to calibrate (link already at/beyond the requested stress level).`)));
      return;
    }
    if (d.status === "stress_insufficient") {
      p.stressOut.appendChild(CE("div", "note w", L(
        `anche al cap di ${fix(d.recipe.tx_pj_amp_ui, 2)} UI di PJ l'occhio resta a Q ${fix(d.recipe.q, 2)} σ > target ${fix(d.target_q, 2)} σ: il solo PJ non basta a chiudere l'occhio fino al target su questo link.`,
        `even at the ${fix(d.recipe.tx_pj_amp_ui, 2)} UI PJ cap the eye stays at Q ${fix(d.recipe.q, 2)} σ > the ${fix(d.target_q, 2)} σ target: PJ alone cannot close the eye to the target on this link.`)));
      return;
    }
    const uiPs = 1e12 / S.cfg.symbol_rate_hz;
    p.stressOut.appendChild(readout([
      { l: L("ricetta PJ", "PJ recipe"), v: fix(d.recipe.tx_pj_amp_ui, 3) + " UI", big: true,
        sub: fix(d.recipe.tx_pj_amp_ui * uiPs, 2) + " ps pk @ " + fix(d.pj_freq_mhz, 0) + " MHz" },
      { l: L("Q calibrato", "calibrated Q"), v: fix(d.recipe.q, 2) + " σ", cls: "ok",
        sub: `target ${fix(d.target_q, 2)} σ (${L("appena sopra", "just above")})` },
      { l: L("Q senza stress", "unstressed Q"), v: fix(d.q_unstressed, 2) + " σ",
        sub: `${d.points.length} sim` },
    ]));
    p.stressOut.appendChild(CE("div", "sub", L(
      "Bisezione sul PJ al TX PLL fino a portare q_min allo slicer appena sopra il target; spunta 'applica ricetta' per impostarla sul banco. DICHIARATO: non è la ricetta di clause (SJ+RJ+interferenza con strumento prescritto).",
      "Bisection on TX-PLL PJ until slicer q_min sits just above the target; tick 'apply recipe' to set it on the bench. DECLARED: not the clause recipe (SJ+RJ+interference with a prescribed instrument).")));
  },
  drawSensitivity(p, d) {
    p.sensOut.innerHTML = "";
    if (d.status === "fail_at_current") {
      const now = d.points && d.points[0];
      p.sensOut.appendChild(CE("div", "note w", L(
        `BER ${now && now.ber != null ? sci(now.ber) : "—"} già sopra il target ${sci(d.target_ber)} alla potenza attuale: nessuna soglia verso il basso — alza la potenza o rilassa il target.`,
        `BER ${now && now.ber != null ? sci(now.ber) : "—"} already above the ${sci(d.target_ber)} target at the current power: no downward threshold — raise the power or relax the target.`)));
      return;
    }
    p.sensOut.appendChild(readout([
      { l: "sensitivity @ PD", v: d.sensitivity_pd_dbm == null ? "—" : fix(d.sensitivity_pd_dbm, 2) + " dBm", big: true,
        cls: "ok", sub: L("potenza MEDIA (non OMA di clause)", "AVERAGE power (not clause OMA)") },
      { l: L("margine", "margin"), v: fix(d.margin_db, 2) + " dB", cls: d.margin_db > 1 ? "ok" : "warn",
        sub: `${L("lancio attuale", "current launch")} ${fix(d.current_launch_dbm, 1)} dBm` },
      { l: "target BER", v: sci(d.target_ber),
        sub: d.status === "capped" ? L("≥ fondo scala (−20 dB)", "≥ span floor (−20 dB)") : `${d.points.length} sim` },
      { l: L("durata per CL95", "CL95 duration"), v: eng(d.cl95_bits) + "b",
        sub: fix(d.cl95_seconds * 1e3, 3) + " ms @ line rate" },
    ]));
    const pts = d.points.filter(q => q.ber != null);
    const lay = PL({ height: 200, showlegend: false, shapes: [hline(d.target_ber, COL.am)] });
    mergeAxis(lay, "xaxis", { title: { text: L("potenza lanciata [dBm]", "launch power [dBm]"), font: { size: 9 } } });
    mergeAxis(lay, "yaxis", { type: "log", title: { text: "BER", font: { size: 9 } } });
    plot(p.sensPlot, [{ x: pts.map(q => q.launch_dbm), y: pts.map(q => q.ber),
      mode: "markers", marker: { size: 8, color: pts.map(q => q.pass ? COL.ok : COL.fail) } }], lay);
    p.sensOut.appendChild(CE("div", "sub", L(
      "Bisezione sulla potenza lanciata a seed fisso; soglia = minima potenza con BER ≤ target e link UP. DICHIARATO: non è la sensitivity di clause (OMA_outer su stressed RX calibrato).",
      "Bisection on launch power at fixed seed; threshold = minimum power with BER ≤ target and link UP. DECLARED: not clause sensitivity (OMA_outer on a calibrated stressed RX).")));
  },
  gateSnapshot(p) {
    if (!p.gate || !S.acc) return null;
    const bits = S.acc.bits_total - p.gate.bits;
    const errs = S.acc.bit_errors_total - p.gate.errs;
    const secs = (Date.now() - p.gate.t) / 1000;
    const target = Number(p.targetBer.value) || 1e-3;
    // confidenza (iid): CL = 1 - exp(-n·p_target) con 0 errori; con errori,
    // bit necessari ~3/p per CL95 — indicatore, non statistica completa
    const cl = bits > 0 ? (1 - Math.exp(-bits * target)) * 100 : 0;
    return { bits, errs, secs, ber: bits ? errs / bits : null, cl, target };
  },
  async refetch(p) {
    try {
      const g = p.gate ? this.gateSnapshot(p) : p.gateFrozen;
      if (p.gateInfo && g) {
        p.gateInfo.innerHTML = `${p.gate ? "⏺" : "⏹"} ${eng(g.bits)}b · ${g.errs} err · BER ${g.ber == null ? "—" : sci(g.ber)} · ${fix(g.secs, 0)}s · CL(BER<${sci(g.target, 0)}) ${fix(Math.min(g.cl, 99.9), 1)}%`;
      }
      const d = await GET(`/api/panel/bert?source=${S.running ? "live" : "auto"}`);
      this.updateInjectionState(p, d.injection);
      if (p.errAn && d.error_analysis) {
        const ea = d.error_analysis;
        p.errAn.innerHTML = `<table class="mini"><tr><th>${L("analisi errori (ED)", "error analysis (ED)")}</th><th>burst</th><th>${L("isolati", "isolated")}</th><th>max burst</th><th>% in burst</th><th>EFI min/mean</th></tr>` +
          `<tr><td>${L("gap ≤", "gap ≤")} ${ea.burst_gap_sym} sym</td><td>${ea.n_bursts}</td><td>${ea.n_isolated}</td><td>${ea.max_burst}</td><td>${ea.burst_err_pct == null ? "—" : fix(ea.burst_err_pct, 1)}</td><td>${ea.efi_min_sym ?? "—"} / ${ea.efi_mean_sym == null ? "—" : fix(ea.efi_mean_sym, 0)}</td></tr></table>`;
      } acqBadge(p, d);
      p.ro.innerHTML = "";
      if (d.link_down) { p.ro.appendChild(readout([{ l: "SYNC", v: "LOSS", cls: "fail", big: true, sub: "pattern lock perso: l'ED non conta" }])); return; }
      const a = S.acc || {};
      const laneNames = d.bit_errors_by_lane.length === 2 ? ["MSB", "LSB"] : ["bit"];
      p.ro.appendChild(readout([
        { l: L("sync pattern", "pattern sync"), v: d.sync ? "LOCK" : "LOSS", cls: d.sync ? "ok" : "fail" },
        { l: "BER / SER", v: `${sci(d.ber)} / ${sci(d.ser)}`, big: true, sub: `${d.bit_errors} bit · ${d.symbol_errors} sym` },
        { l: "MSB / LSB", v: d.bit_errors_by_lane.map((v, i) => `${laneNames[i]} ${v}`).join(" · ") },
        { l: L("inseriti (record latched)", "inserted (latched record)"), v: String(d.inserted.length), cls: d.inserted.length ? "warn" : "" },
        { l: L("inseriti (totale)", "inserted (total)"), v: String(a.injected_total || 0), sub: `${eng(d.n_bits)}b ${L("nel record", "in record")}` },
      ]));
      const shapes = [vline(d.validation_start, COL.muted, "dot")];
      const lay = PL({ height: 190, showlegend: false, shapes });
      mergeAxis(lay, "xaxis", { title: { text: "posizione nel record [simboli] — mappa errori", font: { size: 9 } } });
      mergeAxis(lay, "yaxis", { title: { text: "err/bin", font: { size: 9 } } });
      const traces = [{ x: d.hist_x, y: d.hist, type: "bar", marker: { color: COL.fail } }];
      if (d.inserted.length) traces.push({ x: d.inserted, y: d.inserted.map(() => Math.max(...d.hist, 1)), mode: "markers", marker: { color: COL.am, symbol: "triangle-down", size: 9 }, name: L("inseriti", "inserted") });
      plot(p.plotEl, traces, lay);
    } catch (e) { p.note.innerHTML = `<span class="fail">${e.message}</span>`; }
  },
  updateTxSummary(p) {
    if (!p.txSummary) return;
    const uiPs = 1e12 / S.cfg.symbol_rate_hz;
    p.txSummary.innerHTML = "";
    p.txSummary.appendChild(readout([
      { l: L("RJ iniettato", "injected RJ"), v: fix(S.cfg.tx_rj_rms_fs / 1000, 2) + " ps", sub: fix(S.cfg.tx_rj_rms_fs * 1e-3 / uiPs, 4) + " UI rms" },
      { l: L("PJ iniettato", "injected PJ"), v: fix(S.cfg.tx_pj_amp_ui * uiPs, 2) + " ps pk", sub: "@ " + fix(S.cfg.tx_pj_freq_mhz, 0) + " MHz" },
      { l: "DCD", v: fix(S.cfg.tx_dcd_pct / 100 * uiPs, 2) + " ps pp", sub: fix(S.cfg.tx_dcd_pct, 1) + " %UI" },
      { l: L("skew P/N", "P/N skew"), v: fix(S.cfg.pn_skew_ps, 2) + " ps", sub: L("notch DM a ", "DM notch at ") + (S.cfg.pn_skew_ps > 0 ? fix(500 / S.cfg.pn_skew_ps, 0) + " GHz" : "∞") },
      { l: "UI", v: fix(uiPs, 2) + " ps" },
    ]));
  },
  onConfig(p) { syncParams(p.body); this.syncRoute(p); this.updateSourceSummary(p); this.updateTxSummary(p); this.syncOutput(p); this.updateInjectionState(p); this.refetch(p); },
  updateEd(p) {
    const a = S.acc; if (!a || !p.edDisplay) return;
    const locked = a.last && a.last.link_up !== false && a.last.cdr_locked !== false;
    p.edDisplay.innerHTML = `
      <span class="ed-led ${locked ? "on" : "off"}"></span>
      <span class="ed-lab">${locked ? "SYNC" : "SYNC LOSS"}</span>
      <span class="ed-num">${eng(a.bits_total)}<small>bit</small></span>
      <span class="ed-num err">${eng(a.bit_errors_total)}<small>err</small></span>
      <span class="ed-num">${a.bits_total ? sci(a.ber_cum) : "—"}<small>BER</small></span>
      <span class="ed-num warn2">${a.sync_losses ?? 0}<small>${L("perdite sync", "sync losses")}</small></span>`;
  },
  onTick(p) { this.updateEd(p); this.updateInjectionState(p); if (throttled(p, 1800)) this.refetch(p); },
};

/* --- Ethernet L2 (traffic analyzer) --- */
PANEL_DEFS.l2 = {
  title: "Ethernet · Traffic L2-lite", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    p.body.appendChild(paramsBlock(["pattern", "l2_frame_bytes", "l2_ipg_bytes", "l2_streams"]));
    const toolsBar = CE("div", "scope-bar");
    const bench = CE("button", "btn btn-accent", L("Benchmark frame size", "Frame-size benchmark"));
    bench.dataset.action = "traffic_benchmark";
    bench.onclick = async () => {
      bench.disabled = true; bench.textContent = L("misura…", "measuring…");
      try {
        const d = await POST("/api/experiment/traffic", { frame_sizes: [64, 128, 256, 512, 1024] });
        const rows = d.rows;
        const lay = PL({ height: 220, yaxis2: { overlaying: "y", side: "right", type: "log",
          title: { text: L("frame loss [%]", "frame loss [%]"), font: { size: 9 } }, gridcolor: "rgba(0,0,0,0)" } });
        mergeAxis(lay, "xaxis", { title: { text: L("dimensione frame [B]", "frame size [B]"), font: { size: 9 } } });
        mergeAxis(lay, "yaxis", { title: { text: L("throughput utile [Gb/s]", "useful throughput [Gb/s]"), font: { size: 9 } } });
        plot(p.benchPlot, [
          { x: rows.map(r => r.frame_bytes), y: rows.map(r => r.throughput_gbps), name: "throughput", line: { color: COL.ok, width: 2 } },
          { x: rows.map(r => r.frame_bytes), y: rows.map(r => Math.max(r.loss_pct, 1e-4)), name: "FLR %", yaxis: "y2", line: { color: COL.fail, dash: "dot" } },
        ], lay);
        p.benchTable.innerHTML = `<table class="mini"><tr><th>B</th><th>det/exp</th><th>OK</th><th>FCS</th><th>lost</th><th>eff.</th></tr>${rows.map(r => `<tr><td>${r.frame_bytes}</td><td>${r.frames_detected}/${r.frames_expected}</td><td>${r.frames_ok}</td><td>${r.frames_fcs_bad}</td><td>${r.frames_lost}</td><td>${fix(r.payload_efficiency_pct, 1)}%</td></tr>`).join("")}</table>`;
      } catch (e) { p.benchTable.innerHTML = `<div class="note w">${e.message}</div>`; }
      bench.disabled = false; bench.textContent = L("Benchmark frame size", "Frame-size benchmark");
    };
    const ont = CE("button", "btn", L("ONT: load ramp + latency (~6 s)", "ONT: load ramp + latency (~6 s)"));
    ont.dataset.action = "ont";
    ont.onclick = async () => {
      ont.disabled = true; ont.textContent = L("misura…", "measuring…");
      try {
        const d = await POST("/api/experiment/ont", {});
        const lay = PL({ height: 210, yaxis2: { overlaying: "y", side: "right",
          title: { text: "FLR [%]", font: { size: 9 } }, gridcolor: "rgba(0,0,0,0)" } });
        mergeAxis(lay, "xaxis", { title: { text: "offered load [%]", font: { size: 9 } } });
        mergeAxis(lay, "yaxis", { title: { text: "goodput [Gb/s]", font: { size: 9 } } });
        const rr = d.ramp.filter(r => isFinite(r.goodput_gbps));
        plot(p.benchPlot, [
          { x: rr.map(r => r.offered_pct), y: rr.map(r => r.goodput_gbps), name: "goodput", mode: "lines+markers", line: { color: COL.ok, width: 2 } },
          { x: d.ramp.map(r => r.offered_pct), y: d.ramp.map(r => r.loss_pct), name: "FLR", yaxis: "y2", mode: "lines+markers", line: { color: COL.fail, dash: "dot" } },
        ], lay);
        const bud = d.latency_budget.map(b => `<tr><td>${tr(b.item)}</td><td>${b.ns >= 1000 ? fix(b.ns / 1000, 2) + " µs" : fix(b.ns, 1) + " ns"}</td><td>${tr(b.detail)}</td></tr>`).join("");
        p.benchTable.innerHTML = `<table class="mini"><tr><th>${L("latency budget (one-way)", "latency budget (one-way)")}</th><th>t</th><th></th></tr>${bud}` +
          `<tr><th>${L("totale (budget)", "total (budget)")}</th><th>${fix(d.latency_total_ns / 1000, 2)} µs</th><th></th></tr>` +
          (d.latency_measured_analog_ns != null ? `<tr><td>${L("GD analogico MISURATO (xcorr)", "MEASURED analog GD (xcorr)")}</td><td>${d.latency_measured_analog_ns < 1 ? fix(d.latency_measured_analog_ns * 1e3, 1) + " ps" : fix(d.latency_measured_analog_ns, 1) + " ns"}</td><td>${L("con filtri zero-fase ≈ 0: attiva causal_filters per il GD reale; fibra e DSP restano budget (record ≪ ritardo)", "≈ 0 with zero-phase filters: enable causal_filters for the real GD; fiber and DSP stay budget (record ≪ delay)")}</td></tr>` : "") +
          (d.cdr_lock_us != null ? `<tr><td>${L("service disruption proxy", "service disruption proxy")}</td><td>${fix(d.cdr_lock_us, 2)} µs</td><td>${L("tempo di lock del CDR", "CDR lock time")}</td></tr>` : "") + `</table>` +
          `<div class="note">${L("Ramp: l'IPG modula l'offered load come il rate scheduler di un ONT; la perdita qui viene SOLO dai bit error del PHY (nessun DUT con code). Latenza = budget dai blocchi, non un round-trip con timestamp.", "Ramp: IPG modulates offered load like an ONT rate scheduler; loss here comes ONLY from PHY bit errors (no queueing DUT). Latency = block budget, not a timestamped round-trip.")}</div>`;
      } catch (e) { p.benchTable.innerHTML = `<div class="note w">${e.message}</div>`; }
      ont.disabled = false; ont.textContent = L("ONT: load ramp + latency (~6 s)", "ONT: load ramp + latency (~6 s)");
    };
    const disr = CE("button", "btn", L("Service disruption", "Service disruption"));
    disr.dataset.action = "disrupt";
    disr.title = L("interrompe il segnale per un record (fibra tagliata) e misura l'outage fino al ritorno del lock — il test di disruption di un ONT", "kills the signal for one record (fiber cut) and measures the outage until lock returns — an ONT disruption test");
    disr.onclick = () => POST("/api/disrupt", {}).then(() => toast(L("segnale interrotto: guarda SYNC LOSS e l'outage misurato", "signal cut: watch SYNC LOSS and the measured outage"))).catch(e => toast(e.message));
    p.disrInfo = CE("span", "", "");
    toolsBar.append(bench, ont, disr, p.disrInfo, CE("span", "", L("PHY end-to-end; non RFC 2544", "end-to-end PHY; not RFC 2544")));
    p.body.appendChild(toolsBar);
    p.ro = CE("div"); p.body.appendChild(p.ro);
    p.insp = CE("div"); p.body.appendChild(p.insp);
    p.benchPlot = CE("div", "plot"); p.body.appendChild(p.benchPlot);
    p.benchTable = CE("div"); p.body.appendChild(p.benchTable);
    p.note = CE("div", "note", L(
      "Frame reali con preamble/SFD, header, sequence e FCS attraversano FEC e PHY. Workflow ispirato a Xena: il benchmark misura throughput/loss sulla frame size, ma non è RFC 2544 (mancano DUT di rete, latency, rate search e multi-stream).",
      "Real frames with preamble/SFD, header, sequence, and FCS cross FEC and PHY. Xena-inspired workflow: the benchmark measures throughput/loss versus frame size, but is not RFC 2544 (no network DUT, latency, rate search, or multi-stream)."));
    p.body.appendChild(p.note);
    this.onTick(p);
  },
  async refetchFrames(p) {
    try {
      const d = await GET(`/api/panel/l2?source=${S.running ? "live" : "auto"}`);
      let head = "";
      if (d.per_stream) {
        head = `<table class="mini"><tr><th>${L("stream", "stream")}</th><th>size</th><th>det</th><th>OK</th><th>FCS</th><th>${L("persi", "lost")}</th></tr>` +
          d.per_stream.map(st => `<tr><td><b>S${st.stream_id}</b></td><td>${st.size}B</td><td>${st.detected}</td><td class="ok">${st.ok}</td><td class="${st.fcs_bad ? "fail" : ""}">${st.fcs_bad}</td><td class="${st.lost ? "fail" : ""}">${st.lost}</td></tr>`).join("") +
          `</table><div class="note">${L("Multi-stream stile Xena: ogni stream ha id, sequence e size propri (round-robin). I frame grandi raccolgono più bit error per frame: guarda S0/S2 vs S1.", "Xena-style multi-stream: each stream has its own id, sequence space, and size (round-robin). Large frames collect more bit errors per frame: compare S0/S2 vs S1.")}</div>`;
      }
      if (!d.frames || !d.frames.length) { p.insp.innerHTML = head; return; }
      const rows = d.frames.map(f => `<tr>
        <td>${f.seq}</td><td>${f.da.slice(0, 8)}…</td><td>${f.sa.slice(0, 8)}…</td><td>${f.ethertype}</td><td>${f.payload_len}B</td>
        <td class="${f.fcs_ok ? "ok" : "fail"}">${f.fcs_rx}</td><td>${f.fcs_calc}</td>
        <td class="${f.fcs_ok ? "ok" : "fail"}">${f.fcs_ok ? "OK" : "BAD"}</td></tr>
        <tr><td colspan="8" style="font-family:monospace;font-size:9px;color:var(--muted,#7e93a2)">${f.hex_head} …</td></tr>`).join("");
      p.insp.innerHTML = head + `<table class="mini"><tr><th>seq</th><th>DA</th><th>SA</th><th>EthType</th><th>len</th><th>${L("FCS ricevuta", "FCS received")}</th><th>${L("CRC-32 ricalcolato", "recomputed CRC-32")}</th><th>✓</th></tr>${rows}</table>` +
        `<div class="note">${L("Ispettore frame: questi sono i byte VERI decodificati dall'ultimo record RX (dopo FEC e descrambler). Ogni frame si verifica così: preamble+SFD (55…d5) delimitano, il sequence number scova i persi, e la FCS ricevuta deve coincidere col CRC-32 ricalcolato sui byte — esattamente come l'ED di uno Xena/ONT.", "Frame inspector: these are the REAL bytes decoded from the last RX record (after FEC and descrambler). Each frame is verified like this: preamble+SFD (55…d5) delimit it, the sequence number catches lost frames, and the received FCS must match the CRC-32 recomputed over the bytes — exactly like a Xena/ONT error detector.")}</div>`;
    } catch (e) { p.insp.innerHTML = ""; }
  },
  onTick(p) {
    if (throttled(p, 2200)) this.refetchFrames(p);
    const a = S.acc; if (!a) return;
    if (p.disrInfo) p.disrInfo.textContent = a.last_disruption_ms != null ? `⏱ outage ${fix(a.last_disruption_ms, 0)} ms` : "";
    if (!a.l2) return;
    const l = a.l2;
    p.ro.innerHTML = "";
    if (!l.active) {
      p.ro.appendChild(readout([{ l: L("traffico", "traffic"), v: "OFF", sub: L("imposta pattern = frame Ethernet (L2)", "set pattern = Ethernet frames (L2)") }]));
      return;
    }
    if (S.acc.last && S.acc.last.link_up === false) {
      p.ro.appendChild(readout([{ l: "LINK", v: "DOWN", cls: "fail", big: true }]));
      return;
    }
    p.ro.appendChild(readout([
      { l: L("frame OK (cum.)", "frames OK (cum.)"), v: String(l.frames_ok), big: true, cls: "ok", sub: l.frame_bytes + "B/frame" },
      { l: L("rilevati / attesi", "detected / expected"), v: `${l.frames_detected || 0} / ${l.frames_expected}` },
      { l: L("FCS errati", "bad FCS"), v: String(l.frames_fcs_bad), cls: l.frames_fcs_bad ? "fail" : "ok" },
      { l: L("persi", "lost"), v: String(l.frames_lost), cls: l.frames_lost ? "fail" : "ok", sub: isFinite(l.loss_pct) ? fix(l.loss_pct, 2) + " %" : "" },
      { l: L("throughput utile", "useful throughput"), v: fix(l.throughput_gbps, 2) + " Gb/s", sub: L("payload con FCS ok / tempo", "FCS-good payload / time") },
      { l: L("offered load", "offered load"), v: (() => { const w = l.frame_bytes + 8, ipg = S.cfg.l2_ipg_bytes || 12; return fix(100 * w / (w + ipg), 1); })() + " %", sub: `IPG ${S.cfg.l2_ipg_bytes || 12} B`, title: L("frazione di linea occupata da frame vs IPG: il rate control del generatore, come su uno Xena/ONT", "line fraction carrying frames vs IPG: the generator rate control, as on a Xena/ONT") },
    ]));
  },
  onConfig(p) { syncParams(p.body); p.lastFetch = 0; this.onTick(p); },
};

/* --- AN/LT Clause 73/72-136 --- */
PANEL_DEFS.anlt = {
  title: "AN/LT · Clause 73 + training", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    const bar = CE("div", "scope-bar");
    const btn = CE("button", "btn btn-accent", L("Avvia AN + LT (~15 s)", "Run AN + LT (~15 s)"));
    btn.dataset.action = "anlt_panel";
    p.applyChk = CE("input"); p.applyChk.type = "checkbox";
    const lab = CE("label", "", ""); lab.append(p.applyChk, document.createTextNode(L(" applica i tap negoziati", " apply negotiated taps")));
    btn.onclick = async () => {
      btn.disabled = true; btn.textContent = L("negoziazione + training…", "negotiating + training…");
      try {
        const d = await POST("/api/experiment/anlt", { apply: p.applyChk.checked });
        const res = d.an.resolution;
        p.ro.innerHTML = "";
        p.ro.appendChild(readout(res.hcd ? [
          { l: "HCD", v: res.hcd_name, big: true, cls: "ok", sub: `${res.lanes}×${res.lane_gbps} Gb/s ${res.modulation}` },
          { l: "FEC", v: tr(res.fec).split(" — ")[0], sub: tr(res.fec) },
          { l: L("abilità comuni", "common abilities"), v: String(res.common.length), sub: res.common.join(" ") },
          ...(d.lt.holdout ? [{ l: "holdout", v: d.lt.holdout.accepted ? "OK" : L("RIFIUTATO", "REJECTED"), cls: d.lt.holdout.accepted ? "ok" : "warn", sub: `Q train ${d.lt.holdout.q_trained == null ? "—" : fix(d.lt.holdout.q_trained, 2)} vs cur ${d.lt.holdout.q_current == null ? "—" : fix(d.lt.holdout.q_current, 2)}`, title: L("verifica su seed indipendente dal training: i coefficienti si applicano solo se non peggiorano — l'LT su un solo seed può overfittare", "verification on a seed independent of training: coefficients apply only if they do not regress — single-seed LT can overfit") }] : []),
          ...(d.lt.reverse ? [{ l: L("LT inverso", "reverse LT"), v: d.lt.reverse.ready ? `Q ${fix(d.lt.reverse.q_after, 2)} σ` : "NO LOCK", cls: d.lt.reverse.ready ? "ok" : "fail", sub: (d.lt.both_ready ? "both_ready ✓" : L("solo una direzione pronta", "only one direction ready")) + ` · ${d.lt.reverse.exchanges} exch`, title: L("direzione partner→locale: il partner allena il proprio TX guidato dal nostro ricevitore — canale dichiarato simmetrico, rumore indipendente. In Clause 72/136 il link è UP solo con both_ready.", "partner→local direction: the partner trains its own TX driven by our receiver — channel declared symmetric, independent noise. In Clause 72/136 the link is UP only with both_ready.") }] : []),
          { l: L("LT · occhio", "LT · eye"), v: d.lt.cdr_locked ? `Q ${fix(d.lt.q_after, 2)} σ` : "NO LOCK", cls: d.lt.eye_open ? (d.lt.q_after >= 3 ? "ok" : "warn") : "fail", sub: (d.lt.eye_open ? L("aperto", "open") + (d.lt.q_after < 3 ? L(" (marginale)", " (marginal)") : "") : L("chiuso", "closed")) + ` · BER ${sci(d.lt.ber_after)} · ${d.lt.exchanges} exch · ${fix(d.lt.duration_us, 0)} µs` + (d.applied ? L(" · applicato", " · applied") : ""), title: L("metrica di training: Q minimo fra gli occhi allo slicer (apertura in unità σ), valida solo con CDR agganciato", "training metric: minimum eye Q at the slicer (opening in σ units), valid only with CDR locked") },
        ] : [{ l: "HCD", v: "—", cls: "fail", big: true, sub: tr(res.parallel_detect) }]));
        // pagine base
        const pg = d.an.pages;
        p.pages.innerHTML = `<table class="mini"><tr><th></th><th>base page</th><th>abilities</th><th>FEC</th><th>nonce</th></tr>` +
          [["local", pg.local_base], ["partner", pg.partner_base]].map(([who, b]) =>
            `<tr><td>${who}</td><td>${b.raw_hex}</td><td>${b.abilities.join(" ")}</td><td>${b.fec_bits.join(" ") || "—"}</td><td>${b.nonce}</td></tr>`).join("") + `</table>`;
        // timeline stati AN
        p.sm.innerHTML = `<table class="mini"><tr><th>t [ms]</th><th>${L("stato", "state")}</th><th></th></tr>` +
          d.an.timeline.map(t2 => `<tr><td>${fix(t2.t_ms, 2)}</td><td><b>${t2.state}</b></td><td>${tr(t2.note)}</td></tr>`).join("") + `</table>` +
          `<div class="note">${tr(d.an.medium_note)}</div>`;
        // LT: SNR per scambio + tabella richieste coefficienti
        const fr = d.lt.frames;
        const lay = PL({ height: 190, showlegend: false });
        mergeAxis(lay, "xaxis", { title: { text: L("tempo di training [µs]", "training time [µs]"), font: { size: 9 } } });
        mergeAxis(lay, "yaxis", { title: { text: L("Q min (apertura occhio) [σ]", "min eye Q [σ]"), font: { size: 9 } } });
        plot(p.ltPlot, [{ x: fr.map(f => f.t_us), y: fr.map(f => f.q), mode: "lines+markers", line: { color: COL.dg, width: 2, shape: "hv" } }], lay);
        if (d.lt.rx_notes && d.lt.rx_notes.length) p.ltPlot.insertAdjacentHTML("beforeend", `<div class="note">${d.lt.rx_notes.join(" · ")}</div>`);
        p.ltTable.innerHTML = `<table class="mini"><tr><th>t [µs]</th><th>coeff</th><th>request</th><th>status</th><th>Q</th><th>taps</th></tr>` +
          fr.map(f => `<tr><td>${fix(f.t_us, 0)}</td><td>${f.coeff}</td><td>${f.request}</td><td class="${f.status === "updated" || f.status === "ready" ? "ok" : ""}">${f.status}</td><td>${f.q == null ? "—" : fix(f.q, 2)}</td><td>${f.taps.map(t2 => fix(t2, 2)).join(" ")}</td></tr>`).join("") + `</table>`;
      } catch (e) { toast(e.message); }
      btn.disabled = false; btn.textContent = L("Avvia AN + LT (~15 s)", "Run AN + LT (~15 s)");
    };
    bar.append(btn, lab);
    p.body.appendChild(bar);
    p.ro = CE("div"); p.body.appendChild(p.ro);
    p.pages = CE("div"); p.body.appendChild(p.pages);
    p.sm = CE("div"); p.body.appendChild(p.sm);
    p.ltPlot = CE("div", "plot"); p.body.appendChild(p.ltPlot);
    p.ltTable = CE("div"); p.ltTable.style.cssText = "max-height:180px;overflow-y:auto"; p.body.appendChild(p.ltTable);
    p.body.appendChild(CE("div", "note", L(
      "Auto-Negotiation Clause 73 a livello di PROTOCOLLO (base page 48 bit, priority resolution → HCD, timer di Table 73-7; niente segnalazione DME) + Link Training BIDIREZIONALE con l'handshake di Clause 72/136 su un TX FIR a 5 tap: preset di clause, richieste increment/decrement per c(−2)/c(−1)/c(+1)/c(+2) con vincolo di picco, adattazione RX locale (CTLE/CDR), receiver ready per direzione e both_ready. I tap allenati si applicano solo se superano un holdout su seed indipendente (l'LT su un solo seed può overfittare). La decisione del RX usa la metrica di apertura d'occhio misurata (Q minimo allo slicer). Clause 73 esiste per KR/CR (backplane/rame): sull'ottica la gestione è CMIS.",
      "Clause 73 Auto-Negotiation at the PROTOCOL level (48-bit base page, priority resolution → HCD, Table 73-7 timers; no DME signalling) plus BIDIRECTIONAL Link Training with the Clause 72/136 handshake on a 5-tap TX FIR: clause presets, increment/decrement requests for c(−2)/c(−1)/c(+1)/c(+2) with peak constraint, local RX adaptation (CTLE/CDR), receiver ready per direction and both_ready. The trained taps are accepted only if they pass a holdout on an independent seed (single-seed LT can overfit). RX decisions use the bench-measured eye-opening metric (min Q at the slicer). Clause 73 exists for KR/CR (backplane/copper): optics is managed via CMIS.")));
  },
};

/* --- Link training --- */
PANEL_DEFS.train = {
  title: "Link training (coordinate descent)", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    const bar = CE("div", "scope-bar");
    const btn = CE("button", "btn btn-accent", L("Avvia training (~10 s)", "Start training (~10 s)"));
    btn.dataset.action = "local_train";
    btn.onclick = async () => {
      btn.disabled = true; btn.textContent = "training…";
      try {
        const d = await POST("/api/experiment/train", {});
        const rows = d.steps.map(s =>
          `<tr><td>${s.param}</td><td>${s.chosen == null ? "invariato" : (s.field.includes("hz") ? fix(s.chosen / 1e9, 1) + " GHz" : fix(s.chosen, 2))}</td><td>${sci(s.score_after)}</td></tr>`).join("");
        p.out.innerHTML = `<div class="readout">
          <div class="ro"><label>BER media prima</label><b>${sci(d.score_before)}</b><span class="sub">2 seed</span></div>
          <div class="ro"><label>BER media dopo</label><b class="${d.score_after < d.score_before ? "ok" : ""}">${sci(d.score_after)}</b><span class="sub">config applicata</span></div>
          <div class="ro"><label>holdout indipendente</label><b class="${d.accepted ? "ok" : "fail"}">${sci(d.verification_before)} → ${sci(d.verification_after)}</b><span class="sub">${d.accepted ? L("accettato", "accepted") : L("respinto: ripristinata config", "rejected: config restored")}</span></div>
          </div><table class="mini"><tr><th>fase</th><th>scelta</th><th>score</th></tr>${rows}</table>`;
      } catch (e) { p.out.innerHTML = `<div class="note w">${e.message}</div>`; }
      btn.disabled = false; btn.textContent = "Avvia training (~10 s)";
    };
    bar.append(btn);
    p.body.appendChild(bar);
    p.out = CE("div"); p.body.appendChild(p.out);
    p.body.appendChild(CE("div", "note", L("Fasi: CTLE zero → CTLE gain DC → TX FIR pre → TX FIR post, ognuna valutata end-to-end su 2 seed (i LINK DOWN contano 0.5). NON è l'AN/LT di clause (nessuno scambio di coefficienti col link partner): è un tuning locale onesto. La config migliore viene applicata al banco.", "Phases: CTLE zero → CTLE DC gain → TX FIR pre → TX FIR post, each evaluated end-to-end on 2 seeds (LINK DOWN counts 0.5). This is NOT clause AN/LT (no coefficient exchange with a link partner): it is an honest local tuning. The best config is applied to the bench.")));
  },
};


/* --- CMIS-lite: gestione modulo (DOM/VDM) --- */
PANEL_DEFS.cmis = {
  title: "Module · CMIS-lite (DOM/VDM)", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    p.host = CE("div"); p.body.appendChild(p.host);
    p.note = CE("div", "note", L(
      "Subset ispirato a CMIS 5.x (MSA pubblico): Module/DataPath state machine, flag di lane e monitor DOM/VDM derivati dal banco reale (LOL dal lock del CDR, potenze da MZM/PD, BER dai contatori). NON è la register map completa: niente pagine/I2C/CDB/firmware — vedi roadmap.",
      "Subset inspired by CMIS 5.x (public MSA): Module/DataPath state machine, lane flags and DOM/VDM monitors derived from the real bench (LOL from CDR lock, powers from MZM/PD, BER from counters). NOT the full register map: no pages/I2C/CDB/firmware — see roadmap."));
    p.body.appendChild(p.note);
    p.lastFetch = 0;
    this.refetch(p);
  },
  async refetch(p) {
    try {
      const d = await GET(`/api/panel/cmis?source=${S.running ? "live" : "auto"}`); acqBadge(p, d);
      const lf = d.lane_flags[0];
      const flag = (on, name) => `<span class="badge ${on ? "fail" : "ok"}">${name}: ${on ? "ON" : "off"}</span>`;
      const states = ["ModuleLowPwr", "ModuleReady"];
      const dps = ["DataPathDeinit", "DataPathInit", "DataPathActivated"];
      const smBox = (list, active) => list.map(x =>
        `<span class="badge ${x === active ? (active.includes("Activated") || active.includes("Ready") ? "ok" : "warn") : ""}" style="opacity:${x === active ? 1 : 0.4}">${x}</span>`).join(" → ");
      const domRows = d.dom.map(r =>
        `<tr><td>${r.name}</td><td>${r.value == null ? "—" : fix(r.value, 2)} ${r.unit}</td><td>${r.warn_lo}…${r.warn_hi}</td><td><span class="badge ${r.status === "ok" ? "ok" : (r.status === "na" ? "" : "warn")}">${r.status.toUpperCase()}</span></td></tr>`).join("");
      const vdmRows = d.vdm.map(r =>
        `<tr><td>${r.name}</td><td>${r.value == null ? "—" : (typeof r.value === "number" && r.value !== 0 && Math.abs(r.value) < 1e-2 ? sci(r.value) : fix(r.value, 3))}</td></tr>`).join("");
      p.host.innerHTML = `
        <div class="readout">
          <div class="ro"><label>${L("modulo", "module")}</label><b>${d.module.part}</b><span class="sub">${d.module.form_factor} · ${d.module.media}</span></div>
          <div class="ro"><label>Module state</label><b>${smBox(states, d.module_state)}</b></div>
          <div class="ro"><label>DataPath state</label><b>${smBox(dps, d.datapath_state)}</b></div>
        </div>
        <div style="margin:6px 0">${flag(lf.rx_los, "RX-LOS")} ${flag(lf.rx_lol, "RX-LOL")} ${flag(lf.tx_fault, "TX-FAULT")}</div>
        <table class="mini"><tr><th>DOM</th><th>${L("valore", "value")}</th><th>${L("soglie warn", "warn range")}</th><th></th></tr>${domRows}</table>
        <table class="mini" style="margin-top:6px"><tr><th>VDM</th><th>${L("valore", "value")}</th></tr>${vdmRows}</table>`;
    } catch (e) { p.host.innerHTML = `<div class="note w">${e.message}</div>`; }
  },
  onConfig(p) { this.refetch(p); },
  onTick(p) { if (throttled(p, 2500)) this.refetch(p); },
};

/* --- sweep parametrico integrato --- */
PANEL_DEFS.sweep = {
  title: "Sweep parametrico (end-to-end)", size: "s6",
  make(p) {
    p.body.innerHTML = "";
    const bar = CE("div", "scope-bar");
    p.fieldSel = CE("select");
    for (const [k, v] of Object.entries(S.sweepable || {})) {
      const o = CE("option"); o.value = k; o.textContent = tr(v.label); p.fieldSel.appendChild(o);
    }
    p.lo = CE("input"); p.lo.type = "number"; p.lo.style.width = "90px";
    p.hi = CE("input"); p.hi.type = "number"; p.hi.style.width = "90px";
    p.n = CE("input"); p.n.type = "number"; p.n.value = 9; p.n.min = 3; p.n.max = 15; p.n.style.width = "56px";
    const syncRange = () => { const d = S.sweepable[p.fieldSel.value]; p.lo.value = d.lo; p.hi.value = d.hi; };
    p.fieldSel.onchange = syncRange;
    if (S.sweepable && Object.keys(S.sweepable).length) syncRange();
    const btn = CE("button", "btn btn-accent", L("Esegui", "Run"));
    btn.dataset.action = "sweep";
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
        mergeAxis(lay, "xaxis", { title: { text: tr(d.label), font: { size: 10 } } });
        mergeAxis(lay, "yaxis", { type: "log", title: { text: "BER (validation)", font: { size: 10 } } });
        plot(p.plotEl, traces, lay);
        p.note.innerHTML = `Ogni punto è una run end-to-end completa (nuovo canale/rumore ricalcolati). Le "✗" sono punti LINK DOWN: il CDR o il pattern lock non agganciano — su un banco reale il BERT mostrerebbe loss-of-sync, non una BER.`;
      } catch (e) { p.note.innerHTML = `<span class="fail">${e.message}</span>`; }
      btn.disabled = false; btn.textContent = "Esegui";
    };
    bar.append(p.fieldSel, CE("span", "", L("da", "from")), p.lo, CE("span", "", L("a", "to")), p.hi, CE("span", "", L("punti", "points")), p.n, btn);
    p.body.appendChild(bar);
    p.plotEl = CE("div", "plot"); p.body.appendChild(p.plotEl);
    p.note = CE("div", "note", L("Scegli un parametro e lancia: vedi la BER end-to-end rispondere alla manopola, incluso il punto in cui il link smette di agganciare.", "Pick a parameter and run: watch the end-to-end BER respond to the knob, including the point where the link stops locking."));
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
    btn.dataset.action = "jtol";
    btn.onclick = async () => {
      btn.disabled = true; btn.textContent = "bisezione… (~10 s)";
      try {
        const freqs = p.freqs.value.split(",").map(Number).filter(v => v > 0);
        p.lastData = await POST("/api/experiment/jtol", { freqs_mhz: freqs, target_ber: Number(p.target.value) });
        this.draw(p);
      } catch (e) { p.note.innerHTML = `<span class="fail">${e.message}</span>`; }
      btn.disabled = false; btn.textContent = "Misura JTOL";
    };
    bar.append(CE("span", "", "freq [MHz]:"), p.freqs, CE("span", "", "target BER:"), p.target, btn);
    p.body.appendChild(bar);
    // maschera di CONTESTO sovrapponibile (forma tipica delle maschere JTOL:
    // −20 dB/dec fino al corner, poi floor) — parametri espliciti, NON di clause
    const mbar = CE("div", "scope-bar");
    p.maskOn = CE("input"); p.maskOn.type = "checkbox"; p.maskOn.checked = true;
    const maskLab = CE("label", "", ""); maskLab.append(p.maskOn, document.createTextNode(" " + L("maschera", "mask")));
    p.maskFloor = CE("input"); p.maskFloor.type = "text"; p.maskFloor.value = "0.05"; p.maskFloor.style.width = "55px";
    p.maskCorner = CE("input"); p.maskCorner.type = "text"; p.maskCorner.style.width = "95px";
    p.maskCorner.placeholder = L("auto (loop BW)", "auto (loop BW)");
    p.maskOn.onchange = p.maskFloor.onchange = p.maskCorner.onchange = () => { if (p.lastData) this.draw(p); };
    mbar.append(maskLab, CE("span", "", "floor [UI]:"), p.maskFloor, CE("span", "", "corner [MHz]:"), p.maskCorner);
    p.body.appendChild(mbar);
    p.plotEl = CE("div", "plot"); p.body.appendChild(p.plotEl);
    p.note = CE("div", "note", L("Bisezione sull'ampiezza del PJ iniettato al TX PLL, per frequenza: la curva che ne esce è la firma della banda del CDR.", "Bisection on the PJ amplitude injected at the TX PLL, per frequency: the resulting curve is the signature of the CDR bandwidth."));
    p.body.appendChild(p.note);
  },
  maskAt(f_mhz, floor_ui, corner_mhz) {
    return Math.min(5, floor_ui * Math.max(1, corner_mhz / f_mhz));
  },
  draw(p) {
    const d = p.lastData;
    const ok = d.points.filter(q => q.amp_ui != null);
    const fbw = S.cfg.cdr_bw * S.cfg.symbol_rate_hz / 1e6;
    const traces = [{ x: ok.map(q => q.freq_mhz), y: ok.map(q => q.amp_ui), mode: "lines+markers", name: "tolleranza", line: { color: COL.dg, width: 2 }, marker: { size: 8, symbol: ok.map(q => q.capped ? "triangle-up" : "circle") } }];
    let maskNote = "";
    const floor = Number(p.maskFloor.value);
    const corner = Number(p.maskCorner.value) > 0 ? Number(p.maskCorner.value) : fbw;
    if (p.maskOn.checked && isFinite(floor) && floor > 0 && d.points.length) {
      const fs = d.points.map(q => q.freq_mhz);
      const fLo = Math.min(...fs) / 2, fHi = Math.max(...fs) * 2;
      const grid = [];
      for (let i = 0; i <= 40; i++) grid.push(fLo * Math.pow(fHi / fLo, i / 40));
      traces.push({ x: grid, y: grid.map(f => this.maskAt(f, floor, corner)), mode: "lines", name: L("maschera (contesto)", "mask (context)"), line: { color: COL.am, dash: "dash", width: 1.5 } });
      const fails = d.points.filter(q => q.amp_ui == null || q.amp_ui < this.maskAt(q.freq_mhz, floor, corner));
      maskNote = `<br><b>${L("Maschera di contesto", "Context mask")}</b> (floor ${fix(floor, 3)} UI · corner ${fix(corner, 0)} MHz, −20 dB/dec): ` +
        (fails.length
          ? `<span class="fail">${fails.length}/${d.points.length} ${L("punti sotto la maschera", "points below the mask")}</span> (${fails.map(q => fix(q.freq_mhz, 0) + " MHz").join(", ")})`
          : `<span class="ok">${L("tutti i punti sopra la maschera", "all points above the mask")}</span>`) +
        ` — ${L("forma tipica dichiarata, NON una maschera di clause", "typical declared shape, NOT a clause mask")}.`;
    }
    const lay = PL({ height: 270, showlegend: false });
    mergeAxis(lay, "xaxis", { type: "log", title: { text: "frequenza PJ [MHz]", font: { size: 10 } } });
    mergeAxis(lay, "yaxis", { title: { text: "ampiezza PJ tollerata [UI pk]", font: { size: 10 } }, range: [0, 0.4] });
    plot(p.plotEl, traces, lay);
    const rows = d.points.map(q => q.amp_ui == null ? `${q.freq_mhz} MHz: ${L("link già KO senza PJ", "link already down without PJ")}` : `${fix(q.freq_mhz, 0)} MHz: ${fix(q.amp_ui, 3)} UI (${fix(q.amp_ps, 2)} ps)${q.capped ? " ≥cap" : ""}`).join(" · ");
    p.note.innerHTML = `Target BER ${sci(d.target_ber)} — ${rows}.<br>Il <b>minimo vicino a ~${fix(fbw, 0)} MHz</b> (banda del loop) è il <b>jitter peaking</b> del CDR di 2° ordine: prova a cambiare cdr_bw/damping e rifai la misura. Il record (~${fix(S.cfg.n_symbols / (S.cfg.symbol_rate_hz / 1e9), 0)} ns) limita le basse frequenze a ≥3 cicli. <b>NON normativa</b>: le maschere JTOL di clause hanno pattern, durata e procedure prescritte.${maskNote}`;
  },
};

/* ---------------- workbench a sezioni (ordinato per flusso del segnale) --- */
const GROUPS = [L("PANORAMICA", "OVERVIEW"), L("SORGENTE · TX", "SOURCE · TX"),
  L("CANALE · OTTICA", "CHANNEL · OPTICS"), "RX · DSP",
  L("STRUMENTI · ANALISI LIVE", "INSTRUMENTS · LIVE ANALYSIS")];
const GROUP_COLORS = [COL.muted, COL.dg, COL.el, COL.op, COL.am];
// [tipo, nome, dominio, gruppo, ordine nel gruppo]
const PALETTE = [
  ["chain", L("Catena del segnale", "Signal chain"), null, 0, 0],
  ["bert", L("BERT · generatore TX + analizzatore errori", "BERT · TX generator + error analyzer"), "digital", 1, 0],
  ["tx", "TX: FIR·DAC·driver", "electrical", 1, 2],
  ["channel", L("Canale elettrico", "Electrical channel"), "electrical", 2, 0],
  ["com", "COM · IEEE 802.3 Annex 93A", "electrical", 2, 0.5],
  ["optical", L("Ottica: MZM·fibra", "Optics: MZM · fiber"), "optical", 2, 1],
  ["rxfe", "RX front-end: PD·TIA·AGC", "electrical", 3, 0],
  ["pd", "Photodiode · PD", "optical", 3, 1],
  ["tia", "TIA / electrical AFE", "electrical", 3, 2],
  ["agc", "AGC · gain & headroom", "electrical", 3, 3],
  ["ctle", L("CTLE configurabile", "Configurable CTLE"), "electrical", 3, 4],
  ["adc", "ADC interleaved", "digital", 3, 5],
  ["timing", L("Timing · CDR", "Timing · CDR"), "digital", 3, 6],
  ["eq", "RX FFE (FSE) + DFE", "digital", 3, 7],
  ["decisions", L("Decisioni · slicer", "Decisions · slicer"), "digital", 3, 8],
  ["scope", "Scope · DCA", "electrical", 4, 0],
  ["jitter", "Jitter · TIE", "digital", 4, 1],
  ["spectrum", "Spectrum analyzer", "electrical", 4, 2],
  ["berlive", L("BER live (accumulo)", "Live BER (accumulated)"), "digital", 4, 3],
  ["feclive", L("FEC live (accumulo)", "Live FEC (accumulated)"), "digital", 4, 5],
  ["l2", "Ethernet · Traffic L2", "digital", 4, 6],
  ["cmis", "Module · CMIS-lite", "optical", 4, 6.5],
  ["sweep", L("Sweep parametrico", "Parametric sweep"), null, 4, 7],
  ["jtol", "JTOL-lite (PJ)", "digital", 4, 8],
  ["train", "Link training", "digital", 4, 9],
  ["anlt", "AN/LT · Clause 73", "digital", 4, 9.5],
  ["standards", "Standard IEEE/OIF", null, 4, 10],
  ["dr4proc", L("DR4 · procedura fisica", "DR4 · physical procedure"), "optical", 4, 10.5],
  ["instruments", "Instrument alignment", null, 4, 11],
  ["checks", "Checkpoint & ledger", null, 4, 12],
  ["physics", L("Audit fisico · invarianti", "Physics audit · invariants"), null, 4, 12.5],
  ["education", L("Academy · guida ai blocchi", "Academy · block guide"), null, 0, 1],
];
const VIEWS = {
  "Banco completo": ["chain", "bert", "scope", "jitter", "berlive", "feclive", "tx", "channel", "com", "optical", "pd", "tia", "agc", "ctle", "timing", "eq", "decisions", "spectrum", "sweep", "checks", "physics"],
  "Essenziale": ["chain", "scope", "berlive", "feclive"],
  "Sorgente e TX": ["chain", "bert", "tx", "scope", "jitter"],
  "Canale e ottica": ["chain", "channel", "com", "optical", "scope", "spectrum"],
  "RX e DSP": ["chain", "pd", "tia", "agc", "ctle", "adc", "timing", "eq", "decisions", "scope"],
  "Analisi live": ["scope", "jitter", "spectrum", "berlive", "feclive", "sweep", "jtol", "com", "standards", "dr4proc", "instruments", "checks", "physics"],
  "BERT e traffico": ["chain", "bert", "l2", "anlt", "feclive", "berlive", "train", "cmis"],
  "Scope P/N": ["chain", "scope", "scope", "bert", "jitter", "spectrum"],
  "Academy": ["chain", "education", "standards", "dr4proc", "instruments", "scope", "jitter", "bert", "l2"],
};
const VIEW_EN = { "Banco completo": "Full bench", "Essenziale": "Essential",
  "Sorgente e TX": "Source and TX", "Canale e ottica": "Channel and optics",
  "RX e DSP": "RX and DSP", "Analisi live": "Live analysis",
  "BERT e traffico": "BERT and traffic", "Academy": "Academy" };
VIEW_EN["Scope P/N"] = "P/N scope desk";
const PANEL_EN = {
  chain: "Signal chain", stimulus: "Stimulus · PPG", serpll: "Serializer · TX PLL · P/N output",
  tx: "TX · FIR · DAC · driver", channel: "Electrical channel · medium · crosstalk", com: "COM · IEEE 802.3 Annex 93A",
  optical: "Optics · MZM / EML · fiber", rxfe: "RX front-end · PD · TIA · AGC",
  pd: "Photodiode · PD", tia: "TIA / electrical AFE", agc: "AGC · gain and headroom",
  ctle: "CTLE · configurable sections", adc: "Interleaved ADC", timing: "Timing · CDR",
  eq: "RX FFE (T/2 FSE) + DFE", decisions: "Decisions · slicer", scope: "Scope · DCA",
  jitter: "Jitter · TIE", spectrum: "Spectrum analyzer", berlive: "Live BER · accumulated",
  bert: "BERT · TX generator + error analyzer", feclive: "Live FEC · accumulated",
  l2: "Ethernet · Traffic L2-lite", sweep: "End-to-end parametric sweep",
  jtol: "JTOL-lite (PJ)", train: "Link training · coordinate descent", anlt: "AN/LT · Clause 73 + training",
  standards: "IEEE / OIF standards", checks: "Checkpoints & signal ledger",
  dr4proc: "DR4 · end-to-end physical procedure",
  physics: "Physics audit · invariants",
  instruments: "Instrument alignment · DCA / BERT / Traffic",
  education: "Academy · block and standards guide",
};
const PANEL_LEARN = { anlt: "anlt", cmis: "cmis", stimulus: "stimulus", serpll: "serpll", tx: "tx", channel: "channel", com: "channel",
  optical: "optical", rxfe: "rxfe", pd: "rxfe", tia: "rxfe", agc: "rxfe", ctle: "ctle", adc: "adc", timing: "timing",
  eq: "eq", decisions: "eq", scope: "scope", jitter: "scope", bert: "bert",
  feclive: "fec", l2: "l2", standards: "standards" };
let PANEL_SEQ = 0;
let _layoutPersistence = true;
let _buildingLayout = false;
let _layoutGeneration = 0;
let _activePanelId = null;
let _dragPanelId = null;
let _dragGroupId = null;
let _tabGroups = [];
const CUSTOM_VIEW = "__custom__";
const WORKSPACE_KEY = "labpro_workspace4";
const LEGACY_WORKSPACE_KEY = "labpro_workspace3";
// Compatibilità di navigazione senza card duplicate: Academy, vecchi layout
// e URL ?panels=stimulus/serpll aprono una vista della SOLA console BERT.
const PANEL_ALIASES = {
  stimulus: { type: "bert", tab: "source" },
  serpll: { type: "bert", tab: "stress" },
  bertcheck: { type: "bert", tab: "checker" },
  bertproc: { type: "bert", tab: "procedures" },
};

function workspacePanel(id) { return S.panels.find(p => p.id === id); }
function tabGroup(id) { return _tabGroups.find(g => g.id === id); }
function syncTabGroup(g) {
  const count = S.panels.filter(p => p.group === g.id).length;
  g.el.classList.toggle("collapsed", g.collapsed);
  g.el.classList.toggle("empty", count === 0);
  g.el.classList.toggle("has-active", S.panels.some(p => p.group === g.id && p.id === _activePanelId));
  g.label.setAttribute("aria-expanded", g.collapsed ? "false" : "true");
  g.count.textContent = String(count);
  // I gruppi vuoti restano drop-target visibili finché esiste almeno un tab:
  // altrimenti, spostato l'ultimo tab, non ci sarebbe modo di rimetterlo.
  g.el.hidden = S.panels.length === 0;
}
function moveGroupToIndex(g, target) {
  const from = _tabGroups.indexOf(g); if (from < 0) return;
  target = Math.max(0, Math.min(target, _tabGroups.length - 1));
  if (from === target) return;
  _tabGroups.splice(from, 1); _tabGroups.splice(target, 0, g);
  syncPanelOrder(); saveLayout();
}
function moveGroupRelative(g, targetGroup, before) {
  const from = _tabGroups.indexOf(g), target = _tabGroups.indexOf(targetGroup);
  if (from < 0 || target < 0 || g === targetGroup) return;
  let insert = target + (before ? 0 : 1);
  _tabGroups.splice(from, 1); if (from < insert) insert--;
  _tabGroups.splice(Math.max(0, Math.min(insert, _tabGroups.length)), 0, g);
  syncPanelOrder(); saveLayout();
}
function movePanelToGroupEnd(p, group) {
  const from = S.panels.indexOf(p); if (from < 0 || !group) return;
  S.panels.splice(from, 1); p.group = group.id;
  let at = S.panels.length;
  for (let i = S.panels.length - 1; i >= 0; i--) {
    if (S.panels[i].group === group.id) { at = i + 1; break; }
  }
  S.panels.splice(at, 0, p); group.collapsed = false;
  syncPanelOrder(); activatePanel(p, true); saveLayout();
}
function ensureTabGroups(state = null) {
  if (_tabGroups.length) return;
  const byId = new Map((state || []).filter(x => Number.isInteger(x.id)).map(x => [x.id, x]));
  const ordered = [...byId.keys()].filter(id => id >= 0 && id < GROUPS.length);
  for (let id = 0; id < GROUPS.length; id++) if (!ordered.includes(id)) ordered.push(id);
  const list = $("#workspace-tab-list");
  for (const id of ordered) {
    const saved = byId.get(id) || {};
    const g = { id, collapsed: !!saved.collapsed };
    g.el = CE("div", "workspace-tab-group"); g.el.dataset.groupId = id;
    g.el.style.setProperty("--group-color", GROUP_COLORS[id]);
    g.label = CE("button", "tab-group-label"); g.label.type = "button";
    g.label.draggable = true;
    g.label.append(document.createTextNode(GROUPS[id]), g.count = CE("span", "tab-group-count", "0"));
    g.label.title = `${GROUPS[id]} — ` + TT("clic = comprimi; trascina = riordina gruppo; rilascia qui un tab = spostalo nel gruppo", "click = collapse; drag = reorder group; drop a tab here = move it into the group");
    g.label.onclick = () => { if (_dragGroupId != null) return; g.collapsed = !g.collapsed; syncTabGroup(g); saveLayout(); };
    g.label.onkeydown = e => {
      if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && e.shiftKey) {
        e.preventDefault(); moveGroupToIndex(g, _tabGroups.indexOf(g) + (e.key === "ArrowLeft" ? -1 : 1)); g.label.focus();
      }
    };
    g.label.ondragstart = e => {
      _dragGroupId = g.id; g.el.classList.add("group-dragging");
      if (e.dataTransfer) { e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", `group:${g.id}`); }
    };
    g.label.ondragover = e => {
      if (_dragGroupId == null && _dragPanelId == null) return;
      e.preventDefault(); clearDropHints(); const r = g.el.getBoundingClientRect();
      if (_dragGroupId != null && _dragGroupId !== g.id)
        g.el.classList.add(e.clientX < r.left + r.width / 2 ? "group-drop-before" : "group-drop-after");
      if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
    };
    g.label.ondrop = e => {
      e.preventDefault();
      if (_dragGroupId != null) {
        const dragged = tabGroup(_dragGroupId), r = g.el.getBoundingClientRect();
        if (dragged) moveGroupRelative(dragged, g, e.clientX < r.left + r.width / 2);
      } else if (_dragPanelId != null) movePanelToGroupEnd(workspacePanel(_dragPanelId), g);
      clearDropHints();
    };
    g.label.ondragend = () => { g.el.classList.remove("group-dragging"); clearDropHints(); _dragGroupId = null; };
    g.tabsEl = CE("div", "tab-group-tabs");
    g.tabsEl.ondragover = e => { if (_dragPanelId != null) { e.preventDefault(); if (e.dataTransfer) e.dataTransfer.dropEffect = "move"; } };
    g.tabsEl.ondrop = e => { if (_dragPanelId != null) { e.preventDefault(); movePanelToGroupEnd(workspacePanel(_dragPanelId), g); } };
    g.el.append(g.label, g.tabsEl); list.appendChild(g.el); _tabGroups.push(g);
  }
}
function clearDropHints() {
  document.querySelectorAll(".workspace-tab.drop-before,.workspace-tab.drop-after")
    .forEach(el => el.classList.remove("drop-before", "drop-after"));
  document.querySelectorAll(".workspace-tab-group.group-drop-before,.workspace-tab-group.group-drop-after")
    .forEach(el => el.classList.remove("group-drop-before", "group-drop-after"));
}
function syncWorkspaceEmpty() {
  const empty = $("#workspace-empty");
  if (empty) empty.hidden = S.panels.length !== 0;
}
function syncPanelOrder() {
  ensureTabGroups();
  const list = $("#workspace-tab-list"), stage = $("#workbench");
  const known = new Set(_tabGroups.map(g => g.id));
  for (const p of S.panels) if (!known.has(p.group)) p.group = 4;
  S.panels = _tabGroups.flatMap(g => S.panels.filter(p => p.group === g.id));
  for (const g of _tabGroups) {
    list.appendChild(g.el);
    for (const p of S.panels.filter(p => p.group === g.id)) g.tabsEl.appendChild(p.tabEl);
    syncTabGroup(g);
  }
  for (const p of S.panels) stage.appendChild(p.el);
}
function movePanelToIndex(p, target) {
  const from = S.panels.indexOf(p);
  if (from < 0) return;
  target = Math.max(0, Math.min(target, S.panels.length - 1));
  if (from === target) return;
  const neighbor = S.panels[target]; if (neighbor) p.group = neighbor.group;
  S.panels.splice(from, 1);
  S.panels.splice(target, 0, p);
  syncPanelOrder();
  p.tabEl.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
  saveLayout();
}
function movePanelRelative(p, targetPanel, before) {
  const from = S.panels.indexOf(p), target = S.panels.indexOf(targetPanel);
  if (from < 0 || target < 0 || p === targetPanel) return;
  let insert = target + (before ? 0 : 1);
  S.panels.splice(from, 1); p.group = targetPanel.group;
  if (from < insert) insert--;
  S.panels.splice(Math.max(0, Math.min(insert, S.panels.length)), 0, p);
  syncPanelOrder();
  saveLayout();
}
function createWorkspaceTab(p, dot, label) {
  ensureTabGroups();
  const tab = CE("div", "workspace-tab");
  tab.draggable = true; tab.dataset.panelId = p.id;
  tab.style.setProperty("--tab-color", (dot && DOMC[dot]) || COL.muted);
  const main = CE("button", "workspace-tab-main");
  main.type = "button"; main.id = `workspace-tab-${p.id}`;
  main.setAttribute("role", "tab"); main.setAttribute("aria-controls", `workspace-panel-${p.id}`);
  main.setAttribute("aria-selected", "false"); main.tabIndex = -1;
  if (dot) main.appendChild(CE("span", "dom-dot", ""));
  const dotEl = main.querySelector(".dom-dot");
  if (dotEl) dotEl.style.background = DOMC[dot];
  main.appendChild(CE("span", "workspace-tab-label", label));
  main.title = TT("seleziona; frecce = cambia tab, Maiusc+frecce = riordina", "select; arrows = switch tab, Shift+arrows = reorder");
  main.onclick = () => activatePanel(p);
  main.onkeydown = e => {
    const i = S.panels.indexOf(p);
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault(); const d = e.key === "ArrowLeft" ? -1 : 1;
      if (e.shiftKey) { movePanelToIndex(p, i + d); p.tabButton.focus(); }
      else {
        const q = S.panels[(i + d + S.panels.length) % S.panels.length];
        if (q) activatePanel(q, true);
      }
    } else if (e.key === "Home" || e.key === "End") {
      e.preventDefault(); const q = S.panels[e.key === "Home" ? 0 : S.panels.length - 1];
      if (q) activatePanel(q, true);
    } else if (e.key === "Delete") { e.preventDefault(); closePanel(p); }
  };
  const close = CE("button", "workspace-tab-close", "×");
  close.type = "button";
  close.setAttribute("aria-label", L(`chiudi ${label}`, `close ${label}`));
  close.title = TT("chiude il pannello senza modificare il banco", "closes the panel without changing the bench");
  close.onclick = e => { e.stopPropagation(); closePanel(p); };
  tab.append(main, close);
  tab.ondragstart = e => {
    _dragPanelId = p.id; tab.classList.add("dragging");
    if (e.dataTransfer) { e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", String(p.id)); }
  };
  tab.ondragover = e => {
    if (_dragPanelId == null || _dragPanelId === p.id) return;
    e.preventDefault(); clearDropHints();
    const r = tab.getBoundingClientRect();
    tab.classList.add(e.clientX < r.left + r.width / 2 ? "drop-before" : "drop-after");
    if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
  };
  tab.ondrop = e => {
    e.preventDefault();
    const dragged = workspacePanel(_dragPanelId);
    const r = tab.getBoundingClientRect();
    if (dragged) movePanelRelative(dragged, p, e.clientX < r.left + r.width / 2);
    clearDropHints();
  };
  tab.ondragend = () => {
    tab.classList.remove("dragging"); clearDropHints(); _dragPanelId = null;
  };
  p.tabEl = tab; p.tabButton = main;
  (tabGroup(p.group) || tabGroup(4)).tabsEl.appendChild(tab);
}
function mountPanel(p) {
  if (p._mounted) return;
  p._mounted = true; p._needsConfig = false;
  try { p.def.make(p); decorateControls(p.body); }
  catch (e) { p.body.innerHTML = `<div class="note w">${e.message}</div>`; console.error(e); }
  // Il reset compare solo dopo il mount lazy, quando le manopole esistono.
  if (p.body.querySelector(".param, [data-ffe]")) {
    const btnReset = CE("button", "icon-btn", "↺");
    btnReset.title = L("riporta le manopole di questo pannello ai valori default", "reset this panel's knobs to their defaults");
    btnReset.setAttribute("aria-label", L("reset manopole ai default", "reset knobs to defaults"));
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
    p.head.insertBefore(btnReset, p.btnExport);
  }
  if (p.type === "scope") refreshDcaProbes();
}
function activatePanel(p, focusTab = false) {
  if (!p || !S.panels.includes(p)) return;
  _activePanelId = p.id;
  const group = tabGroup(p.group); if (group) group.collapsed = false;
  for (const q of S.panels) {
    const active = q === p;
    q.el.hidden = !active; q.el.classList.toggle("active", active);
    q.tabEl.classList.toggle("active", active);
    q.tabButton.setAttribute("aria-selected", active ? "true" : "false");
    q.tabButton.tabIndex = active ? 0 : -1;
  }
  for (const g of _tabGroups) syncTabGroup(g);
  const wasMounted = p._mounted;
  mountPanel(p);
  if (p._needsConfig && p.def.onConfig) {
    p._needsConfig = false; _cfgDirty.delete(p);
    try { p.def.onConfig(p); } catch (e) { panelError(p, e); }
  } else if (wasMounted && p.def.onTick) {
    try { p.lastFetch = 0; p.def.onTick(p); } catch (e) { panelError(p, e); }
  }
  const stage = $("#workbench"); if (stage) stage.scrollTop = 0;
  p.tabEl.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
  if (focusTab) p.tabButton.focus();
  if (window.Plotly) requestAnimationFrame(() => {
    for (const gd of p.el.querySelectorAll(".js-plotly-plot")) try { Plotly.Plots.resize(gd); } catch (e) { }
  });
  syncWorkspaceEmpty(); saveLayout(false);
}
function closePanel(p) {
  const idx = S.panels.indexOf(p); if (idx < 0) return;
  const wasActive = p.id === _activePanelId;
  destroyPanel(p); S.panels.splice(idx, 1);
  if (p.type === "scope") refreshDcaProbes();
  if (wasActive) {
    _activePanelId = null;
    const next = S.panels[Math.min(idx, S.panels.length - 1)];
    if (next) activatePanel(next, true);
  }
  syncPanelOrder();
  syncWorkspaceEmpty(); saveLayout();
}

function addPanel(type, size, groupOverride) {
  const alias = PANEL_ALIASES[type];
  const requestedBertTab = alias ? alias.tab : null;
  if (alias) type = alias.type;
  const def = PANEL_DEFS[type]; if (!def) return;
  const existing = S.panels.filter(p => p.type === type);
  // i pannelli "multi" (Scope) possono avere più istanze: canale A/B per
  // confrontare due nodi fianco a fianco
  if (existing.length && !def.multi) {
    activatePanel(existing[0], true);
    if (requestedBertTab && def.showTab) def.showTab(existing[0], requestedBertTab);
    flash(existing[0].el); return existing[0];
  }
  if (def.multi && existing.length >= 2) { activatePanel(existing[0], true); flash(existing[0].el); return existing[0]; }
  const pal = PALETTE.find(x => x[0] === type);
  const p = { id: ++PANEL_SEQ, type, def, size: size || def.size || "s6",
    group: Number.isInteger(groupOverride) && groupOverride >= 0 && groupOverride < GROUPS.length
      ? groupOverride : (pal ? pal[3] : 4),
    order: (pal ? pal[4] : 99) + existing.length * 0.1 };
  p.requestedBertTab = requestedBertTab;
  p.el = CE("section", "panel " + p.size);
  p.el.id = `workspace-panel-${p.id}`; p.el.hidden = true;
  p.el.setAttribute("role", "tabpanel"); p.el.tabIndex = -1;
  p.head = CE("div", "panel-head");
  const dot = pal && pal[2] ? `<span class="dom-dot" style="background:${DOMC[pal[2]]}"></span>` : "";
  const instanceNo = def.multi ? (existing.length ? Math.max(...existing.map(x => x.instanceNo || 1)) + 1 : 1) : 0;
  p.instanceNo = instanceNo;
  const chLabel = def.multi ? ` · CH${instanceNo}` : "";
  const fullLabel = L(def.title, PANEL_EN[type]) + chLabel;
  p.head.innerHTML = `${dot}<span class="t">${L(def.title, PANEL_EN[type])}${chLabel}</span><span class="spacer"></span>`;
  if (PANEL_LEARN[type]) {
    const learn = CE("button", "icon-btn", "?");
    learn.title = L("spiega blocco, formula, misura ed esperimento", "explain block, formula, measurement, and experiment");
    learn.setAttribute("aria-label", L("apri Academy per questo blocco", "open Academy for this block"));
    learn.onclick = () => openEducation(PANEL_LEARN[type]);
    p.head.appendChild(learn);
  }
  const btnExp = CE("button", "icon-btn", "⤓");
  btnExp.dataset.action = "panel_export";
  btnExp.setAttribute("aria-label", L("esporta card (PNG/CSV)", "export card (PNG/CSV)"));
  const hExp = S.actionHelp && S.actionHelp.panel_export;
  if (hExp) btnExp.title = TT(hExp.it, hExp.en);
  btnExp.onclick = () => exportPanel(p);
  p.btnExport = btnExp;
  p.head.append(btnExp);
  p.body = CE("div", "panel-body");
  p.el.append(p.head, p.body);
  $("#workbench").appendChild(p.el);
  createWorkspaceTab(p, pal && pal[2], fullLabel);
  p.el.setAttribute("aria-labelledby", p.tabButton.id);
  S.panels.push(p);
  syncPanelOrder();
  syncWorkspaceEmpty();
  if (!_buildingLayout) activatePanel(p, true);
  saveLayout();
  return p;
}
function flash(el) { el.style.outline = "2px solid " + COL.op; setTimeout(() => el.style.outline = "", 900); }
// distruzione pulita: senza Plotly.purge ogni chiusura di pannello o cambio
// vista (21 card in "Banco completo") lasciava vivi dati e resize-handler di
// tutti i grafici — memoria in crescita monotona a ogni switch
function destroyPanel(p) {
  p._dead = true;    // i refetch in coda non ripartono su una card rimossa
  if (window.Plotly) {
    for (const gd of p.el.querySelectorAll(".js-plotly-plot")) {
      try { Plotly.purge(gd); } catch (e) { /* grafico mai inizializzato */ }
    }
  }
  _cfgDirty.delete(p);
  if (p.tabEl) p.tabEl.remove();
  p.el.remove();
}
// export della card: ogni grafico Plotly in PNG (2×), il canvas Scope in
// PNG, ogni tabella in CSV — l'export era del tutto assente (e la modebar
// Plotly resta disattivata per pulizia visiva)
function exportPanel(p) {
  let n = 0;
  const stamp = new Date().toISOString().slice(0, 19).replace(/[T:]/g, "-");
  if (window.Plotly) {
    p.el.querySelectorAll(".js-plotly-plot").forEach((gd, i) => {
      Plotly.downloadImage(gd, { format: "png", scale: 2,
        filename: `${p.type}-plot${i + 1}-${stamp}` });
      n++;
    });
  }
  const cv = p.el.querySelector("canvas.scope");
  if (cv) {
    const a = CE("a"); a.href = cv.toDataURL("image/png");
    a.download = `${p.type}-scope-${stamp}.png`;
    document.body.appendChild(a); a.click(); a.remove(); n++;
  }
  p.el.querySelectorAll("table.mini").forEach((tb, i) => {
    const rows = [...tb.rows].map(r => [...r.cells].map(c =>
      `"${c.innerText.replace(/"/g, '""').replace(/\s*\n\s*/g, " ")}"`).join(","));
    const a = CE("a");
    a.href = URL.createObjectURL(new Blob([rows.join("\n")], { type: "text/csv" }));
    a.download = `${p.type}-table${i + 1}-${stamp}.csv`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    n++;
  });
  if (!n) toast(L("nessun grafico o tabella esportabile in questa card",
                  "no exportable plot or table in this card"));
}
function applyView(name) {
  ensureTabGroups();
  _buildingLayout = true;
  for (const p of [...S.panels]) { destroyPanel(p); }
  S.panels = []; _activePanelId = null; syncPanelOrder(); syncWorkspaceEmpty();
  addPanelsStaggered(VIEWS[name] || VIEWS["Banco completo"], () => {
    // I tab sono creati in modo lazy: Scope P/N riceve il piano iniziale
    // prima del primo mount, quindi non serve montare card nascoste.
    if (name === "Scope P/N") {
      const scopes = S.panels.filter(p => p.type === "scope");
      if (scopes[0]) scopes[0].initialNode = "vp";
      if (scopes[1]) scopes[1].initialNode = "vn";
    }
    _buildingLayout = false;
    if (S.panels[0]) activatePanel(S.panels[0]);
    const vs = $("#view-select"); if (vs) vs.value = name;
    saveLayout(false);
  });
}
function saveLayout(markCustom = true) {
  if (!_layoutPersistence || _buildingLayout) return;
  const panels = S.panels.map(p => [p.type, p.size, p.group]);
  const groups = _tabGroups.map(g => ({ id: g.id, collapsed: g.collapsed }));
  const activeIndex = Math.max(0, S.panels.findIndex(p => p.id === _activePanelId));
  // layout2 resta come mirror di downgrade; workspace4 aggiunge gruppi,
  // ordine tab, collapse e tab attivo senza perdere i vecchi layout.
  localStorage.setItem("labpro_layout2", JSON.stringify(panels.map(x => x.slice(0, 2))));
  localStorage.setItem(WORKSPACE_KEY, JSON.stringify({ version: 4, activeIndex, groups, panels }));
  if (markCustom) {
    const vs = $("#view-select"); if (vs) vs.value = CUSTOM_VIEW;
  }
}
function addPanelsStaggered(list, done) {
  // creazione SCAGLIONATA: un pannello alla volta con un respiro fra l'uno
  // e l'altro — il render sincrono di 15+ pannelli Plotly in un colpo solo
  // congelava la pagina per ~15 s all'avvio
  // Il token annulla una vista precedente se l'utente cambia selezione prima
  // che la costruzione sia terminata, evitando card residue della vecchia vista.
  const generation = ++_layoutGeneration;
  let i = 0;
  const step = () => {
    if (generation !== _layoutGeneration) return;
    if (i >= list.length) { if (done) done(); return; }
    const [t, sz, group] = Array.isArray(list[i]) ? list[i] : [list[i], undefined, undefined];
    i++;
    try { addPanel(t, sz, group); } catch (e) { console.warn("panel", t, e); }
    setTimeout(() => requestAnimationFrame(step), 60);
  };
  step();
}
function loadLayout() {
  // ?safe / ?panels=a,b: diagnostica non persistente. In precedenza ogni
  // addPanel sovrascriveva il layout dell'utente con la vista di test.
  const q = new URLSearchParams(location.search);
  if (q.has("safe")) {
    _layoutPersistence = false;
    $("#view-select").value = CUSTOM_VIEW;
    addPanel("chain"); return;
  }
  if (q.has("panels")) {
    _layoutPersistence = false;
    $("#view-select").value = CUSTOM_VIEW;
    _buildingLayout = true;
    addPanelsStaggered(q.get("panels").split(","), () => {
      _buildingLayout = false;
      if (S.panels[0]) activatePanel(S.panels[0]);
    });
    return;
  }
  let saved = null, activeIndex = 0, groupState = null;
  try {
    const ws = JSON.parse(localStorage.getItem(WORKSPACE_KEY));
    if (ws && ws.version === 4 && Array.isArray(ws.panels)) {
      saved = ws.panels; groupState = Array.isArray(ws.groups) ? ws.groups : null;
      activeIndex = Number.isInteger(ws.activeIndex) ? ws.activeIndex : 0;
    }
  } catch (e) { }
  if (!saved) try {
    const ws3 = JSON.parse(localStorage.getItem(LEGACY_WORKSPACE_KEY));
    if (ws3 && ws3.version === 3 && Array.isArray(ws3.panels)) {
      saved = ws3.panels; activeIndex = Number.isInteger(ws3.activeIndex) ? ws3.activeIndex : 0;
    }
  } catch (e) { }
  if (!saved) try { saved = JSON.parse(localStorage.getItem("labpro_layout2")); } catch (e) { }
  ensureTabGroups(groupState);
  if (saved && saved.length) {
    _buildingLayout = true;
    addPanelsStaggered(saved, () => {
      _buildingLayout = false;
      activatePanel(S.panels[Math.max(0, Math.min(activeIndex, S.panels.length - 1))] || S.panels[0]);
      $("#view-select").value = CUSTOM_VIEW;
      saveLayout(false);
    });
  }
  else applyView("Banco completo");
}

/* ---------------- errori dei pannelli visibili ---------------- */
// prima: 18 refetch su 22 senza try/catch → unhandled rejection e pannello
// che congela mostrando dati vecchi come fossero validi. Ogni refetch è ora
// avvolto una volta sola qui: un errore diventa un badge ⚠ sull'header (con
// il messaggio nel tooltip), il successivo refetch riuscito lo toglie.
function panelError(p, e) {
  if (!p || !p.head) return;
  if (!e) { if (p.errEl) { p.errEl.remove(); p.errEl = null; } return; }
  console.warn("panel", p.type, e);
  if (!p.errEl) {
    p.errEl = CE("span", "panel-err", "⚠");
    const sp = p.head.querySelector(".spacer");
    if (sp) p.head.insertBefore(p.errEl, sp); else p.head.appendChild(p.errEl);
  }
  p.errEl.title = L("ultimo aggiornamento fallito: ", "last refresh failed: ") + (e.message || e);
}
function panelLoading(p, active) {
  if (!p || !p.head) return;
  if (!active) {
    if (p.loadingEl) { p.loadingEl.remove(); p.loadingEl = null; }
    p.el.classList.remove("is-loading"); return;
  }
  if (!p.loadingEl) {
    p.loadingEl = CE("span", "panel-loading", L("AGGIORNAMENTO…", "UPDATING…"));
    const sp = p.head.querySelector(".spacer");
    if (sp) p.head.insertBefore(p.loadingEl, sp); else p.head.appendChild(p.loadingEl);
  }
  p.loadingEl.title = L("i dati visibili appartengono al record precedente finché il calcolo non termina", "visible data belong to the previous record until computation completes");
  p.el.classList.add("is-loading");
}
// ...e SERIALIZZATO per pannello: una sola richiesta in volo alla volta, con
// al massimo un rilancio in coda ("l'ultimo vince"). Le risposte non possono
// più dipingersi fuori ordine — prima 31 pannelli su 34 potevano mostrare il
// dato di una richiesta superata sopra quello più recente.
for (const def of Object.values(PANEL_DEFS)) {
  if (!def.refetch) continue;
  const orig = def.refetch;
  def.refetch = function (p, ...args) {
    if (p._dead) return;
    if (p._refetchBusy) { p._refetchQueued = args; return; }
    p._refetchBusy = true;
    const run = (a) => {
      const cfgVersion = p._cfgVersion || 0;
      const done = () => { if ((p._cfgVersion || 0) === cfgVersion) panelLoading(p, false); };
      return Promise.resolve()
        .then(() => orig.call(this, p, ...a))
        .then(v => { panelError(p, null); done(); return v; },
              e => { panelError(p, e); done(); })
        .then(() => {
          const nxt = p._refetchQueued;
          p._refetchQueued = null;
          if (nxt && !p._dead) return run(nxt);
          p._refetchBusy = false;
        });
    };
    return run(args);
  };
}

/* ---------------- avvio ---------------- */
async function boot() {
  const st = await GET("/api/state");
  S.cfg = st.cfg; S.acc = st.acc; S.running = st.running; S.presets = st.presets;
  S.defaults = st.defaults || {}; S.sweepable = st.sweepable || {};
  S.controlHelp = st.control_help || {}; S.actionHelp = st.action_help || {};
  decorateControls($("#topbar"));
  const ps = $("#preset-select");
  ps.innerHTML = `<option value="">— ${L("preset didattici", "educational presets")} —</option>`;
  for (const p of st.presets) { const o = CE("option"); o.value = p.name; o.textContent = tr(p.name); o.title = tr(p.desc); ps.appendChild(o); }
  ps.onchange = () => { if (ps.value) loadNamedConfig(ps.value, $("#profile-select"), ps); };
  const pf = $("#profile-select");
  pf.innerHTML = `<option value="">— ${L("profili standard IEEE/OIF", "IEEE/OIF standard profiles")} —</option>`;
  for (const p of (st.profiles || [])) { const o = CE("option"); o.value = p.name; o.textContent = tr(p.name); o.title = tr(p.desc); pf.appendChild(o); }
  pf.onchange = () => { if (pf.value) loadNamedConfig(pf.value, ps, pf); };
  $("#btn-run").onclick = () => POST("/api/run", { running: !S.running }).catch(e => toast(e.message));
  const anltBtn = $("#btn-anlt");
  if (anltBtn) anltBtn.onclick = async () => {
    anltBtn.disabled = true; const prev = anltBtn.textContent;
    anltBtn.textContent = "AN/LT…";
    try {
      addPanel("anlt");                       // mostra il dettaglio del protocollo
      const d = await POST("/api/experiment/anlt", { apply: true });
      const lt = d.lt;
      toast(lt.cdr_locked
        ? `AN/LT: ${d.an.resolution.hcd_name || "—"} · CDR LOCK · Q ${fix(lt.q_after, 2)} σ` +
          (d.applied ? L(" · tap applicati al banco", " · taps applied to the bench") : "")
        : L("AN/LT: training failure — nessun lock, AN riparte", "AN/LT: training failure — no lock, AN restarts"));
      const panel = S.panels.find(x => x.type === "anlt");
      if (panel && panel.el.querySelector("button.btn-accent")) flash(panel.el);
    } catch (e) { toast(e.message); }
    anltBtn.disabled = false; anltBtn.textContent = prev;
  };
  $("#btn-reset").onclick = () => POST("/api/reset").catch(e => toast(e.message));
  const expCancel = $("#exp-cancel");
  if (expCancel) {
    expCancel.textContent = L("ANNULLA", "CANCEL");
    // il tooltip arriva dal contratto experiment_cancel via decorateControls
    expCancel.onclick = () => POST("/api/experiment/cancel")
      .then(d => toast(d.cancelled
        ? L("annullamento richiesto: l'esperimento si ferma al prossimo record", "cancellation requested: the experiment stops at the next record")
        : L("nessun esperimento in corso", "no experiment running")))
      .catch(e => toast(e.message));
  }
  expBadge(st.experiment ? { state: "start", name: st.experiment } : { state: "end" });
  // export/import configurazione (file JSON versionato, stesso formato
  // della sessione persistita: version + cfg completa + camera)
  $("#btn-export").onclick = () => {
    const a = CE("a");
    a.href = "/api/config/export";
    a.download = "";           // il nome file arriva dal Content-Disposition
    document.body.appendChild(a); a.click(); a.remove();
  };
  const cfgFile = CE("input");
  cfgFile.type = "file"; cfgFile.accept = "application/json,.json";
  cfgFile.hidden = true; document.body.appendChild(cfgFile);
  $("#btn-import").onclick = () => cfgFile.click();
  cfgFile.onchange = async () => {
    const f = cfgFile.files[0];
    cfgFile.value = "";
    if (!f) return;
    try {
      const payload = JSON.parse(await f.text());
      const r = await POST("/api/config/import", payload);
      const dropped = r.dropped_fields || [];
      toast(dropped.length
        ? L(`config importata; ${dropped.length} campi non più esistenti ignorati: ${dropped.join(", ")}`,
            `config imported; ${dropped.length} obsolete fields ignored: ${dropped.join(", ")}`)
        : L("configurazione importata e applicata al banco", "configuration imported and applied to the bench"));
    } catch (e) {
      toast(e instanceof SyntaxError
        ? L("file non valido: non è un JSON del banco", "invalid file: not a bench JSON")
        : e.message);
    }
  };
  document.documentElement.lang = LANG;   // screen reader: fonetica giusta anche in EN
  $("#workspace-tabs").setAttribute("aria-label", L("Pannelli strumenti aperti", "Open instrument panels"));
  $("#workspace-empty").textContent = L(
    "Nessun pannello aperto — usa ＋ Pannello per aggiungere uno strumento.",
    "No open panels — use ＋ Panel to add an instrument.");
  $("#btn-lang").textContent = LANG === "it" ? "EN" : "IT";
  $("#btn-lang").onclick = () => { localStorage.setItem("labpro_lang", LANG === "it" ? "en" : "it"); location.reload(); };
  $("#preset-select").title = TT("carica una configurazione didattica completa", "loads a complete educational configuration");
  $("#profile-select").title = TT("carica un contesto per-lane IEEE/OIF; non equivale a compliance di clause", "loads an IEEE/OIF per-lane context; this is not clause compliance");
  $("#view-select").title = TT("cambia solo il layout delle card", "changes card layout only");
  $("#btn-add").title = TT("apre il catalogo delle card; non altera il datapath", "opens the card catalog; does not alter the datapath");
  $("#btn-reset").textContent = L("AZZERA", "RESET");
  $("#btn-add").textContent = L("＋ Pannello", "＋ Panel");
  const topLabels = [L("record", "records"), L("bit", "bits"), "BER cum.",
    L("frame FEC", "FEC frames"), L("stato", "status")];
  document.querySelectorAll(".tb-cell label").forEach((e, i) => e.textContent = topLabels[i]);
  $("#sb-note").textContent = L(
    "Laboratorio didattico con proxy dichiarati — Gardner/MM guidano il datapath; oracle resta un riferimento ideale dichiarato.",
    "Educational lab with declared proxies — Gardner/MM drive the datapath; oracle remains an explicitly ideal reference.");
  const vs = $("#view-select");
  for (const name of Object.keys(VIEWS)) { const o = CE("option"); o.value = name; o.textContent = L(name, VIEW_EN[name]); vs.appendChild(o); }
  const customView = CE("option"); customView.value = CUSTOM_VIEW;
  customView.textContent = L("Personalizzato", "Custom"); customView.disabled = true;
  vs.appendChild(customView);
  vs.onchange = () => applyView(vs.value);
  const dd = $(".dropdown");
  $("#btn-add").setAttribute("aria-haspopup", "true");
  $("#btn-add").onclick = (e) => {
    e.stopPropagation();
    const open = dd.classList.toggle("open");
    $("#btn-add").setAttribute("aria-expanded", String(open));
    if (open) setTimeout(() => {
      const f = $("#panel-menu input");
      if (f) { f.value = ""; f.oninput(); f.focus(); }
    }, 0);
  };
  document.addEventListener("click", () => { dd.classList.remove("open"); $("#btn-add").setAttribute("aria-expanded", "false"); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { dd.classList.remove("open"); $("#btn-add").setAttribute("aria-expanded", "false"); }
    // scorciatoia da strumento: R = RUN/STOP ovunque, tranne mentre l'utente
    // sta scrivendo o scegliendo un valore. Il focus su un normale bottone non
    // deve disattivare silenziosamente la shortcut.
    const editing = e.target instanceof Element
      && e.target.matches("input, textarea, select, [contenteditable='true']");
    if ((e.key === "r" || e.key === "R") && !editing
        && !e.metaKey && !e.ctrlKey && !e.altKey) {
      e.preventDefault(); $("#btn-run").click();
    }
  });
  const menu = $("#panel-menu");
  // filtro del catalogo: 34 card in lista piatta erano difficili da scandire
  const mFilter = CE("input");
  mFilter.type = "search";
  mFilter.placeholder = L("filtra pannelli…", "filter panels…");
  mFilter.setAttribute("aria-label", L("filtra pannelli", "filter panels"));
  mFilter.style.cssText = "margin:4px 6px 6px;width:calc(100% - 12px)";
  mFilter.onclick = (e) => e.stopPropagation();   // non chiudere il menu
  mFilter.oninput = () => {
    const q = mFilter.value.trim().toLowerCase();
    for (const b of menu.querySelectorAll("button"))
      b.hidden = !!q && !b.textContent.toLowerCase().includes(q);
    for (const s of menu.querySelectorAll(".menu-sec")) {
      let el = s.nextElementSibling, any = false;
      while (el && !el.classList.contains("menu-sec")) {
        if (el.tagName === "BUTTON" && !el.hidden) any = true;
        el = el.nextElementSibling;
      }
      s.hidden = !!q && !any;
    }
  };
  menu.appendChild(mFilter);
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
