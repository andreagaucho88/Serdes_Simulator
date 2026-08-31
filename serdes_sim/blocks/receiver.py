"""Ricevitore ottico: PD square-law, rumori (shot/TIA/RIN), TIA, AGC, CTLE."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..utils import (Q_E_C, apply_frequency_response, butterworth_magnitude,
                     butterworth_response,
                     enbw_one_sided_hz, db10, rms_ac,
                     white_noise_from_one_sided_psd)


def ctle_response(f_hz, zero_hz, pole_hz, high_pole_hz, dc_gain_db=0.0):
    if not (0 < zero_hz < pole_hz < high_pole_hz):
        raise ValueError("richiesto 0 < fz < fp < fh")
    s = 1j * np.asarray(f_hz)
    g_dc = 10 ** (dc_gain_db / 20)
    return g_dc * ((1 + s / zero_hz) / (1 + s / pole_hz)) / (1 + s / high_pole_hz)


def ctle_peaking_db(zero_hz, pole_hz, high_pole_hz, dc_gain_db=0.0,
                    f_max_hz=80e9):
    """Peaking = max|H| − |H(DC)| in dB (indicatore del boost alle alte)."""
    f = np.linspace(1e6, f_max_hz, 4001)
    H = ctle_response(f, zero_hz, pole_hz, high_pole_hz, dc_gain_db)
    mag_db = 20 * np.log10(np.abs(H))
    return float(mag_db.max() - dc_gain_db), float(f[np.argmax(mag_db)])


@dataclass
class ReceiverResult:
    i_pd_signal_a: np.ndarray
    pd_sat_fraction: float
    # noise budget (PSD one-sided all'ingresso TIA)
    S_shot_a2_hz: float
    S_tia_a2_hz: float
    S_rin_a2_hz: float
    tia_enbw_hz: float
    noise_rms_after_tia_a: dict      # sorgente -> RMS [A]
    i_pd_noisy_a: np.ndarray
    v_tia_v: np.ndarray
    tia_clip_fraction: float
    agc_gain: float
    v_agc_v: np.ndarray
    v_ctle_v: np.ndarray
    H_ctle: np.ndarray
    f_fft_hz: np.ndarray
    ctle_noise_enhancement_db: float


def run_receiver(cfg, P_fiber_w, rng) -> ReceiverResult:
    # --- Photodiode: square-law, banda, saturazione -------------------------
    i_pd_unfiltered_a = cfg.pd_responsivity_a_w * P_fiber_w + cfg.pd_dark_current_a
    i_pd_bandlimited_a, _, _ = apply_frequency_response(
        i_pd_unfiltered_a, cfg.fs_analog_hz,
        lambda f: butterworth_response(f, cfg.pd_bw_hz, order=3,
                                       causal=cfg.causal_filters))
    i_pd_signal_a = np.minimum(i_pd_bandlimited_a, cfg.pd_saturation_a)
    pd_sat_fraction = float(np.mean(i_pd_bandlimited_a > cfg.pd_saturation_a))

    # --- Noise budget -------------------------------------------------------
    # I_mean include già la dark current (sommata sopra): non va ricontata.
    # (Il builder v7 la sommava due volte; deviazione dichiarata, ~2 nA su ~µA.)
    I_mean_a = float(np.mean(i_pd_signal_a))
    RIN_linear_hz_inv = 10 ** (cfg.rin_db_hz / 10)
    S_shot_a2_hz = 2 * Q_E_C * I_mean_a
    S_tia_a2_hz = cfg.tia_noise_a_rt_hz ** 2
    S_rin_a2_hz = I_mean_a ** 2 * RIN_linear_hz_inv

    f_enbw_hz = np.linspace(0, cfg.fs_analog_hz / 2, 80_001)
    H_tia_positive = butterworth_magnitude(f_enbw_hz, cfg.tia_bw_hz, order=3)
    tia_enbw_hz = enbw_one_sided_hz(H_tia_positive, f_enbw_hz)
    noise_rms_after_tia_a = {
        "shot": float(np.sqrt(S_shot_a2_hz * tia_enbw_hz)),
        "TIA input": float(np.sqrt(S_tia_a2_hz * tia_enbw_hz)),
        "RIN": float(np.sqrt(S_rin_a2_hz * tia_enbw_hz)),
    }

    n = len(i_pd_signal_a)
    shot_white_a = white_noise_from_one_sided_psd(S_shot_a2_hz, n, cfg.fs_analog_hz, rng)
    tia_white_a = white_noise_from_one_sided_psd(S_tia_a2_hz, n, cfg.fs_analog_hz, rng)
    rin_white_a = white_noise_from_one_sided_psd(S_rin_a2_hz, n, cfg.fs_analog_hz, rng)
    i_pd_noisy_a = i_pd_signal_a + shot_white_a + tia_white_a + rin_white_a

    # --- TIA + AGC ----------------------------------------------------------
    v_tia_unfiltered_v = cfg.tia_transimpedance_ohm * i_pd_noisy_a
    v_tia_filtered_v, _, _ = apply_frequency_response(
        v_tia_unfiltered_v, cfg.fs_analog_hz,
        lambda f: butterworth_response(f, cfg.tia_bw_hz, order=3,
                                       causal=cfg.causal_filters))
    v_tia_v = np.clip(v_tia_filtered_v, -cfg.tia_clip_v, cfg.tia_clip_v)
    tia_clip_fraction = float(np.mean(np.abs(v_tia_filtered_v) > cfg.tia_clip_v))
    v_tia_ac_v = v_tia_v - np.mean(v_tia_v)
    agc_gain = float(cfg.agc_target_rms_v / max(rms_ac(v_tia_ac_v), 1e-30))
    v_agc_v = agc_gain * v_tia_ac_v

    # --- CTLE ---------------------------------------------------------------
    dc_gain_db = getattr(cfg, "ctle_dc_gain_db", 0.0)
    v_ctle_v, H_ctle, f_fft_hz = apply_frequency_response(
        v_agc_v, cfg.fs_analog_hz,
        lambda f: ctle_response(f, cfg.ctle_zero_hz, cfg.ctle_pole_hz,
                                cfg.ctle_hf_pole_hz, dc_gain_db))

    f_noise_hz = np.linspace(0, cfg.fs_analog_hz / 2, 100_001)
    Hct_pos = ctle_response(f_noise_hz, cfg.ctle_zero_hz, cfg.ctle_pole_hz,
                            cfg.ctle_hf_pole_hz, dc_gain_db)
    ctle_noise_enhancement_db = float(db10(
        np.trapz(np.abs(Hct_pos) ** 2, f_noise_hz) / (f_noise_hz[-1] - f_noise_hz[0])))

    return ReceiverResult(
        i_pd_signal_a=i_pd_signal_a,
        pd_sat_fraction=pd_sat_fraction,
        S_shot_a2_hz=S_shot_a2_hz,
        S_tia_a2_hz=S_tia_a2_hz,
        S_rin_a2_hz=S_rin_a2_hz,
        tia_enbw_hz=tia_enbw_hz,
        noise_rms_after_tia_a=noise_rms_after_tia_a,
        i_pd_noisy_a=i_pd_noisy_a,
        v_tia_v=v_tia_v,
        tia_clip_fraction=tia_clip_fraction,
        agc_gain=agc_gain,
        v_agc_v=v_agc_v,
        v_ctle_v=v_ctle_v,
        H_ctle=H_ctle,
        f_fft_hz=f_fft_hz,
        ctle_noise_enhancement_db=ctle_noise_enhancement_db,
    )
