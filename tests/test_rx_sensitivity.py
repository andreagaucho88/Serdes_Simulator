"""BERT RX sensitivity search (iterazione 28, punto 7 prima tranche).

Bisezione sulla potenza lanciata a seed fisso: soglia = minima potenza con
BER contata ≤ target e link UP, riportata come potenza MEDIA al PD
(dichiarata, non OMA_outer di clause).
"""

import json
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from serdes_sim import LinkConfig                              # noqa: E402
from serdes_sim.engine import (ExperimentCancelled,            # noqa: E402
                               rx_sensitivity_search)

CFG = LinkConfig()          # ottica; baseline BER ~2e-2 (stressata, didattica)


@pytest.mark.slow
def test_threshold_below_current_with_reachable_target():
    # target sopra la BER attuale: il punto operativo passa e la bisezione
    # scende a cercare la potenza minima
    d = rx_sensitivity_search(CFG, target_ber=5e-2)
    assert d["status"] in ("ok", "capped")
    assert d["threshold_launch_dbm"] <= CFG.laser_dbm
    assert d["margin_db"] >= 0
    assert d["sensitivity_pd_dbm"] is not None
    assert d["points"] and all("ber" in q for q in d["points"])
    # durata guidata dalla confidenza: CL95 ~ 3/target
    assert d["cl95_bits"] == pytest.approx(3.0 / 5e-2)
    assert d["cl95_seconds"] > 0
    # la soglia dichiarata deve davvero passare (l'ultima misura del trail)
    assert d["points"][-1]["pass"] is True


def test_unreachable_target_reports_fail_at_current():
    d = rx_sensitivity_search(CFG, target_ber=1e-6)
    assert d["status"] == "fail_at_current"
    assert d["threshold_launch_dbm"] is None
    assert d["margin_db"] is None
    assert len(d["points"]) == 1     # una sola misura: niente ricerca inutile


def test_default_target_uses_infec_threshold():
    from serdes_sim.blocks import fec as fec_block
    cfg = CFG.with_updates(fec_mode="kp4")
    d = rx_sensitivity_search(cfg, target_ber=None)
    expected = fec_block.prefec_ber_threshold(1e-13, n=544, t=15, m=10)
    assert d["target_ber"] == pytest.approx(expected)


def test_copper_medium_is_refused():
    with pytest.raises(ValueError, match="optical"):
        rx_sensitivity_search(CFG.with_updates(link_medium="copper"))


def test_cancel_token_aborts_immediately():
    evt = threading.Event()
    evt.set()
    t0 = time.perf_counter()
    with pytest.raises(ExperimentCancelled):
        rx_sensitivity_search(CFG, target_ber=5e-2, cancel=evt)
    assert time.perf_counter() - t0 < 3.0


from tornado.testing import AsyncHTTPTestCase                  # noqa: E402

from labpro import server                                      # noqa: E402


class SensitivityApiTest(AsyncHTTPTestCase):
    def get_app(self):
        return server.make_app()

    def test_invalid_target_is_json_400(self):
        resp = self.fetch("/api/experiment/sensitivity", method="POST",
                          body=json.dumps({"target_ber": "non-un-numero"}))
        assert resp.code == 400
        assert "target_ber" in json.loads(resp.body)["error"]

    def test_out_of_range_target_is_json_400(self):
        resp = self.fetch("/api/experiment/sensitivity", method="POST",
                          body=json.dumps({"target_ber": 0.9}))
        assert resp.code == 400
        assert "error" in json.loads(resp.body)
