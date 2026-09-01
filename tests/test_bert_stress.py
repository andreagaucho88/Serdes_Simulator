"""Error insertion mirata + stressed-eye calibration (iterazione 29).

Chiude la seconda tranche del punto 7: l'inserzione sceglie DOVE cadono i
bit (lane MSB/LSB del PAM4, simboli RS interi) e lo stress si calibra su un
target di apertura d'occhio misurata, come nel flusso reale di un test RX.
"""

import json
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from serdes_sim import LinkConfig                              # noqa: E402
from serdes_sim.engine import (ExperimentCancelled, simulate,  # noqa: E402
                               stressed_eye_calibrate)
from serdes_sim.livebench import LiveBench                       # noqa: E402

CFG = LinkConfig()


# ---------------------------------------------------------------- insertion
def _positions(target, bits=20, **extra):
    r = simulate(CFG.with_updates(err_insert_bits=bits,
                                  err_insert_target=target, **extra),
                 seed=99, depth="light")
    return np.asarray(r.err_positions)


def test_msb_target_hits_only_even_bit_positions():
    # mapper MSB-first: colonna 0 del simbolo PAM4 = posizioni pari
    pos = _positions("msb")
    assert len(pos) == 20 and np.all(pos % 2 == 0)


def test_lsb_target_hits_only_odd_bit_positions():
    pos = _positions("lsb")
    assert len(pos) == 20 and np.all(pos % 2 == 1)


def test_rs_symbol_target_groups_bits_into_aligned_gf_symbols():
    pos = _positions("rs_symbol", bits=20)
    groups = sorted(set(pos // 10))
    assert len(groups) == 2          # 20 bit → 2 simboli GF(2^10) interi
    for g in groups:
        inside = np.sort(pos[pos // 10 == g] % 10)
        assert inside.tolist() == list(range(10)), "gruppo non allineato/completo"


def test_random_target_is_the_default_and_backward_compatible():
    r = simulate(CFG.with_updates(err_insert_bits=20), seed=99, depth="light")
    assert CFG.err_insert_target == "random"
    assert len(r.err_positions) == 20


def test_invalid_target_is_a_validation_problem():
    problems = CFG.with_updates(err_insert_target="a_caso").validate()
    assert any("err_insert_target" in p for p in problems)


# ------------------------------------------------------------- TX output
def test_tx_output_off_mutes_driver_and_drops_link():
    r = simulate(CFG.with_updates(
        tx_output_on=False, tx_diff_noise_mv=20,
        vcm_offset_v=0.2, vcm_noise_mv=10,
        pn_gain_mismatch_pct=10, pn_skew_ps=2),
        seed=42, depth="light")
    assert bool(np.all(r.tx.driver_voltage_v == 0))     # mute elettrico
    assert bool(np.all(r.tx.v_diff_v == 0))             # nessun Vdiff fantasma
    assert np.array_equal(r.tx.vp_v, r.tx.vn_v)         # solo common-mode
    assert float(np.std(r.tx.vcm_v)) > 0                # il CM configurato resta
    assert r.link_up is False                            # niente lock: DOWN vero


def test_tx_output_default_on_is_backward_compatible():
    assert CFG.tx_output_on is True
    r = simulate(CFG, seed=42, depth="light")
    assert r.link_up is True


def test_injection_report_proves_single_physical_rx_and_fec_correction():
    """Errore dopo FEC-encoder → RX fisico → tap pre-FEC → decoder → post."""
    # Canale deliberatamente sotto soglia: qui stiamo provando la correzione
    # causale dei simboli inseriti, non il failure già presente nella baseline
    # ottica stressata del preset di default.
    cfg = CFG.with_updates(fec_mode="kp4", n_symbols=16383,
                           fiber_km=0.0, chirp_alpha=0.0,
                           channel_il_nyquist_db=6.0,
                           err_insert_bits=20,
                           err_insert_target="rs_symbol")
    r = simulate(cfg, seed=99, depth="light")
    assert r.link_up and r.fec_link is not None
    bench = LiveBench(cfg.with_updates(err_insert_bits=0))
    bench.records = 1
    request = {"id": 1, "bits": 20, "burst": False,
               "target": "rs_symbol", "queued_at": 0.0}
    with bench._lock:
        report = bench._finish_injection_locked(request, r)
    assert report["physical_rx_locked"] is True
    assert report["tx_inserted"] == 20
    assert report["pre_fec_errors"] > 0
    assert report["fec_input_errors"] > 0
    assert report["fec_frames_corrected"] >= 1
    assert report["fec_frames_uncorrectable"] == 0
    assert report["post_fec_errors"] == 0
    assert report["post_fec_ber"] == 0.0
    assert bench.capture_bert()[4] == "injection"


def test_livebench_injection_is_single_flight_and_latched():
    bench = LiveBench(CFG)
    # Stato RUN controllato senza avviare il worker: verifica atomica della
    # coda senza una race artificiale del test.
    with bench._lock:
        bench._running = True
    first = bench.inject_errors(10, target="msb")
    assert first["id"] == 1 and first["bits"] == 10
    with pytest.raises(RuntimeError, match="già in corso"):
        bench.inject_errors(10)
    snap = bench.snapshot()
    assert snap["injection"]["pending"]["id"] == first["id"]
    bench.set_config(CFG.with_updates(tx_pj_amp_ui=0.01))
    cancelled = bench.snapshot()["injection"]
    assert cancelled["pending"] is None and cancelled["active"] is None
    assert cancelled["last"]["id"] == first["id"]
    assert cancelled["last"]["status"] == "discarded_config_change"
    with bench._lock:
        bench._running = False


def test_livebench_keeps_measured_injection_after_newer_physical_record():
    """E2E reale del bug UI: il record N+1 non cancella la misura one-shot."""
    cfg = CFG.with_updates(fec_mode="kp4", fiber_km=0.0, chirp_alpha=0.0,
                           channel_il_nyquist_db=6.0)
    bench = LiveBench(cfg, seed0=710_000)
    bench.start()
    try:
        deadline = time.monotonic() + 20.0
        while bench.snapshot()["records"] < 1 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert bench.snapshot()["records"] >= 1

        ticket = bench.inject_errors(20, target="rs_symbol")
        last = None
        while time.monotonic() < deadline:
            last = bench.snapshot()["injection"]["last"]
            if last is not None and last["id"] == ticket["id"]:
                break
            time.sleep(0.05)
        assert last is not None and last["status"] == "measured"
        assert last["physical_rx_locked"] is True
        assert last["tx_inserted"] == 20
        assert last["fec_input_errors"] > 0
        assert last["fec_frames_corrected"] > 0
        assert last["post_fec_errors"] == 0

        injection_record = last["record"]
        while (bench.snapshot()["records"] <= injection_record
               and time.monotonic() < deadline):
            time.sleep(0.05)
        cfg_latched, sim, _, _, source, persisted = bench.capture_bert()
        assert cfg_latched == cfg and source == "injection"
        assert persisted["id"] == ticket["id"]
        assert sim.seed == persisted["seed"]
        assert bench.snapshot()["records"] > injection_record
    finally:
        bench.stop()


# ------------------------------------------------------------- stress cal
@pytest.mark.slow
def test_stress_cal_finds_recipe_just_above_target():
    d = stressed_eye_calibrate(CFG, target_q=1.2)
    assert d["status"] == "ok"
    assert 0 < d["recipe"]["tx_pj_amp_ui"] <= 0.35
    # ricetta conservativa: Q appena SOPRA il target, sotto il Q senza stress
    assert d["target_q"] < d["recipe"]["q"] < d["q_unstressed"]
    assert d["recipe"]["upper_bound_ui"] >= d["recipe"]["tx_pj_amp_ui"]
    assert len(d["points"]) >= 4


def test_stress_cal_declares_already_below_without_searching():
    d = stressed_eye_calibrate(CFG, target_q=9.0)
    assert d["status"] == "already_below"
    assert d["recipe"] is None
    assert len(d["points"]) == 1     # una sola misura, niente bisezione


def test_stress_cal_cancel_token_aborts_immediately():
    evt = threading.Event()
    evt.set()
    t0 = time.perf_counter()
    with pytest.raises(ExperimentCancelled):
        stressed_eye_calibrate(CFG, target_q=1.2, cancel=evt)
    assert time.perf_counter() - t0 < 3.0


# ------------------------------------------------------------------- HTTP
from tornado.testing import AsyncHTTPTestCase                  # noqa: E402

from labpro import server                                      # noqa: E402


class StressApiTest(AsyncHTTPTestCase):
    def setUp(self):
        self._bench_before = server.BENCH
        server.BENCH = LiveBench(CFG)
        with server.BENCH._lock:
            server.BENCH._running = True
        super().setUp()

    def tearDown(self):
        super().tearDown()
        server.BENCH = self._bench_before

    def get_app(self):
        return server.make_app()

    def test_invalid_target_q_is_json_400(self):
        resp = self.fetch("/api/experiment/stresscal", method="POST",
                          body=json.dumps({"target_q": 99}))
        assert resp.code == 400
        assert "target_q" in json.loads(resp.body)["error"]

    def test_inject_rejects_unknown_target(self):
        resp = self.fetch("/api/inject", method="POST",
                          body=json.dumps({"bits": 10, "target": "boh"}))
        assert resp.code == 400
        assert "target" in json.loads(resp.body)["error"]

    def test_inject_accepts_targeted_mode(self):
        resp = self.fetch("/api/inject", method="POST",
                          body=json.dumps({"bits": 10, "target": "rs_symbol"}))
        assert resp.code == 200
        d = json.loads(resp.body)
        assert d["ok"] is True and d["target"] == "rs_symbol"
        assert d["request"]["id"] == 1 and d["request"]["bits"] == 10
        # La stessa transazione non può essere sovrascritta in silenzio.
        again = self.fetch("/api/inject", method="POST",
                           body=json.dumps({"bits": 10}))
        assert again.code == 409

    def test_inject_validates_effective_count_and_requires_run(self):
        for value in (0, 201, 1.5, "boh"):
            resp = self.fetch("/api/inject", method="POST",
                              body=json.dumps({"bits": value}))
            assert resp.code == 400, value
        with server.BENCH._lock:
            server.BENCH._running = False
        stopped = self.fetch("/api/inject", method="POST",
                             body=json.dumps({"bits": 10}))
        assert stopped.code == 409
        assert "RUN" in json.loads(stopped.body)["error"]
