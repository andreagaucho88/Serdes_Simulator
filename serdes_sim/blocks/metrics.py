"""Metriche: BER con intervalli di confidenza, statistiche per livello,
LLR calibrati e GMI, waterfall detector-only, bathtub empirica + dual-Dirac,
BER contour, segmenti eye."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats
from scipy.special import logsumexp

from ..utils import affine_fit, qfunc, zero_error_upper_bound
from .dsp import sample_adc_at_ui
from .stimulus import (PAM4_GRAY, hard_slice, nearest_level_index,
                       symbols_to_bits)


def binomial_interval(errors, trials, confidence=0.95):
    """Intervallo Clopper-Pearson. ATTENZIONE: assume prove iid — con burst
    (error propagation DFE) l'intervallo reale è più largo di questo."""
    alpha = 1 - confidence
    lo = 0.0 if errors == 0 else stats.beta.ppf(alpha / 2, errors, trials - errors + 1)
    hi = 1.0 if errors == trials else stats.beta.ppf(1 - alpha / 2, errors + 1, trials - errors)
    return float(lo), float(hi)


def stage_error_metrics(samples, truth, validation_mask, name, spec=PAM4_GRAY):
    y = np.asarray(samples)[validation_mask]
    d = np.asarray(truth)[validation_mask]
    decided = hard_slice(y, spec.levels_array)
    ser_errors = int(np.count_nonzero(decided != d))
    true_bits = symbols_to_bits(d, spec)
    decided_bits = symbols_to_bits(decided, spec)
    bit_errors = int(np.count_nonzero(true_bits != decided_bits))
    n_bits = len(true_bits)
    lo, hi = binomial_interval(bit_errors, n_bits)
    upper_one_sided = float(zero_error_upper_bound(n_bits)) if bit_errors == 0 else float("nan")
    return {
        "stage": name, "symbols": len(d), "symbol_errors": ser_errors,
        "SER": ser_errors / len(d), "bits": n_bits, "bit_errors": bit_errors,
        "BER": bit_errors / n_bits, "BER_95pct_low": lo, "BER_95pct_high": hi,
        "zero_error_95pct_upper": upper_one_sided,
    }


# ---------------------------------------------------------------------------
# Statistiche per livello ed eye-opening proxy (NON TDECQ)
# ---------------------------------------------------------------------------

def level_statistics(train_out, train_truth, spec=PAM4_GRAY):
    rows = []
    for level in spec.levels_array:
        x = train_out[np.isclose(train_truth, level)]
        # con pattern clock i livelli interni non vengono trasmessi
        rows.append({
            "nominal_level": float(level),
            "mean": float(np.mean(x)) if len(x) else float(level),
            "sigma": float(np.std(x, ddof=1)) if len(x) > 1 else 0.0,
            "count": int(len(x)),
        })
    for r in rows:
        r["lower_3sigma"] = r["mean"] - 3 * r["sigma"]
        r["upper_3sigma"] = r["mean"] + 3 * r["sigma"]
    openings = [rows[i + 1]["lower_3sigma"] - rows[i]["upper_3sigma"]
                for i in range(len(rows) - 1)]
    return rows, openings


def snr_report(y, truth, level_stats, spec=PAM4_GRAY):
    """SNR e Q-factor al piano di decisione.

    - SNR_slicer = E[d²]/E[(y−d)²] su validation: include rumore, ISI residua
      e non linearità (per questo a volte si chiama SNDR del sampler).
    - Q per occhio = (μ_{i+1}−μ_i)/(σ_i+σ_{i+1}): il classico Q-factor fra
      livelli adiacenti; per gaussiane BER_occhio ≈ Q(Q_factor).
    """
    y = np.asarray(y)
    d = np.asarray(truth)
    err = y - d
    signal_power = float(np.mean(d ** 2))
    error_power = float(np.mean(err ** 2))
    snr_db = 10 * np.log10(signal_power / max(error_power, 1e-30))
    q_per_eye = []
    for a, b in zip(level_stats[:-1], level_stats[1:]):
        denom = a["sigma"] + b["sigma"]
        q_per_eye.append((b["mean"] - a["mean"]) / denom if denom > 0 else float("inf"))
    # Approssimazione da Q_min per M-PAM Gray: ogni soglia è attraversata da
    # due livelli adiacenti. Il fattore 2(M-1)/(M log2 M) è indispensabile:
    # usare direttamente Q(q_min) sovrastima la BER PAM4 del 33%.
    m = len(spec.levels_array)
    q_min = float(min(q_per_eye)) if q_per_eye else float("nan")
    q_factor = 2 * (m - 1) / (m * spec.bits_per_symbol)
    ber_qmin = float(q_factor * qfunc(q_min)) if q_per_eye else float("nan")

    # Modello gaussiano per-livello completo: integra ogni N(mu_i,sigma_i)
    # fra le soglie calibrate e pesa le regioni decise con la distanza di
    # Hamming. È il confronto corretto con la BER contata; Q_min resta un
    # indicatore worst-eye, non un modello esatto dell'intero PAMn.
    _, thresholds = decision_thresholds(level_stats)
    bounds = np.r_[-np.inf, np.asarray(thresholds), np.inf]
    counts = np.asarray([r["count"] for r in level_stats], dtype=float)
    priors = counts / max(float(np.sum(counts)), 1.0)
    ber_levels = 0.0
    for i, row in enumerate(level_stats):
        sigma = max(float(row["sigma"]), 1e-30)
        cdf = stats.norm.cdf((bounds - float(row["mean"])) / sigma)
        decision_prob = np.diff(cdf)
        for j, prob in enumerate(decision_prob):
            hamming = np.count_nonzero(spec.bit_array[i] != spec.bit_array[j])
            ber_levels += priors[i] * float(prob) * hamming / spec.bits_per_symbol
    return {
        "snr_slicer_db": snr_db,
        "error_rms": float(np.sqrt(error_power)),
        "q_per_eye": q_per_eye,
        "q_min": q_min,
        "ber_from_qmin_gaussian": ber_qmin,
        "ber_gaussian_levels": float(ber_levels),
    }


def optical_level_proxies(P_w):
    """OMA/ER proxy dai percentili della potenza istantanea (dichiarato:
    senza clock alignment né filtro di riferimento — non è una misura TDECQ)."""
    P = np.asarray(P_w)
    p_low = float(np.mean(P[P <= np.percentile(P, 10)]))
    p_high = float(np.mean(P[P >= np.percentile(P, 90)]))
    return {
        "p_avg_w": float(np.mean(P)),
        "p_low_w": p_low,
        "p_high_w": p_high,
        "oma_outer_w": p_high - p_low,
        "extinction_ratio_db": 10 * np.log10(max(p_high, 1e-30) / max(p_low, 1e-30)),
    }


def decision_confusion_matrix(decided, truth, levels):
    """Matrice livello trasmesso × livello deciso (conteggi)."""
    levels = np.asarray(levels)
    n = len(levels)
    ti = nearest_level_index(truth, levels)
    di = nearest_level_index(decided, levels)
    counts = np.zeros((n, n), dtype=int)
    np.add.at(counts, (ti, di), 1)
    return counts


def decision_thresholds(level_stats):
    """Soglie fra livelli adiacenti: punto medio nominale e soglia calibrata
    pesata sulle deviazioni standard (proxy del crossing di likelihood).

    Le soglie valgono SOLO per il piano di osservazione da cui provengono le
    level_stats (uscita FSE ≠ uscita DFE ≠ baseline 1 sps)."""
    if len(level_stats) < 2:
        return [], []
    mids, calibrated = [], []
    for a, b in zip(level_stats[:-1], level_stats[1:]):
        mids.append(0.5 * (a["mean"] + b["mean"]))
        denom = a["sigma"] + b["sigma"]
        calibrated.append((a["mean"] * b["sigma"] + b["mean"] * a["sigma"]) / denom
                          if denom > 0 else 0.5 * (a["mean"] + b["mean"]))
    return mids, calibrated


# ---------------------------------------------------------------------------
# LLR calibrati e GMI
# ---------------------------------------------------------------------------

def calibrated_llr(y, means, variances, spec=PAM4_GRAY):
    """LLR per bit con likelihood gaussiane per livello (media/var dal training)."""
    y = np.asarray(y)[:, None]
    log_likelihood = -0.5 * np.log(2 * np.pi * variances) - (y - means) ** 2 / (2 * variances)
    bps = spec.bits_per_symbol
    bit_array = spec.bit_array
    out = np.empty((len(y), bps))
    for bit_position in range(bps):
        is_zero = bit_array[:, bit_position] == 0
        out[:, bit_position] = (logsumexp(log_likelihood[:, is_zero], axis=1)
                                - logsumexp(log_likelihood[:, ~is_zero], axis=1))
    return out


# alias di compatibilità v7
calibrated_pam4_llr = calibrated_llr


def gmi_from_llr(llr, true_bit_pairs):
    gmi_per_bit = []
    for b in range(llr.shape[1]):
        sign = 1 - 2 * true_bit_pairs[:, b].astype(float)
        penalty = np.logaddexp(0, -sign * llr[:, b]) / np.log(2)
        gmi_per_bit.append(float(1 - np.mean(penalty)))
    return gmi_per_bit, float(np.sum(gmi_per_bit))


# ---------------------------------------------------------------------------
# Waterfall detector-only (AWGN dopo il FSE — NON equivale a potenza ottica)
# ---------------------------------------------------------------------------

def detector_waterfall(base, truth, rng, spec=PAM4_GRAY,
                       sigma_min=0.015, sigma_max=0.22, n=18):
    sigma_sweep = np.linspace(sigma_min, sigma_max, n)
    truth_bits = symbols_to_bits(truth, spec)
    bers, errors_list = [], []
    for sigma in sigma_sweep:
        noisy = base + rng.normal(0, sigma, len(base))
        decided_bits = symbols_to_bits(hard_slice(noisy, spec.levels_array), spec)
        errors = int(np.count_nonzero(decided_bits != truth_bits))
        errors_list.append(errors)
        bers.append(errors / len(truth_bits))
    return sigma_sweep, np.asarray(errors_list), np.asarray(bers), len(truth_bits)


# ---------------------------------------------------------------------------
# Bathtub empirica pre-EQ + modello dual-Dirac + contour H/V
# ---------------------------------------------------------------------------

def dual_dirac_bathtub(phase_s, ui_s, sigma_rj_s, dj_pp_s):
    half_opening = 0.5 * (ui_s - dj_pp_s)
    return 0.5 * (qfunc((half_opening - phase_s) / sigma_rj_s)
                  + qfunc((half_opening + phase_s) / sigma_rj_s))


@dataclass
class BathtubResult:
    phase_ui: np.ndarray
    empirical_ber: np.ndarray
    empirical_errors: np.ndarray
    n_bits: int
    model_ber: np.ndarray
    sigma_rj_s: float
    dj_pp_s: float
    plot_floor: float


def empirical_bathtub(cfg, adc_samples_v, adc_nominal_time_ui, pam4_symbols,
                      rx_integer_delay_ui, n_phases=93,
                      sigma_rj_s=0.35e-12, dj_pp_s=2.0e-12,
                      spec=PAM4_GRAY) -> BathtubResult:
    phase_grid = np.linspace(-0.46, 0.46, n_phases)
    k_train = np.arange(cfg.training_start, cfg.training_stop)
    truth_train = pam4_symbols[k_train]
    k_val = np.arange(cfg.training_stop + 200, cfg.n_symbols - 200)
    truth_bits = symbols_to_bits(pam4_symbols[k_val], spec)
    bers, errs = [], []
    for phase_ui in phase_grid:
        y_train = sample_adc_at_ui(adc_samples_v, adc_nominal_time_ui,
                                   k_train + rx_integer_delay_ui + 0.5 + phase_ui)
        gain, offset = affine_fit(truth_train, y_train)
        y_val = sample_adc_at_ui(adc_samples_v, adc_nominal_time_ui,
                                 k_val + rx_integer_delay_ui + 0.5 + phase_ui)
        decided_bits = symbols_to_bits(hard_slice((y_val - offset) / gain,
                                                  spec.levels_array), spec)
        errors = int(np.count_nonzero(decided_bits != truth_bits))
        errs.append(errors)
        bers.append(errors / len(truth_bits))
    model = dual_dirac_bathtub(phase_grid * cfg.ui_s, cfg.ui_s, sigma_rj_s, dj_pp_s)
    return BathtubResult(
        phase_ui=phase_grid,
        empirical_ber=np.asarray(bers),
        empirical_errors=np.asarray(errs),
        n_bits=len(truth_bits),
        model_ber=model,
        sigma_rj_s=sigma_rj_s,
        dj_pp_s=dj_pp_s,
        plot_floor=0.5 / len(truth_bits),
    )


def ber_contour(cfg, sigma_rj_s=0.35e-12, dj_pp_s=2.0e-12,
                vertical_half_level_v=45e-3, vertical_noise_rms_v=7e-3):
    """Contour fase-soglia con modelli H/V indipendenti dichiarati."""
    threshold_mv = np.linspace(-35, 35, 81)
    phase_ui = np.linspace(-0.47, 0.47, 121)
    vertical_ber = 0.5 * (qfunc((vertical_half_level_v + threshold_mv[:, None] * 1e-3) / vertical_noise_rms_v)
                          + qfunc((vertical_half_level_v - threshold_mv[:, None] * 1e-3) / vertical_noise_rms_v))
    horizontal_ber = dual_dirac_bathtub(phase_ui[None, :] * cfg.ui_s,
                                        cfg.ui_s, sigma_rj_s, dj_pp_s)
    contour = np.minimum(0.5, 1 - (1 - horizontal_ber) * (1 - vertical_ber))
    return phase_ui, threshold_mv, contour


# ---------------------------------------------------------------------------
# Eye
# ---------------------------------------------------------------------------

def eye_segments(x, sps, start_symbol=80, traces=260):
    x = np.asarray(x)
    rows = []
    for k in range(start_symbol, min(len(x) // sps - 2, start_symbol + traces)):
        center = k * sps + sps // 2
        rows.append(x[center - sps:center + sps])
    return np.asarray(rows)


def eye_density(x, sps, start_symbol=80, traces=2000, bins_v=120):
    """Istogramma 2D (tempo UI × ampiezza) per un eye a densità."""
    available = len(np.asarray(x)) // sps - 2
    start_symbol = max(1, min(start_symbol, max(available - 8, 1)))
    segs = eye_segments(x, sps, start_symbol, traces)
    if segs.size == 0:
        raise ValueError("record troppo corto per costruire un eye")
    n_t = segs.shape[1]
    t_ui = (np.arange(n_t) - n_t // 2) / sps
    t_flat = np.tile(t_ui, segs.shape[0])
    v_flat = segs.reshape(-1)
    v_lo, v_hi = np.percentile(v_flat, [0.1, 99.9])
    pad = 0.1 * (v_hi - v_lo)
    H, t_edges, v_edges = np.histogram2d(
        t_flat, v_flat, bins=[n_t, bins_v],
        range=[[t_ui[0] - 0.5 / sps, t_ui[-1] + 0.5 / sps], [v_lo - pad, v_hi + pad]])
    return H.T, t_edges, v_edges, segs, t_ui


def _tdecq_noise_enhancement(taps, b_ref, a_ref, sps, n_freq=8192):
    """Ceq del reference receiver da densita di rumore sagomata dal BT4.

    IEEE 802.3 clause 121, Equation 121-9, pesa la risposta in potenza
    dell'equalizzatore con lo spettro del rumore bianco dopo il filtro di
    riferimento.  ``sqrt(sum(tap**2))`` e corretto solo per rumore bianco
    gia campionato e non per il rumore correlato dal BT4.
    """
    from scipy import signal as _sig

    taps = np.asarray(taps, dtype=float)
    w, h_ref = _sig.freqz(b_ref, a_ref, worN=n_freq)
    # I tap sono T-spaced, mentre w e in rad/campione analogico.
    delays = np.arange(len(taps), dtype=float) * float(sps)
    h_eq = np.exp(-1j * w[:, None] * delays[None, :]) @ taps
    noise_psd = np.abs(h_ref) ** 2
    den = float(np.trapz(noise_psd, w))
    num = float(np.trapz(noise_psd * np.abs(h_eq) ** 2, w))
    return float(np.sqrt(num / max(den, 1e-30)))


def tdecq_report(P_w, symbols, spec, sps, symbol_rate_hz, fs_hz,
                 target_ser=4.8e-4, q_t=3.414,
                 histogram_width_ui=0.04):
    """TDECQ con la struttura di clause 121.8.5.3 — DICHIARATO non certificato.

    Procedura implementata (ogni passo come da clause, con le deviazioni
    dichiarate): filtro di ricezione Bessel-Thomson 4° ordine a 0.5·baud
    (qui zero-fase); equalizzatore di riferimento FFE 5 tap T-spaced
    adattato MMSE; due finestre verticali centrate a 0.45 e 0.55 UI, larghe
    0.04 UI; rumore gaussiano σ_G aggiunto ALL'INGRESSO dell'equalizzatore.
    C_eq e integrato dalla PSD del rumore bianco sagomata dal BT4 e dalla
    risposta dei tap T-spaced (Equation 121-9), non approssimato con la sola
    norma L2 dei tap. Si cerca il σ_G che porta il SER medio delle due
    finestre al target 4.8e-4.

    TDECQ = 10·log10(σ_ideal / σ_G),  σ_ideal = OMA_outer/(6·Q_t), Q_t=3.414.
    Deviazioni dichiarate: BT4 zero-fase; adattamento con i simboli noti
    (bench, non pattern lock dello strumento); la ricerca dei tap usa una
    griglia ridge finita, non l'ottimizzazione strumentale esaustiva.
    """
    from scipy import signal as _sig
    P = np.asarray(P_w, dtype=float)
    sym = np.asarray(symbols)
    levels = spec.levels_array
    m = len(levels)

    # 1. filtro di ricezione BT4 0.5·baud (zero-fase, dichiarato)
    wn = min(0.5 * symbol_rate_hz / (fs_hz / 2), 0.99)
    b, a = _sig.bessel(4, wn, btype="low", norm="mag")
    Pf = _sig.filtfilt(b, a, P)

    # 2. allineamento: offset intero via correlazione, poi fase fine a
    # passi di 0.02 UI (il campionamento è frazionario, non troncato)
    k = np.arange(200, len(sym) - 200)
    grid = np.arange(len(Pf), dtype=float)

    def sample_at(off, sub=1):
        pos = (k[::sub] + 0.5 + off) * sps
        ok = (pos > 2) & (pos < len(Pf) - 2)
        return np.interp(pos[ok], grid, Pf), sym[k[::sub][ok]]

    best = (0.0, 0.0)
    for d_int in (-2, -1, 0, 1, 2):
        y, t = sample_at(float(d_int), sub=7)
        c = float(np.corrcoef(y, t)[0, 1])
        if abs(c) > abs(best[1]):
            best = (float(d_int), c)
    delay = best[0]
    if best[1] < 0:          # catena non invertente sull'ottica, ma guardia
        sym = -sym
    # fase fine: massimizza la correlazione (proxy del centro occhio)
    fine = (0.0, -1.0)
    for ph in np.arange(-0.45, 0.451, 0.02):
        y, t = sample_at(delay + ph, sub=7)
        c = abs(float(np.corrcoef(y, t)[0, 1]))
        if c > fine[1]:
            fine = (ph, c)
    delay += fine[0]

    def sample(ph):
        return sample_at(delay + ph)

    # 3. FFE di riferimento 5 tap T-spaced. Come da clause, l'equalizzatore
    # è scelto per MINIMIZZARE il TDECQ: un fit MMSE puro inverte il droop
    # del BT4 gonfiando C_eq (noise enhancement) anche quando non serve.
    # Si esplora una griglia di regolarizzazione ridge e si tiene il minimo.
    y0, t0 = sample(0.0)
    X = np.stack([np.roll(y0, sh) for sh in (-2, -1, 0, 1, 2)], axis=1)
    Xv, tv = X[4:-4], t0[4:-4]
    p_levels = np.interp(tv, levels, np.linspace(0.0, 1.0, m))
    scale = float(np.percentile(y0, 99.5) - np.percentile(y0, 0.5))
    base = float(np.percentile(y0, 0.5))
    target = base + scale * p_levels
    XtX = Xv.T @ Xv
    Xty = Xv.T @ target
    trace_n = float(np.trace(XtX)) / XtX.shape[0]

    # 121.8.5.3: finestre larghe 0.04 UI centrate a 0.45/0.55 UI. Cinque
    # sezioni per finestra integrano il contenuto orizzontale senza
    # trasformarlo in due campioni puntuali.
    if not (0 < histogram_width_ui <= 0.20):
        raise ValueError("histogram_width_ui deve essere in (0, 0.20]")

    def sample_window(center_offset):
        ys, ts = [], []
        for dph in np.linspace(-histogram_width_ui / 2,
                               histogram_width_ui / 2, 5):
            yy, tt = sample(center_offset + float(dph))
            ys.append(yy)
            ts.append(tt)
        return np.concatenate(ys), np.concatenate(ts)

    y_m, t_m = sample_window(-0.05)
    y_p, t_p = sample_window(+0.05)

    def clusters_for(taps, y, t):
        Xp = np.stack([np.roll(y, sh) for sh in (-2, -1, 0, 1, 2)], axis=1)
        ye = (Xp @ taps)[4:-4]
        tt = t[4:-4]
        mus, sig = [], []
        for lv in levels:
            x = ye[np.isclose(tt, lv)]
            if len(x) < 30:
                return None
            mus.append(float(np.mean(x)))
            sig.append(float(np.std(x)))
        order = np.argsort(mus)
        return np.asarray(mus)[order], np.asarray(sig)[order]

    def ser_with(cl, ceq, sigma_g):
        tot = 0.0
        for mus, sig in cl:
            thr = 0.5 * (mus[:-1] + mus[1:])
            bounds = np.r_[-np.inf, thr, np.inf]
            ser = 0.0
            for i in range(m):
                s_eff = max(float(np.sqrt(sig[i] ** 2
                                          + (sigma_g * ceq) ** 2)), 1e-30)
                cdf = stats.norm.cdf((bounds - mus[i]) / s_eff)
                probs = np.diff(cdf)
                ser += (1.0 - probs[i]) / m
            tot += ser / len(cl)
        return tot

    best_out = None
    for lam in (0.0, 1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3):
        try:
            taps = np.linalg.solve(
                XtX + lam * trace_n * np.eye(5), Xty)
        except np.linalg.LinAlgError:
            continue
        # Il reference equalizer ha guadagno DC unitario: Σc[k] = 1.
        tap_sum = float(np.sum(taps))
        if abs(tap_sum) < 1e-12:
            continue
        taps = taps / tap_sum
        ceq = _tdecq_noise_enhancement(taps, b, a, sps)
        cl = [clusters_for(taps, y_m, t_m), clusters_for(taps, y_p, t_p)]
        if any(c is None for c in cl):
            continue
        oma_outer = float(np.mean([c[0][-1] - c[0][0] for c in cl]))
        if oma_outer <= 0:
            continue
        sigma_ideal = oma_outer / (6.0 * q_t)
        if ser_with(cl, ceq, 0.0) > target_ser:
            continue
        lo, hi = 0.0, 4.0 * sigma_ideal
        while ser_with(cl, ceq, hi) < target_ser and hi < 64 * sigma_ideal:
            hi *= 2
        for _ in range(45):
            mid = 0.5 * (lo + hi)
            if ser_with(cl, ceq, mid) < target_ser:
                lo = mid
            else:
                hi = mid
        sigma_g = 0.5 * (lo + hi)
        tdecq = float(10 * np.log10(sigma_ideal / max(sigma_g, 1e-30)))
        if best_out is None or tdecq < best_out["tdecq_db"]:
            best_out = {"tdecq_db": tdecq, "sigma_ideal": sigma_ideal,
                        "sigma_g": sigma_g, "oma_outer": oma_outer,
                        "ceq_db": float(20 * np.log10(ceq)),
                        "taps": [float(v) for v in taps],
                        "tap_sum": float(np.sum(taps)),
                        "ridge_lambda": lam,
                        "target_ser": target_ser, "q_t": q_t,
                        "histogram_centers_ui": [0.45, 0.55],
                        "histogram_width_ui": histogram_width_ui,
                        "reference_receiver_bw_hz": 0.5 * symbol_rate_hz,
                        "ceq_method": "BT4-shaped noise integral (121-9)"}
    if best_out is None:
        return {"tdecq_db": None,
                "reason": "SER oltre il target per ogni equalizzatore provato"}
    return best_out
