"""Pagine DSP: timing recovery, equalizzazione FSE+DFE, BER/LLR/bathtub."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from serdes_sim.utils import db10

from .. import common, content, diagrams, plots
from .. import theme as T
from ..state import (get_cfg, run_sim, param_int_slider,
                     param_select, param_slider)


def page_timing():
    common.page_header("STADIO 08 · TIMING RECOVERY", "Acquisition, Gardner e "
                       "Mueller–Müller", "digital", "cdr",
                       "Prima di equalizzare bisogna sapere quando campionare: "
                       "acquisition dai campioni ADC, poi il TED.")
    with st.expander("Teoria — acquisition, TED, S-curve"):
        st.markdown(content.TIMING_THEORY)

    with st.container(border=True):
        st.markdown("**Parametri CDR (nel datapath)**")
        t1, t2, t3, t4 = st.columns(4)
        with t1:
            param_select("Modo", "cdr_mode", ["gardner", "mm", "oracle"],
                         format_func=lambda m: {"gardner": "Gardner",
                                                "mm": "Mueller-Müller",
                                                "oracle": "oracle (ideale)"}[m])
        with t2:
            param_slider("Banda loop [·f_baud]", "cdr_bw", 0.0004, 0.005,
                         0.0002, fmt="%.4f")
        with t3:
            param_slider("Damping ζ", "cdr_damping", 0.5, 2.0, 0.1)
        with t4:
            param_slider("Offset clock RX [ppm]", "rx_ppm_offset",
                         -300.0, 300.0, 10.0)

    sim = run_sim()
    cfg_now = get_cfg()
    timing = sim.timing

    if sim.cdr is not None:
        c = sim.cdr
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(f"CDR {cfg_now.cdr_mode}",
                  "LOCKED" if c.locked else "UNLOCKED",
                  delta=(f"lock al simbolo {c.lock_symbol}" if c.locked
                         else c.detail[:40]),
                  delta_color="normal" if c.locked else "inverse",
                  help="Loop PI del 2° ordine + NCO NEL datapath: decide "
                       "davvero gli istanti di campionamento di FSE/DFE/BER")
        m2.metric("Pattern lock (BERT)",
                  "SYNC" if c.pattern_locked else "NO SYNC",
                  delta=(f"lag {c.pattern_lag} · |corr| {abs(c.pattern_corr):.2f}"
                         if c.pattern_lag is not None else "—"),
                  delta_color="normal" if c.pattern_locked else "inverse",
                  help="Allineamento per cross-correlazione con la sequenza "
                       "attesa, come un error detector reale")
        m3.metric("Cycle slips", str(c.cycle_slips))
        m4.metric("Banda loop", f"{cfg_now.cdr_bw:.4f}·f_baud",
                  delta=f"zeta {cfg_now.cdr_damping:g}", delta_color="off")
        col_a, col_b = st.columns(2)
        with col_a:
            sub = max(1, len(c.tau_trace_ui) // 1500)
            fig = plots.line_fig(
                [dict(x=np.arange(0, len(c.tau_trace_ui), sub),
                      y=c.tau_trace_ui[::sub], color=T.DIGITAL, width=1.2)],
                title="Fase NCO nel tempo (traiettoria del CDR)",
                xtitle="Simbolo", ytitle="tau [UI]")
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Con rx_ppm_offset ≠ 0 la fase diventa una rampa che "
                       "il registro di frequenza deve assorbire.")
        with col_b:
            fig = plots.line_fig(
                [dict(x=np.arange(0, len(c.freq_trace_ppm), sub),
                      y=c.freq_trace_ppm[::sub], color=T.AMBER, width=1.2)],
                title="Registro di frequenza del loop",
                xtitle="Simbolo", ytitle="correzione [ppm]")
            if cfg_now.rx_ppm_offset:
                plots.hline(fig, -cfg_now.rx_ppm_offset, color=T.GREEN_OK,
                            label="offset da inseguire")
            st.plotly_chart(fig, use_container_width=True)
        if not sim.link_up:
            st.error("LINK DOWN: senza lock (CDR o pattern) le metriche a "
                     "valle non esistono — è il comportamento di un "
                     "ricevitore reale.")
    if timing is None:
        return

    st.subheader("Riferimento oracle (diagnostica)")
    st.markdown(T.note(
        "La mappa qui sotto è l'<b>acquisition oracle</b> (minimo MSE usando "
        "i simboli noti): serve da riferimento per confrontare dove aggancia "
        "il CDR reale rispetto all'ottimo ideale."), unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        rel = db10(timing.phase_mse / timing.phase_mse.min())
        fig = plots.line_fig(
            [dict(x=timing.phase_grid_ui, y=rel, color=T.DIGITAL, width=2.2)],
            title=f"MSE vs fase (delay={timing.rx_integer_delay_ui:+d} UI)",
            xtitle="Fase frazionaria [UI]", ytitle="MSE relativa [dB]")
        plots.vline(fig, timing.best_phase_ui, color=T.GREEN_OK,
                    label=f"best {timing.best_phase_ui:+.3f}")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = plots.heat_fig(
            db10(timing.delay_phase_mse / timing.delay_phase_mse.min()),
            timing.phase_grid_ui, timing.integer_delay_grid_ui,
            title="Mappa acquisition: delay × fase", xtitle="Fase [UI]",
            ytitle="Ritardo intero [UI]",
            colorscale=[[0, T.DIGITAL], [0.35, T.PANEL_2], [1, T.PANEL]],
            colorbar_title="dB")
        st.plotly_chart(fig, use_container_width=True)

    if timing.gardner_scurve is not None:
        col3, col4 = st.columns(2)
        with col3:
            fig = plots.line_fig(
                [dict(x=timing.phase_grid_ui, y=timing.gardner_scurve,
                      name="Gardner", color=T.DIGITAL, width=2.2),
                 dict(x=timing.phase_grid_ui, y=timing.mm_scurve,
                      name="Mueller–Müller", color=T.AMBER, width=2.0)],
                title="S-curve dei due TED", xtitle="Fase [UI]",
                ytitle="E[e]")
            plots.hline(fig, 0, color=T.GRID, dash="solid")
            plots.vline(fig, timing.best_phase_ui, color=T.GREEN_OK)
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Il TED è utilizzabile dove la S-curve attraversa lo zero "
                       "con pendenza costante: quello è il range di cattura.")
        with col4:
          if timing.loop_phase_trace_ui is not None:
            fig = plots.line_fig(
                [dict(x=np.arange(len(timing.loop_phase_trace_ui)),
                      y=timing.loop_phase_trace_ui, color=T.DIGITAL, width=1.2)],
                title="Loop Gardner first-order: fase stimata",
                xtitle="Simbolo", ytitle="Fase [UI]")
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Loop didattico first-order (solo modalità oracle): il "
                       "CDR vero del datapath è quello mostrato in alto.")
    st.markdown(T.note(
        "Interpolare fra i campioni ADC non annulla aperture jitter o "
        "quantizzazione: <b>ricombina campioni già degradati</b>."),
        unsafe_allow_html=True)


def page_eq():
    common.page_header("STADIO 09 · EQUALIZZAZIONE", "FSE NLMS a 2 sps + DFE",
                       "digital", "eq",
                       "Il FSE assorbe ISI lineare e fase residua; il DFE cancella "
                       "i postcursor usando le decisioni — con il loro rischio.")
    with st.expander("Teoria — NLMS, tap frazionari, error propagation"):
        st.markdown(content.EQ_THEORY)
        st.markdown(diagrams.dfe_schematic(), unsafe_allow_html=True)
    with st.expander("Esercizio guidato C"):
        st.markdown(content.EXERCISE_C)

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            param_int_slider("Tap FSE (dispari)", "fse_taps", 5, 31, step=2)
        with c2:
            param_int_slider("Tap DFE", "dfe_taps", 1, 12)
        with c3:
            param_int_slider("Fine training [simboli]", "training_stop", 600, 6000)

    cfg = get_cfg()
    sim = run_sim()
    if not common.require_link(sim):
        return
    eq = sim.eq

    ber = sim.metrics_rows
    m1, m2, m3 = st.columns(3)
    m1.metric("BER baseline 1 sps", common.ber_str(ber[0]["BER"]))
    m2.metric("BER FSE", common.ber_str(ber[1]["BER"]),
              delta=f"{(ber[1]['BER'] - ber[0]['BER']):.2e}", delta_color="inverse")
    m3.metric("BER FSE+DFE", common.ber_str(ber[2]["BER"]),
              delta=f"{(ber[2]['BER'] - ber[1]['BER']):.2e}", delta_color="inverse")

    col1, col2 = st.columns(2)
    with col1:
        mse = pd.Series(eq.fse_learning_error ** 2).rolling(120).mean()
        fig = plots.line_fig(
            [dict(x=np.arange(len(mse)), y=mse, color=T.DIGITAL, width=1.4)],
            title="Convergenza NLMS (MSE mobile)", xtitle="Update",
            ytitle="MSE", ylog=True)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        tap_pos_ui = (np.arange(cfg.fse_taps) - cfg.fse_taps // 2) / cfg.adc_sps
        fig = plots.stem_fig(tap_pos_ui, eq.fse_taps_w,
                             title="Tap FSE (spaziatura 0.5 UI)",
                             xtitle="Posizione [UI]", ytitle="Coefficiente",
                             color=T.DIGITAL)
        st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        fig = plots.stem_fig(np.arange(1, cfg.dfe_taps + 1), eq.dfe_coeff,
                             title="Coefficienti DFE (postcursor)",
                             xtitle="Postcursor [UI]", ytitle="b_m",
                             color=T.AMBER)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Confrontali con il cursor plot del canale: il DFE impara "
                   "esattamente i postcursor residui dopo il FSE.")
    with col4:
        if eq.dfe_forced is not None:
            w0, w1 = eq.inject_at - 3, eq.inject_at + 14
            xs = np.arange(w0, w1)
            fig = plots.line_fig(
                [dict(x=xs, y=eq.dfe_output[w0:w1], name="DFE nominale",
                      color=T.DIGITAL, mode="lines+markers"),
                 dict(x=xs, y=eq.dfe_forced[w0:w1], name="con errore forzato",
                      color=T.RED_FAIL, mode="lines+markers", dash="dash")],
                title="Error propagation: una decisione sbagliata",
                xtitle="Indice simbolo", ytitle="Uscita DFE")
            plots.vline(fig, eq.inject_at, color=T.RED_FAIL, label="iniezione")
            st.plotly_chart(fig, use_container_width=True)
            n_prop = len(eq.propagation_span)
            st.caption(f"L'errore forzato influenza {n_prop} sample successivi "
                       "(risposta causale della feedback history).")

    if eq.dfe_tap_trace is not None:
        st.subheader("Adaptation continua: DD-LMS contro stima one-shot")
        col_a, col_b = st.columns(2)
        with col_a:
            trace = eq.dfe_tap_trace
            xs = np.arange(len(trace)) * 16
            traces = [dict(x=xs, y=trace[:, m], name=f"b{m + 1}",
                           color=[T.DIGITAL, T.AMBER, T.TEAL, T.OPTICAL,
                                  T.MUTED][m % 5], width=1.6)
                      for m in range(trace.shape[1])]
            fig = plots.line_fig(traces, title="Traiettoria dei tap DFE (LMS)",
                                 xtitle="Simbolo", ytitle="b_m", height=320)
            for m, b in enumerate(eq.dfe_coeff):
                plots.hline(fig, b, color=T.GRID, dash="dot")
            plots.vline(fig, cfg.training_stop, color=T.GREEN_OK,
                        label="fine training → DD")
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Linee puntinate: la stima one-shot ai minimi quadrati. "
                       "Dopo la linea verde l'LMS diventa decision-directed: "
                       "insegue le proprie decisioni, giuste o sbagliate.")
        with col_b:
            fig = plots.conditional_histograms(
                eq.dfe_output[eq.validation_fse], eq.d_fse[eq.validation_fse],
                sim.spec.levels_array,
                title="Istogramma uscita DFE con soglie")
            for t in sim.thresholds_dfe[0]:
                plots.vline(fig, t, color=T.MUTED, dash="dot")
            for t in sim.thresholds_dfe[1]:
                plots.vline(fig, t, color=T.GREEN_OK, dash="dash")
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Soglie stimate sul piano post-DFE (training). Grigio: "
                       "punto medio; verde: calibrata sulle σ. La coda che "
                       "attraversa la soglia È la BER.")

    st.subheader("Costellazioni: prima e dopo")
    col5, col6, col7 = st.columns(3)
    val = eq.validation_fse
    for col, (y, name, color) in zip(
            (col5, col6, col7),
            [(eq.rx_baud_norm[eq.validation_baud][:2500], "baseline 1 sps", T.MUTED),
             (eq.fse_output[val][:2500], "FSE", T.DIGITAL),
             (eq.dfe_output[val][:2500], "FSE + DFE", T.GREEN_OK)]):
        with col:
            fig = plots.line_fig(
                [dict(x=np.arange(len(y)), y=y, mode="markers", color=color,
                      marker_size=2.4, opacity=0.5)],
                title=name, xtitle="Simbolo (validation)", ytitle="Ampiezza",
                height=300)
            for lv in sim.spec.levels_array:
                plots.hline(fig, lv, color=T.GRID, dash="dot")
            st.plotly_chart(fig, use_container_width=True)


def page_ber():
    common.page_header("STADIO 10 · DECISIONI E METRICHE", "BER, LLR, GMI e bathtub",
                       "digital", "ber",
                       "Una BER senza conteggio errori e intervallo di confidenza "
                       "non è una misura: è un'opinione.")
    with st.expander("Teoria — confidence, LLR, GMI, dual-Dirac"):
        st.markdown(content.BER_THEORY)

    sim = run_sim()
    if not common.require_link(sim):
        return
    eq = sim.eq

    st.subheader("Metriche per stadio (validation set)")
    st.dataframe(common.metrics_dataframe(sim.metrics_rows),
                 use_container_width=True, hide_index=True)

    spec = sim.spec

    # --- Decisioni: chi sbaglia verso chi -----------------------------------
    st.subheader("Decisioni: confusion matrix e Q-factor")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        labels = [f"{v:+.2f}" for v in spec.levels_array]
        conf = sim.confusion.astype(float)
        conf_norm = conf / np.maximum(conf.sum(axis=1, keepdims=True), 1)
        fig = plots.heat_fig(
            np.log10(np.maximum(conf_norm, 1e-6)), labels, labels,
            title="Confusion matrix post-DFE (log₁₀ P)",
            xtitle="livello deciso", ytitle="livello trasmesso",
            colorscale=[[0, T.PANEL], [0.5, T.PANEL_2], [1, T.RED_FAIL]],
            height=360, colorbar_title="log₁₀P")
        st.plotly_chart(fig, use_container_width=True)
        n_levels = len(spec.levels_array)
        off_tri = int(sum(sim.confusion[i, j]
                          for i in range(n_levels) for j in range(n_levels)
                          if abs(i - j) > 1))
        total_err = int(sim.confusion.sum()
                        - np.trace(sim.confusion))
        if total_err == 0:
            st.caption("Nessun errore di simbolo sulla validation: la matrice "
                       "è diagonale.")
        elif off_tri == 0:
            msg = ("Tutti gli errori sono fra livelli adiacenti (banda "
                   "tridiagonale)")
            if spec.mapping == "gray":
                msg += ": con Gray ogni errore di simbolo costa 1 solo bit."
            st.caption(msg)
        else:
            st.caption(f"{off_tri} errori su {total_err} saltano più di un "
                       "livello: il rumore/ISI è abbastanza forte da "
                       "attraversare due soglie — il vantaggio del Gray si "
                       "riduce e la BER gaussiana da Q non è più affidabile.")
    with col_d2:
        snr = sim.snr_dfe
        c1, c2 = st.columns(2)
        c1.metric("SNR al slicer", f"{snr['snr_slicer_db']:.2f} dB",
                  help="10·log₁₀(E[d²]/E[(y−d)²]) su validation: include "
                       "rumore, ISI residua e non linearità")
        c2.metric("Q minimo", f"{snr['q_min']:.2f}",
                  help="Q = (μ₊−μ₋)/(σ₊+σ₋) dell'occhio peggiore")
        eye_names = ["basso", "medio", "alto"][:len(snr["q_per_eye"])]
        fig = plots.bar_fig(eye_names, snr["q_per_eye"],
                            title="Q-factor per occhio (post-DFE)",
                            ytitle="Q", color=T.TEAL,
                            text=[f"{q:.2f}" for q in snr["q_per_eye"]],
                            height=255)
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Q(Q_min) = {snr['ber_from_qmin_gaussian']:.1e} è un "
                   "proxy del SOLO occhio peggiore (non pesa i livelli né "
                   "somma i tre occhi; σ stimate sul training) — confrontalo "
                   f"con la BER contata {sim.ber_post_dfe:.1e}: se divergono, "
                   "il rumore non è gaussiano, c'è error propagation o gli "
                   "errori saltano più di un livello. Definizioni nella "
                   "pagina Misure & definizioni.")
    col1, col2 = st.columns(2)
    with col1:
        fig = plots.conditional_histograms(
            eq.fse_output[eq.validation_fse], eq.d_fse[eq.validation_fse],
            spec.levels_array, title="Distribuzioni condizionali (uscita FSE)")
        st.plotly_chart(fig, use_container_width=True)
        stats_df = pd.DataFrame(sim.level_stats)
        stats_df["opening_3σ →"] = [""] + [f"{v:+.4f}" for v in sim.eye_openings_3sigma]
        st.dataframe(stats_df.round(4), use_container_width=True, hide_index=True)
        st.markdown(T.warn("<b>opening_3σ è un proxy diagnostico</b>, non "
                           "TDECQ/SECQ."), unsafe_allow_html=True)
    with col2:
        bit_names = ["A", "B", "C"][:len(sim.gmi_per_bit)]
        cols = st.columns(len(sim.gmi_per_bit) + 1)
        for c, name, g in zip(cols, bit_names, sim.gmi_per_bit):
            c.metric(f"GMI bit {name}", f"{g:.4f}")
        cols[-1].metric("GMI totale",
                        f"{sim.gmi_total:.4f}/{spec.bits_per_symbol}")
        llr = sim.llr
        fig = plots.conditional_histograms(
            llr[:, 0], np.zeros(len(llr)), [0.0], colors=[T.DIGITAL],
            title="Istogramma LLR bit A (validation)", xtitle="LLR", height=300)
        fig.data[0].name = "LLR bit A"
        st.plotly_chart(fig, use_container_width=True)
        st.caption("LLR positivo = evidenza per bit 0. Code strette intorno a "
                   "zero = simboli ambigui che un FEC soft può ancora usare.")

    st.subheader("Waterfall detector-only")
    sigma, errors, bers, n_bits = sim.waterfall
    floor = 0.5 / n_bits
    fig = plots.line_fig(
        [dict(x=sigma, y=np.maximum(bers, floor), color=T.DIGITAL,
              mode="lines+markers", width=2)],
        xtitle="AWGN RMS aggiunto dopo il FSE [unità norm.]",
        ytitle="BER misurata", ylog=True, height=340)
    plots.hline(fig, floor, color=T.MUTED, label="floor 0.5/N")
    st.plotly_chart(fig, use_container_width=True)
    st.markdown(T.warn(
        "Sweep <b>detector-only</b>: il rumore è aggiunto dopo il FSE. Isola il "
        "detector ma NON equivale a variare la potenza ottica (shot, RIN, "
        "saturazioni e tap non vengono ricalcolati). Per quello usa la pagina "
        "Esperimenti."), unsafe_allow_html=True)

    if sim.bathtub is not None:
        st.subheader("Bathtub e BER contour")
        bt = sim.bathtub
        col3, col4 = st.columns(2)
        with col3:
            fig = plots.line_fig(
                [dict(x=bt.phase_ui, y=np.maximum(bt.empirical_ber, bt.plot_floor),
                      name="empirica pre-EQ", color=T.DIGITAL, mode="markers",
                      marker_size=5),
                 dict(x=bt.phase_ui, y=np.maximum(bt.model_ber, 1e-18),
                      name="dual-Dirac dichiarato", color=T.AMBER)],
                title="Bathtub: conteggio finito vs estrapolazione",
                xtitle="Fase [UI]", ytitle="BER", ylog=True,
                yaxis=dict(range=[-6, 0]))
            plots.hline(fig, bt.plot_floor, color=T.MUTED, label="floor 0.5/N")
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"Modello: σ_RJ={bt.sigma_rj_s * 1e12:.2f} ps, "
                       f"DJ_pp={bt.dj_pp_s * 1e12:.1f} ps — estrapolazione "
                       "dichiarata, valida solo se il jitter è davvero RJ+DJ.")
        with col4:
            phase_ui, threshold_mv, contour = sim.contour
            fig = plots.heat_fig(
                np.log10(np.maximum(contour, 1e-18)), phase_ui, threshold_mv,
                title="BER contour (modello H/V indipendente)",
                xtitle="Fase [UI]", ytitle="Offset soglia [mV]",
                colorscale="Viridis", colorbar_title="log₁₀ BER")
            st.plotly_chart(fig, use_container_width=True)
