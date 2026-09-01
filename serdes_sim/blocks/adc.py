"""ADC 2 sps time-interleaved in architettura di nuova generazione.

Modello allineato ai RX ADC-based 112G/224G: array SAR fino a 64 vie dietro
pochi rank di track&hold veloci (skew e banda condivisi per rank), banda del
front-end con spread fra i rank (mismatch dipendente dalla frequenza, che la
calibrazione gain/offset/skew NON corregge), calibrazione foreground/
background/off che interagisce col PVT, rumore termico input-referred,
aperture jitter, TIE comune sinusoidale, quantizzazione. Il tone-lab misura
SNDR/ENOB/spur sia a bassa frequenza sia vicino a Nyquist (dove skew e banda
dominano davvero). Con i default storici (rank=1, banda off, cal foreground,
rumore 0) il percorso è BIT-IDENTICO al modello precedente."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..utils import (apply_frequency_response, butterworth_response, db20,
                     quantize_bipolar)


def centered_rms_pattern(rng, count, target_rms):
    x = rng.normal(size=count)
    x -= np.mean(x)
    rms = float(np.sqrt(np.mean(x ** 2)))
    if target_rms == 0 or rms == 0:
        return np.zeros(count)
    return x * (target_rms / rms)


@dataclass
class AdcResult:
    lane_gain: np.ndarray
    lane_offset_v: np.ndarray
    lane_skew_s: np.ndarray
    adc_nominal_time_ui: np.ndarray
    adc_samples_v: np.ndarray
    adc_lsb_v: float
    adc_clip_fraction: float
    cal_effective: float = 1.0            # fattore residuo applicato ai mismatch
    lane_rank: np.ndarray | None = None   # rank T/H di ogni lane (None = flat)
    rank_skew_s: np.ndarray | None = None
    rank_bw_hz: np.ndarray | None = None  # banda effettiva per rank (None = off)


def cal_residual_factor(cfg, mismatch_pvt: float) -> float:
    """Quanto mismatch residuo resta nell'array, e se insegue il PVT.

    - foreground (storico): residui statici calibrati a nominale; con il PVT
      il residuo scala col fattore mismatch di processo/temperatura;
    - background: la calibrazione insegue lentamente PVT/temperatura, il
      residuo resta quello nominale di targa;
    - off: array SAR non calibrato — mismatch grezzi, ×8 DICHIARATO rispetto
      ai residui (ordine di grandezza da letteratura, non un dato di targa).
    """
    if cfg.adc_cal_mode == "background":
        return 1.0
    if cfg.adc_cal_mode == "off":
        return 8.0 * mismatch_pvt
    return mismatch_pvt


def run_adc(cfg, v_ctle_v, rng) -> AdcResult:
    M = cfg.adc_interleaves
    # i mismatch fra i lane peggiorano ai corner di processo e con |ΔT|;
    # la calibrazione decide quanto ne resta (cal_residual_factor)
    eff = cal_residual_factor(cfg, cfg.pvt_factors["mismatch"])
    lane_gain = centered_rms_pattern(rng, M, cfg.adc_gain_mismatch_rms * eff)
    lane_offset_v = centered_rms_pattern(
        rng, M, cfg.adc_offset_mismatch_rms_v * eff)
    lane_skew_s = centered_rms_pattern(
        rng, M, cfg.adc_skew_mismatch_rms_fs * 1e-15 * eff)

    # gerarchia a rank (SOTA 112/224G: pochi T/H veloci davanti a molti SAR
    # lenti): i lane di uno stesso rank CONDIVIDONO skew e banda del rank —
    # è ciò che concentra le spur alle righe k·fs/R invece di k·fs/M
    R = max(1, int(cfg.adc_ranks))
    lane_rank = None
    rank_skew_s = None
    if R > 1:
        lane_rank = np.arange(M) % R
        rank_skew_s = centered_rms_pattern(
            rng, R, cfg.adc_skew_mismatch_rms_fs * 1e-15 * eff)
        lane_skew_s = lane_skew_s + rank_skew_s[lane_rank]

    n_adc = cfg.n_symbols * cfg.adc_sps
    adc_n = np.arange(n_adc)
    adc_lane = adc_n % M
    # rx_ppm_offset: il clock RX corre a (1+ppm) rispetto al TX, quindi le
    # posizioni dei campioni (in UI del TX) scivolano — il CDR deve inseguirle
    ppm_scale = 1.0 + getattr(cfg, "rx_ppm_offset", 0.0) * 1e-6
    adc_nominal_time_ui = adc_n / cfg.adc_sps * ppm_scale + cfg.adc_phase_ui
    common_tie_ui = 0.012 * np.sin(2 * np.pi * adc_n / (1700 * cfg.adc_sps))
    aperture_jitter_ui = rng.normal(0, cfg.adc_jitter_rms_fs * 1e-15 / cfg.ui_s, n_adc)
    adc_actual_time_ui = (adc_nominal_time_ui + common_tie_ui + aperture_jitter_ui
                          + lane_skew_s[adc_lane] / cfg.ui_s)

    # front-end T/H: polo del 1° ordine per rank con spread di banda — un
    # mismatch DIPENDENTE dalla frequenza, che la cal gain/offset/skew non
    # può correggere (servirebbero equalizzatori per-lane; dichiarato)
    rank_bw_hz = None
    grid = np.arange(len(v_ctle_v))
    if cfg.adc_frontend_bw_hz > 0:
        spread = (centered_rms_pattern(rng, R, cfg.adc_bw_mismatch_pct / 100)
                  if cfg.adc_bw_mismatch_pct > 0 else np.zeros(R))
        rank_bw_hz = cfg.adc_frontend_bw_hz * np.maximum(1 + spread, 0.2)
        adc_frontend_v = np.empty(n_adc)
        sample_rank = adc_lane % R
        for ri in range(R):
            filt, _, _ = apply_frequency_response(
                v_ctle_v, cfg.fs_analog_hz,
                lambda f, bw=rank_bw_hz[ri]: butterworth_response(
                    f, bw, order=1, causal=cfg.causal_filters))
            sel = sample_rank == ri
            adc_frontend_v[sel] = np.interp(
                adc_actual_time_ui[sel] * cfg.analog_sps, grid, filt)
    else:
        adc_frontend_v = np.interp(
            adc_actual_time_ui * cfg.analog_sps, grid, v_ctle_v)
    adc_mismatched_v = (adc_frontend_v * (1 + lane_gain[adc_lane])
                        + lane_offset_v[adc_lane])
    if cfg.adc_noise_rms_mv > 0:
        # rumore termico input-referred (kT/C + comparatore + reference)
        adc_mismatched_v = adc_mismatched_v + rng.normal(
            0, cfg.adc_noise_rms_mv * 1e-3, n_adc)
    adc_samples_v, _, adc_lsb_v, adc_clip_fraction = quantize_bipolar(
        adc_mismatched_v, cfg.adc_bits, cfg.adc_full_scale_vpp)

    return AdcResult(
        lane_gain=lane_gain,
        lane_offset_v=lane_offset_v,
        lane_skew_s=lane_skew_s,
        adc_nominal_time_ui=adc_nominal_time_ui,
        adc_samples_v=adc_samples_v,
        adc_lsb_v=float(adc_lsb_v),
        adc_clip_fraction=adc_clip_fraction,
        cal_effective=float(eff),
        lane_rank=lane_rank,
        rank_skew_s=rank_skew_s,
        rank_bw_hz=rank_bw_hz,
    )


@dataclass
class ToneLabResult:
    freq_hz: np.ndarray
    spec_ideal_dbfs: np.ndarray
    spec_mismatch_dbfs: np.ndarray
    sndr_ideal_db: float
    sndr_mismatch_db: float
    enob_ideal: float
    enob_mismatch: float
    spur_ideal_dbfs: float
    spur_mismatch_dbfs: float
    interleave_lines_hz: np.ndarray
    # tono vicino a Nyquist: dove skew e banda dominano davvero (il numero
    # di targa dei SerDes di nuova generazione è l'ENOB a Nyquist)
    tone_low_hz: float = 0.0
    tone_nyq_hz: float = 0.0
    sndr_nyq_ideal_db: float = float("nan")
    sndr_nyq_db: float = float("nan")
    enob_nyq_ideal: float = float("nan")
    enob_nyq: float = float("nan")
    spur_nyq_dbfs: float = float("nan")


def adc_spectrum_metrics(x, tone_bin, full_scale_peak_v):
    x = np.asarray(x) - np.mean(x)
    X = np.fft.rfft(x)
    amp = 2 * np.abs(X) / len(x)
    amp[0] *= 0.5
    power = amp ** 2 / 2
    mask = np.ones_like(power, dtype=bool)
    mask[[0, tone_bin]] = False
    sndr = 10 * np.log10(power[tone_bin] / np.sum(power[mask]))
    spur = np.max(amp[mask])
    return (sndr, (sndr - 1.76) / 6.02,
            db20(np.maximum(amp / full_scale_peak_v, 1e-12)),
            float(db20(spur / full_scale_peak_v)))


def _tone_pair(cfg, adc: AdcResult, tone_bin: int, n_tone: int, rng=None):
    """Coppia (ideale, effettiva) per un tono coerente a tone_bin.

    Il ramo "effettivo" include gain/offset/skew per lane, il polo di banda
    del rank (ampiezza+fase alla frequenza del tono), l'aperture jitter e il
    rumore input-referred: l'ENOB riportato è quello EFFETTIVO del
    convertitore, non il solo limite quantizzazione+mismatch — a Nyquist il
    jitter domina (SNR_j = −20·log10(2π·f·σ_t)), come nei datasheet reali.
    Il ramo ideale resta la sola quantizzazione (riferimento)."""
    M = cfg.adc_interleaves
    fs_adc_hz = cfg.fs_adc_hz
    tone_hz = tone_bin * fs_adc_hz / n_tone
    n = np.arange(n_tone)
    lanes = n % M
    t_ideal_s = n / fs_adc_hz
    t_bad_s = t_ideal_s + adc.lane_skew_s[lanes]
    if rng is not None and cfg.adc_jitter_rms_fs > 0:
        t_bad_s = t_bad_s + rng.normal(0, cfg.adc_jitter_rms_fs * 1e-15,
                                       n_tone)
    tone_ideal_v = 0.48 * np.sin(2 * np.pi * tone_hz * t_ideal_s)
    amp = np.ones(M)
    ph = np.zeros(M)
    if adc.rank_bw_hz is not None:
        R = len(adc.rank_bw_hz)
        h = 1.0 / (1.0 + 1j * tone_hz / adc.rank_bw_hz)   # polo 1° ordine
        lane_h = h[np.arange(M) % R]
        amp = np.abs(lane_h)
        ph = np.angle(lane_h)
    tone_bad_v = (0.48 * amp[lanes]
                  * np.sin(2 * np.pi * tone_hz * t_bad_s + ph[lanes])
                  * (1 + adc.lane_gain[lanes]) + adc.lane_offset_v[lanes])
    if rng is not None and cfg.adc_noise_rms_mv > 0:
        tone_bad_v = tone_bad_v + rng.normal(0, cfg.adc_noise_rms_mv * 1e-3,
                                             n_tone)
    tone_ideal_q = quantize_bipolar(tone_ideal_v, cfg.adc_bits,
                                    cfg.adc_full_scale_vpp)[0]
    tone_bad_q = quantize_bipolar(tone_bad_v, cfg.adc_bits,
                                  cfg.adc_full_scale_vpp)[0]
    fs_peak = cfg.adc_full_scale_vpp / 2
    return (tone_hz,
            adc_spectrum_metrics(tone_ideal_q, tone_bin, fs_peak),
            adc_spectrum_metrics(tone_bad_q, tone_bin, fs_peak))


def run_tone_lab(cfg, adc: AdcResult) -> ToneLabResult:
    """Tono coerente attraverso il modello di mismatch: isola spur k*fs/M.

    Due toni: uno basso (spettro esportato, come da sempre) e uno vicino a
    Nyquist (~0.45·fs) per SNDR/ENOB dove skew, banda e jitter pesano
    davvero. Il ramo effettivo usa un rng LOCALE deterministico (il tone-lab
    è uno strumento, non il datapath: non consuma il rng del record)."""
    M = cfg.adc_interleaves
    n_tone = 2 ** 14
    tone_bin = 997
    fs_adc_hz = cfg.fs_adc_hz
    rng = np.random.default_rng(20240731)
    tone_hz, (sndr_i, enob_i, spec_i, spur_i), (sndr_b, enob_b, spec_b, spur_b) = \
        _tone_pair(cfg, adc, tone_bin, n_tone, rng=rng)
    nyq_bin = 7333                       # ≈0.4475·fs, non armonico di fs/M
    nyq_hz, (sndr_ni, enob_ni, _, _), (sndr_nb, enob_nb, _, spur_nb) = \
        _tone_pair(cfg, adc, nyq_bin, n_tone, rng=rng)
    freq_hz = np.fft.rfftfreq(n_tone, 1 / fs_adc_hz)
    lines = np.array([k * fs_adc_hz / M for k in range(1, M // 2 + 1)])
    return ToneLabResult(
        freq_hz=freq_hz,
        spec_ideal_dbfs=spec_i,
        spec_mismatch_dbfs=spec_b,
        sndr_ideal_db=float(sndr_i),
        sndr_mismatch_db=float(sndr_b),
        enob_ideal=float(enob_i),
        enob_mismatch=float(enob_b),
        spur_ideal_dbfs=spur_i,
        spur_mismatch_dbfs=spur_b,
        interleave_lines_hz=lines,
        tone_low_hz=float(tone_hz),
        tone_nyq_hz=float(nyq_hz),
        sndr_nyq_ideal_db=float(sndr_ni),
        sndr_nyq_db=float(sndr_nb),
        enob_nyq_ideal=float(enob_ni),
        enob_nyq=float(enob_nb),
        spur_nyq_dbfs=float(spur_nb),
    )
