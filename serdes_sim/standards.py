"""Standards registry for LabPro: limits, verdict taxonomy, contracts.

This module is the ONLY place where a normative number (limit, threshold,
mask coordinate, reference-receiver constant) may be written down.  Every
other layer — physics blocks, procedures, panel builders, the UI, the
Academy cards — reads it from here, so a limit can never disagree with
itself between the model and the screen.

Three ideas are kept deliberately separate:

* ``SpecLimit``: a limit with its provenance (standard, clause, table,
  edition, reference plane, pattern, reference receiver) and a
  ``confidence`` flag.  ``"published"`` means the value was transcribed from
  the public standard text and may drive a *model* PASS/FAIL;
  ``"to-verify"`` means the value is quoted from public material but has not
  been checked against the licensed text, so it is shown as context only.
* The verdict taxonomy (``PASS``, ``FAIL``, ``MARGINAL``, ``PROXY``,
  ``NOT_APPLICABLE``, ``NOT_ASSESSED``, ``ERROR``) with a ``verdict()``
  object that always carries basis, evidence and source.  ``compliance``
  is a separate field and is never PASS in this project: LabPro does not
  execute a certified clause procedure with traceable instruments.
* ``measurement_contracts``: for the active profile, which clause governs
  each measurement, what LabPro implements, and which claim is allowed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math

IEEE_8023 = "https://www.ieee802.org/3/"
IEEE_COM = "https://www.ieee802.org/3/ad_hoc/COM/public/"
OIF_IA = "https://www.oiforum.com/technical-work/implementation-agreements-ias/"

# ---------------------------------------------------------------------------
# Verdict taxonomy (closed)
# ---------------------------------------------------------------------------
PASS = "PASS"
FAIL = "FAIL"
MARGINAL = "MARGINAL"            # |value − limit| within the declared uncertainty
PROXY = "PROXY"                  # measured with a declared proxy: no pass/fail
NOT_APPLICABLE = "NOT_APPLICABLE"
NOT_ASSESSED = "NOT_ASSESSED"    # no limit, unverified limit, or blocker
ERROR = "ERROR"
VERDICTS = frozenset({PASS, FAIL, MARGINAL, PROXY, NOT_APPLICABLE,
                      NOT_ASSESSED, ERROR})
COMPLIANCE_VALUES = frozenset({NOT_ASSESSED, NOT_APPLICABLE})
BASES = frozenset({"clause-limit", "model-limit", "context-limit",
                   "proxy", "blocker", "checkpoint", "none"})

_LEGACY = {
    "WARN": NOT_ASSESSED, "NOT ASSESSED": NOT_ASSESSED,
    "NOT APPLICABLE": NOT_APPLICABLE, "MODEL PASS": PASS,
    "MODEL FAIL": FAIL, "ok": PASS, "OK": PASS, "na": NOT_APPLICABLE,
    "warn": FAIL, "fail": FAIL, "pass": PASS, "proxy": PROXY,
}


def normalize_status(value) -> str:
    """Map any legacy status string onto the closed taxonomy."""
    if value is None:
        return NOT_ASSESSED
    if value is True:
        return PASS
    if value is False:
        return FAIL
    s = str(value)
    if s in VERDICTS:
        return s
    return _LEGACY.get(s, _LEGACY.get(s.upper(), NOT_ASSESSED))


def verdict(model, *, compliance=NOT_ASSESSED, basis="none", evidence="",
            source=None, value=None, limit=None, cmp=None, unit=None,
            uncertainty=None, margin=None, note_it=None, note_en=None,
            limit_id=None, clause=None, confidence=None):
    """Build a verdict object.  ``model`` is what the LabPro model concludes;
    ``compliance`` is what may be claimed against the standard."""
    model = normalize_status(model)
    compliance = normalize_status(compliance)
    if compliance not in COMPLIANCE_VALUES:
        raise ValueError("compliance may only be NOT_ASSESSED or NOT_APPLICABLE")
    if basis not in BASES:
        raise ValueError(f"unknown verdict basis {basis!r}")
    return {
        "model": model, "compliance": compliance, "basis": basis,
        "evidence": evidence, "source": source, "value": value,
        "limit": limit, "cmp": cmp, "unit": unit,
        "uncertainty": uncertainty, "margin": margin,
        "note": {"it": note_it or "", "en": note_en or ""},
        "limit_id": limit_id, "clause": clause, "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Normative constants shared by the physics layer (single source of truth)
# ---------------------------------------------------------------------------
# TDECQ reference receiver, IEEE 802.3 Clause 121.8.5.3 structure.
TDECQ_TARGET_SER = 4.8e-4
TDECQ_Q_T = 3.414
TDECQ_HISTOGRAM_CENTERS_UI = (0.45, 0.55)
TDECQ_HISTOGRAM_WIDTH_UI = 0.04
TDECQ_REFERENCE_RX_BW_FRACTION = 0.5     # BT4 at 0.5·baud for PAM4
NRZ_REFERENCE_RX_BW_FRACTION = 0.75      # BT4 at 0.75·baud for NRZ masks
TDECQ_FFE_TAPS = 5
# COM, IEEE 802.3 Annex 93A with the 802.3ck 100GBASE-KR1 parameter set.
COM_KR1_THRESHOLD_DB = 3.0
COM_DER0 = 1e-4
# Transmitter linearity, IEEE 802.3ck (level separation mismatch ratio).
RLM_MIN_8023CK = 0.95
# SNDR linear-fit pulse length (Clause 120D.3.1.5 / 162.9.3.1 family).
SNDR_FIT_NP = 200
# PMD bit-error-ratio requirements used as clause limits for counted BER.
KP4_PMD_BER = 2.4e-4        # RS(544,514) PAM4 PMDs (802.3bs/cd/ck/cu/db/df)
KR4_PMD_BER = 5e-5          # RS(528,514) 25G NRZ PMDs (802.3bm Clause 95)
NRZ_UNCODED_BER = 1e-12     # 10GBASE-LR (Clause 52), no FEC
FEC_TARGET_FER = 1e-13      # post-FEC frame-loss target of the iid model
# Context-only JTOL mask shape (NOT a clause mask): −20 dB/decade to the
# corner frequency, then a floor.  Served as data so the client never
# computes physics.
JTOL_CONTEXT_MASK = {"floor_ui": 0.05, "slope_db_per_decade": -20.0,
                     "cap_ui": 5.0}


# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SpecLimit:
    id: str                      # tdecq, com, rlm, sndr, ber_prefec, er, ...
    measure: str
    unit: str
    limit: float | None          # None: not transcribed / no limit exists
    cmp: str | None              # "<=" or ">="
    standard: str
    clause: str
    table: str
    edition: str
    reference_plane: str
    pattern: str
    reference_rx: str
    implementation: str          # what LabPro runs for this measure
    confidence: str              # published | to-verify | none
    note_it: str
    note_en: str
    source: str = IEEE_8023

    def as_dict(self):
        return asdict(self)


def _lim(id, measure, unit, limit, cmp, standard, clause, table, edition,
         plane, pattern, ref_rx, implementation, confidence, note_it,
         note_en, source=IEEE_8023):
    if confidence not in ("published", "to-verify", "none"):
        raise ValueError(confidence)
    return SpecLimit(id, measure, unit, limit, cmp, standard, clause, table,
                     edition, plane, pattern, ref_rx, implementation,
                     confidence, note_it, note_en, source)


_ED_2022 = "IEEE Std 802.3-2022"
_TDECQ_RX = "BT4 0.5·Bd + 5-tap T-spaced FFE"
_TDECQ_IMPL = "clause-structured"
_TDECQ_NOTE_IT = ("Struttura di 121.8.5.3 (BT4, FFE 5 tap, finestre 0.45/0.55 UI, "
                  "SER 4.8e-4). σS del ricevitore numerico = 0: ideale dichiarato.")
_TDECQ_NOTE_EN = ("121.8.5.3 structure (BT4, 5-tap FFE, 0.45/0.55 UI windows, "
                  "SER 4.8e-4). Numerical receiver σS = 0: declared ideal.")


def _tdecq(standard, clause, table, edition=_ED_2022, limit=3.4,
           confidence="published", note_it=_TDECQ_NOTE_IT,
           note_en=_TDECQ_NOTE_EN, source=IEEE_8023):
    return _lim("tdecq", "TDECQ", "dB", limit, "<=", standard, clause, table,
                edition, "TP2 · optical PMD transmitter output", "SSPRQ",
                _TDECQ_RX, _TDECQ_IMPL, confidence, note_it, note_en, source)


def _ber(limit, standard, clause, edition=_ED_2022, confidence="published",
         plane="post-slicer, pre-FEC", note_it="", note_en=""):
    return _lim("ber_prefec", "BER pre-FEC", "", limit, "<=", standard,
                clause, "PMD BER requirement", edition, plane,
                "active pattern", "LabPro RX (ADC/CDR/FSE/DFE)",
                "counted-with-confidence", confidence,
                note_it or ("Confronto fra il limite superiore CL95 della BER "
                            "contata sul record e il requisito BER del PMD; il "
                            "tempo di osservazione di clause non è rispettato."),
                note_en or ("Compares the CL95 upper bound of the BER counted "
                            "on the record with the PMD BER requirement; the "
                            "clause observation time is not met."))


def _er(limit, standard, clause, table, confidence="to-verify"):
    return _lim("er", "Extinction ratio", "dB", limit, ">=", standard, clause,
                table, _ED_2022, "TP2 · optical PMD transmitter output",
                "active pattern", "level means over symbol runs",
                "clause-structured", confidence,
                "Livelli medi sui run di simboli identici (finestra centrale "
                "20%): struttura del metodo di clause, valore del limite da "
                "verificare sul testo.",
                "Level means over runs of identical symbols (central 20% "
                "window): clause-method structure, limit value to verify "
                "against the text.")


def _oma(standard, clause, table):
    return _lim("oma_outer", "OMA outer", "dBm", None, ">=", standard, clause,
                table, _ED_2022, "TP2 · optical PMD transmitter output",
                "active pattern", "level means over symbol runs",
                "clause-structured", "none",
                "Il limite OMA outer per-profilo non è ancora trascritto: il "
                "valore misurato è mostrato come contesto.",
                "The per-profile OMA outer limit is not yet transcribed: the "
                "measured value is shown as context.")


def _com(limit, standard, clause, table, confidence, applicable=True,
         note_it="", note_en="", source=IEEE_8023):
    return _lim("com", "COM", "dB", limit, ">=", standard, clause, table,
                _ED_2022 if standard.startswith("IEEE") else "OIF CEI IA",
                "passive electrical channel incl. package",
                "n/a (statistical)", "Annex 93A reference RX (CTLE + DFE)",
                "annex-subset" if applicable else "not-applicable",
                confidence,
                note_it or ("Subset di Annex 93A con il set di parametri "
                            "100GBASE-KR1: soglia pubblica 3 dB, DER₀ 1e-4."),
                note_en or ("Annex 93A subset with the 100GBASE-KR1 parameter "
                            "set: public 3 dB threshold, DER₀ 1e-4."),
                source)


def _rlm(limit, standard, clause, table, confidence):
    return _lim("rlm", "RLM", "", limit, ">=", standard, clause, table,
                _ED_2022, "transmitter output after the clause reference receiver",
                "transmitter linearity test pattern (clause) — LabPro: active pattern",
                "clause level-separation formula on measured level means",
                "proxy", confidence,
                "Formula di clause RLM = min(3·ES1, 3·ES2, 2−3·ES1, 2−3·ES2) sui "
                "livelli medi misurati; il pattern di linearità di clause non è "
                "applicato, quindi il risultato resta un proxy dichiarato.",
                "Clause formula RLM = min(3·ES1, 3·ES2, 2−3·ES1, 2−3·ES2) on the "
                "measured level means; the clause linearity test pattern is not "
                "applied, so the result remains a declared proxy.")


def _sndr(limit, standard, clause, table, confidence):
    return _lim("sndr", "SNDR", "dB", limit, ">=", standard, clause, table,
                _ED_2022, "transmitter output test point",
                "PRBS13Q (clause) — LabPro: active pattern",
                f"linear-fit pulse response, Np={SNDR_FIT_NP} UI, M=analog sps",
                "clause-structured", confidence,
                "Fit lineare del pulse su tutte le fasi (Y=P·X), σe dal residuo; "
                "σn non è misurata separatamente (inclusa nel residuo).",
                "Linear pulse fit over all phases (Y=P·X), σe from the residual; "
                "σn is not measured separately (folded into the residual).")


def _mask(standard, clause, table, coords, confidence, note_it, note_en):
    lim = _lim("eye_mask", "TX eye mask hit ratio", "", coords.get("hit_ratio"),
               "<=", standard, clause, table, _ED_2022,
               "TP2 after BT4 0.75·Bd reference receiver", "active pattern",
               "BT4 0.75·Bd", "clause-structured", confidence, note_it, note_en)
    return lim, coords


# Eye-mask geometry data (normalized: x in UI, y in 0/1 level units).
# Geometry declared as: central hexagon (X1,0.5)-(X2,Y1)-(1−X2,Y1)-(1−X1,0.5)-
# (1−X2,1−Y1)-(X2,1−Y1) plus forbidden bands y ≥ 1+Y3 and y ≤ −Y3.
EYE_MASKS = {
    "10GBASE-LR": {"x1": 0.25, "x2": 0.40, "x3": 0.45, "y1": 0.25, "y2": 0.28,
                   "y3": 0.40, "hit_ratio": 5e-5, "geometry": "declared"},
}

LIMITS_BY_INTERFACE: dict[str, tuple[SpecLimit, ...]] = {
    "400GBASE-DR4": (
        _tdecq("IEEE 802.3bs", "Clause 124 · 124.8.5 (method 121.8.5)", "Table 124-6"),
        _er(3.5, "IEEE 802.3bs", "Clause 124 · 124.8.4", "Table 124-6"),
        _oma("IEEE 802.3bs", "Clause 124 · 124.8.4", "Table 124-6"),
        _ber(KP4_PMD_BER, "IEEE 802.3bs", "Clause 124 (PMD BER, RS(544,514) PCS)"),
    ),
    "400GBASE-FR8": (
        _tdecq("IEEE 802.3bs", "Clause 122 · 122.8.5 (method 121.8.5)", "Table 122-6"),
        _er(4.5, "IEEE 802.3bs", "Clause 122 · 122.8.4", "Table 122-6"),
        _oma("IEEE 802.3bs", "Clause 122 · 122.8.4", "Table 122-6"),
        _ber(KP4_PMD_BER, "IEEE 802.3bs", "Clause 122 (PMD BER, RS(544,514) PCS)"),
    ),
    "100GBASE-FR1": (
        _tdecq("IEEE 802.3cu", "Clause 140 · 140.7.5 (method 121.8.5)", "Table 140-6"),
        _er(3.5, "IEEE 802.3cu", "Clause 140 · 140.7.4", "Table 140-6"),
        _oma("IEEE 802.3cu", "Clause 140 · 140.7.4", "Table 140-6"),
        _ber(KP4_PMD_BER, "IEEE 802.3cu", "Clause 140 (PMD BER, RS(544,514) PCS)"),
    ),
    "100GBASE-LR1": (
        _tdecq("IEEE 802.3cu", "Clause 140 · 140.7.5 (method 121.8.5)", "Table 140-6"),
        _er(3.5, "IEEE 802.3cu", "Clause 140 · 140.7.4", "Table 140-6"),
        _oma("IEEE 802.3cu", "Clause 140 · 140.7.4", "Table 140-6"),
        _ber(KP4_PMD_BER, "IEEE 802.3cu", "Clause 140 (PMD BER, RS(544,514) PCS)"),
    ),
    "100GBASE-SR1": (
        _tdecq("IEEE 802.3db", "Clause 167 · TDECQ (method 121.8.5)", "Table 167-6",
               limit=None, confidence="none",
               note_it="Il limite TDECQ di 100GBASE-SR1 non è trascritto (discussione "
                       "pubblica 4.3–4.5 dB): nessun confronto finché non è verificato "
                       "sul testo di Table 167-6.",
               note_en="The 100GBASE-SR1 TDECQ limit is not transcribed (public "
                       "discussion 4.3–4.5 dB): no comparison until verified against "
                       "the Table 167-6 text."),
        _er(2.5, "IEEE 802.3db", "Clause 167", "Table 167-6"),
        _oma("IEEE 802.3db", "Clause 167", "Table 167-6"),
        _ber(KP4_PMD_BER, "IEEE 802.3db", "Clause 167 (PMD BER, RS(544,514) PCS)"),
    ),
    "800GBASE-DR8": (
        _tdecq("IEEE 802.3df", "800GBASE-DR8 PMD clause (method 121.8.5)",
               "PMD transmit characteristics table", edition="IEEE Std 802.3df-2024",
               confidence="to-verify",
               note_it=_TDECQ_NOTE_IT + " Numero di tabella 802.3df da verificare.",
               note_en=_TDECQ_NOTE_EN + " 802.3df table number to verify."),
        _er(3.5, "IEEE 802.3df", "800GBASE-DR8 PMD clause", "PMD transmit table"),
        _oma("IEEE 802.3df", "800GBASE-DR8 PMD clause", "PMD transmit table"),
        _ber(KP4_PMD_BER, "IEEE 802.3df", "800GBASE-DR8 PMD (RS(544,514) PCS)",
             edition="IEEE Std 802.3df-2024"),
    ),
    "100GBASE-SR4": (
        _lim("tdec", "TDEC", "dB", None, "<=", "IEEE 802.3bm", "Clause 95 · 95.8.5",
             "Table 95-6", _ED_2022, "TP2", "PRBS31 / SSPR", "BT4 0.75·Bd",
             "not-implemented", "none",
             "TDEC (NRZ) non è implementato: per i profili NRZ il banco espone "
             "solo maschere e livelli.",
             "TDEC (NRZ) is not implemented: NRZ profiles expose only masks and "
             "levels."),
        _ber(KR4_PMD_BER, "IEEE 802.3bm", "Clause 95 (PMD BER, RS(528,514) PCS)"),
    ),
    "10GBASE-LR": (
        _mask("IEEE 802.3ae", "Clause 52 · 52.9.7", "Table 52-12",
              EYE_MASKS["10GBASE-LR"], "to-verify",
              "Coordinate della maschera 10GBASE-LR (X1 0.25, X2 0.40, X3 0.45, "
              "Y1 0.25, Y2 0.28, Y3 0.40); geometria dichiarata (esagono X1/X2/Y1 "
              "+ bande ±Y3) da verificare sulla Figure 52-13.",
              "10GBASE-LR mask coordinates (X1 0.25, X2 0.40, X3 0.45, Y1 0.25, "
              "Y2 0.28, Y3 0.40); declared geometry (X1/X2/Y1 hexagon + ±Y3 "
              "bands) to verify against Figure 52-13.")[0],
        _er(3.5, "IEEE 802.3ae", "Clause 52 · 52.9.4", "Table 52-12"),
        _ber(NRZ_UNCODED_BER, "IEEE 802.3ae", "Clause 52 (PMD BER, no FEC)"),
    ),
    "25GBASE-LR": (
        _er(3.5, "IEEE 802.3cc", "Clause 114", "Table 114-6"),
        _ber(KR4_PMD_BER, "IEEE 802.3cc", "Clause 114 (PMD BER with RS-FEC)",
             confidence="to-verify"),
    ),
    "25GBASE-CR": (
        _ber(None, "IEEE 802.3by", "Clause 110 (PMD BER with RS-FEC)",
             confidence="none",
             note_it="Requisito BER di 25GBASE-CR non trascritto.",
             note_en="25GBASE-CR BER requirement not transcribed."),
    ),
    "50GBASE-KR": (
        _com(COM_KR1_THRESHOLD_DB, "IEEE 802.3cd", "Clause 137 · channel COM",
             "Table 137-? (COM parameters)", "published", applicable=False,
             note_it="COM ≥ 3 dB è il limite di clause; il set di parametri Annex "
                     "93A implementato è quello 100GBASE-KR1 a 53.125 GBd, quindi "
                     "a 26.5625 GBd il calcolo non è applicabile.",
             note_en="COM ≥ 3 dB is the clause limit; the implemented Annex 93A "
                     "parameter set is the 53.125 GBd 100GBASE-KR1 one, so at "
                     "26.5625 GBd the computation is not applicable."),
        _rlm(0.95, "IEEE 802.3cd", "Clause 136 · 136.9.3.1", "Table 136-8", "to-verify"),
        _sndr(None, "IEEE 802.3cd", "Clause 136 · 136.9.3.1", "Table 136-8", "none"),
        _ber(KP4_PMD_BER, "IEEE 802.3cd", "Clause 137 (PMD BER, RS(544,514) PCS)"),
    ),
    "100GBASE-KR1": (
        _com(COM_KR1_THRESHOLD_DB, "IEEE 802.3ck", "Clause 162 · Annex 93A",
             "Clause 162 COM parameter tables", "published"),
        _rlm(RLM_MIN_8023CK, "IEEE 802.3ck", "Clause 162 · 162.9.3.1", "Table 162-10",
             "published"),
        _sndr(32.5, "IEEE 802.3ck", "Clause 162 · 162.9.3.1", "Table 162-10",
              "to-verify"),
        _ber(KP4_PMD_BER, "IEEE 802.3ck", "Clause 162 (PMD BER, RS(544,514) PCS)"),
    ),
    "100GAUI-1 C2M": (
        _com(None, "IEEE 802.3ck", "Annex 120G (C2M)", "—", "none", applicable=False,
             note_it="100GAUI-1 C2M è specificato con maschere d'occhio host/modulo "
                     "(VEC/VEO, Annex 120G), non con COM: non applicabile.",
             note_en="100GAUI-1 C2M is specified with host/module eye masks "
                     "(VEC/VEO, Annex 120G), not with COM: not applicable."),
        _rlm(RLM_MIN_8023CK, "IEEE 802.3ck", "Annex 120G", "Table 120G-?", "to-verify"),
        _sndr(None, "IEEE 802.3ck", "Annex 120G", "Table 120G-?", "none"),
        _ber(KP4_PMD_BER, "IEEE 802.3ck", "Annex 120G (AUI BER with RS(544,514))",
             confidence="to-verify"),
    ),
    "CEI-56G-LR": (
        _com(3.0, "OIF CEI-4.0/5.x", "CEI-56G-LR · channel COM", "IA table",
             "to-verify", applicable=False,
             note_it="CEI-56G-LR usa COM ≥ 3 dB con un set di parametri OIF: il "
                     "set implementato è quello 802.3ck KR1, quindi non applicabile.",
             note_en="CEI-56G-LR uses COM ≥ 3 dB with an OIF parameter set: the "
                     "implemented set is the 802.3ck KR1 one, so not applicable.",
             source=OIF_IA),
    ),
    "CEI-112G-VSR": (
        _com(None, "OIF CEI-5.x", "CEI-112G-VSR · eye mask based", "—", "none",
             applicable=False,
             note_it="VSR è specificato con maschere d'occhio host/modulo, non COM.",
             note_en="VSR is specified with host/module eye masks, not COM.",
             source=OIF_IA),
    ),
    "CEI-224G-LR": (
        _com(3.0, "OIF CEI-224G (draft)", "CEI-224G-LR · channel COM", "draft",
             "to-verify", applicable=False,
             note_it="Progetto OIF in corso: soglia e parametri non definitivi.",
             note_en="OIF project in progress: threshold and parameters not final.",
             source=OIF_IA),
    ),
    "200G/lane C2C": (),
}


def limits_for_interface(interface: str | None) -> dict[str, SpecLimit]:
    if not interface:
        return {}
    return {lim.id: lim for lim in LIMITS_BY_INTERFACE.get(interface, ())}


def all_limits():
    for interface, lims in LIMITS_BY_INTERFACE.items():
        for lim in lims:
            yield interface, lim


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def compare(value, limit, cmp):
    """Signed margin: positive means the value satisfies the limit."""
    if cmp == "<=":
        return limit - value
    if cmp == ">=":
        return value - limit
    raise ValueError(cmp)


def evaluate_limit(lim: SpecLimit | None, value, *, uncertainty=None,
                   implementation=None, evidence="", fail_reason=None,
                   applicable=True):
    """Turn a measured value into a verdict against a registry limit.

    * ``implementation`` overrides the limit's declared implementation
      (``"proxy"`` forces PROXY, ``"not-applicable"`` forces NOT_APPLICABLE).
    * A limit with ``confidence != "published"`` never produces PASS/FAIL.
    * With an uncertainty ``u``, |margin| < u gives MARGINAL.
    """
    impl = implementation or (lim.implementation if lim else "none")
    unit = lim.unit if lim else None
    src = lim.source if lim else None
    clause = f"{lim.standard} · {lim.clause}" if lim else None
    limit_id = lim.id if lim else None
    if not applicable or impl == "not-applicable":
        return verdict(NOT_APPLICABLE, compliance=NOT_APPLICABLE, basis="none",
                       evidence=evidence, source=src, value=value, unit=unit,
                       limit=(lim.limit if lim else None),
                       cmp=(lim.cmp if lim else None), limit_id=limit_id,
                       clause=clause, note_it=(lim.note_it if lim else None),
                       note_en=(lim.note_en if lim else None),
                       confidence=(lim.confidence if lim else None))
    if value is None:
        model = FAIL if fail_reason else NOT_ASSESSED
        return verdict(model, basis="model-limit" if fail_reason else "none",
                       evidence=fail_reason or evidence, source=src, unit=unit,
                       limit=(lim.limit if lim else None),
                       cmp=(lim.cmp if lim else None), limit_id=limit_id,
                       clause=clause, note_it=(lim.note_it if lim else None),
                       note_en=(lim.note_en if lim else None),
                       confidence=(lim.confidence if lim else None))
    if impl in ("proxy", "declared-proxy"):
        return verdict(PROXY, basis="proxy", evidence=evidence, source=src,
                       value=value, unit=unit,
                       limit=(lim.limit if lim else None),
                       cmp=(lim.cmp if lim else None), limit_id=limit_id,
                       clause=clause, note_it=(lim.note_it if lim else None),
                       note_en=(lim.note_en if lim else None),
                       confidence=(lim.confidence if lim else None))
    if lim is None or lim.limit is None:
        return verdict(NOT_ASSESSED, basis="none", evidence=evidence, source=src,
                       value=value, unit=unit, limit_id=limit_id, clause=clause,
                       note_it=(lim.note_it if lim else None),
                       note_en=(lim.note_en if lim else None),
                       confidence=(lim.confidence if lim else None))
    margin = compare(float(value), float(lim.limit), lim.cmp)
    if lim.confidence != "published":
        return verdict(NOT_ASSESSED, basis="context-limit", evidence=evidence,
                       source=src, value=value, limit=lim.limit, cmp=lim.cmp,
                       unit=unit, uncertainty=uncertainty, margin=margin,
                       limit_id=limit_id, clause=clause, note_it=lim.note_it,
                       note_en=lim.note_en, confidence=lim.confidence)
    u = float(uncertainty) if uncertainty is not None else 0.0
    if margin - u >= 0:
        model = PASS
    elif margin + u < 0:
        model = FAIL
    else:
        model = MARGINAL
    return verdict(model, basis="clause-limit", evidence=evidence, source=src,
                   value=value, limit=lim.limit, cmp=lim.cmp, unit=unit,
                   uncertainty=uncertainty, margin=margin, limit_id=limit_id,
                   clause=clause, note_it=lim.note_it, note_en=lim.note_en,
                   confidence=lim.confidence)


def ber_verdict(errors, bits, lim: SpecLimit | None, confidence=0.95,
                model_threshold=None):
    """Counted-BER verdict from the Clopper-Pearson interval.

    PASS if the CL upper bound is below the limit, FAIL if the lower bound is
    above it, MARGINAL in between.  ``model_threshold`` (iid FEC model) is
    evaluated the same way and returned separately.
    """
    from scipy import stats as _st
    errors = int(errors)
    bits = int(bits)
    if bits <= 0:
        return (verdict(NOT_ASSESSED, basis="none",
                        evidence="no bits observed"),
                None)
    alpha = 1.0 - confidence
    lo = 0.0 if errors == 0 else float(_st.beta.ppf(alpha / 2, errors, bits - errors + 1))
    hi = (1.0 if errors == bits
          else float(_st.beta.ppf(1 - alpha / 2, errors + 1, bits - errors)))
    if errors == 0:
        hi = float(-math.expm1(math.log1p(-confidence) / bits))   # one-sided
    ber = errors / bits
    bound = {"ber": ber, "errors": errors, "bits": bits, "cl": confidence,
             "lower": lo, "upper": hi}

    def _against(limit, basis, clause, src, conf, note_it, note_en):
        if limit is None:
            return verdict(NOT_ASSESSED, basis="none",
                           evidence=f"{errors} err / {bits} bit", value=ber,
                           uncertainty=hi - ber, clause=clause, source=src)
        if conf != "published":
            return verdict(NOT_ASSESSED, basis="context-limit", value=ber,
                           limit=limit, cmp="<=", uncertainty=hi - ber,
                           margin=limit - ber, clause=clause, source=src,
                           evidence=f"{errors} err / {bits} bit · CL95 ≤ {hi:.3g}",
                           note_it=note_it, note_en=note_en, confidence=conf)
        if hi <= limit:
            model = PASS
        elif lo > limit:
            model = FAIL
        else:
            model = MARGINAL
        return verdict(model, basis=basis, value=ber, limit=limit, cmp="<=",
                       uncertainty=hi - ber, margin=limit - ber, clause=clause,
                       source=src, confidence=conf, note_it=note_it,
                       note_en=note_en,
                       evidence=(f"{errors} err / {bits} bit · CL95 "
                                 f"[{lo:.3g}, {hi:.3g}]"))

    clause_v = _against(lim.limit if lim else None, "clause-limit",
                        (f"{lim.standard} · {lim.clause}" if lim else None),
                        (lim.source if lim else None),
                        (lim.confidence if lim else "none"),
                        (lim.note_it if lim else None),
                        (lim.note_en if lim else None))
    clause_v["bound"] = bound
    model_v = None
    if model_threshold is not None:
        model_v = _against(float(model_threshold), "model-limit",
                           "LabPro iid RS model (FER 1e-13)", None, "published",
                           "Soglia del modello binomiale iid del codec RS: non è "
                           "un limite di clause.",
                           "Threshold of the iid binomial RS-codec model: not a "
                           "clause limit.")
        model_v["bound"] = bound
    return clause_v, model_v


def jtol_context_mask_ui(freq_mhz, corner_mhz, floor_ui=None):
    """Context-only JTOL mask amplitude at ``freq_mhz`` (data, not clause)."""
    m = JTOL_CONTEXT_MASK
    floor = m["floor_ui"] if floor_ui is None else float(floor_ui)
    ratio = max(1.0, float(corner_mhz) / max(float(freq_mhz), 1e-9))
    # −20 dB/decade in amplitude is ratio**1; the exponent keeps the slope
    # a single declared datum instead of an implicit 1/f.
    exponent = -m["slope_db_per_decade"] / 20.0
    return min(m["cap_ui"], floor * ratio ** exponent)


# ---------------------------------------------------------------------------
# Per-interface clause map and measurement contracts
# ---------------------------------------------------------------------------
INTERFACE_CLAUSES = {
    "10GBASE-LR": {"standard": "IEEE 802.3ae", "pmd": "Clause 52", "pcs": "Clause 49",
                   "fec": "none", "tx": "52.9 (eye mask 52.9.7)", "rx": "52.9.9 (stressed receiver)"},
    "25GBASE-LR": {"standard": "IEEE 802.3cc", "pmd": "Clause 114", "pcs": "Clause 107",
                   "fec": "Clause 108 RS(528,514) (optional)", "tx": "114.7", "rx": "114.7"},
    "25GBASE-CR": {"standard": "IEEE 802.3by", "pmd": "Clause 110", "pcs": "Clause 107",
                   "fec": "Clause 108 RS(528,514)", "tx": "110.8 (Clause 92-style)", "rx": "110.8"},
    "100GBASE-SR4": {"standard": "IEEE 802.3bm", "pmd": "Clause 95", "pcs": "Clause 82",
                     "fec": "Clause 91 RS(528,514)", "tx": "95.8 (TDEC 95.8.5)", "rx": "95.8"},
    "50GBASE-KR": {"standard": "IEEE 802.3cd", "pmd": "Clause 137", "pcs": "Clause 133",
                   "fec": "Clause 134 RS(544,514)", "tx": "136.9.3 (SNDR/RLM)", "rx": "137 (COM, JTOL)"},
    "400GBASE-FR8": {"standard": "IEEE 802.3bs", "pmd": "Clause 122", "pcs": "Clause 119",
                     "fec": "Clause 119 RS(544,514)", "tx": "122.8.5 (TDECQ, method 121.8.5)",
                     "rx": "122.8.9 (stressed receiver)"},
    "400GBASE-DR4": {"standard": "IEEE 802.3bs", "pmd": "Clause 124", "pcs": "Clause 119",
                     "fec": "Clause 119 RS(544,514)", "tx": "124.8.5 (TDECQ, method 121.8.5)",
                     "rx": "124.8.9 (stressed receiver)", "channel": "Table 124-11"},
    "100GBASE-FR1": {"standard": "IEEE 802.3cu", "pmd": "Clause 140", "pcs": "Clause 82",
                     "fec": "Clause 91 RS(544,514)", "tx": "140.7.5 (TDECQ, method 121.8.5)",
                     "rx": "140.7 (stressed receiver)"},
    "100GBASE-LR1": {"standard": "IEEE 802.3cu", "pmd": "Clause 140", "pcs": "Clause 82",
                     "fec": "Clause 91 RS(544,514)", "tx": "140.7.5 (TDECQ, method 121.8.5)",
                     "rx": "140.7 (stressed receiver)"},
    "100GBASE-SR1": {"standard": "IEEE 802.3db", "pmd": "Clause 167", "pcs": "Clause 82",
                     "fec": "Clause 91 RS(544,514)", "tx": "167 (TDECQ/TECQ, method 121.8.5)",
                     "rx": "167 (stressed receiver)"},
    "100GAUI-1 C2M": {"standard": "IEEE 802.3ck", "pmd": "Annex 120G (C2M)", "pcs": "Clause 82",
                      "fec": "Clause 91 RS(544,514)", "tx": "120G (host/module eye VEC/VEO)",
                      "rx": "120G (stressed input)"},
    "100GBASE-KR1": {"standard": "IEEE 802.3ck", "pmd": "Clause 162", "pcs": "Clause 82",
                     "fec": "Clause 91 RS(544,514)", "tx": "162.9.3 (SNDR/RLM)",
                     "rx": "162 (COM via Annex 93A, interference tolerance)"},
    "800GBASE-DR8": {"standard": "IEEE 802.3df", "pmd": "800GBASE-DR8 PMD clause",
                     "pcs": "800G PCS", "fec": "RS(544,514)",
                     "tx": "TDECQ (method 121.8.5)", "rx": "stressed receiver"},
    "CEI-56G-LR": {"standard": "OIF CEI-4.0/5.x", "pmd": "CEI-56G-LR", "pcs": "outside CEI",
                   "fec": "outside CEI", "tx": "CEI TX (SNDR/RLM)", "rx": "CEI COM/JTOL"},
    "CEI-112G-VSR": {"standard": "OIF CEI-5.x", "pmd": "CEI-112G-VSR", "pcs": "outside CEI",
                     "fec": "outside CEI", "tx": "CEI eye masks", "rx": "CEI stressed input"},
    "CEI-224G-LR": {"standard": "OIF CEI-224G (draft)", "pmd": "CEI-224G-LR", "pcs": "outside CEI",
                    "fec": "outside CEI", "tx": "draft", "rx": "draft"},
    "200G/lane C2C": {"standard": "IEEE P802.3dj", "pmd": "draft C2C", "pcs": "draft",
                      "fec": "draft (concatenated)", "tx": "draft", "rx": "draft"},
}


def measurement_contracts(cfg, active_profile=None, active_meta=None):
    """Per-profile contract rows: measure → clause → implementation → claim.

    Applicability comes from the configuration; clause text and limits come
    from the active interface.  Without an active profile the rows fall back
    to the generic 802.3 method references (labelled as such).
    """
    active_meta = active_meta or {}
    interface = active_meta.get("interface")
    cl = INTERFACE_CLAUSES.get(interface, {})
    standard = active_meta.get("standard") or "IEEE 802.3 profile required"
    lims = limits_for_interface(interface)
    optical_pam4 = cfg.link_medium == "optical" and cfg.modulation == "PAM4"
    electrical_pam4 = cfg.link_medium == "copper" and cfg.modulation == "PAM4"
    kr1_rate = abs(cfg.symbol_rate_hz - 53.125e9) < 1.0
    com_lim = lims.get("com")
    com_applicable = (electrical_pam4 and kr1_rate
                      and (com_lim is None or com_lim.implementation != "not-applicable"))
    is_oif = standard.startswith("OIF")
    src = active_meta.get("source") or IEEE_8023

    def row(mid, measure, clause, plane, applicable, implementation,
            note_it, note_en, source=src, limit=None):
        return {
            "id": mid, "measure": measure, "standard": standard,
            "clause": clause, "reference_plane": plane,
            "applicable": bool(applicable), "implementation": implementation,
            "compliance": NOT_ASSESSED if applicable else NOT_APPLICABLE,
            "note": {"it": note_it, "en": note_en}, "source": source,
            "limit": (limit.as_dict() if limit is not None else None),
        }

    tdecq_clause = cl.get("tx", "121.8.5 (generic method)") if optical_pam4 else "—"
    # SNDR/RLM sono metriche del trasmettitore ELETTRICO (120D.3.1 / 136 / 162):
    # su un PMD ottico restano contesto, non requisiti della clausola PMD.
    if cfg.link_medium == "optical":
        tx_clause = "120D.3.1 method as context (not a requirement of the optical PMD clause)"
    else:
        tx_clause = cl.get("tx", "120D.3.1 (generic method)")
    rows = [
        row("com", "COM",
            (com_lim.clause if com_lim else ("Annex 93A · 100GBASE-KR1 parameter set"
                                             if electrical_pam4 else "—")),
            "passive electrical channel incl. declared TX/RX package",
            com_applicable,
            "annex-subset" if com_applicable else "not-applicable",
            ("DER₀=1e-4, FFE/CTLE/DFE prescritti e casi package; manca il set "
             "completo di S-parameter vittima/NEXT/FEXT per la conformità."),
            ("DER₀=1e-4, prescribed FFE/CTLE/DFE and package cases; a complete "
             "victim/NEXT/FEXT S-parameter set is still required for compliance."),
            IEEE_COM if not is_oif else src, com_lim),
        row("tdecq", "TDECQ", tdecq_clause,
            "optical PMD measurement point after the reference receiver",
            optical_pam4, "clause-structured" if optical_pam4 else "not-applicable",
            ("Struttura 121.8.5.3 con SSPRQ completo nella procedura DR4; stress "
             "di riflessione/polarizzazione, incertezza strumentale tracciabile e "
             "golden correlation restano blocchi espliciti."),
            ("121.8.5.3 structure with the full SSPRQ period in the DR4 procedure; "
             "reflection/polarization stress, traceable instrument uncertainty and "
             "golden correlation remain explicit blockers."),
            src, lims.get("tdecq")),
        row("sndr", "SNDR", tx_clause if cfg.modulation == "PAM4" else "—",
            "specified electrical or optical transmitter test point",
            cfg.modulation == "PAM4", "clause-structured",
            ("Fit lineare del pulse su tutte le fasi (Np=200 UI); σn non separata; "
             "il pattern di clause (PRBS13Q) non è imposto."),
            ("Linear pulse fit over all phases (Np=200 UI); σn not separated; "
             "the clause pattern (PRBS13Q) is not enforced."),
            src, lims.get("sndr")),
        row("rlm", "RLM", tx_clause if cfg.modulation == "PAM4" else "—",
            "transmitter output after the clause reference receiver",
            cfg.modulation == "PAM4", "proxy",
            ("Formula di clause sui livelli medi misurati con il pattern attivo; "
             "il pattern di linearità di clause non è applicato: proxy dichiarato."),
            ("Clause formula on level means measured with the active pattern; "
             "the clause linearity pattern is not applied: declared proxy."),
            src, lims.get("rlm")),
        row("optical_levels", "OMA / ER / P0…P3",
            (cl.get("tx", "PMD transmitter characteristics").split(" (")[0]
             if cfg.link_medium == "optical" else "—"),
            "optical PMD TP2", cfg.link_medium == "optical", "clause-structured",
            ("Livelli medi sui run di simboli identici (finestra centrale 20%); "
             "i limiti OMA per profilo non sono ancora trascritti."),
            ("Level means over runs of identical symbols (central 20% window); "
             "per-profile OMA limits are not transcribed yet."),
            src, lims.get("er")),
        row("eye_mask", "TX eye mask (NRZ)",
            cl.get("tx", "—") if cfg.modulation == "NRZ" else "—",
            "TP2 after BT4 0.75·Bd reference receiver",
            cfg.modulation == "NRZ" and cfg.link_medium == "optical",
            "clause-structured" if "eye_mask" in lims else "not-implemented",
            ("Maschera valutata come dato server-side; la geometria è dichiarata e "
             "da verificare sulla figura di clause."),
            ("Mask evaluated server-side as data; the geometry is declared and to "
             "be verified against the clause figure."),
            src, lims.get("eye_mask")),
        row("eye_opening", "EH / EW @ BER",
            "profile-specific stressed-eye / transmitter procedure",
            "selected DCA node after declared reference filter", True,
            "gaussian-tail-extrapolation",
            ("Il BER target è esplicito, ma l'estrapolazione gaussiana delle code "
             "non sostituisce una maschera di clause o la calibrazione del RX."),
            ("The BER target is explicit, but Gaussian tail extrapolation is not a "
             "substitute for a clause mask or receiver calibration."), src),
        row("jitter", "RJ / DJ(δδ) / TJ",
            "profile-specific jitter output / tolerance clause",
            "selected clock or signal crossing plane", True, "dual-dirac-tail-fit",
            ("Decomposizione dual-Dirac dichiarata; servono pattern, banda e durata "
             "di clause prima di applicare un limite."),
            ("Declared dual-Dirac decomposition; a clause pattern, bandwidth and "
             "duration are required before a limit applies."), src),
        row("ber", "BER pre-FEC", cl.get("pmd", "active PMD clause") + " (PMD BER)",
            "post-slicer, pre-FEC", True, "counted-with-confidence",
            ("Intervallo Clopper–Pearson sul record; il tempo di osservazione di "
             "clause non è rispettato."),
            ("Clopper–Pearson interval on the record; the clause observation time "
             "is not met."), src, lims.get("ber_prefec")),
        row("fec", "FEC corrected / uncorrectable codewords",
            cl.get("fec", "active PCS/FEC clause"), "RS decoder output",
            cfg.fec_mode != "none", "in-path-codec",
            ("Il codice RS scelto è reale; distribuzione PCS su più lane, alignment "
             "marker e vettori di test di clause restano requisiti separati."),
            ("The selected RS code is real; full PCS lane distribution, alignment "
             "markers and clause test vectors remain separate requirements."), src),
        row("jtol", "JTOL", cl.get("rx", "profile-specific jitter tolerance mask"),
            "receiver input", electrical_pam4, "engineering-sweep",
            ("La bisezione del PJ misura la risposta del CDR del modello; la "
             "maschera di contesto è servita come dato, non è una maschera di clause."),
            ("PJ bisection measures the model CDR response; the context mask is "
             "served as data and is not a clause mask."), src),
        row("traffic", "throughput / FLR / latency",
            "MAC/PCS plus selected traffic-test method (IETF/ITU)",
            "L2 service interface", cfg.pattern == "eth", "engineering-benchmark",
            ("I frame Ethernet attraversano il modello, ma RFC 2544/Y.1564 non sono "
             "misure di conformità PHY IEEE 802.3."),
            ("Ethernet frames traverse the model, but RFC 2544/Y.1564 procedures are "
             "not IEEE 802.3 PHY compliance measurements."), src),
    ]
    return rows


def fmt_number(x):
    """Numero normativo leggibile: 2.4e-4, 3.4, 0.95 (mai 0.00024)."""
    if x is None:
        return "—"
    x = float(x)
    if x != 0 and abs(x) < 1e-2:
        mant, exp = f"{x:.1e}".split("e")
        return f"{mant.rstrip('0').rstrip('.')}e{int(exp)}"
    return f"{x:g}"


def registry_snapshot():
    """JSON-ready dump of the registry for reports and the UI."""
    return {
        "verdicts": sorted(VERDICTS),
        "constants": {
            "tdecq_target_ser": TDECQ_TARGET_SER, "tdecq_q_t": TDECQ_Q_T,
            "tdecq_histogram_centers_ui": list(TDECQ_HISTOGRAM_CENTERS_UI),
            "tdecq_histogram_width_ui": TDECQ_HISTOGRAM_WIDTH_UI,
            "tdecq_reference_rx_bw_fraction": TDECQ_REFERENCE_RX_BW_FRACTION,
            "com_kr1_threshold_db": COM_KR1_THRESHOLD_DB, "com_der0": COM_DER0,
            "rlm_min_8023ck": RLM_MIN_8023CK, "sndr_fit_np": SNDR_FIT_NP,
            "kp4_pmd_ber": KP4_PMD_BER, "kr4_pmd_ber": KR4_PMD_BER,
            "nrz_uncoded_ber": NRZ_UNCODED_BER, "fec_target_fer": FEC_TARGET_FER,
            "jtol_context_mask": dict(JTOL_CONTEXT_MASK),
        },
        "limits": {iface: [lim.as_dict() for lim in lims]
                   for iface, lims in LIMITS_BY_INTERFACE.items()},
        "eye_masks": EYE_MASKS,
        "interface_clauses": INTERFACE_CLAUSES,
    }
