"""Pagina panoramica: cos'è il simulatore, come si usa, mappa lezioni."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import common, content
from .. import theme as T
from ..state import get_cfg, run_sim

LESSON_MAP = [
    ("L01", "dB, potenza, impedenza, reference plane", "Catena · Note"),
    ("L02", "poli, zeri, Bode, ENBW", "PD·TIA·CTLE"),
    ("L03", "gain, headroom, clipping", "TX elettrico"),
    ("L04", "rumore, sampling, ADC/DAC, jitter", "ADC · PD·TIA·CTLE"),
    ("L05", "architettura end-to-end e budget", "Catena completa"),
    ("L06", "PRBS, PAM4, eye, BER e confidence", "Stimolo · BER"),
    ("L07-L09", "linee, S-parameter, pulse response e ISI", "Canale elettrico"),
    ("L10-L12", "TX FFE, DAC, driver, sampler", "TX elettrico · ADC"),
    ("L13", "CTLE, FSE, DFE e adaptation", "Equalizzazione"),
    ("L14", "PSD, shot, RIN, soglie e BER", "PD·TIA·CTLE · BER"),
    ("L15", "RJ/DJ, bathtub e contour", "BER · bathtub"),
    ("L16", "PLL/CDR, Gardner e Mueller–Müller", "Timing recovery"),
    ("L19-L20", "campo, fibra, attenuazione e CD", "Fibra e dispersione"),
    ("L21-L22", "PIN, responsivity, TIA, AGC", "PD·TIA·CTLE"),
    ("L23-L24", "laser, chirp, RIN, MZM", "MZM e laser"),
    ("L25-L26", "OMA, sensitivity, budget, GMI", "Catena · BER"),
]


def page_overview():
    common.page_header("SIMULATORE DIDATTICO · 112G-CLASS PAM4",
                       "Catena SerDes + link ottico IM/DD", None, None,
                       "Laboratorio interattivo: il segnale dal bit al BER, senza salti.")

    st.markdown("""
Questo strumento è il companion eseguibile delle lezioni **L01–L28** del corso.
Segue il segnale senza scorciatoie:

**bit → PAM4 → TX FFE → DAC/driver → canale elettrico → MZM → fibra →
PD/TIA/CTLE → ADC 2 sps → CDR → FSE/DFE → LLR, BER, GMI.**

Non c'è una `simulate_link()` opaca: ogni stadio ha la sua pagina con lo schema,
le equazioni, i parametri da muovere, gli osservabili che possono falsificare
il modello e almeno un checkpoint automatico.
""")

    col1, col2 = st.columns([1.15, 1])
    with col1:
        st.subheader("Come si usa")
        st.markdown("""
1. **Scegli un preset** nella barra laterale (o parti dal default 2 km).
2. Apri la pagina **Catena completa** per i KPI e il signal ledger.
3. Entra nelle pagine dei singoli **stadi**: muovi i parametri e osserva
   come cambiano gli osservabili *a valle* (la simulazione è sempre end-to-end).
4. Usa **Esperimenti** per gli sweep monoparametrici (BER/GMI vs parametro).
5. In ogni pagina, le note teoriche sono nell'expander "Teoria".
""")
        st.markdown(T.note(content.SEVEN_QUESTIONS.replace("\n", "<br>")),
                    unsafe_allow_html=True)
    with col2:
        st.subheader("Stato del link corrente")
        sim = run_sim()
        if not sim.link_up:
            st.error("LINK DOWN — CDR/pattern lock non agganciano: vedi Timing recovery.")
            return
        c1, c2 = st.columns(2)
        c1.metric("BER pre-EQ", common.ber_str(sim.ber_pre_eq))
        c2.metric("BER FSE+DFE", common.ber_str(sim.ber_post_dfe))
        c1.metric("GMI [bit/simbolo]", f"{sim.gmi_total:.3f}")
        c2.metric("P @ PD [dBm]", f"{sim.optical.power_budget_dbm['PD input']:.2f}")
        n_pass = sum(1 for ck in sim.checks if ck["status"] == "PASS")
        c1.metric("Checkpoint", f"{n_pass}/{len(sim.checks)} PASS")
        c2.metric("Baud rate", f"{get_cfg().symbol_rate_hz / 1e9:.3f} GBd")
        st.markdown(T.warn(content.VALIDITY), unsafe_allow_html=True)

    st.subheader("Mappa lezioni → pagine del simulatore")
    st.dataframe(pd.DataFrame(LESSON_MAP, columns=["Lezione", "Competenza", "Pagina"]),
                 use_container_width=True, hide_index=True)
