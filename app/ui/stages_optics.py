"""Pagine ottiche: MZM + laser, fibra + dispersione cromatica."""

from __future__ import annotations

import numpy as np
import streamlit as st

from serdes_sim.blocks.optical import imdd_small_signal_response
from serdes_sim.utils import db20

from .. import common, content, diagrams, plots
from .. import theme as T
from ..state import get_cfg, run_sim, param_slider


def page_mzm():
    common.page_header("STADIO 04 · MODULATORE", "Laser CW e Mach-Zehnder",
                       "optical", "mzm",
                       "Qui il segnale attraversa il piano E/O: da tensione a "
                       "campo ottico complesso, con |E|² = P.")
    with st.expander("Teoria — transfer function, bias, Vπ, chirp"):
        st.markdown(content.MZM_THEORY)
        st.markdown(diagrams.mzm_schematic(), unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("**Parametri laser + MZM**")
        c1, c2, c3 = st.columns(3)
        with c1:
            param_slider("Potenza laser [dBm]", "laser_dbm", -6.0, 12.0, 0.5)
        with c2:
            param_slider("Vπ [V]", "vpi_v", 1.5, 6.0, 0.1)
        with c3:
            param_slider("Bias [rad]", "mzm_bias_rad", 0.6, 2.6, 0.02,
                         help="π/2 ≈ 1.571 = quadratura")
        c4, c5, c6 = st.columns(3)
        with c4:
            param_slider("Banda MZM [GHz]", "mzm_bw_hz", 15.0, 60.0, 1.0, scale=1e9)
        with c5:
            param_slider("IL MZM [dB]", "mzm_il_db", 1.0, 9.0, 0.25)
        with c6:
            param_slider("Chirp α", "chirp_alpha", -1.5, 1.5, 0.05)

    cfg = get_cfg()
    sim = run_sim()
    opt = sim.optical

    m1, m2, m3 = st.columns(3)
    m1.metric("P laser", f"{cfg.laser_dbm:.1f} dBm")
    m2.metric("P media dopo MZM", f"{opt.power_budget_dbm['MZM output']:.2f} dBm")
    m3.metric("Swing drive picco", f"{np.max(np.abs(opt.mzm_drive_v)):.3f} V "
              f"({np.max(np.abs(opt.mzm_drive_v)) / cfg.vpi_v:.2f}·Vπ)")

    col1, col2 = st.columns(2)
    with col1:
        fig = plots.line_fig(
            [dict(x=opt.v_static, y=opt.p_static, color=T.OPTICAL, width=2.2)],
            title="Transfer statica P/P_in vs drive", xtitle="Drive [V]",
            ytitle="P/P_in")
        plots.vline(fig, 0, label="bias point")
        swing = float(np.max(np.abs(opt.mzm_drive_v)))
        fig.add_vrect(x0=-swing, x1=swing, fillcolor=T.OPTICAL, opacity=0.07,
                      line_width=0)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("La banda evidenziata è lo swing effettivo del drive: se "
                   "esce dal tratto quasi-lineare, la cosenoide comprime i "
                   "livelli esterni PAM4.")
    with col2:
        n_show = 10 * cfg.analog_sps
        t_ps = np.arange(n_show) / cfg.fs_analog_hz * 1e12
        fig = plots.line_fig(
            [dict(x=t_ps, y=opt.P_mzm_w[:n_show] * 1e3, color=T.OPTICAL,
                  width=2.0)],
            title="Potenza ottica modulata", xtitle="Tempo [ps]",
            ytitle="P [mW]")
        st.plotly_chart(fig, use_container_width=True)

    fig = plots.line_fig(
        [dict(x=t_ps, y=opt.inst_freq_shift_hz[:n_show] / 1e9, color=T.AMBER,
              width=1.8)],
        title="Chirp istantaneo Δf(t)", xtitle="Tempo [ps]", ytitle="Δf [GHz]",
        height=280)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown(T.note(
        "Prima della fibra il chirp è <b>invisibile</b> al photodiode "
        "(square-law). È la dispersione che converte questa fase in distorsione "
        "d'ampiezza: vedi la pagina Fibra."), unsafe_allow_html=True)


def page_fiber():
    common.page_header("STADIO 05 · FIBRA", "Attenuazione e dispersione cromatica",
                       "optical", "fiber",
                       "La CD agisce sul campo: per IM/DD diventa un filtro "
                       "cos(θ) con nulli — un notch dentro Nyquist non si equalizza.")
    with st.expander("Teoria — β₂, fading IM/DD, primo nullo"):
        st.markdown(content.FIBER_THEORY)
    with st.expander("Esercizio guidato B"):
        st.markdown(content.EXERCISE_B)

    with st.container(border=True):
        st.markdown("**Parametri fibra**")
        c1, c2, c3 = st.columns(3)
        with c1:
            param_slider("Lunghezza [km]", "fiber_km", 0.0, 20.0, 0.25)
        with c2:
            param_slider("D [ps/(nm·km)]", "dispersion_ps_nm_km", -25.0, 25.0, 0.5,
                         help="C-band ≈ +17; O-band vicino a 0")
        with c3:
            param_slider("λ [nm]", "wavelength_nm", 1260.0, 1610.0, 5.0)
        c4, c5 = st.columns(3)[:2]
        with c4:
            param_slider("Loss [dB/km]", "fiber_loss_db_km", 0.1, 0.6, 0.01)
        with c5:
            param_slider("Coupling IL [dB]", "coupling_il_db", 0.0, 6.0, 0.25)

    cfg = get_cfg()
    sim = run_sim()
    opt = sim.optical

    accumulated = cfg.dispersion_ps_nm_km * cfg.fiber_km
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("β₂", f"{opt.beta2_s2_m * 1e27:.2f} ps²/km")
    m2.metric("D·L", f"{accumulated:.1f} ps/nm")
    m3.metric("Primo nullo IM/DD",
              "∞" if not np.isfinite(opt.f_null_hz) else f"{opt.f_null_hz / 1e9:.1f} GHz")
    m4.metric("P @ PD", f"{opt.power_budget_dbm['PD input']:.2f} dBm")

    col1, col2 = st.columns(2)
    with col1:
        f_plot = np.linspace(0, 1.5 * cfg.nyquist_hz, 1200)
        H = imdd_small_signal_response(cfg, f_plot, alpha=0.0)
        fig = plots.line_fig(
            [dict(x=f_plot / 1e9, y=db20(np.maximum(np.abs(H), 1e-5)),
                  color=T.OPTICAL, width=2.2)],
            title="Fading CD small-signal (chirp-free)", xtitle="Frequenza [GHz]",
            ytitle="|H| [dB]", yaxis=dict(range=[-60, 5]))
        plots.vline(fig, cfg.nyquist_hz / 1e9, label="Nyquist")
        if np.isfinite(opt.f_null_hz) and opt.f_null_hz < 1.5 * cfg.nyquist_hz:
            plots.vline(fig, opt.f_null_hz / 1e9, color=T.RED_FAIL, label="1º nullo")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = plots.line_fig(
            [dict(x=f_plot / 1e9,
                  y=db20(np.maximum(np.abs(imdd_small_signal_response(cfg, f_plot, alpha=a)), 1e-4)),
                  name=f"α={a:+.1f}",
                  color=c, width=1.8)
             for a, c in zip([-1.0, 0.0, 0.4, 1.0],
                             [T.MUTED, T.ELECTRICAL, T.OPTICAL, T.AMBER])],
            title="Chirp × CD: il segno di α sposta i nulli",
            xtitle="Frequenza [GHz]", ytitle="[dB]",
            yaxis=dict(range=[-45, 10]))
        plots.vline(fig, cfg.nyquist_hz / 1e9, label="Nyquist")
        st.plotly_chart(fig, use_container_width=True)

    n_show = 10 * cfg.analog_sps
    t_ps = np.arange(n_show) / cfg.fs_analog_hz * 1e12
    fig = plots.line_fig(
        [dict(x=t_ps, y=opt.P_mzm_w[:n_show] * 1e3, name="dopo MZM",
              color=T.MUTED, width=1.4),
         dict(x=t_ps, y=opt.P_fiber_w[:n_show] * 1e3 * 10 ** ((cfg.coupling_il_db
              + cfg.fiber_loss_db_km * cfg.fiber_km) / 10),
              name="al PD (rinormalizzata per la loss)", color=T.OPTICAL, width=2.0)],
        title="Potenza: distorsione da CD (loss compensata per confronto)",
        xtitle="Tempo [ps]", ytitle="P [mW]", height=320)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown(T.warn(
        "Il percorso principale propaga il <b>campo complesso</b> e applica lo "
        "square-law al PD: il grafico small-signal è solo il controllo fisico "
        "di tendenza."), unsafe_allow_html=True)
