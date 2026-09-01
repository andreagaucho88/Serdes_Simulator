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
