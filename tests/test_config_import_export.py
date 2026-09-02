"""Import/export della configurazione + persistenza camera (iterazione 27).

Il file esportato è lo stesso formato della sessione persistita
({version, cfg completa, chamber}): rimportarlo deve riprodurre il banco
identico; i campi non più esistenti vengono scartati con nota, un file
invalido viene rifiutato senza toccare nulla.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tornado.testing import AsyncHTTPTestCase     # noqa: E402

from labpro import server                          # noqa: E402

DEFAULT_CHAMBER = dict(on=False, mode="cycle", t_min=-10.0, t_max=85.0,
                       period_s=180.0, tau_s=10.0)


class ConfigImportExportTest(AsyncHTTPTestCase):
    def get_app(self):
        return server.make_app()

    def setUp(self):
        super().setUp()
        self._cfg_before = server.BENCH.cfg
        self._profile_before = server.PROFILE["name"]
        self._chamber_before = server.BENCH.chamber_settings()
        # persist() viene chiamata dagli endpoint: mai sul file di sessione
        # REALE dell'utente durante i test
        self._persist_before = server.PERSIST
        self._tmp = tempfile.TemporaryDirectory()
        server.PERSIST = Path(self._tmp.name) / "session.json"

    def tearDown(self):
        server.PERSIST = self._persist_before
        self._tmp.cleanup()
        server.BENCH.set_config(self._cfg_before)
        server.PROFILE["name"] = self._profile_before
        server.BENCH.set_chamber(**self._chamber_before)
        super().tearDown()

    def test_config_patch_accepts_flat_and_legacy_nested_contracts(self):
        original = server.BENCH.cfg.channel_il_nyquist_db
        resp = self.fetch("/api/config", method="POST", body=json.dumps(
            {"channel_il_nyquist_db": original + 1.0}))
        assert resp.code == 200
        assert server.BENCH.cfg.channel_il_nyquist_db == original + 1.0
        resp = self.fetch("/api/config", method="POST", body=json.dumps(
            {"updates": {"channel_il_nyquist_db": original}}))
        assert resp.code == 200
        assert server.BENCH.cfg.channel_il_nyquist_db == original

    def test_config_patch_rejects_ambiguous_or_non_object_updates(self):
        before = server.BENCH.cfg
        for payload in ({"updates": {}, "fec_mode": "none"},
                        {"updates": ["not", "an", "object"]},
                        {"ctle_zeros_hz": ["not-a-number"]}):
            resp = self.fetch("/api/config", method="POST",
                              body=json.dumps(payload))
            assert resp.code == 400
            assert server.BENCH.cfg == before

    def test_export_import_roundtrip(self):
        resp = self.fetch("/api/config/export")
        assert resp.code == 200
        assert "attachment" in resp.headers.get("Content-Disposition", "")
        payload = json.loads(resp.body)
        assert payload["version"] == server.SESSION_VERSION
        assert set(server.CHAMBER_KEYS) == set(payload["chamber"])
        # modifica un campo, poi reimporta il file: il banco torna identico
        original = payload["cfg"]["channel_il_nyquist_db"]
        server.BENCH.set_config(server.BENCH.cfg.with_updates(
            channel_il_nyquist_db=original + 3.0))
        resp2 = self.fetch("/api/config/import", method="POST",
                           body=json.dumps(payload))
        assert resp2.code == 200, resp2.body
        d = json.loads(resp2.body)
        assert d["ok"] is True and d["dropped_fields"] == []
        assert server.BENCH.cfg.channel_il_nyquist_db == original

    def test_import_drops_obsolete_fields_with_note(self):
        payload = {"version": 1,
                   "cfg": {**server.BENCH.cfg.to_dict(),
                           "campo_del_2024_rimosso": 42}}
        resp = self.fetch("/api/config/import", method="POST",
                          body=json.dumps(payload))
        assert resp.code == 200, resp.body
        assert json.loads(resp.body)["dropped_fields"] == [
            "campo_del_2024_rimosso"]

    def test_import_rejects_payload_without_cfg(self):
        resp = self.fetch("/api/config/import", method="POST",
                          body=json.dumps({"version": 1}))
        assert resp.code == 400
        assert "cfg" in json.loads(resp.body)["error"]

    def test_import_rejects_invalid_values_without_touching_bench(self):
        before = server.BENCH.cfg
        payload = {"version": 1,
                   "cfg": {**before.to_dict(), "symbol_rate_hz": -1.0}}
        resp = self.fetch("/api/config/import", method="POST",
                          body=json.dumps(payload))
        assert resp.code == 400
        assert server.BENCH.cfg == before
        for bad_version in (0, 1.5, "not-a-version"):
            payload = {"version": bad_version, "cfg": before.to_dict()}
            resp = self.fetch("/api/config/import", method="POST",
                              body=json.dumps(payload))
            assert resp.code == 400
            assert server.BENCH.cfg == before

    def test_import_restores_chamber_settings(self):
        payload = {"version": 1, "cfg": server.BENCH.cfg.to_dict(),
                   "chamber": {"on": True, "mode": "soak", "t_max": 77.0}}
        resp = self.fetch("/api/config/import", method="POST",
                          body=json.dumps(payload))
        assert resp.code == 200
        ch = server.BENCH.chamber_settings()
        assert ch["on"] is True and ch["mode"] == "soak"
        assert ch["t_max"] == 77.0

    def test_chamber_validation_rejects_bad_types_ranges_and_unknown_fields(self):
        before = server.BENCH.chamber_settings()
        bad_payloads = [
            {"on": "false"},
            {"mode": "explode"},
            {"period_s": 1.0},
            {"t_min": 90.0, "t_max": 20.0},
            {"secret": 1},
        ]
        for payload in bad_payloads:
            resp = self.fetch("/api/chamber", method="POST",
                              body=json.dumps(payload))
            assert resp.code == 400, payload
            assert "error_en" in json.loads(resp.body)
            assert server.BENCH.chamber_settings() == before

    def test_import_is_transactional_when_chamber_is_invalid(self):
        before_cfg = server.BENCH.cfg
        before_profile = server.PROFILE["name"]
        before_chamber = server.BENCH.chamber_settings()
        payloads = [
            {"version": 1,
             "cfg": {**before_cfg.to_dict(), "channel_il_nyquist_db": 19.0},
             "profile": next(iter(server.STANDARD_PROFILES)),
             "chamber": {"mode": "unknown"}},
            {"version": 1,
             "cfg": {**before_cfg.to_dict(), "channel_il_nyquist_db": 19.0},
             "profile": "profile-that-does-not-exist",
             "chamber": before_chamber},
        ]
        for payload in payloads:
            resp = self.fetch("/api/config/import", method="POST",
                              body=json.dumps(payload))
            assert resp.code == 400
            assert server.BENCH.cfg == before_cfg
            assert server.PROFILE["name"] == before_profile
            assert server.BENCH.chamber_settings() == before_chamber


def test_session_file_persists_chamber(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "PERSIST", tmp_path / "session.json")
    cfg_before = server.BENCH.cfg
    try:
        server.BENCH.set_chamber(on=True, mode="ramp", t_max=70.0)
        server.persist()
        saved = json.loads(server.PERSIST.read_text())
        assert saved["chamber"]["mode"] == "ramp"
        # la camera cambia, poi il riavvio (load_persisted) la ripristina
        server.BENCH.set_chamber(on=False, mode="cycle", t_max=85.0)
        server.load_persisted()
        ch = server.BENCH.chamber_settings()
        assert ch["on"] is True and ch["mode"] == "ramp" and ch["t_max"] == 70.0
    finally:
        server.BENCH.set_config(cfg_before)
        server.BENCH.set_chamber(**DEFAULT_CHAMBER)


def test_invalid_persisted_chamber_cannot_partially_restore_session(tmp_path,
                                                                    monkeypatch):
    cfg_before = server.BENCH.cfg
    chamber_before = server.BENCH.chamber_settings()
    profile_before = server.PROFILE["name"]
    error_before = server._persistence_error
    loaded_before = server._persistence_loaded
    state_file = tmp_path / "session.json"
    state_file.write_text(json.dumps({
        "version": server.SESSION_VERSION,
        "cfg": {**cfg_before.to_dict(), "channel_il_nyquist_db": 18.0},
        "profile": next(iter(server.STANDARD_PROFILES)),
        "chamber": {"mode": "invalid"},
    }))
    monkeypatch.setattr(server, "PERSIST", state_file)
    try:
        assert server.load_persisted() is False
        assert server.BENCH.cfg == cfg_before
        assert server.PROFILE["name"] == profile_before
        assert server.BENCH.chamber_settings() == chamber_before
        assert server._persistence_error == "restore_failed"
        state_file.write_text(json.dumps({
            "version": 1.5,
            "cfg": {**cfg_before.to_dict(), "channel_il_nyquist_db": 18.0},
            "chamber": chamber_before,
        }))
        assert server.load_persisted() is False
        assert server.BENCH.cfg == cfg_before
    finally:
        server._persistence_error = error_before
        server._persistence_loaded = loaded_before
