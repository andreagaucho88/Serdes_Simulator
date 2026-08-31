"""Regression e unit test del motore. Esecuzione:

    cd simulatore && python -m pytest tests -q
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from serdes_sim import LinkConfig, simulate, sweep
from serdes_sim.blocks import fec
from serdes_sim.blocks.metrics import decision_thresholds, eye_density
from serdes_sim.utils import butterworth_magnitude, butterworth_response


@pytest.fixture(scope="module")
def baseline_full():
    return simulate(LinkConfig(), depth="full")


# --- regressione numerica delle baseline -------------------------------------

def test_oracle_baseline_regression():
    # la modalità idealizzata resta bit-esatta rispetto alla fisica v7
    r = simulate(LinkConfig(cdr_mode="oracle"), depth="light")
    assert r.ber_pre_eq == pytest.approx(6.440e-2, rel=0.02)
    assert r.ber_post_dfe == pytest.approx(2.026e-2, rel=0.02)
    assert r.gmi_total == pytest.approx(1.8327, abs=0.01)


def test_cdr_baseline_links_up(baseline_full):
    r = baseline_full
    assert r.cdr is not None and r.cdr.locked and r.cdr.pattern_locked
    assert r.link_up
    assert abs(r.cdr.pattern_corr) > 0.8      # catena invertente: corr negativa
    assert 0.01 < r.ber_post_dfe < 0.03       # vicino all'oracle
    assert r.cdr.cycle_slips == 0


def test_baseline_checkpoints_pass(baseline_full):
    fails = [c for c in baseline_full.checks if c["status"] == "FAIL"]
    assert fails == [], f"checkpoint FAIL sulla baseline: {fails}"


def test_link_down_gates_metrics():
    r = simulate(LinkConfig(laser_dbm=-6.0), depth="light")
    assert not r.link_up
    assert np.isnan(r.ber_post_dfe)
    assert r.eq is None and r.fec is None and r.gmi_total is None
    assert any("LINK DOWN" in c["check"] for c in r.checks
               if c["status"] == "FAIL")


def test_cdr_tracks_ppm_offset():
    r = simulate(LinkConfig(rx_ppm_offset=-200.0), depth="light")
    assert r.link_up
    f_tail = float(np.mean(r.cdr.freq_trace_ppm[-800:]))
    assert f_tail == pytest.approx(200.0, abs=50.0)


def test_oracle_with_ppm_rejected():
    assert LinkConfig(cdr_mode="oracle", rx_ppm_offset=100.0).validate()


# --- codec RS(544,514) -------------------------------------------------------

def test_rs_codec_corrects_up_to_t():
    rows = fec.codec_demo(error_counts=(0, 1, 7, 15), seed=11)
    assert all(r["esito"] == "corretto" for r in rows)


def test_rs_codec_beyond_t_no_silent_success():
    # oltre t: failure dichiarata o miscorrezione, MAI ripristino garantito
    rows = fec.codec_demo(error_counts=(16,), seed=11)
    assert rows[0]["esito"] != "corretto" or rows[0]["correzioni_riportate"] <= 15


def test_rs_encode_syndrome_zero():
    rng = np.random.default_rng(3)
    cw = fec.rs_encode(rng.integers(0, fec.GF_SIZE, fec.RS_K))
    assert not np.any(fec.rs_syndromes(cw))


def test_fer_curve_families():
    # KR4 (t=7) deve avere soglia pre-FEC più bassa di KP4 (t=15)
    thr_kp4 = fec.prefec_ber_threshold(1e-13, n=544, t=15, m=10)
    thr_kr4 = fec.prefec_ber_threshold(1e-13, n=528, t=7, m=10)
    assert thr_kr4 < thr_kp4
    assert 1e-5 < thr_kp4 < 1e-3  # ordine di grandezza del ~2e-4 citato


def test_burstiness_semantics():
    # errori raggruppati negli stessi simboli 10b -> ratio < 1
    true_bits = np.zeros(544 * 10 * 2, dtype=np.uint8)
    clustered = true_bits.copy()
    clustered[:40] ^= 1          # 40 bit errati in 4 simboli
    fa = fec.analyze_link_fec(true_bits, clustered)
    assert fa.burstiness_ratio < 0.5
    spread = true_bits.copy()
    spread[::250] ^= 1           # stessi ~40 errori, sparsi
    fa2 = fec.analyze_link_fec(true_bits, spread)
    assert fa2.burstiness_ratio > fa.burstiness_ratio


# --- validazioni e guardie ---------------------------------------------------

def test_depth_validated():
    with pytest.raises(ValueError):
        simulate(LinkConfig(), depth="banana")


def test_config_rejects_even_fse_taps():
    assert any("fse_taps" in p for p in LinkConfig(fse_taps=6).validate())


def test_config_rejects_nonpositive():
    assert LinkConfig(tia_bw_hz=-1).validate()
    assert LinkConfig(adc_interleaves=0).validate()


def test_thresholds_guard_short():
    assert decision_thresholds([]) == ([], [])
    assert decision_thresholds([{"mean": 0, "sigma": 1}]) == ([], [])


def test_eye_density_short_record():
    x = np.random.default_rng(0).normal(size=16 * 40)
    H, te, ve, segs, t_ui = eye_density(x, 16, start_symbol=80)
    assert H.size > 0


# --- filtri causali ----------------------------------------------------------

def test_causal_magnitude_matches_zero_phase():
    f = np.linspace(-100e9, 100e9, 4001)
    mag0 = butterworth_magnitude(f, 35e9, 3)
    magc = np.abs(butterworth_response(f, 35e9, 3, causal=True))
    assert np.allclose(mag0, magc, rtol=1e-9)


def test_causal_run_produces_finite_link():
    r = simulate(LinkConfig(causal_filters=True), depth="light")
    assert np.isfinite(r.ber_post_dfe) and r.ber_post_dfe < 0.4


# --- modulazioni -------------------------------------------------------------

def test_nrz_beats_pam4():
    r_nrz = simulate(LinkConfig(modulation="NRZ"), depth="light")
    r_pam = simulate(LinkConfig(), depth="light")
    assert r_nrz.ber_post_dfe <= r_pam.ber_post_dfe


def test_gray_beats_binary():
    r_gray = simulate(LinkConfig(), depth="light")
    r_bin = simulate(LinkConfig(pam4_mapping="binary"), depth="light")
    assert r_gray.ber_post_dfe <= r_bin.ber_post_dfe * 1.05


# --- sweep -------------------------------------------------------------------

def test_sweep_carries_val_bits():
    rows = sweep(LinkConfig(), "fiber_km", [0.0, 2.0])
    assert all(r["val_bits"] > 1000 for r in rows)
    assert all(np.isfinite(r["FER_RS544_iid"]) for r in rows)


# --- piani di riferimento ----------------------------------------------------

def test_threshold_planes_are_distinct(baseline_full):
    r = baseline_full
    assert r.thresholds_dfe[0] and r.thresholds_baud[0]
    # i piani non devono essere identici (statistiche diverse)
    assert not np.allclose(r.thresholds_dfe[1], r.thresholds_baud[1], atol=1e-6)


# --- FEC nel percorso (in-path) ---------------------------------------------

GOOD_LINK = dict(fiber_km=0.0, chirp_alpha=0.0, channel_il_nyquist_db=6.0)


def test_rs_codec_class_kr4():
    rng = np.random.default_rng(5)
    msg = rng.integers(0, fec.GF_SIZE, fec.KR4.k)
    cw = fec.KR4.encode(msg)
    assert len(cw) == 528 and not np.any(fec.KR4.syndromes(cw))
    bad = cw.copy()
    pos = rng.choice(528, 7, replace=False)
    bad[pos] ^= rng.integers(1, fec.GF_SIZE, 7)
    fixed, n = fec.KR4.decode(bad)
    assert n == 7 and np.array_equal(fixed, cw)
    bad2 = cw.copy()
    pos = rng.choice(528, 8, replace=False)
    bad2[pos] ^= rng.integers(1, fec.GF_SIZE, 8)
    with pytest.raises(ValueError):
        fec.KR4.decode(bad2)


def test_fec_in_path_corrects_good_link():
    r = simulate(LinkConfig(fec_mode="kp4", **GOOD_LINK), depth="light")
    fl = r.fec_link
    assert fl is not None and fl.n_frames >= 1
    assert fl.frames_uncorrectable == 0
    assert fl.post_fec_ber == 0.0
    assert fl.pre_fec_ber > 0  # il decoder ha davvero lavorato
    assert fl.symbols_corrected > 0


def test_fec_in_path_fails_on_bad_link():
    r = simulate(LinkConfig(fec_mode="kp4"), depth="light")  # default stressato
    fl = r.fec_link
    assert fl.frames_uncorrectable == fl.n_frames  # tutti persi: BER 2e-2 >> soglia


def test_fec_miscorrection_category():
    # received a distanza ≤ t da un ALTRO codeword: il decoder "corregge"
    # verso quello — decode_stream deve classificarlo miscorrected
    rng = np.random.default_rng(9)
    c1 = fec.KP4.encode(rng.integers(0, fec.GF_SIZE, fec.KP4.k))
    c2 = fec.KP4.encode(rng.integers(0, fec.GF_SIZE, fec.KP4.k))
    received = c2.copy()
    pos = rng.choice(fec.KP4.n, 10, replace=False)
    received[pos] ^= rng.integers(1, fec.GF_SIZE, 10)
    tx_bits = fec.gf_symbols_to_bits(c1)
    rx_bits = fec.gf_symbols_to_bits(received)
    fl = fec.decode_stream(rx_bits, tx_bits, fec.KP4, 1)
    assert fl.frames_miscorrected == 1
    assert fl.frames_corrected == 0 and fl.frames_uncorrectable == 0
    assert fl.post_fec_bit_errors > 0


def test_fec_frames_validation_only():
    r = simulate(LinkConfig(fec_mode="kp4", **GOOD_LINK), depth="light")
    codec_syms = 544 * 10 // 2   # simboli PAM4 per frame KP4
    for f in r.fec_frames_covered:
        assert f * codec_syms >= r.cfg.training_stop + 200


def test_eye_measures_polarity_rectified():
    from labpro.paneldata import eye_measures
    # baseline (eye CTLE chiuso ma polarità raddrizzata)
    r = simulate(LinkConfig(), depth="light")
    m = eye_measures(r, LinkConfig(), node="vctle")
    assert m["inverted"] is True          # la catena MZM/TIA inverte
    means = [s["mean"] for s in m["levels"]]
    assert means == sorted(means)         # crescenti nel dominio raddrizzato
    assert all(q > 0 for q in m["q_per_eye"])
    assert 0 < m["rlm_proxy"] <= 1.0
    assert m["t_rise_ps"] is not None
    # link buono: gli occhi devono risultare APERTI (height 3σ positiva)
    cfg2 = LinkConfig(**GOOD_LINK)
    r2 = simulate(cfg2, depth="light")
    m2 = eye_measures(r2, cfg2, node="vctle")
    assert all(h > 0 for h in m2["eye_heights"])


def test_fec_bits_roundtrip():
    rng = np.random.default_rng(2)
    bits = rng.integers(0, 2, 5140, dtype=np.uint8)
    assert np.array_equal(
        fec.gf_symbols_to_bits(fec.bits_to_gf_symbols(bits)), bits)


# --- jitter TX e analisi TIE -------------------------------------------------

def test_tx_pj_tone_is_measured():
    from labpro.paneldata import jitter_panel
    cfg = LinkConfig(tx_pj_amp_ui=0.06, tx_pj_freq_mhz=400.0)
    r = simulate(cfg, depth="light")
    jp = jitter_panel(r, cfg, node="driver")
    spec = np.array([v or 0 for v in jp["spec_mag_mui"]])
    f = np.array(jp["spec_f_mhz"])
    assert abs(f[np.argmax(spec)] - 400) < 40  # tono PJ ritrovato
    assert jp["n_edges"] > 1000


def test_tx_rj_degrades_ber():
    r0 = simulate(LinkConfig(), depth="light")
    r1 = simulate(LinkConfig(tx_rj_rms_fs=800.0), depth="light")
    assert r1.ber_post_dfe > r0.ber_post_dfe


def test_tx_jitter_zero_keeps_baseline_bitexact():
    # con jitter a zero non vengono consumati draw rng: baseline identica
    r0 = simulate(LinkConfig(), depth="light")
    r1 = simulate(LinkConfig(tx_pj_freq_mhz=999.0), depth="light")  # ampiezza 0
    assert r0.ber_post_dfe == r1.ber_post_dfe


def test_livebench_epf_hist_accumulates():
    import time
    from serdes_sim.livebench import LiveBench
    b = LiveBench(LinkConfig(fec_mode="kp4", **GOOD_LINK))
    b.start(); time.sleep(2.5); b.stop()
    s = b.snapshot()
    hist = s["fec"]["epf_hist"]
    assert len(hist) == 41 and sum(hist) == s["fec"]["frames_total"] > 0


def test_s4p_mixed_mode():
    # s4p sintetico: solo trasmissione differenziale ideale fra le coppie
    # (1,3)→(2,4): S21=S43=0.5, S23=S41=-0.25 → SDD21=0.75, SCD21=0.25? no:
    # SDD21 = 0.5*(S21 - S23 - S41 + S43)
    from serdes_sim.blocks.channel import parse_touchstone_text, s4p_mixed_mode_21
    rows = []
    for f in (1.0, 10.0, 20.0):
        S = [[0.0] * 8 for _ in range(4)]
        vals = []
        M = np.zeros((4, 4))
        M[1, 0] = 0.5; M[3, 2] = 0.5    # S21, S43
        M[1, 2] = -0.25; M[3, 0] = -0.25  # S23, S41
        for i in range(4):
            for j in range(4):
                vals += [M[i, j], 0.0]
        rows.append(" ".join(str(v) for v in [f] + vals))
    text = "# GHZ S RI R 50\n" + "\n".join(rows)
    fhz, S4, z0, n_ports = parse_touchstone_text(text)
    assert n_ports == 4 and len(fhz) == 3
    sdd21, scd21 = s4p_mixed_mode_21(fhz, S4, "13_24")
    assert np.allclose(sdd21, 0.5 * (0.5 - (-0.25) - (-0.25) + 0.5))
    # il mapping alternativo dà un risultato diverso (porte diverse)
    sdd21b, _ = s4p_mixed_mode_21(fhz, S4, "12_34")
    assert not np.allclose(sdd21, sdd21b)


def test_ethernet_roundtrip_and_analyzer():
    from serdes_sim.blocks import ethernet
    bits, n_frames, _ = ethernet.build_stream_bits(60000, 256)
    a = ethernet.analyze_stream_bits(bits, 256, window_s=1e-6)
    assert a.frames_ok >= n_frames - 1 and a.frames_fcs_bad == 0
    assert a.frames_lost == 0
    # corrompi un byte: un frame perde l'FCS
    bad = bits.copy(); bad[3000] ^= 1
    a2 = ethernet.analyze_stream_bits(bad, 256, window_s=1e-6)
    assert a2.frames_fcs_bad >= 1


def test_l2_through_phy_with_fec():
    r = simulate(LinkConfig(pattern="eth", fec_mode="kp4", **GOOD_LINK),
                 depth="light")
    assert r.link_up and r.l2 is not None
    assert r.l2.frames_ok >= 1 and r.l2.frames_fcs_bad == 0
    assert r.l2.frames_lost == 0


def test_bert_error_insertion_counted():
    base = simulate(LinkConfig(**GOOD_LINK), depth="light")
    r = simulate(LinkConfig(err_insert_bits=20, **GOOD_LINK), depth="light")
    delta = r.metrics_rows[2]["bit_errors"] - base.metrics_rows[2]["bit_errors"]
    assert 15 <= delta <= 20     # quasi tutte le inserzioni contate dall'ED


def test_copper_medium_runs_and_skips_optics():
    r = simulate(LinkConfig(link_medium="copper",
                            channel_il_nyquist_db=14.0), depth="light")
    assert r.link_up and r.optical is None
    assert r.ber_post_dfe < 0.05


def test_pn_skew_degrades_link():
    r0 = simulate(LinkConfig(), depth="light")
    r1 = simulate(LinkConfig(pn_skew_ps=6.0), depth="light")
    assert r1.ber_post_dfe > r0.ber_post_dfe


def test_link_train_improves_or_keeps():
    from serdes_sim.engine import link_train
    cfg = LinkConfig(ctle_zero_hz=15e9)   # partenza volutamente storta
    new_cfg, steps, base, final = link_train(cfg, seeds=(1101,))
    assert final <= base + 1e-9
    assert len(steps) == 4


def test_livebench_accumulates_and_resets():
    import time
    from serdes_sim.livebench import LiveBench
    b = LiveBench(LinkConfig(fec_mode="kp4", **GOOD_LINK))
    b.start()
    time.sleep(2.5)
    b.stop()
    s = b.snapshot()
    assert s["records"] >= 2 and s["bits_total"] > 0
    assert s["fec"]["in_path"] and s["fec"]["frames_total"] >= 2
    b.set_config(LinkConfig())
    assert b.snapshot()["records"] == 0
