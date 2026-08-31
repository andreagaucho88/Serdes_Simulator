"""SerDes Optical Lab Pro — server Tornado.

Avvio:  cd simulatore && python -m labpro.server [--port 8640]

- REST: stato, config, preset, run/stop/reset, dati pannello
- WebSocket /ws: push di ogni record del LiveBench (contatori che si riempiono)
"""

from __future__ import annotations

import argparse
import inspect
import json
import shutil
import sys
import threading
from pathlib import Path

import tornado.ioloop
import tornado.web
import tornado.websocket

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from serdes_sim import LinkConfig, PRESETS, SWEEPABLE_FIELDS, sweep  # noqa: E402
from serdes_sim.engine import jitter_tolerance  # noqa: E402
from serdes_sim.livebench import LiveBench   # noqa: E402
from labpro import paneldata                 # noqa: E402

STATIC_DIR = Path(__file__).resolve().parent / "static"
PERSIST = Path(__file__).resolve().parent / ".labpro_session.json"

BENCH = LiveBench()
CLIENTS: set = set()
MAIN_LOOP = None
_persist_lock = threading.Lock()


def load_persisted():
    try:
        d = json.loads(PERSIST.read_text())
        d["cfg"]["tx_ffe_taps"] = tuple(d["cfg"]["tx_ffe_taps"])
        BENCH.set_config(LinkConfig(**d["cfg"]))
    except Exception:
        pass


def persist():
    with _persist_lock:
        try:
            tmp = PERSIST.with_suffix(".tmp")
            tmp.write_text(json.dumps({"cfg": BENCH.cfg.to_dict()}))
            tmp.replace(PERSIST)
        except Exception:
            pass


def broadcast(payload: dict):
    msg = json.dumps(payload)
    for c in list(CLIENTS):
        try:
            c.write_message(msg)
        except Exception:
            CLIENTS.discard(c)


def on_record(snapshot):
    if MAIN_LOOP is not None:
        MAIN_LOOP.add_callback(broadcast, {"type": "tick", "acc": snapshot})


BENCH.on_record = on_record


class Base(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Cache-Control", "no-store")

    def write_json(self, obj):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(obj))

    def body_json(self):
        try:
            return json.loads(self.request.body or b"{}")
        except Exception:
            return {}


class Index(Base):
    def get(self):
        self.write((STATIC_DIR / "index.html").read_text())


class ApiState(Base):
    def get(self):
        cfg = BENCH.cfg
        self.write_json({
            "cfg": cfg.to_dict(),
            "defaults": LinkConfig().to_dict(),
            "problems": cfg.validate(),
            "running": BENCH.running,
            "acc": paneldata.J(BENCH.snapshot()),
            "presets": [{"name": k, "desc": v[1]} for k, v in PRESETS.items()],
            "sweepable": {k: {"label": v[0], "lo": v[1], "hi": v[2]}
                          for k, v in SWEEPABLE_FIELDS.items()},
        })


class ApiSweep(Base):
    def post(self):
        body = self.body_json()
        field = body.get("field")
        if field not in SWEEPABLE_FIELDS:
            self.set_status(400)
            return self.write_json({"error": f"campo non sweepable: {field}"})
        lo = float(body.get("lo", SWEEPABLE_FIELDS[field][1]))
        hi = float(body.get("hi", SWEEPABLE_FIELDS[field][2]))
        n = max(3, min(int(body.get("n", 9)), 15))
        import numpy as np
        was_running = BENCH.running
        BENCH.stop()          # niente contesa CPU durante lo sweep
        try:
            rows = sweep(BENCH.cfg, field, np.linspace(lo, hi, n))
        except ValueError as exc:
            self.set_status(400)
            return self.write_json({"error": str(exc)})
        finally:
            if was_running:
                BENCH.start()
        self.write_json({"ok": True, "field": field,
                         "label": SWEEPABLE_FIELDS[field][0],
                         "rows": paneldata.J(rows)})


class ApiJtol(Base):
    def post(self):
        body = self.body_json()
        freqs = body.get("freqs_mhz") or [50, 200, 800, 2000]
        # sotto ~3 cicli per record la "tolleranza" misurerebbe solo un offset
        # quasi statico: il record è troppo corto (limite dichiarato)
        record_s = BENCH.cfg.n_symbols / BENCH.cfg.symbol_rate_hz
        f_min_mhz = 3.0 / record_s / 1e6
        freqs = [max(float(f), f_min_mhz) for f in freqs][:6]
        target = float(body.get("target_ber", 4e-2))
        was_running = BENCH.running
        BENCH.stop()
        try:
            points = jitter_tolerance(BENCH.cfg, freqs, target_ber=target)
        finally:
            if was_running:
                BENCH.start()
        ui_ps = 1e12 / BENCH.cfg.symbol_rate_hz
        for pt in points:
            pt["amp_ps"] = (pt["amp_ui"] * ui_ps
                            if pt.get("amp_ui") is not None else None)
        self.write_json({"ok": True, "target_ber": target,
                         "ui_ps": ui_ps, "points": paneldata.J(points)})


class ApiConfig(Base):
    def post(self):
        updates = self.body_json().get("updates", {})
        cfg = BENCH.cfg
        try:
            if "tx_ffe_taps" in updates:
                updates["tx_ffe_taps"] = tuple(updates["tx_ffe_taps"])
            new = cfg.with_updates(**updates)
        except TypeError as exc:
            self.set_status(400)
            return self.write_json({"error": f"campo sconosciuto: {exc}"})
        problems = new.validate()
        if problems:
            self.set_status(400)
            return self.write_json({"error": "; ".join(problems)})
        BENCH.set_config(new)
        persist()
        broadcast({"type": "config", "cfg": new.to_dict()})
        self.write_json({"ok": True, "cfg": new.to_dict()})


class ApiPreset(Base):
    def post(self):
        name = self.body_json().get("name")
        if name not in PRESETS:
            self.set_status(400)
            return self.write_json({"error": "preset sconosciuto"})
        BENCH.set_config(PRESETS[name][0])
        persist()
        broadcast({"type": "config", "cfg": BENCH.cfg.to_dict()})
        self.write_json({"ok": True, "cfg": BENCH.cfg.to_dict()})


class ApiRun(Base):
    def post(self):
        if self.body_json().get("running"):
            BENCH.start()
        else:
            BENCH.stop()
        broadcast({"type": "run", "running": BENCH.running})
        self.write_json({"ok": True, "running": BENCH.running})


class ApiReset(Base):
    def post(self):
        BENCH.reset_stats()
        broadcast({"type": "tick", "acc": paneldata.J(BENCH.snapshot())})
        self.write_json({"ok": True})


class ApiS2P(Base):
    def post(self):
        body = self.body_json()
        text = body.get("text", "")
        try:
            from serdes_sim.blocks.channel import (parse_touchstone_s2p_text,
                                                   sparameter_diagnostics)
            f, S, z0 = parse_touchstone_s2p_text(text)
            diag = sparameter_diagnostics(f, S).to_dict()
        except Exception as exc:
            self.set_status(400)
            return self.write_json({"error": str(exc)})
        if body.get("apply"):
            BENCH.set_config(BENCH.cfg.with_updates(
                s2p_text=text, s2p_name=body.get("name", "upload"),
                use_s2p_channel=True))
            persist()
            broadcast({"type": "config", "cfg": BENCH.cfg.to_dict()})
        self.write_json({"ok": True, "points": len(f), "z0": z0,
                         "diag": paneldata.J(diag)})


class ApiPanel(Base):
    def get(self, name):
        builder = paneldata.PANEL_BUILDERS.get(name)
        if builder is None:
            self.set_status(404)
            return self.write_json({"error": f"pannello sconosciuto: {name}"})
        cfg = BENCH.cfg
        source = self.get_argument("source", "auto")
        # live: ultimo record del bench (nuovo rumore); ref: sim full cache
        sim = None
        if source in ("auto", "live") and name in ("eye", "spectrum", "jitter"):
            sim = BENCH.latest
        if sim is None or sim.cfg != cfg:
            try:
                sim = paneldata.ref_sim(cfg)
            except ValueError as exc:
                self.set_status(400)
                return self.write_json({"error": str(exc)})
        kwargs = {}
        params = inspect.signature(builder).parameters
        if "node" in params:
            kwargs["node"] = self.get_argument("node", "vctle")
        if "n_traces" in params:
            kwargs["n_traces"] = int(self.get_argument("n", "500"))
        if "nperseg" in params:
            kwargs["nperseg"] = int(self.get_argument("nperseg", "4096"))
        try:
            self.write_json(builder(sim, cfg, **kwargs))
        except Exception as exc:
            self.set_status(500)
            self.write_json({"error": f"{type(exc).__name__}: {exc}"})


class WS(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self):
        CLIENTS.add(self)
        self.write_message(json.dumps({
            "type": "hello",
            "cfg": BENCH.cfg.to_dict(),
            "running": BENCH.running,
            "acc": paneldata.J(BENCH.snapshot()),
        }))

    def on_close(self):
        CLIENTS.discard(self)

    def on_message(self, message):
        pass  # il canale di comando è REST


def ensure_plotly():
    """Copia plotly.min.js dal pacchetto python (nessuna CDN)."""
    target = STATIC_DIR / "plotly.min.js"
    if not target.exists():
        import plotly
        src = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
        shutil.copy(src, target)


def make_app():
    return tornado.web.Application([
        (r"/", Index),
        (r"/api/state", ApiState),
        (r"/api/config", ApiConfig),
        (r"/api/preset", ApiPreset),
        (r"/api/run", ApiRun),
        (r"/api/reset", ApiReset),
        (r"/api/s2p", ApiS2P),
        (r"/api/experiment/sweep", ApiSweep),
        (r"/api/experiment/jtol", ApiJtol),
        (r"/api/panel/(\w+)", ApiPanel),
        (r"/ws", WS),
        (r"/static/(.*)", tornado.web.StaticFileHandler,
         {"path": str(STATIC_DIR)}),
    ])


def main():
    global MAIN_LOOP
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8640)
    parser.add_argument("--no-autostart", action="store_true",
                        help="non avviare l'acquisizione continua all'avvio")
    args = parser.parse_args()
    ensure_plotly()
    load_persisted()
    app = make_app()
    app.listen(args.port, address="127.0.0.1")
    MAIN_LOOP = tornado.ioloop.IOLoop.current()
    if not args.no_autostart:
        BENCH.start()
    print(f"SerDes Optical Lab Pro → http://localhost:{args.port}")
    MAIN_LOOP.start()


if __name__ == "__main__":
    main()
