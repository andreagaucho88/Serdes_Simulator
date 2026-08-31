"""Pagina standard: mappa IEEE 802.3 / OIF-CEI per velocità di corsia,
con evidenza della famiglia più vicina alla configurazione corrente."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from serdes_sim.blocks import fec

from .. import common, plots
from .. import theme as T
from ..state import get_cfg, set_cfg, run_sim, apply_preset

# Tabella orientativa (riferimenti indicativi, non testo normativo).
# Le corsie ELETTRICHE (AUI/C2M/KR/CR) e i PMD OTTICI sono elencati separati:
# condividono il baud rate ma hanno clause, metriche e reach diversi.
# (GBd, mod, Gb/s lane, famiglia, stato, elettrico, ottico, fec_kind, fec_label, nota)
STANDARD_ROWS = [
    (10.3125, "NRZ", 10.3125, "10G — 802.3ae/ap", "pubblicato",
     "10GBASE-KR (Cl. 72), XFI/SFI", "10GBASE-LR/ER (Cl. 52)",
     "none", "FEC opzionale (Cl. 74)",
     "L'era pre-FEC obbligatorio: link chiusi a occhio."),
    (25.78125, "NRZ", 25.78125, "25G/lane — 802.3by/bj · OIF CEI-28G",
     "pubblicato",
     "25GBASE-KR/CR (Cl. 110-111), CEI-28G-VSR/MR/LR",
     "25GBASE-LR, 100GBASE-LR4 (4×25G)",
     "kr4", "RS(528,514) 'KR4' (Cl. 91/108)",
     "Ultima generazione NRZ dominante."),
    (26.5625, "PAM4", 53.125, "50G/lane — 802.3bs/cd · OIF CEI-56G",
     "pubblicato",
     "50GBASE-KR/CR (Cl. 136-137), CEI-56G-PAM4",
     "50GBASE-FR/LR, 200GBASE-DR4, 400GBASE-FR8/LR8",
     "kp4", "RS(544,514) 'KP4' (Cl. 134)",
     "Il passaggio a PAM4: FEC diventa obbligatorio."),
    (53.125, "PAM4", 106.25, "100G/lane — 802.3ck/cu/df · OIF CEI-112G",
     "pubblicato (802.3df: 2024)",
     "100GBASE-KR1/CR1 (802.3ck), AUI C2M, CEI-112G-XSR/VSR/MR/LR",
     "100G-DR/FR1/LR1 (802.3cu), 400GBASE-DR4, 800G (802.3df)",
     "kp4", "RS(544,514) 'KP4'",
     "Il profilo di questo simulatore (56 GBd didattico)."),
    (106.25, "PAM4", 212.5, "200G/lane — P802.3dj · OIF CEI-224G",
     "IN SVILUPPO (draft)",
     "CEI-224G: progetti per reach in definizione, C2M/C2C",
     "200G/λ DR/FR proposti in P802.3dj",
     "kp4", "RS(544,514) + interleaving/concatenazione in studio",
     "Progetto attivo: numeri e clause possono ancora cambiare."),
]

# modelli FEC per famiglia (binomiale iid sul NOSTRO codec/parametri)
FEC_MODELS = {
    "kp4": ("RS(544,514) t=15", dict(n=544, t=15, m=10)),
    "kr4": ("RS(528,514) t=7", dict(n=528, t=7, m=10)),
    "none": ("nessun FEC obbligatorio", None),
}


def page_standards():
    common.page_header("CONTESTO · STANDARD", "Dove sei: IEEE 802.3 e OIF-CEI",
                       None, None,
                       "Una velocità di corsia individua una famiglia di clause: "
                       "elettrico, ottico e FEC viaggiano insieme.")

    st.markdown(T.warn(
        "Tabella <b>orientativa</b> per lo studio: i numeri di clause sono "
        "riferimenti indicativi, non testo normativo. Per compliance serve la "
        "clause applicabile (pattern, filtri, procedura e decision rule "
        "prescritti)."), unsafe_allow_html=True)

    cfg = get_cfg()
    sim = run_sim()
    gbd = cfg.symbol_rate_hz / 1e9
    bps = sim.spec.bits_per_symbol
    lane_gbs = gbd * bps

    # famiglia più vicina (per GBd e modulazione compatibile)
    candidates = [(abs(row[0] - gbd) / row[0], row) for row in STANDARD_ROWS
                  if row[1] == cfg.modulation]
    closest = min(candidates, key=lambda t: t[0]) if candidates else None

    st.subheader("La tua configurazione")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Baud rate", f"{gbd:.3f} GBd",
              help="Simboli/s. Le famiglie di standard sono definite dal baud "
                   "rate di corsia, non dal bit rate aggregato.")
    c2.metric("Modulazione", sim.spec.label)
    c3.metric("Rate di corsia", f"{lane_gbs:.2f} Gb/s",
              help="baud × bit/simbolo, raw (prima di FEC/overhead)")
    if closest:
        dev_pct = closest[0] * 100
        c4.metric("Famiglia più vicina", closest[1][3].split("—")[0].strip(),
                  delta=f"{dev_pct:.1f}% dal baud nominale", delta_color="off")

    if closest and closest[0] < 0.08:
        row = closest[1]
        st.markdown(T.note(
            f"<b>{row[3]}</b> ({row[4]}) — corsie elettriche (AUI/KR/CR): "
            f"{row[5]} · PMD ottici: {row[6]} · FEC: {row[8]}<br>{row[9]}"),
            unsafe_allow_html=True)
    elif closest:
        st.markdown(T.note(
            f"Il baud rate corrente ({gbd:.2f} GBd) non coincide con nessuna "
            f"corsia standard {cfg.modulation}: la più vicina è "
            f"<b>{closest[1][3]}</b> a {closest[1][0]} GBd "
            f"({closest[0] * 100:.1f}% di distanza). Usa i bottoni qui sotto "
            "per allinearti a una corsia reale."), unsafe_allow_html=True)

    # --- soglia pre-FEC della famiglia individuata ---------------------------
    st.subheader("Il tuo link contro la soglia pre-FEC della SUA famiglia")
    ber = sim.ber_post_dfe
    fec_kind = closest[1][7] if closest else "kp4"
    fec_name, fec_params = FEC_MODELS[fec_kind]
    if fec_params is None:
        c1, c2 = st.columns(2)
        c1.metric("BER post-DSP contata", f"{ber:.2e}")
        target = 1e-12
        ok = ber <= target
        c2.metric("Riferimento senza FEC", f"BER ≤ {target:.0e}",
                  delta="raggiunta" if ok else "non raggiunta (su questo record "
                  "una BER così bassa non è comunque dimostrabile)",
                  delta_color="normal" if ok else "inverse")
        st.caption("Questa famiglia non prescrive un FEC obbligatorio: il "
                   "link deve chiudere a occhio nudo.")
    else:
        ber_threshold = fec.prefec_ber_threshold(1e-13, **fec_params)
        c1, c2, c3 = st.columns(3)
        c1.metric("BER post-DSP contata", f"{ber:.2e}",
                  help="Contata sulla validation; l'intervallo di confidenza è "
                       "nella pagina Misure (ipotesi iid)")
        c2.metric(f"Soglia pre-FEC {fec_name}", f"{ber_threshold:.2e}",
                  help=f"BER a cui la FER del modello binomiale iid di "
                       f"{fec_name} scende a 1e-13. È il NOSTRO modello, non "
                       "un numero di clause; per KP4 l'ordine di grandezza "
                       "coincide con il ≈2e-4 comunemente citato.")
        margin_db = 10 * np.log10(ber_threshold / max(ber, 1e-30))
        ok = ber <= ber_threshold
        c3.metric("Rapporto BER (in dB)", f"{margin_db:+.1f} dB",
                  help="10·log₁₀(soglia/BER): NON è un margine di potenza o "
                       "di apertura; dice solo di quanto la BER contata sta "
                       "sotto (o sopra) la soglia del modello.",
                  delta="sotto soglia: chiudibile col FEC (modello iid)"
                  if ok else "sopra soglia: il FEC non salva questo link",
                  delta_color="normal" if ok else "inverse")
    if not ok:
        st.markdown(T.note(
            "Il profilo didattico di default è volutamente stressato (2 km in "
            "C-band a 56 GBd): per vedere un link 'da standard' prova il preset "
            "back-to-back, riduci la fibra o passa in O-band "
            "(preset 100GBASE-LR1 context)."), unsafe_allow_html=True)

    # --- tabella completa con highlight -------------------------------------
    st.subheader("Mappa delle corsie")
    df = pd.DataFrame(
        [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[8], r[9])
         for r in STANDARD_ROWS],
        columns=["GBd", "mod", "Gb/s lane", "famiglia", "stato",
                 "corsie elettriche (AUI/KR/CR)", "PMD ottici (esempi)",
                 "FEC", "nota"])

    def _highlight(r):
        is_match = closest and abs(r["GBd"] - closest[1][0]) < 1e-6 and \
            r["mod"] == cfg.modulation and closest[0] < 0.08
        return ["background-color: rgba(255,122,89,0.14)" if is_match else ""] * len(r)

    st.dataframe(df.style.apply(_highlight, axis=1), use_container_width=True,
                 hide_index=True, height=250)
    st.caption("Stato aggiornato al momento della stesura (2026): 802.3df è "
               "pubblicato (2024), P802.3dj e OIF CEI-224G sono progetti in "
               "corso — verificare su ieee802.org/3 e oiforum.com prima di "
               "citare clause. Le corsie elettriche (AUI/C2M/KR/CR) e i PMD "
               "ottici condividono il baud ma hanno metriche diverse "
               "(COM vs TDECQ).")

    st.subheader("Portami su una corsia standard")
    cols = st.columns(len(STANDARD_ROWS))
    for col, row in zip(cols, STANDARD_ROWS):
        gbd_row, mod = row[0], row[1]
        with col:
            if st.button(f"{gbd_row:g} GBd\n{mod}", key=f"std_{gbd_row}_{mod}",
                         use_container_width=True):
                set_cfg(cfg.with_updates(symbol_rate_hz=gbd_row * 1e9,
                                         modulation=mod))
                for key in [k for k in st.session_state
                            if str(k).startswith("w_")]:
                    del st.session_state[key]
                st.rerun()
    st.caption("I bottoni impostano baud rate e modulazione della corsia; il "
               "resto della catena (canale, ottica, RX) resta la tua "
               "configurazione — è il punto: lo standard fissa la corsia, il "
               "budget lo chiudi tu.")

    st.subheader("Cosa prescrive davvero uno standard (e questo tool no)")
    st.markdown("""
| Dominio | Metrica normativa | Nel simulatore |
|---|---|---|
| TX ottico | **TDECQ** (eye closure con equalizzatore di riferimento a 5 tap) | eye a densità + opening 3σ (**proxy dichiarati**) |
| Canale elettrico | **COM** (Channel Operating Margin, Annex 93A) e IL/RL mask | IL/RL del modello o dell'S2P caricato, cursor plot |
| RX | stressed receiver sensitivity con pattern e stress prescritti | sweep di sensitivity end-to-end (pagina Esperimenti) |
| FEC | RS(544,514) con bit muxing/interleaving di clause | codec RS(544,514) reale + analisi iid/burst |
| Jitter | scomposizione RJ/DJ con metodi di clause | bathtub empirica + dual-Dirac dichiarato |
""")
