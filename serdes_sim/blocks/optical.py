"""Catena ottica: laser CW, MZM push-pull con chirp, fibra (loss + CD sul campo),
fading IM/DD small-signal come controllo fisico."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..utils import (C0_M_S, apply_frequency_response, butterworth_response,
                     white_noise_from_one_sided_psd,
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
    reflection_mpi_db: float = None  # potenza dell'eco MPI (−2·RL) o None
    laser_rin_rms_pct: float = None  # RIN alla sorgente: σ relativa [%] o None


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
        # Transfer calibrata su una sensibilita ELETTRICA fissa.  La vecchia
        # implementazione divideva per il percentile del record stesso:
        # qualunque cambio di gain/swing del driver veniva quindi cancellato
        # e non poteva propagarsi all'OMA.  ±Vpp/2 mappa ora realmente 0..1.
        u = np.clip(0.5 + mzm_drive_v / cfg.optical_drive_vpp_v, 0.0, 1.0)
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
        # Conserva anche la fase della sorgente: la linewidth era applicata
        # soltanto al ramo MZM e veniva silenziosamente persa per EML/DML/
        # VCSEL.  Il modulo unitario evita di duplicare laser_power_w.
        source_phase = laser_field / max(np.sqrt(laser_power_w), 1e-30)
        E_mzm = (np.sqrt(np.maximum(p_eml, 0.0)) * source_phase
                 * np.exp(1j * delta_phi_rad))
        # La curva statica e l'istogramma del pannello devono condividere lo
        # stesso asse FISICO in volt.  Con l'asse normalizzato precedente la
        # transfer e l'occupancy del drive venivano sovrapposte in domini
        # diversi e nascondevano proprio la sensibilita appena resa esplicita.
        v_static = np.linspace(-0.5 * cfg.optical_drive_vpp_v,
                               0.5 * cfg.optical_drive_vpp_v, 1200)
        us = np.clip(0.5 + v_static / cfg.optical_drive_vpp_v, 0.0, 1.0)
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

    # RIN alla sorgente (rin_at_source): rumore d'intensità moltiplicativo
    # sull'uscita del modulatore (laser CW × modulatore lineare ⇒ equivale
    # a metterlo sul laser), bianco sulla banda analogica.  La PSD è quella
    # della definizione di clausola RIN_xOMA (52.9.6 / 124.8.7): rumore al
    # livello ALTO riferito all'OMA, cioè σ²_high = 10^(RIN/10)·OMA²·BW; per
    # gli altri livelli il rumore scala con la potenza istantanea.  Entra nel
    # campo ottico (TDECQ/SECQ lo vedono) e arriva al PD via square-law; il
    # termine RIN del ricevitore viene azzerato per non contarlo due volte.
    # Con il flag spento resta il modello storico della baseline (corrente
    # di rumore bianca al PD riferita alla corrente media).
    laser_rin_rms_pct = None
    if cfg.rin_at_source and rng is not None:
        p_inst = np.abs(E_mzm) ** 2
        p_hi = float(np.percentile(p_inst, 99.0))
        p_lo = float(np.percentile(p_inst, 1.0))
        oma_over_hi = (p_hi - p_lo) / p_hi if p_hi > 0 else 0.0
        rel = white_noise_from_one_sided_psd(10 ** (cfg.rin_db_hz / 10),
                                             len(E_mzm), cfg.fs_analog_hz, rng) * oma_over_hi
        E_mzm = E_mzm * np.sqrt(np.clip(1.0 + rel, 1e-3, None))
        P_mzm_w = np.abs(E_mzm) ** 2
        laser_rin_rms_pct = float(100.0 * np.std(rel))
    E_launch = E_mzm * 10 ** (-cfg.coupling_il_db / 20)
    # Riflessione ottica: interferenza multipath (MPI) coerente da una COPPIA
    # di discontinuità con return loss RL ciascuna.  L'eco che rientra nel
    # verso di propagazione è riflesso due volte, quindi la sua potenza sta
    # 2·RL sotto il segnale (campo 10^(−RL/10)); ritardo
    # optical_reflection_delay_ns e fase casuale per record.  Nella procedura
    # DR4 è lo stress "reflection" alla tolleranza ORL del TX (21.4 dB per
    # discontinuità → eco a −42.8 dB).  DICHIARATO: eco singola coerente,
    # non un modello di cavità né di feedback nel laser (quello è coperto dal
    # RIN_21.4OMA, cioè dallo stress RIN alla sorgente).
    reflection_mpi_db = None
    if cfg.optical_return_loss_db > 0:
        r_field = 10 ** (-2.0 * cfg.optical_return_loss_db / 20)
        delay = int(round(cfg.optical_reflection_delay_ns * 1e-9 * cfg.fs_analog_hz))
        delay = max(1, min(delay, len(E_launch) - 1))
        phase = (rng.uniform(0, 2 * np.pi) if rng is not None else 0.0)
        echo = np.roll(E_launch, delay) * r_field * np.exp(1j * phase)
        E_launch = E_launch + echo
        reflection_mpi_db = float(-2.0 * cfg.optical_return_loss_db)
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
        reflection_mpi_db=reflection_mpi_db,
        laser_rin_rms_pct=laser_rin_rms_pct,
    )
