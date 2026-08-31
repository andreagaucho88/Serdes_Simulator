"""ADC 2 sps time-interleaved: gain/offset/skew per lane, aperture jitter,
TIE comune sinusoidale, quantizzazione. Include il tone-lab per spur/SNDR."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..utils import db20, quantize_bipolar


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


def run_adc(cfg, v_ctle_v, rng) -> AdcResult:
    M = cfg.adc_interleaves
    lane_gain = centered_rms_pattern(rng, M, cfg.adc_gain_mismatch_rms)
    lane_offset_v = centered_rms_pattern(rng, M, cfg.adc_offset_mismatch_rms_v)
    lane_skew_s = centered_rms_pattern(rng, M, cfg.adc_skew_mismatch_rms_fs * 1e-15)

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

    adc_frontend_v = np.interp(
        adc_actual_time_ui * cfg.analog_sps,
        np.arange(len(v_ctle_v)), v_ctle_v)
    adc_mismatched_v = adc_frontend_v * (1 + lane_gain[adc_lane]) + lane_offset_v[adc_lane]
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


def run_tone_lab(cfg, adc: AdcResult) -> ToneLabResult:
    """Tono coerente attraverso il modello di mismatch: isola spur k*fs/M."""
    M = cfg.adc_interleaves
    n_tone = 2 ** 14
    tone_bin = 997
    fs_adc_hz = cfg.fs_adc_hz
    tone_hz = tone_bin * fs_adc_hz / n_tone
    n = np.arange(n_tone)
    lanes = n % M
    t_ideal_s = n / fs_adc_hz
    t_bad_s = t_ideal_s + adc.lane_skew_s[lanes]
    tone_ideal_v = 0.48 * np.sin(2 * np.pi * tone_hz * t_ideal_s)
    tone_bad_v = (0.48 * np.sin(2 * np.pi * tone_hz * t_bad_s)
                  * (1 + adc.lane_gain[lanes]) + adc.lane_offset_v[lanes])
    tone_ideal_q = quantize_bipolar(tone_ideal_v, cfg.adc_bits, cfg.adc_full_scale_vpp)[0]
    tone_bad_q = quantize_bipolar(tone_bad_v, cfg.adc_bits, cfg.adc_full_scale_vpp)[0]
    sndr_i, enob_i, spec_i, spur_i = adc_spectrum_metrics(tone_ideal_q, tone_bin, cfg.adc_full_scale_vpp / 2)
    sndr_b, enob_b, spec_b, spur_b = adc_spectrum_metrics(tone_bad_q, tone_bin, cfg.adc_full_scale_vpp / 2)
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
    )
