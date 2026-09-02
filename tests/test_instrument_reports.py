"""Report in formato strumento (Xena2544, SAMComplete Y.1564, MP1900A) e
libreria golden IEEE: le procedure girano davvero sulla catena, i campi
dei report hanno i nomi dei report reali, la correlazione con le waveform
misurate sta entro la tolleranza dichiarata."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tornado.testing import AsyncHTTPTestCase   # noqa: E402

from serdes_sim.config import LinkConfig        # noqa: E402
from serdes_sim.engine import simulate          # noqa: E402
from serdes_sim.instrument_procedures import (  # noqa: E402
    bert_pam4_result, rfc2544_report, y1564_report)
from labpro import instrument_reports as ir     # noqa: E402
from labpro import server                       # noqa: E402

GOOD = dict(fiber_km=0.0, chirp_alpha=0.0, channel_il_nyquist_db=6.0, fec_mode="kp4",
            n_symbols=32768)
LIB = "ieee_802_3bs_smf_2017"


def test_rfc2544_report_has_xena2544_structure_and_passes_on_a_good_link():
    cfg = LinkConfig().with_updates(**GOOD)
    r = rfc2544_report(cfg, frame_sizes=(512,), max_iterations=1)
    assert r["procedure"]["version"] == "1.0.0"
    for key in ("test_summary", "test_setup", "port_configuration", "throughput_setup",
                "throughput", "latency_jitter", "frame_loss", "back_to_back", "summary"):
        assert key in r
    assert r["test_setup"]["Frame Sizes Used"] == [512]
    thr = r["throughput"][0]
    for col in ir.THROUGHPUT_KEYS:
        assert col in thr, col
    assert thr["Result State"] == "PASS" and thr["Loss (Frames)"] == 0
    assert thr["Tx Off.Rate (Percent)"] == pytest.approx(100.0)
    assert thr["Tx Rate (L1) (Bit/s)"] == pytest.approx(cfg.symbol_rate_hz * 2, rel=1e-6)
    assert thr["Tx Rate (L2) (Bit/s)"] < thr["Tx Rate (L1) (Bit/s)"]
    lat = r["latency_jitter"][0]
    assert lat["Min Latency (micsec)"] <= lat["Avg Latency (micsec)"] <= lat["Max Latency (micsec)"]
    assert lat["Avg Latency (micsec)"] > 0.05           # serializzazione + FEC + DSP
    assert lat["latency_budget_ns"] > 0 and lat["latency_measured_analog_ns"] >= 0
    loss = {row["Rate (Percent)"]: row for row in r["frame_loss"]}
    assert set(loss) == {100.0, 50.0}
    assert loss[50.0]["Tx Off.Rate (Percent)"] == pytest.approx(50.0, abs=1.0)
    assert loss[50.0]["IPG (Bytes)"] > loss[100.0]["IPG (Bytes)"] == 12
    b2b = r["back_to_back"][0]
    assert b2b["Tx Burst (Frames)"] == loss[100.0]["Rx (Frames)"] > 0
    assert r["verdict"]["model"] == "PASS" and r["summary"]["failed"] == 0
    md = ir.rfc2544_markdown(r)
    xml = ir.rfc2544_xml(r)
    assert "Throughput Test Results" in md and "Tx Off.Rate (Percent)" in md
    assert xml.startswith('<?xml') and "<ThroughputTest>" in xml and "<TestDateTime>" in xml
    json.dumps(r)


def test_rfc2544_reports_rate_independent_loss_on_a_bad_link():
    cfg = LinkConfig().with_updates(fec_mode="none", n_symbols=32768)   # BER ~2e-2
    r = rfc2544_report(cfg, frame_sizes=(256,), max_iterations=2)
    thr = r["throughput"][0]
    assert thr["Result State"] == "FAIL" and thr["Loss Rate (Percent)"] > 0
    assert len(thr["search_trail"]) >= 2
    assert thr["rate_independent_loss"] is True
    assert r["verdict"]["model"] == "FAIL"


def test_y1564_samcomplete_flow_kpis_and_policing_not_applicable():
    cfg = LinkConfig().with_updates(l2_streams=2, l2_stream_weights=(3, 1, 1, 1), **GOOD)
    r = y1564_report(cfg, cir_steps_pct=(50.0, 100.0))
    assert len(r["services"]) == 2
    line_mbps = cfg.symbol_rate_hz * 2 / 1e6
    cirs = [s["cir_mbps"] for s in r["services"]]
    assert sum(cirs) == pytest.approx(0.8 * line_mbps) and cirs[0] == pytest.approx(3 * cirs[1])
    steps = [row["Step"] for row in r["service_configuration"] if row["Service"] == "Svc 1"]
    assert steps == ["CIR 50 %", "CIR 100 %", "CIR + EIR", "Traffic policing (CIR+EIR+25 %)"]
    for row in r["service_configuration"]:
        for col in ir.Y1564_CFG_KEYS:
            assert col in row, col
        if row["Step"].startswith("Traffic policing"):
            assert row["Result"] == "NOT_APPLICABLE"
        else:
            assert row["Result"] == "PASS"
            assert row["IR (Mbps)"] == pytest.approx(row["Offered (Mbps)"], rel=1e-6)
            assert row["FLR (%)"] == 0.0 and row["FTD (µs)"] > 0
    for row in r["service_performance"]:
        assert row["Result"] == "PASS" and row["Availability (%)"] == 100.0
        assert row["IR (Mbps)"] == pytest.approx(row["CIR (Mbps)"], rel=1e-6)
    assert r["verdict"]["model"] == "PASS"
    assert "Service Configuration Test" in ir.y1564_markdown(r)
    csv = ir.y1564_csv(r)
    assert csv.splitlines()[0].startswith("Phase,Service,Step")
    json.dumps(r)


def test_bert_pam4_result_matches_anritsu_error_cases():
    sim = simulate(LinkConfig().with_updates(channel_il_nyquist_db=14.0), seed=3, depth="light")
    r = bert_pam4_result(sim, {"bits": 1000, "errors": 3, "sync_losses": 0})
    assert r["available"]
    m = np.asarray(r["symbol_error_matrix"]["counts"])
    assert m.shape == (4, 4) and int(m.sum()) == r["symbols_measured"]
    off = int(m.sum() - np.trace(m))
    assert off == r["symbol_error_matrix"]["total_symbol_errors"] > 0
    # ogni errore fra livelli adiacenti (Gray) è un solo bit: MSB o LSB
    lanes = r["lanes"]
    assert lanes["MSB"]["EC"] + lanes["LSB"]["EC"] >= off
    for lane in ("MSB", "LSB"):
        assert lanes[lane]["EC"] == lanes[lane]["INS"]["EC"] + lanes[lane]["OMI"]["EC"]
        assert lanes[lane]["ER"] == pytest.approx(lanes[lane]["EC"] / r["symbols_measured"])
    # tabella Anritsu: 0↔1, 1↔2, 2↔3 con Gray sono errori di un bit
    assert lanes["LSB"]["EC"] == int(m[0, 1] + m[1, 0] + m[2, 3] + m[3, 2])
    assert lanes["MSB"]["EC"] == int(m[1, 2] + m[2, 1] + m[0, 2] + m[2, 0] + m[1, 3] + m[3, 1]) + int(m[0, 3] + m[3, 0])
    assert r["cumulative"]["Bit Count"] == 1000
    md = ir.bert_markdown(r)
    assert "Result PAM4" in md and "| MSB ER |" in md
    assert ir.bert_csv(r).splitlines()[0] == "Lane,Item,Total,INS,OMI"
    nrz = simulate(LinkConfig().with_updates(modulation="NRZ"), seed=1, depth="light")
    assert bert_pam4_result(nrz)["available"] is False


# ---------------------------------------------------------------- golden library
def test_golden_library_metadata_and_stored_pattern():
    from serdes_sim.golden import golden_library, load_library_dataset, validate_dataset
    libs = golden_library()
    lib = next(x for x in libs if x["name"] == LIB)
    assert len(lib["waveforms"]) == 6 and lib["symbol_rate_hz"] == 53.125e9
    assert lib["source_url"].startswith("https://www.ieee802.org/3/bs/public/adhoc/smf/")
    assert all(len(w["source_sha256"]) == 64 for w in lib["waveforms"])
    d = load_library_dataset(LIB, "70G")
    assert validate_dataset(d) == [] and d["source"] == "instrument"
    assert len(d["symbols"]) == 2047 and d["samples_per_ui"] == 20
    assert d["pattern_model"]["fit_residual"] < 0.1
    assert d["reference"]["tdecq_range_db"] == [2.06, 2.82]
    assert d["reference"]["rx_bw_fraction"] == pytest.approx(0.728)
    assert d["sigma_s_w"] > 0


def test_golden_library_correlates_within_tolerance():
    from serdes_sim.golden import correlate_golden, load_library_dataset
    for wid in ("70G", "28G"):
        d = load_library_dataset(LIB, wid)
        r = correlate_golden(d, optimize="mmse")       # veloce: la tolleranza vale anche MMSE
        m = r["measured"]
        assert m["tdecq_db"] is not None and m["tdecq_clause_db"] > m["tdecq_db"]
        assert 6.0 < m["oma_outer_dbm"] < 9.0 and 6.0 < m["er_db"] < 7.5
        assert r["verdict"]["model"] in ("PASS", "FAIL")
        assert abs(r["deltas"]["tdecq_db"]) < 1.0
    r70 = correlate_golden(load_library_dataset(LIB, "70G"), optimize="min_tdecq")
    assert r70["verdict"]["model"] == "PASS" and r70["deltas"]["tdecq_db"] <= 0.5


def test_flexdca_import_identifies_the_pattern_from_a_csv_export():
    from serdes_sim.golden import dataset_from_flexdca, load_library_dataset, parse_flexdca_csv
    d = load_library_dataset(LIB, "70G")
    P = np.asarray(d["waveform_w"])
    sps = 20
    rate = 53.125e9
    t = np.arange(len(P)) / (rate * sps)
    text = ("File Format, WaveformXYValues\nFormat Version, 1\nInstrument, N1010A\nPoints, %d\n"
            "Signal Type, PAM4\nChannel Bandwidth, 70E+9\nChannel Noise, 3.808E-5\n"
            "X Units, Second\nY Units, Watt\nData, \n" % len(P)
            + "\n".join(f"{ti:.15g},{pi:.9g}" for ti, pi in zip(t, P)))
    parsed = parse_flexdca_csv(text)
    assert parsed["header"]["Signal Type"] == "PAM4" and len(parsed["y"]) == len(P)
    ds = dataset_from_flexdca(text, symbol_rate_hz=rate, reference={"tdecq_range_db": [2.06, 2.82],
                                                                     "rx_bw_fraction": 0.728})
    assert ds["samples_per_ui"] == 20 and len(ds["symbols"]) == 2047
    assert ds["pattern_model"]["model"].startswith("delayed-copies")
    assert ds["pattern_model"]["fit_residual"] < 0.1
    assert ds["sigma_s_w"] == pytest.approx(3.808e-5)
    assert list(ds["symbols"]) == list(d["symbols"])


class InstrumentApiTest(AsyncHTTPTestCase):
    def get_app(self):
        return server.make_app()

    def test_golden_library_listing(self):
        resp = self.fetch("/api/golden/library")
        assert resp.code == 200
        body = json.loads(resp.body)
        assert body["libraries"][0]["name"] == LIB and len(body["libraries"][0]["waveforms"]) == 6

    def test_instrument_reports_contract(self):
        resp = self.fetch("/api/report/rfc2544?format=md")
        assert resp.code == 400 and "error_en" in json.loads(resp.body)
        resp = self.fetch("/api/report/y1564?format=pdf")
        assert resp.code == 400
        resp = self.fetch("/api/report/bert?format=json")
        assert resp.code == 200
        body = json.loads(resp.body)
        assert body["kind"] == "bert" and "available" in body["report"]
        resp = self.fetch("/api/report/bert?format=csv")
        assert resp.code == 200 and resp.headers["Content-Type"].startswith("text/csv")


# ---------------------------------------------------------------- fixture S-parameter
def test_bundled_ieee_fixture_deembeds_the_scope_waveform():
    from labpro.paneldata import (apply_fixture, bundled_fixtures, deembed_fixture,
                                  fixture_from_touchstone, fixture_response)
    fx = bundled_fixtures()
    assert fx and fx[0]["id"] == "ieee_3ck_module_board"
    sp = fixture_from_touchstone(Path(fx[0]["path"]).read_text())
    assert sp["ports"] == 4 and sp["n_points"] == 701 and sp["f_hz"][-1] == pytest.approx(70e9)
    il = sp["il_db"]
    assert il["1"] > -1.0 and il["26.5625"] < il["10"] < il["1"]      # perdita che cresce con f
    cfg = LinkConfig()
    f = np.linspace(-cfg.fs_analog_hz / 2, cfg.fs_analog_hz / 2, 4001)
    H = fixture_response(f, cfg, 0.0, sparams=sp)
    assert np.allclose(H[f < 0], np.conj(H[f > 0][::-1]), atol=1e-9)   # hermitiana
    rng = np.random.default_rng(2)
    x = np.repeat(rng.choice([-1.0, -1 / 3, 1 / 3, 1.0], 3000), cfg.analog_sps)
    y = apply_fixture(x, cfg, 0.0, sparams=sp)
    z = deembed_fixture(y, cfg, 0.0, sparams=sp)
    assert np.std(y - x) > 0.05 * np.std(x)
    assert np.std(z - x) < 0.35 * np.std(y - x)


class FixtureApiTest(AsyncHTTPTestCase):
    def get_app(self):
        return server.make_app()

    def test_fixture_endpoint_bundled_and_clear(self):
        resp = self.fetch("/api/scope/fixture")
        body = json.loads(resp.body)
        assert resp.code == 200 and body["bundled"][0]["id"] == "ieee_3ck_module_board"
        resp = self.fetch("/api/scope/fixture", method="POST",
                          body=json.dumps({"bundled": "ieee_3ck_module_board"}))
        assert resp.code == 200
        loaded = json.loads(resp.body)["loaded"]
        assert loaded["ports"] == 4 and loaded["f_max_ghz"] == pytest.approx(70.0)
        resp = self.fetch("/api/scope/fixture", method="POST", body=json.dumps({"bundled": "nope"}))
        assert resp.code == 400
        resp = self.fetch("/api/scope/fixture", method="POST", body=json.dumps({"clear": True}))
        assert json.loads(resp.body)["loaded"] is None
        resp = self.fetch("/api/scope?nodes=vctle&fix=s2p")
        assert resp.code == 400
