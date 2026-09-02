"""Server SCPI su TCP per controllare il banco come uno strumento reale.

Compatibile con PyVISA/pyvisa-py (``TCPIP::host::5025::SOCKET``,
``read_termination="\\n"``): comandi separati da ``;``, mnemonici con forma
corta/lunga (``MEAS:EYE:TDEQ?`` ≡ ``MEASure:EYE:TDEQ?``), query con ``?``,
argomenti separati da virgola con stringhe fra virgolette, coda errori
``SYSTem:ERRor?`` e ``*IDN?``/``*RST``/``*OPC?``/``*CLS`` come da IEEE 488.2.

L'albero dei comandi ricalca gli strumenti reali che il banco emula:

* ``MEASure:EYE:*`` / ``MEASure:JITTer:*`` — misure del DCA (FlexDCA);
* ``SOURce:*`` (PPG) e ``SENSe:*`` / ``CALCulate:DATA:EALarm?`` (ED) — BERT
  in stile MP1900A;
* ``TRAFfic:*`` — generatore/analyzer di traffico e i report RFC 2544 /
  Y.1564 in formato Xena2544 e SAMComplete;
* ``PROCedure:*`` — DR4, stressed RX, libreria golden;
* ``CONFigure:PARameter`` — accesso generico a ogni campo di ``LinkConfig``.

DICHIARATO: i mnemonici sono ispirati agli strumenti ma non replicano le loro
grammatiche complete; le risposte strutturate sono JSON su una riga.  Il
server non è autenticato e va esposto solo su localhost.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
import time

SCPI_VERSION = "1999.0"
DEFAULT_PORT = 5025
_MNEMONIC = re.compile(r"^([A-Za-z*][A-Za-z0-9*]*)(\d*)$")


class ScpiError(Exception):
    """Errore SCPI con codice IEEE 488.2 (negativo)."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = int(code)
        self.message = message


def _split_top(text: str, sep: str) -> list[str]:
    """Split che rispetta le virgolette."""
    out, buf, quote = [], [], None
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch == sep:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return out


def parse_args(text: str) -> list:
    """Argomenti SCPI: numeri → float/int, stringhe fra virgolette → str,
    parole nude (ON/OFF, PRBS, MAX) → str maiuscola."""
    text = text.strip()
    if not text:
        return []
    out = []
    for tok in _split_top(text, ","):
        tok = tok.strip()
        if not tok:
            continue
        if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "\"'":
            out.append(tok[1:-1])
            continue
        try:
            v = float(tok)
            out.append(int(v) if v.is_integer() and "." not in tok and "e" not in tok.lower() else v)
        except ValueError:
            out.append(tok.upper())
    return out


def _node_matches(node: str, spec: str) -> bool:
    """``spec`` = mnemonico con la forma corta in MAIUSCOLO (es. MEASure)."""
    m = _MNEMONIC.match(node)
    if not m:
        return False
    word = m.group(1).upper()
    short = "".join(c for c in spec if c.isupper() or c == "*" or c.isdigit())
    return word in (short.upper(), spec.upper())


class ScpiDispatcher:
    """Tabella dei comandi: ``register("MEASure:EYE:TDEQ", query=fn)``."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.commands: list[tuple[list[str], dict]] = []
        self.errors: list[tuple[int, str]] = []
        self.started = time.time()

    def register(self, path: str, *, set=None, query=None, doc: str = ""):   # noqa: A002
        self.commands.append((path.split(":"), {"set": set, "query": query, "doc": doc, "path": path}))

    def push_error(self, code: int, message: str):
        self.errors.append((code, message))
        if len(self.errors) > 32:
            self.errors.pop(0)

    def _lookup(self, nodes: list[str]):
        for spec_nodes, entry in self.commands:
            if len(spec_nodes) != len(nodes):
                continue
            if all(_node_matches(n, s) for n, s in zip(nodes, spec_nodes)):
                return entry
        return None

    async def execute(self, line: str) -> list[str]:
        """Esegue una riga (comandi separati da ``;``); ritorna le risposte
        delle query.  Gli errori finiscono nella coda SYSTem:ERRor."""
        responses = []
        for part in _split_top(line.strip(), ";"):
            part = part.strip()
            if not part:
                continue
            m = re.match(r"^:?(\*?[A-Za-z][A-Za-z0-9:*]*)(\??)\s*(.*)$", part)
            if not m:
                self.push_error(-100, f"Command error; {part!r}")
                continue
            head, is_query, rest = m.group(1), bool(m.group(2)), m.group(3)
            nodes = [n for n in head.strip(":").split(":") if n]
            entry = self._lookup(nodes)
            if entry is None:
                self.push_error(-113, f"Undefined header; {head}")
                continue
            fn = entry["query"] if is_query else entry["set"]
            if fn is None:
                self.push_error(-100 if is_query else -104,
                                f"{'Query' if is_query else 'Command'} not allowed; {head}")
                continue
            try:
                args = parse_args(rest)
                out = fn(*args)
                if inspect.isawaitable(out):
                    out = await out
            except ScpiError as exc:
                self.push_error(exc.code, exc.message)
                continue
            except (ValueError, KeyError, TypeError) as exc:
                self.push_error(-222, f"Data out of range; {exc}")
                continue
            except Exception as exc:                 # esperimento fallito ecc.
                self.push_error(-300, f"Device-specific error; {exc}")
                continue
            if is_query:
                responses.append(format_response(out))
        return responses


def format_response(v) -> str:
    if v is None:
        return "NAN"                     # valore non disponibile (come 9.91E+37 sugli strumenti)
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int,)):
        return str(v)
    if isinstance(v, float):
        return f"{v:.9g}"
    if isinstance(v, str):
        return v
    return json.dumps(v, separators=(",", ":"), default=str)


def build_dispatcher(ctx) -> ScpiDispatcher:
    """Albero dei comandi sopra il contesto del banco (``ctx``: vedi
    ``labpro.server.ScpiContext``)."""
    d = ScpiDispatcher(ctx)
    r = d.register

    # --- IEEE 488.2 common commands -----------------------------------------
    r("*IDN", query=lambda: f"SerDes Optical Lab PRO,LabPro,{ctx.serial()},{ctx.version()}", doc="identity")
    r("*RST", set=lambda: ctx.reset(), doc="preset default and clear statistics")
    r("*CLS", set=lambda: d.errors.clear(), doc="clear the error queue")
    r("*OPC", set=lambda: None, query=lambda: 1, doc="operation complete (commands are synchronous)")
    r("*WAI", set=lambda: None)
    r("*ESR", query=lambda: 0)
    r("*STB", query=lambda: 0)
    r("*TST", query=lambda: 0)
    r("SYSTem:ERRor", query=lambda: ('%d,"%s"' % d.errors.pop(0)) if d.errors else '0,"No error"')
    r("SYSTem:ERRor:COUNt", query=lambda: len(d.errors))
    r("SYSTem:VERSion", query=lambda: SCPI_VERSION)
    r("SYSTem:HELP", query=lambda: [e["path"] + ("?" if e["query"] else "") for _, e in d.commands])
    r("SYSTem:UPTime", query=lambda: time.time() - d.started)

    # --- configurazione generica -------------------------------------------
    r("CONFigure:PARameter", set=lambda name, value: ctx.set_param(str(name), value),
      query=lambda name: ctx.get_param(str(name)), doc='CONF:PAR "field",value · CONF:PAR? "field"')
    r("CONFigure:PARameter:LIST", query=lambda: ctx.param_names())
    r("CONFigure:PROFile", set=lambda name: ctx.load_profile(str(name)), query=lambda: ctx.profile_name() or "")
    r("CONFigure:PRESet", set=lambda name: ctx.load_preset(str(name)))
    r("CONFigure:HASH", query=lambda: ctx.config_hash())
    r("CONFigure:ALL", query=lambda: ctx.config_dict())

    # --- acquisizione (DCA/BERT RUN) ---------------------------------------
    r("ACQuire:RUN", set=lambda: ctx.run(True))
    r("ACQuire:STOP", set=lambda: ctx.run(False))
    r("ACQuire:STATe", set=lambda st: ctx.run(_onoff(st)), query=lambda: 1 if ctx.running() else 0)
    r("ACQuire:RECords", query=lambda: ctx.records())
    r("ACQuire:CLEar", set=lambda: ctx.reset_stats())
    r("ACQuire:SINGle", set=lambda: ctx.single(), doc="acquire one record synchronously")

    # --- DCA (FlexDCA-like) --------------------------------------------------
    r("MEASure:EYE:TDEQ", query=lambda node="OPTICAL": ctx.measure("tdecq", node))
    r("MEASure:EYE:HEIGht", query=lambda node="VCTLE": ctx.measure("eye_height", node))
    r("MEASure:EYE:WIDTh", query=lambda node="VCTLE": ctx.measure("eye_width", node))
    r("MEASure:EYE:OMA", query=lambda node="OPTICAL": ctx.measure("oma", node))
    r("MEASure:EYE:ERATio", query=lambda node="OPTICAL": ctx.measure("er", node))
    r("MEASure:EYE:RLM", query=lambda node="VCTLE": ctx.measure("rlm", node))
    r("MEASure:EYE:SNDR", query=lambda node="VCTLE": ctx.measure("sndr", node))
    r("MEASure:EYE:ALL", query=lambda node="VCTLE": ctx.measure("all", node))
    r("MEASure:JITTer:RJ", query=lambda: ctx.jitter("rj_ps"))
    r("MEASure:JITTer:DJ", query=lambda: ctx.jitter("dj_dd_ps"))
    r("MEASure:JITTer:TJ", query=lambda: ctx.jitter("tj_ps"))
    r("MEASure:JITTer:J2", query=lambda: ctx.jitter("j2_ps"))
    r("MEASure:JITTer:J9", query=lambda: ctx.jitter("j9_ps"))
    r("MEASure:JITTer:ALL", query=lambda: ctx.jitter("all"))
    r("MEASure:COM", query=lambda: ctx.com())
    r("MEASure:STANdards", query=lambda: ctx.standards())

    # --- BERT: ED (MP1900A-like) --------------------------------------------
    r("SENSe:MEASure:STARt", set=lambda: ctx.run(True))
    r("SENSe:MEASure:STOP", set=lambda: ctx.run(False))
    r("SENSe:MEASure:STATe", query=lambda: "RUNNING" if ctx.running() else "STOPPED")
    r("SENSe:PATTern:TYPE", query=lambda: ctx.get_param("pattern"))
    r("CALCulate:DATA:EALarm", query=lambda item="CURRENT:ER:TOTAL": ctx.ed_item(str(item)),
      doc='CALC:DATA:EAL? "CURRent:ER:TOTal" | "CURRent:EC:TOTal" | ":ER:MSB" | ":ER:LSB" | ":EC:INS" | ":EC:OMI" | ":SYNC:LOSS" | "CURRent:BITS"')
    r("CALCulate:DATA:PAM4", query=lambda: ctx.pam4_result())
    r("SENSe:ERRor:INSert", set=lambda n=1, target="RANDOM": ctx.inject(int(n), str(target)),
      doc="insert n bit errors (bench must be running)")

    # --- BERT: PPG (MP1900A-like) -------------------------------------------
    r("SOURce:PATTern:TYPE", set=lambda kind: ctx.set_param("pattern", _pattern(str(kind))),
      query=lambda: ctx.get_param("pattern").upper())
    r("SOURce:PATTern:PRBS:LENGth", set=lambda n: ctx.set_param("prbs_order", int(n)),
      query=lambda: ctx.get_param("prbs_order"))
    r("SOURce:OUTPut:DATA:ENABle", set=lambda st: ctx.set_param("tx_output_on", _onoff(st)),
      query=lambda: 1 if ctx.get_param("tx_output_on") else 0)
    r("SOURce:JITTer:SJ:AMPLitude", set=lambda ui: ctx.set_param("tx_pj_amp_ui", float(ui)),
      query=lambda: ctx.get_param("tx_pj_amp_ui"))
    r("SOURce:JITTer:SJ:FREQuency", set=lambda hz: ctx.set_param("tx_pj_freq_mhz", float(hz) / 1e6),
      query=lambda: ctx.get_param("tx_pj_freq_mhz") * 1e6)
    r("SOURce:JITTer:RJ:AMPLitude", set=lambda fs: ctx.set_param("tx_rj_rms_fs", float(fs)),
      query=lambda: ctx.get_param("tx_rj_rms_fs"))
    r("SOURce:JITTer:BUJ:AMPLitude", set=lambda ui: ctx.set_param("tx_buj_amp_ui", float(ui)),
      query=lambda: ctx.get_param("tx_buj_amp_ui"))
    r("SOURce:SI:AMPLitude", set=lambda pct: ctx.set_param("tx_si_amp_pct", float(pct)),
      query=lambda: ctx.get_param("tx_si_amp_pct"))
    r("SOURce:SI:FREQuency", set=lambda hz: ctx.set_param("tx_si_freq_mhz", float(hz) / 1e6),
      query=lambda: ctx.get_param("tx_si_freq_mhz") * 1e6)
    r("SOURce:BAUDrate", set=lambda bd: ctx.set_param("symbol_rate_hz", float(bd)),
      query=lambda: ctx.get_param("symbol_rate_hz"))
    r("SOURce:MODulation", set=lambda m: ctx.set_param("modulation", str(m).upper()),
      query=lambda: ctx.get_param("modulation"))
    r("SOURce:FEC", set=lambda m: ctx.set_param("fec_mode", str(m).lower()),
      query=lambda: ctx.get_param("fec_mode"))

    # --- traffico (Xena / VIAVI) ---------------------------------------------
    r("TRAFfic:ENABle", set=lambda st: ctx.set_param("pattern", "eth" if _onoff(st) else "prbs"),
      query=lambda: 1 if ctx.get_param("pattern") == "eth" else 0)
    r("TRAFfic:WORKload", set=lambda w: ctx.set_param("l2_workload", str(w).lower()),
      query=lambda: ctx.get_param("l2_workload"))
    r("TRAFfic:SCHeduler", set=lambda w: ctx.set_param("l2_scheduler", str(w).lower()),
      query=lambda: ctx.get_param("l2_scheduler"))
    r("TRAFfic:FRAMe:SIZE", set=lambda b: ctx.set_param("l2_frame_bytes", int(b)),
      query=lambda: ctx.get_param("l2_frame_bytes"))
    r("TRAFfic:IPG", set=lambda b: ctx.set_param("l2_ipg_bytes", int(b)),
      query=lambda: ctx.get_param("l2_ipg_bytes"))
    r("TRAFfic:STATistics", query=lambda: ctx.traffic_stats())
    r("TRAFfic:RFC2544:RUN", set=lambda *sizes: ctx.experiment("rfc2544", [int(s) for s in sizes] or None))
    r("TRAFfic:RFC2544:RESult", query=lambda fmt="JSON": ctx.report("rfc2544", str(fmt).lower()))
    r("TRAFfic:Y1564:RUN", set=lambda: ctx.experiment("y1564", None))
    r("TRAFfic:Y1564:RESult", query=lambda fmt="JSON": ctx.report("y1564", str(fmt).lower()))

    # --- procedure ------------------------------------------------------------
    r("PROCedure:DR4:RUN", set=lambda seed=500283: ctx.experiment("dr4", int(seed)))
    r("PROCedure:DR4:RESult", query=lambda: ctx.report("dr4", "json"))
    r("PROCedure:STRessed:RUN", set=lambda target=None: ctx.experiment("stressed_rx", target))
    r("PROCedure:STRessed:RESult", query=lambda: ctx.report("stressed_rx", "json"))
    r("PROCedure:GOLDen:LIBRary:RUN", set=lambda opt="MIN_TDECQ": ctx.experiment("golden_library", str(opt).lower()))
    r("PROCedure:GOLDen:LIBRary:RESult", query=lambda: ctx.report("golden_library", "json"))
    r("REPort:STANdards", query=lambda fmt="JSON": ctx.report("standards", str(fmt).lower()))
    r("REPort:BERT", query=lambda fmt="JSON": ctx.report("bert", str(fmt).lower()))
    return d


def _onoff(v) -> bool:
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).upper()
    if s in ("ON", "1", "TRUE"):
        return True
    if s in ("OFF", "0", "FALSE"):
        return False
    raise ScpiError(-224, f"Illegal parameter value; {v}")


def _pattern(kind: str) -> str:
    table = {"PRBS": "prbs", "SSPRQ": "ssprq", "ETH": "eth", "ETHERNET": "eth",
             "CLOCK": "clock", "HEX": "custom", "CUSTOM": "custom", "SSPRQLIKE": "ssprq_like"}
    if kind.upper() not in table:
        raise ScpiError(-224, f"Illegal parameter value; {kind}")
    return table[kind.upper()]


async def start_server(ctx, host: str = "127.0.0.1", port: int = DEFAULT_PORT):
    """Avvia il server SCPI sul loop asyncio corrente."""
    dispatcher = build_dispatcher(ctx)

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            while True:
                raw = await reader.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", "replace").strip("\r\n")
                if not line.strip():
                    continue
                for resp in await dispatcher.execute(line):
                    writer.write((resp + "\n").encode("utf-8"))
                await writer.drain()
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()

    server = await asyncio.start_server(handle, host, port)
    server.dispatcher = dispatcher
    return server
