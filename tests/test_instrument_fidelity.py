"""Veridicità end-to-end della catena strumentale (iterazione 46).

Copre: PCS 64b/66b (block lock a qualunque offset), scheduler/impairment/
workload L2 con identità contabili chiuse, J2/J9 dal tail-fit, fixture DCA
e de-embedding, MPI a coppia di riflessioni, RIN alla sorgente, stressed RX
(SECQ), correlazione golden e la griglia di stress DR4 v1.2.
"""

import numpy as np
import pytest

from serdes_sim.blocks import ethernet as eth
from serdes_sim.blocks import pcs
from serdes_sim.config import STANDARD_PROFILES, LinkConfig
from serdes_sim.engine import simulate

GOOD_LINK = dict(fiber_km=0.0, chirp_alpha=0.0, channel_il_nyquist_db=6.0)
DR4 = "IEEE 802.3bs — 400GBASE-DR4 · 100G/λ ottico 500 m"


def _frames(n=30, size=256):
    body = bytes(range(256)) * (size // 256 + 1)
    return [bytes([0x55] * 7 + [0xD5]) + bytes([i]) + body[:size - 1] for i in range(n)]


# ---------------------------------------------------------------- L1 · PCS
@pytest.mark.parametrize("offset", [0, 1, 17, 65, 66, 131])
def test_pcs_64b66b_block_lock_at_any_bit_offset(offset):
    enc = pcs.encode(_frames(), 12)
    assert enc.n_blocks * pcs.BLOCK_BITS == len(enc.line_bits)
    data, st = pcs.decode(enc.line_bits[offset:], offset)
    assert st.lock and st.sync_header_errors == 0 and not st.hi_ber
    assert st.lock_offset_bits == (-offset) % pcs.BLOCK_BITS
    assert st.first_block_index == (offset + st.lock_offset_bits) // pcs.BLOCK_BITS
    assert st.overhead_pct == pytest.approx(3.125)
    assert st.start_blocks >= 28 and st.terminate_blocks >= 28 and st.idle_blocks >= 28
    # ogni frame intero dopo il primo blocco decodificato è ricostruito byte-exact
    for f in _frames()[2:]:
        assert f in data


def test_pcs_sync_header_monitor_counts_errors_and_hi_ber():
    enc = pcs.encode(_frames(), 12)
    bits = enc.line_bits.copy()
    for b in (5, 9, 40):                       # tre header 01/10 → 00/11
        bits[b * pcs.BLOCK_BITS] ^= 1
    _, st = pcs.decode(bits, 0)
    assert st.lock and st.sync_header_errors == 3 and not st.hi_ber
    for b in range(100, 100 + pcs.HI_BER_THRESHOLD):
        bits[b * pcs.BLOCK_BITS] ^= 1
    _, st = pcs.decode(bits, 0)
    assert st.lock and st.hi_ber and st.sync_header_errors == 3 + pcs.HI_BER_THRESHOLD


# ---------------------------------------------------------------- L2 · MAC
def _eth_cfg(**kw):
    return LinkConfig().with_updates(pattern="eth", **kw)


@pytest.mark.parametrize("coding", ["scrambler", "64b66b"])
@pytest.mark.parametrize("offset", [0, 37, 66, 1000])
def test_l2_loopback_is_exact_for_both_codings_and_any_offset(coding, offset):
    cfg = _eth_cfg(l2_pcs_coding=coding, l2_frame_bytes=256, l2_streams=2)
    bits, sched = eth.build_line_bits(cfg, 120_000)
    a, st, _ = eth.analyze_line_bits(cfg, bits[offset:], sched, offset, window_s=1e-6)
    assert a is not None and a.coding == coding
    assert a.frames_expected > 20
    assert a.frames_ok == a.frames_expected and a.frames_lost == 0
    assert a.frames_fcs_bad == 0 and a.frames_duplicated == 0 and a.frames_out_of_order == 0
    if coding == "64b66b":
        assert st is not None and st.lock and st.sync_header_errors == 0
    else:
        assert st is None


def test_l2_weighted_scheduler_shares_follow_weights():
    cfg = _eth_cfg(l2_scheduler="weighted", l2_streams=3, l2_stream_weights=(4, 2, 1, 1),
                   l2_frame_bytes=128)
    _, sched = eth.build_line_bits(cfg, 200_000)
    counts = np.bincount([f.stream_id for f in sched.frames], minlength=3)
    assert counts[0] / counts[1] == pytest.approx(2.0, abs=0.15)
    assert counts[1] / counts[2] == pytest.approx(2.0, abs=0.2)
    cfg_rr = _eth_cfg(l2_scheduler="round_robin", l2_streams=3, l2_frame_bytes=128)
    _, sched = eth.build_line_bits(cfg_rr, 200_000)
    counts = np.bincount([f.stream_id for f in sched.frames], minlength=3)
    assert max(counts) - min(counts) <= 1
    cfg_imix = _eth_cfg(l2_scheduler="imix", l2_streams=1)
    _, sched = eth.build_line_bits(cfg_imix, 200_000)
    sizes = np.array([f.size_bytes for f in sched.frames])
    assert set(np.unique(sizes)) == {64, 576, 1024}
    assert np.mean(sizes == 64) == pytest.approx(7 / 12, abs=0.08)


def test_l2_impairment_emulator_counters_close_in_loopback():
    cfg = _eth_cfg(l2_drop_pct=5.0, l2_dup_pct=3.0, l2_misorder_pct=2.0, l2_corrupt_pct=2.0,
                   l2_streams=2, l2_frame_bytes=128)
    bits, sched = eth.build_line_bits(cfg, 200_000)
    assert sched.n_dropped > 0 and sched.n_duplicated > 0
    assert sched.n_reordered > 0 and sched.n_corrupted > 0
    a, _, _ = eth.analyze_line_bits(cfg, bits, sched, 0, window_s=1e-6)
    # finestra dell'analyzer (scrambler): 58 bit di burn-in + allineamento
    # al byte, poi byte interi fino alla fine del record
    w0 = 58 + (8 - 58 % 8) % 8
    w1 = w0 + ((len(bits) - w0) // 8) * 8
    win = [f for f in sched.frames if f.line_bit_start >= w0 and f.line_bit_body_end <= w1]
    dropped = sum(1 for f in win if f.dropped)
    corrupted = sum(1 for f in win if f.corrupted and not f.dropped)
    duplicated = sum(1 for f in win if f.duplicate)
    reordered = sum(1 for f in win if f.reordered)
    assert dropped and corrupted and duplicated and reordered
    # identità: attesi = sequenze logiche (drop inclusi, duplicati esclusi)
    assert a.frames_expected == len({(f.stream_id, f.seq) for f in win if not f.duplicate})
    assert a.frames_detected == a.frames_ok + a.frames_fcs_bad
    # persi = solo impairment emulati (drop + FCS bad); nessuna perdita PHY
    assert a.frames_lost == a.lost_emulated == dropped + corrupted
    assert a.lost_phy == 0
    assert a.frames_fcs_bad == a.corrupt_emulated == corrupted
    assert a.frames_duplicated == duplicated
    assert a.frames_out_of_order == reordered
    per = {st.stream_id: st for st in a.per_stream}
    assert sum(st.lost_emulated for st in per.values()) == a.lost_emulated
    assert sum(st.duplicates for st in per.values()) == a.frames_duplicated
    assert sum(st.out_of_order for st in per.values()) == a.frames_out_of_order
    assert sum(st.expected for st in per.values()) == a.frames_expected


@pytest.mark.parametrize("name", sorted(k for k, v in eth.WORKLOADS.items() if v))
def test_workload_profiles_produce_bursts_and_kpis(name):
    prof = eth.WORKLOADS[name]
    cfg = _eth_cfg(l2_workload=name)
    bits, sched = eth.build_line_bits(cfg, 1_500_000)   # storage: burst da 64 frame
    assert sched.workload == name
    sizes = {f.size_bytes for f in sched.frames}
    assert sizes <= {sz for sz, _ in prof["sizes"]}
    a, _, _ = eth.analyze_line_bits(cfg, bits, sched, 0, window_s=1e-6)
    assert a.workload == name and a.frames_ok == a.frames_expected > 0
    if prof["burst_on"]:
        assert any(f.extra_ipg for f in sched.frames)
        assert a.bursts_in_window >= 1 and a.burst_completion_us > 0
        assert a.tail_loss_pct == 0.0
    else:
        assert not any(f.extra_ipg for f in sched.frames)
        assert a.bursts_in_window == 0
    assert sum(a.size_histogram.values()) == a.frames_expected


def test_l2_chain_audit_closes_on_a_good_link():
    """E2E vero: frame → PCS 64b/66b → serializer → canale → RX → FEC → PCS
    → analyzer, con workload, WRR e impairment emulati. Ogni riga di verifica
    della catena deve chiudere."""
    from labpro.paneldata import l2_panel
    cfg = LinkConfig().with_updates(
        pattern="eth", l2_pcs_coding="64b66b", l2_workload="llm_inference",
        l2_scheduler="weighted", l2_stream_weights=(4, 2, 1, 1), l2_streams=3,
        l2_drop_pct=10.0, l2_dup_pct=8.0, l2_corrupt_pct=15.0, n_symbols=65535,
        fec_mode="kp4", **GOOD_LINK)
    sim = simulate(cfg, seed=7, depth="light")
    assert sim.link_up and sim.l1 is not None and sim.l1.lock
    assert sim.l2 is not None and sim.l2.frames_ok > 0
    d = l2_panel(sim, cfg)
    assert d["l1"]["lock"] and d["l1"]["sync_header_errors"] == 0
    assert d["l1"]["overhead_pct"] == pytest.approx(3.125)
    assert d["workload"]["name"] == "llm_inference"
    assert d["frames_lost"] >= d["lost_emulated"] > 0
    assert d["frames_duplicated"] > 0 and d["corrupt_emulated"] > 0
    audit = {row["name"]: row for row in d["audit"]}
    assert len(audit) >= 6
    bad = {k: v for k, v in audit.items() if v["status"] != "PASS"}
    assert not bad, bad
    # il profilo di workload fissa il mix di stream (llm_inference: 2 stream)
    assert len(d["per_stream"]) == eth.WORKLOADS["llm_inference"]["streams"]
    assert d["frames_expected"] >= 30
    assert all(f["fcs_ok"] in (True, False) for f in d["frames"])


# ---------------------------------------------------------------- jitter J2/J9
def test_tail_fit_reports_j2_measured_and_j9_extrapolated():
    from labpro.paneldata import _tie_tail_fit
    rng = np.random.default_rng(5)
    sigma, dj = 0.01, 0.04                     # UI: RJ rms e DJ(δδ) picco-picco
    tie = rng.normal(0, sigma, 40_000) + rng.choice([-dj / 2, dj / 2], 40_000)
    ui_ps = 1e12 / 53.125e9
    fit = _tie_tail_fit(tie, ui_ps)
    assert fit is not None and fit["n_edges"] == 40_000
    assert fit["j2_ber"] == 2.5e-3 and fit["j9_ber"] == 2.5e-10
    j2_theory = (dj + 2 * 2.807 * sigma) * ui_ps
    j9_theory = (dj + 2 * 6.20 * sigma) * ui_ps
    assert fit["j2_ps"] == pytest.approx(j2_theory, rel=0.3)
    assert fit["j2_measured_ps"] == pytest.approx(j2_theory, rel=0.2)
    assert fit["j9_ps"] == pytest.approx(j9_theory, rel=0.3)
    assert fit["j9_ps"] > fit["j2_ps"] > 0


# ---------------------------------------------------------------- DCA fixture
def test_fixture_deembedding_recovers_the_waveform():
    from labpro.paneldata import apply_fixture, deembed_fixture, fixture_response
    cfg = LinkConfig()
    f = np.linspace(0, cfg.fs_analog_hz / 2, 2049)
    h = fixture_response(f, cfg, 6.0)
    nyq = np.argmin(np.abs(f - cfg.symbol_rate_hz / 2))
    assert 20 * np.log10(abs(h[nyq])) == pytest.approx(-6.0, abs=0.05)
    assert abs(h[0]) == pytest.approx(1.0, abs=1e-6)
    rng = np.random.default_rng(1)
    x = np.repeat(rng.choice([-1.0, -1 / 3, 1 / 3, 1.0], 3000), cfg.analog_sps)
    y = apply_fixture(x, cfg, 6.0)
    z = deembed_fixture(y, cfg, 6.0)
    err_fixture = np.std(y - x)
    err_deembed = np.std(z - x)
    assert err_fixture > 0.1 * np.std(x)
    assert err_deembed < 0.25 * err_fixture


# ---------------------------------------------------------------- optics
def test_reflection_pair_mpi_and_rin_at_source_are_visible_in_the_field():
    base = STANDARD_PROFILES[DR4][0]
    s0 = simulate(base, seed=3, depth="light")
    assert s0.optical.reflection_mpi_db is None and s0.optical.laser_rin_rms_pct is None
    s1 = simulate(base.with_updates(optical_return_loss_db=15.0), seed=3, depth="light")
    assert s1.optical.reflection_mpi_db == -30.0
    assert np.std(s1.optical.P_fiber_w - s0.optical.P_fiber_w) > 0
    s2 = simulate(base.with_updates(rin_db_hz=-136.0, rin_at_source=True), seed=3,
                  depth="light")
    assert 3.0 < s2.optical.laser_rin_rms_pct < 15.0
    assert np.std(s2.optical.P_fiber_w - s0.optical.P_fiber_w) > 0
    s3 = simulate(base.with_updates(rin_db_hz=-136.0, rin_at_source=False), seed=3,
                  depth="light")
    assert np.array_equal(s3.optical.P_fiber_w, s0.optical.P_fiber_w)


# ---------------------------------------------------------------- golden
def test_golden_correlation_verdicts_and_validation():
    from serdes_sim.golden import (correlate_golden, synthetic_golden_dataset,
                                   validate_dataset)
    from serdes_sim.procedures import _golden_step
    ds = synthetic_golden_dataset(DR4, n_symbols=4096)
    assert validate_dataset(ds) == []
    r = correlate_golden(ds)
    assert r["ok"] and r["verdict"]["model"] == "PROXY" and r["verdict"]["basis"] == "proxy"
    assert r["compared"] == 3 and r["worst_delta_db"] < 1e-3   # waveform a 5 cifre
    inst = dict(ds, source="instrument", instrument="DCA export")
    inst["reference"] = dict(ds["reference"], tdecq_db=ds["reference"]["tdecq_db"] + 0.1)
    ok = correlate_golden(inst)
    assert ok["verdict"]["model"] == "PASS"
    assert ok["deltas"]["tdecq_db"] == pytest.approx(-0.1, abs=1e-3)
    inst["reference"] = dict(ds["reference"], tdecq_db=ds["reference"]["tdecq_db"] + 1.0)
    bad = correlate_golden(inst)
    assert bad["verdict"]["model"] == "FAIL"
    assert _golden_step(None)["status"] == "NOT_ASSESSED"
    assert _golden_step(None)["basis"] == "blocker"
    assert _golden_step(r)["status"] == "PROXY"
    assert _golden_step(ok)["status"] == "PASS"
    broken = dict(ds, schema="x", symbols=[0, 1, 2])
    probs = validate_dataset(broken)
    assert any("schema" in p for p in probs) and any("symbols" in p for p in probs)
    assert correlate_golden({"schema": "x"})["ok"] is False
    # Validation covers the complete payload, not only a short prefix.
    late_bad_symbol = dict(ds, symbols=list(ds["symbols"]))
    late_bad_symbol["symbols"][-1] = 4
    assert any("0..3" in p for p in validate_dataset(late_bad_symbol))
    assert correlate_golden(late_bad_symbol)["ok"] is False
    bad_wave = dict(ds, waveform_w=list(ds["waveform_w"]))
    bad_wave["waveform_w"][-1] = float("nan")
    assert any("finite" in p for p in validate_dataset(bad_wave))
    bad_ref = dict(ds, reference={"tdecq_db": 3.0, "tolerance_db": -0.1})
    assert any("tolerance" in p for p in validate_dataset(bad_ref))
    bad_opt = dict(ds, optimize="not-an-equalizer")
    assert any("optimize" in p for p in validate_dataset(bad_opt))


# ---------------------------------------------------------------- stressed RX
def test_stressed_receiver_calibrates_to_a_declared_target():
    from serdes_sim.procedures import (STRESSED_RIN_RANGE, STRESSED_RX_FINAL_SYMBOLS,
                                       run_stressed_receiver)
    base = STANDARD_PROFILES[DR4][0]
    r = run_stressed_receiver(base, profile=DR4, target_secq_db=6.0, iters=6)
    assert r["status"] == "ok" and r["target_basis"] == "model"
    assert r["secq_db"] == pytest.approx(6.0, abs=0.5)
    assert STRESSED_RIN_RANGE[0] < r["recipe"]["rin_db_hz"] < STRESSED_RIN_RANGE[1]
    assert r["final_record_symbols"] == STRESSED_RX_FINAL_SYMBOLS
    assert r["rx"]["bits"] > 50_000
    assert r["rx"]["verdict"]["model"] in ("PASS", "MARGINAL", "FAIL")
    status = {s["id"]: s["status"] for s in r["steps"]}
    assert status["calibration"] == "PASS" and status["target"] == "PROXY"
    assert status["si"] == "NOT_ASSESSED" and status["instruments"] == "NOT_ASSESSED"
    assert r["compliance_status"] == "NOT_ASSESSED"
    assert len(r["trail"]) >= 4
    # il TX del profilo da solo eccede il limite del registro: onestà
    r0 = run_stressed_receiver(base, profile=DR4, iters=2)
    assert r0["status"] == "already_above" and r0["target_basis"] == "clause"
    assert r0["target_secq_db"] == 3.4 and r0["model_status"] == "FAIL"
    assert {s["id"]: s["status"] for s in r0["steps"]}["calibration"] == "FAIL"


# ---------------------------------------------------------------- scope of L1/L2
@pytest.mark.parametrize("pattern", ["prbs", "ssprq"])
def test_l1_and_l2_exist_only_with_ethernet_traffic(pattern):
    """PCS 64b/66b, scheduler, workload e impairment vivono SOLO sul pattern
    Ethernet: con PRBS/SSPRQ/clock non esiste né uno stream L1 né un
    analyzer L2, anche se i knob sono impostati."""
    from labpro.paneldata import l2_panel
    cfg = LinkConfig().with_updates(pattern=pattern, l2_pcs_coding="64b66b",
                                    l2_workload="ai_training", l2_drop_pct=5.0,
                                    n_symbols=8191, **GOOD_LINK)
    sim = simulate(cfg, seed=3, depth="light")
    assert sim.l1 is None and sim.l2 is None and sim.l2_schedule is None
    assert not any("PCS" in c["check"] or "L2" in c["check"] for c in sim.checks)
    d = l2_panel(sim, cfg)
    assert d.get("inactive") and not d.get("frames")
    eth_cfg = cfg.with_updates(pattern="eth")
    sim_eth = simulate(eth_cfg, seed=3, depth="light")
    assert sim_eth.l1 is not None and sim_eth.l2 is not None
