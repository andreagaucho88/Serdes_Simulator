"""Pagine ricevitore: PD + noise + TIA + CTLE, ADC interleaved."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from serdes_sim.blocks.metrics import eye_density
from serdes_sim.utils import db20

from .. import common, content, diagrams, plots
from .. import theme as T
from ..state import get_cfg, run_sim, param_slider, param_int_slider


def page_receiver():
    common.page_header("STADIO 06 · RICEVITORE OTTICO", "PD, rumore, TIA e CTLE",
                       "electrical", "tia",
                       "Il piano O/E è irreversibile: dopo lo square-law la fase "
                       "ottica non esiste più. Qui entra anche tutto il rumore.")
    with st.expander("Teoria — square-law, noise budget, ENBW, CTLE"):
        st.markdown(content.RX_THEORY)
        st.markdown(diagrams.pd_tia_schematic(), unsafe_allow_html=True)
        st.markdown(diagrams.ctle_schematic(), unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("**Parametri PD / TIA / AGC**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            param_slider("Responsivity [A/W]", "pd_responsivity_a_w", 0.3, 1.1, 0.05)
        with c2:
            param_slider("Banda PD [GHz]", "pd_bw_hz", 20.0, 70.0, 1.0, scale=1e9)
        c1b, c2b = st.columns(4)[:2]
        with c1b:
            param_slider("Dark current [nA]", "pd_dark_current_a", 0.0, 100.0,
                         1.0, scale=1e-9,
                         help="Somma alla fotocorrente ed entra nello shot noise")
        with c2b:
            param_slider("Saturazione PD [mA]", "pd_saturation_a", 0.05, 3.0,
                         0.05, scale=1e-3,
                         help="Sotto il picco di fotocorrente il PD comprime: "
                              "non recuperabile")
        with c3:
            param_slider("RIN [dB/Hz]", "rin_db_hz", -160.0, -125.0, 1.0)
        with c4:
            param_slider("Rumore TIA [pA/√Hz]", "tia_noise_a_rt_hz", 5.0, 80.0, 1.0,
                         scale=1e-12)
        c5, c6, c7, c8 = st.columns(4)
        with c5:
            param_slider("Z_T [Ω]", "tia_transimpedance_ohm", 500.0, 6000.0, 100.0)
        with c6:
            param_slider("Banda TIA [GHz]", "tia_bw_hz", 15.0, 60.0, 1.0, scale=1e9)
        with c7:
            param_slider("Clip TIA [±V]", "tia_clip_v", 0.2, 1.5, 0.05)
        with c8:
            param_slider("Target AGC [Vrms]", "agc_target_rms_v", 0.05, 0.5, 0.01)
        st.markdown("**Parametri CTLE**")
        c9, c10, c11, c12 = st.columns(4)
        with c9:
            param_slider("Zero [GHz]", "ctle_zero_hz", 2.0, 24.0, 0.5, scale=1e9)
        with c10:
            param_slider("Polo [GHz]", "ctle_pole_hz", 8.0, 45.0, 0.5, scale=1e9)
        with c11:
            param_slider("Polo alto [GHz]", "ctle_hf_pole_hz", 30.0, 90.0, 1.0,
                         scale=1e9)
        with c12:
            param_slider("Guadagno DC [dB]", "ctle_dc_gain_db", -12.0, 6.0, 0.5,
                         help="Nei CTLE reali il boost si ottiene spesso "
                              "attenuando il DC, non alzando le alte")

    cfg = get_cfg()
    if cfg.validate():
        st.error(" · ".join(cfg.validate()))
        return
    sim = run_sim()
    rx = sim.receiver

    from serdes_sim.blocks.receiver import ctle_peaking_db
    peaking_db, f_peak = ctle_peaking_db(cfg.ctle_zero_hz, cfg.ctle_pole_hz,
                                         cfg.ctle_hf_pole_hz, cfg.ctle_dc_gain_db)
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("I media PD", f"{np.mean(rx.i_pd_signal_a) * 1e6:.1f} µA",
              help="Fotocorrente media R·⟨P⟩ + I_dark")
    m2.metric("ENBW TIA", f"{rx.tia_enbw_hz / 1e9:.2f} GHz",
              help="∫|H|²df: la banda che conta per il rumore, non la −3 dB")
    m3.metric("Guadagno AGC", f"{rx.agc_gain:.2f}×",
              help="Scala l'RMS al target: normalizza, non apre l'occhio")
    m4.metric("Peaking CTLE", f"{peaking_db:.1f} dB @ {f_peak / 1e9:.0f} GHz",
              help="max|H| − |H(DC)|: il boost delle alte frequenze")
    m5.metric("Noise enh. CTLE", f"{rx.ctle_noise_enhancement_db:+.2f} dB",
              help="Potenza media di |H|² su 0..fs/2: il costo in rumore")

    with st.container(border=True):
        a1, a2 = st.columns([1, 2.2])
        with a1:
            autotune = st.button("🎯 Ottimizza lo zero del CTLE",
                                 use_container_width=True,
                                 help="Sweep end-to-end dello zero (7 punti): "
                                      "sceglie quello con BER minima")
        with a2:
            st.caption("L'ottimo non è 'canale piatto': è il compromesso fra "
                       "ISI residua e noise enhancement, e dipende da tutto "
                       "quello che sta a valle (FSE, DFE). Per questo lo sweep "
                       "è end-to-end.")
        if autotune:
            from serdes_sim import sweep as engine_sweep
            # la griglia resta sotto il polo: il vincolo fz < fp deve valere
            zero_max = min(18e9, 0.85 * cfg.ctle_pole_hz)
            grid = np.linspace(min(4e9, 0.5 * zero_max), zero_max, 7)
            progress = st.progress(0.0, text="Sweep zero CTLE…")
            rows = engine_sweep(cfg, "ctle_zero_hz", grid,
                                progress_callback=lambda p: progress.progress(p))
            progress.empty()
            best = min(rows, key=lambda r: (r["BER_FSE_DFE"], r["BER_FSE"]))
            from ..state import set_cfg
            set_cfg(get_cfg().with_updates(ctle_zero_hz=float(best["ctle_zero_hz"])))
            if "w_ctle_zero_hz" in st.session_state:
                del st.session_state["w_ctle_zero_hz"]
            st.session_state["ctle_autotune_msg"] = (
                f"Zero applicato: {best['ctle_zero_hz'] / 1e9:.1f} GHz "
                f"(BER {best['BER_FSE_DFE']:.2e}). ATTENZIONE: sweep su un "
                "solo seed e sulla stessa validation della BER riportata — "
                "è un'indicazione, non un'ottimizzazione robusta (multi-seed "
                "e test set indipendente sono nel piano di lavoro).")
            st.rerun()
    if (m := st.session_state.pop("ctle_autotune_msg", None)):
        st.info(m)

    col1, col2 = st.columns(2)
    with col1:
        sources = list(rx.noise_rms_after_tia_a.keys())
        values = [v * 1e6 for v in rx.noise_rms_after_tia_a.values()]
        fig = plots.bar_fig(sources, values, title="Noise budget dopo il TIA",
                            ytitle="RMS [µA] (input-referred)", color=T.AMBER,
                            text=[f"{v:.2f}" for v in values])
        st.plotly_chart(fig, use_container_width=True)
        st.caption("RMS = √(PSD·ENBW): la banda di rumore è l'ENBW, non la "
                   "banda a −3 dB.")
    with col2:
        mask = (rx.f_fft_hz >= 0) & (rx.f_fft_hz <= 1.25 * cfg.nyquist_hz)
        H_ch = sim.channel.H_electrical
        fig = plots.line_fig(
            [dict(x=rx.f_fft_hz[mask] / 1e9, y=db20(rx.H_ctle[mask]),
                  name="CTLE", color=T.TEAL),
             dict(x=rx.f_fft_hz[mask] / 1e9, y=db20(H_ch[mask]),
                  name="canale", color=T.MUTED, dash="dot"),
             dict(x=rx.f_fft_hz[mask] / 1e9, y=db20(rx.H_ctle[mask] * H_ch[mask]),
                  name="canale × CTLE", color=T.ELECTRICAL, width=2.4)],
            title="CTLE: flatness non è gratis", xtitle="Frequenza [GHz]",
            ytitle="[dB]")
        plots.vline(fig, cfg.nyquist_hz / 1e9, label="Nyquist")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Eye prima e dopo il CTLE")
    col3, col4 = st.columns(2)
    with col3:
        H, te, ve, _, _ = eye_density(rx.v_agc_v, cfg.analog_sps, traces=1200)
        st.plotly_chart(plots.eye_heatmap(H, te, ve, title="Uscita AGC (pre-CTLE)",
                                          domain_color=T.MUTED, height=340),
                        use_container_width=True)
    with col4:
        H, te, ve, _, _ = eye_density(rx.v_ctle_v, cfg.analog_sps, traces=1200)
        st.plotly_chart(plots.eye_heatmap(H, te, ve, title="Uscita CTLE",
                                          domain_color=T.ELECTRICAL, height=340),
                        use_container_width=True)
    st.markdown(T.note(
        "L'AGC normalizza l'RMS ma <b>non apre l'occhio</b>: conserva l'SNR se "
        "è lineare. Se PD o TIA saturano, l'AGC può nascondere l'overload — "
        f"controlla i checkpoint: PD sat {100 * rx.pd_sat_fraction:.4f}%, "
        f"TIA clip {100 * rx.tia_clip_fraction:.4f}%."), unsafe_allow_html=True)


def page_adc():
    common.page_header("STADIO 07 · ADC", "Time-interleaved a 2 sample/UI",
                       "digital", "adc",
                       "Il piano A/D: da qui in poi il DSP vede solo adc_samples_v "
                       "— quantizzazione e mismatch non escono più dal percorso.")
    with st.expander("Teoria — interleaving, mismatch, ENOB"):
        st.markdown(content.ADC_THEORY)
        st.markdown(diagrams.adc_interleave_schematic(), unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("**Parametri ADC**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            param_int_slider("Bit", "adc_bits", 4, 10)
        with c2:
            param_slider("Full scale [Vpp]", "adc_full_scale_vpp", 0.6, 2.5, 0.05)
        with c3:
            param_slider("Jitter apertura [fs RMS]", "adc_jitter_rms_fs",
                         0.0, 400.0, 10.0)
        with c4:
            param_slider("Fase campionamento [UI]", "adc_phase_ui", -0.4, 0.4, 0.01)
        c5, c6, c7 = st.columns(3)
        with c5:
            param_slider("Gain mismatch RMS [%]", "adc_gain_mismatch_rms",
                         0.0, 3.0, 0.05, scale=0.01)
        with c6:
            param_slider("Offset mismatch RMS [mV]", "adc_offset_mismatch_rms_v",
                         0.0, 8.0, 0.1, scale=1e-3)
        with c7:
            param_slider("Skew mismatch RMS [fs]", "adc_skew_mismatch_rms_fs",
                         0.0, 200.0, 5.0)

    cfg = get_cfg()
    sim = run_sim()
    adc = sim.adc

    m1, m2, m3 = st.columns(3)
    m1.metric("LSB", f"{adc.adc_lsb_v * 1e3:.2f} mV")
    m2.metric("Clipping", f"{100 * adc.adc_clip_fraction:.3f} %")
    m3.metric("Sample rate DSP", f"{cfg.fs_adc_hz / 1e9:.1f} GSa/s")

    lanes = pd.DataFrame({
        "lane": np.arange(cfg.adc_interleaves),
        "gain error [%]": 100 * adc.lane_gain,
        "offset [mV]": 1e3 * adc.lane_offset_v,
        "skew [fs]": 1e15 * adc.lane_skew_s,
    })
    st.dataframe(lanes.round(3), use_container_width=True, hide_index=True)

    if sim.tone_lab is not None:
        tl = sim.tone_lab
        fig = plots.line_fig(
            [dict(x=tl.freq_hz / 1e9, y=tl.spec_ideal_dbfs,
                  name="solo quantizzazione", color=T.MUTED, width=1.0),
             dict(x=tl.freq_hz / 1e9, y=tl.spec_mismatch_dbfs,
                  name="con mismatch", color=T.DIGITAL, width=1.0)],
            title="Tone-lab: spettro del tono coerente",
            xtitle="Frequenza [GHz]", ytitle="[dBFS]",
            yaxis=dict(range=[-115, 5]), height=380)
        for line_hz in tl.interleave_lines_hz:
            plots.vline(fig, line_hz / 1e9, color=T.RED_FAIL, dash="dot",
                        label="k·fs/M")
        st.plotly_chart(fig, use_container_width=True)
        summary = pd.DataFrame({
            "caso": ["quantizzazione ideale", "con mismatch"],
            "SNDR [dB]": [tl.sndr_ideal_db, tl.sndr_mismatch_db],
            "ENOB [bit]": [tl.enob_ideal, tl.enob_mismatch],
            "spur max [dBFS]": [tl.spur_ideal_dbfs, tl.spur_mismatch_dbfs],
        })
        st.dataframe(summary.round(2), use_container_width=True, hide_index=True)
        st.markdown(T.note(
            "Su PAM4 gli spur si mescolano allo spettro dati: per questo il "
            "tone-lab usa un <b>tono sinusoidale coerente</b> come diagnostica. "
            "ENOB=(SNDR−1.76)/6.02 è un indicatore sinusoidale, non i bit utili "
            "per PAM4."), unsafe_allow_html=True)
