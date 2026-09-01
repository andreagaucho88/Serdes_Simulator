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


def test_extended_ctle_sweep_moves_the_zero_consumed_by_datapath():
    """Regression: lo sweep storico dello zero non deve diventare morto
    quando il CTLE usa liste 2Z/3P."""
    cfg = LinkConfig(ctle_zeros_hz=(7e9, 18e9),
                     ctle_poles_hz=(24e9, 45e9, 75e9))
    rows = sweep(cfg, "ctle_zero_hz", [5e9, 11e9], seed=17)
    assert [r["effective_value"] for r in rows] == [5e9, 11e9]
    assert rows[0]["BER_FSE_DFE"] != rows[1]["BER_FSE_DFE"]


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


def test_multistream_generator_and_analyzer():
    """Xena-style: 3 stream round-robin con id/sequence/size propri; un bit
    corrotto viene attribuito allo stream giusto."""
    from serdes_sim.blocks import ethernet as eth
    bits, nfr, _ = eth.build_stream_bits(120000, 256, ipg_bytes=12, streams=3)
    a = eth.analyze_stream_bits(bits, 256, window_s=1e-6, streams=3)
    assert a.frames_ok == a.frames_expected and a.frames_lost == 0
    assert len(a.per_stream) == 3
    bad = bits.copy()
    bad[9000] ^= 1                      # dentro un frame dello stream 0
    a2 = eth.analyze_stream_bits(bad, 256, window_s=1e-6, streams=3)
    hit = [st for st in a2.per_stream if st.fcs_bad]
    assert len(hit) == 1 and sum(st.fcs_bad for st in a2.per_stream) == 1


def test_multistream_end_to_end():
    r = simulate(LinkConfig(pattern="eth", l2_streams=3, n_symbols=24000,
                            **GOOD_LINK), seed=11, depth="light")
    assert r.link_up and r.l2 is not None and r.l2.per_stream
    assert len(r.l2.per_stream) == 3
    assert LinkConfig(l2_streams=9).validate()


def test_chamber_profile_and_die_lag():
    import time
    from serdes_sim.livebench import LiveBench
    b = LiveBench(LinkConfig(**GOOD_LINK))
    b.set_chamber(on=True, mode="soak", t_max=85.0, tau_s=2.0)
    # forma d'onda: ciclo triangolare simmetrico
    b.chamber["mode"] = "cycle"
    b._chamber_t0 = 1000.0
    b.chamber["period_s"] = 100.0
    b.chamber["t_min"], b.chamber["t_max"] = -10.0, 90.0
    assert b._chamber_target(1000.0) == pytest.approx(-10.0)
    assert b._chamber_target(1025.0) == pytest.approx(40.0)   # metà salita
    assert b._chamber_target(1050.0) == pytest.approx(90.0)   # picco
    assert b._chamber_target(1075.0) == pytest.approx(40.0)   # discesa
    # integrazione: il die insegue con lag e la BER si muove col profilo
    b.chamber.update(mode="soak", t_max=85.0)
    b._chamber_t0 = time.time()
    b.start(); time.sleep(2.5); b.stop()
    snap = b.snapshot()
    temps = [t for t in snap["hist"]["temp_c"] if t is not None]
    assert len(temps) >= 2 and temps[-1] > temps[0] + 5.0
    assert snap["chamber"]["on"] and snap["chamber"]["die_t"] > 30.0


def test_dark_current_arrhenius():
    f25 = LinkConfig().pvt_factors["dark"]
    f125 = LinkConfig(pvt_temp_c=125.0).pvt_factors["dark"]
    fm40 = LinkConfig(pvt_temp_c=-40.0).pvt_factors["dark"]
    assert f25 == pytest.approx(1.0)
    assert 1500 < f125 < 3500          # raddoppio ogni ~9 °C
    assert fm40 < 0.01


def test_service_disruption_measured():
    import time
    from serdes_sim.livebench import LiveBench
    b = LiveBench(LinkConfig(**GOOD_LINK))
    b.start(); time.sleep(1.2)
    b.disrupt()
    time.sleep(2.5); b.stop()
    snap = b.snapshot()
    assert snap["sync_losses"] >= 1
    assert snap["last_disruption_ms"] is not None
    assert 100 < snap["last_disruption_ms"] < 5000


def test_ont_measured_analog_gd():
    from serdes_sim.engine import l2_ont_report
    cfg = LinkConfig(pattern="eth", causal_filters=True,
                     channel_delay_ps=40.0, **GOOD_LINK)
    out = l2_ont_report(cfg, ipg_grid=(12,))
    # con filtri causali il GD analogico misurato è > del solo canale
    assert 0.04 <= out["latency_measured_analog_ns"] <= 0.5


def test_rx_pvt_corners_order_and_identity():
    """PVT del ricevitore: TT/0%/25°C = identità (fattori 1.0, baseline
    intatta); il worst case SS+caldo+VDD basso peggiora la BER, FF+freddo
    la migliora — l'ordine fisico di una qualifica RX."""
    cfgs = dict(fiber_km=0.0, chirp_alpha=0.0, channel_il_nyquist_db=12.0)
    f = LinkConfig().pvt_factors
    assert f == {"bw": 1.0, "noise": 1.0, "mismatch": 1.0,
                 "dark": 1.0, "cdr_gain": 1.0}
    tt = simulate(LinkConfig(**cfgs), seed=7, depth="light")
    ss = simulate(LinkConfig(pvt_process="ss", pvt_temp_c=125.0,
                             pvt_vdd_pct=-10.0, **cfgs), seed=7,
                  depth="light")
    ff = simulate(LinkConfig(pvt_process="ff", pvt_temp_c=-40.0, **cfgs),
                  seed=7, depth="light")
    assert ss.ber_post_dfe > tt.ber_post_dfe > ff.ber_post_dfe
    assert LinkConfig(pvt_process="xx").validate()
    assert LinkConfig(pvt_temp_c=200.0).validate()


def test_acquisition_batch_frozen_per_seed():
    """CONGELAMENTO batch per seed (roadmap punto 1): questi numeri sono
    l'ancora deterministica del banco sulla config default. Se una modifica
    al motore li cambia, il cambiamento va dichiarato e i valori aggiornati
    QUI, consapevolmente."""
    from serdes_sim.engine import acquisition_batch
    rows = acquisition_batch(LinkConfig(), seeds=(500283, 500354))
    frozen = {
        500283: dict(ber=2.005616e-02, q_min=1.855421, snr_db=12.742197,
                     tie_rms_ps=4.379432),
        500354: dict(ber=2.085840e-02, q_min=1.936855, snr_db=12.581927,
                     tie_rms_ps=4.392091),
    }
    for row in rows:
        exp = frozen[row["seed"]]
        assert row["link_up"]
        for key, val in exp.items():
            assert row[key] == pytest.approx(val, rel=1e-4), (row["seed"], key)


def test_tdecq_golden_vectors():
    """TDECQ (struttura clause 121.8.5.3) contro vettori sintetici
    indipendenti dalla catena: (a) waveform PAM4 ideale → TDECQ al floor
    dello strumento reale (BT4+doppia fase+Ceq≥1 ⇒ ~1 dB, NON 0); (b)
    rumore per-UI crescente → TDECQ strettamente crescente; (c) OMA
    misurata entro il 7% dal vero."""
    from serdes_sim.blocks.metrics import tdecq_report
    from serdes_sim.blocks.stimulus import PAM4_GRAY, generate_stimulus
    rng = np.random.default_rng(5)
    sym = generate_stimulus(6000, 13, PAM4_GRAY)
    p_lin = np.interp(sym, PAM4_GRAY.levels_array,
                      np.linspace(0.2, 1.2, 4))
    wave = np.repeat(p_lin, 16)
    r0 = tdecq_report(wave, sym, PAM4_GRAY, 16, 56e9, 56e9 * 16)
    assert r0["tdecq_db"] is not None
    assert 0.8 <= r0["tdecq_db"] <= 1.6
    assert abs(r0["oma_outer"] - 1.0) < 0.07
    prev = r0["tdecq_db"]
    for frac in (0.3, 0.5, 0.7):
        noisy = wave + np.repeat(
            rng.normal(0, frac * r0["sigma_ideal"], len(sym)), 16)
        r = tdecq_report(noisy, sym, PAM4_GRAY, 16, 56e9, 56e9 * 16)
        assert r["tdecq_db"] > prev
        prev = r["tdecq_db"]


def test_tdecq_on_real_chain_and_dispersion():
    from serdes_sim.blocks.metrics import tdecq_report
    from serdes_sim.config import STANDARD_PROFILES
    dr4 = [v[0] for k, v in STANDARD_PROFILES.items() if "DR4" in k][0]
    s0 = simulate(dr4, seed=42, depth="light")
    r0 = tdecq_report(s0.optical.P_fiber_w, s0.pam4_symbols, s0.spec,
                      dr4.analog_sps, dr4.symbol_rate_hz, dr4.fs_analog_hz)
    assert r0["tdecq_db"] is not None and 1.0 < r0["tdecq_db"] < 6.0
    # dispersione seria → TDECQ peggiora o fallisce
    bad = dr4.with_updates(fiber_km=4.0, wavelength_nm=1550.0,
                           dispersion_ps_nm_km=17.0)
    s1 = simulate(bad, seed=42, depth="light")
    r1 = tdecq_report(s1.optical.P_fiber_w, s1.pam4_symbols, s1.spec,
                      bad.analog_sps, bad.symbol_rate_hz, bad.fs_analog_hz)
    assert r1["tdecq_db"] is None or r1["tdecq_db"] > r0["tdecq_db"]


def test_tdecq_reference_receiver_contract():
    """Il reference RX usa finestre di clause, tap a DC unitaria e Ceq
    integrato sul rumore sagomato dal BT4."""
    from scipy import signal
    from serdes_sim.blocks.metrics import (_tdecq_noise_enhancement,
                                           tdecq_report)
    from serdes_sim.blocks.stimulus import PAM4_GRAY, generate_stimulus

    sps = 16
    wn = 0.5 * 56e9 / (56e9 * sps / 2)
    b, a = signal.bessel(4, wn, btype="low", norm="mag")
    assert _tdecq_noise_enhancement([0, 0, 1, 0, 0], b, a, sps) \
        == pytest.approx(1.0, abs=1e-12)

    sym = generate_stimulus(6000, 13, PAM4_GRAY)
    power = np.repeat(np.interp(sym, PAM4_GRAY.levels_array,
                                np.linspace(0.2, 1.2, 4)), sps)
    report = tdecq_report(power, sym, PAM4_GRAY, sps, 56e9, 56e9 * sps)
    assert report["tap_sum"] == pytest.approx(1.0, abs=1e-12)
    assert report["histogram_centers_ui"] == [0.45, 0.55]
    assert report["histogram_width_ui"] == pytest.approx(0.04)
    assert report["ceq_method"].endswith("(121-9)")


def test_dr4_versioned_procedure_closes_full_physical_chain():
    """Golden della procedura P0: SSPRQ completo, due estremi di
    dispersione e catena TX→fibra→RX→DSP. Il profilo rappresentativo attuale
    chiude il link ma fallisce onestamente il limite TDECQ del modello."""
    from serdes_sim.procedures import (DR4_TDECQ_V1,
                                       dr4_dispersion_bounds_ps_nm,
                                       run_dr4_tdecq_e2e)

    dmin, dmax = dr4_dispersion_bounds_ps_nm(1310.0)
    assert dmin == pytest.approx(-0.93, abs=1e-12)
    assert dmax == pytest.approx(+0.80, abs=1e-12)
    report = run_dr4_tdecq_e2e(seed=500283)
    assert report["procedure"]["version"] == DR4_TDECQ_V1.version
    assert report["compliance_status"] == "NOT ASSESSED"
    assert not report["uncertainty_complete"]
    assert len(report["cases"]) == 2
    assert all(c["pattern_exact"] and c["link_up"]
               and c["physical_checks_pass"] for c in report["cases"])
    assert all(c["ber_post_dfe"] == 0.0 for c in report["cases"])
    values = [c["tdecq"]["tdecq_db"] for c in report["cases"]]
    assert values[1] > values[0]
    assert report["worst_tdecq_db"] == pytest.approx(4.33479, abs=0.03)
    assert report["numerical_uncertainty_db"] == pytest.approx(0.10, abs=0.02)
    assert report["guarded_tdecq_db"] == pytest.approx(4.43795, abs=0.04)
    assert report["model_status"] == "FAIL"
    status = {s["id"]: s["status"] for s in report["steps"]}
    assert (status["pattern"] == status["channel"]
            == status["channel_loss"] == status["e2e"] == "PASS")
    assert status["calibration"] == status["numeric_uncertainty"] == "PASS"
    assert status["tdecq_limit"] == "FAIL"
    assert status["reflection"] == status["uncertainty"] == "WARN"


def test_fec_codeword_interleaving_splits_bursts():
    """Il motivo per cui lo standard interleava: un burst di 24 simboli RS
    contigui sulla linea uccide un codeword (t=15) senza interleaving, ma
    con depth 2 si divide 12/12 e viene corretto."""
    from serdes_sim.blocks import fec
    rng = np.random.default_rng(3)
    payload = rng.integers(0, 2, 4 * fec.KP4.k * fec.GF_M).astype(np.uint8)
    coded = fec.encode_stream(payload, fec.KP4, 4)
    burst_sym = 24
    start_bit = 5 * fec.GF_M          # dentro il primo gruppo
    for depth, expect_unc in ((1, 1), (2, 0)):
        line = fec.interleave_symbols(coded, fec.KP4, depth)
        hit = line.copy()
        hit[start_bit:start_bit + burst_sym * fec.GF_M] ^= 1
        rx = fec.deinterleave_symbols(hit, fec.KP4, depth)
        tx = fec.deinterleave_symbols(line, fec.KP4, depth)
        res = fec.decode_stream(rx, tx, fec.KP4, 4)
        assert res.frames_uncorrectable == expect_unc, depth
        if depth == 2:
            assert res.post_fec_ber == 0.0
            assert max(res.errors_per_frame) <= 15


def test_fec_interleave_roundtrip_and_e2e():
    from serdes_sim.blocks import fec
    rng = np.random.default_rng(1)
    bits = rng.integers(0, 2, 4 * 5440 + 123).astype(np.uint8)
    for d in (2, 4):
        rt = fec.deinterleave_symbols(
            fec.interleave_symbols(bits, fec.KP4, d), fec.KP4, d)
        assert np.array_equal(rt, bits)
    r = simulate(LinkConfig(fec_mode="kp4", fec_interleave=2,
                            n_symbols=20000, **GOOD_LINK),
                 seed=7, depth="light")
    fl = r.fec_link
    assert fl is not None and fl.n_frames % 2 == 0
    assert fl.frames_uncorrectable == 0 and fl.post_fec_ber == 0.0


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


def test_all_standard_profiles_represent_working_links():
    """Un profilo di standard PUBBLICATO deve rappresentare un link che
    funziona: link su, e FEC che corregge (o BER bassa dove il FEC è
    esterno). Audit richiesto dall'utente: prima di questo test 6 profili
    su 17 giravano sopra soglia (TIA a Z_T fissa che schiacciava il
    livello alto PAM4 → introdotto il VGA da ROSA)."""
    from serdes_sim.config import STANDARD_PROFILES
    for name, (cfg, _desc) in STANDARD_PROFILES.items():
        r = simulate(cfg, seed=42, depth="light")
        assert r.link_up, f"{name}: LINK DOWN"
        if r.fec_link is not None:
            assert r.fec_link.frames_uncorrectable == 0, name
            assert r.fec_link.post_fec_ber == 0.0, name
        else:
            assert r.ber_post_dfe < 5e-3, f"{name}: BER {r.ber_post_dfe:.1e}"


def test_vga_tia_no_level_crush_at_high_power():
    """Alta potenza ottica: il VGA del TIA riduce Z_T invece di schiacciare
    il livello PAM4 alto contro le rail (q_top crollava a 0.2)."""
    from serdes_sim.config import STANDARD_PROFILES
    dr4 = [v[0] for k, v in STANDARD_PROFILES.items() if "DR4" in k][0]
    r = simulate(dr4.with_updates(laser_dbm=6.0), seed=42, depth="light")
    assert r.link_up
    qs = r.snr_dfe["q_per_eye"]
    # gli occhi devono restare comparabili (niente crush asimmetrico)
    assert min(qs) > 0.5 * max(qs)


def test_autoneg_priority_follows_data_rate():
    from serdes_sim.blocks.autoneg import resolve
    # 40GBASE-KR4 (40G) batte 25GBASE-KR/CR (25G)
    assert resolve(["A10", "A3"], ["A10", "A3"])["hcd"] == "A3"
    # 100GBASE-CR10 (100G totali) batte 50GBASE-KR (50G)
    assert resolve(["A13", "A5"], ["A13", "A5"])["hcd"] == "A5"
    # 200GBASE-KR4 batte 100GBASE-KR1
    assert resolve(["A16", "A15"], ["A16", "A15"])["hcd"] == "A15"


def test_lt_holdout_guards_against_overfit():
    from serdes_sim.engine import anlt_session
    out = anlt_session(LinkConfig(**GOOD_LINK), lt_rounds=1, lt_step=0.03)
    h = out["lt"]["holdout"]
    assert isinstance(h["accepted"], bool)
    if not h["accepted"]:
        # rifiutato → i tap del banco restano quelli di partenza
        assert tuple(out["cfg_after"].tx_ffe_taps) == \
            LinkConfig(**GOOD_LINK).tx_ffe_taps


def test_bt4_reference_filter_and_sndr():
    from labpro import paneldata
    cfg = LinkConfig(**GOOD_LINK)
    sim = simulate(cfg, seed=11, depth="light")
    m_off = paneldata.eye_measures(sim, cfg, node="driver")
    m_bt = paneldata.eye_measures(sim, cfg, node="driver",
                                  ref_filter="bt4_05")
    # il BT4 a 0.5·Bd taglia banda: rise time più lento
    assert m_bt["t_rise_ps"] > m_off["t_rise_ps"]
    # SNDR con fit lineare: al driver (pulito) è alto, dopo il canale scende
    m_ch = paneldata.eye_measures(sim, cfg, node="vctle")
    assert m_off["sndr_db"] > 35.0
    assert m_ch["sndr_db"] < m_off["sndr_db"]


def test_optical_p_levels_monotone_dbm():
    from labpro import paneldata
    cfg = LinkConfig(**GOOD_LINK)
    sim = simulate(cfg, seed=11, depth="light")
    m = paneldata.eye_measures(sim, cfg, node="pfiber")
    pl = m["p_levels_dbm"]
    assert len(pl) == 4 and all(a < b for a, b in zip(pl, pl[1:]))
    assert -20 < pl[0] < pl[-1] < 5


def test_pd_square_law():
    hi = simulate(LinkConfig(laser_dbm=3.0, **GOOD_LINK), seed=5,
                  depth="light")
    lo = simulate(LinkConfig(laser_dbm=0.0, **GOOD_LINK), seed=5,
                  depth="light")
    # sulla CORRENTE del PD (prima del VGA del TIA, che normalizza)
    ratio_db = 20 * np.log10(np.std(hi.receiver.i_pd_signal_a)
                             / np.std(lo.receiver.i_pd_signal_a))
    assert abs(ratio_db - 6.0) < 0.8   # -3 dB ottici = -6 dB elettrici


def test_cd_fading_null_matches_theory():
    """Primo nullo della risposta IM su fibra dispersiva:
    f = sqrt(c / (2 λ² D L)) — 19.2 GHz a 10 km / 1550 nm."""
    from scipy import signal as sp_sig
    cfg = LinkConfig(fiber_km=10.0, chirp_alpha=0.0,
                     channel_il_nyquist_db=6.0, wavelength_nm=1550.0,
                     dispersion_ps_nm_km=17.0, fiber_gamma_w_inv_km=0.0,
                     pmd_ps_sqrt_km=0.0)
    sim = simulate(cfg, seed=5, depth="light")
    fs = cfg.fs_analog_hz
    pin = sim.optical.P_mzm_w - np.mean(sim.optical.P_mzm_w)
    pout = sim.optical.P_fiber_w - np.mean(sim.optical.P_fiber_w)
    f, Pi = sp_sig.welch(pin, fs=fs, nperseg=8192)
    _, Po = sp_sig.welch(pout, fs=fs, nperseg=8192)
    H = Po / np.maximum(Pi, 1e-30)
    mask = (f > 2e9) & (f < 28e9)
    f_null = f[mask][np.argmin(H[mask])]
    theory = np.sqrt(3e8 / (2 * (1.55e-6) ** 2 * 17e-6 * 1e4))
    assert abs(f_null - theory) / theory < 0.15


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


def test_clause93a_package_equations_and_gaussian_golden():
    """Golden vectors calcolabili a mano per il nucleo COM.

    A package length of zero is an identity.  With Gaussian noise only,
    A_ni=Q^-1(DER0)*sigma and COM=20log10(A_s/A_ni).
    """
    from scipy.stats import norm
    from serdes_sim.blocks.com import margin_from_components, package_s21

    f = np.array([-53.125e9, 0.0, 53.125e9])
    assert np.allclose(package_s21(f, 0.0), 1.0)
    out = margin_from_components(0.100, 0.010, der0=1e-4)
    expected_ani = norm.isf(1e-4) * 0.010
    assert out["a_ni_v"] == pytest.approx(expected_ani, rel=1e-10)
    assert out["com_db"] == pytest.approx(
        20 * np.log10(0.100 / expected_ani), rel=1e-10)


def test_clause93a_com_is_profile_scoped_and_never_claims_compliance():
    from serdes_sim.blocks.com import com_report
    from serdes_sim.config import STANDARD_PROFILES

    optical = com_report(LinkConfig())
    assert not optical["applicable"]
    assert optical["model_result"] == "NOT APPLICABLE"

    kr1 = STANDARD_PROFILES[
        "IEEE 802.3ck — 100GBASE-KR1 · backplane elettrico"][0]
    out = com_report(kr1)
    assert out["applicable"] and out["normative"] is False
    assert out["compliance_result"] == "NOT ASSESSED"
    assert out["threshold_db"] == 3.0 and out["parameters"]["der0"] == 1e-4
    assert len(out["package_cases"]) == 2
    assert all(np.isfinite(r["com_db"]) for r in out["package_cases"])
    assert out["com_db"] == min(r["com_db"] for r in out["package_cases"])
    assert out["worst_case"]["peak_isi_at_der_mv"] >= 0


def test_every_measure_has_an_explicit_standards_contract():
    from serdes_sim.standards import measurement_contracts

    rows = measurement_contracts(LinkConfig())
    ids = {r["id"] for r in rows}
    assert {"com", "tdecq", "sndr", "rlm", "optical_levels",
            "eye_opening", "jitter", "ber", "fec", "jtol", "traffic"} <= ids
    assert all(r["standard"] and r["clause"] and r["reference_plane"]
               for r in rows)
    # No partial/proxy measurement may emit a normative verdict.
    assert all(r["compliance"] == "not-assessed" for r in rows)


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


# --- SSPRQ bit-exact, pattern editor e CMIS-lite -----------------------------

def test_ssprq_exact_public_clause120_vector():
    """Golden vector: confronto sull'INTERO periodo pubblico IEEE, non un prefix."""
    import hashlib
    from serdes_sim.blocks.ssprq_data import (SSPRQ_PERIOD_SYMBOLS,
                                               SSPRQ_SYMBOL_SHA256)
    from serdes_sim.blocks.stimulus import ssprq_symbol_indices
    symbols = ssprq_symbol_indices()
    assert len(symbols) == SSPRQ_PERIOD_SYMBOLS == 65535
    assert hashlib.sha256(symbols.tobytes()).hexdigest() == SSPRQ_SYMBOL_SHA256
    assert np.bincount(symbols, minlength=4).tolist() == [15215, 17553, 17552, 15215]
    repeated = ssprq_symbol_indices(SSPRQ_PERIOD_SYMBOLS + 7)
    assert np.array_equal(repeated[-7:], symbols[:7])


def test_ssprq_bits_reproduce_official_pam4_symbols():
    from serdes_sim.blocks.stimulus import (PAM4_GRAY, ssprq_bits,
                                            ssprq_symbol_indices,
                                            symbols_from_bits)
    bits = ssprq_bits(2 * 4096, PAM4_GRAY)
    mapped = symbols_from_bits(bits, PAM4_GRAY)
    expected = PAM4_GRAY.levels_array[ssprq_symbol_indices(4096)]
    assert np.array_equal(mapped, expected)


def test_ssprq_exact_runs_and_requires_clause_mapping():
    r = simulate(LinkConfig(pattern="ssprq"), depth="light")
    assert (r.occupancy > 0).all()
    assert LinkConfig(pattern="ssprq", modulation="NRZ").validate()
    assert LinkConfig(pattern="ssprq", pam4_mapping="binary").validate()
    assert LinkConfig(pattern="ssprq", fec_mode="kp4").validate()


def test_custom_hex_pattern_is_msb_first_cyclic_and_validated():
    from serdes_sim.blocks.stimulus import custom_hex_bits, normalize_custom_hex
    assert normalize_custom_hex("0xA5_c3:00") == "A5C300"
    assert custom_hex_bits("A5", 12).tolist() == [1, 0, 1, 0, 0, 1, 0, 1,
                                                     1, 0, 1, 0]
    assert LinkConfig(custom_pattern_hex="ABC").validate()
    assert LinkConfig(custom_pattern_hex="ZZ").validate()
    assert LinkConfig(pattern="custom_hex", fec_mode="kp4").validate()
    r = simulate(LinkConfig(pattern="custom_hex",
                            custom_pattern_hex="1B1BE4E4"), depth="light")
    assert len(r.tx_bits) == 2 * r.cfg.n_symbols

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


# --- audit fisico/UI severo -------------------------------------------------

def test_control_help_covers_every_engine_knob_and_visible_param():
    """Un nuovo campo fisico non puo comparire senza spiegazione IT/EN e
    piano di riferimento; vale anche per ogni parametro esposto dalla UI."""
    import re
    from dataclasses import fields
    from labpro.control_help import CONTROL_HELP

    expected = {f.name for f in fields(LinkConfig)}
    assert set(CONTROL_HELP) == expected
    for name, item in CONTROL_HELP.items():
        assert item["it"] and item["en"] and item["block"] and item["plane"], name
        assert item["observe_it"] and item["observe_en"], name
        assert item["verify_it"] and item["verify_en"], name
        assert item["boundary_it"] and item["boundary_en"], name

    source = (Path(__file__).resolve().parent.parent /
              "labpro/static/app.js").read_text(encoding="utf-8")
    params = source[source.index("const PARAMS = {"):
                    source.index("const PARAM_EN")]
    visible = set(re.findall(r"^\s{2}([a-z][a-z0-9_]*):", params,
                             flags=re.MULTILINE))
    assert visible <= set(CONTROL_HELP), sorted(visible - set(CONTROL_HELP))


def test_every_declared_ui_action_has_a_rich_help_contract():
    """Ogni bottone operativo marcato nella UI deve avere un contratto
    bilingue: effetto, piano, osservabile, confine e stato/API coinvolti."""
    import re
    from labpro.action_help import ACTION_HELP

    root = Path(__file__).resolve().parent.parent
    source = ((root / "labpro/static/app.js").read_text(encoding="utf-8")
              + (root / "labpro/static/index.html").read_text(encoding="utf-8"))
    used = set(re.findall(r'data-action="([a-z0-9_]+)"', source))
    used |= set(re.findall(r'\.dataset\.action\s*=\s*"([a-z0-9_]+)"', source))
    assert used == set(ACTION_HELP), {
        "used_without_help": sorted(used - set(ACTION_HELP)),
        "dead_help": sorted(set(ACTION_HELP) - used),
    }
    required = {"title_it", "title_en", "block", "plane", "it", "en",
                "observe_it", "observe_en", "boundary_it", "boundary_en"}
    for action, item in ACTION_HELP.items():
        assert required <= set(item), action
        assert all(item[k] for k in required), action
        assert item["endpoint"] or item["mutates"], action


def test_physics_audit_closes_current_record_invariants():
    from labpro.paneldata import physics_audit_panel
    cfg = LinkConfig()
    sim = simulate(cfg, seed=20240731, depth="light")
    audit = physics_audit_panel(sim, cfg)
    assert audit["failed"] == 0 and audit["warnings"] == 0
    assert {row["name"] for row in audit["rows"]} >= {
        "TX FIR H(0)", "TX FIR H(Nyquist)", "Optical field identity",
        "Optical budget closure", "MZM quadrature mean", "Shot-noise PSD",
        "P/N identities", "TIA VGA range", "AGC gain range",
        "CTLE DC gain", "BER counted vs Gaussian levels",
    }


def test_tia_vga_sign_range_and_agc_hard_limit_are_observable():
    hi = simulate(LinkConfig(laser_dbm=9.0), seed=81, depth="light").receiver
    min_zt = 2500.0 * 10 ** (-10.0 / 20)
    assert min_zt <= hi.tia_effective_transimpedance_ohm <= 2500.0
    assert 0 <= hi.tia_vga_atten_db <= 10.0
    assert hi.tia_vga_atten_db == pytest.approx(
        -20 * np.log10(hi.tia_effective_transimpedance_ohm / 2500.0))

    low = simulate(LinkConfig(laser_dbm=-6.0, agc_target_rms_v=0.4),
                   seed=81, depth="light").receiver
    assert low.agc_at_limit
    assert 20 * np.log10(low.agc_gain) == pytest.approx(24.0)
    assert low.agc_unconstrained_gain > low.agc_gain


def test_channel_panel_exposes_pulse_impulse_and_effective_ctle_path():
    from labpro.paneldata import channel_panel
    cfg = LinkConfig(ctle_zeros_hz=(7e9, 18e9),
                     ctle_poles_hz=(24e9, 45e9, 75e9))
    data = channel_panel(simulate(cfg, seed=83, depth="light"), cfg)
    assert len(data["pulse_combo"]) == len(data["impulse_combo"])
    assert len(data["impulse"]) == len(data["impulse_t_ui"])
    assert np.isfinite(data["isi_rms_combo"]) and data["isi_rms_combo"] > 0
    assert "before AGC/clip/ADC" in data["pulse_plane"]


def _poly_mul_mod(a, b, polynomial, degree):
    out = 0
    while b:
        if b & 1:
            out ^= a
        b >>= 1
        a <<= 1
        if a & (1 << degree):
            a ^= polynomial
    return out


def _poly_pow_x(exponent, polynomial, degree):
    result, base = 1, 2
    while exponent:
        if exponent & 1:
            result = _poly_mul_mod(result, base, polynomial, degree)
        base = _poly_mul_mod(base, base, polynomial, degree)
        exponent >>= 1
    return result


def test_prbs_period_balance_and_primitive_polynomial_certificates():
    """I periodi corti sono verificati per enumerazione; PRBS23/31 con il
    certificato algebrico di primitivita, senza allocare miliardi di bit."""
    from serdes_sim.blocks.stimulus import prbs_bits
    polynomials = {
        7: (1 << 7) | (1 << 6) | 1,
        9: (1 << 9) | (1 << 5) | 1,
        11: (1 << 11) | (1 << 9) | 1,
        13: (1 << 13) | (1 << 12) | (1 << 2) | (1 << 1) | 1,
        15: (1 << 15) | (1 << 14) | 1,
        23: (1 << 23) | (1 << 18) | 1,
        31: (1 << 31) | (1 << 28) | 1,
    }
    prime_factors = {
        7: (127,), 9: (7, 73), 11: (23, 89), 13: (8191,),
        15: (7, 31, 151), 23: (47, 178481), 31: (2147483647,),
    }
    for degree, polynomial in polynomials.items():
        period = 2 ** degree - 1
        assert _poly_pow_x(period, polynomial, degree) == 1
        for factor in prime_factors[degree]:
            assert _poly_pow_x(period // factor, polynomial, degree) != 1
        if degree <= 15:
            bits = prbs_bits(degree, 2 * period)
            assert np.array_equal(bits[:period], bits[period:])
            assert int(bits[:period].sum()) == 2 ** (degree - 1)


def test_tx_fir_exact_endpoints_and_panel_report():
    from labpro.paneldata import tx_panel
    cfg = LinkConfig(tx_ffe_taps=(-0.03, -0.2, 0.9, -0.07, 0.01))
    data = tx_panel(simulate(cfg, seed=89, depth="light"), cfg)
    taps = np.asarray(cfg.tx_ffe_taps)
    assert data["h0"] == pytest.approx(float(taps.sum()))
    assert data["hnyquist"] == pytest.approx(
        float(np.sum(taps * (-1.0) ** np.arange(len(taps)))))
    assert len(data["f_norm"]) == len(data["ffe_db"]) == len(data["combined_db"])


def test_channel_il_slider_is_smooth_loss_not_mismatch_ripple():
    from serdes_sim.blocks.channel import channel_response
    ideal_rl = LinkConfig(return_loss_db=120.0)
    total_ideal = -20 * np.log10(abs(channel_response(
        np.asarray([ideal_rl.nyquist_hz]), ideal_rl)[0]))
    assert total_ideal == pytest.approx(ideal_rl.channel_il_nyquist_db,
                                       abs=0.02)
    cfg = LinkConfig(return_loss_db=14.0)
    total = -20 * np.log10(abs(channel_response(
        np.asarray([cfg.nyquist_hz]), cfg)[0]))
    assert abs(total - cfg.channel_il_nyquist_db) > 0.05


def test_tx_clock_stress_calibration_rj_pj_and_ssc():
    from serdes_sim.blocks.tx import tx_clock_tie_ui
    ui_s = LinkConfig().ui_s
    rj_cfg = LinkConfig(tx_rj_rms_fs=1000.0)
    rj = tx_clock_tie_ui(rj_cfg, np.random.default_rng(20240731))
    assert np.std(rj) * ui_s / 1e-15 == pytest.approx(1000.0, rel=0.03)

    pj_cfg = LinkConfig(tx_pj_amp_ui=0.06, tx_pj_freq_mhz=200.0)
    pj = tx_clock_tie_ui(pj_cfg, np.random.default_rng(1))
    freq = np.fft.rfftfreq(len(pj), d=ui_s)
    amp = 2 * np.abs(np.fft.rfft(pj - pj.mean())) / len(pj)
    peak = int(np.argmax(amp[1:]) + 1)
    assert freq[peak] / 1e6 == pytest.approx(200.0, abs=5.0)
    # La FFT corta non e bin-centred: l'ampiezza va stimata al tono noto,
    # altrimenti lo scalloping loss appare falsamente come errore fisico.
    k = np.arange(len(pj))
    omega = 2 * np.pi * pj_cfg.tx_pj_freq_mhz * 1e6 * ui_s
    design = np.column_stack((np.sin(omega * k), np.cos(omega * k),
                              np.ones(len(k))))
    coeff, *_ = np.linalg.lstsq(design, pj, rcond=None)
    fitted_amp = float(np.hypot(coeff[0], coeff[1]))
    assert fitted_amp == pytest.approx(0.06, rel=1e-6)

    ssc_cfg = LinkConfig(tx_ssc_ppm=4000.0, tx_ssc_khz=33.0)
    ssc = tx_clock_tie_ui(ssc_cfg, np.random.default_rng(1))
    measured_ppm = float(np.mean(np.diff(ssc)) * 1e6)
    k = np.arange(ssc_cfg.n_symbols)
    period = 1 / (ssc_cfg.tx_ssc_khz * 1e3)
    frac = ((k / ssc_cfg.symbol_rate_hz) / period) % 1
    tri = np.where(frac < .5, 2 * frac, 2 - 2 * frac)
    expected_ppm = float(np.mean(-ssc_cfg.tx_ssc_ppm * tri[1:]))
    assert measured_ppm == pytest.approx(expected_ppm, abs=1e-9)


def test_full_gaussian_level_ber_matches_counted_baseline():
    sim = simulate(LinkConfig(), seed=20240731, depth="light")
    counted = sim.ber_post_dfe
    gaussian = sim.snr_dfe["ber_gaussian_levels"]
    assert sim.metrics_rows[2]["bit_errors"] >= 30
    assert gaussian == pytest.approx(counted, rel=0.10)
