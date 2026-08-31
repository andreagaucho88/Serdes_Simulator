"""Catena ottica: laser CW, MZM push-pull con chirp, fibra (loss + CD sul campo),
fading IM/DD small-signal come controllo fisico."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..utils import (C0_M_S, apply_frequency_response, butterworth_response,
                     dbm_to_w, w_to_dbm)


@dataclass
class OpticalResult:
    laser_power_w: float
    mzm_drive_v: np.ndarray          # dopo la banda del MZM
    delta_phi_rad: np.ndarray
    E_mzm: np.ndarray                # campo, |E|^2 = P [W]
    P_mzm_w: np.ndarray
    inst_freq_shift_hz: np.ndarray   # chirp istantaneo
    E_launch: np.ndarray
    E_fiber: np.ndarray
    P_fiber_w: np.ndarray
    beta2_s2_m: float
    f_null_hz: float                 # primo nullo IM/DD small-signal
    power_budget_dbm: dict           # piano -> dBm medio
    # transfer statica per il grafico
    v_static: np.ndarray
    p_static: np.ndarray


def mzm_static_transfer(cfg, n_points=1200):
    v = np.linspace(-cfg.vpi_v, cfg.vpi_v, n_points)
    p = np.cos((cfg.mzm_bias_rad + np.pi * v / cfg.vpi_v) / 2) ** 2
    return v, p


def imdd_small_signal_response(cfg, f_hz, alpha=None):
    """cos(theta) - alpha*sin(theta): mappa di tendenza, non il modello principale."""
    lambda_m = cfg.wavelength_nm * 1e-9
    D_s_m2 = cfg.dispersion_ps_nm_km * 1e-6
    beta2 = -(lambda_m ** 2 / (2 * np.pi * C0_M_S)) * D_s_m2
    theta = 0.5 * beta2 * cfg.fiber_km * 1e3 * (2 * np.pi * np.asarray(f_hz)) ** 2
    a = cfg.chirp_alpha if alpha is None else alpha
    return np.cos(theta) - a * np.sin(theta)


def run_optical(cfg, electrical_waveform_v) -> OpticalResult:
    laser_power_w = float(dbm_to_w(cfg.laser_dbm))
    laser_field = np.sqrt(laser_power_w) * np.ones(len(electrical_waveform_v), dtype=complex)

    # MZM: banda sul drive, poi transfer cos + chirp esponenziale
    mzm_drive_v, _, _ = apply_frequency_response(
        electrical_waveform_v, cfg.fs_analog_hz,
        lambda f: butterworth_response(f, cfg.mzm_bw_hz, order=3,
                                       causal=cfg.causal_filters))
    delta_phi_rad = cfg.mzm_bias_rad + np.pi * mzm_drive_v / cfg.vpi_v
    mzm_field_loss = 10 ** (-cfg.mzm_il_db / 20)
    E_mzm = (laser_field * mzm_field_loss * np.cos(delta_phi_rad / 2)
             * np.exp(1j * cfg.chirp_alpha * delta_phi_rad / 2))
    P_mzm_w = np.abs(E_mzm) ** 2
    phase_mzm = np.unwrap(np.angle(E_mzm))
    inst_freq_shift_hz = np.gradient(phase_mzm, 1 / cfg.fs_analog_hz) / (2 * np.pi)

    # Fibra: coupling loss, CD sul campo, attenuazione
    lambda_m = cfg.wavelength_nm * 1e-9
    D_s_m2 = cfg.dispersion_ps_nm_km * 1e-6
    beta2_s2_m = -(lambda_m ** 2 / (2 * np.pi * C0_M_S)) * D_s_m2
    fiber_length_m = cfg.fiber_km * 1e3

    E_launch = E_mzm * 10 ** (-cfg.coupling_il_db / 20)
    fiber_field_loss = 10 ** (-(cfg.fiber_loss_db_km * cfg.fiber_km) / 20)
    E_fiber, _, _ = apply_frequency_response(
        E_launch, cfg.fs_analog_hz,
        lambda f: np.exp(-0.5j * beta2_s2_m * fiber_length_m * (2 * np.pi * f) ** 2),
        force_real=False)
    E_fiber = E_fiber * fiber_field_loss
    P_fiber_w = np.abs(E_fiber) ** 2

    if cfg.fiber_km > 0 and cfg.dispersion_ps_nm_km != 0:
        f_null_hz = float(np.sqrt(C0_M_S / (2 * abs(D_s_m2) * lambda_m ** 2 * fiber_length_m)))
    else:
        f_null_hz = float("inf")

    power_budget_dbm = {
        "laser": cfg.laser_dbm,
        "MZM output": float(w_to_dbm(np.mean(P_mzm_w))),
        "fiber launch": float(w_to_dbm(np.mean(np.abs(E_launch) ** 2))),
        "PD input": float(w_to_dbm(np.mean(P_fiber_w))),
    }

    v_static, p_static = mzm_static_transfer(cfg)
    return OpticalResult(
        laser_power_w=laser_power_w,
        mzm_drive_v=mzm_drive_v,
        delta_phi_rad=delta_phi_rad,
        E_mzm=E_mzm,
        P_mzm_w=P_mzm_w,
        inst_freq_shift_hz=inst_freq_shift_hz,
        E_launch=E_launch,
        E_fiber=E_fiber,
        P_fiber_w=P_fiber_w,
        beta2_s2_m=beta2_s2_m,
        f_null_hz=f_null_hz,
        power_budget_dbm=power_budget_dbm,
        v_static=v_static,
        p_static=p_static,
    )
