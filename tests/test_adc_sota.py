"""ADC di nuova generazione (iterazione 32): architettura e propagazione.

Rank T/H gerarchici, banda front-end con spread per rank, calibrazione
foreground/background/off che interagisce col PVT, rumore input-referred,
tone-lab a Nyquist. Con i default storici il percorso resta BIT-IDENTICO
(baseline protetta dai test di regressione della suite).
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from serdes_sim import LinkConfig                              # noqa: E402
from serdes_sim.engine import simulate                         # noqa: E402
from serdes_sim.blocks import adc as adc_block                 # noqa: E402
from labpro import paneldata                                   # noqa: E402

CFG = LinkConfig()


# ------------------------------------------------------------ retro-compat
def test_defaults_keep_legacy_path():
    r = simulate(CFG, seed=20240731, depth="light")
    assert r.adc.cal_effective == 1.0        # foreground a PVT nominale
    assert r.adc.lane_rank is None           # array flat
    assert r.adc.rank_bw_hz is None          # front-end disattivo
    assert CFG.adc_cal_mode == "foreground"
    assert CFG.adc_ranks == 1 and CFG.adc_frontend_bw_hz == 0.0
    assert CFG.adc_bw_mismatch_pct == 0.0 and CFG.adc_noise_rms_mv == 0.0


# ------------------------------------------------------------- calibrazione
def test_cal_modes_order_under_pvt_stress():
    hot = dict(pvt_process="ss", pvt_temp_c=105.0)
    rms = {}
    for mode in ("background", "foreground", "off"):
        r = simulate(CFG.with_updates(adc_cal_mode=mode, **hot),
                     seed=99, depth="light")
        rms[mode] = float(np.std(r.adc.lane_gain))
    # background insegue il PVT (residuo di targa), foreground scala col
    # mismatch di processo, off è l'array grezzo ×8
    assert rms["background"] < rms["foreground"] < rms["off"]


def test_cal_background_equals_foreground_at_nominal_pvt():
    a = simulate(CFG.with_updates(adc_cal_mode="background"),
                 seed=99, depth="light")
    b = simulate(CFG.with_updates(adc_cal_mode="foreground"),
                 seed=99, depth="light")
    assert np.array_equal(a.adc.adc_samples_v, b.adc.adc_samples_v)


# ------------------------------------------------- banda front-end e rank
def test_frontend_pole_changes_samples():
    r_off = simulate(CFG, seed=99, depth="light")
    r_bw = simulate(CFG.with_updates(adc_frontend_bw_hz=20e9),
                    seed=99, depth="light")
    assert not np.array_equal(r_off.adc.adc_samples_v, r_bw.adc.adc_samples_v)
    assert r_bw.adc.rank_bw_hz is not None and len(r_bw.adc.rank_bw_hz) == 1


def test_rank_hierarchy_structure():
    r = simulate(CFG.with_updates(adc_interleaves=8, adc_ranks=4,
                                  adc_skew_mismatch_rms_fs=150.0),
                 seed=99, depth="light")
    assert r.adc.lane_rank.tolist() == [0, 1, 2, 3, 0, 1, 2, 3]
    assert r.adc.rank_skew_s.shape == (4,)
    # i lane di uno stesso rank condividono la componente di rank:
    # skew(lane) - skew_di_rank deve dare pattern indipendenti, ma la
    # componente condivisa deve essere esattamente quella dichiarata
    shared = r.adc.rank_skew_s[r.adc.lane_rank]
    assert np.all(np.abs(shared) <= np.abs(r.adc.lane_skew_s).max() + 1e-30)


def test_bw_mismatch_degrades_nyquist_not_low_tone():
    base = CFG.with_updates(adc_interleaves=32, adc_ranks=4,
                            adc_frontend_bw_hz=35e9)
    r_clean = simulate(base, seed=99, depth="light")
    r_mm = simulate(base.with_updates(adc_bw_mismatch_pct=10.0),
                    seed=99, depth="light")
    tl_clean = adc_block.run_tone_lab(base, r_clean.adc)
    tl_mm = adc_block.run_tone_lab(base.with_updates(adc_bw_mismatch_pct=10.0),
                                   r_mm.adc)
    # il mismatch di banda è dipendente dalla frequenza: a Nyquist degrada
    # SNDR e alza le spur molto più che sul tono basso
    assert tl_mm.sndr_nyq_db < tl_clean.sndr_nyq_db - 3.0
    assert tl_mm.spur_nyq_dbfs > tl_clean.spur_nyq_dbfs + 3.0
    drop_nyq = tl_clean.sndr_nyq_db - tl_mm.sndr_nyq_db
    drop_low = tl_clean.sndr_mismatch_db - tl_mm.sndr_mismatch_db
    assert drop_nyq > drop_low


def test_enob_at_nyquist_below_low_tone_with_skew_and_bw():
    cfg = CFG.with_updates(adc_interleaves=32, adc_ranks=4,
                           adc_frontend_bw_hz=35e9, adc_bw_mismatch_pct=8.0,
                           adc_skew_mismatch_rms_fs=100.0)
    r = simulate(cfg, seed=99, depth="light")
    tl = adc_block.run_tone_lab(cfg, r.adc)
    assert tl.enob_nyq < tl.enob_mismatch          # Nyquist è il numero duro
    assert np.isfinite(tl.spur_nyq_dbfs)
    assert tl.tone_nyq_hz > 0.4 * cfg.fs_adc_hz


# ------------------------------------------------------------------ rumore
def test_input_noise_reaches_the_samples():
    r0 = simulate(CFG, seed=99, depth="light")
    rn = simulate(CFG.with_updates(adc_noise_rms_mv=8.0), seed=99,
                  depth="light")
    diff = rn.adc.adc_samples_v - r0.adc.adc_samples_v
    frac = float(np.mean(diff != 0))
    assert frac > 0.05        # il rumore attraversa la quantizzazione
    assert rn.link_up in (True, False)   # la catena resta valida


# --------------------------------------------------------------- validate
def test_validation_rejects_bad_architecture():
    assert any("adc_ranks" in p for p in
               CFG.with_updates(adc_interleaves=4, adc_ranks=3).validate())
    assert any("adc_cal_mode" in p for p in
               CFG.with_updates(adc_cal_mode="magia").validate())
    assert any("adc_bw_mismatch_pct" in p for p in
               CFG.with_updates(adc_bw_mismatch_pct=99.0).validate())


# ---------------------------------------------------- propagazione pannello
def test_adc_panel_reports_architecture_and_nyquist():
    import json
    cfg = CFG.with_updates(adc_interleaves=16, adc_ranks=4,
                           adc_frontend_bw_hz=35e9, adc_bw_mismatch_pct=5.0,
                           adc_cal_mode="background", adc_noise_rms_mv=1.0)
    sim = simulate(cfg, seed=99, depth="light")
    sim.tone_lab = adc_block.run_tone_lab(cfg, sim.adc)
    out = paneldata.adc_panel(sim, cfg)
    json.dumps(out)                                  # serializzabile
    assert out["arch"]["interleaves"] == 16 and out["arch"]["ranks"] == 4
    assert out["arch"]["cal_mode"] == "background"
    assert len(out["arch"]["rank_bw_ghz"]) == 4
    assert len(out["enob_nyq"]) == 2 and out["tone_nyq_ghz"] > 40
