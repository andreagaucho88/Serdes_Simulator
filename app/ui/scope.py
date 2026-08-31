"""Scope live: acquisizione animata stile oscilloscopio a persistenza.

Le tracce sono dati reali del motore (con il rumore della run); il rendering
è un canvas HTML5 che accumula le tracce come il fosforo di uno scope, a
60 fps nel browser — Streamlit fa solo da contenitore, quindi l'animazione
è fluida anche se il server non fa nulla.
"""

from __future__ import annotations

import json

import numpy as np
import streamlit as st
import streamlit.components.v1 as components

from serdes_sim import simulate

from .. import common
from .. import theme as T
from ..state import get_cfg

NODES = {
    "Uscita CTLE (ingresso ADC)": ("v_ctle", "electrical", "V"),
    "Uscita TIA (con rumore)": ("v_tia", "electrical", "V"),
    "Potenza ottica al PD": ("p_fiber", "optical", "mW"),
    "Uscita canale elettrico": ("chan", "electrical", "V"),
    "Uscita driver": ("driver", "electrical", "V"),
}


def _get_wave(sim, key):
    if key == "v_ctle":
        return sim.receiver.v_ctle_v
    if key == "v_tia":
        return sim.receiver.v_tia_v
    if key == "p_fiber":
        return sim.optical.P_fiber_w * 1e3
    if key == "chan":
        return sim.channel.electrical_waveform_v
    return sim.tx.driver_voltage_v


def _scope_html(traces, color, unit, mode, ui_per_div):
    data = json.dumps(np.round(np.asarray(traces), 5).tolist())
    return f"""
<div id="scope-wrap" style="font-family:'IBM Plex Mono',monospace;background:#05080C;
     border:1px solid {T.GRID};border-radius:10px;padding:10px 12px;">
  <div style="display:flex;justify-content:space-between;align-items:center;
       color:{T.MUTED};font-size:11px;margin-bottom:6px;">
    <span style="color:{color};">● ACQ RUNNING</span>
    <span id="readout">redraw: 0</span>
    <span>
      persist <input id="persist" type="range" min="1" max="30" value="8"
        style="width:70px;vertical-align:middle;">
      rate <input id="rate" type="range" min="1" max="40" value="12"
        style="width:70px;vertical-align:middle;">
      <button id="pause" style="background:none;border:1px solid {T.GRID};
        color:{T.INK};border-radius:4px;cursor:pointer;font-family:inherit;
        font-size:11px;padding:1px 8px;">⏸</button>
    </span>
  </div>
  <canvas id="scope" width="1100" height="430" style="width:100%;display:block;"></canvas>
  <div style="color:{T.MUTED};font-size:10.5px;margin-top:4px;">
    {ui_per_div} · verticale: {unit} · le tracce sono dati simulati reali,
    accumulati con persistenza tipo fosforo</div>
</div>
<script>
const traces = {data};
const mode = "{mode}";
const cv = document.getElementById("scope");
const ctx = cv.getContext("2d");
const W = cv.width, H = cv.height;
let vmin = Infinity, vmax = -Infinity;
for (const tr of traces) for (const v of tr) {{
  if (v < vmin) vmin = v; if (v > vmax) vmax = v; }}
const pad = 0.12 * (vmax - vmin || 1);
vmin -= pad; vmax += pad;
const y = v => H - (v - vmin) / (vmax - vmin) * H;

function grid() {{
  ctx.fillStyle = "#05080C"; ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = "rgba(140,161,175,0.16)"; ctx.lineWidth = 1;
  ctx.setLineDash([2, 5]);
  for (let i = 1; i < 10; i++) {{
    ctx.beginPath(); ctx.moveTo(W * i / 10, 0); ctx.lineTo(W * i / 10, H); ctx.stroke();
  }}
  for (let j = 1; j < 8; j++) {{
    ctx.beginPath(); ctx.moveTo(0, H * j / 8); ctx.lineTo(W, H * j / 8); ctx.stroke();
  }}
  ctx.setLineDash([]);
}}
grid();

let idx = 0, count = 0, paused = false, offset = 0;
document.getElementById("pause").onclick = e => {{
  paused = !paused; e.target.textContent = paused ? "▶" : "⏸";
  document.querySelector("#scope-wrap span").textContent =
      paused ? "○ ACQ STOPPED" : "● ACQ RUNNING";
}};

function drawTrace(tr) {{
  ctx.beginPath();
  const n = tr.length;
  for (let i = 0; i < n; i++) {{
    const x = W * i / (n - 1);
    if (i === 0) ctx.moveTo(x, y(tr[i])); else ctx.lineTo(x, y(tr[i]));
  }}
  ctx.stroke();
}}

function frame() {{
  if (!paused) {{
    const decay = document.getElementById("persist").value;
    const rate = +document.getElementById("rate").value;
    // dissolvenza del fosforo
    ctx.fillStyle = `rgba(5,8,12,${{1.8 / decay}})`;
    ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = "lighter";
    ctx.strokeStyle = "{color}";
    ctx.lineWidth = 1.1;
    ctx.globalAlpha = 0.16;
    if (mode === "eye") {{
      for (let k = 0; k < rate; k++) {{
        drawTrace(traces[idx]);
        idx = (idx + 1) % traces.length;
        count++;
      }}
    }} else {{
      // roll: finestra scorrevole sul record continuo
      const rec = traces[0];
      const win = 900;
      offset = (offset + rate * 3) % (rec.length - win);
      ctx.globalAlpha = 0.9;
      grid();
      ctx.strokeStyle = "{color}";
      drawTrace(rec.slice(offset, offset + win));
      count += rate;
    }}
    ctx.globalAlpha = 1.0;
    ctx.globalCompositeOperation = "source-over";
    // graticolo sopra, leggero
    ctx.strokeStyle = "rgba(140,161,175,0.10)";
    ctx.strokeRect(0, 0, W, H);
    document.getElementById("readout").textContent =
        "redraw: " + count.toLocaleString() +
        " (buffer " + traces.length + " tracce reali)";
  }}
  requestAnimationFrame(frame);
}}
requestAnimationFrame(frame);
</script>
"""


def _readout_rows(rows):
    """Pannello misure stile DCA: label a sinistra, valore mono a destra."""
    html = [f'<div style="background:#05080C;border:1px solid {T.GRID};'
            'border-radius:10px;padding:10px 14px;">']
    for label, value, accent in rows:
        if label == "---":
            html.append(f'<hr style="border-color:{T.GRID};margin:6px 0;">')
            continue
        color = accent or T.INK
        html.append(
            f'<div style="display:flex;justify-content:space-between;'
            f'margin:3px 0;font-size:0.82rem;">'
            f'<span style="color:{T.MUTED};">{label}</span>'
            f'<span style="font-family:{T.FONT_MONO};color:{color};">{value}'
            f'</span></div>')
    html.append("</div>")
    return "".join(html)


def _render_dca(cfg, seed, node_name, mode, n_traces):
    key, domain, unit = NODES[node_name]
    with st.spinner("Acquisizione…"):
        sim = _scope_sim(json.dumps(cfg.to_dict()), seed)
    if not sim.link_up:
        st.error("LINK DOWN — nessuna misura: CDR/pattern lock non agganciano.")
        return
    wave = _get_wave(sim, key)
    color = T.DOMAIN_COLORS[domain]

    col_scope, col_meas = st.columns([2.1, 1])
    with col_scope:
        if mode == "eye":
            sps = cfg.analog_sps
            rows = []
            start = 80
            for k in range(start, min(len(wave) // sps - 2, start + n_traces)):
                center = k * sps + sps // 2
                rows.append(wave[center - sps:center + sps])
            html = _scope_html(np.asarray(rows), color, unit, "eye",
                               "orizzontale: 2 UI (0.2 UI/div)")
        else:
            html = _scope_html(wave[:24000][None, :], color, unit, "roll",
                               "orizzontale: scorrimento continuo del record")
        components.html(html, height=520)

    with col_meas:
        # misure sul nodo visualizzato (unità del nodo, non sempre volt)
        pp_label = "V_pp" if unit == "V" else f"ampiezza pk-pk [{unit}]"
        rows = [("MISURE SUL NODO", "", None),
                (pp_label, f"{np.max(wave) - np.min(wave):.4g} {unit}", None),
                ("RMS (AC)", f"{np.std(wave):.4g} {unit}", None),
                ("media", f"{np.mean(wave):.4g} {unit}", None)]
        if key == "p_fiber":
            ol = sim.optical_levels
            rows += [("OMA outer (proxy)", f"{1e3 * ol['oma_outer_w']:.3f} mW",
                      T.OPTICAL),
                     ("ER (proxy)", f"{ol['extinction_ratio_db']:.2f} dB",
                      T.OPTICAL)]
        # analisi di link al piano di decisione
        snr = sim.snr_dfe
        ber = sim.ber_post_dfe
        n_fail = sum(1 for ck in sim.checks if ck["status"] == "FAIL")
        rows += [("---", "", None),
                 ("LINK (slicer)", "", None),
                 ("timing", "acquisition supervisionata", T.AMBER),
                 ("BER contata", f"{ber:.2e}",
                  T.GREEN_OK if ber < 2.4e-4 else T.AMBER),
                 ("SNR slicer", f"{snr['snr_slicer_db']:.2f} dB", None),
                 ("Q minimo", f"{snr['q_min']:.2f}", None),
                 ("GMI", f"{sim.gmi_total:.3f}/{sim.spec.bits_per_symbol}", None),
                 ("checkpoint", f"{n_fail} FAIL" if n_fail else "tutti PASS",
                  T.RED_FAIL if n_fail else T.GREEN_OK)]
        # analisi FEC: verdetto solo con dati sufficienti e coerenti
        fa = sim.fec
        model_ok = fa.fer_iid_model_qmeas < 1e-13
        record_ok = fa.n_frames > 0 and fa.frames_uncorrectable == 0
        insufficient = fa.n_frames < 1 or (model_ok and fa.symbol_errors < 1
                                           and fa.n_symbols_10b < 100_000)
        if insufficient:
            verdict, vcolor = "DATI INSUFFICIENTI", T.AMBER
        elif model_ok and record_ok:
            verdict, vcolor = "LINK OK con FEC (modello iid)", T.GREEN_OK
        elif not model_ok:
            verdict, vcolor = "FEC INSUFFICIENTE", T.RED_FAIL
        else:
            verdict, vcolor = "FRAME PERSI NEL RECORD", T.RED_FAIL
        rows += [("---", "", None),
                 ("ANALISI FEC RS(544,514)", "", None),
                 ("pre-FEC BER", f"{fa.pre_fec_ber:.2e}", None),
                 ("SER simboli 10b", f"{fa.symbol_error_rate:.2e}", None),
                 ("FER modello iid", f"{fa.fer_iid_model_qmeas:.1e}",
                  T.GREEN_OK if model_ok else T.RED_FAIL),
                 ("frame nel record",
                  f"{fa.frames_uncorrectable}/{fa.n_frames} persi"
                  if fa.n_frames else "0 frame completi",
                  (T.GREEN_OK if fa.frames_uncorrectable == 0 else T.RED_FAIL)
                  if fa.n_frames else T.AMBER),
                 ("burstiness", f"{fa.burstiness_ratio:.2f}", None),
                 ("verdetto", verdict, vcolor)]
        st.markdown(_readout_rows(rows), unsafe_allow_html=True)
        st.caption(f"acq #{seed - 20240731} · seed {seed} · il verdetto FEC "
                   "estrapola dal modello binomiale iid: con record corto o "
                   "burst va letto come indicazione, non come misura")


def page_scope():
    common.page_header("DIAGNOSTICA · SCOPE LIVE", "DCA: acquisizione e analisi",
                       None, None,
                       "Come un communication analyzer: fosforo live a sinistra, "
                       "misure e analisi FEC a destra. Ogni parametro cambiato "
                       "in qualunque pagina si riflette qui.")

    cfg = get_cfg()
    c1, c2, c3, c4, c5 = st.columns([1.6, 1, 1, 1, 1])
    with c1:
        node_name = st.selectbox("Nodo osservato", list(NODES.keys()))
    with c2:
        mode = st.radio("Modalità", ["eye", "roll"], horizontal=True,
                        help="eye: tracce sovrapposte a 2 UI; roll: scorrimento "
                             "continuo del record")
    with c3:
        n_traces = st.slider("Tracce nel buffer", 100, 2000, 600, 50)
    with c4:
        if st.button("Nuova acquisizione", use_container_width=True,
                     help="Nuova realizzazione di rumore/jitter (nuovo seed)"):
            st.session_state["scope_seed"] = \
                st.session_state.get("scope_seed", 20240731) + 1
    with c5:
        live = st.toggle("Acquisizione continua",
                         help="Nuova acquisizione automatica ogni 5 s "
                              "(nuovo rumore, stessa configurazione)")

    if live:
        @st.fragment(run_every="5s")
        def _live_fragment():
            # riflette anche le modifiche fatte da UN'ALTRA tab: ogni tab
            # Streamlit è una sessione separata, quindi rileggiamo la config
            # persistita a ogni acquisizione
            from ..state import reload_cfg_from_disk
            reload_cfg_from_disk()
            st.session_state["scope_seed"] = \
                st.session_state.get("scope_seed", 20240731) + 1
            _render_dca(get_cfg(), st.session_state["scope_seed"],
                        node_name, mode, n_traces)
        _live_fragment()
    else:
        _render_dca(cfg, st.session_state.get("scope_seed", 20240731),
                    node_name, mode, n_traces)

    st.caption("Le misure di link e FEC sono calcolate al piano di decisione "
               "sull'acquisizione corrente (stessa fisica end-to-end della "
               "catena, nuovo rumore a ogni acquisizione). I controlli "
               "persist/rate agiscono solo sul rendering.")


@st.cache_resource(show_spinner=False, max_entries=6)
def _scope_sim(cfg_json: str, seed: int):
    from serdes_sim import LinkConfig
    payload = json.loads(cfg_json)
    payload["tx_ffe_taps"] = tuple(payload["tx_ffe_taps"])
    return simulate(LinkConfig(**payload), seed=seed, depth="light")
