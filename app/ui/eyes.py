"""Pagina eye gallery: il diagramma ad occhio a ogni piano della catena."""

from __future__ import annotations

import streamlit as st

from serdes_sim.blocks.metrics import eye_density

from .. import common, plots
from .. import theme as T
from ..state import get_cfg, run_sim

# (titolo, estrattore, dominio, unità, nota didattica)
EYE_STAGES = [
    ("Uscita driver", lambda s: s.tx.driver_voltage_v, "electrical", "V",
     "Il TX FFE è visibile come pre/de-enfasi sulle transizioni."),
    ("Uscita canale elettrico", lambda s: s.channel.electrical_waveform_v,
     "electrical", "V",
     "L'ISI del canale chiude l'occhio: confronta con il cursor plot."),
    ("Potenza ottica dopo MZM", lambda s: s.optical.P_mzm_w * 1e3, "optical", "mW",
     "La cosenoide del MZM comprime i livelli esterni: spaziature non uniformi."),
    ("Potenza ottica al PD", lambda s: s.optical.P_fiber_w * 1e3, "optical", "mW",
     "Dopo la fibra: la CD (e il chirp) deformano l'occhio in modo non simmetrico."),
    ("Uscita TIA", lambda s: s.receiver.v_tia_v, "electrical", "V",
     "Qui è entrato tutto il rumore (shot, RIN, TIA): l'occhio si 'ingrassa'."),
    ("Uscita CTLE (ingresso ADC)", lambda s: s.receiver.v_ctle_v, "electrical", "V",
     "Il CTLE riapre l'occhio pagando noise enhancement alle alte frequenze."),
]


def page_eyes():
    common.page_header("DIAGNOSTICA · EYE", "L'occhio lungo tutta la catena",
                       None, None,
                       "Sei piani di osservazione, stessa scala temporale (2 UI): "
                       "dove l'occhio si chiude e chi lo riapre.")

    cfg = get_cfg()
    sim = run_sim()
    if not common.require_link(sim):
        return

    traces = st.slider("Tracce accumulate per occhio", 200, 4000, 1500, 100,
                       help="Più tracce = densità più fedele, rendering più lento")

    for i in range(0, len(EYE_STAGES), 2):
        cols = st.columns(2)
        for col, (title, extract, domain, unit, note) in zip(cols, EYE_STAGES[i:i + 2]):
            with col:
                y = extract(sim)
                H, te, ve, _, _ = eye_density(y, cfg.analog_sps, traces=traces)
                fig = plots.eye_heatmap(
                    H, te, ve, title=title,
                    domain_color=T.DOMAIN_COLORS[domain], height=330,
                    vtitle=f"[{unit}]")
                st.plotly_chart(fig, use_container_width=True)
                st.caption(note)

    # --- dopo l'ADC non esiste più un occhio continuo -----------------------
    st.subheader("Dopo il piano A/D: da occhio a costellazione")
    st.markdown(T.note(
        "A 2 sample/UI non esiste più un occhio continuo: il DSP vede solo "
        "campioni. Da qui in poi la diagnostica giusta è l'<b>istogramma dei "
        "campioni al centro simbolo</b> e le distribuzioni per livello."),
        unsafe_allow_html=True)

    eq = sim.eq
    spec = sim.spec
    col1, col2 = st.columns(2)
    with col1:
        fig = plots.conditional_histograms(
            eq.rx_baud_norm[eq.validation_baud], eq.truth_baud[eq.validation_baud],
            spec.levels_array, title="Campioni a centro simbolo (pre-EQ)")
        # soglie calcolate SU QUESTO piano (baseline 1 sps), non sul FSE
        for t in sim.thresholds_baud[0]:
            plots.vline(fig, t, color=T.MUTED, dash="dot")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Soglie a punto medio stimate sul piano pre-EQ.")
    with col2:
        fig = plots.conditional_histograms(
            eq.dfe_output[eq.validation_fse], eq.d_fse[eq.validation_fse],
            spec.levels_array, title="Dopo FSE + DFE (con soglie di decisione)")
        # soglie del piano DFE (statistiche post-DFE, non del FSE)
        for t in sim.thresholds_dfe[0]:
            plots.vline(fig, t, color=T.MUTED, dash="dot")
        for t in sim.thresholds_dfe[1]:
            plots.vline(fig, t, color=T.GREEN_OK, dash="dash")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Soglie stimate sul piano post-DFE. Grigio: punto medio; "
                   "verde: calibrata pesata sulle σ (proxy del crossing di "
                   "likelihood). NOTA: la BER riportata usa lo slicer a "
                   "livelli nominali, non queste soglie.")
