"""Contratto HTTP del server Lab PRO (prima: 20 endpoint a copertura zero).

Verifica il contratto d'errore JSON ({"error": ...} su OGNI status, mai la
pagina HTML di Tornado che rompeva GET() lato client) e gli endpoint di stato
che non richiedono simulazioni costose.
"""

import json
import sys
from concurrent.futures import Future
from pathlib import Path
from urllib.parse import urlparse
from unittest.mock import patch

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


def test_initial_websocket_send_consumes_async_failure():
    """Il primo hello usa lo stesso guard del broadcast: un reload immediato
    non deve lasciare WebSocketClosedError non recuperate nel loop."""
    future = Future()

    class ClosingClient:
        def write_message(self, message):
            assert json.loads(message)["type"] == "hello"
            return future

    client = ClosingClient()
    before = set(server.CLIENTS)
    try:
        server.CLIENTS.add(client)
        server._ws_send(client, json.dumps({"type": "hello"}))
        assert client in server.CLIENTS
        future.set_exception(ConnectionError("closed during hello"))
        assert client not in server.CLIENTS
    finally:
        server.CLIENTS.clear()
        server.CLIENTS.update(before)


def test_server_ctrl_c_stops_livebench_without_propagating_interrupt(capsys):
    class InterruptingLoop:
        def start(self):
            raise KeyboardInterrupt

    class Bench:
        stopped = False

        def stop(self):
            self.stopped = True

    bench = Bench()
    server._serve_until_stopped(InterruptingLoop(), bench)
    assert bench.stopped
    assert "arrestato" in capsys.readouterr().out


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

    def test_cross_origin_mutation_is_rejected(self):
        parsed = urlparse(self.get_url("/"))
        other_loopback_origin = f"{parsed.scheme}://{parsed.hostname}:{parsed.port + 1}"
        resp = self.fetch(
            "/api/config",
            method="POST",
            headers={"Origin": other_loopback_origin},
            body=json.dumps({"updates": {}}),
        )
        assert resp.code == 403
        assert "cross-origin" in json.loads(resp.body)["error"]

    def test_loopback_origin_reaches_normal_api_validation(self):
        resp = self.fetch(
            "/api/config",
            method="POST",
            headers={"Origin": self.get_url("/").rstrip("/")},
            body=json.dumps({"updates": {"unknown_field": 1}}),
        )
        assert resp.code == 400
        assert "campo sconosciuto" in json.loads(resp.body)["error"]

    def test_non_loopback_host_is_rejected(self):
        resp = self.fetch("/api/state", headers={"Host": "attacker.example"})
        assert resp.code == 403
        assert "non-loopback" in json.loads(resp.body)["error"]

    def test_oversized_request_body_is_rejected(self):
        with patch.object(server, "MAX_REQUEST_BODY_BYTES", 32):
            resp = self.fetch(
                "/api/config",
                method="POST",
                body=json.dumps({"updates": {"padding": "x" * 64}}),
            )
        assert resp.code == 413
        assert "16 MiB" in json.loads(resp.body)["error"]

    def test_oversized_touchstone_upload_is_rejected(self):
        with patch.object(server, "MAX_TOUCHSTONE_TEXT_BYTES", 16):
            resp = self.fetch(
                "/api/s2p",
                method="POST",
                body=json.dumps({"text": "x" * 17}),
            )
        assert resp.code == 413
        assert "8 MiB" in json.loads(resp.body)["error"]
