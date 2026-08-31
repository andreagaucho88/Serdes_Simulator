"""Elementi di pagina condivisi: header con schema catena, badge dei check."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from . import diagrams
from . import theme as T


def page_header(section: str, title: str, domain: str | None,
                active_block: str | None, subtitle: str | None = None):
    st.markdown(T.eyebrow(section, domain), unsafe_allow_html=True)
    st.title(title)
    if subtitle:
        st.markdown(f'<p style="color:{T.MUTED};margin-top:-0.6rem;">{subtitle}</p>',
                    unsafe_allow_html=True)
    st.markdown(diagrams.chain_diagram(active_block), unsafe_allow_html=True)
    st.markdown(diagrams.domain_legend(), unsafe_allow_html=True)
    st.markdown("")


def require_link(sim) -> bool:
    """False (con banner) se il CDR/pattern lock non agganciano: senza link
    le metriche a valle non esistono — comportamento di un ricevitore reale."""
    if getattr(sim, "link_up", True):
        return True
    detail = sim.cdr.detail if getattr(sim, "cdr", None) is not None else ""
    st.error("**LINK DOWN** — il CDR o il pattern lock non agganciano con "
             "questa configurazione: BER/GMI/FEC non esistono. "
             f"Diagnosi nella pagina *Timing recovery*. {detail}")
    return False


def checks_badges(checks: list[dict]):
    """Rende i checkpoint come badge PASS/FAIL."""
    html = []
    for ck in checks:
        cls = "badge-pass" if ck["status"] == "PASS" else "badge-fail"
        symbol = "✓" if ck["status"] == "PASS" else "✗"
        detail = f' — {ck["detail"]}' if ck.get("detail") else ""
        html.append(
            f'<div style="margin:0.18rem 0;">'
            f'<span class="{cls}">{symbol} {ck["status"]}</span> '
            f'<span style="font-size:0.88rem;color:{T.INK};">{ck["check"]}'
            f'<span style="color:{T.MUTED};">{detail}</span></span></div>')
    st.markdown("".join(html), unsafe_allow_html=True)


def metrics_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in ("SER", "BER", "BER_95pct_low", "BER_95pct_high", "zero_error_95pct_upper"):
        if col in df:
            df[col] = df[col].map(lambda v: f"{v:.3e}" if pd.notna(v) else "—")
    return df


def ber_str(value: float) -> str:
    return f"{value:.2e}"
