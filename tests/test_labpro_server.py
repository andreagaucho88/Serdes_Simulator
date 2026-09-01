"""Contratto HTTP del server Lab PRO (prima: 20 endpoint a copertura zero).

Verifica il contratto d'errore JSON ({"error": ...} su OGNI status, mai la
pagina HTML di Tornado che rompeva GET() lato client) e gli endpoint di stato
che non richiedono simulazioni costose.
"""

import json
import sys
from concurrent.futures import Future
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tornado.testing import AsyncHTTPTestCase     # noqa: E402

from labpro import server                          # noqa: E402


def test_broadcast_removes_client_on_async_websocket_failure():
    """write_message fallisce su Future: non deve produrre task fantasma."""
    future = Future()

    class DeadClient:
        def write_message(self, message):
            json.loads(message)
            return future

    client = DeadClient()
    before = set(server.CLIENTS)
    try:
        server.CLIENTS.add(client)
        server.broadcast({"type": "tick", "acc": {}})
        assert client in server.CLIENTS
        future.set_exception(ConnectionError("closed"))
        assert client not in server.CLIENTS
    finally:
        server.CLIENTS.clear()
        server.CLIENTS.update(before)


class ApiContractTest(AsyncHTTPTestCase):
    def get_app(self):
        return server.make_app()

    def test_state_ok(self):
        resp = self.fetch("/api/state")
        assert resp.code == 200
        d = json.loads(resp.body)
        for key in ("cfg", "defaults", "running", "acc",
                    "control_help", "action_help", "profiles"):
            assert key in d, f"chiave mancante in /api/state: {key}"

    def test_unknown_panel_is_json_404(self):
        resp = self.fetch("/api/panel/pannello_inesistente")
        assert resp.code == 404
        assert "error" in json.loads(resp.body)

    def test_unknown_config_field_is_json_400(self):
        resp = self.fetch("/api/config", method="POST",
                          body=json.dumps({"updates": {"campo_inventato": 1}}))
        assert resp.code == 400
        assert "error" in json.loads(resp.body)

    def test_unknown_url_is_json_not_html(self):
        # write_error uniforme: anche i 404 di routing devono essere JSON
        resp = self.fetch("/api/inesistente")
        assert resp.code == 404
        body = resp.body.decode()
        assert not body.lstrip().startswith("<"), "pagina HTML al posto del JSON"
        assert "error" in json.loads(body)

    def test_invalid_traffic_body_is_json_400(self):
        resp = self.fetch("/api/experiment/traffic", method="POST",
                          body=json.dumps({"frame_sizes": []}))
        assert resp.code == 400
        assert "error" in json.loads(resp.body)

    def test_scope_rejects_bad_nodes(self):
        resp = self.fetch("/api/scope?nodes=nodo_finto")
        assert resp.code == 400
        assert "error" in json.loads(resp.body)
