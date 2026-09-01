"""Audit di CASCATA fisica: ogni manopola deve muovere il segnale nella
direzione giusta fino allo slicer (iterazione 32, richiesta utente).

L'audit knob (test_knob_efficacy) verifica CHE una manopola abbia effetto e
DOVE; questo file verifica che l'effetto abbia il VERSO fisico giusto e —
dove la teoria dà un numero — la grandezza giusta. Tutte le catene sono
misurate sulla BER contata / q_min allo slicer: se una di queste asserzioni
si rompe, la fisica del banco è diventata bugiarda.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from serdes_sim import LinkConfig                              # noqa: E402
from serdes_sim.engine import simulate                         # noqa: E402
from serdes_sim.blocks import adc as adc_block                 # noqa: E402

pytestmark = pytest.mark.slow

CFG = LinkConfig()
SEED = 99


def q_of(cfg):
    r = simulate(cfg, seed=SEED, depth="light")
    return float(r.snr_dfe["q_min"]) if r.link_up else None


def ber_of(cfg):
    r = simulate(cfg, seed=SEED, depth="light")
    return float(r.ber_post_dfe) if r.link_up else 1.0


def pd_dbm_of(cfg):
    r = simulate(cfg, seed=SEED, depth="light")
    return float(r.optical.power_budget_dbm["PD input"])


def assert_monotone_q(field, values, **extra):
    qs = [q_of(CFG.with_updates(**{field: v}, **extra)) for v in values]
    for a, b, va, vb in zip(qs, qs[1:], values, values[1:]):
        assert b is None or (a is not None and b < a), (
            f"{field}: q non peggiora da {va} a {vb} ({a} → {b})")
    return qs


# ------------------------------------------------------------ sorgente/TX
def test_laser_power_cascade_and_budget_arithmetic():
    # meno potenza lanciata → meno potenza al PD (dB per dB) → meno q,
    # fino al link down: la catena ottica non ha guadagni fantasma
    assert_monotone_q("laser_dbm", [6.0, 2.0, -2.0])
    p6, p2 = pd_dbm_of(CFG.with_updates(laser_dbm=6.0)), \
        pd_dbm_of(CFG.with_updates(laser_dbm=2.0))
    assert p6 - p2 == pytest.approx(4.0, abs=0.05)   # budget dB-per-dB


def test_rin_cascade():
    assert_monotone_q("rin_db_hz", [-160.0, -145.0, -135.0])


def test_tx_clock_jitter_cascade():
    assert_monotone_q("tx_rj_rms_fs", [0.0, 400.0, 900.0])


def test_mzm_bias_away_from_quadrature_trades_power_for_eye():
    # allontanarsi dalla quadratura: PIÙ potenza media al PD (verso il
    # picco di trasmissione) ma occhio PEGGIORE — entrambe le direzioni
    q_quad = q_of(CFG.with_updates(mzm_bias_rad=1.5708))
    q_off = q_of(CFG.with_updates(mzm_bias_rad=0.9))
    assert q_off < q_quad
    assert (pd_dbm_of(CFG.with_updates(mzm_bias_rad=0.9))
            > pd_dbm_of(CFG.with_updates(mzm_bias_rad=1.5708)))


# --------------------------------------------------------- canale/ottica
def test_channel_insertion_loss_cascade():
    assert_monotone_q("channel_il_nyquist_db", [8.0, 12.0, 18.0])


def test_fiber_dispersion_cascade():
    assert_monotone_q("fiber_km", [0.5, 1.5, 2.5, 3.5],
                      dispersion_ps_nm_km=15.0)


# ------------------------------------------------------------------- RX
def test_pd_responsivity_cascade():
    qs = [q_of(CFG.with_updates(pd_responsivity_a_w=v))
          for v in (1.0, 0.7, 0.4)]
    assert qs[0] > qs[1] > qs[2]


def test_tia_noise_cascade():
    assert_monotone_q("tia_noise_a_rt_hz", [10e-12, 40e-12, 80e-12])


# ------------------------------------------------------------------ ADC
def test_adc_bits_improve_then_saturate():
    q5, q7, q9 = (q_of(CFG.with_updates(adc_bits=b)) for b in (5, 7, 9))
    assert q5 < q7                      # 5 bit: quantization-limited
    assert q9 > q5
    assert abs(q9 - q7) < 0.05          # oltre ~7 bit domina il rumore
                                        # analogico: saturazione VERA


def test_adc_aperture_jitter_cascade():
    assert_monotone_q("adc_jitter_rms_fs", [0.0, 300.0, 700.0])


def test_adc_frontend_bw_cascade():
    qs = [q_of(CFG.with_updates(adc_frontend_bw_hz=bw))
          for bw in (45e9, 30e9, 20e9)]
    assert qs[0] > qs[1] > qs[2]        # meno banda → più ISI → meno occhio


def test_adc_input_noise_cascade():
    assert_monotone_q("adc_noise_rms_mv", [0.0, 3.0, 8.0])


def test_adc_calibration_cascade_under_pvt():
    warm = dict(pvt_temp_c=85.0, adc_gain_mismatch_rms=0.02,
                adc_skew_mismatch_rms_fs=150.0,
                adc_offset_mismatch_rms_v=4e-3)
    q = {m: q_of(CFG.with_updates(adc_cal_mode=m, **warm))
         for m in ("background", "foreground", "off")}
    # a caldo la cal background insegue la deriva (meglio della foreground
    # coi residui che scalano); l'array grezzo è nettamente peggiore
    assert q["background"] > q["foreground"] > q["off"]


def test_adc_bw_mismatch_cascade():
    base = CFG.with_updates(adc_interleaves=32, adc_ranks=4,
                            adc_frontend_bw_hz=30e9)
    assert (q_of(base.with_updates(adc_bw_mismatch_pct=10.0))
            < q_of(base))


# ------------------------------------------------------------------ DSP
def test_dfe_taps_help_on_isi_channel():
    b1 = ber_of(CFG.with_updates(dfe_taps=1))
    b8 = ber_of(CFG.with_updates(dfe_taps=8))
    q1 = q_of(CFG.with_updates(dfe_taps=1))
    q8 = q_of(CFG.with_updates(dfe_taps=8))
    assert b8 < b1 and q8 > q1          # più tap → meno ISI residuo


# ---------------------------------------------- verosimiglianza numerica
def test_tone_lab_matches_quantization_theory():
    r = simulate(CFG, seed=SEED, depth="light")
    tl = adc_block.run_tone_lab(CFG, r.adc)
    # 7 bit, tono a −3.3 dBFS: SNDR ideale ≈ 6.02·7+1.76−3.3 = 40.6 dB
    assert tl.sndr_ideal_db == pytest.approx(40.6, abs=1.5)


def test_enob_at_nyquist_matches_aperture_jitter_limit():
    cfg = CFG.with_updates(adc_jitter_rms_fs=300.0, adc_gain_mismatch_rms=0.0,
                           adc_offset_mismatch_rms_v=0.0,
                           adc_skew_mismatch_rms_fs=0.0)
    r = simulate(cfg, seed=SEED, depth="light")
    tl = adc_block.run_tone_lab(cfg, r.adc)
    snr_j = -20 * np.log10(2 * np.pi * tl.tone_nyq_hz * 300e-15)
    expected_enob = (snr_j - 1.76) / 6.02
    # con solo jitter, l'ENOB effettivo a Nyquist DEVE seguire la formula
    # del limite d'apertura (misurato: 3.11 vs 3.11)
    assert tl.enob_nyq == pytest.approx(expected_enob, abs=0.6)


def test_enob_nyquist_monotone_in_jitter():
    def enob(j):
        cfg = CFG.with_updates(adc_jitter_rms_fs=j)
        r = simulate(cfg, seed=SEED, depth="light")
        return adc_block.run_tone_lab(cfg, r.adc).enob_nyq
    assert enob(90.0) > enob(300.0) > enob(700.0)
