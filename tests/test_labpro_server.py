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


def test_server_shutdown_stops_livebench_and_handles_process_signals(capsys):
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

    class SignalLoop:
        stopped = False

        def add_callback_from_signal(self, callback):
            callback()

        def stop(self):
            self.stopped = True

    registered = {}
    with patch.object(server.signal, "signal",
                      side_effect=lambda signum, handler:
                      registered.setdefault(signum, handler)):
        loop = SignalLoop()
        server._install_shutdown_handlers(loop)
    assert set(registered) == {server.signal.SIGINT, server.signal.SIGTERM}
    registered[server.signal.SIGTERM](server.signal.SIGTERM, None)
    assert loop.stopped


def test_state_file_environment_override_is_expanded(tmp_path):
    state_file = tmp_path / "private" / "session.json"
    with patch.dict(server.os.environ,
                    {"SERDES_LAB_STATE_FILE": str(state_file)}):
        assert server._default_state_path() == state_file


def test_persist_creates_private_parent_and_atomic_session(tmp_path):
    state_file = tmp_path / "new" / "state" / "session.json"
    old_error = server._persistence_error
    try:
        with patch.object(server, "PERSIST", state_file):
            assert server.persist() is True
            payload = json.loads(state_file.read_text(encoding="utf-8"))
            assert payload["version"] == server.SESSION_VERSION
            expected_cfg = json.loads(json.dumps(server.BENCH.cfg.to_dict()))
            assert payload["cfg"] == expected_cfg
            assert state_file.stat().st_mode & 0o777 == 0o600
            assert list(state_file.parent.iterdir()) == [state_file]
    finally:
        server._persistence_error = old_error


class ApiContractTest(AsyncHTTPTestCase):
    def get_app(self):
        return server.make_app()

    def test_state_ok(self):
        resp = self.fetch("/api/state")
        assert resp.code == 200
        d = json.loads(resp.body)
        for key in ("cfg", "defaults", "running", "acc",
                    "control_help", "action_help", "profiles", "persistence"):
            assert key in d, f"chiave mancante in /api/state: {key}"

    def test_health_is_lightweight_and_does_not_expose_local_paths(self):
        resp = self.fetch("/api/health")
        assert resp.code == 200
        d = json.loads(resp.body)
        assert d["status"] in {"ok", "degraded"}
        assert d["service"] == "serdes-optical-lab-pro"
        assert d["api_version"] == 1
        assert d["version"]
        assert set(d["persistence"]) == {"status", "restored"}
        assert str(server.PERSIST).encode() not in resp.body

    def test_health_reports_persistence_failure_as_degraded(self):
        with patch.object(server, "_persistence_error", "write_failed"):
            resp = self.fetch("/api/health")
        assert resp.code == 200
        d = json.loads(resp.body)
        assert d["status"] == "degraded"
        assert d["persistence"]["status"] == "error"

    def test_malformed_json_is_rejected_without_mutating_config(self):
        before = server.BENCH.cfg
        resp = self.fetch("/api/config", method="POST", body=b'{"updates":')
        assert resp.code == 400
        assert json.loads(resp.body)["error"] == "Bad request"
        assert server.BENCH.cfg == before

    def test_non_object_json_is_rejected(self):
        resp = self.fetch("/api/run", method="POST", body=b"[]")
        assert resp.code == 400
        assert json.loads(resp.body)["error"] == "Bad request"

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
        assert "security policy" in json.loads(resp.body)["error"]

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
        assert "security policy" in json.loads(resp.body)["error"]

    def test_oversized_request_body_is_rejected(self):
        with patch.object(server, "MAX_REQUEST_BODY_BYTES", 32):
            resp = self.fetch(
                "/api/config",
                method="POST",
                body=json.dumps({"updates": {"padding": "x" * 64}}),
            )
        assert resp.code == 413
        assert json.loads(resp.body)["error"] == "Request body too large"

    def test_oversized_touchstone_upload_is_rejected(self):
        with patch.object(server, "MAX_TOUCHSTONE_TEXT_BYTES", 16):
            resp = self.fetch(
                "/api/s2p",
                method="POST",
                body=json.dumps({"text": "x" * 17}),
            )
        assert resp.code == 413
        assert "8 MiB" in json.loads(resp.body)["error"]

    def test_json_transport_escapes_html_delimiters(self):
        def payload(_sim, _cfg):
            return {"value": "<script>alert('x')</script>"}

        with patch.dict(server.paneldata.PANEL_BUILDERS, {"education": payload}):
            resp = self.fetch("/api/panel/education")
        assert resp.code == 200
        assert b"<script>" not in resp.body
        assert "<script>" in json.loads(resp.body)["value"]

    def test_panel_failure_does_not_expose_exception_details(self):
        def fail(_sim, _cfg):
            raise RuntimeError("private /server/path and implementation detail")

        with patch.dict(server.paneldata.PANEL_BUILDERS, {"education": fail}):
            resp = self.fetch("/api/panel/education")
        assert resp.code == 500
        body = json.loads(resp.body)
        assert body["error"] == "errore interno del pannello"
        assert b"/server/path" not in resp.body
