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
    r = simulate(CFG.with_updates(tx_output_on=False), seed=42, depth="light")
    assert bool(np.all(r.tx.driver_voltage_v == 0))     # mute elettrico
    assert r.link_up is False                            # niente lock: DOWN vero


def test_tx_output_default_on_is_backward_compatible():
    assert CFG.tx_output_on is True
    r = simulate(CFG, seed=42, depth="light")
    assert r.link_up is True


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
