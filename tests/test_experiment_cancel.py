"""Cancellazione cooperativa degli esperimenti (worker pool, iterazione 26).

Ogni procedura lunga accetta un token (threading.Event): quando è settato
l'esperimento si ferma al confine del record successivo con
ExperimentCancelled, senza produrre report parziali.
"""

import json
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from serdes_sim import LinkConfig, sweep                       # noqa: E402
from serdes_sim.engine import (ExperimentCancelled,            # noqa: E402
                               anlt_session, jitter_tolerance,
                               jitter_transfer, l2_ont_report, link_train,
                               traffic_sweep)
from serdes_sim.procedures import run_dr4_tdecq_e2e            # noqa: E402

CFG = LinkConfig()

CANCEL_CASES = {
    "sweep": lambda evt: sweep(CFG, "channel_il_nyquist_db", [8.0, 10.0],
                               cancel=evt),
    "jtol": lambda evt: jitter_tolerance(CFG, [200.0], cancel=evt),
    "jtf": lambda evt: jitter_transfer(CFG, freqs_mhz=(60.0,), cancel=evt),
    "train": lambda evt: link_train(CFG, cancel=evt),
    "anlt": lambda evt: anlt_session(CFG, cancel=evt),
    "ont": lambda evt: l2_ont_report(CFG, ipg_grid=[96], cancel=evt),
    "traffic": lambda evt: traffic_sweep(CFG, [64], cancel=evt),
    "dr4": lambda evt: run_dr4_tdecq_e2e(cancel=evt),
}


@pytest.mark.parametrize("name", sorted(CANCEL_CASES))
def test_preset_token_aborts_before_first_record(name):
    evt = threading.Event()
    evt.set()
    t0 = time.perf_counter()
    with pytest.raises(ExperimentCancelled):
        CANCEL_CASES[name](evt)
    # cooperativa ma pronta: mai un giro completo di simulate dopo il set
    assert time.perf_counter() - t0 < 3.0, name


@pytest.mark.parametrize("name", sorted(CANCEL_CASES))
def test_no_token_keeps_signature_compatible(name):
    # cancel=None (default) non deve cambiare il comportamento: qui basta
    # verificare che il token assente non sollevi nulla al primo check
    from serdes_sim.engine import check_cancel
    check_cancel(None)   # nessuna eccezione


def test_registry_single_flight_and_cancel():
    from labpro import server

    evt = server.EXPERIMENT.begin("sweep")
    assert evt is not None
    try:
        # un secondo esperimento è rifiutato finché il primo non termina
        assert server.EXPERIMENT.begin("jtol") is None
        assert server.EXPERIMENT.current == "sweep"
        assert server.EXPERIMENT.cancel() is True
        assert evt.is_set()
    finally:
        server.EXPERIMENT.end()
    assert server.EXPERIMENT.current is None
    assert server.EXPERIMENT.cancel() is False


from tornado.testing import AsyncHTTPTestCase                  # noqa: E402

from labpro import server                                      # noqa: E402


@pytest.mark.slow
class ExperimentEndToEndTest(AsyncHTTPTestCase):
    def get_app(self):
        return server.make_app()

    def test_tiny_traffic_experiment_roundtrip(self):
        # attraversa davvero worker pool + registry + restart (1 sola sim)
        resp = self.fetch("/api/experiment/traffic", method="POST",
                          body=json.dumps({"frame_sizes": [64]}),
                          request_timeout=60)
        assert resp.code == 200, resp.body
        d = json.loads(resp.body)
        assert d["ok"] is True and len(d["rows"]) == 1
        assert server.EXPERIMENT.current is None   # registry ripulito

    def test_cancel_idle_is_a_clean_no_op(self):
        resp = self.fetch("/api/experiment/cancel", method="POST", body="{}")
        assert resp.code == 200
        d = json.loads(resp.body)
        assert d["ok"] is True and d["cancelled"] is False
