"""Spectrum analyzer: PSD Welch di ogni nodo della catena, con finestra,
RBW ed ENBW dichiarate, unità corrette per piano e confronto col noise budget."""

from __future__ import annotations

import numpy as np
import streamlit as st
from scipy import signal as sp_signal

from serdes_sim.utils import butterworth_magnitude, db10

from .. import common, plots
from .. import theme as T
from ..state import get_cfg, run_sim

# nodo -> (estrattore, dominio, unità PSD, sample-rate-key, nota)
SPECTRUM_NODES = {
    "Uscita driver": (lambda s: s.tx.driver_voltage_v, "electrical",
                      "V²/Hz", "analog", "spettro dati + pre-enfasi FFE"),
    "Uscita canale elettrico": (lambda s: s.channel.electrical_waveform_v,
                                "electrical", "V²/Hz", "analog",
                                "il canale scava le alte frequenze"),
    "Potenza ottica dopo MZM": (lambda s: s.optical.P_mzm_w, "optical",
                                "W²/Hz", "analog",
                                "PSD della potenza istantanea P(t), non del campo"),
    "Potenza ottica al PD": (lambda s: s.optical.P_fiber_w, "optical",
                             "W²/Hz", "analog",
                             "il fading CD scolpisce lo spettro di P(t)"),
    "Fotocorrente + rumori (pre-TIA)": (lambda s: s.receiver.i_pd_noisy_a,
                                        "electrical", "A²/Hz", "analog",
                                        "qui i rumori sono ancora bianchi"),
    "Uscita TIA": (lambda s: s.receiver.v_tia_v, "electrical", "V²/Hz",
                   "analog", "confrontala col floor previsto dal noise budget"),
    "Uscita CTLE": (lambda s: s.receiver.v_ctle_v, "electrical", "V²/Hz",
                    "analog", "il peaking rialza segnale E rumore"),
    "Campioni ADC": (lambda s: s.adc.adc_samples_v, "digital", "V²/Hz",
                     "adc", "fs = 2×baud: guarda le righe k·fs/M dell'interleave"),
}


def _welch_psd(x, fs_hz, nperseg):
    f, psd = sp_signal.welch(np.asarray(x, dtype=float), fs=fs_hz,
                             window="hann", nperseg=nperseg,
                             noverlap=nperseg // 2, detrend="constant",
                             scaling="density")
    return f, psd


def page_spectrum():
    common.page_header("DIAGNOSTICA · SPETTRO", "Spectrum analyzer",
                       None, None,
                       "PSD Welch su qualunque nodo, con finestra e RBW "
                       "dichiarate — e il confronto misurato-vs-budget che uno "
                       "spettro dati da solo non può dare.")

    cfg = get_cfg()
    sim = run_sim()

    c1, c2, c3 = st.columns([1.6, 1.4, 1])
    with c1:
        node_name = st.selectbox("Nodo", list(SPECTRUM_NODES.keys()),
                                 index=5)
    with c2:
        overlay_name = st.selectbox(
            "Overlay (opzionale)", ["nessuno"] + list(SPECTRUM_NODES.keys()))
    with c3:
        nperseg = st.select_slider("N per segmento (Welch)",
                                   [1024, 2048, 4096, 8192], 4096)

    extract, domain, unit, rate_key, note = SPECTRUM_NODES[node_name]
    x = extract(sim)
    fs = cfg.fs_analog_hz if rate_key == "analog" else cfg.fs_adc_hz
    f, psd = _welch_psd(x, fs, min(nperseg, len(x) // 4))

    # RBW/ENBW della finestra Hann: ENBW = 1.5 bin
    bin_hz = fs / min(nperseg, len(x) // 4)
    rbw_hz = 1.5 * bin_hz
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Sample rate", f"{fs / 1e9:.1f} GSa/s")
    m2.metric("RBW (Hann)", f"{rbw_hz / 1e6:.1f} MHz",
              help="Resolution bandwidth = ENBW della finestra × fs/nperseg; "
                   "per Hann ENBW = 1.5 bin. Ogni PSD è media di segmenti "
                   "sovrapposti al 50% (Welch).")
    m3.metric("Segmenti mediati", f"{max(1, 2 * len(x) // nperseg - 1)}")
    m4.metric("Unità", unit,
              help="PSD one-sided in unità²/Hz del piano osservato: V²/Hz "
                   "elettrico, A²/Hz fotocorrente, W²/Hz per la potenza "
                   "ottica istantanea (non è OSNR: quella è un'altra misura).")

    traces = [dict(x=f / 1e9, y=db10(np.maximum(psd, 1e-30)),
                   name=node_name, color=T.DOMAIN_COLORS[domain], width=1.6)]

    if overlay_name != "nessuno":
        o_extract, o_domain, o_unit, o_rate, _ = SPECTRUM_NODES[overlay_name]
        xo = o_extract(sim)
        fso = cfg.fs_analog_hz if o_rate == "analog" else cfg.fs_adc_hz
        fo, psdo = _welch_psd(xo, fso, min(nperseg, len(xo) // 4))
        traces.append(dict(x=fo / 1e9, y=db10(np.maximum(psdo, 1e-30)),
                           name=f"{overlay_name} [{o_unit}]",
                           color=T.MUTED, width=1.2, dash="dot"))

    # confronto col budget: floor previsto all'uscita TIA
    if node_name == "Uscita TIA":
        rx = sim.receiver
        S_total = rx.S_shot_a2_hz + rx.S_tia_a2_hz + rx.S_rin_a2_hz
        model = (S_total * cfg.tia_transimpedance_ohm ** 2
                 * butterworth_magnitude(f, cfg.tia_bw_hz, 3) ** 2
                 * sim.receiver.agc_gain ** 0)  # piano TIA, prima dell'AGC
        traces.append(dict(x=f / 1e9, y=db10(np.maximum(model, 1e-30)),
                           name="floor previsto dal noise budget",
                           color=T.AMBER, width=2.0, dash="dash"))

    fig = plots.line_fig(traces, xtitle="Frequenza [GHz]",
                         ytitle=f"PSD [dB rel. 1 {unit}]",
                         height=430)
    plots.vline(fig, cfg.nyquist_hz / 1e9, label="Nyquist dati")
    if rate_key == "adc":
        for k in range(1, cfg.adc_interleaves // 2 + 1):
            plots.vline(fig, k * cfg.fs_adc_hz / cfg.adc_interleaves / 1e9,
                        color=T.RED_FAIL, dash="dot", label="k·fs/M")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(note)

    if node_name == "Uscita TIA":
        st.markdown(T.note(
            "Sopra la banda del segnale la PSD misurata deve adagiarsi sul "
            "<b>floor previsto</b> (S_shot+S_TIA+S_RIN)·Z_T²·|H_TIA|²: se non "
            "coincide, o il budget è sbagliato o c'è una sorgente non "
            "modellata. È il controllo di coerenza più potente di questa "
            "pagina."), unsafe_allow_html=True)
    st.markdown(T.warn(
        "Limiti dichiarati: PSD di un record finito (~8k UI), niente "
        "spettrogramma né cross-spectrum/coherence per ora; l'estensione è "
        "nel piano di lavoro (HANDOFF)."), unsafe_allow_html=True)
