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


def test_tx_differential_noise_is_real_stimulus_stress():
    cfg = LinkConfig(link_medium="copper", channel_il_nyquist_db=9.0)
    r0 = simulate(cfg, seed=19, depth="light")
    r1 = simulate(cfg.with_updates(tx_diff_noise_mv=80.0), seed=19,
                  depth="light")
    assert np.array_equal(r0.tx.driver_voltage_v, r1.tx.driver_voltage_v)
    assert not np.array_equal(r0.tx.v_diff_v, r1.tx.v_diff_v)
    assert r1.ber_post_dfe >= r0.ber_post_dfe


def test_pn_scope_nodes_obey_differential_definitions():
    cfg = LinkConfig(pn_gain_mismatch_pct=12.0, pn_skew_ps=1.0,
                     vcm_offset_v=0.1, vcm_noise_mv=10.0)
    r = simulate(cfg, seed=23, depth="light")
    assert np.allclose(r.tx.v_diff_v, r.tx.vp_v - r.tx.vn_v)
    assert np.allclose(r.tx.vcm_v, 0.5 * (r.tx.vp_v + r.tx.vn_v))
    # Il mismatch da solo non cambia il differenziale ma genera common-mode.
    r2 = simulate(LinkConfig(pn_gain_mismatch_pct=12.0), seed=23,
                  depth="light")
    assert np.allclose(r2.tx.v_diff_v, r2.tx.driver_voltage_v)
    assert np.std(r2.tx.vcm_v) > 0


def test_single_ended_drive_consumes_branch_and_common_mode():
    base = LinkConfig(vcm_offset_v=0.12, vcm_noise_mv=8.0,
                      pn_gain_mismatch_pct=6.0)
    rd = simulate(base, seed=29, depth="light")
    rp = simulate(base.with_updates(electrical_drive_mode="single_ended_p"),
                  seed=29, depth="light")
    assert np.array_equal(rp.channel_input_v, rp.tx.vp_v)
    assert np.array_equal(rd.channel_input_v, rd.tx.v_diff_v)
    assert not np.allclose(rp.channel.electrical_waveform_v,
                           rd.channel.electrical_waveform_v)


def test_eml_is_distinct_large_signal_modulator():
    cfg = LinkConfig(optical_modulator="eml", laser_type="dfb_eml_integrated",
                     electrical_drive_mode="single_ended_p",
                     eml_er_db=5.0, eml_chirp_alpha=2.5)
    r = simulate(cfg, seed=31, depth="light")
    assert r.optical.modulator == "eml"
    assert "EML output" in r.optical.power_budget_dbm
    assert np.min(r.optical.p_static) > 0
    assert np.ptp(r.optical.inst_freq_shift_hz) > 0


def test_optical_architectures_are_consistent_and_mmf_is_physical():
    assert LinkConfig(optical_modulator="eml").validate()
    dml = LinkConfig(optical_modulator="dml", laser_type="dfb_direct",
                     electrical_drive_mode="single_ended_p")
    rd = simulate(dml, seed=32, depth="light")
    assert rd.optical.modulator == "dml"
    vcsel = LinkConfig(optical_modulator="vcsel", laser_type="vcsel_direct",
                       electrical_drive_mode="single_ended_p", fiber_type="mmf",
                       wavelength_nm=850.0, fiber_km=0.1)
    rv = simulate(vcsel, seed=33, depth="light")
    assert rv.optical.modulator == "vcsel"
    assert np.isclose(rv.optical.modal_bw_hz, 47e9)
    assert rv.optical.beta2_s2_m == 0


def test_fiber_cd_slope_pmd_kerr_are_reported():
    cfg = LinkConfig(fiber_km=5.0, pmd_ps_sqrt_km=0.5,
                     fiber_gamma_w_inv_km=2.0,
                     dispersion_slope_ps_nm2_km=0.08)
    r = simulate(cfg, seed=34, depth="light")
    assert r.optical.beta2_s2_m != 0 and r.optical.beta3_s3_m != 0
    assert r.optical.pmd_dgd_ps > 0
    assert r.optical.nonlinear_phase_peak_rad > 0


def test_jitter_panel_has_live_bathtub_and_acquisition_identity():
    from labpro.paneldata import jitter_panel
    cfg = LinkConfig(link_medium="copper", channel_il_nyquist_db=6.0,
                     tx_rj_rms_fs=500.0)
    r1 = simulate(cfg, seed=501, depth="light")
    r2 = simulate(cfg, seed=502, depth="light")
    j1, j2 = jitter_panel(r1, cfg, "driver"), jitter_panel(r2, cfg, "driver")
    assert len(j1["bathtub_x_ui"]) == len(j1["bathtub_ber_proxy"]) == 161
    assert min(j1["bathtub_ber_proxy"]) > 0
    assert j1["tie_rms_ps"] != j2["tie_rms_ps"]
    assert not r1.timing_is_supervised
    assert simulate(cfg.with_updates(cdr_mode="oracle"), depth="light").timing_is_supervised


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


def test_livebench_hist_strips_and_rate():
    import time
    from serdes_sim.livebench import LiveBench
    b = LiveBench(LinkConfig(**GOOD_LINK))
    b.start(); time.sleep(2.0); b.stop()
    s = b.snapshot()
    h = s["hist"]
    assert s["records"] > 0
    # un punto per record, per ogni strip
    for key in ("ber", "snr_db", "f_ppm", "tau_rms_ui", "q_min", "errors"):
        assert len(h[key]) == min(s["records"], 240), key
    assert all(v is None or v > 0 for v in h["snr_db"])
    if s["records"] >= 2:
        assert s["records_per_s"] and s["records_per_s"] > 0


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
        # Touchstone 1.x: S11,S21,...,SN1,S12,... (column-major)
        for j in range(4):
            for i in range(4):
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
    assert np.allclose(S4[:, 1, 0], 0.5)   # S21 non trasposto
    assert np.allclose(S4[:, 0, 1], 0.0)   # S12 distinto


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
    # Un falso 55-D5 nel payload non deve creare un frame fantasma.
    fake = np.concatenate([bits, ethernet._bytes_to_bits(b"\x55\xd5" + bytes(80))])
    a3 = ethernet.analyze_stream_bits(fake, 256, window_s=1e-6)
    assert a3.frames_detected == a.frames_detected


def test_traffic_sweep_is_real_l2_phy_path():
    from serdes_sim.engine import traffic_sweep
    rows = traffic_sweep(LinkConfig(link_medium="copper",
                                    channel_il_nyquist_db=6.0,
                                    fec_mode="kp4"), (64, 256))
    assert [r["frame_bytes"] for r in rows] == [64, 256]
    assert all(r["link_up"] and r["frames_detected"] > 0 for r in rows)
    assert all(0 <= r["payload_efficiency_pct"] <= 100 for r in rows)


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


def test_burst_insertion_is_contiguous_and_stresses_fec():
    """Stesso numero di bit, ma il burst deve costare di più al RS in
    simboli/frame colpiti rispetto agli errori sparsi."""
    from serdes_sim.blocks import fec as fec_block
    iid = simulate(LinkConfig(err_insert_bits=40, fec_mode="kp4",
                              **GOOD_LINK), depth="light")
    burst = simulate(LinkConfig(err_insert_bits=40, err_insert_burst=True,
                                fec_mode="kp4", **GOOD_LINK), depth="light")
    assert iid.link_up and burst.link_up
    # il burst concentra gli errori: i frame corrotti sono meno (o uguali),
    # ma i simboli RS per frame colpito sono di più
    fi, fb = iid.fec_link, burst.fec_link
    hit_i = fi.frames_corrected + fi.frames_uncorrectable
    hit_b = fb.frames_corrected + fb.frames_uncorrectable
    assert hit_b <= hit_i


def test_l2_ipg_changes_offered_load():
    r12 = simulate(LinkConfig(pattern="eth", l2_ipg_bytes=12,
                              **GOOD_LINK), depth="light")
    r384 = simulate(LinkConfig(pattern="eth", l2_ipg_bytes=384,
                               **GOOD_LINK), depth="light")
    assert r12.l2 is not None and r384.l2 is not None
    # più IPG = meno frame nella stessa finestra (offered load più basso);
    # la sopravvivenza dei singoli frame dipende dalla BER residua (×3 dal
    # descrambler self-sync), quindi qui non si pretende lost == 0
    assert r384.l2.frames_expected < r12.l2.frames_expected


def test_pcs_scrambler_keeps_link_alive_on_long_ipg():
    """Senza scrambler l'IPG 0x00 lungo produce run costanti che uccidono
    il CDR: con lo scrambler Clause 49 il link resta UP anche a IPG 2000."""
    r = simulate(LinkConfig(pattern="eth", l2_ipg_bytes=2000,
                            **GOOD_LINK), depth="light")
    assert r.link_up and r.ber_post_dfe < 5e-3


def test_scrambler_roundtrip_and_error_multiplication():
    from serdes_sim.blocks import ethernet
    rng = np.random.default_rng(3)
    d = rng.integers(0, 2, 4000).astype(np.uint8)
    line = ethernet.scramble(d)
    assert np.array_equal(ethernet.descramble(line), d)
    hit = line.copy(); hit[2000] ^= 1
    assert int((ethernet.descramble(hit) ^ d).sum()) == 3


def test_jitter_transfer_tracks_low_freq():
    from serdes_sim.engine import jitter_transfer
    pts = jitter_transfer(LinkConfig(**GOOD_LINK), freqs_mhz=(10.0, 800.0),
                          amp_ui=0.05)
    lo = next(q for q in pts if q["freq_mhz"] == 10.0)
    hi = next(q for q in pts if q["freq_mhz"] == 800.0)
    assert lo["jtf_db"] is not None
    # in banda il loop insegue (JTF vicino a 0 dB); fuori banda attenua
    assert lo["jtf_db"] > -6.0
    if hi["jtf_db"] is not None:
        assert hi["jtf_db"] < lo["jtf_db"]


def test_anlt_resolution_and_lt_protocol():
    from serdes_sim.engine import anlt_session
    out = anlt_session(LinkConfig(**GOOD_LINK), lt_rounds=2, lt_step=0.03)
    res = out["an"]["resolution"]
    assert res["hcd"] == "A18"          # 112G/lane PAM4 → 400GBASE-KR4/CR4
    assert "RS(544,514)" in res["fec"]
    states = [t["state"] for t in out["an"]["timeline"]]
    assert states[0] == "AN_ENABLE" and states[-1] == "AN_GOOD"
    lt = out["lt"]
    # rigore: il verdetto esiste solo con CDR agganciato e occhio aperto
    assert lt["cdr_locked"] and lt["eye_open"]
    assert lt["q_after"] > 0
    assert lt["frames"][0]["request"].startswith("preset 1")
    assert lt["frames"][-1]["request"] == "local receiver ready"
    assert all(f["status"] in ("updated", "not_updated", "at_limit",
                               "ready", "no lock") for f in lt["frames"])
    assert len(lt["taps_after"]) == 5   # il training lavora sul FIR a 5 tap


def test_anlt_brings_up_dead_link():
    """Config reale trovata sul banco: IL 20 dB + CTLE spenta = CDR mai
    agganciato. L'LT rigoroso (preset 2/3 a 5 tap + metrica di apertura)
    deve fare il bring-up: CDR LOCKED e occhio aperto."""
    from serdes_sim.engine import anlt_session
    dead = LinkConfig(tx_ffe_taps=(-0.08, 1.0, -0.08),
                      channel_il_nyquist_db=20.0, return_loss_db=12.0,
                      ctle_zeros_hz=(), ctle_poles_hz=())
    assert not simulate(dead, seed=1101, depth="light").link_up
    out = anlt_session(dead, lt_rounds=2, lt_step=0.03)
    lt = out["lt"]
    assert lt["cdr_locked"] and lt["eye_open"]
    assert out["cfg_after"].validate() == []


def test_tx_fir_five_taps_valid_and_effective():
    c3 = LinkConfig(**GOOD_LINK)
    c5 = c3.with_updates(tx_ffe_taps=(0.0, -0.08, 1.0, -0.08, 0.0))
    assert c5.validate() == []
    assert LinkConfig(tx_ffe_taps=(1.0, 0.0)).validate() != []
    r3 = simulate(c3, seed=7, depth="light")
    r5 = simulate(c5, seed=7, depth="light")
    # stesso FIR imbottito di zeri = stessa risposta (main resta centrato)
    assert abs(r3.ber_post_dfe - r5.ber_post_dfe) < 1e-12


def test_eye_measures_eh_at_ber_and_jitter_tailfit():
    from labpro import paneldata
    cfg = LinkConfig(**GOOD_LINK)
    sim = simulate(cfg, seed=11, depth="light")
    m = paneldata.eye_measures(sim, cfg, node="vctle")
    assert "eh_at_ber" in m and len(m["eh_at_ber"]["2.4e-4"]) == 3
    # l'EH estrapolata a BER più severa è sempre più piccola
    for h4, h6 in zip(m["eh_at_ber"]["2.4e-4"], m["eh_at_ber"]["1e-6"]):
        assert h6 < h4
    jp = paneldata.jitter_panel(sim, cfg, node="vctle")
    tf = jp["tail_fit"]
    assert tf is not None and tf["rj_ps"] >= 0
    assert tf["tj_1e12_ps"] >= tf["tj_2p4e4_ps"]


def test_anlt_bidirectional_both_ready():
    from serdes_sim.engine import anlt_session
    out = anlt_session(LinkConfig(**GOOD_LINK), lt_rounds=1, lt_step=0.03)
    lt = out["lt"]
    rev = lt["reverse"]
    assert rev["ready"] and rev["q_after"] > 0
    assert lt["both_ready"] == (lt["ready"] and rev["ready"]) == True


def test_l2_frame_inspector_decodes_real_bytes():
    from labpro import paneldata
    cfg = LinkConfig(pattern="eth", fec_mode="kp4", **GOOD_LINK)
    sim = simulate(cfg, seed=11, depth="light")
    d = paneldata.l2_panel(sim, cfg)
    frames = d["frames"]
    assert len(frames) >= 1
    f0 = frames[0]
    assert f0["ethertype"] == "0x88b5" and f0["fcs_ok"]
    assert f0["fcs_rx"] == f0["fcs_calc"]
    assert f0["hex_head"].startswith("55 55 55 55 55 55 55 d5")
    # sequence numbers crescenti
    seqs = [f["seq"] for f in frames]
    assert seqs == sorted(seqs)


def test_eye_contour_shape_and_center():
    from labpro import paneldata
    cfg = LinkConfig(**GOOD_LINK)
    sim = simulate(cfg, seed=11, depth="light")
    d = paneldata.eye_contour_panel(sim, cfg, node="vctle")
    lb = np.asarray(d["logber"])
    assert lb.shape == (70, 25)
    # il centro dell'occhio deve avere BER migliore dei bordi di fase
    assert lb.min() < -2.0
    assert lb[:, 0].min() > lb.min() - 1e-9


def test_adc_panel_sampling_plots():
    from labpro import paneldata
    cfg = LinkConfig(**GOOD_LINK)
    sim = simulate(cfg, seed=11, depth="light")
    d = paneldata.adc_panel(sim, cfg)
    sm = d["sampling"]
    assert sm is not None and len(sm["data_hist"]) == 80
    assert len(sm["scatter_y"]) == len(sm["scatter_dec"])
    assert len(sm["thresholds_v"]) == 3
    # i campioni DATA devono essere multimodali: il picco della hist edge
    # al centro (transizioni) supera quello della data al centro
    assert sum(sm["data_hist"]) > 0 and sum(sm["edge_hist"]) > 0


def test_education_cards_are_substantive():
    from labpro.education import TOPICS
    assert len(TOPICS) >= 17
    for t in TOPICS:
        assert len(t["deep"]["it"]) > 200, t["id"]
        assert len(t["deep"]["en"]) > 200, t["id"]
        assert len(t["numbers"]) >= 4, t["id"]
        assert len(t["actions"]) >= 2, t["id"]


def test_anlt_no_common_ability():
    from serdes_sim.blocks.autoneg import resolve
    res = resolve(["A16", "A17"], ["A0", "A2"])
    assert res["hcd"] is None


def test_l2_ont_report_budget_and_ramp():
    from serdes_sim.engine import l2_ont_report
    cfg = LinkConfig(pattern="eth", fec_mode="kp4", **GOOD_LINK)
    out = l2_ont_report(cfg, ipg_grid=(12, 384))
    assert out["latency_total_ns"] > 0
    items = [b["item"] for b in out["latency_budget"]]
    assert "serializzazione frame" in items
    assert "FEC store&forward (enc+dec)" in items
    offered = [r["offered_pct"] for r in out["ramp"]]
    assert offered[0] > offered[1]      # IPG più grande = offered più basso


def test_copper_medium_runs_and_skips_optics():
    r = simulate(LinkConfig(link_medium="copper",
                            channel_il_nyquist_db=14.0), depth="light")
    assert r.link_up and r.optical is None
    assert r.ber_post_dfe < 0.05


def test_standard_catalog_is_consistent_and_honest():
    from serdes_sim.config import STANDARD_PROFILES, STANDARD_PROFILE_META
    assert len(STANDARD_PROFILES) >= 12
    assert set(STANDARD_PROFILES) == set(STANDARD_PROFILE_META)
    assert not any("802.3by — 25GBASE-LR" in name for name in STANDARD_PROFILES)
    dj = STANDARD_PROFILES["P802.3dj (draft) — 200G/lane · elettrico C2C"][0]
    assert dj.fec_mode == "none"
    assert STANDARD_PROFILE_META[
        "P802.3dj (draft) — 200G/lane · elettrico C2C"]["status"] == "draft"
    assert all(not cfg.validate() for cfg, _ in STANDARD_PROFILES.values())


def test_education_catalog_is_bilingual_and_covers_chain():
    from labpro.education import TOPICS_BY_ID
    required = {"stimulus", "fec", "serpll", "tx", "channel", "optical",
                "rxfe", "ctle", "adc", "timing", "eq", "scope", "bert",
                "l2", "standards"}
    assert required <= set(TOPICS_BY_ID)
    for topic in TOPICS_BY_ID.values():
        for field in ("title", "idea", "observe", "experiment", "limits"):
            assert topic[field]["it"] and topic[field]["en"]


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
    assert "verification_before" in steps[-1]
    if not steps[-1]["accepted"]:
        assert new_cfg == cfg


def test_ctle_variable_topology_changes_real_datapath():
    from serdes_sim.blocks.receiver import ctle_response
    f = np.array([0.0, 10e9, 40e9])
    h12 = ctle_response(f, zeros_hz=(8e9,), poles_hz=(24e9, 55e9))
    h23 = ctle_response(f, zeros_hz=(8e9, 18e9),
                        poles_hz=(24e9, 45e9, 75e9))
    assert np.isclose(h12[0], 1.0) and np.isclose(h23[0], 1.0)
    assert not np.allclose(h12, h23)
    cfg = LinkConfig(ctle_zeros_hz=(8e9, 18e9),
                     ctle_poles_hz=(24e9, 45e9, 75e9))
    assert not cfg.validate()
    r = simulate(cfg, depth="light")
    assert r.link_up and np.all(np.isfinite(r.receiver.v_ctle_v))


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
    assert b.latest is None


# --- SSPRQ-like e CMIS-lite --------------------------------------------------

def test_ssprq_like_pattern_runs_and_stresses():
    r = simulate(LinkConfig(pattern="ssprq_like"), depth="light")
    assert r.link_up
    # il pattern stress non deve essere banale: occupa tutti i livelli
    assert (r.occupancy > 0).all()


def test_ssprq_with_fec_rejected():
    assert LinkConfig(pattern="ssprq_like", fec_mode="kp4").validate()


def test_cmis_states_follow_bench():
    from labpro.paneldata import cmis_panel
    up = cmis_panel(simulate(LinkConfig(**GOOD_LINK), depth="light"),
                    LinkConfig(**GOOD_LINK))
    assert up["datapath_state"] == "DataPathActivated"
    assert not up["lane_flags"][0]["rx_lol"]
    down_cfg = LinkConfig(laser_dbm=-6.0)
    dn = cmis_panel(simulate(down_cfg, depth="light"), down_cfg)
    assert dn["datapath_state"] != "DataPathActivated"
    assert dn["lane_flags"][0]["rx_lol"] or dn["lane_flags"][0]["rx_los"]
    assert len(up["dom"]) == 5 and len(up["vdm"]) >= 3
