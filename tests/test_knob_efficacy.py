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
# stadi osservati: driver, pfib (potenza al PD), vctle, adc, ber
KNOBS = {
    "symbol_rate_hz": (60e9, {}, {"driver"}, set()),
    "analog_sps": (8, {}, {"driver"}, set()),
    "n_symbols": (6000, {}, {"driver"}, set()),
    "prbs_order": (15, {}, {"driver"}, set()),
    "modulation": ("NRZ", {}, {"driver"}, set()),
    "pam4_mapping": ("binary", {}, {"driver"}, set()),
    "fec_mode": ("kp4", {}, {"driver"}, set()),
    "tx_rj_rms_fs": (500.0, {}, {"driver"}, set()),
    "tx_pj_amp_ui": (0.1, {}, {"driver"}, set()),
    "tx_pj_freq_mhz": (1200.0, {"tx_pj_amp_ui": 0.08}, {"driver"}, set()),
    "tx_dcd_pct": (10.0, {}, {"driver"}, set()),
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
    "s2p_text": (DEMO_S2P, {"use_s2p_channel": True}, {"pfib"}, {"driver"}),
    # PPG / BERT / L2
    "pattern": ("clock2", {}, {"driver"}, set()),
    "l2_frame_bytes": (128, {"pattern": "eth"}, {"driver"}, set()),
    "err_insert_bits": (20, {}, {"driver", "ber"}, set()),
    # coppia differenziale P/N (post-driver: NON tocca il driver ideale)
    "pn_skew_ps": (4.0, {}, {"pfib"}, {"driver"}),
    # il mismatch da solo non tocca il differenziale (fisica: genera solo CM);
    # l'effetto DM appare con un common-mode presente → prerequisito
    "pn_gain_mismatch_pct": (10.0, {"vcm_offset_v": 0.15}, {"pfib"}, set()),
    "vcm_offset_v": (0.2, {"pn_gain_mismatch_pct": 10.0}, {"pfib"}, set()),
    "vcm_noise_mv": (50.0, {"pn_gain_mismatch_pct": 10.0}, {"pfib"}, set()),
    # crosstalk e mezzo
    "xtalk_next_db": (-25.0, {}, {"pfib"}, {"driver"}),
    "xtalk_fext_db": (-25.0, {}, {"pfib"}, {"driver"}),
    "link_medium": ("copper", {}, {"vctle"}, {"driver"}),
    # ottica
    "laser_dbm": (5.0, {}, {"pfib"}, {"driver"}),
    "vpi_v": (2.5, {}, {"pfib"}, {"driver"}),
    "mzm_bias_rad": (1.9, {}, {"pfib"}, {"driver"}),
    "mzm_bw_hz": (25e9, {}, {"pfib"}, {"driver"}),
    "mzm_il_db": (6.5, {}, {"pfib"}, {"driver"}),
    "chirp_alpha": (-0.8, {}, {"pfib"}, {"driver"}),
    "coupling_il_db": (4.0, {}, {"pfib"}, {"driver"}),
    "wavelength_nm": (1310.0, {}, {"pfib"}, {"driver"}),
    "fiber_km": (5.0, {}, {"pfib"}, {"driver"}),
    "dispersion_ps_nm_km": (-10.0, {}, {"pfib"}, {"driver"}),
    "fiber_loss_db_km": (0.4, {}, {"pfib"}, {"driver"}),
    # RX: tocca dal CTLE in giù, NON l'ottica a monte
    "pd_responsivity_a_w": (0.5, {}, {"vctle"}, {"driver", "pfib"}),
    "pd_dark_current_a": (5e-5, {}, {"vctle"}, {"driver", "pfib"}),
    "pd_bw_hz": (25e9, {}, {"vctle"}, {"driver", "pfib"}),
    "pd_saturation_a": (5e-5, {}, {"vctle"}, {"driver", "pfib"}),
    "rin_db_hz": (-130.0, {}, {"vctle"}, {"driver", "pfib"}),
    "tia_noise_a_rt_hz": (60e-12, {}, {"vctle"}, {"driver", "pfib"}),
    "tia_transimpedance_ohm": (5000.0, {}, {"vctle"}, {"driver", "pfib"}),
    "tia_bw_hz": (22e9, {}, {"vctle"}, {"driver", "pfib"}),
    "tia_clip_v": (0.3, {}, {"vctle"}, {"driver", "pfib"}),
    "agc_target_rms_v": (0.35, {}, {"vctle"}, {"driver", "pfib"}),
    "ctle_zero_hz": (5e9, {}, {"vctle"}, {"driver", "pfib"}),
    "ctle_pole_hz": (20e9, {}, {"vctle"}, {"driver", "pfib"}),
    "ctle_hf_pole_hz": (70e9, {}, {"vctle"}, {"driver", "pfib"}),
    "ctle_dc_gain_db": (-6.0, {}, {"vctle"}, {"driver", "pfib"}),
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


@pytest.fixture(scope="module")
def base_obs():
    return _observe(simulate(LinkConfig(), depth="light"))


def test_every_config_field_has_a_knob_spec():
    missing = [f.name for f in fields(LinkConfig) if f.name not in KNOBS]
    assert missing == [], f"campi senza voce nell'audit manopole: {missing}"


@pytest.mark.parametrize("field", [k for k, v in KNOBS.items() if v is not None])
def test_knob_has_effect_in_the_right_places(field, base_obs):
    value, extra, must_change, must_not_change = KNOBS[field]
    r = simulate(LinkConfig(**{field: value, **extra}), depth="light")
    obs = _observe(r)
    changed = _changed(base_obs, obs)
    assert changed, f"manopola MORTA: {field}={value} non cambia nulla"
    missing = must_change - changed
    assert not missing, (f"{field}: atteso effetto su {missing}, "
                         f"cambiati solo {changed}")
    # località: mai effetti a MONTE del blocco (extra prerequisiti esclusi)
    if not extra:
        leaked = must_not_change & changed
        assert not leaked, (f"{field}: effetto illegittimo a monte su {leaked}")
