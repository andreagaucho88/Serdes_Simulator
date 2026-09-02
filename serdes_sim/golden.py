"""Correlazione con golden instrument / golden vector.

Un dataset golden è un file JSON con una waveform ottica catturata (o
sintetica), i simboli trasmessi e i valori di riferimento riportati dallo
strumento (TDECQ, OMA outer, ER).  LabPro esegue la propria misura sulla
stessa waveform e riporta i delta con un verdetto:

* ``source == "instrument"`` (DCA reale, waveform esportata): il verdetto è
  del modello (PASS/FAIL entro tolleranza) e la conformità resta
  NOT_ASSESSED — ma la DR4 può finalmente chiudere lo step "golden
  correlation" invece di lasciarlo bloccante;
* ``source == "synthetic-labpro"`` (esempio generato dal banco): serve solo
  a esercitare la pipeline, quindi il verdetto è PROXY (auto-correlazione).

Schema (``labpro-golden/1``)::

    {"schema": "labpro-golden/1", "source": "instrument" | "synthetic-labpro",
     "instrument": "Keysight N1000A + N1092E", "interface": "400GBASE-DR4",
     "symbol_rate_hz": 53.125e9, "samples_per_ui": 8,
     "modulation": "PAM4", "mapping": "gray",
     "symbols": [0..3 ...], "waveform_w": [W ...],
     "reference": {"tdecq_db": 2.9, "oma_outer_dbm": 0.4, "er_db": 4.6,
                   "tolerance_db": 0.3}}
"""

from __future__ import annotations

import math
import time

import numpy as np

from .blocks.metrics import optical_levels_runs, tdecq_report
from .blocks.stimulus import get_modulation
from .standards import (FAIL, NOT_ASSESSED, PASS, PROXY, limits_for_interface,
                        verdict)

GOLDEN_SCHEMA = "labpro-golden/1"
DEFAULT_TOLERANCE_DB = 0.3
DR4_PROFILE_NAME = "IEEE 802.3bs — 400GBASE-DR4 · 100G/λ ottico 500 m"


def validate_dataset(d) -> list[str]:
    problems = []
    if not isinstance(d, dict):
        return ["il dataset deve essere un oggetto JSON"]
    if d.get("schema") != GOLDEN_SCHEMA:
        problems.append(f"schema deve essere {GOLDEN_SCHEMA}")
    if d.get("source") not in ("instrument", "synthetic-labpro"):
        problems.append("source deve essere instrument o synthetic-labpro")
    try:
        rate = float(d.get("symbol_rate_hz"))
        if not 1e9 <= rate <= 400e9:
            problems.append("symbol_rate_hz fuori range")
    except (TypeError, ValueError):
        problems.append("symbol_rate_hz mancante o non numerico")
    sps = d.get("samples_per_ui")
    if not isinstance(sps, int) or not 4 <= sps <= 64:
        problems.append("samples_per_ui deve essere un intero in [4, 64]")
    sym = d.get("symbols")
    wave = d.get("waveform_w")
    if not isinstance(sym, list) or len(sym) < 512:
        problems.append("symbols: servono almeno 512 simboli")
    if not isinstance(wave, list) or len(wave) < 512 * 4:
        problems.append("waveform_w: servono almeno 512 UI di campioni")
    if isinstance(sym, list) and isinstance(wave, list) and isinstance(sps, int):
        if len(wave) != len(sym) * sps:
            problems.append("waveform_w deve avere len(symbols) × samples_per_ui campioni")
        if any((not isinstance(v, int)) or v < 0 or v > 3 for v in sym[:64]):
            problems.append("symbols deve contenere indici di livello 0..3")
    ref = d.get("reference")
    if not isinstance(ref, dict) or not any(k in ref for k in ("tdecq_db", "oma_outer_dbm", "er_db")):
        problems.append("reference deve contenere almeno tdecq_db, oma_outer_dbm o er_db")
    return problems


def correlate_golden(d: dict) -> dict:
    """Esegue le misure LabPro sulla waveform del dataset e le confronta con
    i valori dello strumento.  Ritorna sempre un dict (mai eccezioni per
    dati validi)."""
    t0 = time.perf_counter()
    problems = validate_dataset(d)
    if problems:
        return {"ok": False, "problems": problems}
    spec = get_modulation(d.get("modulation", "PAM4"), d.get("mapping", "gray"))
    idx = np.asarray(d["symbols"], dtype=int)
    symbols = spec.levels_array[idx]
    P = np.asarray(d["waveform_w"], dtype=float)
    sps = int(d["samples_per_ui"])
    rate = float(d["symbol_rate_hz"])
    fs = rate * sps
    ref = d["reference"]
    tol = float(ref.get("tolerance_db", DEFAULT_TOLERANCE_DB))
    measured = {}
    try:
        td = tdecq_report(P, symbols, spec, sps, rate, fs)
        measured["tdecq_db"] = td.get("tdecq_db")
        measured["ceq_db"] = td.get("ceq_db")
    except Exception as exc:                      # waveform non processabile
        measured["tdecq_db"] = None
        measured["error"] = str(exc)
    try:
        lv = optical_levels_runs(P, symbols, spec.levels_array, sps)
        if lv is not None:
            measured["oma_outer_dbm"] = 10 * math.log10(max(lv["oma_outer_w"] * 1e3, 1e-12))
            measured["er_db"] = lv["extinction_ratio_db"]
    except Exception:
        pass
    deltas = {}
    worst = 0.0
    compared = 0
    for key in ("tdecq_db", "oma_outer_dbm", "er_db"):
        if key in ref and ref[key] is not None and measured.get(key) is not None:
            delta = float(measured[key]) - float(ref[key])
            deltas[key] = delta
            worst = max(worst, abs(delta))
            compared += 1
    synthetic = d.get("source") != "instrument"
    if compared == 0:
        model = NOT_ASSESSED
    elif synthetic:
        model = PROXY
    else:
        model = PASS if worst <= tol else FAIL
    evidence = (", ".join(f"Δ{k} {v:+.3f} dB" for k, v in deltas.items())
                + f" · tolerance ±{tol:g} dB · source {d.get('source')}")
    return {
        "ok": True, "source": d.get("source"), "instrument": d.get("instrument", ""),
        "interface": d.get("interface"), "n_symbols": int(len(idx)),
        "samples_per_ui": sps, "symbol_rate_hz": rate,
        "measured": measured, "reference": {k: ref.get(k) for k in ("tdecq_db", "oma_outer_dbm", "er_db")},
        "deltas": deltas, "worst_delta_db": worst, "tolerance_db": tol,
        "compared": compared,
        "verdict": verdict(model, basis=("proxy" if synthetic else "checkpoint"),
                           evidence=evidence, value=worst, limit=tol, cmp="<=",
                           unit="dB", margin=tol - worst),
        "elapsed_s": time.perf_counter() - t0,
        "loaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def synthetic_golden_dataset(profile_name: str = DR4_PROFILE_NAME, seed: int = 777,
                             n_symbols: int = 4096) -> dict:
    """Dataset di ESEMPIO generato dal banco stesso (source synthetic-labpro):
    esercita la pipeline di correlazione; per costruzione i delta sono ~0 e
    il verdetto resta PROXY."""
    from .config import STANDARD_PROFILE_META, STANDARD_PROFILES
    from .engine import simulate
    cfg = STANDARD_PROFILES[profile_name][0].with_updates(
        n_symbols=int(n_symbols), pattern="prbs", fec_mode="none")
    sim = simulate(cfg, seed=seed, depth="light")
    spec = sim.spec
    idx = [int(np.argmin(np.abs(spec.levels_array - v))) for v in sim.pam4_symbols]
    P = np.asarray(sim.optical.P_fiber_w, dtype=float)
    td = tdecq_report(P, sim.pam4_symbols, spec, cfg.analog_sps,
                      cfg.symbol_rate_hz, cfg.fs_analog_hz)
    lv = optical_levels_runs(P, sim.pam4_symbols, spec.levels_array, cfg.analog_sps)
    interface = STANDARD_PROFILE_META[profile_name]["interface"]
    lim = limits_for_interface(interface).get("tdecq")
    return {
        "schema": GOLDEN_SCHEMA, "source": "synthetic-labpro",
        "instrument": "LabPro tdecq_report (self-generated example)",
        "interface": interface, "symbol_rate_hz": cfg.symbol_rate_hz,
        "samples_per_ui": int(cfg.analog_sps), "modulation": cfg.modulation,
        "mapping": cfg.pam4_mapping, "seed": int(seed),
        "symbols": idx,
        "waveform_w": [float(f"{v:.5g}") for v in P],
        "reference": {
            "tdecq_db": td.get("tdecq_db"),
            "oma_outer_dbm": (10 * math.log10(lv["oma_outer_w"] * 1e3) if lv else None),
            "er_db": (lv["extinction_ratio_db"] if lv else None),
            "tolerance_db": DEFAULT_TOLERANCE_DB,
            "limit_db": (lim.limit if lim else None),
        },
        "note": ("synthetic example: replace with a DCA export (source=instrument) "
                 "to close the DR4 golden-correlation step"),
    }
