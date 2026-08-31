"""CDR reale nel datapath: TED (Gardner o Mueller-Müller) → loop PI del
secondo ordine → NCO/accumulatore di fase che decide DAVVERO gli istanti di
campionamento usati da FSE/DFE/BER.

Nessun oracle: il guadagno del TED è stimato con un probe cieco, il lock è
rilevato dalla stabilità della fase, e l'allineamento al pattern trasmesso
avviene con una cross-correlazione stile BERT (pattern lock) — l'unica
conoscenza usata è la sequenza attesa, come in un error detector reale.
Se CDR o pattern lock falliscono, il link è DOWN e le metriche a valle non
esistono (gating nel motore).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class CdrResult:
    mode: str
    locked: bool
    tau_trace_ui: np.ndarray          # fase NCO per simbolo [UI, detrended no]
    freq_trace_ppm: np.ndarray        # registro di frequenza [ppm]
    ted_gain: float                   # guadagno TED stimato (probe cieco)
    lock_symbol: int | None
    cycle_slips: int
    pos_data_samples: np.ndarray      # posizione frazionaria (in campioni ADC)
                                      # dell'istante dati per ciascun simbolo RX
    delay_ui_est: float               # ritardo medio stimato del campione dati
    # pattern lock (BERT-style)
    pattern_lag: int | None = None
    pattern_corr: float = 0.0
    pattern_locked: bool = False
    link_up: bool = False
    detail: str = ""


def _scan_scurve_gain(v, sps_samples, rms2, n_probe=1200, start=200):
    """Stima cieca del guadagno del TED: media del TED normalizzato su 8 fasi
    → ampiezza della fondamentale (fit sinusoidale) → |pendenza| allo zero
    K ≈ 2πA. Robusta rispetto alla fase di partenza, che è ignota."""
    def mean_ted(off_ui):
        acc = 0.0
        n = 0
        p = start * sps_samples + off_ui * sps_samples
        limit = len(v) - 2
        for _ in range(n_probe):
            i2 = int(p + sps_samples)
            if i2 + 1 >= limit:
                break
            i0 = int(p); f0 = p - i0
            pm = p + sps_samples / 2
            i1 = int(pm); f1 = pm - i1
            f2 = p + sps_samples - i2
            ye = v[i0] * (1 - f0) + v[i0 + 1] * f0
            ym = v[i1] * (1 - f1) + v[i1 + 1] * f1
            yl = v[i2] * (1 - f2) + v[i2 + 1] * f2
            acc += (yl - ye) * ym
            n += 1
            p += sps_samples
        return acc / max(n, 1) / rms2

    m = np.array([mean_ted(ph) for ph in np.arange(8) / 8.0])
    amp = 2 * np.abs(np.fft.fft(m)[1]) / 8
    return 2 * np.pi * amp


def run_cdr(cfg, adc_samples, mode="gardner", levels=None) -> CdrResult:
    """Loop chiuso per tutto il record. Ritorna posizioni dati per simbolo."""
    v = np.asarray(adc_samples, dtype=float)
    sps = float(cfg.adc_sps)                 # campioni ADC per UI (nominali RX)
    n_sym = int(len(v) / sps) - 4

    # guadagno TED (scan cieco della S-curve) e parametri del loop PI
    rms2 = float(np.mean(v ** 2)) or 1.0
    K = _scan_scurve_gain(v, sps, rms2)
    if K < 1e-6:
        return CdrResult(mode=mode, locked=False, tau_trace_ui=np.zeros(1),
                         freq_trace_ppm=np.zeros(1), ted_gain=0.0,
                         lock_symbol=None, cycle_slips=0,
                         pos_data_samples=np.zeros(1), delay_ui_est=0.0,
                         detail="S-curve piatta: nessuna informazione di timing")
    zeta = cfg.cdr_damping
    wnT = 2 * cfg.cdr_bw / (zeta + 1 / (4 * zeta))
    kp = 2 * zeta * wnT / K      # errore in UI (ted normalizzato / K)
    ki = wnT * wnT / K
    slope = K

    rms = float(np.sqrt(rms2))
    lv = np.asarray(levels if levels is not None else [-1.0, 1.0])
    lv_scaled = lv * rms / max(float(np.std(lv)), 1e-9)

    tau = np.empty(n_sym)
    fppm = np.empty(n_sym)
    pos = np.empty(n_sym)
    p = 2.0 * sps          # partenza arbitraria (nessun oracle)
    f = 0.0                # correzione di frequenza [campioni/simbolo]
    y_prev = 0.0
    d_prev = 0.0
    N = len(v) - 2
    for k in range(n_sym):
        i0 = int(p); f0 = p - i0
        if i0 + int(sps) + 1 >= N:
            n_sym = k
            break
        ye = v[i0] + (v[i0 + 1] - v[i0]) * f0
        pm = p + sps / 2
        i1 = int(pm); f1 = pm - i1
        ym = v[i1] + (v[i1 + 1] - v[i1]) * f1
        pl = p + sps
        i2 = int(pl); f2 = pl - i2
        yl = v[i2] + (v[i2 + 1] - v[i2]) * f2

        if mode == "mm":
            d_now = lv_scaled[np.argmin(np.abs(ye - lv_scaled))]
            ted = (d_prev * ye - d_now * y_prev) / rms2
            y_prev, d_prev = ye, d_now
        else:  # gardner
            ted = (yl - ye) * ym / rms2

        # feedback: il loop si assesta da solo sullo zero stabile della
        # S-curve (l'ambiguità dato/fronte è risolta a valle dal pattern lock)
        f += ki * ted
        f = float(np.clip(f, -0.001, 0.001))       # ±1000 ppm [UI/simbolo]
        p += sps * (1.0 + kp * ted + f)
        pos[k] = i0 + f0            # istante dati usato per il simbolo k
        tau[k] = p / sps - (k + 1)
        fppm[k] = f * 1e6

    tau = tau[:n_sym]; fppm = fppm[:n_sym]; pos = pos[:n_sym]

    # lock: la fase detrended della coda deve essere stabile
    tail = tau[-max(n_sym // 4, 200):]
    x = np.arange(len(tail))
    trend = np.polyfit(x, tail, 1)
    resid = tail - np.polyval(trend, x)
    settled = float(np.std(resid)) < 0.06
    diffs = np.abs(np.diff(tau))
    cycle_slips = int(np.sum(diffs > 0.5))
    locked = bool(settled and cycle_slips == 0 and n_sym > 1000)

    # tempo di lock: primo simbolo da cui la fase resta entro ±0.08 UI
    lock_symbol = None
    if locked:
        ref = float(np.median(tail))
        drift = tau - (np.arange(n_sym) - (n_sym - len(tail) / 2)) * trend[0]
        inside = np.abs(drift - ref) < 0.08
        run = 0
        for i, ok in enumerate(inside):
            run = run + 1 if ok else 0
            if run >= 400:
                lock_symbol = i - 399
                break

    return CdrResult(
        mode=mode, locked=locked, tau_trace_ui=tau, freq_trace_ppm=fppm,
        ted_gain=float(slope), lock_symbol=lock_symbol,
        cycle_slips=cycle_slips, pos_data_samples=pos,
        delay_ui_est=float(np.median(pos / sps - np.arange(len(pos)))),
        detail=f"std fase coda={np.std(resid):.3f} UI, slips={cycle_slips}",
    )


def pattern_sync(y_data, tx_symbols, max_lag=64):
    """Pattern lock stile BERT: cross-correlazione dei campioni dati col
    pattern atteso. Ritorna (lag, correlazione normalizzata, inverted)."""
    y = np.asarray(y_data, dtype=float)
    a = np.asarray(tx_symbols, dtype=float)
    n = min(len(y) - max_lag, len(a) - max_lag, 4000)
    if n < 500:
        return None, 0.0, False
    seg = y[max_lag:max_lag + n]
    seg = (seg - seg.mean()) / (seg.std() or 1)
    best_lag, best_c = None, 0.0
    for lag in range(-max_lag, max_lag + 1):
        # il simbolo RX k corrisponde al TX k + lag
        atx = a[max_lag + lag: max_lag + lag + n]
        atx = (atx - atx.mean()) / (atx.std() or 1)
        c = float(np.dot(seg, atx) / n)
        if abs(c) > abs(best_c):
            best_c, best_lag = c, lag
    return best_lag, best_c, best_c < 0
