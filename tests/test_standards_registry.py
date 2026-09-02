"""Registro degli standard, tassonomia dei verdetti e guardie di coerenza.

Questi test sono la polizza dell'iterazione 45: ogni limite normativo vive in
``serdes_sim/standards.py`` e viene consumato (mai riscritto) da fisica,
procedure, pannelli, help e Academy.  Se un numero ricompare a mano nel
front-end o in una scheda, qui fallisce.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from serdes_sim import LinkConfig, simulate                       # noqa: E402
from serdes_sim.config import (STANDARD_PROFILE_META,             # noqa: E402
                               STANDARD_PROFILES, field_schema)
from serdes_sim import standards as st                            # noqa: E402
from serdes_sim.blocks import metrics                             # noqa: E402
from labpro import paneldata                                      # noqa: E402

APP_JS = (ROOT / "labpro/static/app.js").read_text(encoding="utf-8")
STYLE = (ROOT / "labpro/static/style.css").read_text(encoding="utf-8")
EDU = (ROOT / "labpro/education.py").read_text(encoding="utf-8")
HELP = (ROOT / "labpro/control_help.py").read_text(encoding="utf-8")

DR4 = "IEEE 802.3bs — 400GBASE-DR4 · 100G/λ ottico 500 m"
KR1 = "IEEE 802.3ck — 100GBASE-KR1 · backplane elettrico"
C2M = "IEEE 802.3ck — 100G/lane C2M (AUI) · elettrico corto"
LR10 = "IEEE 802.3ae — 10GBASE-LR · PMD ottico 10 km (NRZ)"


# --------------------------------------------------------------- registry ---

def test_every_limit_carries_full_provenance():
    seen = 0
    for interface, lim in st.all_limits():
        seen += 1
        assert lim.standard and lim.clause and lim.table and lim.edition, lim.id
        assert lim.reference_plane and lim.pattern and lim.reference_rx, lim.id
        assert lim.note_it and lim.note_en, (interface, lim.id)
        assert lim.confidence in ("published", "to-verify", "none"), lim.id
        assert lim.cmp in ("<=", ">=", None), lim.id
        if lim.limit is None:
            assert lim.confidence == "none", (interface, lim.id)
        else:
            assert lim.confidence != "none", (interface, lim.id)
            assert np.isfinite(lim.limit)
    assert seen >= 40


def test_registry_covers_every_catalog_interface():
    for name, meta in STANDARD_PROFILE_META.items():
        iface = meta["interface"]
        assert iface in st.LIMITS_BY_INTERFACE, (name, iface)
        assert iface in st.INTERFACE_CLAUSES, (name, iface)
        assert st.INTERFACE_CLAUSES[iface]["standard"].split()[0] == meta["standard"].split()[0]


def test_published_limits_are_the_ones_the_model_uses():
    dr4 = st.limits_for_interface("400GBASE-DR4")
    assert dr4["tdecq"].limit == 3.4 and dr4["tdecq"].confidence == "published"
    assert dr4["ber_prefec"].limit == st.KP4_PMD_BER == 2.4e-4
    kr1 = st.limits_for_interface("100GBASE-KR1")
    assert kr1["com"].limit == st.COM_KR1_THRESHOLD_DB == 3.0
    assert kr1["rlm"].limit == st.RLM_MIN_8023CK == 0.95
    # SR1: il limite non è trascritto → nessun pass/fail possibile
    sr1 = st.limits_for_interface("100GBASE-SR1")
    assert sr1["tdecq"].limit is None and sr1["tdecq"].confidence == "none"
    # C2M non usa COM
    assert st.limits_for_interface("100GAUI-1 C2M")["com"].implementation == "not-applicable"
    snap = st.registry_snapshot()
    json.dumps(snap)
    assert set(snap["verdicts"]) == st.VERDICTS


def test_verdict_taxonomy_is_closed_and_normalised():
    assert st.normalize_status("WARN") == st.NOT_ASSESSED
    assert st.normalize_status("NOT ASSESSED") == st.NOT_ASSESSED
    assert st.normalize_status("MODEL PASS") == st.PASS
    assert st.normalize_status("na") == st.NOT_APPLICABLE
    assert st.normalize_status(True) == st.PASS and st.normalize_status(False) == st.FAIL
    with pytest.raises(ValueError):
        st.verdict(st.PASS, compliance=st.PASS)      # la conformità non è mai PASS
    with pytest.raises(ValueError):
        st.verdict(st.PASS, basis="whatever")


def test_evaluate_limit_semantics():
    lim = st.limits_for_interface("400GBASE-DR4")["tdecq"]
    assert st.evaluate_limit(lim, 3.0)["model"] == st.PASS
    assert st.evaluate_limit(lim, 3.6)["model"] == st.FAIL
    assert st.evaluate_limit(lim, 3.45, uncertainty=0.1)["model"] == st.MARGINAL
    assert st.evaluate_limit(lim, 3.35, uncertainty=0.1)["model"] == st.MARGINAL
    v = st.evaluate_limit(lim, 3.0)
    assert v["basis"] == "clause-limit" and v["compliance"] == st.NOT_ASSESSED
    assert v["margin"] == pytest.approx(0.4)
    assert st.evaluate_limit(lim, None, fail_reason="no eye")["model"] == st.FAIL
    assert st.evaluate_limit(lim, None)["model"] == st.NOT_ASSESSED
    assert st.evaluate_limit(lim, 1.0, implementation="proxy")["model"] == st.PROXY
    assert st.evaluate_limit(lim, 1.0, applicable=False)["model"] == st.NOT_APPLICABLE
    # limite "da verificare": mai PASS/FAIL, ma margine informativo
    er = st.limits_for_interface("400GBASE-DR4")["er"]
    v2 = st.evaluate_limit(er, 5.0)
    assert v2["model"] == st.NOT_ASSESSED and v2["basis"] == "context-limit"
    assert v2["margin"] == pytest.approx(1.5)
    # nessun limite trascritto
    oma = st.limits_for_interface("400GBASE-DR4")["oma_outer"]
    assert st.evaluate_limit(oma, -1.0)["model"] == st.NOT_ASSESSED


def test_ber_verdict_uses_clopper_pearson_bounds():
    lim = st.limits_for_interface("400GBASE-DR4")["ber_prefec"]
    ok, model = st.ber_verdict(0, 1_000_000, lim, model_threshold=2.1e-4)
    assert ok["model"] == st.PASS and ok["bound"]["upper"] < 1e-5
    assert model["model"] == st.PASS and model["basis"] == "model-limit"
    bad, _ = st.ber_verdict(100, 100_000, lim)
    assert bad["model"] == st.FAIL
    marginal, _ = st.ber_verdict(2, 10_000, lim)
    assert marginal["model"] == st.MARGINAL
    none, _ = st.ber_verdict(0, 0, lim)
    assert none["model"] == st.NOT_ASSESSED


def test_jtol_context_mask_is_data():
    corner = 100.0
    assert st.jtol_context_mask_ui(corner, corner) == pytest.approx(st.JTOL_CONTEXT_MASK["floor_ui"])
    assert st.jtol_context_mask_ui(corner / 10, corner) == pytest.approx(10 * st.JTOL_CONTEXT_MASK["floor_ui"])
    assert st.jtol_context_mask_ui(1e-6, corner) == st.JTOL_CONTEXT_MASK["cap_ui"]
    assert st.jtol_context_mask_ui(corner, corner, floor_ui=0.1) == pytest.approx(0.1)


@pytest.mark.parametrize("name", sorted(STANDARD_PROFILES))
def test_contract_clause_follows_the_active_profile(name):
    cfg = STANDARD_PROFILES[name][0]
    meta = STANDARD_PROFILE_META[name]
    rows = {r["id"]: r for r in st.measurement_contracts(cfg, name, meta)}
    iface = meta["interface"]
    cl = st.INTERFACE_CLAUSES[iface]
    for r in rows.values():
        assert r["compliance"] in (st.NOT_ASSESSED, st.NOT_APPLICABLE)
        assert r["standard"] == meta["standard"]
        assert r["note"]["it"] and r["note"]["en"]
    optical_pam4 = cfg.link_medium == "optical" and cfg.modulation == "PAM4"
    assert rows["tdecq"]["applicable"] == optical_pam4
    if optical_pam4:
        assert rows["tdecq"]["clause"] == cl["tx"]
        assert rows["tdecq"]["limit"] is not None
    if meta["standard"].startswith("OIF"):
        assert "PMD" not in rows["optical_levels"]["clause"]
    if iface == "100GBASE-KR1":
        assert rows["com"]["applicable"] and rows["com"]["limit"]["limit"] == 3.0
    if iface == "100GAUI-1 C2M":
        assert not rows["com"]["applicable"]
        assert rows["com"]["compliance"] == st.NOT_APPLICABLE
    if iface == "10GBASE-LR":
        assert rows["eye_mask"]["applicable"] and rows["eye_mask"]["limit"]


# --------------------------------------------------------------- metrics ----

def test_com_tx_filter_is_the_gaussian_rise_time_form():
    from serdes_sim.blocks.com import KR1_93A, _ctle, _reference_tx_filter
    f = np.array([0.0, 10e9, 26.5625e9, 53.125e9])
    tr = KR1_93A.tx_transition_time_s
    expected = np.exp(-2.0 * (np.pi * f * tr / 1.6832) ** 2)
    assert np.allclose(_reference_tx_filter(f, KR1_93A), expected, rtol=1e-12)
    # stadio a bassa frequenza: g_DC2 in DC, trasparente in alta frequenza
    lo = _ctle(np.array([1.0]), 0.0, KR1_93A, gdc2_db=-6.0)[0]
    assert abs(lo) == pytest.approx(10 ** (-6 / 20), rel=1e-3)
    hi_with = _ctle(np.array([40e9]), 0.0, KR1_93A, gdc2_db=-6.0)[0]
    hi_without = _ctle(np.array([40e9]), 0.0, KR1_93A, gdc2_db=0.0)[0]
    assert abs(hi_with) == pytest.approx(abs(hi_without), rel=0.02)


def test_rlm_clause_formula():
    ideal = metrics.rlm_clause([-1.0, -1 / 3, 1 / 3, 1.0])
    assert ideal["rlm"] == pytest.approx(1.0)
    compressed = metrics.rlm_clause([-1.0, -0.3, 0.3, 1.0])
    assert compressed["es1"] == pytest.approx(0.3) and compressed["rlm"] == pytest.approx(0.9)
    assert metrics.rlm_clause([0.0, 0.0, 0.0, 0.0]) is None


def test_sndr_linear_fit_on_synthetic_pulse():
    from serdes_sim.blocks.stimulus import PAM4_GRAY, generate_stimulus
    rng = np.random.default_rng(3)
    sym = generate_stimulus(4000, 13, PAM4_GRAY)
    sps = 8
    wave = np.repeat(sym, sps).astype(float)
    sigma = 0.02
    noisy = wave + rng.normal(0, sigma, len(wave))
    out = metrics.sndr_linear_fit(noisy, sym, sps, np_taps=40)
    assert out is not None
    # p_max = 1 (pulse rettangolare di ampiezza unitaria), σe ≈ σ del rumore
    assert out["p_max"] == pytest.approx(1.0, abs=0.05)
    assert out["sndr_db"] == pytest.approx(20 * np.log10(1.0 / sigma), abs=1.0)


def test_optical_levels_runs_recovers_ideal_levels():
    from serdes_sim.blocks.stimulus import PAM4_GRAY, generate_stimulus
    sym = generate_stimulus(6000, 13, PAM4_GRAY)
    sps = 16
    levels_w = np.interp(sym, PAM4_GRAY.levels_array, [1e-4, 2e-4, 3e-4, 4e-4])
    wave = np.repeat(levels_w, sps)
    out = metrics.optical_levels_runs(wave, sym, PAM4_GRAY.levels_array, sps)
    assert out is not None
    assert np.allclose(out["p_levels_w"], [1e-4, 2e-4, 3e-4, 4e-4], rtol=1e-9)
    assert out["extinction_ratio_db"] == pytest.approx(10 * np.log10(4.0))
    assert all(n > 0 for n in out["samples"])


def test_eye_mask_hits_geometry():
    mask = st.EYE_MASKS["10GBASE-LR"]
    n = 33
    clean = np.array([np.r_[np.zeros(n // 2), np.ones(n - n // 2)], np.ones(n), np.zeros(n)])
    out = metrics.eye_mask_hits(clean, mask, 0.0, 1.0)
    assert out["hits"] == 0 and out["samples"] > 0
    mid = np.array([np.full(n, 0.5)])
    assert metrics.eye_mask_hits(mid, mask, 0.0, 1.0)["hits"] > 0
    over = np.array([np.full(n, 1.5)])
    assert metrics.eye_mask_hits(over, mask, 0.0, 1.0)["hits"] > 0


def test_tdecq_sigma_s_credits_measurement_noise():
    from serdes_sim.blocks.stimulus import PAM4_GRAY, generate_stimulus
    sym = generate_stimulus(4000, 13, PAM4_GRAY)
    wave = np.repeat(np.interp(sym, PAM4_GRAY.levels_array, np.linspace(0.2, 1.2, 4)), 16)
    base = metrics.tdecq_report(wave, sym, PAM4_GRAY, 16, 56e9, 56e9 * 16)
    credited = metrics.tdecq_report(wave, sym, PAM4_GRAY, 16, 56e9, 56e9 * 16,
                                    sigma_s_w=base["sigma_g"])
    assert credited["tdecq_db"] == pytest.approx(base["tdecq_db"] - 10 * np.log10(np.sqrt(2)), abs=1e-6)
    assert base["measure"] == "TDECQ"
    assert metrics.tecq_report(wave, sym, PAM4_GRAY, 16, 56e9, 56e9 * 16)["measure"] == "TECQ"


# --------------------------------------------------------------- config -----

def test_field_schema_rejects_bad_types_and_ranges():
    assert LinkConfig().validate() == []
    assert LinkConfig(fiber_km=-5.0).validate()
    assert LinkConfig(adc_bits=0).validate()
    assert LinkConfig(n_symbols=10_000_000).validate()
    assert LinkConfig(tx_ffe_taps=("a", "b", "c")).validate()
    assert LinkConfig(tx_output_on="no").validate()
    assert LinkConfig(symbol_rate_hz="56e9").validate()
    assert LinkConfig(laser_dbm=float("nan")).validate()
    assert LinkConfig(fiber_km=None).validate()
    schema = field_schema()
    assert set(schema) == set(LinkConfig().to_dict())
    assert schema["fiber_km"]["type"] == "float" and schema["fiber_km"]["hi"] >= 100
    assert schema["tx_output_on"]["type"] == "bool"
    assert all(not c.validate() for c, _ in STANDARD_PROFILES.values())


# --------------------------------------------------------------- panels -----

@pytest.fixture(scope="module")
def dr4_sim():
    return simulate(STANDARD_PROFILES[DR4][0], seed=42, depth="light")


def _walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, obj


def _assert_closed_taxonomy(payload, where):
    for path, value in _walk(payload):
        key = path.rsplit(".", 1)[-1]
        if key in ("model", "compliance") and ".verdict" in path:
            assert value in st.VERDICTS, (where, path, value)
        if key == "status" and ("steps" in path or "checks" in path or "rows" in path):
            assert value in st.VERDICTS, (where, path, value)


def test_compliance_panel_verdicts_are_closed_and_traceable(dr4_sim):
    cfg = STANDARD_PROFILES[DR4][0]
    out = paneldata.standards_panel(dr4_sim, cfg, profile=DR4)
    json.dumps(out)
    _assert_closed_taxonomy(out, "standards")
    assert out["profile"]["interface"] == "400GBASE-DR4" and not out["profile"]["modified"]
    rows = {r["id"]: r for r in out["measurement_contracts"]}
    td = rows["tdecq"]
    assert td["verdict"]["basis"] == "clause-limit" and td["verdict"]["limit"] == 3.4
    assert td["verdict"]["model"] in (st.PASS, st.FAIL, st.MARGINAL)
    assert rows["rlm"]["verdict"]["model"] == st.PROXY
    assert rows["ber"]["verdict"]["bound"]["cl"] == 0.95
    assert "ratio_db" not in out              # il "263 dB" non esiste più
    assert rows["com"]["verdict"]["model"] == st.NOT_APPLICABLE
    assert all(r["note"]["it"] and r["note"]["en"] for r in rows.values())
    assert all(isinstance(m["note"], dict) for m in out["manifest"])
    # memo per record: la seconda chiamata non ricalcola il TDECQ
    assert "tdecq" in dr4_sim.__dict__.get("_labpro_memo", {})


def test_modified_profile_is_still_recognised(dr4_sim):
    cfg = STANDARD_PROFILES[DR4][0].with_updates(fiber_km=1.0, laser_dbm=2.0)
    out = paneldata.standards_panel(dr4_sim, cfg, profile=DR4)
    assert out["profile"]["name"] == DR4
    assert out["profile"]["modified_fields"] == ["fiber_km", "laser_dbm"]
    ctx = paneldata.profile_context(cfg, None)
    assert ctx["name"] is None            # senza tracker: uguaglianza esatta


def test_other_builders_carry_verdict_objects(dr4_sim):
    cfg = STANDARD_PROFILES[DR4][0]
    for name in ("checks", "physics", "cmis", "optical"):
        out = paneldata.PANEL_BUILDERS[name](dr4_sim, cfg)
        json.dumps(out)
        _assert_closed_taxonomy(out, name)
    eye = paneldata.eye_panel(dr4_sim, cfg, node="pfiber", n_traces=20, profile=DR4)
    assert eye["meas"]["tdecq"]["verdict"]["limit"] == 3.4
    assert eye["meas"]["rlm_clause"]["rlm"] == eye["meas"]["rlm_proxy"]
    assert eye["meas"]["sndr_fit"] is not None
    opt = paneldata.optical_panel(dr4_sim, cfg, profile=DR4)
    assert opt["p_levels"]["verdicts"]["er"]["model"] == st.NOT_ASSESSED   # to-verify
    assert opt["p_levels"]["verdicts"]["rlm"]["model"] == st.PROXY


def test_nrz_profile_gets_the_clause_mask_as_data():
    cfg = STANDARD_PROFILES[LR10][0]
    sim = simulate(cfg, seed=7, depth="light")
    eye = paneldata.eye_panel(sim, cfg, node="pfiber", n_traces=20, profile=LR10)
    mask = eye["meas"]["eye_mask"]
    assert mask is not None and mask["geometry"] == "declared"
    assert mask["verdict"]["model"] == st.NOT_ASSESSED      # geometria da verificare
    assert mask["hit_ratio"] is not None
    out = paneldata.standards_panel(sim, cfg, profile=LR10)
    rows = {r["id"]: r for r in out["measurement_contracts"]}
    assert rows["eye_mask"]["applicable"] and rows["eye_mask"]["measured"]["value"] is not None


def test_report_bundle_is_traceable(dr4_sim):
    cfg = STANDARD_PROFILES[DR4][0]
    rep = paneldata.standards_report(dr4_sim, cfg, profile=DR4, extras={"records": 3})
    json.dumps(rep)
    assert rep["schema"] == "labpro-standards-report/1"
    assert len(rep["config_sha256"]) == 64
    assert rep["acquisition"]["seed"] == 42 and rep["acquisition"]["records"] == 3
    assert rep["profile"]["interface"] == "400GBASE-DR4"
    assert rep["versions"]["numpy"] and rep["versions"]["scipy"]
    assert rep["registry"]["limits"]["400GBASE-DR4"]
    assert all(c["verdict"]["compliance"] in (st.NOT_ASSESSED, st.NOT_APPLICABLE)
               for c in rep["contracts"])
    md = paneldata.standards_report_markdown(rep)
    assert md.startswith("# LabPro standards report · 400GBASE-DR4")
    assert "| TDECQ |" in md and "NOT_ASSESSED" in md
    # determinismo: stesso record ⇒ stesso hash e stessi verdetti
    rep2 = paneldata.standards_report(dr4_sim, cfg, profile=DR4, extras={"records": 3})
    assert rep2["config_sha256"] == rep["config_sha256"]
    assert [c["verdict"]["model"] for c in rep2["contracts"]] == \
        [c["verdict"]["model"] for c in rep["contracts"]]


# --------------------------------------------------------------- guards -----

def test_no_normative_number_lives_in_the_frontend():
    for literal in ("<= 3.4", "3.4 dB", ">= 0.95", "≤3.4 dB", "≤ 3.4 dB", "32.5 dB"):
        assert literal not in APP_JS, f"limite normativo ricomparso in app.js: {literal!r}"
    assert "maskAt(" not in APP_JS               # la maschera JTOL è un dato del server
    assert "PANEL_DEFS.stimulus" not in APP_JS   # pannelli morti rimossi
    assert "PANEL_DEFS.serpll" not in APP_JS
    assert "verdictChip(" in APP_JS and "measureRow(" in APP_JS


def test_help_and_academy_numbers_come_from_the_registry():
    assert "2.4e-3-2e-2" not in HELP
    assert "26.5625 GBd (100G/lane" not in HELP and "53.125 GBd (200G/lane" not in HELP
    assert "26.5625 GBd (50G/lane" in HELP and "53.125 GBd (100G/lane" in HELP
    assert st.fmt_number(st.KP4_PMD_BER) == "2.4e-4" and "2.4e-4" in HELP
    assert '"≤ 3.4 dB' not in EDU and '"≥ 3 dB"' not in EDU and '"≥ 0.95' not in EDU
    assert "clause 120D)" not in EDU and "120.5.11.2.1" in EDU
    assert 'Profilo 100GBASE-DR"' not in EDU      # profilo inesistente nel catalogo
    from labpro.education import TOPICS
    nums = {n["l"]: n["v"] for t in TOPICS for n in t["numbers"]}
    assert nums["TDECQ DR4"].startswith(f"≤ {st.limits_for_interface('400GBASE-DR4')['tdecq'].limit:g} dB")
    assert nums["COM minimo"].startswith(f"≥ {st.COM_KR1_THRESHOLD_DB:g} dB")
    assert nums["soglia pre-FEC KP4"].startswith(st.fmt_number(st.KP4_PMD_BER))


def test_academy_profiles_and_panels_exist():
    from labpro.education import TOPICS
    panel_ids = set(re.findall(r"^PANEL_DEFS\.(\w+) = \{", APP_JS, flags=re.MULTILINE))
    alias_ids = set(re.findall(r"^\s+(\w+): \{ type: \"bert\"", APP_JS, flags=re.MULTILINE))
    for t in TOPICS:
        assert t["panel"] in panel_ids | alias_ids, (t["id"], t["panel"])
        for a in t["actions"]:
            m = re.match(r"Profilo (\S+)", a["do"]["it"])
            if m:
                assert any(m.group(1) in name for name in STANDARD_PROFILES), a["do"]["it"]


def test_known_italian_leaks_are_wrapped():
    leaks = [
        "(${f.frames_lost} persi)", 'sub: "nessun frame decodificabile"',
        'sub: "CDR o pattern lock non agganciano', '"btn btn-accent", "Misura JTOL")',
        'textContent = "training…"', '? "invariato" :', 'v: "ORACLE (ideale)"',
        'Canale attivo: <b>', 'title: "stima dual-Dirac grezza', '"rapporto log "',
        '"BER contata "', 'title = "IC95% (iid): ["', '"tempo [UI]")', 'name: "canale"',
        '<label>BER media prima</label>', 'aria-label="close"',
    ]
    for leak in leaks:
        assert leak not in APP_JS, f"stringa italiana non tradotta: {leak!r}"


def test_ui_components_exist_in_css():
    for sel in (".verdict.v-pass", ".verdict.v-proxy", ".mbar", ".mrow", ".cmp-head",
                "#toasts", ".panel.pinned", ".note:empty", ".note.folded", ".tabs-nav",
                ".panel.is-first-load", "--series-5"):
        assert sel in STYLE, sel


def test_server_serves_report_and_tracks_profile():
    from tornado.testing import AsyncHTTPTestCase
    from labpro import server

    class T(AsyncHTTPTestCase):
        def get_app(self):
            return server.make_app()

        def runTest(self):
            import os
            os.environ["ASYNC_TEST_TIMEOUT"] = "240"   # report = sim full-depth + COM
            old_cfg, old_profile = server.BENCH.cfg, server.PROFILE["name"]
            try:
                hdr = {"Content-Type": "application/json", "Origin": self.get_url("/")[:-1]}
                r = self.fetch("/api/preset", method="POST", headers=hdr,
                               body=json.dumps({"name": KR1}))
                assert r.code == 200
                d = json.loads(r.body)
                assert d["profile"]["name"] == KR1 and d["profile"]["modified_fields"] == []
                assert d["cfg"]["s2p_text"] == "" and "s2p_bytes" in d["cfg"]
                r = self.fetch("/api/config", method="POST", headers=hdr,
                               body=json.dumps({"updates": {"channel_il_nyquist_db": 15.0}}))
                assert r.code == 200
                st_ = json.loads(self.fetch("/api/state").body)
                assert st_["profile"]["name"] == KR1
                assert st_["profile"]["modified_fields"] == ["channel_il_nyquist_db"]
                assert "field_schema" in st_
                # parametri non validi → 400 bilingue, mai 500
                r = self.fetch("/api/config", method="POST", headers=hdr,
                               body=json.dumps({"updates": {"symbol_rate_hz": "56e9"}}))
                assert r.code == 400 and "error_en" in json.loads(r.body)
                r = self.fetch("/api/config", method="POST", headers=hdr,
                               body=b'{"updates":{"laser_dbm":NaN}}')
                assert r.code == 400
                r = self.fetch("/api/panel/eye?n=abc")
                assert r.code == 400
                r = self.fetch("/api/experiment/sweep", method="POST", headers=hdr,
                               body=json.dumps({"field": "laser_dbm", "lo": "x"}))
                assert r.code == 400
                r = self.fetch("/api/report/standards?format=xml")
                assert r.code == 400
                r = self.fetch("/api/report/standards?format=json", request_timeout=120)
                assert r.code == 200
                rep = json.loads(r.body)
                assert rep["schema"] == "labpro-standards-report/1"
                assert rep["profile"]["name"] == KR1
                assert rep["com"] is not None and rep["com"]["verdict"]["model"] in st.VERDICTS
                r = self.fetch("/api/report/standards?format=md", request_timeout=120)
                assert r.code == 200 and r.headers["Content-Type"].startswith("text/markdown")
                assert b"# LabPro standards report" in r.body
                # preset didattico: nessun profilo
                r = self.fetch("/api/preset", method="POST", headers=hdr,
                               body=json.dumps({"name": "Back-to-back (senza fibra)"}))
                assert json.loads(r.body)["profile"]["name"] is None
            finally:
                server.BENCH.set_config(old_cfg)
                server.PROFILE["name"] = old_profile

    t = T()
    t.setUp()
    try:
        t.runTest()
    finally:
        t.tearDown()
