"""Pagina catena completa: KPI, explorer dei segnali, ledger, checkpoint."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from .. import common, plots
from .. import theme as T
from ..state import get_cfg, run_sim

# stage ledger name -> (dominio, descrizione breve)
EXPLORABLE = {
    "dac_waveform": ("electrical", "Uscita DAC (dopo banda)", "ampiezza norm."),
    "driver_voltage_v": ("electrical", "Uscita driver / ingresso canale", "V"),
    "electrical_waveform_v": ("electrical", "Uscita canale / drive MZM", "V"),
    "P_mzm_w": ("optical", "Potenza ottica dopo MZM", "mW"),
    "P_fiber_w": ("optical", "Potenza ottica al PD", "mW"),
    "i_pd_signal_a": ("electrical", "Fotocorrente (pre-rumore)", "µA"),
    "v_tia_v": ("electrical", "Uscita TIA (con rumore)", "V"),
    "v_ctle_v": ("electrical", "Uscita CTLE / ingresso ADC", "V"),
}


def _get_signal(sim, name):
    if name == "P_mzm_w":
        return sim.optical.P_mzm_w * 1e3
    if name == "P_fiber_w":
        return sim.optical.P_fiber_w * 1e3
    if name == "i_pd_signal_a":
        return sim.receiver.i_pd_signal_a * 1e6
    if name == "dac_waveform":
        return sim.tx.dac_waveform
    if name == "driver_voltage_v":
        return sim.tx.driver_voltage_v
    if name == "electrical_waveform_v":
        return sim.channel.electrical_waveform_v
    if name == "v_tia_v":
        return sim.receiver.v_tia_v
    if name == "v_ctle_v":
        return sim.receiver.v_ctle_v
    raise KeyError(name)


def page_chain():
    common.page_header("CATENA COMPLETA · END-TO-END", "Il link in un colpo d'occhio",
                       None, None,
                       "Ogni run è end-to-end: cambiando un parametro in qualunque "
                       "pagina, tutto ciò che sta a valle viene ricalcolato.")
    cfg = get_cfg()
    sim = run_sim()
    if not common.require_link(sim):
        return

    # --- KPI ---------------------------------------------------------------
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("BER pre-EQ", common.ber_str(sim.ber_pre_eq))
    k2.metric("BER FSE", common.ber_str(sim.ber_post_fse))
    k3.metric("BER FSE+DFE", common.ber_str(sim.ber_post_dfe))
    k4.metric("GMI [bit/simb]", f"{sim.gmi_total:.3f}")
    k5.metric("Tempo di run", f"{sim.elapsed_s * 1e3:.0f} ms")

    st.markdown("")

    # --- Budget di potenza ottica + waveform explorer ----------------------
    col1, col2 = st.columns([1, 1.4])
    with col1:
        st.subheader("Budget di potenza ottica")
        budget = sim.optical.power_budget_dbm
        fig = plots.bar_fig(list(budget.keys()), list(budget.values()),
                            ytitle="P media [dBm]", color=T.OPTICAL,
                            text=[f"{v:.2f}" for v in budget.values()], height=300)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Piani di riferimento: laser → MZM (IL + bias) → coupling → fibra → PD.")

    with col2:
        st.subheader("Explorer dei segnali")
        name = st.selectbox(
            "Nodo della catena",
            list(EXPLORABLE.keys()),
            format_func=lambda n: f"{EXPLORABLE[n][1]}  ·  [{EXPLORABLE[n][2]}]")
        domain, label, unit = EXPLORABLE[name]
        y = _get_signal(sim, name)
        n_show = 24 * cfg.analog_sps
        t_ps = np.arange(n_show) / cfg.fs_analog_hz * 1e12
        fig = plots.line_fig(
            [dict(x=t_ps, y=y[:n_show], color=T.DOMAIN_COLORS[domain], width=1.6)],
            xtitle="Tempo [ps]", ytitle=f"{label} [{unit}]", height=300)
        st.plotly_chart(fig, use_container_width=True)

    # --- Eye all'ingresso ADC ----------------------------------------------
    st.subheader("Eye PAM4 all'ingresso ADC (dopo CTLE)")
    from serdes_sim.blocks.metrics import eye_density
    H, t_edges, v_edges, _, _ = eye_density(sim.receiver.v_ctle_v, cfg.analog_sps,
                                            traces=1500)
    fig = plots.eye_heatmap(H, t_edges, v_edges, domain_color=T.ELECTRICAL,
                            height=420)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Eye a densità (2 UI). Diagnostico: non è una misura di BER né TDECQ.")

    # --- Ledger + checkpoint -----------------------------------------------
    col3, col4 = st.columns([1.5, 1])
    with col3:
        st.subheader("Signal ledger")
        df = pd.DataFrame(sim.ledger)
        df["mean"] = df["mean"].map("{:.3g}".format)
        df["ac_rms"] = df["ac_rms"].map("{:.3g}".format)
        df["peak_abs"] = df["peak_abs"].map("{:.3g}".format)
        st.dataframe(df, use_container_width=True, hide_index=True, height=420)
        st.caption("Identità, dominio, unità, sample rate e reference plane di ogni "
                   "stadio: il manifest di misura della catena.")
    with col4:
        st.subheader("Checkpoint automatici")
        common.checks_badges(sim.checks)

    st.subheader("Metriche di errore (validation set)")
    st.dataframe(common.metrics_dataframe(sim.metrics_rows),
                 use_container_width=True, hide_index=True)
