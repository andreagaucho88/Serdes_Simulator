"""Pagina FEC: codec RS(544,514) reale + analisi del pattern d'errore del link."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from serdes_sim.blocks import fec

from .. import common, plots
from .. import theme as T
from ..state import param_select, run_sim

THEORY = r"""
**Che cosa è implementato davvero** (identico al notebook v7):

- campo $GF(2^{10})$ con polinomio primitivo $x^{10}+x^3+1$;
- generatore $g(x)=\prod_{j=0}^{29}(x-\alpha^j)$;
- encoder sistematico 514 dati + 30 parity;
- syndrome → Berlekamp–Massey → Chien search → soluzione delle magnitudini;
- correzione fino a $t=15$ symbol errors, failure dichiarata oltre.

**Cosa non è**: il PCS Ethernet completo (scrambler, alignment marker, bit
muxing, interleaving fra codeword) resta clause-dependent. È un codec RS
algebricamente reale, non una dichiarazione di conformità.

**Come leggiamo il link**: lo stimolo PRBS non è RS-encoded, quindi misuriamo
il *pattern d'errore* post-DFE e chiediamo: "spezzato in simboli da 10 bit e
frame da 544, questo pattern sarebbe correggibile?" — lo stesso ragionamento
con cui si stima il FEC gain da una misura di raw BER. Sotto ipotesi di errori
indipendenti:

$$q = 1-(1-p)^{10},\qquad FER = P[X>15],\ X\sim Binomial(544, q)$$

I burst (per esempio da error propagation del DFE) rompono l'ipotesi iid: a
parità di BER la distribuzione per codeword cambia radicalmente.
"""


def page_fec():
    common.page_header("STADIO 11 · FEC", "Reed-Solomon RS(544,514) su GF(2¹⁰)",
                       "digital", "fec",
                       "Il FEC 'KP4' dei link 100G/200G per corsia: correzione "
                       "reale fino a 15 symbol errors per codeword.")
    with st.expander("Teoria — codec, iid vs burst, cosa è proxy"):
        st.markdown(THEORY)

    with st.container(border=True):
        param_select("FEC nel percorso", "fec_mode", ["none", "kp4", "kr4"],
                     format_func=lambda m: {"none": "nessuno (analisi what-if)",
                                            "kp4": "KP4 RS(544,514) in-path",
                                            "kr4": "KR4 RS(528,514) in-path"}[m],
                     help="Con kp4/kr4 l'encoder è prima del mapper e il "
                          "decoder dopo lo slicer: FEC reale nel percorso")

    sim = run_sim()
    if not common.require_link(sim):
        return
    fa = sim.fec

    if sim.fec_link is not None:
        fl = sim.fec_link
        st.markdown(T.note(
            f"<b>FEC in-path attivo ({fl.codec_name})</b> — frame decodati "
            f"{fl.n_frames} (solo validation): {fl.frames_clean} clean, "
            f"{fl.frames_corrected} corretti ({fl.symbols_corrected} simboli), "
            f"{fl.frames_uncorrectable} persi, {fl.frames_miscorrected} "
            f"miscorretti · pre-FEC {fl.pre_fec_ber:.2e} → post-FEC "
            f"{fl.post_fec_ber:.2e}"), unsafe_allow_html=True)

    # --- KPI dal link -------------------------------------------------------
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Pre-FEC BER", f"{fa.pre_fec_ber:.2e}")
    k2.metric("SER simboli 10b", f"{fa.symbol_error_rate:.2e}")
    k3.metric("Burstiness", f"{fa.burstiness_ratio:.2f}",
              help="SER misurata / q attesa da BER iid: <1 = errori raggruppati "
                   "negli stessi simboli, >1 = più sparsi dell'iid")
    k4.metric("FER modello iid", f"{fa.fer_iid_model_qmeas:.2e}")
    k5.metric("Frame nel record", f"{fa.frames_uncorrectable}/{fa.n_frames} persi")

    # --- errori per frame + curva teorica ----------------------------------
    col1, col2 = st.columns(2)
    with col1:
        if fa.n_frames:
            fig = plots.bar_fig(
                [f"frame {i}" for i in range(fa.n_frames)],
                fa.errors_per_frame,
                title="Symbol errors per codeword (record misurato)",
                ytitle="simboli errati su 544", color=T.DIGITAL,
                text=[str(v) for v in fa.errors_per_frame])
            plots.hline(fig, fec.RS_T, color=T.RED_FAIL, label="capacità t=15")
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"Record di validation: {fa.n_bits} bit → "
                       f"{fa.n_symbols_10b} simboli → {fa.n_frames} frame "
                       f"completi. Run massimo di simboli errati consecutivi: "
                       f"{fa.max_consecutive_symbol_errors}.")
        else:
            st.info("Record troppo corto per un frame completo da 544 simboli.")
    with col2:
        raw = np.logspace(-7, -1.3, 121)
        q, fer = fec.fer_curve(raw)
        fig = plots.line_fig(
            [dict(x=raw, y=np.maximum(q, 1e-30), name="q simbolo (iid)",
                  color=T.MUTED),
             dict(x=raw, y=np.maximum(fer, 1e-30), name="FER RS(544,514) iid",
                  color=T.DIGITAL, width=2.4)],
            title="Da raw BER a FER (ipotesi iid)", xtitle="pre-FEC BER",
            ytitle="probabilità", xlog=True, ylog=True, height=360,
            yaxis=dict(range=[-18, 0.5]))
        fig.add_trace(__import__("plotly.graph_objects", fromlist=["go"]).Scatter(
            x=[fa.pre_fec_ber], y=[max(fa.fer_iid_model_qmeas, 1e-18)],
            mode="markers+text", text=["sei qui"], textposition="top left",
            marker=dict(size=11, color=T.OPTICAL, symbol="x"),
            showlegend=False))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Il marker usa la q misurata dal record. Il ginocchio della "
                   "curva è il motivo per cui si cita una 'soglia pre-FEC': "
                   "poco sopra, il FEC non salva nulla; poco sotto, la FER "
                   "crolla di ordini di grandezza.")

    # --- burstiness ---------------------------------------------------------
    if len(fa.error_gap_bits):
        st.subheader("Burstiness del pattern d'errore")
        col3, col4 = st.columns(2)
        with col3:
            import plotly.graph_objects as go
            fig = go.Figure(go.Histogram(x=fa.error_gap_bits, nbinsx=60,
                                         marker_color=T.AMBER))
            fig.update_layout(plots.base_layout(
                title=dict(text="Gap fra bit errati [bit]",
                           font=dict(family=T.FONT_DISPLAY, size=15)),
                xaxis=dict(title="distanza dal precedente errore"),
                yaxis=dict(title="conteggio", type="log"), height=320))
            st.plotly_chart(fig, use_container_width=True)
        with col4:
            st.markdown(T.note(
                "Gap piccoli e frequenti = <b>burst</b> (tipico dell'error "
                "propagation del DFE: una decisione sbagliata inquina la "
                "feedback history). Sotto burst la colonna dei symbol error "
                "per frame diventa 'a grumi' e la FER reale peggiora rispetto "
                "al modello iid a parità di BER — è il motivo per cui gli "
                "standard usano interleaving/symbol muxing prima del RS."),
                unsafe_allow_html=True)

    # --- codec demo interattivo --------------------------------------------
    st.subheader("Banco del codec: inietta errori e decodifica")
    c1, c2 = st.columns([1, 2.2])
    with c1:
        n_err = st.slider("Symbol errors da iniettare", 0, 20, 12)
        seed = st.number_input("Seed iniezione", 1, 9999, 7)
        run = st.button("Encode → corrompi → decode", type="primary",
                        use_container_width=True)
    with c2:
        if run:
            rows = fec.codec_demo(error_counts=(n_err,), seed=int(seed))
            row = rows[0]
            if row["esito"] == "corretto":
                st.success(f"Iniettati {n_err} symbol errors → decoder OK, "
                           f"{row['correzioni_riportate']} correzioni riportate, "
                           "codeword ripristinato bit-esatto.")
            elif row["esito"] == "MISCORREZIONE":
                st.error("MISCORREZIONE: il decoder ha 'corretto' verso un "
                         "codeword diverso — possibile oltre t, mai entro t.")
            else:
                st.warning(f"Oltre capacità: {row['esito']}. Un decoder "
                           "bounded-distance oltre t=15 dichiara failure "
                           "oppure (raramente) miscorregge: non può correggere.")
        else:
            st.caption("Prova 15 (limite), poi 16: il comportamento cambia "
                       "qualitativamente. Il codec è quello vero, non una "
                       "lookup table.")
    demo_rows = fec.codec_demo()
    st.dataframe(pd.DataFrame(demo_rows), use_container_width=True,
                 hide_index=True)
    st.markdown(T.warn(
        "La <b>FER del record</b> qui sopra usa pochi frame: è un'osservazione, "
        "non una statistica. Il modello iid estrapola, ma solo se il pattern "
        "non è bursty — controlla sempre la burstiness prima di fidarti."),
        unsafe_allow_html=True)
