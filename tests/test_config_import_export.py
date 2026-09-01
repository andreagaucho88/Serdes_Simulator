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
        # persist() viene chiamata dagli endpoint: mai sul file di sessione
        # REALE dell'utente durante i test
        self._persist_before = server.PERSIST
        self._tmp = tempfile.TemporaryDirectory()
        server.PERSIST = Path(self._tmp.name) / "session.json"

    def tearDown(self):
        server.PERSIST = self._persist_before
        self._tmp.cleanup()
        server.BENCH.set_config(self._cfg_before)
        server.BENCH.set_chamber(**DEFAULT_CHAMBER)
        super().tearDown()

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

    def test_import_restores_chamber_settings(self):
        payload = {"version": 1, "cfg": server.BENCH.cfg.to_dict(),
                   "chamber": {"on": True, "mode": "soak", "t_max": 77.0}}
        resp = self.fetch("/api/config/import", method="POST",
                          body=json.dumps(payload))
        assert resp.code == 200
        ch = server.BENCH.chamber_settings()
        assert ch["on"] is True and ch["mode"] == "soak"
        assert ch["t_max"] == 77.0


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
