"""Entry point del simulatore didattico SerDes + link ottico.

Avvio:  cd simulatore && python -m streamlit run app/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import theme as T                      # noqa: E402
from app.state import get_cfg, set_cfg, apply_preset, run_sim  # noqa: E402
from app.ui.overview import page_overview       # noqa: E402
from app.ui.chain import page_chain             # noqa: E402
from app.ui.stages_tx import page_stimulus, page_tx, page_channel  # noqa: E402
from app.ui.stages_optics import page_mzm, page_fiber  # noqa: E402
from app.ui.stages_rx import page_receiver, page_adc   # noqa: E402
from app.ui.stages_dsp import page_timing, page_eq, page_ber  # noqa: E402
from app.ui.fec_page import page_fec             # noqa: E402
from app.ui.eyes import page_eyes                # noqa: E402
from app.ui.measures import page_measures        # noqa: E402
from app.ui.scope import page_scope              # noqa: E402
from app.ui.spectrum import page_spectrum        # noqa: E402
from app.ui.standards import page_standards      # noqa: E402
from app.ui.experiments import page_experiments  # noqa: E402
from app.ui.realism import page_realism          # noqa: E402
from app.ui.notes import page_notes              # noqa: E402

from serdes_sim import PRESETS                   # noqa: E402

st.set_page_config(
    page_title="SerDes Optical Lab",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(T.GLOBAL_CSS, unsafe_allow_html=True)


# --- Sidebar: rack di controllo -------------------------------------------

with st.sidebar:
    st.markdown(
        f'<div style="font-family:{T.FONT_DISPLAY};font-size:1.25rem;'
        f'font-weight:600;">SerDes <span style="color:{T.OPTICAL};">Optical</span> Lab</div>'
        f'<div style="font-family:{T.FONT_MONO};font-size:0.7rem;color:{T.MUTED};'
        f'letter-spacing:0.12em;">CATENA ELETTRO-OTTICA · 112G PAM4</div>',
        unsafe_allow_html=True)
    st.markdown("")

    preset_name = st.selectbox(
        "Preset", list(PRESETS.keys()),
        index=list(PRESETS.keys()).index(
            st.session_state.get("preset_name", list(PRESETS.keys())[0]))
        if st.session_state.get("preset_name") in PRESETS else 0,
        help="Configurazioni di partenza; i parametri si modificano nelle "
             "pagine dei singoli stadi.")
    st.caption(PRESETS[preset_name][1])
    if st.button("Applica preset", use_container_width=True):
        apply_preset(preset_name)
        st.rerun()

    causal = st.toggle("Filtri causali (fase reale)",
                       value=get_cfg().causal_filters,
                       help="OFF: filtri in sola magnitudine (fase zero, scelta "
                            "didattica del notebook v7). ON: Butterworth "
                            "causale con fase e group delay reali su DAC, "
                            "driver, MZM, PD e TIA. |H| identica: cambia solo "
                            "la fase.")
    if causal != get_cfg().causal_filters:
        set_cfg(get_cfg().with_updates(causal_filters=causal))

    with st.expander("Riproducibilità"):
        st.number_input("Seed rumore/jitter", 1, 10 ** 9,
                        int(st.session_state.get("seed", 20240731)), key="seed",
                        help="Stesso seed = stesse realizzazioni di rumore, "
                             "jitter e mismatch")

    # mini-monitor sempre visibile
    try:
        sim = run_sim()
        st.markdown("---")
        st.markdown(
            f'<div style="font-family:{T.FONT_MONO};font-size:0.78rem;'
            f'color:{T.MUTED};">MONITOR LINK</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        if sim.link_up:
            c1.metric("BER", f"{sim.ber_post_dfe:.1e}")
            c2.metric("GMI", f"{sim.gmi_total:.3f}")
        else:
            c1.metric("LINK", "DOWN")
            c2.metric("CDR", "no lock")
        st.caption(f"{sim.spec.label} · PRBS{sim.cfg.prbs_order} · "
                   f"{sim.cfg.symbol_rate_hz / 1e9:g} GBd")
        n_fail = sum(1 for ck in sim.checks if ck["status"] == "FAIL")
        if n_fail:
            st.markdown(f'<span class="badge-fail">✗ {n_fail} checkpoint FAIL</span>',
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<span class="badge-pass">✓ tutti i checkpoint PASS</span>',
                        unsafe_allow_html=True)
    except Exception as exc:
        st.error(f"Configurazione non valida: {exc}")

    st.markdown("---")
    st.caption("Fisica: notebook v7 del corso (L01–L28). Le metriche non "
               "normative sono etichettate proxy.")


# --- Navigazione -----------------------------------------------------------

pages = {
    "Inizio": [
        st.Page(page_overview, title="Panoramica", icon="🗺️", default=True),
        st.Page(page_chain, title="Catena completa", icon="⛓️",
                url_path="catena"),
    ],
    "Stadi della catena": [
        st.Page(page_stimulus, title="01 · Stimolo PRBS · NRZ/PAM4", icon="🎲",
                url_path="stimolo"),
        st.Page(page_tx, title="02 · TX: FFE, DAC, driver", icon="📤",
                url_path="tx"),
        st.Page(page_channel, title="03 · Canale elettrico", icon="🧵",
                url_path="canale"),
        st.Page(page_mzm, title="04 · MZM e laser", icon="💡", url_path="mzm"),
        st.Page(page_fiber, title="05 · Fibra e dispersione", icon="🌈",
                url_path="fibra"),
        st.Page(page_receiver, title="06 · PD, TIA, CTLE", icon="📥",
                url_path="ricevitore"),
        st.Page(page_adc, title="07 · ADC interleaved", icon="🎚️",
                url_path="adc"),
        st.Page(page_timing, title="08 · Timing recovery", icon="⏱️",
                url_path="timing"),
        st.Page(page_eq, title="09 · FSE + DFE", icon="🧮", url_path="eq"),
        st.Page(page_ber, title="10 · BER, LLR, bathtub", icon="📊",
                url_path="ber"),
        st.Page(page_fec, title="11 · FEC RS(544,514)", icon="🛡️",
                url_path="fec"),
    ],
    "Diagnostica": [
        st.Page(page_scope, title="Scope live (DCA)", icon="📺",
                url_path="scope"),
        st.Page(page_spectrum, title="Spectrum analyzer", icon="📡",
                url_path="spettro"),
        st.Page(page_eyes, title="Eye lungo la catena", icon="👁️",
                url_path="eye"),
        st.Page(page_measures, title="Misure & definizioni", icon="📐",
                url_path="misure"),
    ],
    "Laboratorio": [
        st.Page(page_experiments, title="Esperimenti (sweep)", icon="🧪",
                url_path="sweep"),
        st.Page(page_standards, title="Standard IEEE / OIF", icon="📖",
                url_path="standard"),
        st.Page(page_realism, title="IBIS-AMI e realismo", icon="🧩",
                url_path="realismo"),
        st.Page(page_notes, title="Note e glossario", icon="📚",
                url_path="note"),
    ],
}

nav = st.navigation(pages)
nav.run()
