"""Auto-Negotiation stile IEEE 802.3 Clause 73 — modello di protocollo.

DICHIARATO: qui si modella lo strato di PROTOCOLLO dell'AN di Clause 73
(base page a 48 bit con selector/nonce/ability/FEC, macchina a stati con i
timer di Table 73-7, priority resolution → HCD), NON la segnalazione
elettrica DME a 312.5 MBd sul lane 0. Il sottoinsieme di Table 73-4 è
quello elencato in TECH_TABLE (fino ad A18, 802.3ck). Clause 73 esiste per
backplane e cavo in rame (KR/CR): un modulo ottico NON fa AN — la sua
gestione è CMIS — e il banco lo dichiara quando link_medium = "optical".
"""

from __future__ import annotations

import numpy as np

# Table 73-4 (sottoinsieme dichiarato). Ordine = priorità crescente:
# la HCD (highest common denominator) è l'ultima abilità comune della lista.
# (bit, nome, Gb/s per lane, numero lane, modulazione, FEC associato)
TECH_TABLE = [
    ("A0",  "1000BASE-KX",         1.0,  1, "NRZ",  None),
    ("A11", "2.5GBASE-KX",         2.5,  1, "NRZ",  None),
    ("A12", "5GBASE-KR",           5.0,  1, "NRZ",  None),
    ("A1",  "10GBASE-KX4",         2.5,  4, "NRZ",  None),
    ("A2",  "10GBASE-KR",         10.0,  1, "NRZ",  "cl74-negoziabile"),
    ("A3",  "40GBASE-KR4",        10.0,  4, "NRZ",  "cl74-negoziabile"),
    ("A4",  "40GBASE-CR4",        10.0,  4, "NRZ",  "cl74-negoziabile"),
    ("A5",  "100GBASE-CR10",      10.0, 10, "NRZ",  "cl74"),
    ("A9",  "25GBASE-KR-S/CR-S",  25.0,  1, "NRZ",  "negoziabile (F2/F3)"),
    ("A10", "25GBASE-KR/CR",      25.0,  1, "NRZ",  "negoziabile (F2/F3)"),
    ("A6",  "100GBASE-KP4",       25.0,  4, "PAM4", "RS(544,514) obbligatorio"),
    ("A7",  "100GBASE-KR4",       25.0,  4, "NRZ",  "RS(528,514) obbligatorio"),
    ("A8",  "100GBASE-CR4",       25.0,  4, "NRZ",  "RS(528,514) obbligatorio"),
    ("A13", "50GBASE-KR/CR",      50.0,  1, "PAM4", "RS(544,514) obbligatorio"),
    ("A14", "100GBASE-KR2/CR2",   50.0,  2, "PAM4", "RS(544,514) obbligatorio"),
    ("A15", "200GBASE-KR4/CR4",   50.0,  4, "PAM4", "RS(544,514) obbligatorio"),
    ("A16", "100GBASE-KR1/CR1",  100.0,  1, "PAM4", "RS(544,514) obbligatorio"),
    ("A17", "200GBASE-KR2/CR2",  100.0,  2, "PAM4", "RS(544,514) obbligatorio"),
    ("A18", "400GBASE-KR4/CR4",  100.0,  4, "PAM4", "RS(544,514) obbligatorio"),
]
TECH_BY_BIT = {t[0]: t for t in TECH_TABLE}
PRIORITY = {t[0]: i for i, t in enumerate(TECH_TABLE)}

# posizione dei bit nella base page (Clause 73.6): A0 = D21 … A22 = D43
_A_BASE_D = 21
_FEC_D = {"F2": 44, "F3": 45, "F0": 46, "F1": 47}


def local_abilities_from_cfg(cfg):
    """Abilities pubblicizzate coerenti col banco: la famiglia il cui rate
    per lane è più vicino al lane simulato, più i fallback più lenti dello
    stesso mezzo (comportamento tipico di un PHY multi-rate)."""
    lane_gbps = cfg.symbol_rate_hz * (2 if cfg.modulation == "PAM4" else 1) / 1e9
    if lane_gbps >= 90:
        abil = ["A16", "A17", "A18", "A13", "A14", "A15", "A10", "A2"]
    elif lane_gbps >= 45:
        abil = ["A13", "A14", "A15", "A10", "A2"]
    elif lane_gbps >= 20:
        abil = ["A10", "A9", "A6", "A7", "A2"] if cfg.modulation == "PAM4" \
            else ["A10", "A9", "A7", "A2"]
    else:
        abil = ["A2", "A12", "A0"]
    return [a for a in abil if a in TECH_BY_BIT]


def build_base_page(abilities, fec_bits=(), nonce=0, echoed_nonce=0,
                    ack=False, pause=True):
    """Base page a 48 bit (D0..D47) come intero + campi decodificati."""
    page = 0b00001                        # D[4:0] selector = 802.3
    page |= (echoed_nonce & 0x1F) << 5    # D[9:5]
    if pause:
        page |= 1 << 10                   # C0 pause ability
    if ack:
        page |= 1 << 14                   # D14 acknowledge
    page |= (nonce & 0x1F) << 16          # D[20:16] transmitted nonce
    for a in abilities:
        idx = int(a[1:])
        page |= 1 << (_A_BASE_D + idx)
    for f in fec_bits:
        page |= 1 << _FEC_D[f]
    return {
        "raw_hex": f"0x{page:012X}",
        "selector": "IEEE 802.3",
        "nonce": nonce, "echoed_nonce": echoed_nonce,
        "ack": ack, "pause": pause,
        "abilities": list(abilities), "fec_bits": list(fec_bits),
    }


def resolve(local_abilities, partner_abilities, local_fec=(), partner_fec=()):
    """Priority resolution di Clause 73: HCD = abilità comune a priorità
    massima; poi risoluzione FEC (F0-F3 per 10/25G, obbligatorio ≥50G)."""
    common = sorted(set(local_abilities) & set(partner_abilities),
                    key=lambda a: PRIORITY[a])
    if not common:
        return {"hcd": None, "common": [], "fec": "—",
                "parallel_detect": "nessuna abilità comune → AN fallisce "
                "(in un PHY reale si resta in ABILITY_DETECT)"}
    hcd = common[-1]
    bit, name, lane_gbps, lanes, mod, fec_class = TECH_BY_BIT[hcd]
    if fec_class and "obbligatorio" in fec_class:
        fec = fec_class
    elif fec_class and "F2/F3" in fec_class:
        lf, pf = set(local_fec), set(partner_fec)
        if "F2" in lf or "F2" in pf:
            fec = "RS(528,514) — RS-FEC richiesto via F2"
        elif "F3" in lf or "F3" in pf:
            fec = "BASE-R (Clause 74) richiesto via F3"
        else:
            fec = "nessuno (né F2 né F3 richiesti)"
    elif fec_class:
        lf, pf = set(local_fec), set(partner_fec)
        if "F0" in lf and "F0" in pf and ("F1" in lf or "F1" in pf):
            fec = "BASE-R (Clause 74) — F0 comune e F1 richiesto"
        else:
            fec = "nessuno (Clause 74 non richiesto)"
    else:
        fec = "non previsto per questa abilità"
    return {"hcd": hcd, "hcd_name": name, "common": common,
            "lane_gbps": lane_gbps, "lanes": lanes, "modulation": mod,
            "total_gbps": lane_gbps * lanes, "fec": fec,
            "needs_training": lane_gbps >= 10.0}


def an_session(local_abilities, partner_abilities, local_fec=(),
               partner_fec=(), seed=7):
    """Sessione AN completa: pagine, macchina a stati con timeline, HCD.

    Timer da Table 73-7 (valori tipici nel range di clause):
    break_link_timer 67 ms, link_fail_inhibit_timer 510 ms (PHY con LT).
    La cadenza delle pagine DME è ~O(µs); qui si riportano i conteggi e i
    millisecondi cumulativi della macchina a stati (timeline indicativa)."""
    rng = np.random.default_rng(seed)
    nonce_l = int(rng.integers(1, 31))
    nonce_p = int(rng.integers(1, 31))
    if nonce_p == nonce_l:                        # nonce uguali → ritrasmette
        nonce_p = (nonce_p + 7) % 31 + 1
    res = resolve(local_abilities, partner_abilities, local_fec, partner_fec)

    pages = {
        "local_base": build_base_page(local_abilities, local_fec, nonce_l),
        "partner_base": build_base_page(partner_abilities, partner_fec,
                                        nonce_p),
        "local_ack": build_base_page(local_abilities, local_fec, nonce_l,
                                     echoed_nonce=nonce_p, ack=True),
        "partner_ack": build_base_page(partner_abilities, partner_fec,
                                       nonce_p, echoed_nonce=nonce_l,
                                       ack=True),
    }
    t = 0.0
    timeline = [{"t_ms": t, "state": "AN_ENABLE",
                 "note": "AN abilitato, DME sul lane 0"}]
    t += 67.0
    timeline.append({"t_ms": t, "state": "TRANSMIT_DISABLE",
                     "note": "break_link_timer scaduto (60–75 ms)"})
    timeline.append({"t_ms": t + 0.01, "state": "ABILITY_DETECT",
                     "note": "3 base page identiche ricevute → ability_match"})
    timeline.append({"t_ms": t + 0.02, "state": "ACKNOWLEDGE_DETECT",
                     "note": "pagina con Ack=1 ed echoed nonce corretto"})
    timeline.append({"t_ms": t + 0.03, "state": "COMPLETE_ACKNOWLEDGE",
                     "note": "ack_finished (nessuna next page in questo modello)"})
    if res["hcd"] is None:
        timeline.append({"t_ms": t + 0.04, "state": "ABILITY_DETECT",
                         "note": "nessuna HCD → si resta in negoziazione"})
    else:
        timeline.append({"t_ms": t + 0.04, "state": "AN_GOOD_CHECK",
                         "note": f"HCD = {res['hcd_name']}; parte il PMD "
                                 "control (link training) se previsto"})
        t_lt = t + 0.04 + (510.0 if res["needs_training"] else 1.0)
        timeline.append({"t_ms": t_lt, "state": "AN_GOOD",
                         "note": "link_status=OK entro il "
                                 "link_fail_inhibit_timer (510 ms)"})
    return {"pages": pages, "timeline": timeline, "resolution": res,
            "nonce_local": nonce_l, "nonce_partner": nonce_p}
