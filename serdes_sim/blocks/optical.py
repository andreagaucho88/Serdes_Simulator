"""Catena ottica: laser CW, MZM push-pull con chirp, fibra (loss + CD sul campo),
fading IM/DD small-signal come controllo fisico."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..utils import (C0_M_S, apply_frequency_response, butterworth_response,
                     dbm_to_w, w_to_dbm)


@dataclass
class OpticalResult:
    modulator: str
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
    beta3_s3_m: float
    pmd_dgd_ps: float
    modal_bw_hz: float
    nonlinear_phase_peak_rad: float
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
    if cfg.fiber_type == "mmf":
        if cfg.fiber_km <= 0:
            return np.ones_like(np.asarray(f_hz), dtype=float)
        modal_bw_hz = cfg.mmf_modal_bw_mhz_km / cfg.fiber_km * 1e6
        return np.abs(butterworth_response(np.asarray(f_hz), modal_bw_hz,
                                           order=3, causal=False))
    lambda_m = cfg.wavelength_nm * 1e-9
    D_s_m2 = cfg.dispersion_ps_nm_km * 1e-6
    beta2 = -(lambda_m ** 2 / (2 * np.pi * C0_M_S)) * D_s_m2
    theta = 0.5 * beta2 * cfg.fiber_km * 1e3 * (2 * np.pi * np.asarray(f_hz)) ** 2
    a = cfg.chirp_alpha if alpha is None else alpha
    return np.cos(theta) - a * np.sin(theta)


def run_optical(cfg, electrical_waveform_v, rng=None) -> OpticalResult:
    laser_power_w = float(dbm_to_w(cfg.laser_dbm))
    laser_field = np.sqrt(laser_power_w) * np.ones(len(electrical_waveform_v), dtype=complex)
    if cfg.laser_linewidth_mhz > 0 and rng is not None:
        # Lorentzian linewidth: Wiener phase, var(Delta phi)=2*pi*DeltaNu*dt.
        sigma = np.sqrt(2 * np.pi * cfg.laser_linewidth_mhz * 1e6
                        / cfg.fs_analog_hz)
        laser_phase = np.cumsum(rng.normal(0.0, sigma, len(laser_field)))
        laser_field *= np.exp(1j * laser_phase)

    # Due architetture distinte. MZM mantiene esattamente la baseline; EML e
    # un modello large-signal dichiarato (ER finito + chirp alpha-Henry), non
    # una curva MZM rinominata.
    mod_bw = (cfg.mzm_bw_hz if cfg.optical_modulator == "mzm" else
              cfg.eml_bw_hz if cfg.optical_modulator == "eml" else
              cfg.direct_laser_bw_hz)
    mzm_drive_v, _, _ = apply_frequency_response(
        electrical_waveform_v, cfg.fs_analog_hz,
        lambda f: butterworth_response(f, mod_bw, order=3,
                                       causal=cfg.causal_filters))
    if cfg.optical_modulator == "mzm":
        delta_phi_rad = cfg.mzm_bias_rad + np.pi * mzm_drive_v / cfg.vpi_v
        field_loss = 10 ** (-cfg.mzm_il_db / 20)
        E_mzm = (laser_field * field_loss * np.cos(delta_phi_rad / 2)
                 * np.exp(1j * cfg.chirp_alpha * delta_phi_rad / 2))
        v_static, p_static = mzm_static_transfer(cfg)
        budget_label = "MZM output"
    else:
        scale = float(np.percentile(np.abs(mzm_drive_v), 99.5))
        u = np.clip(0.5 + 0.5 * mzm_drive_v / max(scale, 1e-12), 0.0, 1.0)
        is_eml = cfg.optical_modulator == "eml"
        er_db = cfg.eml_er_db if is_eml else cfg.direct_laser_er_db
        chirp = (cfg.eml_chirp_alpha if is_eml
                 else cfg.direct_laser_chirp_alpha)
        p_min = 10 ** (-er_db / 10)
        transmission = p_min + (1.0 - p_min) * u
        # EML include una insertion loss esterna; DML/VCSEL usano laser_dbm
        # come potenza ottica nominale disponibile, senza IL fittizia.
        power_loss = 10 ** (-cfg.eml_il_db / 10) if is_eml else 1.0
        p_eml = laser_power_w * power_loss * transmission
        # Proxy large-signal per chirp transiente dell'EML. Il log evita che
        # la fase venga falsamente descritta con la transfer coseno del MZM.
        delta_phi_rad = 0.5 * chirp * np.log(
            np.maximum(p_eml, 1e-18) / max(float(np.mean(p_eml)), 1e-18))
        E_mzm = np.sqrt(np.maximum(p_eml, 0.0)) * np.exp(1j * delta_phi_rad)
        v_static = np.linspace(-1.0, 1.0, 1200)
        us = np.clip(0.5 + 0.5 * v_static, 0.0, 1.0)
        p_static = p_min + (1.0 - p_min) * us
        budget_label = f"{cfg.optical_modulator.upper()} output"
    P_mzm_w = np.abs(E_mzm) ** 2
    phase_mzm = np.unwrap(np.angle(E_mzm))
    inst_freq_shift_hz = np.gradient(phase_mzm, 1 / cfg.fs_analog_hz) / (2 * np.pi)

    # Fibra: coupling loss, CD sul campo, attenuazione
    lambda_m = cfg.wavelength_nm * 1e-9
    D_s_m2 = (cfg.dispersion_ps_nm_km * 1e-6
              if cfg.fiber_type == "smf" else 0.0)
    beta2_s2_m = -(lambda_m ** 2 / (2 * np.pi * C0_M_S)) * D_s_m2
    S_s_m3 = (cfg.dispersion_slope_ps_nm2_km * 1e3
              if cfg.fiber_type == "smf" else 0.0)
    beta3_s3_m = ((lambda_m ** 4 / (2 * np.pi * C0_M_S) ** 2)
                  * (S_s_m3 - 4 * np.pi * C0_M_S * beta2_s2_m
                     / lambda_m ** 3))
    fiber_length_m = cfg.fiber_km * 1e3

    E_launch = E_mzm * 10 ** (-cfg.coupling_il_db / 20)
    # Kerr SPM con effective length che include l'attenuazione. Ai power
    # level degli interconnect l'effetto e normalmente piccolo, ma ora e
    # esplicito e può essere stressato senza alterare il power budget.
    alpha_np_km = np.log(10) / 10 * cfg.fiber_loss_db_km
    leff_km = (cfg.fiber_km if alpha_np_km == 0 else
               (1 - np.exp(-alpha_np_km * cfg.fiber_km)) / alpha_np_km)
    nl_phase = cfg.fiber_gamma_w_inv_km * leff_km * np.abs(E_launch) ** 2
    E_launch = E_launch * np.exp(1j * nl_phase)
    fiber_field_loss = 10 ** (-(cfg.fiber_loss_db_km * cfg.fiber_km) / 20)
    E_fiber, _, _ = apply_frequency_response(
        E_launch, cfg.fs_analog_hz,
        lambda f: np.exp(-1j * fiber_length_m * (
            0.5 * beta2_s2_m * (2 * np.pi * f) ** 2
            + beta3_s3_m * (2 * np.pi * f) ** 3 / 6)),
        force_real=False)
    modal_bw_hz = float("inf")
    if cfg.fiber_type == "mmf" and cfg.fiber_km > 0:
        # Modal bandwidth-distance product, system-level. Per 100 m e
        # 4700 MHz·km produce 47 GHz. Non pretende di modellare DMD/launch.
        modal_bw_hz = cfg.mmf_modal_bw_mhz_km / cfg.fiber_km * 1e6
        E_fiber, _, _ = apply_frequency_response(
            E_fiber, cfg.fs_analog_hz,
            lambda f: butterworth_response(f, modal_bw_hz, order=3,
                                           causal=cfg.causal_filters),
            force_real=False)
    pmd_dgd_ps = (cfg.pmd_ps_sqrt_km * np.sqrt(max(cfg.fiber_km, 0.0))
                  if cfg.fiber_type == "smf" else 0.0)
    if pmd_dgd_ps > 0 and 0 < cfg.pmd_power_split < 1:
        dgd_s = pmd_dgd_ps * 1e-12
        e_fast, _, _ = apply_frequency_response(
            E_fiber, cfg.fs_analog_hz,
            lambda f: np.exp(+1j * np.pi * f * dgd_s), force_real=False)
        e_slow, _, _ = apply_frequency_response(
            E_fiber, cfg.fs_analog_hz,
            lambda f: np.exp(-1j * np.pi * f * dgd_s), force_real=False)
        p_pmd = (cfg.pmd_power_split * np.abs(e_fast) ** 2
                 + (1 - cfg.pmd_power_split) * np.abs(e_slow) ** 2)
        E_fiber = np.sqrt(np.maximum(p_pmd, 0.0)) * np.exp(1j * np.angle(E_fiber))
    E_fiber = E_fiber * fiber_field_loss
    P_fiber_w = np.abs(E_fiber) ** 2

    if (cfg.fiber_type == "smf" and cfg.fiber_km > 0
            and cfg.dispersion_ps_nm_km != 0):
        f_null_hz = float(np.sqrt(C0_M_S / (2 * abs(D_s_m2) * lambda_m ** 2 * fiber_length_m)))
    else:
        f_null_hz = float("inf")

    power_budget_dbm = {
        "laser": cfg.laser_dbm,
        budget_label: float(w_to_dbm(np.mean(P_mzm_w))),
        # chiave generica per il nuovo workbench; l'alias MZM conserva la
        # compatibilita dei pannelli Streamlit legacy.
        "modulator output": float(w_to_dbm(np.mean(P_mzm_w))),
        "MZM output": float(w_to_dbm(np.mean(P_mzm_w))),
        "fiber launch": float(w_to_dbm(np.mean(np.abs(E_launch) ** 2))),
        "PD input": float(w_to_dbm(np.mean(P_fiber_w))),
    }

    return OpticalResult(
        modulator=cfg.optical_modulator,
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
        beta3_s3_m=beta3_s3_m,
        pmd_dgd_ps=float(pmd_dgd_ps),
        modal_bw_hz=float(modal_bw_hz),
        nonlinear_phase_peak_rad=float(np.max(np.abs(nl_phase))),
        f_null_hz=f_null_hz,
        power_budget_dbm=power_budget_dbm,
        v_static=v_static,
        p_static=p_static,
    )
