"""Metriche: BER con intervalli di confidenza, statistiche per livello,
LLR calibrati e GMI, waterfall detector-only, bathtub empirica + dual-Dirac,
BER contour, segmenti eye."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats
from scipy.special import logsumexp

from ..standards import (SNDR_FIT_NP, TDECQ_HISTOGRAM_CENTERS_UI,
                         TDECQ_HISTOGRAM_WIDTH_UI, TDECQ_Q_T,
                         TDECQ_REFERENCE_RX_BW_FRACTION, TDECQ_TARGET_SER)
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
                 target_ser=TDECQ_TARGET_SER, q_t=TDECQ_Q_T,
                 histogram_width_ui=TDECQ_HISTOGRAM_WIDTH_UI,
                 sigma_s_w=0.0, measure="TDECQ", optimize="mmse",
                 rx_bw_fraction=None):
    """TDECQ con la struttura di clause 121.8.5.3 — DICHIARATO non certificato.

    ``sigma_s_w`` è il rumore RMS del ricevitore di misura (O/E + scope,
    121.8.5.3): il rapporto usa sqrt(σ_G² + σ_S²) nella forma dell'equazione
    121-11 come implementata qui. Nel banco numerico σ_S = 0 (dichiarato
    ideale), quindi il valore coincide con 10·log10(σ_ideal/σ_G).
    ``measure`` etichetta il risultato (TDECQ a TP2 dopo il canale di
    dispersione; TECQ per la stessa procedura senza canale ottico).

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
    (bench, non pattern lock dello strumento). ``optimize="mmse"`` (default
    storico) sceglie i tap su una griglia ridge MMSE; ``optimize="min_tdecq"``
    parte da lì e ottimizza i tap per il TDECQ minimo come richiede
    121.8.5.3. ``rx_bw_fraction`` sovrascrive la banda del BT4 (0.5·baud di
    clausola) per correlazioni con strumenti che usano un'altra impostazione.
    """
    from scipy import signal as _sig
    P = np.asarray(P_w, dtype=float)
    sym = np.asarray(symbols)
    levels = spec.levels_array
    m = len(levels)

    # 1. filtro di ricezione BT4 0.5·baud (zero-fase, dichiarato)
    bw_frac = (TDECQ_REFERENCE_RX_BW_FRACTION if rx_bw_fraction is None
               else float(rx_bw_fraction))
    wn = min(bw_frac * symbol_rate_hz / (fs_hz / 2), 0.99)
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

    centers = tuple(float(c) - 0.5 for c in TDECQ_HISTOGRAM_CENTERS_UI)
    y_m, t_m = sample_window(centers[0])
    y_p, t_p = sample_window(centers[1])

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

    def evaluate(taps, lam=None):
        """TDECQ per un set di tap; None se il SER resta sopra il target
        anche senza rumore aggiunto. Il reference equalizer ha guadagno DC
        unitario: Σc[k] = 1."""
        taps = np.asarray(taps, dtype=float)
        tap_sum = float(np.sum(taps))
        if abs(tap_sum) < 1e-12:
            return None
        taps = taps / tap_sum
        ceq = _tdecq_noise_enhancement(taps, b, a, sps)
        cl = [clusters_for(taps, y_m, t_m), clusters_for(taps, y_p, t_p)]
        if any(c is None for c in cl):
            return None
        oma_outer = float(np.mean([c[0][-1] - c[0][0] for c in cl]))
        if oma_outer <= 0:
            return None
        sigma_ideal = oma_outer / (6.0 * q_t)
        if ser_with(cl, ceq, 0.0) > target_ser:
            return None
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
        sigma_total = float(np.sqrt(sigma_g ** 2 + float(sigma_s_w) ** 2))
        tdecq = float(10 * np.log10(sigma_ideal / max(sigma_total, 1e-30)))
        return {"tdecq_db": tdecq, "sigma_ideal": sigma_ideal,
                "sigma_g": sigma_g, "sigma_s": float(sigma_s_w),
                "oma_outer": oma_outer,
                "ceq_db": float(20 * np.log10(ceq)),
                "taps": [float(v) for v in taps],
                "tap_sum": float(np.sum(taps)),
                "ridge_lambda": lam,
                "target_ser": target_ser, "q_t": q_t,
                "histogram_centers_ui": list(TDECQ_HISTOGRAM_CENTERS_UI),
                "histogram_width_ui": histogram_width_ui,
                "reference_receiver_bw_hz": bw_frac * symbol_rate_hz,
                "ceq_method": "BT4-shaped noise integral (121-9)",
                "equalizer_optimization": optimize,
                "measure": measure}

    best_out = None
    for lam in (0.0, 1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3):
        try:
            taps = np.linalg.solve(
                XtX + lam * trace_n * np.eye(5), Xty)
        except np.linalg.LinAlgError:
            continue
        out = evaluate(taps, lam)
        if out is not None and (best_out is None
                                or out["tdecq_db"] < best_out["tdecq_db"]):
            best_out = out
    if optimize == "min_tdecq" and best_out is not None:
        # 121.8.5.3: i tap dell'equalizzatore di riferimento sono ottimizzati
        # per MINIMIZZARE il TDECQ, non in senso MMSE. Ricerca Nelder-Mead sui
        # 4 tap liberi (somma vincolata a 1) a partire dalla soluzione
        # MMSE/ridge migliore.
        from scipy import optimize as _opt
        start = np.asarray(best_out["taps"], dtype=float)
        free_idx = [0, 1, 3, 4]

        def unpack(v):
            t = np.zeros(5)
            t[free_idx] = v
            t[2] = 1.0 - float(np.sum(v))
            return t

        def cost(v):
            out = evaluate(unpack(v))
            return 1e3 if out is None else out["tdecq_db"]

        res = _opt.minimize(cost, start[free_idx], method="Nelder-Mead",
                            options={"xatol": 1e-3, "fatol": 2e-3,
                                     "maxiter": 400})
        out = evaluate(unpack(res.x))
        if out is not None and out["tdecq_db"] < best_out["tdecq_db"]:
            out["ridge_lambda"] = best_out["ridge_lambda"]
            out["optimizer_iterations"] = int(res.nit)
            best_out = out
    if best_out is None:
        return {"tdecq_db": None, "measure": measure,
                "reason": {"it": "SER oltre il target per ogni equalizzatore provato",
                           "en": "SER above target for every equalizer tried"}}
    return best_out


def tecq_report(P_tp2_w, symbols, spec, sps, symbol_rate_hz, fs_hz, **kw):
    """TECQ: la stessa procedura del TDECQ applicata alla waveform a TP2
    senza il canale ottico di dispersione (struttura 802.3db, dichiarata)."""
    return tdecq_report(P_tp2_w, symbols, spec, sps, symbol_rate_hz, fs_hz,
                        measure="TECQ", **kw)


# ---------------------------------------------------------------------------
# Trasmettitore PAM4: RLM (formula di clause) e SNDR (fit lineare Y = P·X)
# ---------------------------------------------------------------------------

def rlm_clause(level_means):
    """Level separation mismatch ratio con la formula di IEEE 802.3
    (120D.3.1.2 / 162.9.3.1): V_mid=(V0+V3)/2, ES1=(V1−V_mid)/(V0−V_mid),
    ES2=(V2−V_mid)/(V3−V_mid), RLM=min(3·ES1, 3·ES2, 2−3·ES1, 2−3·ES2).

    DICHIARATO: i livelli medi arrivano dal pattern attivo del banco, non dal
    pattern di linearità di clause, quindi il risultato è un proxy."""
    v = sorted(float(x) for x in level_means)
    if len(v) != 4:
        return None
    v0, v1, v2, v3 = v
    v_mid = 0.5 * (v0 + v3)
    d0, d3 = v0 - v_mid, v3 - v_mid
    if abs(d0) < 1e-30 or abs(d3) < 1e-30:
        return None
    es1 = (v1 - v_mid) / d0
    es2 = (v2 - v_mid) / d3
    rlm = min(3 * es1, 3 * es2, 2 - 3 * es1, 2 - 3 * es2)
    return {"rlm": float(rlm), "es1": float(es1), "es2": float(es2),
            "v_mid": float(v_mid), "levels": v,
            "method": "clause formula on measured level means (pattern proxy)"}


def sndr_linear_fit(wave, symbols, sps, delay_ui=0.0, np_taps=SNDR_FIT_NP,
                    pre_taps=None):
    """SNDR con la struttura di 120D.3.1.5/.6: fit lineare Y = P·X del
    pulse response su tutte le M fasi per UI, Np tap in UI, residuo e.

    SNDR = 10·log10(p_max² / σ_e²). DICHIARATO: σ_n (rumore misurato con
    pattern statico) non è separato dal residuo; il pattern è quello attivo.
    Una colonna costante assorbe l'offset DC."""
    w = np.asarray(wave, dtype=float)
    x = np.asarray(symbols, dtype=float)
    x = x - float(np.mean(x))
    sps = int(sps)
    n_sym = len(w) // sps
    if n_sym < np_taps + 64:
        return None
    pre = int(pre_taps if pre_taps is not None else max(2, np_taps // 8))
    post = np_taps - pre
    n0 = pre + 200
    n1 = min(n_sym - post - 2, len(x) - post - 2)
    if n1 - n0 < 256:
        return None
    n = np.arange(n0, n1)
    # matrice X (N × Np): x[n − j + pre], più colonna costante
    cols = [x[n - j + pre] for j in range(np_taps)]
    X = np.stack(cols + [np.ones(len(n))], axis=1)
    shift = int(round(float(delay_ui) * sps))
    Y = np.stack([w[n * sps + m + shift] for m in range(sps)], axis=1)   # N × M
    try:
        P, *_ = np.linalg.lstsq(X, Y, rcond=None)
    except np.linalg.LinAlgError:
        return None
    E = Y - X @ P
    sigma_e = float(np.sqrt(np.mean(E ** 2)))
    pulse = P[:-1]                                # Np × M
    p_max = float(np.max(np.abs(pulse)))
    if p_max < 1e-15 or sigma_e < 1e-30:
        return None
    j_max, m_max = np.unravel_index(int(np.argmax(np.abs(pulse))), pulse.shape)
    return {"sndr_db": float(10 * np.log10(p_max ** 2 / sigma_e ** 2)),
            "p_max": p_max, "sigma_e": sigma_e, "np_taps": int(np_taps),
            "m_phases": sps, "pre_taps": pre,
            "peak_tap_ui": int(j_max) - pre, "peak_phase": int(m_max),
            "method": "linear-fit pulse response Y=P·X (σn folded into σe)"}


def optical_levels_runs(P_w, symbols, levels, sps, delay_ui=0.0, min_run=4,
                        window=0.2):
    """Livelli ottici P0…P3 sui run di simboli identici (struttura del metodo
    di clause per OMA_outer/ER: media sulla finestra centrale del run).

    DICHIARATO: run ≥ ``min_run`` simboli e finestra centrale ``window``
    sono parametri dichiarati, non ancora verificati sul testo di clause."""
    P = np.asarray(P_w, dtype=float)
    sym = np.asarray(symbols)
    lv = np.asarray(levels, dtype=float)
    sps = int(sps)
    shift = int(round(float(delay_ui) * sps))
    means, counts = [], []
    # confini dei run
    change = np.flatnonzero(np.diff(sym) != 0) + 1
    starts = np.r_[0, change]
    ends = np.r_[change, len(sym)]
    for level in lv:
        acc, n_acc = 0.0, 0
        for s, e in zip(starts, ends):
            if e - s < min_run or not np.isclose(sym[s], level):
                continue
            a = s * sps + shift
            b = e * sps + shift
            span = b - a
            lo = a + int(round(span * (0.5 - window / 2)))
            hi = a + int(round(span * (0.5 + window / 2)))
            if lo < 0 or hi > len(P) or hi <= lo:
                continue
            seg = P[lo:hi]
            acc += float(np.sum(seg))
            n_acc += len(seg)
        means.append(acc / n_acc if n_acc else None)
        counts.append(n_acc)
    if any(m is None for m in means):
        return None
    p0, p3 = means[0], means[-1]
    return {"p_levels_w": [float(m) for m in means], "samples": counts,
            "oma_outer_w": float(p3 - p0), "p_avg_w": float(np.mean(P)),
            "extinction_ratio_db": (float(10 * np.log10(p3 / p0))
                                    if p0 > 0 and p3 > 0 else None),
            "min_run": int(min_run), "window": float(window),
            "method": "run-based level means, central window (declared)"}


def _point_in_polygon(px, py, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            xint = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if px < xint:
                inside = not inside
    return inside


def eye_mask_hits(traces, mask, p0, p1):
    """Conteggio dei campioni dentro la maschera NRZ (geometria dichiarata:
    esagono X1/X2/Y1 + bande y ≥ 1+Y3 e y ≤ −Y3), su tracce di 2 UI
    centrate sul simbolo (colonna centrale = centro UI).

    ``p0``/``p1`` normalizzano l'ampiezza ai livelli 0/1 misurati."""
    tr = np.asarray(traces, dtype=float)
    if tr.ndim != 2 or tr.shape[1] < 8 or p1 <= p0:
        return None
    n_tr, n_col = tr.shape
    sps = (n_col - 1) / 2.0
    x = (np.arange(n_col) - sps) / sps + 0.5          # UI, 0.5 = centro
    y = (tr - p0) / (p1 - p0)
    x1, x2, y1, y3 = mask["x1"], mask["x2"], mask["y1"], mask["y3"]
    hexagon = [(x1, 0.5), (x2, y1), (1 - x2, y1), (1 - x1, 0.5),
               (1 - x2, 1 - y1), (x2, 1 - y1)]
    in_ui = (x >= 0.0) & (x <= 1.0)
    cols = np.flatnonzero(in_ui)
    hits = 0
    total = n_tr * len(cols)
    for c in cols:
        yc = y[:, c]
        band = np.count_nonzero((yc >= 1 + y3) | (yc <= -y3))
        # hexagon test only for points within its vertical extent
        cand = np.flatnonzero((yc > y1) & (yc < 1 - y1))
        hexhits = sum(1 for k in cand if _point_in_polygon(float(x[c]), float(yc[k]), hexagon))
        hits += band + hexhits
    ratio = hits / total if total else None
    return {"hits": int(hits), "samples": int(total), "hit_ratio": ratio,
            "hexagon": hexagon, "bands": [1 + y3, -y3],
            "geometry": mask.get("geometry", "declared")}
