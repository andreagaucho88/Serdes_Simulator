"""Ricevitore ottico: PD square-law, rumori (shot/TIA/RIN), TIA, AGC, CTLE."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..utils import (Q_E_C, apply_frequency_response, butterworth_magnitude,
                     butterworth_response,
                     enbw_one_sided_hz, db10, rms_ac,
                     white_noise_from_one_sided_psd)


def ctle_response(f_hz, zero_hz=None, pole_hz=None, high_pole_hz=None,
                  dc_gain_db=0.0, *, zeros_hz=None, poles_hz=None):
    """Risposta CTLE a topologia arbitraria come prodotto di sezioni reali.

    La firma scalare storica resta supportata (1 zero, 2 poli). Le keyword
    ``zeros_hz``/``poles_hz`` permettono 1..4 zeri e 1..5 poli.
    """
    zeros = tuple(zeros_hz) if zeros_hz is not None else (zero_hz,)
    poles = (tuple(poles_hz) if poles_hz is not None
             else (pole_hz, high_pole_hz))
    if not zeros or not poles or any(v is None or v <= 0 for v in zeros + poles):
        raise ValueError("CTLE richiede frequenze positive per zeri e poli")
    s = 1j * np.asarray(f_hz)
    g_dc = 10 ** (dc_gain_db / 20)
    H = np.full(np.shape(s), g_dc, dtype=complex)
    for fz in zeros:
        H *= 1 + s / fz
    for fp in poles:
        H /= 1 + s / fp
    return H


def ctle_peaking_db(zero_hz=None, pole_hz=None, high_pole_hz=None,
                    dc_gain_db=0.0, f_max_hz=80e9, *, zeros_hz=None,
                    poles_hz=None):
    """Peaking = max|H| − |H(DC)| in dB (indicatore del boost alle alte)."""
    f = np.linspace(1e6, f_max_hz, 4001)
    H = ctle_response(f, zero_hz, pole_hz, high_pole_hz, dc_gain_db,
                      zeros_hz=zeros_hz, poles_hz=poles_hz)
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


def run_receiver_copper(cfg, v_in, rng) -> ReceiverResult:
    """AFE per link elettrico (KR/CR/C2M): niente PD/TIA in corrente.

    Il rumore dell'amplificatore è modellato come densità di tensione
    input-referred equivalente vₙ = iₙ·Z_T (dichiarato): stessa manopola
    tia_noise, stesso ordine di grandezza di un AFE reale."""
    n = len(v_in)
    vn_v_rthz = cfg.tia_noise_a_rt_hz * cfg.tia_transimpedance_ohm
    S_v2_hz = vn_v_rthz ** 2
    noise_v = white_noise_from_one_sided_psd(S_v2_hz, n, cfg.fs_analog_hz, rng)

    f_enbw_hz = np.linspace(0, cfg.fs_analog_hz / 2, 80_001)
    H_pos = butterworth_magnitude(f_enbw_hz, cfg.tia_bw_hz, order=3)
    enbw_hz = enbw_one_sided_hz(H_pos, f_enbw_hz)

    v_filtered, _, _ = apply_frequency_response(
        v_in + noise_v, cfg.fs_analog_hz,
        lambda f: butterworth_response(f, cfg.tia_bw_hz, order=3,
                                       causal=cfg.causal_filters))
    v_afe = np.clip(v_filtered, -cfg.tia_clip_v, cfg.tia_clip_v)
    clip_fraction = float(np.mean(np.abs(v_filtered) > cfg.tia_clip_v))
    v_ac = v_afe - np.mean(v_afe)
    agc_gain = float(cfg.agc_target_rms_v / max(rms_ac(v_ac), 1e-30))
    v_agc_v = agc_gain * v_ac

    dc_gain_db = getattr(cfg, "ctle_dc_gain_db", 0.0)
    v_ctle_v, H_ctle, f_fft_hz = apply_frequency_response(
        v_agc_v, cfg.fs_analog_hz,
        lambda f: ctle_response(
            f, dc_gain_db=dc_gain_db,
            zeros_hz=cfg.ctle_zeros_effective_hz,
            poles_hz=cfg.ctle_poles_effective_hz))
    f_noise_hz = np.linspace(0, cfg.fs_analog_hz / 2, 100_001)
    Hct = ctle_response(f_noise_hz, dc_gain_db=dc_gain_db,
                        zeros_hz=cfg.ctle_zeros_effective_hz,
                        poles_hz=cfg.ctle_poles_effective_hz)
    noise_enh_db = float(db10(np.trapz(np.abs(Hct) ** 2, f_noise_hz)
                              / (f_noise_hz[-1] - f_noise_hz[0])))
    zeros = np.zeros(n)
    return ReceiverResult(
        i_pd_signal_a=zeros, pd_sat_fraction=0.0,
        S_shot_a2_hz=0.0, S_tia_a2_hz=S_v2_hz, S_rin_a2_hz=0.0,
        tia_enbw_hz=enbw_hz,
        noise_rms_after_tia_a={"AFE (V, equivalente)": float(
            np.sqrt(S_v2_hz * enbw_hz))},
        i_pd_noisy_a=zeros,
        v_tia_v=v_afe, tia_clip_fraction=clip_fraction,
        agc_gain=agc_gain, v_agc_v=v_agc_v, v_ctle_v=v_ctle_v,
        H_ctle=H_ctle, f_fft_hz=f_fft_hz,
        ctle_noise_enhancement_db=noise_enh_db,
    )


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
    # Transimpedenza VARIABILE come nelle ROSA reali: se l'uscita nominale
    # supererebbe ~70% delle rail (link corto/alta potenza), il VGA del TIA
    # riduce Z_T invece di lasciar clippare l'ampiezza — senza questo, un
    # profilo DR/FR con potenza da clause schiaccia il livello PAM4 alto
    # (visto sul banco: q dell'occhio superiore 0.2 con Z_T fissa).
    # Il range del VGA è limitato (~10 dB di attenuazione, come nei chip
    # veri): oltre, l'overload clippa davvero contro le rail.
    zt_ohm = float(cfg.tia_transimpedance_ohm)
    v_pk_nominal = float(np.percentile(np.abs(zt_ohm * i_pd_noisy_a), 99.5))
    if v_pk_nominal > 0.7 * cfg.tia_clip_v:
        atten = 0.7 * cfg.tia_clip_v / v_pk_nominal
        zt_ohm *= max(atten, 10 ** (-10 / 20))
    v_tia_unfiltered_v = zt_ohm * i_pd_noisy_a
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
        lambda f: ctle_response(
            f, dc_gain_db=dc_gain_db,
            zeros_hz=cfg.ctle_zeros_effective_hz,
            poles_hz=cfg.ctle_poles_effective_hz))

    f_noise_hz = np.linspace(0, cfg.fs_analog_hz / 2, 100_001)
    Hct_pos = ctle_response(f_noise_hz, dc_gain_db=dc_gain_db,
                            zeros_hz=cfg.ctle_zeros_effective_hz,
                            poles_hz=cfg.ctle_poles_effective_hz)
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
