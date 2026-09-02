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
from .standards import (FAIL, NOT_ASSESSED, PASS, PROXY, TDECQ_REFERENCE_RX_BW_FRACTION,
                        limits_for_interface, verdict)

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


def correlate_golden(d: dict, optimize: str = "min_tdecq") -> dict:
    """Esegue le misure LabPro sulla waveform del dataset e le confronta con
    i valori dello strumento.  Ritorna sempre un dict (mai eccezioni per
    dati validi).

    Il TDECQ di confronto usa la banda del ricevitore di riferimento dello
    strumento (``reference.rx_bw_fraction``, default clausola 0.5·baud) e
    l'ottimizzazione dei tap per TDECQ minimo (121.8.5.3); il valore alla
    banda di clausola è riportato a parte come ``tdecq_clause_db`` quando
    lo strumento usava un'altra impostazione.  ``reference.tdecq_range_db``
    = [min, max] (per esempio più posizioni del tap principale) fa passare
    ogni valore dentro l'intervallo ± tolleranza.
    """
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
    sigma_s = float(d.get("sigma_s_w") or 0.0)
    bw_frac = ref.get("rx_bw_fraction")
    optimize = d.get("optimize") or optimize
    measured = {}
    try:
        td = tdecq_report(P, symbols, spec, sps, rate, fs, sigma_s_w=sigma_s,
                          optimize=optimize, rx_bw_fraction=bw_frac)
        measured["tdecq_db"] = td.get("tdecq_db")
        measured["ceq_db"] = td.get("ceq_db")
        measured["taps"] = td.get("taps")
        measured["rx_bw_fraction"] = (float(bw_frac) if bw_frac is not None
                                      else TDECQ_REFERENCE_RX_BW_FRACTION)
        if bw_frac is not None and abs(float(bw_frac) - TDECQ_REFERENCE_RX_BW_FRACTION) > 1e-9:
            tdc = tdecq_report(P, symbols, spec, sps, rate, fs, sigma_s_w=sigma_s,
                               optimize=optimize)
            measured["tdecq_clause_db"] = tdc.get("tdecq_db")
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
    rng = ref.get("tdecq_range_db")
    if rng and measured.get("tdecq_db") is not None:
        lo, hi = float(min(rng)), float(max(rng))
        v = float(measured["tdecq_db"])
        # delta rispetto all'intervallo: 0 dentro, distanza dal bordo fuori
        delta = (v - hi) if v > hi else ((v - lo) if v < lo else 0.0)
        deltas["tdecq_db"] = delta
        worst = max(worst, abs(delta))
        compared += 1
    for key in ("tdecq_db", "oma_outer_dbm", "er_db"):
        if key == "tdecq_db" and rng:
            continue
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
        "measured": measured,
        "reference": {k: ref.get(k) for k in ("tdecq_db", "tdecq_range_db", "oma_outer_dbm",
                                              "er_db", "rx_bw_fraction", "note")},
        "pattern_model": d.get("pattern_model"),
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
        "optimize": "mmse",                # riferimento calcolato con lo stesso EQ
        "note": ("synthetic example: replace with a DCA export (source=instrument) "
                 "to close the DR4 golden-correlation step"),
    }


# ---------------------------------------------------------------------------
# Import da strumento (FlexDCA) e identificazione del pattern
# ---------------------------------------------------------------------------

def parse_flexdca_csv(text: str) -> dict:
    """Legge un export Keysight FlexDCA: ``WaveformXYValues`` (colonne
    tempo, ampiezza) o ``WaveformPattern`` (una colonna + ``XInc``).
    Ritorna header (dict), tempo [s] e ampiezza (array)."""
    hdr, ys, xs = {}, [], []
    in_data = False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if in_data:
            parts = [v for v in line.split(",") if v.strip() != ""]
            if len(parts) >= 2:
                xs.append(float(parts[0]))
                ys.append(float(parts[1]))
            else:
                ys.append(float(parts[0]))
        elif line.startswith("Data"):
            in_data = True
        else:
            k, _, v = line.partition(",")
            hdr[k.strip()] = v.strip()
    if not ys:
        raise ValueError("FlexDCA: nessun dato dopo la riga 'Data'")
    y = np.asarray(ys, dtype=float)
    if xs and len(xs) == len(ys):
        t = np.asarray(xs, dtype=float)
    else:
        xinc = float(hdr.get("XInc", "0").replace("E", "e"))
        if xinc <= 0:
            raise ValueError("FlexDCA: manca XInc per un file a una colonna")
        t = float(hdr.get("XOrg", "0").replace("E", "e")) + xinc * np.arange(len(y))
    return {"header": hdr, "t": t, "y": y}


def _num(hdr: dict, key: str, default=None):
    v = hdr.get(key)
    if v in (None, ""):
        return default
    try:
        return float(str(v).replace("E", "e"))
    except ValueError:
        return default


def _bt4_lowpass(P, sps, frac=TDECQ_REFERENCE_RX_BW_FRACTION):
    from scipy import signal as _sig
    wn = min(frac * 2.0 / sps, 0.99)
    b, a = _sig.bessel(4, wn, btype="low", norm="mag")
    return _sig.filtfilt(b, a, P)


def _decision_directed(P, sps):
    """Decisioni a 4 livelli sul segnale filtrato BT4 alla fase con la
    migliore separazione dei cluster (k-means 1-D).  Ritorna
    (indici di livello 0..3 in ordine di ampiezza, fase [UI], qualità)."""
    Pf = _bt4_lowpass(P, sps)
    n = len(P) // sps
    best = None
    for ph in np.linspace(0, 1, 20, endpoint=False):
        pos = ((np.arange(n) + ph) * sps).astype(int)
        pos = pos[pos < len(Pf)]
        y = Pf[pos]
        c = np.percentile(y, [12.5, 37.5, 62.5, 87.5])
        for _ in range(15):
            lab = np.argmin(np.abs(y[:, None] - c[None, :]), axis=1)
            c = np.array([y[lab == i].mean() if np.any(lab == i) else c[i]
                          for i in range(4)])
        lab = np.argmin(np.abs(y[:, None] - c[None, :]), axis=1)
        sig = max(float(y[lab == i].std()) for i in range(4) if np.any(lab == i))
        gap = float(np.min(np.diff(np.sort(c))))
        q = gap / max(sig, 1e-12)
        if best is None or q > best[0]:
            best = (q, ph, lab, c)
    q, ph, lab, c = best
    order = np.argsort(c)
    remap = np.zeros(4, int)
    remap[order] = np.arange(4)
    return remap[lab].astype(int), float(ph), float(q)


def _circ_corr(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    x = x - x.mean()
    y = y - y.mean()
    den = float(np.linalg.norm(x) * np.linalg.norm(y)) or 1.0
    c = np.fft.ifft(np.fft.fft(x) * np.conj(np.fft.fft(y))).real / den
    k = int(np.argmax(np.abs(c)))
    return float(c[k]), k


def _ffe_residual(Pf, idx, ph, sps, levels, taps=9):
    """Residuo RMS (in frazione dello spacing) di un FFE LS a ``taps`` tap
    T/2 che mappa il segnale sulle ampiezze del pattern candidato."""
    n = len(idx)
    pos = ((np.arange(n) + ph) * sps).astype(int)
    cols = []
    half = taps // 2
    for sh in range(-half, half + 1):
        p = np.clip(pos + int(round(sh * sps / 2)), 0, len(Pf) - 1)
        cols.append(Pf[p])
    X = np.c_[np.stack(cols, axis=1), np.ones(n)]
    tgt = levels[idx]
    w, *_ = np.linalg.lstsq(X, tgt, rcond=None)
    r = X @ w - tgt
    gain = float(np.sum(w[:-1]))          # guadagno DC: segno = polarità
    return float(np.std(r) / (levels[1] - levels[0])), gain


def identify_pattern(P, sps, orders=(7, 9, 11, 13, 15), max_residual=0.25):
    """Riconosce il pattern PAM4 di una waveform catturata (pattern lock
    software).  Modelli provati, per ogni ordine PRBS:

    * PRBSnQ di clausola: coppie di bit di due periodi PRBS (offset 0/1,
      Gray/binario, polarità);
    * due copie ritardate dello stesso PRBS su MSB e LSB (generatori a MUX,
      per esempio SHF/Anritsu): ritardi dalla correlazione con le decisioni.

    Il candidato migliore è quello con il residuo minimo di un FFE LS a 9
    tap T/2 (deve stare sotto ``max_residual`` dello spacing).  Ritorna un
    dict con ``symbols`` (indici 0..3 in ordine di ampiezza, allineati al
    campione 0) e la descrizione del modello, oppure None se nessun modello
    spiega la waveform (si resta con le decisioni dirette, dichiarato)."""
    from .blocks.stimulus import prbs_bits
    P = np.asarray(P, dtype=float)
    dd, ph, q = _decision_directed(P, sps)
    n = len(dd)
    Pf = _bt4_lowpass(P, sps)
    levels = get_modulation("PAM4", "gray").levels_array
    gray_idx = np.array([0, 1, 3, 2])          # (msb, lsb) → indice ampiezza Gray
    candidates = []
    for order in orders:
        per = 2 ** order - 1
        if n < per:
            continue
        prbs = prbs_bits(order, per).astype(int)
        k = np.arange(n)
        # --- modello A: MSB e LSB da copie ritardate dello stesso PRBS
        msb_dd = (dd >= 2).astype(float)[:per]
        c_m, s_m = _circ_corr(msb_dd, prbs)
        lsb_hyp = [((dd % 2).astype(float)[:per], "binary"),
                   (((dd == 1) | (dd == 2)).astype(float)[:per], "gray")]
        shifts = set()
        for v, _ in lsb_hyp:
            _, s = _circ_corr(v, prbs)
            shifts.add(s)
        for s_l in shifts:
            for inv_l in (0, 1):
                for inv_m in (0, 1):
                    msb = prbs[(k - s_m) % per] ^ inv_m
                    lsb = prbs[(k - s_l) % per] ^ inv_l
                    candidates.append(("delayed-copies", order, 2 * msb + lsb))
                    candidates.append(("delayed-copies-gray", order, gray_idx[2 * msb + lsb]))
        # --- modello B: PRBSnQ di clausola (coppie di bit)
        bits = prbs_bits(order, 2 * per + 2).astype(int)
        for off in (0, 1):
            b2 = bits[off:off + 2 * per].reshape(-1, 2)
            for swap in (False, True):
                pair = b2[:, ::-1] if swap else b2
                sym_bin = 2 * pair[:, 0] + pair[:, 1]
                for mapping, arr in (("binary", sym_bin), ("gray", gray_idx[sym_bin])):
                    _, s = _circ_corr((dd[:per] - 1.5), (arr - 1.5))
                    base = np.roll(arr, s)
                    full = base[np.arange(n) % per]
                    for inv in (0, 1):
                        candidates.append((f"prbs{order}q-{mapping}", order,
                                           (3 - full) if inv else full))
    best = None
    for name, order, idx in candidates:
        idx = np.asarray(idx, dtype=int)
        for p_ in np.linspace(ph - 0.25, ph + 0.25, 11):
            res, gain = _ffe_residual(Pf, idx, p_, sps, levels)
            if gain <= 0:                       # polarità invertita: scarta
                continue
            if best is None or res < best[0]:
                best = (res, name, order, idx, p_)
    if best is None or best[0] > max_residual:
        return None
    res, name, order, idx, p_ = best
    return {"symbols": idx, "model": name, "prbs_order": int(order),
            "fit_residual": float(res), "agreement_with_decisions": float(np.mean(idx == dd)),
            "decision_quality": float(q), "phase_ui": float(p_)}


def align_known_pattern(P, sps, pattern_idx, max_residual=0.25):
    """Pattern lock con pattern NOTO (come lo strumento): allinea la
    sequenza periodica ``pattern_idx`` (indici 0..3) alla waveform con la
    correlazione delle decisioni e verifica il residuo FFE.  Ritorna il dict
    di :func:`identify_pattern` oppure None se il pattern non spiega la
    waveform."""
    P = np.asarray(P, dtype=float)
    pat = np.asarray(pattern_idx, dtype=int)
    per = len(pat)
    dd, ph, q = _decision_directed(P, sps)
    n = len(dd)
    Pf = _bt4_lowpass(P, sps)
    levels = get_modulation("PAM4", "gray").levels_array
    L = min(per, n)
    _, k = _circ_corr(dd[:L] - 1.5, pat[:L] - 1.5)
    best = None
    for shift in (k, (k + 1) % per, (k - 1) % per):
        idx = np.roll(pat, shift)[np.arange(n) % per]
        for p_ in np.linspace(ph - 0.25, ph + 0.25, 11):
            res, gain = _ffe_residual(Pf, idx, p_, sps, levels)
            if gain <= 0:
                continue
            if best is None or res < best[0]:
                best = (res, idx, p_, shift)
    if best is None or best[0] > max_residual:
        return None
    res, idx, p_, shift = best
    return {"symbols": idx, "model": "known-pattern", "prbs_order": None,
            "fit_residual": float(res), "agreement_with_decisions": float(np.mean(idx == dd)),
            "decision_quality": float(q), "phase_ui": float(p_), "shift": int(shift)}


def dataset_from_flexdca(text: str, symbol_rate_hz=None, reference=None,
                         source: str = "instrument", instrument: str = "Keysight FlexDCA export",
                         interface=None, target_sps: int = 20, note: str = "") -> dict:
    """Costruisce un dataset ``labpro-golden/1`` da un export FlexDCA.

    La waveform è decimata/interpolata a ``target_sps`` campioni per UI, il
    pattern è riconosciuto con :func:`identify_pattern` (fallback:
    decisioni dirette, dichiarato), il rumore del canale dell'header diventa
    σ_S della misura.  ``reference`` è il dict con i valori dello strumento
    (``tdecq_db`` o ``tdecq_range_db``, ``oma_outer_dbm``, ``er_db``,
    ``tolerance_db``, ``rx_bw_fraction``)."""
    parsed = parse_flexdca_csv(text)
    hdr, t, y = parsed["header"], parsed["t"], parsed["y"]
    rate = symbol_rate_hz or _num(hdr, "Symbol Rate (Baud)") or (
        (_num(hdr, "Bit Rate (b/s)") or 0) / 2)
    if not rate:
        raise ValueError("symbol_rate_hz mancante: non è nell'header FlexDCA")
    rate = float(rate)
    dt = float(np.median(np.diff(t))) if len(t) > 1 else 1.0 / (rate * target_sps)
    sps0 = 1.0 / (dt * rate)
    n_sym = int(np.floor(len(y) / sps0))
    if abs(sps0 - round(sps0)) < 1e-6 and int(round(sps0)) % target_sps == 0:
        dec = int(round(sps0)) // target_sps
        P = y[::dec]
    else:
        grid = np.arange(n_sym * target_sps) * (1.0 / (rate * target_sps))
        P = np.interp(grid, t - t[0], y)
    P = np.asarray(P[:n_sym * target_sps], dtype=float)
    if str(hdr.get("Y Units", "")).lower().startswith("volt"):
        note = (note + " " if note else "") + "Y in volt: trattato come potenza relativa (O/E lineare dichiarato)"
    if float(np.min(P)) < 0:
        P = P - float(np.min(P))
    ident = identify_pattern(P, target_sps)
    if ident is None:
        dd, _, q = _decision_directed(P, target_sps)
        symbols = dd[:n_sym]
        model = {"model": "decision-directed", "fit_residual": None,
                 "decision_quality": float(q)}
    else:
        symbols = ident["symbols"][:n_sym]
        model = {k: v for k, v in ident.items() if k != "symbols"}
    ref = dict(reference or {})
    ref.setdefault("tolerance_db", DEFAULT_TOLERANCE_DB)
    return {
        "schema": GOLDEN_SCHEMA, "source": source, "instrument": instrument,
        "interface": interface, "symbol_rate_hz": rate, "samples_per_ui": int(target_sps),
        "modulation": "PAM4", "mapping": "gray",
        "symbols": [int(v) for v in symbols],
        "waveform_w": [float(f"{v:.6g}") for v in P],
        "sigma_s_w": _num(hdr, "Channel Noise", 0.0),
        "acquisition": {"instrument": hdr.get("Instrument"), "software": hdr.get("SwVersion"),
                        "date": hdr.get("Date"), "signal_type": hdr.get("Signal Type"),
                        "channel_bandwidth_hz": _num(hdr, "Channel Bandwidth"),
                        "samples_per_ui_original": float(sps0), "points_original": int(len(y)),
                        "file_format": hdr.get("File Format")},
        "pattern_model": model,
        "reference": ref, "note": note,
    }


# ---------------------------------------------------------------------------
# Libreria golden distribuita con il pacchetto
# ---------------------------------------------------------------------------

def _library_root():
    from pathlib import Path
    return Path(__file__).resolve().parent / "data" / "golden"


def golden_library() -> list[dict]:
    """Elenca le librerie golden incluse nel pacchetto (metadati, senza
    waveform)."""
    import json
    out = []
    root = _library_root()
    if not root.exists():
        return out
    for lib_dir in sorted(root.iterdir()):
        meta = lib_dir / "library.json"
        if not meta.exists():
            continue
        lib = json.loads(meta.read_text())
        out.append({k: v for k, v in lib.items() if k != "waveforms"}
                   | {"waveforms": [{k: v for k, v in w.items() if k != "file"}
                                    for w in lib.get("waveforms", [])]})
    return out


def load_library_dataset(library: str, waveform_id: str) -> dict:
    """Carica una waveform della libreria come dataset ``labpro-golden/1``
    (il pattern viene riconosciuto alla prima chiamata e messo in cache)."""
    import json
    lib_dir = _library_root() / library
    lib = json.loads((lib_dir / "library.json").read_text())
    w = next((x for x in lib["waveforms"] if x["id"] == waveform_id), None)
    if w is None:
        raise KeyError(f"waveform {waveform_id!r} non presente in {library!r}")
    npz = np.load(lib_dir / w["file"])
    P = np.asarray(npz["waveform_w"], dtype=float)
    sps = int(lib["samples_per_ui"])
    n_sym = len(P) // sps
    cache = _PATTERN_CACHE.get((library, waveform_id))
    if cache is None and "symbols" in npz.files:
        # pattern riconosciuto in fase di costruzione della libreria (vedi
        # library.json → pattern_model): pattern lock già fatto
        cache = (np.asarray(npz["symbols"], dtype=int)[:n_sym],
                 dict(w.get("pattern_model") or {"model": "library"}))
    if cache is None:
        ident = identify_pattern(P, sps)
        if ident is None:
            dd, _, q = _decision_directed(P, sps)
            cache = (dd[:n_sym], {"model": "decision-directed", "decision_quality": float(q)})
        else:
            cache = (ident["symbols"][:n_sym], {k: v for k, v in ident.items() if k != "symbols"})
        _PATTERN_CACHE[(library, waveform_id)] = cache
    symbols, model = cache
    ref = dict(w["reference"])
    ref["tdecq_range_db"] = [ref["tdecq_5t_min_db"], ref["tdecq_5t_max_db"]]
    ref["tolerance_db"] = lib.get("tolerance_db", DEFAULT_TOLERANCE_DB)
    ref["rx_bw_fraction"] = lib.get("reference_rx_bw_fraction")
    ref["note"] = lib.get("reference_rx_note", "")
    return {
        "schema": GOLDEN_SCHEMA, "source": "instrument",
        "instrument": lib.get("instrument", ""), "interface": lib.get("interface"),
        "library": library, "waveform_id": waveform_id,
        "title": lib.get("title"), "provenance": lib.get("provenance"),
        "source_url": lib.get("source_url"), "license_note": lib.get("license_note"),
        "symbol_rate_hz": float(lib["symbol_rate_hz"]), "samples_per_ui": sps,
        "modulation": "PAM4", "mapping": "gray",
        "symbols": [int(v) for v in symbols],
        "waveform_w": [float(v) for v in P[:n_sym * sps]],
        "sigma_s_w": float(w.get("channel_noise_w") or 0.0),
        "acquisition": {"channel_bandwidth_hz": w.get("channel_bandwidth_hz"),
                        "date": w.get("acquisition_date"),
                        "samples_per_ui_original": w.get("samples_per_ui_original"),
                        "points_original": w.get("points_original"),
                        "source_file": w.get("source_file"), "source_sha256": w.get("source_sha256"),
                        "flexdca_equivalent_bw_ghz": w.get("flexdca_equivalent_bw_ghz")},
        "pattern_model": model,
        "reference": ref,
        "note": f"{lib.get('title')} · {waveform_id}",
    }


_PATTERN_CACHE: dict = {}


def correlate_library(library: str, optimize: str = "min_tdecq", ids=None,
                      cancel=None, progress=None) -> dict:
    """Correlazione sistematica di tutta una libreria: una riga per
    waveform (LabPro vs strumento) e un verdetto complessivo del modello."""
    t0 = time.perf_counter()
    lib = next((x for x in golden_library() if x["name"] == library), None)
    if lib is None:
        raise KeyError(f"libreria golden {library!r} sconosciuta")
    rows = []
    todo = [w for w in lib["waveforms"] if not ids or w["id"] in ids]
    for i, w in enumerate(todo):
        if cancel is not None:
            from .procedures import check_cancel
            check_cancel(cancel)
        if progress is not None:
            progress(i, len(todo), w["id"])
        d = load_library_dataset(library, w["id"])
        r = correlate_golden(d, optimize=optimize)
        rows.append({"id": w["id"], "flexdca_bw_ghz": w.get("flexdca_equivalent_bw_ghz"),
                     "channel_bandwidth_hz": w.get("channel_bandwidth_hz"),
                     "measured": r.get("measured"), "reference": r.get("reference"),
                     "deltas": r.get("deltas"), "verdict": r.get("verdict"),
                     "pattern_model": r.get("pattern_model"), "elapsed_s": r.get("elapsed_s")})
    statuses = [row["verdict"]["model"] for row in rows]
    model = (FAIL if FAIL in statuses else (PASS if statuses and all(s_ == PASS for s_ in statuses)
                                            else NOT_ASSESSED))
    n_pass = sum(1 for s_ in statuses if s_ == PASS)
    worst = max((abs(v) for row in rows for v in (row["deltas"] or {}).values()), default=0.0)
    return {
        "library": library, "title": lib.get("title"), "instrument": lib.get("instrument"),
        "reference_rx_bw_fraction": lib.get("reference_rx_bw_fraction"),
        "tolerance_db": lib.get("tolerance_db"), "optimize": optimize,
        "rows": rows, "n_pass": n_pass, "n_total": len(rows),
        "worst_delta_db": worst,
        "verdict": verdict(model, basis="checkpoint",
                           evidence=f"{n_pass}/{len(rows)} waveforms within tolerance, worst |Δ| {worst:.3f} dB",
                           value=worst, limit=lib.get("tolerance_db"), cmp="<=", unit="dB"),
        "elapsed_s": time.perf_counter() - t0,
        "loaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
