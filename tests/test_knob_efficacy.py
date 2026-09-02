"""Audit permanente delle manopole: OGNI campo di LinkConfig, perturbato in
modo che 'morda' nel regime default, deve produrre un effetto osservabile —
e deve produrlo negli STADI GIUSTI (località: una manopola del canale non può
toccare il driver a monte).

Se un campo nuovo viene aggiunto a LinkConfig senza una voce qui, il test
fallisce: niente manopole fantasma.
"""

import sys
from dataclasses import fields
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from serdes_sim import LinkConfig, simulate
from serdes_sim.blocks.channel import DEMO_S2P

# (perturbazione, extra prerequisiti, stadi che DEVONO cambiare,
#  stadi che NON devono cambiare)
# stadi osservati: driver, pfib (potenza al PD), vtia, vctle, adc, ber
KNOBS = {
    "symbol_rate_hz": (60e9, {}, {"driver"}, set()),
    "analog_sps": (8, {}, {"driver"}, set()),
    "n_symbols": (6000, {}, {"driver"}, set()),
    "prbs_order": (15, {}, {"driver"}, set()),
    "custom_pattern_hex": ("0123456789ABCDEF", {"pattern": "custom_hex"},
                           {"driver"}, set()),
    "modulation": ("NRZ", {}, {"driver"}, set()),
    "pam4_mapping": ("binary", {}, {"driver"}, set()),
    "fec_mode": ("kp4", {}, {"driver"}, set()),
    "fec_interleave": (2, {"fec_mode": "kp4", "n_symbols": 20000,
                           "err_insert_bits": 200, "err_insert_burst": True},
                       {"ber"}, set()),
    "tx_rj_rms_fs": (500.0, {}, {"driver"}, set()),
    "tx_pj_amp_ui": (0.1, {}, {"driver"}, set()),
    "tx_pj_freq_mhz": (1200.0, {"tx_pj_amp_ui": 0.08}, {"driver"}, set()),
    "tx_dcd_pct": (10.0, {}, {"driver"}, set()),
    "tx_buj_amp_ui": (0.12, {}, {"driver"}, set()),
    "tx_ssc_ppm": (4000.0, {}, {"driver"}, set()),
    "tx_ssc_khz": (30.0, {"tx_ssc_ppm": 4000.0}, {"driver"}, set()),
    "tx_ffe_taps": ((-0.15, 1.0, -0.02), {}, {"driver"}, set()),
    "dac_bits": (5, {}, {"driver"}, set()),
    "dac_full_scale_vpp": (1.8, {}, {"driver"}, set()),
    "dac_bw_hz": (22e9, {}, {"driver"}, set()),
    "driver_gain_v_per_unit": (0.9, {}, {"driver"}, set()),
    "driver_bw_hz": (22e9, {}, {"driver"}, set()),
    "driver_clip_v": (0.45, {}, {"driver"}, set()),
    # canale: tocca dal canale in giù, NON il driver a monte
    "channel_il_nyquist_db": (18.0, {}, {"pfib"}, {"driver"}),
    "channel_delay_ps": (40.0, {}, {"pfib"}, {"driver"}),
    "group_delay_ripple_ps": (3.0, {}, {"pfib"}, {"driver"}),
    "return_loss_db": (8.0, {}, {"pfib"}, {"driver"}),
    "echo_delay_ui": (2.5, {}, {"pfib"}, {"driver"}),
    # Il baseline deve essere a sua volta un canale misurato valido: in questo
    # modo isoliamo il CONTENUTO Touchstone dall'interruttore use_s2p_channel.
    "s2p_text": (DEMO_S2P,
                 {"use_s2p_channel": True,
                  "s2p_text": DEMO_S2P.replace("-19.5 -86", "-29.5 -86")},
                 {"pfib"}, {"driver"}),
    # PPG / BERT / L2
    "pattern": ("clock2", {}, {"driver"}, set()),
    "l2_frame_bytes": (128, {"pattern": "eth"}, {"driver"}, set()),
    "err_insert_bits": (20, {}, {"driver", "ber"}, set()),
    "err_insert_burst": (True, {"err_insert_bits": 30}, {"driver"}, set()),
    "err_insert_target": ("msb", {"err_insert_bits": 30}, {"driver"}, set()),
    "tx_output_on": (False, {}, {"driver"}, set()),
    "l2_ipg_bytes": (96, {"pattern": "eth"}, {"driver"}, set()),
    "l2_streams": (3, {"pattern": "eth"}, {"driver"}, set()),
    # L2 scheduler / workload / impairment emulator / L1 PCS: cambiano i
    # bit di linea (frame diversi o codifica diversa) → driver
    "l2_scheduler": ("imix", {"pattern": "eth", "l2_streams": 2}, {"driver"}, set()),
    "l2_stream_weights": ((1, 4, 1, 1), {"pattern": "eth", "l2_streams": 2,
                                        "l2_scheduler": "weighted"},
                          {"driver"}, set()),
    "l2_workload": ("ai_training", {"pattern": "eth"}, {"driver"}, set()),
    "l2_drop_pct": (20.0, {"pattern": "eth"}, {"driver"}, set()),
    "l2_dup_pct": (20.0, {"pattern": "eth"}, {"driver"}, set()),
    "l2_misorder_pct": (20.0, {"pattern": "eth"}, {"driver"}, set()),
    "l2_corrupt_pct": (20.0, {"pattern": "eth"}, {"driver"}, set()),
    "l2_pcs_coding": ("64b66b", {"pattern": "eth"}, {"driver"}, set()),
    # coppia differenziale P/N (post-driver: NON tocca il driver ideale)
    "pn_skew_ps": (4.0, {}, {"pfib"}, {"driver"}),
    # il mismatch da solo non tocca il differenziale (fisica: genera solo CM);
    # l'effetto DM appare con un common-mode presente → prerequisito
    "pn_gain_mismatch_pct": (10.0, {"vcm_offset_v": 0.15}, {"pfib"}, set()),
    "vcm_offset_v": (0.2, {"pn_gain_mismatch_pct": 10.0}, {"pfib"}, set()),
    "vcm_noise_mv": (50.0, {"pn_gain_mismatch_pct": 10.0}, {"pfib"}, set()),
    "tx_diff_noise_mv": (50.0, {}, {"pfib"}, {"driver"}),
    "electrical_drive_mode": ("single_ended_p", {}, {"pfib"}, {"driver"}),
    # crosstalk e mezzo
    "xtalk_next_db": (-25.0, {}, {"pfib"}, {"driver"}),
    "xtalk_fext_db": (-25.0, {}, {"pfib"}, {"driver"}),
    "link_medium": ("copper", {}, {"vctle"}, {"driver"}),
    # ottica
    # Questi due campi formano un solo controllo atomico nella UI. Cambiarne
    # uno soltanto produrrebbe intenzionalmente una configurazione invalida;
    # il comportamento accoppiato è verificato nel test dedicato sotto.
    "optical_modulator": None,
    "laser_type": None,
    "laser_dbm": (5.0, {}, {"pfib"}, {"driver"}),
    "laser_linewidth_mhz": (300.0, {"fiber_km": 10.0}, {"pfib"}, {"driver"}),
    "optical_drive_vpp_v": (1.2, {"optical_modulator": "eml",
                                       "laser_type": "dfb_eml_integrated"},
                                  {"pfib"}, {"driver"}),
    "vpi_v": (2.5, {}, {"pfib"}, {"driver"}),
    "mzm_bias_rad": (1.9, {}, {"pfib"}, {"driver"}),
    "mzm_bw_hz": (25e9, {}, {"pfib"}, {"driver"}),
    "mzm_il_db": (6.5, {}, {"pfib"}, {"driver"}),
    "chirp_alpha": (-0.8, {}, {"pfib"}, {"driver"}),
    "eml_bw_hz": (25e9, {"optical_modulator": "eml", "laser_type": "dfb_eml_integrated"}, {"pfib"}, {"driver"}),
    "eml_er_db": (3.0, {"optical_modulator": "eml", "laser_type": "dfb_eml_integrated"}, {"pfib"}, {"driver"}),
    "eml_il_db": (7.0, {"optical_modulator": "eml", "laser_type": "dfb_eml_integrated"}, {"pfib"}, {"driver"}),
    "eml_chirp_alpha": (5.0, {"optical_modulator": "eml", "laser_type": "dfb_eml_integrated", "fiber_km": 8.0}, {"pfib"}, {"driver"}),
    "direct_laser_bw_hz": (18e9, {"optical_modulator": "dml", "laser_type": "dfb_direct"}, {"pfib"}, {"driver"}),
    "direct_laser_er_db": (2.0, {"optical_modulator": "dml", "laser_type": "dfb_direct"}, {"pfib"}, {"driver"}),
    "direct_laser_chirp_alpha": (7.0, {"optical_modulator": "dml", "laser_type": "dfb_direct", "fiber_km": 8.0}, {"pfib"}, {"driver"}),
    "coupling_il_db": (4.0, {}, {"pfib"}, {"driver"}),
    # riflessione ottica (MPI): agisce dal lancio in fibra in giù
    "optical_return_loss_db": (20.0, {}, {"pfib"}, {"driver"}),
    "optical_reflection_delay_ns": (1.0, {"optical_return_loss_db": 20.0},
                                    {"pfib"}, {"driver"}),
    "wavelength_nm": (1310.0, {}, {"pfib"}, {"driver"}),
    "fiber_km": (5.0, {}, {"pfib"}, {"driver"}),
    "dispersion_ps_nm_km": (-10.0, {}, {"pfib"}, {"driver"}),
    "dispersion_slope_ps_nm2_km": (0.5, {"fiber_km": 10.0}, {"pfib"}, {"driver"}),
    "pmd_ps_sqrt_km": (2.0, {"fiber_km": 10.0}, {"pfib"}, {"driver"}),
    "pmd_power_split": (0.2, {"pmd_ps_sqrt_km": 2.0, "fiber_km": 10.0}, {"pfib"}, {"driver"}),
    "fiber_gamma_w_inv_km": (100.0, {"laser_dbm": 12.0, "fiber_km": 10.0}, {"pfib"}, {"driver"}),
    "fiber_loss_db_km": (0.4, {}, {"pfib"}, {"driver"}),
    "fiber_type": ("mmf", {}, {"pfib"}, {"driver"}),
    "mmf_modal_bw_mhz_km": (1200.0, {"fiber_type": "mmf"}, {"pfib"}, {"driver"}),
    # RX: tocca dal CTLE in giù, NON l'ottica a monte
    "pd_responsivity_a_w": (0.5, {}, {"vctle"}, {"driver", "pfib"}),
    "pd_dark_current_a": (5e-5, {}, {"vctle"}, {"driver", "pfib"}),
    "pd_bw_hz": (25e9, {}, {"vctle"}, {"driver", "pfib"}),
    "pd_saturation_a": (5e-5, {}, {"vctle"}, {"driver", "pfib"}),
    "rin_db_hz": (-130.0, {}, {"vctle"}, {"driver", "pfib"}),
    "rin_at_source": (True, {"rin_db_hz": -128.0}, {"pfib"}, {"driver"}),
    "tia_noise_a_rt_hz": (60e-12, {}, {"vctle"}, {"driver", "pfib"}),
    # oltre il range del VGA (~10 dB): overload reale contro le rail
    "tia_transimpedance_ohm": (20000.0, {}, {"vctle"}, {"driver", "pfib"}),
    "tia_vga_range_db": (0.0, {"laser_dbm": 9.0}, {"vctle"}, {"driver", "pfib"}),
    # L'AGC ideale puo normalizzare la variazione a valle: il piano corretto
    # da osservare per il target del VGA TIA e l'uscita TIA stessa.
    "tia_headroom_ratio": (0.35, {}, {"vtia"}, {"driver", "pfib"}),
    "tia_bw_hz": (22e9, {}, {"vctle"}, {"driver", "pfib"}),
    "tia_clip_v": (0.05, {}, {"vctle"}, {"driver", "pfib"}),
    # PVT del ricevitore: agisce da TIA/CTLE in giù, mai sul TX
    "pvt_process": ("ss", {}, {"vctle"}, {"driver", "pfib"}),
    "pvt_temp_c": (125.0, {}, {"vctle"}, {"driver", "pfib"}),
    "pvt_vdd_pct": (-10.0, {}, {"vctle"}, {"driver", "pfib"}),
    "agc_target_rms_v": (0.35, {}, {"vctle"}, {"driver", "pfib"}),
    "agc_min_gain_db": (0.0, {"agc_target_rms_v": 0.05}, {"vctle"}, {"driver", "pfib"}),
    "agc_max_gain_db": (0.0, {"laser_dbm": -3.0,
                               "agc_target_rms_v": 0.4},
                              {"vctle"}, {"driver", "pfib"}),
    "ctle_zero_hz": (5e9, {}, {"vctle"}, {"driver", "pfib"}),
    "ctle_pole_hz": (20e9, {}, {"vctle"}, {"driver", "pfib"}),
    "ctle_hf_pole_hz": (70e9, {}, {"vctle"}, {"driver", "pfib"}),
    "ctle_dc_gain_db": (-6.0, {}, {"vctle"}, {"driver", "pfib"}),
    "ctle_zeros_hz": ((6e9, 16e9), {}, {"vctle"}, {"driver", "pfib"}),
    "ctle_poles_hz": ((24e9, 45e9, 75e9), {}, {"vctle"}, {"driver", "pfib"}),
    # ADC: tocca solo adc/ber
    "adc_sps": (4, {}, {"adc"}, {"driver", "pfib", "vctle"}),
    "adc_bits": (5, {}, {"adc"}, {"driver", "pfib", "vctle"}),
    "adc_full_scale_vpp": (0.9, {}, {"adc"}, {"driver", "pfib", "vctle"}),
    "adc_phase_ui": (0.3, {}, {"adc"}, {"driver", "pfib", "vctle"}),
    "adc_jitter_rms_fs": (300.0, {}, {"adc"}, {"driver", "pfib", "vctle"}),
    "adc_interleaves": (8, {}, {"adc"}, {"driver", "pfib", "vctle"}),
    "adc_gain_mismatch_rms": (0.02, {}, {"adc"}, {"driver", "pfib", "vctle"}),
    "adc_offset_mismatch_rms_v": (5e-3, {}, {"adc"}, {"driver", "pfib", "vctle"}),
    "adc_skew_mismatch_rms_fs": (150.0, {}, {"adc"}, {"driver", "pfib", "vctle"}),
    # architettura SOTA: rank T/H, banda front-end, calibrazione, rumore
    "adc_ranks": (4, {"adc_skew_mismatch_rms_fs": 150.0},
                  {"adc"}, {"driver", "pfib", "vctle"}),
    "adc_frontend_bw_hz": (28e9, {}, {"adc"}, {"driver", "pfib", "vctle"}),
    "adc_bw_mismatch_pct": (10.0, {"adc_frontend_bw_hz": 35e9, "adc_ranks": 4},
                            {"adc"}, {"driver", "pfib", "vctle"}),
    "adc_cal_mode": ("off", {}, {"adc"}, {"driver", "pfib", "vctle"}),
    "adc_noise_rms_mv": (3.0, {}, {"adc"}, {"driver", "pfib", "vctle"}),
    "rx_ppm_offset": (150.0, {}, {"adc"}, {"driver", "pfib", "vctle"}),
    # DSP: tocca solo la BER
    "cdr_mode": ("oracle", {}, {"ber"}, {"driver", "pfib", "vctle", "adc"}),
    "cdr_bw": (0.003, {}, {"ber"}, {"driver", "pfib", "vctle", "adc"}),
    "cdr_damping": (0.6, {}, {"ber"}, {"driver", "pfib", "vctle", "adc"}),
    "fse_taps": (9, {}, {"ber"}, {"driver", "pfib", "vctle", "adc"}),
    "dfe_taps": (2, {}, {"ber"}, {"driver", "pfib", "vctle", "adc"}),
    "training_start": (2500, {}, {"ber"}, {"driver", "pfib", "vctle", "adc"}),
    "training_stop": (2000, {}, {"ber"}, {"driver", "pfib", "vctle", "adc"}),
    "causal_filters": (True, {}, {"driver"}, set()),
    # metadato puro, dichiarato senza effetto fisico
    "s2p_name": None,
    "use_s2p_channel": None,   # testato insieme a s2p_text
    "s4p_pairs": None,         # condizionale: testato in test_s4p_mixed_mode
}


def _observe(r):
    return {
        "driver": r.tx.driver_voltage_v,
        "pfib": (r.optical.P_fiber_w if r.optical is not None
                 else np.zeros(1)),
        "vtia": r.receiver.v_tia_v,
        "vctle": r.receiver.v_ctle_v,
        "adc": r.adc.adc_samples_v,
        "ber": (r.ber_post_dfe if r.link_up else None),
    }


def _changed(a, b):
    out = set()
    for k in a:
        va, vb = a[k], b[k]
        if k == "ber":
            if va != vb:
                out.add(k)
        elif len(va) != len(vb) or not np.allclose(va, vb):
            out.add(k)
    return out


def test_every_config_field_has_a_knob_spec():
    missing = [f.name for f in fields(LinkConfig) if f.name not in KNOBS]
    assert missing == [], f"campi senza voce nell'audit manopole: {missing}"


def test_optical_architecture_control_is_atomic_and_effective():
    """Il selettore UI cambia insieme modulatore e sorgente compatibile."""
    base = _observe(simulate(LinkConfig(), seed=731, depth="light"))
    eml = _observe(simulate(LinkConfig(optical_modulator="eml",
                                       laser_type="dfb_eml_integrated"),
                            seed=731, depth="light"))
    changed = _changed(base, eml)
    assert "pfib" in changed
    assert "driver" not in changed


@pytest.mark.parametrize("arch,laser,extra", [
    ("eml", "dfb_eml_integrated", {}),
    ("dml", "dfb_direct", {}),
    ("vcsel", "vcsel_direct", {"fiber_type": "mmf",
                                "wavelength_nm": 850.0,
                                "dispersion_ps_nm_km": 0.0,
                                "pmd_ps_sqrt_km": 0.0}),
])
def test_driver_swing_propagates_into_non_mzm_optical_oma(arch, laser, extra):
    """La transfer EML/direct non puo rinormalizzare via il record: a
    sensibilita fissa, abbassare il gain del driver deve ridurre l'OMA."""
    common = dict(optical_modulator=arch, laser_type=laser, fiber_km=0.5,
                  **extra)
    low = simulate(LinkConfig(driver_gain_v_per_unit=0.25, **common),
                   seed=732, depth="light")
    nominal = simulate(LinkConfig(driver_gain_v_per_unit=0.65, **common),
                       seed=732, depth="light")
    oma_low = float(np.ptp(low.optical.P_mzm_w))
    oma_nominal = float(np.ptp(nominal.optical.P_mzm_w))
    assert oma_nominal > oma_low * 1.05, (arch, oma_low, oma_nominal)


@pytest.mark.parametrize("arch,laser,extra", [
    ("eml", "dfb_eml_integrated", {}),
    ("dml", "dfb_direct", {}),
    ("vcsel", "vcsel_direct", {"fiber_type": "mmf",
                                "wavelength_nm": 850.0,
                                "dispersion_ps_nm_km": 0.0,
                                "pmd_ps_sqrt_km": 0.0}),
])
def test_linewidth_reaches_fiber_for_every_laser_architecture(arch, laser, extra):
    """La fase Wiener attraversa anche EML/DML/VCSEL: a 0 km il PD non la
    vede, dopo propagazione dispersiva o modale viene convertita in AM."""
    common = dict(optical_modulator=arch, laser_type=laser, **extra)
    b2b0 = simulate(LinkConfig(fiber_km=0.0, laser_linewidth_mhz=0.0,
                               **common), seed=733, depth="light")
    b2b = simulate(LinkConfig(fiber_km=0.0, laser_linewidth_mhz=300.0,
                              **common), seed=733, depth="light")
    assert np.allclose(b2b.optical.P_fiber_w, b2b0.optical.P_fiber_w,
                       rtol=1e-10, atol=1e-15)
    far0 = simulate(LinkConfig(fiber_km=5.0, laser_linewidth_mhz=0.0,
                               **common), seed=733, depth="light")
    far = simulate(LinkConfig(fiber_km=5.0, laser_linewidth_mhz=300.0,
                              **common), seed=733, depth="light")
    assert not np.allclose(far.optical.P_fiber_w, far0.optical.P_fiber_w,
                           rtol=1e-5, atol=1e-12), arch


@pytest.mark.parametrize("field", [k for k, v in KNOBS.items() if v is not None])
def test_knob_has_effect_in_the_right_places(field):
    """Isola davvero la manopola sotto test.

    I prerequisiti ``extra`` (per esempio EML attivo mentre si cambia la sua
    banda) devono essere presenti in ENTRAMBE le simulazioni.  Confrontarli
    col default, come faceva la prima versione dell'audit, produceva falsi
    positivi: bastava che fosse il prerequisito a cambiare il segnale anche
    se la manopola fosse completamente scollegata dal datapath.
    """
    value, extra, must_change, must_not_change = KNOBS[field]
    baseline = _observe(simulate(LinkConfig(**extra), seed=731,
                                 depth="light"))
    exercised = dict(extra)
    exercised[field] = value
    obs = _observe(simulate(LinkConfig(**exercised), seed=731,
                            depth="light"))
    changed = _changed(baseline, obs)
    assert changed, f"manopola MORTA: {field}={value} non cambia nulla"
    missing = must_change - changed
    assert not missing, (f"{field}: atteso effetto su {missing}, "
                         f"cambiati solo {changed}")
    # Località: i prerequisiti sono identici nei due lati del confronto, quindi
    # ora possiamo (e dobbiamo) controllare gli effetti a monte anche per i
    # parametri condizionali.
    leaked = must_not_change & changed
    assert not leaked, (f"{field}: effetto illegittimo a monte su {leaked}")
