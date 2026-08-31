"""Pagine lato TX: stimolo PRBS/PAM4, TX elettrico (FFE/DAC/driver), canale."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from serdes_sim.blocks.channel import parse_touchstone_s2p_text, sparameter_diagnostics, DEMO_S2P
from serdes_sim.blocks.stimulus import PRBS_POLY_LABEL
from serdes_sim.utils import db20

from .. import common, content, plots
from .. import theme as T
from ..state import (get_cfg, set_cfg, run_sim, param_slider, param_int_slider,
                     param_select, ffe_taps_widget)


# ---------------------------------------------------------------------------
# Stimolo
# ---------------------------------------------------------------------------

def page_stimulus():
    common.page_header("STADIO 01 · STIMOLO", "PRBS13Q-style e PAM4", "digital",
                       "stimulus", "Un pattern con istogramma giusto non è ancora "
                       "uno stimulus stressante: contano transizioni e run length.")
    cfg = get_cfg()
    with st.expander("Teoria — rate, PRBS e statistica BER", expanded=False):
        st.markdown(content.STIMULUS_THEORY)

    with st.container(border=True):
        st.markdown("**Parametri**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            param_slider("Baud rate [GBd]", "symbol_rate_hz", 20.0, 120.0, 0.125,
                         scale=1e9, help="56 GBd ⇒ 112 Gb/s raw PAM4")
        with c2:
            param_select("PRBS", "prbs_order", [7, 9, 11, 13, 15, 23, 31],
                         format_func=lambda o: f"PRBS{o} · {PRBS_POLY_LABEL[o]}",
                         help="PRBS13 con periodo 8191 è lo standard PAM4 112G")
        with c3:
            param_select("Modulazione", "modulation", ["PAM4", "NRZ"])
        with c4:
            if get_cfg().modulation == "PAM4":
                param_select("Mapping PAM4", "pam4_mapping", ["gray", "binary"],
                             format_func=lambda m: "Gray (00·01·11·10)"
                             if m == "gray" else "binario (00·01·10·11)",
                             help="Con Gray un errore fra livelli adiacenti "
                                  "costa 1 solo bit")
    cfg = get_cfg()
    sim = run_sim()
    spec = sim.spec
    bps = spec.bits_per_symbol

    rates = pd.DataFrame({
        "grandezza": ["Baud rate", f"Bit rate raw {spec.name}", "UI", "Nyquist",
                      "bit/simbolo", "pattern"],
        "valore": [f"{cfg.symbol_rate_hz / 1e9:.3f} GBd",
                   f"{bps * cfg.symbol_rate_hz / 1e9:.2f} Gb/s",
                   f"{cfg.ui_s * 1e12:.3f} ps",
                   f"{cfg.nyquist_hz / 1e9:.3f} GHz",
                   str(bps),
                   f"PRBS{cfg.prbs_order} · {PRBS_POLY_LABEL[cfg.prbs_order]}"],
    })
    st.dataframe(rates, use_container_width=True, hide_index=True)

    levels = spec.levels_array
    col1, col2 = st.columns(2)
    with col1:
        n = 64
        fig = plots.line_fig(
            [dict(x=np.arange(n), y=sim.pam4_symbols[:n], color=T.DIGITAL,
                  shape="hv", width=1.8)],
            title=f"Primi 64 simboli ({spec.label})", xtitle="Indice simbolo",
            ytitle="Livello")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = plots.bar_fig([f"{v:+.3f}" for v in levels], sim.occupancy,
                            title=f"Occupazione dei {len(levels)} livelli",
                            xtitle=f"Livello {spec.name}",
                            ytitle="Occorrenze", color=T.DIGITAL,
                            text=[str(v) for v in sim.occupancy])
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Matrice di transizione")
    labels = [f"{v:+.2f}" for v in levels]
    fig = plots.heat_fig(sim.transition_probability, labels, labels,
                         xtitle="verso livello", ytitle="da livello",
                         colorscale=[[0, T.PANEL], [1, T.DIGITAL]], height=340,
                         colorbar_title="P")
    st.plotly_chart(fig, use_container_width=True)
    st.markdown(T.note(
        "Con N bit e <b>zero errori</b>, l'upper bound al 95% è ≈ 3/N: "
        f"con i {bps * cfg.n_symbols} bit di questo record non puoi dimostrare "
        f"BER migliori di ≈ {3 / (bps * cfg.n_symbols):.1e}."), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# TX elettrico
# ---------------------------------------------------------------------------

def page_tx():
    common.page_header("STADIO 02 · TX ELETTRICO", "TX FFE, DAC e driver",
                       "electrical", "txffe",
                       "La pre-enfasi non crea SNR: sposta energia in frequenza "
                       "pagando headroom nel DAC e nel driver.")
    with st.expander("Teoria — FFE, quantizzazione, clipping"):
        st.markdown(content.TX_THEORY)

    with st.container(border=True):
        st.markdown("**TX FFE**")
        ffe_taps_widget()
        c1, c2, c3 = st.columns(3)
        with c1:
            param_int_slider("Bit DAC", "dac_bits", 4, 10)
        with c2:
            param_slider("Banda DAC [GHz]", "dac_bw_hz", 15.0, 60.0, 1.0, scale=1e9)
        with c3:
            param_slider("Banda driver [GHz]", "driver_bw_hz", 15.0, 60.0, 1.0, scale=1e9)
        c4, c5, c6 = st.columns(3)
        with c4:
            param_slider("Full scale DAC [Vpp]", "dac_full_scale_vpp", 1.0, 4.0, 0.1)
        with c5:
            param_slider("Guadagno driver [V/unit]", "driver_gain_v_per_unit",
                         0.2, 1.5, 0.05)
        with c6:
            param_slider("Rail driver [±V]", "driver_clip_v", 0.3, 1.5, 0.05)

    cfg = get_cfg()
    sim = run_sim()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Costo di picco FFE", f"{sim.tx.swing_cost:.2f}×")
    m2.metric("LSB DAC", f"{sim.tx.dac_lsb * 1e3:.2f} m")
    m3.metric("Clipping DAC", f"{100 * sim.tx.dac_clip_fraction:.3f} %")
    m4.metric("Clipping driver", f"{100 * sim.tx.driver_clip_fraction:.3f} %")

    col1, col2 = st.columns(2)
    with col1:
        n = 42
        fig = plots.line_fig(
            [dict(x=np.arange(n), y=sim.pam4_symbols[:n], name="PAM4",
                  color=T.MUTED, shape="hv", width=1.4),
             dict(x=np.arange(n), y=sim.tx.tx_ffe_symbols[:n], name="dopo FFE",
                  color=T.DIGITAL, shape="hv", width=1.8)],
            title="Costo di swing della pre-enfasi", xtitle="Simbolo",
            ytitle="Ampiezza")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = plots.line_fig(
            [dict(x=sim.tx.ffe_freq_norm, y=db20(sim.tx.ffe_response),
                  color=T.DIGITAL)],
            title="Risposta in frequenza TX FFE", xtitle="f / Nyquist",
            ytitle="|H| [dB]")
        st.plotly_chart(fig, use_container_width=True)

    n_show = 10 * cfg.analog_sps
    t_ps = np.arange(n_show) / cfg.fs_analog_hz * 1e12
    col3, col4 = st.columns(2)
    with col3:
        fig = plots.line_fig(
            [dict(x=t_ps, y=sim.tx.dac_zoh[:n_show], name="ZOH", color=T.MUTED,
                  width=1.2),
             dict(x=t_ps, y=sim.tx.dac_quantized[:n_show], name="quantizzato",
                  color=T.AMBER, width=1.2, opacity=0.8),
             dict(x=t_ps, y=sim.tx.dac_waveform[:n_show], name="dopo banda",
                  color=T.ELECTRICAL, width=2.2)],
            title="DAC: le tre trasformazioni separate", xtitle="Tempo [ps]",
            ytitle="Ampiezza")
        st.plotly_chart(fig, use_container_width=True)
    with col4:
        fig = plots.line_fig(
            [dict(x=t_ps, y=sim.tx.driver_filtered_v[:n_show], name="lineare",
                  color=T.MUTED, width=1.4),
             dict(x=t_ps, y=sim.tx.driver_voltage_v[:n_show], name="uscita",
                  color=T.ELECTRICAL, width=2.0)],
            title="Driver e rail", xtitle="Tempo [ps]", ytitle="Tensione [V]")
        plots.hline(fig, get_cfg().driver_clip_v, color=T.RED_FAIL, label="+rail")
        plots.hline(fig, -get_cfg().driver_clip_v, color=T.RED_FAIL, label="−rail")
        st.plotly_chart(fig, use_container_width=True)
    st.markdown(T.warn("Il clipping è <b>non invertibile</b>: nessun equalizzatore "
                       "a valle ricostruisce i picchi tagliati dalle rail."),
                unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Canale elettrico
# ---------------------------------------------------------------------------

def page_channel():
    common.page_header("STADIO 03 · CANALE ELETTRICO", "S21, pulse response e ISI",
                       "electrical", "channel",
                       "Dallo spettro S(f) alla pulse response p(t): i cursor a "
                       "distanza intera di UI sono l'ISI che il DSP dovrà pagare.")
    with st.expander("Teoria — perdite, eco, cursor"):
        st.markdown(content.CHANNEL_THEORY)
    with st.expander("Esercizio guidato A"):
        st.markdown(content.EXERCISE_A)

    with st.container(border=True):
        st.markdown("**Parametri del canale analitico**")
        c1, c2, c3 = st.columns(3)
        with c1:
            param_slider("IL @ Nyquist [dB]", "channel_il_nyquist_db", 2.0, 28.0, 0.5)
        with c2:
            param_slider("Return loss [dB]", "return_loss_db", 6.0, 30.0, 1.0,
                         help="Più basso = eco più forte")
        with c3:
            param_slider("Ritardo eco [UI]", "echo_delay_ui", 0.2, 4.0, 0.05)
        c4, c5 = st.columns(3)[:2]
        with c4:
            param_slider("Ritardo canale [ps]", "channel_delay_ps", 0.0, 60.0, 1.0)
        with c5:
            param_slider("Ripple group delay [ps]", "group_delay_ripple_ps",
                         0.0, 5.0, 0.1)

    cfg = get_cfg()
    sim = run_sim()

    if cfg.use_s2p_channel:
        st.markdown(T.note(
            f"<b>Canale attivo: {sim.channel.source}</b> — i parametri del "
            "modello analitico qui sopra sono ignorati finché l'S2P è attivo."),
            unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        mask = (sim.channel.f_fft_hz >= 0) & (sim.channel.f_fft_hz <= 1.35 * cfg.nyquist_hz)
        fig = plots.line_fig(
            [dict(x=sim.channel.f_fft_hz[mask] / 1e9,
                  y=db20(sim.channel.H_electrical[mask]), color=T.ELECTRICAL)],
            title=f"Canale elettrico |S21| — {sim.channel.source}",
            xtitle="Frequenza [GHz]", ytitle="|H| [dB]")
        plots.vline(fig, cfg.nyquist_hz / 1e9, label="Nyquist")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Il ripple periodico è l'eco del mismatch: nel dominio del "
                   "tempo diventa un cursore isolato, non un droop.")
    with col2:
        n_show = 10 * cfg.analog_sps
        t_ps = np.arange(n_show) / cfg.fs_analog_hz * 1e12
        fig = plots.line_fig(
            [dict(x=t_ps, y=sim.tx.driver_voltage_v[:n_show], name="ingresso",
                  color=T.MUTED, width=1.4),
             dict(x=t_ps, y=sim.channel.electrical_waveform_v[:n_show],
                  name="uscita", color=T.ELECTRICAL, width=2.0)],
            title="Distorsione della waveform", xtitle="Tempo [ps]", ytitle="V")
        st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        fig = plots.line_fig(
            [dict(x=sim.channel.pulse_time_ui, y=sim.channel.pulse_normalized,
                  color=T.ELECTRICAL, width=2.0)],
            title="Pulse response (1 UI)", xtitle="Tempo dal main [UI]",
            ytitle="Ampiezza normalizzata")
        plots.vline(fig, 0)
        st.plotly_chart(fig, use_container_width=True)
    with col4:
        fig = plots.stem_fig(sim.channel.cursor_ui, sim.channel.cursor_values,
                             title="Cursor plot p[k]/p[0]", xtitle="Cursor [UI]",
                             ytitle="Ampiezza relativa", color=T.ELECTRICAL)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Precursor: solo il FFE TX (o FSE) può toccarli. Postcursor: "
                   "territorio del DFE.")

    st.subheader("Import Touchstone S2P")
    st.markdown("Carica un file `.s2p` misurato: il parser (Touchstone 1.x, "
                "RI/MA/DB) esegue la checklist di qualità — passività, "
                "reciprocità, group delay, griglia — e può **sostituire il "
                "canale analitico nel percorso principale**.")
    uploaded = st.file_uploader("File S2P", type=["s2p", "S2P", "txt"],
                                label_visibility="collapsed")
    text = uploaded.read().decode("utf-8", errors="replace") if uploaded else DEMO_S2P
    file_name = uploaded.name if uploaded else "demo interno"
    try:
        f_s2p, S, z0 = parse_touchstone_s2p_text(text)
        diag = sparameter_diagnostics(f_s2p, S)
        c1, c2 = st.columns([1, 1.3])
        with c1:
            st.dataframe(diag.to_frame("valore"), use_container_width=True)
            st.caption(f"Z₀ = {z0:g} Ω · {len(f_s2p)} punti · {file_name}")
            try:
                import skrf  # noqa: F401
                st.caption("scikit-rf disponibile per validazioni avanzate "
                           "(mixed-mode, Touchstone 2.x) — vedi pagina "
                           "Realismo e pacchetti.")
            except ImportError:
                pass
        with c2:
            fig = plots.line_fig(
                [dict(x=f_s2p / 1e9, y=db20(np.abs(S[:, 1, 0])), name="S21",
                      color=T.ELECTRICAL),
                 dict(x=f_s2p / 1e9, y=db20(np.abs(S[:, 0, 0])), name="S11",
                      color=T.AMBER, dash="dot")],
                title="S21 / S11 dal file", xtitle="Frequenza [GHz]",
                ytitle="[dB]")
            st.plotly_chart(fig, use_container_width=True)

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Usa questo S2P come canale del percorso principale",
                         type="primary", use_container_width=True):
                set_cfg(get_cfg().with_updates(
                    s2p_text=text, s2p_name=file_name, use_s2p_channel=True))
                st.rerun()
        with b2:
            if st.button("Torna al modello analitico", use_container_width=True,
                         disabled=not cfg.use_s2p_channel):
                set_cfg(get_cfg().with_updates(use_s2p_channel=False))
                st.rerun()
        st.markdown(T.warn(
            "Ricostruzione dichiarata quando l'S2P è attivo: magnitudine "
            "interpolata con hold a DC e oltre f_max; fase 0 a DC ed "
            "estrapolata col group delay dell'ultimo tratto; simmetria "
            "Hermitiana. Non è un de-embedding: reference plane, Z₀ e "
            "calibrazione restano responsabilità di chi ha misurato."),
            unsafe_allow_html=True)
    except Exception as exc:
        st.error(f"S2P non leggibile: {exc}")
