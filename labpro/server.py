"""SerDes Optical Lab Pro — server Tornado.

Avvio:  cd simulatore && python -m labpro.server [--port 8640]

- REST: stato, config, preset, run/stop/reset, dati pannello
- WebSocket /ws: push di ogni record del LiveBench (contatori che si riempiono)
"""

from __future__ import annotations

import argparse
import dataclasses
import inspect
import json
import math
import logging
import os
import signal
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import PackageNotFoundError, version as distribution_version
from pathlib import Path
from urllib.parse import urlparse

import tornado.ioloop
import tornado.web
import tornado.websocket

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from serdes_sim import LinkConfig, PRESETS, SWEEPABLE_FIELDS, sweep  # noqa: E402
from serdes_sim.config import (STANDARD_PROFILES, STANDARD_PROFILE_META,  # noqa: E402
                               field_schema)
from serdes_sim.standards import jtol_context_mask_ui  # noqa: E402
from serdes_sim.engine import (ExperimentCancelled, anlt_session,  # noqa: E402
                               jitter_tolerance, jitter_transfer,
                               l2_ont_report, link_train,
                               rx_sensitivity_search, stressed_eye_calibrate,
                               traffic_sweep)
from serdes_sim.procedures import run_dr4_tdecq_e2e  # noqa: E402
from serdes_sim.livebench import (BertNotRunning, InjectionInProgress,  # noqa: E402
                                  LiveBench)
from labpro import paneldata                 # noqa: E402
from labpro.action_help import ACTION_HELP   # noqa: E402
from labpro.control_help import CONTROL_HELP  # noqa: E402

STATIC_DIR = Path(__file__).resolve().parent / "static"
LEGACY_PERSIST = Path(__file__).resolve().parent / ".labpro_session.json"
SESSION_VERSION = 1     # bump se il formato del payload cambia in modo incompatibile


def _default_state_path() -> Path:
    """Return a writable, per-user session path for source and wheel installs."""
    override = os.environ.get("SERDES_LAB_STATE_FILE")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
        return root / "SerDes Optical Lab PRO" / "session.json"
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / "SerDes Optical Lab PRO" / "session.json"
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / "serdes-optical-lab" / "session.json"


DEFAULT_PERSIST = _default_state_path()
PERSIST: Path | None = DEFAULT_PERSIST

BENCH = LiveBench()
# Profilo IEEE/OIF caricato per ultimo: le manopole non lo azzerano, il
# pannello Compliance mostra "profilo · modificato: campi" invece di "custom".
PROFILE = {"name": None}
# Ultimo report della procedura DR4 (entra nel report di conformità).
LAST_DR4 = {"report": None}
CLIENTS: set = set()
MAIN_LOOP = None
_persist_lock = threading.Lock()
_persistence_loaded = False
_persistence_error = None
log = logging.getLogger("labpro")


CHAMBER_KEYS = ("on", "mode", "t_min", "t_max", "period_s", "tau_s")
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
MAX_REQUEST_BODY_BYTES = 16 * 1024 * 1024
MAX_TOUCHSTONE_TEXT_BYTES = 8 * 1024 * 1024
HTTP_ERROR_MESSAGES = {
    400: "Bad request",
    403: "Request rejected by the local security policy",
    404: "Not found",
    413: "Request body too large",
}


def _is_loopback_endpoint(value: str) -> bool:
    """Accept localhost URLs and Host headers, never public/rebound hosts."""
    try:
        parsed = urlparse(value if "://" in value else f"//{value}")
        return parsed.hostname in LOOPBACK_HOSTS
    except ValueError:
        return False


def _is_same_loopback_origin(origin: str, protocol: str, host: str) -> bool:
    """Require browser mutations and sockets to originate from this server."""
    try:
        parsed = urlparse(origin)
        return (
            parsed.scheme == protocol
            and parsed.netloc.lower() == host.lower()
            and parsed.hostname in LOOPBACK_HOSTS
        )
    except ValueError:
        return False


def _json_payload(obj) -> bytes:
    """Encode JSON without literal HTML delimiters, safe even if embedded."""
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("&", "\\u0026")
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e")
    return payload.encode("utf-8")


def config_from_dict(cfg_d: dict):
    """Ricostruisce una LinkConfig da un dict esterno (sessione o import).

    LinkConfig cresce di iterazione in iterazione: i campi rimossi non devono
    buttare via TUTTA la config. Ritorna (cfg, campi_scartati)."""
    known = {f.name for f in dataclasses.fields(LinkConfig)}
    dropped = sorted(set(cfg_d) - known)
    cfg_d = {k: v for k, v in cfg_d.items() if k in known}
    if "tx_ffe_taps" in cfg_d:
        cfg_d["tx_ffe_taps"] = tuple(cfg_d["tx_ffe_taps"])
    for name in ("ctle_zeros_hz", "ctle_poles_hz"):
        if name in cfg_d:
            cfg_d[name] = tuple(cfg_d[name])
    return LinkConfig(**cfg_d), dropped


def public_cfg(cfg) -> dict:
    """Config per il client: il testo Touchstone (fino a 8 MiB) non viaggia
    in ogni broadcast; resta nell'export e nella sessione persistita."""
    d = cfg.to_dict()
    text = d.get("s2p_text") or ""
    d["s2p_text"] = ""
    d["s2p_bytes"] = len(text.encode("utf-8")) if text else 0
    return d


def profile_state() -> dict:
    """Profilo attivo e campi modificati (per topbar e pannello Compliance)."""
    ctx = paneldata.profile_context(BENCH.cfg, PROFILE["name"])
    return {"name": ctx["name"], "interface": ctx["interface"],
            "modified_fields": ctx["modified_fields"],
            "modified": ctx["modified"]}


def _reject_json_constant(name):
    raise ValueError(f"JSON constant {name} is not allowed")


class BadParam(ValueError):
    """Parametro di richiesta non valido: risposta 400 bilingue."""

    def __init__(self, it, en):
        super().__init__(en)
        self.it, self.en = it, en


def as_number(value, name, lo=None, hi=None, integer=False, default=None):
    """Coercizione con range → BadParam (400) invece di TypeError (500)."""
    if value is None:
        if default is None:
            raise BadParam(f"{name} mancante", f"{name} missing")
        return default
    try:
        if isinstance(value, bool):
            raise ValueError
        v = int(value) if integer else float(value)
        if integer and float(value) != v:
            raise ValueError
    except (TypeError, ValueError):
        raise BadParam(f"{name} non è un numero valido",
                       f"{name} is not a valid number") from None
    if not math.isfinite(v):
        raise BadParam(f"{name} deve essere finito", f"{name} must be finite")
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        raise BadParam(f"{name} fuori range [{lo}, {hi}]",
                       f"{name} out of range [{lo}, {hi}]")
    return v


def persistence_status() -> dict:
    """Public persistence state without exposing the user's filesystem path."""
    if PERSIST is None:
        return {"status": "disabled", "restored": False}
    return {
        "status": "error" if _persistence_error is not None else "ready",
        "restored": _persistence_loaded,
    }


def load_persisted():
    global _persistence_error, _persistence_loaded
    _persistence_loaded = False
    _persistence_error = None
    if PERSIST is None:
        return False
    source = PERSIST
    # One-way compatibility for source checkouts used before 0.1.3. The old
    # package-local file is retained as a recoverable backup, never deleted.
    if not source.exists() and source == DEFAULT_PERSIST and LEGACY_PERSIST.exists():
        source = LEGACY_PERSIST
    if not source.exists():
        return False
    try:
        d = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(d, dict) or not isinstance(d.get("cfg", {}), dict):
            raise ValueError("session payload must be a JSON object")
        if int(d.get("version", SESSION_VERSION)) != SESSION_VERSION:
            raise ValueError("unsupported session version")
        cfg, dropped = config_from_dict(d.get("cfg", {}))
        problems = cfg.validate()
        if problems:
            raise ValueError("persisted config invalid: " + "; ".join(problems))
        BENCH.set_config(cfg)
        PROFILE["name"] = (d.get("profile")
                           if d.get("profile") in STANDARD_PROFILES else None)
        chamber = d.get("chamber")
        if isinstance(chamber, dict):
            BENCH.set_chamber(**{k: v for k, v in chamber.items()
                                 if k in CHAMBER_KEYS})
        if dropped:
            log.warning("sessione ripristinata ignorando campi non più esistenti: %s",
                        ", ".join(dropped))
        _persistence_loaded = True
        if source == LEGACY_PERSIST:
            persist()
        return True
    except Exception:
        _persistence_error = "restore_failed"
        log.warning("sessione %s non ripristinabile: si riparte dai default",
                    source.name, exc_info=True)
        return False


def persist():
    global _persistence_error
    if PERSIST is None:
        return True
    with _persist_lock:
        tmp = None
        try:
            PERSIST.parent.mkdir(parents=True, exist_ok=True)
            tmp = PERSIST.with_name(f".{PERSIST.name}.{os.getpid()}.tmp")
            tmp.write_text(
                json.dumps({"version": SESSION_VERSION,
                            "cfg": BENCH.cfg.to_dict(),
                            "chamber": BENCH.chamber_settings(),
                            "profile": PROFILE["name"]}),
                encoding="utf-8")
            tmp.chmod(0o600)
            tmp.replace(PERSIST)
            _persistence_error = None
            return True
        except Exception:
            _persistence_error = "write_failed"
            if tmp is not None:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
            log.warning("persistenza sessione fallita", exc_info=True)
            if MAIN_LOOP is not None:
                try:
                    MAIN_LOOP.add_callback(
                        broadcast,
                        {"type": "warning", "code": "session_persistence"})
                except Exception:
                    log.debug("persistence warning could not be queued",
                              exc_info=True)
            return False


def _ws_write_done(client, future):
    """Rimuove client morti anche quando write_message fallisce async.

    Tornado restituisce un Future: il try/except sincrono da solo non vedeva
    StreamClosedError e ogni tick produceva una task exception non recuperata.
    """
    try:
        future.result()
    except Exception:
        CLIENTS.discard(client)


def _ws_send(client, message):
    """Invia e consuma SEMPRE l'esito asincrono di write_message.

    Vale sia per i broadcast sia per l'hello iniziale: un reload rapido può
    chiudere il socket proprio mentre ``open()`` sta ancora consegnando il
    primo frame, producendo altrimenti ``Task exception was never retrieved``.
    """
    try:
        future = client.write_message(message)
        if future is not None:
            future.add_done_callback(
                lambda done, ws_client=client: _ws_write_done(ws_client, done))
        return future
    except Exception:
        CLIENTS.discard(client)
        return None


def broadcast(payload: dict):
    msg = json.dumps(payload)
    for c in list(CLIENTS):
        _ws_send(c, msg)


# --- worker pool degli esperimenti -----------------------------------------
# Le procedure lunghe (sweep/JTOL/JTF/AN-LT/ONT/train/traffic/DR4) giravano
# DENTRO il thread dell'IOLoop: server congelato per l'intera durata, niente
# tick WS, nessun altro pannello, nessuna cancellazione. Ora girano in un
# worker dedicato (uno solo: gli esperimenti si serializzano, come sul banco
# vero) con token di cancellazione cooperativo; le sim di riferimento dei
# pannelli hanno un worker separato così un DR4 non blocca lo Scope.
EXPERIMENT_POOL = ThreadPoolExecutor(max_workers=1,
                                     thread_name_prefix="experiment")
REF_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="refsim")


class ExperimentRegistry:
    """Un solo esperimento alla volta, cancellabile da /api/experiment/cancel."""

    def __init__(self):
        self._lock = threading.Lock()
        self._name = None
        self._evt = None

    def begin(self, name):
        with self._lock:
            if self._name is not None:
                return None
            self._name = name
            self._evt = threading.Event()
            return self._evt

    def end(self):
        with self._lock:
            self._name = None
            self._evt = None

    def cancel(self):
        with self._lock:
            if self._evt is None:
                return False
            self._evt.set()
            return True

    @property
    def current(self):
        with self._lock:
            return self._name


EXPERIMENT = ExperimentRegistry()


async def run_experiment(handler, name, fn, restart=True):
    """Esegue fn(cancel_event) nel worker pool degli esperimenti.

    Ferma il bench dentro il worker (l'IOLoop resta libero), lo riavvia alla
    fine se era in RUN — salvo restart=False: il chiamante gestisce il
    riavvio da sé (es. AN/LT/train che prima applicano la config).
    Ritorna (result, ok); con ok=False la risposta è già stata scritta
    (409 esperimento concorrente, oppure 400 annullato dall'utente).
    """
    evt = EXPERIMENT.begin(name)
    if evt is None:
        handler.set_status(409)
        handler.write_json(
            {"error": f"esperimento già in corso: {EXPERIMENT.current}"})
        return None, False
    was_running = BENCH.running
    broadcast({"type": "experiment", "name": name, "state": "start"})
    try:
        def work():
            BENCH.stop()          # niente contesa CPU durante l'esperimento
            return fn(evt)
        result = await tornado.ioloop.IOLoop.current().run_in_executor(
            EXPERIMENT_POOL, work)
        return result, True
    except ExperimentCancelled:
        handler.set_status(400)
        handler.write_json({"error": f"{name}: annullato dall'utente",
                            "cancelled": True})
        return None, False
    finally:
        EXPERIMENT.end()
        if restart and was_running:
            BENCH.start()
        broadcast({"type": "experiment", "name": name, "state": "end"})


def cfg_matches_live(sim, cfg):
    """La sim live coincide con la config del banco a meno dei campi
    VOLATILI per-record (temperatura della camera climatica, error
    insertion one-shot): senza questa normalizzazione, con la camera
    attiva tutti i pannelli ricadrebbero sulla reference."""
    if sim is None:
        return False
    return sim.cfg.with_updates(
        pvt_temp_c=cfg.pvt_temp_c,
        err_insert_bits=cfg.err_insert_bits,
        err_insert_burst=cfg.err_insert_burst,
        err_insert_target=cfg.err_insert_target) == cfg


def on_record(snapshot):
    if MAIN_LOOP is not None:
        MAIN_LOOP.add_callback(broadcast,
                               {"type": "tick", "acc": paneldata.J(snapshot)})


BENCH.on_record = on_record


class Base(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Cache-Control", "no-store")
        self.set_header("X-Content-Type-Options", "nosniff")

    def prepare(self):
        if not _is_loopback_endpoint(self.request.host):
            raise tornado.web.HTTPError(403, "non-loopback Host rejected")
        if len(self.request.body) > MAX_REQUEST_BODY_BYTES:
            raise tornado.web.HTTPError(413, "request body exceeds 16 MiB")
        if self.request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = self.request.headers.get("Origin")
            if origin and not _is_same_loopback_origin(
                origin, self.request.protocol, self.request.host
            ):
                raise tornado.web.HTTPError(403, "cross-origin mutation rejected")

    def write_json(self, obj):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        self.finish(_json_payload(obj))

    def body_json(self):
        try:
            body = json.loads(self.request.body or b"{}",
                              parse_constant=_reject_json_constant)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            raise tornado.web.HTTPError(400, "malformed JSON body") from None
        if not isinstance(body, dict):
            raise tornado.web.HTTPError(400, "JSON body must be an object")
        return body

    def int_arg(self, name, default, lo=None, hi=None):
        return as_number(self.get_argument(name, None), name, lo, hi,
                         integer=True, default=default)

    def float_arg(self, name, default, lo=None, hi=None):
        return as_number(self.get_argument(name, None), name, lo, hi,
                         default=default)

    def write_bad(self, it, en):
        self.set_status(400)
        self.write_json({"error": it, "error_it": it, "error_en": en})

    def _handle_request_exception(self, e):
        if isinstance(e, BadParam):
            if not self._finished:
                self.write_bad(e.it, e.en)
            return
        super()._handle_request_exception(e)

    def write_error(self, status_code, **kwargs):
        # contratto d'errore UNIFORME: sempre {"error": ...} — la pagina HTML
        # 500 di Tornado rompeva GET() lato client ("Unexpected token '<'")
        exc_info = kwargs.get("exc_info")
        if status_code >= 500 and exc_info:
            log.error("Unhandled HTTP request failure", exc_info=exc_info)
        err = HTTP_ERROR_MESSAGES.get(status_code, "Internal server error")
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        self.finish(_json_payload({"error": err}))


class NotFound(Base):
    """Route inesistente → 404 JSON (mai la pagina HTML di Tornado)."""

    def prepare(self):
        raise tornado.web.HTTPError(404)


class Index(Base):
    def get(self):
        self.write((STATIC_DIR / "index.html").read_text())


def _package_version() -> str:
    try:
        return distribution_version("serdes-optical-lab")
    except PackageNotFoundError:
        return "development"


class ApiHealth(Base):
    """Cheap readiness/support endpoint; never starts a simulation."""

    def get(self):
        persistence = persistence_status()
        self.write_json({
            "status": "degraded" if persistence["status"] == "error" else "ok",
            "service": "serdes-optical-lab-pro",
            "version": _package_version(),
            "api_version": 1,
            "running": BENCH.running,
            "experiment": EXPERIMENT.current,
            "persistence": persistence,
        })


class ApiState(Base):
    def get(self):
        cfg = BENCH.cfg
        self.write_json({
            "cfg": public_cfg(cfg),
            "defaults": LinkConfig().to_dict(),
            "problems": cfg.validate(),
            "profile": profile_state(),
            "field_schema": field_schema(),
            "running": BENCH.running,
            "acc": paneldata.J(BENCH.snapshot()),
            "presets": [{"name": k, "desc": v[1]} for k, v in PRESETS.items()],
            "profiles": [{"name": k, "desc": v[1],
                          **STANDARD_PROFILE_META.get(k, {})}
                         for k, v in STANDARD_PROFILES.items()],
            "sweepable": {k: {"label": v[0], "lo": v[1], "hi": v[2]}
                          for k, v in SWEEPABLE_FIELDS.items()},
            "control_help": CONTROL_HELP,
            "action_help": ACTION_HELP,
            "experiment": EXPERIMENT.current,
            "persistence": persistence_status(),
        })


class ApiSweep(Base):
    async def post(self):
        body = self.body_json()
        field = body.get("field")
        if field not in SWEEPABLE_FIELDS:
            self.set_status(400)
            return self.write_json({"error": f"campo non sweepable: {field}"})
        lo = as_number(body.get("lo"), "lo", default=SWEEPABLE_FIELDS[field][1])
        hi = as_number(body.get("hi"), "hi", default=SWEEPABLE_FIELDS[field][2])
        n = as_number(body.get("n"), "n", 3, 15, integer=True, default=9)
        if hi <= lo:
            raise BadParam("hi deve essere > lo", "hi must be > lo")
        import numpy as np
        cfg = BENCH.cfg
        try:
            rows, ok = await run_experiment(
                self, "sweep",
                lambda evt: sweep(cfg, field, np.linspace(lo, hi, n),
                                  cancel=evt))
        except ValueError:
            self.set_status(400)
            return self.write_json({"error": "parametri sweep non validi"})
        if not ok:
            return
        self.write_json({"ok": True, "field": field,
                         "label": SWEEPABLE_FIELDS[field][0],
                         "rows": paneldata.J(rows)})


class ApiJtol(Base):
    async def post(self):
        body = self.body_json()
        freqs = body.get("freqs_mhz") or [50, 200, 800, 2000]
        if not isinstance(freqs, list):
            raise BadParam("freqs_mhz deve essere una lista", "freqs_mhz must be a list")
        # sotto ~3 cicli per record la "tolleranza" misurerebbe solo un offset
        # quasi statico: il record è troppo corto (limite dichiarato)
        record_s = BENCH.cfg.n_symbols / BENCH.cfg.symbol_rate_hz
        f_min_mhz = 3.0 / record_s / 1e6
        freqs = [max(as_number(f, "freqs_mhz", 0.001, 1e5), f_min_mhz)
                 for f in freqs][:6]
        target = as_number(body.get("target_ber"), "target_ber", 1e-9, 0.49,
                           default=4e-2)
        mask_floor = as_number(body.get("mask_floor_ui"), "mask_floor_ui",
                               0.001, 5.0, default=None) if body.get("mask_floor_ui") is not None else None
        mask_corner = (as_number(body.get("mask_corner_mhz"), "mask_corner_mhz",
                                 0.001, 1e5)
                       if body.get("mask_corner_mhz") is not None else None)
        cfg = BENCH.cfg
        points, ok = await run_experiment(
            self, "JTOL",
            lambda evt: jitter_tolerance(cfg, freqs, target_ber=target,
                                         cancel=evt))
        if not ok:
            return
        ui_ps = 1e12 / BENCH.cfg.symbol_rate_hz
        corner = mask_corner or (BENCH.cfg.cdr_bw * BENCH.cfg.symbol_rate_hz / 1e6)
        for pt in points:
            pt["amp_ps"] = (pt["amp_ui"] * ui_ps
                            if pt.get("amp_ui") is not None else None)
            pt["mask_ui"] = jtol_context_mask_ui(pt["freq_mhz"], corner, mask_floor)
            pt["above_mask"] = (pt["amp_ui"] is not None
                                and pt["amp_ui"] >= pt["mask_ui"])
        self.write_json({"ok": True, "target_ber": target,
                         "ui_ps": ui_ps, "points": paneldata.J(points),
                         "mask": {"kind": "context", "normative": False,
                                  "floor_ui": (mask_floor if mask_floor is not None
                                               else jtol_context_mask_ui(1e9, corner)),
                                  "corner_mhz": corner,
                                  "slope_db_per_decade": -20.0}})


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
        except TypeError:
            return self.write_bad("campo sconosciuto o valore non valido",
                                  "unknown field or invalid value")
        try:
            problems = new.validate()
        except (TypeError, ValueError):
            problems = ["valore di tipo non valido"]
        if problems:
            return self.write_bad("; ".join(problems), "; ".join(problems))
        BENCH.set_config(new)
        persist()
        broadcast({"type": "config", "cfg": public_cfg(new),
                   "profile": profile_state()})
        broadcast({"type": "tick", "acc": paneldata.J(BENCH.snapshot())})
        self.write_json({"ok": True, "cfg": public_cfg(new),
                         "profile": profile_state()})


class ApiConfigExport(Base):
    def get(self):
        import time as _time
        payload = {"version": SESSION_VERSION,
                   "exported_at": _time.strftime("%Y-%m-%d %H:%M:%S"),
                   "cfg": BENCH.cfg.to_dict(),
                   "chamber": BENCH.chamber_settings(),
                   "profile": PROFILE["name"]}
        self.set_header("Content-Type", "application/json")
        self.set_header(
            "Content-Disposition",
            f'attachment; filename="labpro_config_'
            f'{_time.strftime("%Y%m%d_%H%M%S")}.json"')
        self.write(json.dumps(payload, indent=1))


class ApiConfigImport(Base):
    def post(self):
        body = self.body_json()
        cfg_d = body.get("cfg")
        if not isinstance(cfg_d, dict) or not cfg_d:
            self.set_status(400)
            return self.write_json(
                {"error": "payload senza 'cfg': usare un file esportato "
                          "dal banco (⤓ CFG)"})
        file_version = body.get("version")
        if file_version is not None:
            try:
                if int(file_version) > SESSION_VERSION:
                    return self.write_bad(
                        f"file di versione {file_version}: più recente di questo LabPro ({SESSION_VERSION})",
                        f"file version {file_version}: newer than this LabPro ({SESSION_VERSION})")
            except (TypeError, ValueError):
                return self.write_bad("campo version non valido", "invalid version field")
        try:
            new, dropped = config_from_dict(cfg_d)
        except (TypeError, ValueError):
            return self.write_bad("config non valida", "invalid config")
        try:
            problems = new.validate()
        except (TypeError, ValueError):
            problems = ["valore di tipo non valido"]
        if problems:
            return self.write_bad("; ".join(problems), "; ".join(problems))
        BENCH.set_config(new)
        PROFILE["name"] = (body.get("profile")
                           if body.get("profile") in STANDARD_PROFILES else None)
        chamber = body.get("chamber")
        if isinstance(chamber, dict):
            BENCH.set_chamber(**{k: v for k, v in chamber.items()
                                 if k in CHAMBER_KEYS})
        persist()
        broadcast({"type": "config", "cfg": public_cfg(new),
                   "profile": profile_state()})
        broadcast({"type": "tick", "acc": paneldata.J(BENCH.snapshot())})
        self.write_json({"ok": True, "cfg": public_cfg(new),
                         "profile": profile_state(),
                         "dropped_fields": dropped,
                         "file_version": file_version})


class ApiPreset(Base):
    def post(self):
        name = self.body_json().get("name")
        source = PRESETS if name in PRESETS else STANDARD_PROFILES
        if name not in source:
            self.set_status(400)
            return self.write_json({"error": "preset/profilo sconosciuto"})
        BENCH.set_config(source[name][0])
        PROFILE["name"] = name if source is STANDARD_PROFILES else None
        persist()
        broadcast({"type": "config", "cfg": public_cfg(BENCH.cfg),
                   "profile": profile_state()})
        broadcast({"type": "tick", "acc": paneldata.J(BENCH.snapshot())})
        self.write_json({"ok": True, "cfg": public_cfg(BENCH.cfg),
                         "profile": profile_state()})


class ApiRun(Base):
    async def post(self):
        if self.body_json().get("running"):
            BENCH.start()
        else:
            # stop() attende il record in volo (fino a 3 s): fuori dall'IOLoop
            await tornado.ioloop.IOLoop.current().run_in_executor(
                None, BENCH.stop)
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
        if not isinstance(text, str):
            self.set_status(400)
            return self.write_json({"error": "Touchstone text must be a string"})
        if len(text.encode("utf-8")) > MAX_TOUCHSTONE_TEXT_BYTES:
            self.set_status(413)
            return self.write_json({"error": "Touchstone upload exceeds 8 MiB"})
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
        except Exception:
            log.info("Touchstone input rejected", exc_info=True)
            self.set_status(400)
            return self.write_json({"error": "Touchstone non valido o non supportato"})
        if body.get("apply"):
            updates = dict(s2p_text=text, s2p_name=body.get("name", "upload"),
                           use_s2p_channel=True)
            if n_ports == 4 and body.get("pairs"):
                updates["s4p_pairs"] = body["pairs"]
            BENCH.set_config(BENCH.cfg.with_updates(**updates))
            persist()
            broadcast({"type": "config", "cfg": public_cfg(BENCH.cfg),
                       "profile": profile_state()})
        self.write_json({"ok": True, "points": len(f), "z0": z0,
                         "n_ports": n_ports, "diag": paneldata.J(diag)})



class ApiJtf(Base):
    async def post(self):
        body = self.body_json()
        freqs = [float(f) for f in (body.get("freqs_mhz")
                                    or [10, 30, 60, 120, 300, 800])][:8]
        cfg = BENCH.cfg
        try:
            points, ok = await run_experiment(
                self, "JTF",
                lambda evt: jitter_transfer(
                    cfg, freqs, amp_ui=float(body.get("amp_ui", 0.04)),
                    cancel=evt))
        except ValueError:
            self.set_status(400)
            return self.write_json({"error": "parametri JTF non validi"})
        if not ok:
            return
        self.write_json({"ok": True, "points": paneldata.J(points),
                         "loop_bw_mhz": BENCH.cfg.cdr_bw
                         * BENCH.cfg.symbol_rate_hz / 1e6})


class ApiAnlt(Base):
    async def post(self):
        body = self.body_json()
        was_running = BENCH.running
        cfg = BENCH.cfg
        try:
            out, ok = await run_experiment(
                self, "AN/LT",
                lambda evt: anlt_session(
                    cfg, partner_abilities=body.get("partner_abilities"),
                    lt_rounds=int(body.get("lt_rounds", 4)),
                    lt_step=float(body.get("lt_step", 0.03)), cancel=evt),
                restart=False)   # il riavvio segue l'eventuale apply dei tap
        except Exception:
            if was_running:
                BENCH.start()
            raise
        if not ok:
            if was_running:
                BENCH.start()
            return
        cfg_after = out.pop("cfg_after")
        if body.get("apply") and out["lt"]["link_up_after"]:
            BENCH.set_config(cfg_after)
            persist()
            broadcast({"type": "config", "cfg": public_cfg(cfg_after), "profile": profile_state()})
            broadcast({"type": "tick", "acc": paneldata.J(BENCH.snapshot())})
            out["applied"] = True
        else:
            out["applied"] = False
        if was_running:
            BENCH.start()
        self.write_json(paneldata.J({"ok": True, **out}))


class ApiOnt(Base):
    async def post(self):
        body = self.body_json()
        grid = [int(v) for v in (body.get("ipg_grid")
                                 or [12, 96, 384, 1024, 2000])][:8]
        cfg = BENCH.cfg
        out, ok = await run_experiment(
            self, "ONT", lambda evt: l2_ont_report(cfg, ipg_grid=grid,
                                                   cancel=evt))
        if not ok:
            return
        self.write_json(paneldata.J({"ok": True, **out}))


class ApiDisrupt(Base):
    def post(self):
        BENCH.disrupt()
        self.write_json({"ok": True})


class ApiChamber(Base):
    def post(self):
        body = self.body_json()
        BENCH.set_chamber(**{k: v for k, v in body.items()
                             if k in CHAMBER_KEYS})
        persist()   # la camera sopravvive al riavvio, come la config
        broadcast({"type": "tick", "acc": paneldata.J(BENCH.snapshot())})
        self.write_json({"ok": True, "chamber": BENCH.chamber})


class ApiInject(Base):
    def post(self):
        body = self.body_json()
        raw_n = body.get("bits", 10)
        try:
            if isinstance(raw_n, bool) or not str(raw_n).strip().lstrip("+-").isdigit():
                raise ValueError
            n = int(raw_n)
        except (TypeError, ValueError):
            self.set_status(400)
            return self.write_json({"error": "bits deve essere un intero fra 1 e 200"})
        if not 1 <= n <= 200:
            self.set_status(400)
            return self.write_json({"error": "bits deve essere un intero fra 1 e 200"})
        target = body.get("target", "random")
        if target not in ("random", "msb", "lsb", "rs_symbol"):
            self.set_status(400)
            return self.write_json(
                {"error": "target deve essere random/msb/lsb/rs_symbol"})
        try:
            request = BENCH.inject_errors(
                n, burst=bool(body.get("burst", False)), target=target)
        except ValueError:
            self.set_status(400)
            return self.write_json({"error": "richiesta di inserimento non valida"})
        except BertNotRunning:
            self.set_status(409)
            return self.write_json({"error": "BERT non in RUN"})
        except InjectionInProgress:
            self.set_status(409)
            return self.write_json({"error": "inserimento errori già in corso"})
        broadcast({"type": "tick", "acc": paneldata.J(BENCH.snapshot())})
        self.write_json({"ok": True, "request": request,
                         "bits": request["bits"], "target": request["target"]})


class ApiTrain(Base):
    async def post(self):
        was_running = BENCH.running
        cfg = BENCH.cfg
        try:
            res, ok = await run_experiment(
                self, "link training",
                lambda evt: link_train(cfg, cancel=evt), restart=False)
        except Exception:
            if was_running:
                BENCH.start()
            raise
        if not ok:
            if was_running:
                BENCH.start()
            return
        new_cfg, steps, base, final = res
        BENCH.set_config(new_cfg)
        persist()
        broadcast({"type": "config", "cfg": public_cfg(new_cfg), "profile": profile_state()})
        if was_running:
            BENCH.start()
        self.write_json({"ok": True, "steps": paneldata.J(steps),
                         "score_before": base, "score_after": final,
                         "verification_before": steps[-1].get("verification_before"),
                         "verification_after": steps[-1].get("verification_after"),
                         "accepted": steps[-1].get("accepted", True),
                         "cfg": public_cfg(new_cfg)})


class ApiTraffic(Base):
    async def post(self):
        body = self.body_json()
        sizes = body.get("frame_sizes")
        if sizes is None:
            sizes = [64, 128, 256, 512, 1024]
        # una lista vuota è un errore del chiamante, non "usa i default"
        if not isinstance(sizes, list) or not 1 <= len(sizes) <= 8:
            self.set_status(400)
            return self.write_json({"error": "frame_sizes deve contenere 1..8 valori"})
        cfg = BENCH.cfg
        try:
            rows, ok = await run_experiment(
                self, "traffic",
                lambda evt: traffic_sweep(cfg, sizes, cancel=evt))
        except ValueError:
            self.set_status(400)
            return self.write_json({"error": "frame_sizes contiene valori non validi"})
        if not ok:
            return
        self.write_json({"ok": True, "kind": "PHY frame-size benchmark",
                         "normative": False, "rows": paneldata.J(rows)})


class ApiDr4Procedure(Base):
    """Procedura versionata DR4, deliberatamente on-demand e non live."""

    async def post(self):
        body = self.body_json()
        try:
            seed = int(body.get("seed", 500283))
        except (TypeError, ValueError):
            self.set_status(400)
            return self.write_json({"error": "seed deve essere un intero"})
        if not 0 <= seed <= 2 ** 32 - 1:
            self.set_status(400)
            return self.write_json({"error": "seed fuori range uint32"})
        report, ok = await run_experiment(
            self, "DR4",
            lambda evt: run_dr4_tdecq_e2e(seed=seed, cancel=evt))
        if not ok:
            return
        LAST_DR4["report"] = paneldata.J(report)
        self.write_json({"ok": True, "report": LAST_DR4["report"]})


class ApiSensitivity(Base):
    async def post(self):
        body = self.body_json()
        target = body.get("target_ber")
        try:
            target = float(target) if target is not None else None
            if target is not None and not 0 < target < 0.5:
                raise ValueError("target_ber fuori range (0, 0.5)")
        except (TypeError, ValueError):
            self.set_status(400)
            return self.write_json({"error": "target_ber non valido"})
        cfg = BENCH.cfg
        try:
            report, ok = await run_experiment(
                self, "RX sensitivity",
                lambda evt: rx_sensitivity_search(cfg, target_ber=target,
                                                  cancel=evt))
        except ValueError:
            self.set_status(400)
            return self.write_json({"error": "ricerca sensitivity non valida"})
        if not ok:
            return
        self.write_json({"ok": True, **paneldata.J(report)})


class ApiStressCal(Base):
    async def post(self):
        body = self.body_json()
        try:
            target_q = float(body.get("target_q", 3.0))
            if not 0.3 <= target_q <= 10.0:
                raise ValueError("target_q fuori range [0.3, 10]")
        except (TypeError, ValueError):
            self.set_status(400)
            return self.write_json({"error": "target_q non valido"})
        cfg = BENCH.cfg
        report, ok = await run_experiment(
            self, "stressed-eye cal",
            lambda evt: stressed_eye_calibrate(cfg, target_q=target_q,
                                               cancel=evt))
        if not ok:
            return
        self.write_json({"ok": True, **paneldata.J(report)})


class ApiExperimentCancel(Base):
    def post(self):
        name = EXPERIMENT.current
        hit = EXPERIMENT.cancel()
        self.write_json({"ok": True, "cancelled": hit, "experiment": name})


class ApiPanel(Base):
    async def get(self, name):
        builder = paneldata.PANEL_BUILDERS.get(name)
        if builder is None:
            self.set_status(404)
            return self.write_json({"error": f"pannello sconosciuto: {name}"})
        source = self.get_argument("source", "auto")
        injection_report = None
        bert_source = None
        if name == "bert" and source in ("auto", "live"):
            cfg, live_sim, records, _, bert_source, injection_report = \
                BENCH.capture_bert()
        else:
            cfg, live_sim, records, _ = BENCH.capture()
        kwargs = {}
        params = inspect.signature(builder).parameters
        if "node" in params:
            node = self.get_argument("node", "vctle")
            if node not in paneldata.NODES:
                raise BadParam("nodo sconosciuto", "unknown node")
            kwargs["node"] = node
        if "n_traces" in params:
            kwargs["n_traces"] = self.int_arg("n", 500, 1, 5000)
        if "nperseg" in params:
            kwargs["nperseg"] = self.int_arg("nperseg", 4096, 64, 65536)
        if "profile" in params:
            kwargs["profile"] = PROFILE["name"]

        def work():
            # live: ultimo record del bench (nuovo rumore); ref: sim full
            # cache — la ref_sim è una simulate full-depth: gira nel worker,
            # non sull'IOLoop (prima congelava tick WS e tutti i pannelli)
            sim = None
            source_used = "reference"
            if source in ("auto", "live") and name in (
                    "eye", "spectrum", "jitter", "pd", "tia", "agc", "optical",
                    "timing", "eq", "decisions", "bert", "checks", "adc", "l2",
                    "eyecontour", "physics", "tx"):
                sim = live_sim
                if cfg_matches_live(sim, cfg):
                    source_used = bert_source or "live"
            if name in ("education", "com"):
                sim = None  # cataloghi/config analysis: niente datapath
                source_used = "static" if name == "education" else "config"
            elif not cfg_matches_live(sim, cfg):
                sim = paneldata.ref_sim(cfg)
            payload = builder(sim, cfg, **kwargs)
            if isinstance(payload, dict):
                if name == "bert":
                    payload["injection"] = injection_report
                payload["_acquisition"] = {
                    "seed": (int(sim.seed) if sim is not None else None),
                    "depth": (sim.depth if sim is not None else None),
                    "source": source_used,
                    "records": records,
                    "record": (injection_report.get("record")
                               if source_used == "injection"
                               and injection_report is not None else records),
                }
            return payload

        try:
            payload = await tornado.ioloop.IOLoop.current().run_in_executor(
                REF_POOL, work)
        except ValueError:
            self.set_status(400)
            return self.write_json({"error": "parametri pannello non validi"})
        except Exception:
            log.exception("Panel builder failed")
            self.set_status(500)
            return self.write_json({"error": "errore interno del pannello"})
        self.write_json(payload)


class ApiReport(Base):
    """Report di conformità tracciabile (JSON o Markdown) dello stesso
    record servito ai pannelli: hash config, seed, profilo, contratti con
    verdetti, invarianti fisici, checkpoint, ultima procedura DR4."""

    async def get(self):
        fmt = self.get_argument("format", "json")
        if fmt not in ("json", "md"):
            raise BadParam("format deve essere json o md", "format must be json or md")
        cfg, live_sim, records, _ = BENCH.capture()
        profile = PROFILE["name"]
        dr4 = LAST_DR4["report"]

        def work():
            sim = live_sim if cfg_matches_live(live_sim, cfg) else paneldata.ref_sim(cfg)
            extras = {"records": records, "dr4": dr4}
            if cfg.link_medium == "copper" and cfg.modulation == "PAM4":
                from serdes_sim.blocks.com import com_report
                ctx = paneldata.profile_context(cfg, profile)
                extras["com"] = paneldata.J(com_report(cfg, interface=ctx["interface"]))
            return paneldata.standards_report(sim, cfg, profile, extras)

        try:
            rep = await tornado.ioloop.IOLoop.current().run_in_executor(
                REF_POOL, work)
        except Exception:
            log.exception("Standards report failed")
            self.set_status(500)
            return self.write_json({"error": "errore interno del report"})
        import time as _time
        stamp = _time.strftime("%Y%m%d_%H%M%S")
        if fmt == "md":
            self.set_header("Content-Type", "text/markdown; charset=UTF-8")
            self.set_header("Content-Disposition",
                            f'attachment; filename="labpro_compliance_{stamp}.md"')
            return self.finish(paneldata.standards_report_markdown(rep))
        self.set_header("Content-Disposition",
                        f'attachment; filename="labpro_compliance_{stamp}.json"')
        self.write_json(rep)


class ApiScope(Base):
    """Acquisizione DCA coerente: fino a quattro nodi dallo stesso record."""
    async def get(self):
        requested = [v.strip() for v in self.get_argument(
            "nodes", "vctle").split(",") if v.strip()]
        if not requested or len(requested) > 4 or any(
                n not in paneldata.NODES for n in requested):
            self.set_status(400)
            return self.write_json({"error": "nodes richiede 1..4 nodi validi"})
        cfg, live_sim, records, running = BENCH.capture()
        source = self.get_argument("source", "auto")
        rf = self.get_argument("rf", "")
        n_traces = min(self.int_arg("n", 600, 1, 5000), 800)
        # vista FlexDCA: eye (default) oppure wave = Oscilloscope mode,
        # finestra continua del record navigabile con start/span [UI]
        view = self.get_argument("view", "eye")
        try:
            start_ui = float(self.get_argument("start", "100"))
            span_ui = float(self.get_argument("span", "64"))
        except ValueError:
            self.set_status(400)
            return self.write_json({"error": "start/span devono essere numeri"})

        def work():
            sim = live_sim if source in ("auto", "live") else None
            source_used = "live"
            if not cfg_matches_live(sim, cfg):
                sim = paneldata.ref_sim(cfg)
                source_used = "reference"
            if view == "wave":
                channels = [paneldata.wave_panel(sim, cfg, node=n,
                                                 start_ui=start_ui,
                                                 span_ui=span_ui,
                                                 ref_filter=rf)
                            for n in requested]
            else:
                channels = [paneldata.eye_panel(sim, cfg, node=n,
                                                n_traces=n_traces,
                                                ref_filter=rf)
                            for n in requested]
            return sim, source_used, channels

        try:
            sim, source_used, channels = await (
                tornado.ioloop.IOLoop.current().run_in_executor(REF_POOL,
                                                                work))
        except Exception:
            log.exception("Scope acquisition failed")
            self.set_status(400)
            return self.write_json({"error": "acquisizione Scope non valida"})
        self.write_json({
            "channels": channels,
            "coherent": True,
            "running": running,
            # Lo Scope mostra per definizione un piano analogico PRE-DSP.
            # Allegare l'esito del detector evita che un occhio chiuso prima
            # di FSE/DFE venga interpretato come link fisicamente fermo.
            "link": paneldata.J({
                "link_up": bool(sim.link_up),
                "cdr_locked": (bool(sim.cdr.locked)
                               if sim.cdr is not None else bool(sim.link_up)),
                "pattern_locked": (bool(sim.cdr.pattern_locked)
                                   if sim.cdr is not None else bool(sim.link_up)),
                "q_min": (sim.snr_dfe["q_min"] if sim.link_up else None),
                "q_per_eye": (sim.snr_dfe["q_per_eye"]
                              if sim.link_up else None),
                "ber_counted": (sim.ber_post_dfe if sim.link_up else None),
                "fec_mode": cfg.fec_mode,
                "post_fec_ber": (sim.fec_link.post_fec_ber
                                 if sim.fec_link is not None else None),
                "fec_frames_uncorrectable": (
                    sim.fec_link.frames_uncorrectable
                    if sim.fec_link is not None else None),
            }),
            "_acquisition": {"seed": int(sim.seed), "depth": sim.depth,
                             "source": source_used, "records": records},
        })


class WS(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        # solo pagine servite in locale: una pagina web qualunque aperta nel
        # browser non deve poter agganciare il banco via WebSocket
        return _is_same_loopback_origin(
            origin, self.request.protocol, self.request.host
        )

    def open(self):
        CLIENTS.add(self)
        _ws_send(self, json.dumps({
            "type": "hello",
            "cfg": public_cfg(BENCH.cfg), "profile": profile_state(),
            "running": BENCH.running,
            "acc": paneldata.J(BENCH.snapshot()),
            "experiment": EXPERIMENT.current,
        }))

    def on_close(self):
        CLIENTS.discard(self)

    def on_message(self, message):
        pass  # il canale di comando è REST


def ensure_plotly():
    """Copia plotly.min.js dal pacchetto python (nessuna CDN)."""
    target = STATIC_DIR / "plotly.min.js"
    if target.exists():
        return
    import plotly
    src = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
    if not src.exists():
        # plotly 6.x non spedisce più package_data/plotly.min.js: meglio un
        # errore leggibile all'avvio che un FileNotFoundError nudo
        raise SystemExit(
            f"plotly.min.js non trovato nel pacchetto plotly {plotly.__version__} "
            f"({src}). Installa 'plotly>=5.24,<6' oppure copia manualmente un "
            f"plotly.min.js in {STATIC_DIR}/.")
    shutil.copy(src, target)


def make_app():
    return tornado.web.Application([
        (r"/", Index),
        (r"/api/health", ApiHealth),
        (r"/api/state", ApiState),
        (r"/api/config", ApiConfig),
        (r"/api/config/export", ApiConfigExport),
        (r"/api/config/import", ApiConfigImport),
        (r"/api/preset", ApiPreset),
        (r"/api/run", ApiRun),
        (r"/api/reset", ApiReset),
        (r"/api/s2p", ApiS2P),
        (r"/api/experiment/sweep", ApiSweep),
        (r"/api/experiment/jtol", ApiJtol),
        (r"/api/experiment/train", ApiTrain),
        (r"/api/experiment/jtf", ApiJtf),
        (r"/api/experiment/traffic", ApiTraffic),
        (r"/api/experiment/dr4-tdecq", ApiDr4Procedure),
        (r"/api/experiment/anlt", ApiAnlt),
        (r"/api/experiment/ont", ApiOnt),
        (r"/api/experiment/sensitivity", ApiSensitivity),
        (r"/api/experiment/stresscal", ApiStressCal),
        (r"/api/experiment/cancel", ApiExperimentCancel),
        (r"/api/chamber", ApiChamber),
        (r"/api/disrupt", ApiDisrupt),
        (r"/api/inject", ApiInject),
        (r"/api/scope", ApiScope),
        (r"/api/panel/(\w+)", ApiPanel),
        (r"/api/report/standards", ApiReport),
        (r"/ws", WS),
        (r"/static/(.*)", tornado.web.StaticFileHandler,
         {"path": str(STATIC_DIR)}),
    ], websocket_ping_interval=20, websocket_ping_timeout=60,
       compress_response=True, default_handler_class=NotFound)


def _serve_until_stopped(loop, bench):
    """Esegue il loop e chiude il LiveBench anche su SIGINT da terminale."""
    try:
        loop.start()
    except KeyboardInterrupt:
        print("\nSerDes Optical Lab Pro arrestato.")
    finally:
        bench.stop()


def _install_shutdown_handlers(loop):
    """Make terminal and launcher shutdown graceful, including background jobs."""
    def request_stop(signum, _frame):
        log.info("shutdown requested by signal %s", signum)
        loop.add_callback_from_signal(loop.stop)

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)


def main():
    global MAIN_LOOP, PERSIST
    parser = argparse.ArgumentParser(
        description="Run SerDes Optical Lab PRO on the local loopback interface.")
    parser.add_argument("--port", type=int, default=8640,
                        help="loopback TCP port (default: 8640)")
    parser.add_argument("--no-autostart", action="store_true",
                        help="start with continuous acquisition stopped")
    persistence = parser.add_mutually_exclusive_group()
    persistence.add_argument(
        "--state-file", type=Path,
        help="session file (default: platform-specific per-user state directory)")
    persistence.add_argument(
        "--no-persist", action="store_true",
        help="do not load or save the Lab PRO session")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.no_persist:
        PERSIST = None
    elif args.state_file is not None:
        PERSIST = args.state_file.expanduser().resolve()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("tornado.access").setLevel(logging.WARNING)
    ensure_plotly()
    load_persisted()
    app = make_app()
    try:
        app.listen(args.port, address="127.0.0.1",
                   max_body_size=MAX_REQUEST_BODY_BYTES)
    except OSError as exc:
        raise SystemExit(
            f"Unable to start Lab PRO on 127.0.0.1:{args.port}: {exc}") from None
    MAIN_LOOP = tornado.ioloop.IOLoop.current()
    _install_shutdown_handlers(MAIN_LOOP)
    if not args.no_autostart:
        BENCH.start()
    print(f"SerDes Optical Lab Pro → http://localhost:{args.port}")
    _serve_until_stopped(MAIN_LOOP, BENCH)


if __name__ == "__main__":
    main()
