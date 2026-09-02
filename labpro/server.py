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
import time
import math
import logging
import os
import signal
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
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
from serdes_sim.procedures import run_dr4_tdecq_e2e, run_stressed_receiver  # noqa: E402
from labpro import __version__ as LABPRO_VERSION, scpi  # noqa: E402
from serdes_sim.instrument_procedures import (bert_pam4_result,  # noqa: E402
                                              rfc2544_report, y1564_report)
from serdes_sim.golden import (correlate_golden, correlate_library,  # noqa: E402
                               dataset_from_flexdca, golden_library,
                               load_library_dataset, synthetic_golden_dataset,
                               validate_dataset)
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
# Ultima correlazione golden e ultima calibrazione stressed-RX.
LAST_GOLDEN = {"result": None, "dataset_meta": None}
LAST_GOLDEN_LIBRARY = {"report": None}
LAST_RFC2544 = {"report": None}
LAST_FIXTURE = {"sparams": None, "meta": None}
SCPI_SETTINGS = {"enabled": True, "port": scpi.DEFAULT_PORT,
                 "status": "starting"}
LAST_Y1564 = {"report": None}
LAST_STRESSED = {"report": None}
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
MAX_FLEXDCA_TEXT_BYTES = 15 * 1024 * 1024
MAX_SESSION_FILE_BYTES = 64 * 1024 * 1024
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


def parse_session_version(value) -> int:
    """Accept integer JSON/string versions, never truncate fractional ones."""
    if isinstance(value, bool):
        raise ValueError("session version must be an integer")
    try:
        numeric = float(value)
        parsed = int(numeric)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("session version must be an integer") from None
    if not math.isfinite(numeric) or numeric != parsed:
        raise ValueError("session version must be an integer")
    return parsed


def normalized_chamber(updates, current=None) -> dict:
    """Validate and merge chamber settings before mutating the LiveBench."""
    if not isinstance(updates, dict):
        raise BadParam("chamber deve essere un oggetto JSON",
                       "chamber must be a JSON object")
    unknown = sorted(set(updates) - set(CHAMBER_KEYS))
    if unknown:
        fields = ", ".join(unknown)
        raise BadParam(f"campi chamber sconosciuti: {fields}",
                       f"unknown chamber fields: {fields}")
    out = dict(current or BENCH.chamber_settings())
    if "on" in updates:
        if not isinstance(updates["on"], bool):
            raise BadParam("chamber.on deve essere booleano",
                           "chamber.on must be a boolean")
        out["on"] = updates["on"]
    if "mode" in updates:
        mode = updates["mode"]
        if mode not in {"cycle", "ramp", "soak"}:
            raise BadParam("chamber.mode deve essere cycle, ramp o soak",
                           "chamber.mode must be cycle, ramp, or soak")
        out["mode"] = mode
    ranges = {
        "t_min": (-40.0, 125.0),
        "t_max": (-40.0, 125.0),
        "period_s": (10.0, 86400.0),
        "tau_s": (1.0, 86400.0),
    }
    for name, (lo, hi) in ranges.items():
        if name in updates:
            out[name] = as_number(updates[name], f"chamber.{name}", lo, hi)
    if out["t_min"] > out["t_max"]:
        raise BadParam("chamber.t_min deve essere <= chamber.t_max",
                       "chamber.t_min must be <= chamber.t_max")
    return out


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
        if source.stat().st_size > MAX_SESSION_FILE_BYTES:
            raise ValueError("session payload exceeds 64 MiB")
        d = json.loads(source.read_text(encoding="utf-8"),
                       parse_constant=_reject_json_constant)
        if not isinstance(d, dict) or not isinstance(d.get("cfg", {}), dict):
            raise ValueError("session payload must be a JSON object")
        if parse_session_version(d.get("version", SESSION_VERSION)) != SESSION_VERSION:
            raise ValueError("unsupported session version")
        cfg, dropped = config_from_dict(d.get("cfg", {}))
        problems = cfg.validate()
        if problems:
            raise ValueError("persisted config invalid: " + "; ".join(problems))
        chamber = (normalized_chamber(d["chamber"])
                   if "chamber" in d else BENCH.chamber_settings())
        profile = (d.get("profile")
                   if d.get("profile") in STANDARD_PROFILES else None)
        # Commit only after every section has been validated. A corrupt
        # chamber must not partially restore config/profile.
        BENCH.set_config(cfg)
        BENCH.set_chamber(**chamber)
        PROFILE["name"] = profile
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
# le query SCPI hanno un worker proprio: non fanno coda dietro ai pannelli del browser
SCPI_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scpi")


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


class ApiHealth(Base):
    """Cheap readiness/support endpoint; never starts a simulation."""

    def get(self):
        persistence = persistence_status()
        scpi_state = {k: SCPI_SETTINGS[k] for k in ("status", "port")}
        degraded = (persistence["status"] == "error"
                    or SCPI_SETTINGS["status"] == "error")
        self.write_json({
            "status": "degraded" if degraded else "ok",
            "service": "serdes-optical-lab-pro",
            "version": LABPRO_VERSION,
            "api_version": 1,
            "running": BENCH.running,
            "experiment": EXPERIMENT.current,
            "persistence": persistence,
            "scpi": scpi_state,
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
        body = self.body_json()
        if "updates" in body:
            if set(body) != {"updates"}:
                return self.write_bad(
                    "payload ambiguo: usare campi diretti oppure solo 'updates'",
                    "ambiguous payload: use direct fields or only 'updates'")
            updates = body["updates"]
        else:
            updates = body
        if not isinstance(updates, dict):
            return self.write_bad("updates deve essere un oggetto JSON",
                                  "updates must be a JSON object")
        updates = dict(updates)
        cfg = BENCH.cfg
        try:
            if "tx_ffe_taps" in updates:
                updates["tx_ffe_taps"] = tuple(updates["tx_ffe_taps"])
            for name in ("ctle_zeros_hz", "ctle_poles_hz"):
                if name in updates:
                    updates[name] = tuple(float(v) for v in updates[name])
            new = cfg.with_updates(**updates)
        except (TypeError, ValueError):
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
                file_version = parse_session_version(file_version)
                if file_version > SESSION_VERSION:
                    return self.write_bad(
                        f"file di versione {file_version}: più recente di questo LabPro ({SESSION_VERSION})",
                        f"file version {file_version}: newer than this LabPro ({SESSION_VERSION})")
                if file_version != SESSION_VERSION:
                    return self.write_bad(
                        f"file di versione {file_version}: non supportato",
                        f"file version {file_version}: unsupported")
            except ValueError:
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
        try:
            chamber = (normalized_chamber(body["chamber"])
                       if "chamber" in body else BENCH.chamber_settings())
        except BadParam as exc:
            return self.write_bad(exc.it, exc.en)
        raw_profile = body.get("profile")
        if raw_profile is not None and raw_profile not in STANDARD_PROFILES:
            return self.write_bad("profilo standard sconosciuto",
                                  "unknown standards profile")
        profile = raw_profile
        # Transactional commit: cfg/profile/chamber change together only
        # after all imported sections have passed validation.
        BENCH.set_config(new)
        BENCH.set_chamber(**chamber)
        PROFILE["name"] = profile
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
        chamber = normalized_chamber(self.body_json())
        BENCH.set_chamber(**chamber)
        persist()   # la camera sopravvive al riavvio, come la config
        broadcast({"type": "tick", "acc": paneldata.J(BENCH.snapshot())})
        self.write_json({"ok": True, "chamber": BENCH.chamber_settings()})


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
        golden = LAST_GOLDEN["result"]
        report, ok = await run_experiment(
            self, "DR4",
            lambda evt: run_dr4_tdecq_e2e(seed=seed, cancel=evt, golden=golden))
        if not ok:
            return
        LAST_DR4["report"] = paneldata.J(report)
        self.write_json({"ok": True, "report": LAST_DR4["report"]})


class ApiStressedRx(Base):
    """Calibrazione stressed-eye sul SECQ + test del RX (procedura v2)."""

    async def post(self):
        body = self.body_json()
        seed = as_number(body.get("seed"), "seed", 0, 2 ** 32 - 1, integer=True,
                         default=500283)
        sj_ui = as_number(body.get("sj_ui"), "sj_ui", 0.0, 0.4, default=0.05)
        sj_mhz = as_number(body.get("sj_mhz"), "sj_mhz", 1.0, 5000.0, default=100.0)
        si_pct = as_number(body.get("si_pct"), "si_pct", 0.0, 30.0, default=0.0)
        si_mhz = as_number(body.get("si_mhz"), "si_mhz", 1.0, 20000.0, default=1000.0)
        target = (as_number(body.get("target_secq_db"), "target_secq_db", 0.1, 10.0)
                  if body.get("target_secq_db") is not None else None)
        cfg = BENCH.cfg
        profile = PROFILE["name"]
        if cfg.link_medium != "optical" or cfg.modulation != "PAM4":
            raise BadParam("la calibrazione stressed-RX richiede un link ottico PAM4",
                           "stressed-RX calibration requires an optical PAM4 link")
        report, ok = await run_experiment(
            self, "stressed RX",
            lambda evt: run_stressed_receiver(cfg, profile=profile, seed=seed,
                                              sj_ui=sj_ui, sj_mhz=sj_mhz,
                                              si_pct=si_pct, si_mhz=si_mhz,
                                              target_secq_db=target, cancel=evt))
        if not ok:
            return
        LAST_STRESSED["report"] = paneldata.J(report)
        self.write_json({"ok": True, "report": LAST_STRESSED["report"]})


class ApiGolden(Base):
    """Dataset golden (waveform + riferimenti strumento) e correlazione."""

    def get(self):
        self.write_json({"result": LAST_GOLDEN["result"],
                         "dataset": LAST_GOLDEN["dataset_meta"]})

    async def post(self):
        body = self.body_json()
        loop = tornado.ioloop.IOLoop.current()
        if body.get("example"):
            dataset = await loop.run_in_executor(REF_POOL, synthetic_golden_dataset)
        elif body.get("library"):
            # waveform della libreria golden inclusa nel pacchetto
            lib = str(body.get("library"))
            wid = str(body.get("waveform") or "")
            try:
                dataset = await loop.run_in_executor(
                    REF_POOL, load_library_dataset, lib, wid)
            except (KeyError, FileNotFoundError):
                log.info("Golden library selection rejected", exc_info=True)
                return self.write_bad("libreria o waveform golden non disponibile",
                                      "golden library or waveform unavailable")
        elif body.get("flexdca_csv"):
            # export FlexDCA (WaveformXYValues / WaveformPattern) + riferimenti
            text = body.get("flexdca_csv")
            if not isinstance(text, str):
                return self.write_bad("flexdca_csv deve essere testo",
                                      "flexdca_csv must be text")
            if len(text.encode("utf-8")) > MAX_FLEXDCA_TEXT_BYTES:
                self.set_status(413)
                return self.write_json({"error": "FlexDCA CSV upload exceeds 15 MiB"})
            rate = (as_number(body.get("symbol_rate_hz"), "symbol_rate_hz", 1e9, 400e9)
                    if body.get("symbol_rate_hz") is not None else None)
            reference = body.get("reference") if isinstance(body.get("reference"), dict) else {}
            try:
                dataset = await loop.run_in_executor(
                    REF_POOL, lambda: dataset_from_flexdca(
                        text, symbol_rate_hz=rate, reference=reference,
                        instrument=str(body.get("instrument") or "Keysight FlexDCA export"),
                        note=str(body.get("note") or "")))
            except ValueError as exc:
                return self.write_bad(f"export FlexDCA non valido: {exc}",
                                      f"invalid FlexDCA export: {exc}")
        else:
            dataset = body.get("dataset")
        problems = validate_dataset(dataset)
        if problems:
            return self.write_bad("dataset golden non valido: " + "; ".join(problems),
                                  "invalid golden dataset: " + "; ".join(problems))
        result = await tornado.ioloop.IOLoop.current().run_in_executor(
            REF_POOL, correlate_golden, dataset)
        meta = {k: dataset.get(k) for k in ("schema", "source", "instrument", "interface",
                                             "symbol_rate_hz", "samples_per_ui", "note",
                                             "library", "waveform_id", "title", "provenance",
                                             "source_url", "pattern_model", "acquisition",
                                             "sigma_s_w")}
        meta["n_symbols"] = len(dataset.get("symbols", []))
        meta["reference"] = {k: v for k, v in (dataset.get("reference") or {}).items()
                             if not isinstance(v, (list, dict)) or k == "tdecq_range_db"}
        LAST_GOLDEN["result"] = paneldata.J(result)
        LAST_GOLDEN["dataset_meta"] = meta
        self.write_json({"ok": True, "result": LAST_GOLDEN["result"], "dataset": meta})


class ApiGoldenLibrary(Base):
    """Librerie golden incluse nel pacchetto (metadati e provenienza)."""

    def get(self):
        self.write_json({"libraries": golden_library(),
                         "last_run": LAST_GOLDEN_LIBRARY["report"]})


class ApiGoldenLibraryRun(Base):
    """Correlazione sistematica LabPro vs strumento su tutta una libreria."""

    async def post(self):
        body = self.body_json()
        lib = str(body.get("library") or "ieee_802_3bs_smf_2017")
        optimize = str(body.get("optimize") or "min_tdecq")
        if optimize not in ("mmse", "min_tdecq"):
            raise BadParam("optimize deve essere mmse o min_tdecq",
                           "optimize must be mmse or min_tdecq")
        if not any(x["name"] == lib for x in golden_library()):
            raise BadParam(f"libreria golden sconosciuta: {lib}",
                           f"unknown golden library: {lib}")
        report, ok = await run_experiment(
            self, "golden library",
            lambda evt: correlate_library(lib, optimize=optimize, cancel=evt))
        if not ok:
            return
        LAST_GOLDEN_LIBRARY["report"] = paneldata.J(report)
        self.write_json({"ok": True, "report": LAST_GOLDEN_LIBRARY["report"]})


class ApiRfc2544(Base):
    """RFC 2544 con la struttura del report Xena2544/Valkyrie2544."""

    async def post(self):
        body = self.body_json()
        sizes = body.get("frame_sizes") or [64, 256, 512, 1024]
        if not isinstance(sizes, list) or not 1 <= len(sizes) <= 8:
            raise BadParam("frame_sizes deve contenere 1..8 valori", "frame_sizes must hold 1..8 values")
        sizes = [int(as_number(v, "frame_sizes", 64, 1024, integer=True)) for v in sizes]
        loss = as_number(body.get("acceptable_loss_pct"), "acceptable_loss_pct", 0.0, 50.0, default=0.0)
        iters = int(as_number(body.get("max_iterations"), "max_iterations", 0, 8, integer=True, default=4))
        cfg = BENCH.cfg
        profile = PROFILE["name"]
        report, ok = await run_experiment(
            self, "RFC 2544",
            lambda evt: rfc2544_report(cfg, frame_sizes=sizes, acceptable_loss_pct=loss,
                                       max_iterations=iters, profile=profile, cancel=evt))
        if not ok:
            return
        LAST_RFC2544["report"] = paneldata.J(report)
        self.write_json({"ok": True, "report": LAST_RFC2544["report"]})


class ApiY1564(Base):
    """ITU-T Y.1564 con il flusso e i KPI di VIAVI SAMComplete."""

    async def post(self):
        body = self.body_json()
        steps = body.get("cir_steps_pct") or [25, 50, 75, 100]
        if not isinstance(steps, list) or not 1 <= len(steps) <= 6:
            raise BadParam("cir_steps_pct deve contenere 1..6 valori", "cir_steps_pct must hold 1..6 values")
        steps = [float(as_number(v, "cir_steps_pct", 1.0, 100.0)) for v in steps]
        sla = body.get("sla") if isinstance(body.get("sla"), dict) else None
        cfg = BENCH.cfg
        profile = PROFILE["name"]
        report, ok = await run_experiment(
            self, "Y.1564",
            lambda evt: y1564_report(cfg, cir_steps_pct=tuple(steps), sla=sla, profile=profile, cancel=evt))
        if not ok:
            return
        LAST_Y1564["report"] = paneldata.J(report)
        self.write_json({"ok": True, "report": LAST_Y1564["report"]})


def bench_cumulative(acc: dict) -> dict:
    """Contatori cumulativi del banco nel vocabolario dell'ED (Bit Count,
    Error Count, Error Rate, Sync/Clock Loss, FEC)."""
    fec = acc.get("fec") or {}
    return {"bits": acc.get("bits_total"), "errors": acc.get("bit_errors_total"),
            "ber": acc.get("ber_cum"), "sync_losses": acc.get("sync_losses"),
            "clock_losses": acc.get("link_down_records"),
            "fec_symbol_errors": fec.get("symbols_corrected", fec.get("fec_symbols_corrected")),
            "fec_uncorrectable": fec.get("frames_uncorrectable", fec.get("fec_frames_uncorrectable"))}


class ApiInstrumentReport(Base):
    """Export in formato strumento: rfc2544 (json|md|xml), y1564 (json|md|csv),
    bert (json|md|csv, dall'ultimo record del banco)."""

    def get(self, kind):
        from labpro import instrument_reports as ir
        fmt = self.get_argument("format", "json").lower()
        if kind == "bert":
            cfg, sim, records, _ = BENCH.capture()
            cum = bench_cumulative(BENCH.snapshot() or {})
            report = (bert_pam4_result(sim, cum, mapping=cfg.pam4_mapping) if sim is not None
                      else {"available": False, "reason": "no record acquired yet"})
            report = paneldata.J(report)
            table = {"json": None, "md": (ir.bert_markdown, "text/markdown", "md"),
                     "csv": (ir.bert_csv, "text/csv", "csv")}
        elif kind == "rfc2544":
            report = LAST_RFC2544["report"]
            table = {"json": None, "md": (ir.rfc2544_markdown, "text/markdown", "md"),
                     "xml": (ir.rfc2544_xml, "application/xml", "xml")}
        elif kind == "y1564":
            report = LAST_Y1564["report"]
            table = {"json": None, "md": (ir.y1564_markdown, "text/markdown", "md"),
                     "csv": (ir.y1564_csv, "text/csv", "csv")}
        else:
            return self.write_bad("report sconosciuto", "unknown report")
        if fmt not in table:
            return self.write_bad(f"format deve essere uno di {', '.join(table)}",
                                  f"format must be one of {', '.join(table)}")
        if report is None:
            return self.write_bad("nessun report: esegui prima la procedura",
                                  "no report yet: run the procedure first")
        if fmt == "json":
            return self.write_json({"kind": kind, "report": report})
        fn, mime, ext = table[fmt]
        self.set_header("Content-Type", f"{mime}; charset=utf-8")
        self.set_header("Content-Disposition",
                        f'attachment; filename="labpro-{kind}-{time.strftime("%Y%m%d-%H%M%S")}.{ext}"')
        self.finish(fn(report))


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
            extras = {"records": records, "dr4": dr4,
                      "golden": LAST_GOLDEN["result"],
                      "golden_library": LAST_GOLDEN_LIBRARY["report"],
                      "rfc2544": LAST_RFC2544["report"], "y1564": LAST_Y1564["report"],
                      "stressed_rx": LAST_STRESSED["report"]}
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


class ApiScopeFixture(Base):
    """Fixture di misura da S-parameter (Touchstone caricato o misura IEEE
    inclusa nel pacchetto) per il de-embedding dello scope."""

    def get(self):
        self.write_json({"loaded": LAST_FIXTURE["meta"],
                         "bundled": [{k: v for k, v in f.items() if k != "path"}
                                     for f in paneldata.bundled_fixtures()]})

    def post(self):
        body = self.body_json()
        if body.get("clear"):
            LAST_FIXTURE["sparams"] = None
            LAST_FIXTURE["meta"] = None
            return self.write_json({"ok": True, "loaded": None})
        name = None
        text = None
        if body.get("bundled"):
            fx = next((f for f in paneldata.bundled_fixtures() if f["id"] == body.get("bundled")), None)
            if fx is None:
                return self.write_bad("fixture inclusa sconosciuta", "unknown bundled fixture")
            text = Path(fx["path"]).read_text()
            name = fx["id"]
        elif isinstance(body.get("text"), str):
            text = body["text"]
            if len(text.encode("utf-8")) > MAX_TOUCHSTONE_TEXT_BYTES:
                self.set_status(413)
                return self.write_json({"error": "Touchstone upload exceeds 8 MiB"})
            name = str(body.get("name") or "upload")
        else:
            return self.write_bad("serve 'text' (Touchstone) o 'bundled'", "need 'text' (Touchstone) or 'bundled'")
        pairs = str(body.get("pairs") or "13_24")
        try:
            sp = paneldata.fixture_from_touchstone(text, pairs=pairs)
        except (ValueError, TypeError) as exc:
            return self.write_bad(f"Touchstone non valido: {exc}", f"invalid Touchstone: {exc}")
        sp["name"] = name
        LAST_FIXTURE["sparams"] = sp
        LAST_FIXTURE["meta"] = {"name": name, "ports": sp["ports"], "z0": sp["z0"],
                                "n_points": sp["n_points"], "f_max_ghz": float(sp["f_hz"][-1] / 1e9),
                                "il_db": sp["il_db"], "pairs": pairs}
        self.write_json({"ok": True, "loaded": LAST_FIXTURE["meta"]})


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
        start_ui = self.float_arg("start", 100.0, 0.0, 1e7)
        span_ui = self.float_arg("span", 64.0, 1.0, 1e5)
        # fixture di misura (dB a Nyquist) e de-embedding: strumenti del DCA,
        # non del datapath
        fix_raw = self.get_argument("fix", "0").strip().lower()
        fixture_sparams = None
        if fix_raw == "s2p":
            fixture_db = 0.0
            fixture_sparams = LAST_FIXTURE["sparams"]
            if fixture_sparams is None:
                raise BadParam("nessuna fixture S-parameter caricata (POST /api/scope/fixture)",
                               "no S-parameter fixture loaded (POST /api/scope/fixture)")
        else:
            fixture_db = as_number(fix_raw, "fix", 0.0, 30.0, default=0.0)
        deembed = self.get_argument("deembed", "0") == "1"

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
                                                 ref_filter=rf,
                                                 fixture_db=fixture_db, fixture_sparams=fixture_sparams,
                                                 deembed=deembed)
                            for n in requested]
            else:
                channels = [paneldata.eye_panel(sim, cfg, node=n,
                                                n_traces=n_traces,
                                                ref_filter=rf,
                                                profile=PROFILE["name"],
                                                fixture_db=fixture_db, fixture_sparams=fixture_sparams,
                                                deembed=deembed)
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
        (r"/api/experiment/stressed-rx", ApiStressedRx),
        (r"/api/golden", ApiGolden),
        (r"/api/golden/library", ApiGoldenLibrary),
        (r"/api/experiment/rfc2544", ApiRfc2544),
        (r"/api/experiment/y1564", ApiY1564),
        (r"/api/report/(rfc2544|y1564|bert)", ApiInstrumentReport),
        (r"/api/experiment/golden-library", ApiGoldenLibraryRun),
        (r"/api/experiment/anlt", ApiAnlt),
        (r"/api/experiment/ont", ApiOnt),
        (r"/api/experiment/sensitivity", ApiSensitivity),
        (r"/api/experiment/stresscal", ApiStressCal),
        (r"/api/experiment/cancel", ApiExperimentCancel),
        (r"/api/chamber", ApiChamber),
        (r"/api/disrupt", ApiDisrupt),
        (r"/api/inject", ApiInject),
        (r"/api/scope", ApiScope),
        (r"/api/scope/fixture", ApiScopeFixture),
        (r"/api/panel/(\w+)", ApiPanel),
        (r"/api/report/standards", ApiReport),
        (r"/ws", WS),
        (r"/static/(.*)", tornado.web.StaticFileHandler,
         {"path": str(STATIC_DIR)}),
    ], websocket_ping_interval=20, websocket_ping_timeout=60,
       compress_response=True, default_handler_class=NotFound)


def _serve_until_stopped(loop, bench):
    """Esegue il loop e chiude il LiveBench anche su SIGINT da terminale."""
    scpi_server = {"value": None}
    try:
        if SCPI_SETTINGS["enabled"] and callable(getattr(loop, "add_callback", None)):
            SCPI_SETTINGS["status"] = "starting"

            async def _start_scpi():
                port = SCPI_SETTINGS["port"]
                try:
                    scpi_server["value"] = await scpi.start_server(
                        ScpiContext(), "127.0.0.1", port)
                    SCPI_SETTINGS["status"] = "ready"
                    print(f"SCPI server on 127.0.0.1:{port} "
                          f"(PyVISA: TCPIP::127.0.0.1::{port}::SOCKET)", flush=True)
                except OSError as exc:
                    SCPI_SETTINGS["status"] = "error"
                    print(f"SCPI server not started: {exc}", flush=True)
            loop.add_callback(_start_scpi)
        elif not SCPI_SETTINGS["enabled"]:
            SCPI_SETTINGS["status"] = "disabled"
        loop.start()
    except KeyboardInterrupt:
        print("\nSerDes Optical Lab Pro arrestato.")
    finally:
        if scpi_server["value"] is not None:
            scpi_server["value"].close()
        if SCPI_SETTINGS["status"] != "error" and SCPI_SETTINGS["enabled"]:
            SCPI_SETTINGS["status"] = "stopped"
        bench.stop()


def _install_shutdown_handlers(loop):
    """Make terminal and launcher shutdown graceful, including background jobs."""
    def request_stop(signum, _frame):
        log.info("shutdown requested by signal %s", signum)
        loop.add_callback_from_signal(loop.stop)

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)


class ScpiContext:
    """Adattatore fra l'albero SCPI (labpro.scpi) e il banco: stessi
    percorsi di validazione, persistenza e broadcast delle API HTTP."""

    def serial(self):
        return "LABPRO-1"

    def version(self):
        from labpro import __version__
        return __version__

    # --- configurazione ------------------------------------------------------
    def _apply(self, new):
        problems = new.validate()
        if problems:
            raise ValueError("; ".join(problems))
        BENCH.set_config(new)
        persist()
        broadcast({"type": "config", "cfg": public_cfg(new), "profile": profile_state()})
        broadcast({"type": "tick", "acc": paneldata.J(BENCH.snapshot())})

    def set_param(self, name, value):
        cfg = BENCH.cfg
        if name not in type(cfg).__dataclass_fields__:
            raise KeyError(f"unknown LinkConfig field {name}")
        if isinstance(value, str) and isinstance(getattr(cfg, name), bool):
            value = scpi._onoff(value)
        if isinstance(getattr(cfg, name), tuple) and isinstance(value, str):
            value = tuple(float(v) for v in value.split(","))
        try:
            new = cfg.with_updates(**{name: value})
        except TypeError as exc:
            raise ValueError(str(exc)) from exc
        self._apply(new)

    def get_param(self, name):
        cfg = BENCH.cfg
        if name not in type(cfg).__dataclass_fields__:
            raise KeyError(f"unknown LinkConfig field {name}")
        v = getattr(cfg, name)
        return list(v) if isinstance(v, tuple) else v

    def param_names(self):
        return sorted(type(BENCH.cfg).__dataclass_fields__)

    def load_profile(self, name):
        if name not in STANDARD_PROFILES:
            raise KeyError(f"unknown profile {name}")
        BENCH.set_config(STANDARD_PROFILES[name][0])
        PROFILE["name"] = name
        persist()
        broadcast({"type": "config", "cfg": public_cfg(BENCH.cfg), "profile": profile_state()})

    def load_preset(self, name):
        if name not in PRESETS:
            raise KeyError(f"unknown preset {name}")
        BENCH.set_config(PRESETS[name][0])
        PROFILE["name"] = None
        persist()
        broadcast({"type": "config", "cfg": public_cfg(BENCH.cfg), "profile": profile_state()})

    def profile_name(self):
        return PROFILE["name"]

    def config_hash(self):
        return BENCH.cfg.short_hash() if hasattr(BENCH.cfg, "short_hash") else profile_state().get("hash", "")

    def config_dict(self):
        return public_cfg(BENCH.cfg)

    def reset(self):
        from serdes_sim.config import LinkConfig
        BENCH.set_config(LinkConfig())
        PROFILE["name"] = None
        BENCH.reset_stats()
        persist()
        broadcast({"type": "config", "cfg": public_cfg(BENCH.cfg), "profile": profile_state()})

    # --- acquisizione --------------------------------------------------------
    async def run(self, on):
        if on:
            BENCH.start()
        else:
            await tornado.ioloop.IOLoop.current().run_in_executor(None, BENCH.stop)
        broadcast({"type": "run", "running": BENCH.running})

    def running(self):
        return bool(BENCH.running)

    def records(self):
        return int((BENCH.snapshot() or {}).get("records", 0))

    def reset_stats(self):
        BENCH.reset_stats()

    def single(self):
        return self._offload(lambda: self._single())

    def _single(self):
        _, _, before, was_running = BENCH.capture()
        if not was_running:
            BENCH.start()
        try:
            deadline = time.monotonic() + 15.0
            while time.monotonic() < deadline:
                _, sim, records, running = BENCH.capture()
                if sim is not None and records > before:
                    return int(records)
                if not running:
                    break
                time.sleep(0.02)
        finally:
            if not was_running:
                BENCH.stop()
        raise scpi.ScpiError(-230, "Data corrupt or stale; acquisition failed")

    def _sim(self):
        cfg, sim, records, _ = BENCH.capture()
        if sim is None:
            raise scpi.ScpiError(-230, "Data corrupt or stale; no record acquired yet")
        return cfg, sim

    @staticmethod
    def _offload(fn):
        """Le misure girano nel pool di riferimento, mai sull'IOLoop (che
        serve HTTP, WebSocket e il LiveBench)."""
        return tornado.ioloop.IOLoop.current().run_in_executor(SCPI_POOL, fn)

    # --- misure DCA ----------------------------------------------------------
    def measure(self, kind, node):
        return self._offload(lambda: self._measure(kind, node))

    def _measure(self, kind, node):
        cfg, sim = self._sim()
        node = str(node).lower()
        if node in ("optical", "pfib", "pfiber", "opt", "pd"):
            node = "pfiber"
        if kind == "tdecq":
            # percorso rapido: solo il TDECQ di clausola sulla potenza ottica
            if cfg.link_medium != "optical" or getattr(sim, "optical", None) is None:
                return None
            from serdes_sim.blocks.metrics import tdecq_report
            rep = tdecq_report(sim.optical.P_fiber_w, sim.pam4_symbols, sim.spec,
                               cfg.analog_sps, cfg.symbol_rate_hz, cfg.fs_analog_hz)
            return rep.get("tdecq_db")
        m = paneldata.eye_measures(sim, cfg, node=node)
        if kind == "all":
            return m
        table = {"tdecq": lambda: (m.get("tdecq") or {}).get("tdecq_db"),
                 "eye_height": lambda: min(m.get("eye_heights") or [float("nan")]),
                 "eye_width": lambda: min(m.get("eye_widths_ui") or [float("nan")]),
                 "oma": lambda: m.get("oma_outer_mw"), "er": lambda: m.get("er_db"),
                 "rlm": lambda: m.get("rlm_proxy"), "sndr": lambda: m.get("sndr_db")}
        return table[kind]()

    def jitter(self, key):
        return self._offload(lambda: self._jitter(key))

    def _jitter(self, key):
        cfg, sim = self._sim()
        j = paneldata.jitter_panel(sim, cfg)
        tf = j.get("tail_fit") or {}
        if key == "all":
            return tf
        alias = {"tj_ps": "tj_1e12_ps"}
        return tf.get(alias.get(key, key))

    def com(self):
        return self._offload(lambda: self._com())

    def _com(self):
        cfg, sim = self._sim()
        return (paneldata.com_panel(sim, cfg, profile=PROFILE["name"]) or {}).get("com_db")

    def standards(self):
        return self._offload(lambda: self._standards())

    def _standards(self):
        cfg, sim = self._sim()
        return paneldata.standards_report(sim, cfg, profile=PROFILE["name"])

    # --- BERT ----------------------------------------------------------------
    def ed_item(self, item):
        return self._offload(lambda: self._ed_item(item))

    def _ed_item(self, item):
        acc = bench_cumulative(BENCH.snapshot() or {})
        cfg, sim, records, _ = BENCH.capture()
        key = item.upper().replace(" ", "")
        pam4 = bert_pam4_result(sim, acc, mapping=cfg.pam4_mapping) if sim is not None else {"available": False}
        lanes = pam4.get("lanes") or {}
        table = {
            "CURRENT:ER:TOTAL": acc.get("ber"), "CURRENT:EC:TOTAL": acc.get("errors"),
            "CURRENT:BITS": acc.get("bits"), "CURRENT:SYNC:LOSS": acc.get("sync_losses"),
            "CURRENT:CLOCK:LOSS": acc.get("clock_losses"),
            "CURRENT:FEC:UNCORR": acc.get("fec_uncorrectable"),
            "CURRENT:ER:MSB": (lanes.get("MSB") or {}).get("ER"), "CURRENT:ER:LSB": (lanes.get("LSB") or {}).get("ER"),
            "CURRENT:EC:MSB": (lanes.get("MSB") or {}).get("EC"), "CURRENT:EC:LSB": (lanes.get("LSB") or {}).get("EC"),
            "CURRENT:EC:INS": sum((lanes.get(k) or {}).get("INS", {}).get("EC", 0) for k in ("MSB", "LSB")),
            "CURRENT:EC:OMI": sum((lanes.get(k) or {}).get("OMI", {}).get("EC", 0) for k in ("MSB", "LSB")),
            "CURRENT:SER": (pam4.get("symbol_error_matrix") or {}).get("symbol_error_ratio"),
        }
        if key not in table:
            raise scpi.ScpiError(-224, f"Illegal parameter value; {item}")
        return table[key]

    def pam4_result(self):
        return self._offload(lambda: self._pam4_result())

    def _pam4_result(self):
        cfg, sim = self._sim()
        return bert_pam4_result(sim, bench_cumulative(BENCH.snapshot() or {}), mapping=cfg.pam4_mapping)

    def inject(self, n, target):
        return BENCH.inject_errors(int(n), burst=False, target=str(target).lower())

    def traffic_stats(self):
        return self._offload(lambda: self._traffic_stats())

    def _traffic_stats(self):
        cfg, sim = self._sim()
        return paneldata.l2_panel(sim, cfg)

    # --- esperimenti (sincroni per la connessione SCPI) ---------------------
    async def experiment(self, name, arg):
        cfg = BENCH.cfg
        profile = PROFILE["name"]
        evt = EXPERIMENT.begin(f"SCPI {name}")
        if evt is None:
            raise scpi.ScpiError(
                -221, f"Settings conflict; experiment already running: {EXPERIMENT.current}")
        if name == "rfc2544":
            fn = lambda: rfc2544_report(  # noqa: E731
                cfg, frame_sizes=arg or (64, 256, 512, 1024),
                profile=profile, cancel=evt)
        elif name == "y1564":
            fn = lambda: y1564_report(cfg, profile=profile, cancel=evt)  # noqa: E731
        elif name == "dr4":
            fn = lambda: run_dr4_tdecq_e2e(  # noqa: E731
                seed=int(arg or 500283), golden=LAST_GOLDEN["result"], cancel=evt)
        elif name == "stressed_rx":
            fn = lambda: run_stressed_receiver(cfg, profile=profile,  # noqa: E731
                                               target_secq_db=(float(arg) if arg is not None else None),
                                               cancel=evt)
        elif name == "golden_library":
            fn = lambda: correlate_library(  # noqa: E731
                "ieee_802_3bs_smf_2017", optimize=str(arg or "min_tdecq"), cancel=evt)
        else:
            EXPERIMENT.end()
            raise scpi.ScpiError(-224, f"Illegal parameter value; {name}")
        was_running = BENCH.running
        broadcast({"type": "experiment", "name": f"SCPI {name}", "state": "start"})
        try:
            if was_running:
                await tornado.ioloop.IOLoop.current().run_in_executor(None, BENCH.stop)
            report = await tornado.ioloop.IOLoop.current().run_in_executor(EXPERIMENT_POOL, fn)
        except ExperimentCancelled as exc:
            raise scpi.ScpiError(-200, "Execution error; experiment cancelled") from exc
        finally:
            EXPERIMENT.end()
            if was_running:
                BENCH.start()
            broadcast({"type": "experiment", "name": f"SCPI {name}", "state": "end"})
        store = {"rfc2544": LAST_RFC2544, "y1564": LAST_Y1564, "stressed_rx": LAST_STRESSED,
                 "golden_library": LAST_GOLDEN_LIBRARY}
        if name in store:
            store[name]["report"] = paneldata.J(report)
        elif name == "dr4":
            LAST_DR4["report"] = paneldata.J(report)
        return None

    def report(self, kind, fmt):
        return self._offload(lambda: self._report(kind, fmt))

    def _report(self, kind, fmt):
        from labpro import instrument_reports as ir
        if kind == "standards":
            cfg, sim = self._sim()
            rep = paneldata.standards_report(sim, cfg, profile=PROFILE["name"])
            return paneldata.standards_report_markdown(rep) if fmt == "md" else rep
        if kind == "bert":
            res = self._pam4_result()
            return {"json": lambda: res, "md": lambda: ir.bert_markdown(res), "csv": lambda: ir.bert_csv(res)}[fmt]()
        table = {"rfc2544": (LAST_RFC2544, {"md": ir.rfc2544_markdown, "xml": ir.rfc2544_xml}),
                 "y1564": (LAST_Y1564, {"md": ir.y1564_markdown, "csv": ir.y1564_csv}),
                 "dr4": (LAST_DR4, {}), "stressed_rx": (LAST_STRESSED, {}),
                 "golden_library": (LAST_GOLDEN_LIBRARY, {})}
        if kind not in table:
            raise scpi.ScpiError(-224, f"Illegal parameter value; {kind}")
        store, fmts = table[kind]
        rep = store.get("report")
        if rep is None:
            raise scpi.ScpiError(-230, "Data corrupt or stale; run the procedure first")
        if fmt == "json":
            return rep
        if fmt not in fmts:
            raise scpi.ScpiError(-224, f"Illegal parameter value; {fmt}")
        return fmts[fmt](rep)


def main():
    global MAIN_LOOP, PERSIST
    parser = argparse.ArgumentParser(
        description="Run SerDes Optical Lab PRO on the local loopback interface.")
    parser.add_argument("--port", type=int, default=8640,
                        help="loopback TCP port (default: 8640)")
    parser.add_argument("--no-autostart", action="store_true",
                        help="start with continuous acquisition stopped")
    parser.add_argument("--scpi-port", type=int, default=scpi.DEFAULT_PORT,
                        help="loopback TCP port of the SCPI server (default: 5025, PyVISA "
                             "TCPIP::127.0.0.1::5025::SOCKET)")
    parser.add_argument("--no-scpi", action="store_true",
                        help="do not start the SCPI server")
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
    if not 1 <= args.scpi_port <= 65535:
        parser.error("--scpi-port must be between 1 and 65535")
    SCPI_SETTINGS["enabled"] = not args.no_scpi
    SCPI_SETTINGS["port"] = args.scpi_port
    SCPI_SETTINGS["status"] = "disabled" if args.no_scpi else "starting"
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
