"""Pagina esperimenti: sweep monoparametrici end-to-end (BER/GMI vs parametro)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import streamlit as st

from serdes_sim import SWEEPABLE_FIELDS, sweep

from .. import common, plots
from .. import theme as T
from ..state import get_cfg


def page_experiments():
    common.page_header("LABORATORIO · SWEEP", "Esperimenti parametrici",
                       None, None,
                       "Ogni punto è una simulazione end-to-end completa "
                       "(depth light): shot, RIN, saturazioni e adaptation "
                       "vengono ricalcolati — a differenza della waterfall "
                       "detector-only.")

    cfg = get_cfg()
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.6, 1, 1, 0.8])
        with c1:
            field = st.selectbox(
                "Parametro da variare", list(SWEEPABLE_FIELDS.keys()),
                format_func=lambda f: SWEEPABLE_FIELDS[f][0])
        label, lo_default, hi_default = SWEEPABLE_FIELDS[field]
        with c2:
            lo = st.number_input("Da", value=float(lo_default), format="%.4g")
        with c3:
            hi = st.number_input("A", value=float(hi_default), format="%.4g")
        with c4:
            n_points = st.number_input("Punti", 3, 25, 9)
        run = st.button("Esegui sweep end-to-end", type="primary",
                        use_container_width=True)

    if run:
        values = np.linspace(lo, hi, int(n_points))
        progress = st.progress(0.0, text="Sweep in corso…")
        rows = sweep(cfg, field, values,
                     progress_callback=lambda p: progress.progress(
                         p, text=f"Sweep in corso… {int(p * 100)}%"))
        progress.empty()
        st.session_state["last_sweep"] = {"field": field, "rows": rows,
                                          "cfg": json.dumps(cfg.to_dict())}

    data = st.session_state.get("last_sweep")
    if not data:
        st.markdown(T.note(
            "Suggerimenti: <b>fiber_km</b> mostra la penalty CD sovrapposta alla "
            "loss; <b>laser_dbm</b> è la vera curva di sensitivity (a differenza "
            "della waterfall detector-only); <b>chirp α</b> mostra il segno che "
            "aiuta o danneggia; <b>adc_bits</b> trova il ginocchio della "
            "quantizzazione."), unsafe_allow_html=True)
        return

    field = data["field"]
    df = pd.DataFrame(data["rows"])
    label = SWEEPABLE_FIELDS[field][0]
    if data["cfg"] != json.dumps(cfg.to_dict()):
        st.info("La configurazione è cambiata dopo questo sweep: rieseguilo per "
                "confrontare con il link corrente.")

    # floor statistico dal numero reale di bit di validation di questo sweep
    floor = 0.5 / max(float(df["val_bits"].min()), 1.0) if "val_bits" in df \
        else 0.5 / 9922
    col1, col2 = st.columns(2)
    with col1:
        fig = plots.line_fig(
            [dict(x=df[field], y=np.maximum(df["BER_pre_EQ"], floor),
                  name="pre-EQ", color=T.MUTED, mode="lines+markers"),
             dict(x=df[field], y=np.maximum(df["BER_FSE"], floor),
                  name="FSE", color=T.DIGITAL, mode="lines+markers"),
             dict(x=df[field], y=np.maximum(df["BER_FSE_DFE"], floor),
                  name="FSE+DFE", color=T.GREEN_OK, mode="lines+markers")],
            title=f"BER vs {label}", xtitle=label, ytitle="BER (validation)",
            ylog=True, height=380)
        plots.hline(fig, floor, color=T.MUTED, label="~floor statistico")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        gmi_max = 1.0 if cfg.modulation == "NRZ" else 2.0
        fig = plots.line_fig(
            [dict(x=df[field], y=df["GMI_bit_per_simbolo"], name="GMI",
                  color=T.AMBER, mode="lines+markers")],
            title=f"GMI vs {label}", xtitle=label,
            ytitle="GMI [bit/simbolo]", height=380,
            yaxis=dict(range=[0, gmi_max + 0.05]))
        plots.hline(fig, gmi_max, color=T.GRID, label=f"max {cfg.modulation}")
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        df.style.format({c: "{:.3e}" for c in
                         ("BER_pre_EQ", "BER_FSE", "BER_FSE_DFE",
                          "FER_RS544_iid") if c in df} |
                        {"GMI_bit_per_simbolo": "{:.4f}", "P_PD_dBm": "{:.2f}"}),
        use_container_width=True, hide_index=True)
    if (df["checks_fail"] > 0).any():
        st.markdown(T.warn(
            "In alcuni punti dello sweep uno o più <b>checkpoint falliscono</b> "
            "(es. saturazioni): quelle BER vanno lette con sospetto — il modello "
            "sta uscendo dal suo dominio di validità."), unsafe_allow_html=True)
