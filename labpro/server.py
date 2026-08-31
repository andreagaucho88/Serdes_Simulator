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
from serdes_sim.config import STANDARD_PROFILES, STANDARD_PROFILE_META  # noqa: E402
from serdes_sim.engine import (anlt_session, jitter_tolerance, jitter_transfer,  # noqa: E402
                               l2_ont_report, link_train, traffic_sweep)
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
        for name in ("ctle_zeros_hz", "ctle_poles_hz"):
            if name in d["cfg"]:
                d["cfg"][name] = tuple(d["cfg"][name])
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
            "profiles": [{"name": k, "desc": v[1],
                          **STANDARD_PROFILE_META.get(k, {})}
                         for k, v in STANDARD_PROFILES.items()],
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
            for name in ("ctle_zeros_hz", "ctle_poles_hz"):
                if name in updates:
                    updates[name] = tuple(float(v) for v in updates[name])
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
        broadcast({"type": "tick", "acc": paneldata.J(BENCH.snapshot())})
        self.write_json({"ok": True, "cfg": new.to_dict()})


class ApiPreset(Base):
    def post(self):
        name = self.body_json().get("name")
        source = PRESETS if name in PRESETS else STANDARD_PROFILES
        if name not in source:
            self.set_status(400)
            return self.write_json({"error": "preset/profilo sconosciuto"})
        BENCH.set_config(source[name][0])
        persist()
        broadcast({"type": "config", "cfg": BENCH.cfg.to_dict()})
        broadcast({"type": "tick", "acc": paneldata.J(BENCH.snapshot())})
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
            from serdes_sim.blocks.channel import (parse_touchstone_text,
                                                   s4p_mixed_mode_21)
            import numpy as np
            f, S, z0, n_ports = parse_touchstone_text(text)
            if n_ports == 4:
                pairs = body.get("pairs", BENCH.cfg.s4p_pairs)
                sdd21, scd21 = s4p_mixed_mode_21(f, S, pairs)
                diag = {
                    "tipo": "s4p → mixed-mode",
                    "sdd21_nyq_db": float(20 * np.log10(max(
                        np.abs(np.interp(BENCH.cfg.nyquist_hz, f,
                                         np.abs(sdd21))), 1e-12))),
                    "scd21_max_db": float(20 * np.log10(max(
                        np.abs(scd21).max(), 1e-12))),
                    "conversione_di_modo":
                        "SCD21 alto = squilibrio P/N del canale",
                }
            else:
                from serdes_sim.blocks.channel import sparameter_diagnostics
                diag = {"tipo": "s2p"} | sparameter_diagnostics(f, S).to_dict()
        except Exception as exc:
            self.set_status(400)
            return self.write_json({"error": str(exc)})
        if body.get("apply"):
            updates = dict(s2p_text=text, s2p_name=body.get("name", "upload"),
                           use_s2p_channel=True)
            if n_ports == 4 and body.get("pairs"):
                updates["s4p_pairs"] = body["pairs"]
            BENCH.set_config(BENCH.cfg.with_updates(**updates))
            persist()
            broadcast({"type": "config", "cfg": BENCH.cfg.to_dict()})
        self.write_json({"ok": True, "points": len(f), "z0": z0,
                         "n_ports": n_ports, "diag": paneldata.J(diag)})



class ApiJtf(Base):
    def post(self):
        body = self.body_json()
        freqs = [float(f) for f in (body.get("freqs_mhz")
                                    or [10, 30, 60, 120, 300, 800])][:8]
        was_running = BENCH.running
        BENCH.stop()
        try:
            points = jitter_transfer(BENCH.cfg, freqs,
                                     amp_ui=float(body.get("amp_ui", 0.04)))
        except ValueError as exc:
            self.set_status(400)
            return self.write_json({"error": str(exc)})
        finally:
            if was_running:
                BENCH.start()
        self.write_json({"ok": True, "points": paneldata.J(points),
                         "loop_bw_mhz": BENCH.cfg.cdr_bw
                         * BENCH.cfg.symbol_rate_hz / 1e6})


class ApiAnlt(Base):
    def post(self):
        body = self.body_json()
        was_running = BENCH.running
        BENCH.stop()
        try:
            out = anlt_session(BENCH.cfg,
                               partner_abilities=body.get("partner_abilities"),
                               lt_rounds=int(body.get("lt_rounds", 6)))
        finally:
            if was_running and not body.get("apply"):
                BENCH.start()
        cfg_after = out.pop("cfg_after")
        if body.get("apply") and out["lt"]["link_up_after"]:
            BENCH.set_config(cfg_after)
            persist()
            broadcast({"type": "config", "cfg": cfg_after.to_dict()})
            broadcast({"type": "tick", "acc": paneldata.J(BENCH.snapshot())})
            if was_running:
                BENCH.start()
            out["applied"] = True
        else:
            out["applied"] = False
        self.write_json(paneldata.J({"ok": True, **out}))


class ApiOnt(Base):
    def post(self):
        body = self.body_json()
        grid = [int(v) for v in (body.get("ipg_grid")
                                 or [12, 96, 384, 1024, 2000])][:8]
        was_running = BENCH.running
        BENCH.stop()
        try:
            out = l2_ont_report(BENCH.cfg, ipg_grid=grid)
        finally:
            if was_running:
                BENCH.start()
        self.write_json(paneldata.J({"ok": True, **out}))


class ApiInject(Base):
    def post(self):
        body = self.body_json()
        n = int(body.get("bits", 10))
        BENCH.inject_errors(n, burst=bool(body.get("burst", False)))
        self.write_json({"ok": True, "bits": n})


class ApiTrain(Base):
    def post(self):
        was_running = BENCH.running
        BENCH.stop()
        try:
            new_cfg, steps, base, final = link_train(BENCH.cfg)
        except Exception:
            if was_running:
                BENCH.start()
            raise
        BENCH.set_config(new_cfg)
        persist()
        broadcast({"type": "config", "cfg": new_cfg.to_dict()})
        if was_running:
            BENCH.start()
        self.write_json({"ok": True, "steps": paneldata.J(steps),
                         "score_before": base, "score_after": final,
                         "verification_before": steps[-1].get("verification_before"),
                         "verification_after": steps[-1].get("verification_after"),
                         "accepted": steps[-1].get("accepted", True),
                         "cfg": new_cfg.to_dict()})


class ApiTraffic(Base):
    def post(self):
        body = self.body_json()
        sizes = body.get("frame_sizes") or [64, 128, 256, 512, 1024]
        if not isinstance(sizes, list) or not 1 <= len(sizes) <= 8:
            self.set_status(400)
            return self.write_json({"error": "frame_sizes deve contenere 1..8 valori"})
        was_running = BENCH.running
        BENCH.stop()
        try:
            rows = traffic_sweep(BENCH.cfg, sizes)
        except ValueError as exc:
            self.set_status(400)
            return self.write_json({"error": str(exc)})
        finally:
            if was_running:
                BENCH.start()
        self.write_json({"ok": True, "kind": "PHY frame-size benchmark",
                         "normative": False, "rows": paneldata.J(rows)})


class ApiPanel(Base):
    def get(self, name):
        builder = paneldata.PANEL_BUILDERS.get(name)
        if builder is None:
            self.set_status(404)
            return self.write_json({"error": f"pannello sconosciuto: {name}"})
        cfg, live_sim, records, _ = BENCH.capture()
        source = self.get_argument("source", "auto")
        # live: ultimo record del bench (nuovo rumore); ref: sim full cache
        sim = None
        source_used = "reference"
        if source in ("auto", "live") and name in (
                "eye", "spectrum", "jitter", "pd", "tia", "agc", "optical"):
            sim = live_sim
            if sim is not None and sim.cfg == cfg:
                source_used = "live"
        if name == "education":
            sim = None  # catalogo statico: nessuna simulazione costosa
            source_used = "static"
        elif sim is None or sim.cfg != cfg:
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
            payload = builder(sim, cfg, **kwargs)
            if isinstance(payload, dict):
                payload["_acquisition"] = {
                    "seed": (int(sim.seed) if sim is not None else None),
                    "depth": (sim.depth if sim is not None else None),
                    "source": source_used,
                    "records": records,
                }
            self.write_json(payload)
        except Exception as exc:
            self.set_status(500)
            self.write_json({"error": f"{type(exc).__name__}: {exc}"})


class ApiScope(Base):
    """Acquisizione DCA coerente: fino a quattro nodi dallo stesso record."""
    def get(self):
        requested = [v.strip() for v in self.get_argument(
            "nodes", "vctle").split(",") if v.strip()]
        if not requested or len(requested) > 4 or any(
                n not in paneldata.NODES for n in requested):
            self.set_status(400)
            return self.write_json({"error": "nodes richiede 1..4 nodi validi"})
        cfg, live_sim, records, running = BENCH.capture()
        source = self.get_argument("source", "auto")
        sim = live_sim if source in ("auto", "live") else None
        source_used = "live"
        if sim is None or sim.cfg != cfg:
            sim = paneldata.ref_sim(cfg)
            source_used = "reference"
        try:
            channels = [paneldata.eye_panel(sim, cfg, node=n,
                                             n_traces=min(int(self.get_argument(
                                                 "n", "600")), 800))
                        for n in requested]
        except Exception as exc:
            self.set_status(400)
            return self.write_json({"error": f"{type(exc).__name__}: {exc}"})
        self.write_json({
            "channels": channels,
            "coherent": True,
            "running": running,
            "_acquisition": {"seed": int(sim.seed), "depth": sim.depth,
                             "source": source_used, "records": records},
        })


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
        (r"/api/experiment/train", ApiTrain),
        (r"/api/experiment/jtf", ApiJtf),
        (r"/api/experiment/traffic", ApiTraffic),
        (r"/api/experiment/anlt", ApiAnlt),
        (r"/api/experiment/ont", ApiOnt),
        (r"/api/inject", ApiInject),
        (r"/api/scope", ApiScope),
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
