"""Server SCPI: grammatica IEEE 488.2 (forme corte/lunghe, query, argomenti,
coda errori), dispatcher sull'albero dei comandi e sessione TCP reale
compatibile con PyVISA (``TCPIP::127.0.0.1::<port>::SOCKET``)."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from labpro import scpi                          # noqa: E402


class FakeCtx:
    """Contesto minimo: un dict di parametri e contatori fittizi."""

    def __init__(self):
        self.params = {"pattern": "prbs", "prbs_order": 13, "tx_output_on": True,
                       "tx_pj_amp_ui": 0.0, "tx_pj_freq_mhz": 100.0, "symbol_rate_hz": 53.125e9,
                       "modulation": "PAM4", "fec_mode": "kp4", "l2_workload": "custom",
                       "tx_si_amp_pct": 0.0, "tx_si_freq_mhz": 1000.0}
        self._running = False
        self.experiments = []

    def serial(self): return "0001"
    def version(self): return "0.2.0"
    def reset(self): self.params["pattern"] = "prbs"
    def reset_stats(self): pass
    def set_param(self, name, value):
        if name not in self.params:
            raise KeyError(name)
        self.params[name] = value
    def get_param(self, name): return self.params[name]
    def param_names(self): return sorted(self.params)
    def load_profile(self, name): self.profile = name
    def load_preset(self, name): self.profile = None
    def profile_name(self): return getattr(self, "profile", None)
    def config_hash(self): return "abc123"
    def config_dict(self): return dict(self.params)
    def run(self, on): self._running = bool(on)
    def running(self): return self._running
    def records(self): return 7
    def single(self): return 1
    def measure(self, kind, node): return {"tdecq": 3.25, "eye_height": 0.12}.get(kind, {"kind": kind, "node": node})
    def jitter(self, key): return 1.5 if key != "all" else {"rj_ps": 1.5}
    def com(self): return 4.2
    def standards(self): return {"ok": True}
    def ed_item(self, item): return {"CURRENT:ER:TOTAL": 1e-6, "CURRENT:EC:TOTAL": 3}[item.upper()]
    def pam4_result(self): return {"available": True}
    def inject(self, n, target): return {"bits": n, "target": target}
    def traffic_stats(self): return {"frames_ok": 10}
    async def experiment(self, name, arg):
        await asyncio.sleep(0.01)
        self.experiments.append((name, arg))
    def report(self, kind, fmt): return {"kind": kind, "fmt": fmt}


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_parse_args_numbers_strings_and_keywords():
    assert scpi.parse_args('"pattern", 13, 1.5e9, ON, \'x,y\'') == ["pattern", 13, 1.5e9, "ON", "x,y"]
    assert scpi.parse_args("") == []


def test_short_and_long_mnemonics_and_queries():
    ctx = FakeCtx()
    d = scpi.build_dispatcher(ctx)
    assert run(d.execute("*IDN?")) == ["SerDes Optical Lab PRO,LabPro,0001,0.2.0"]
    assert run(d.execute("meas:eye:tdeq?")) == ["3.25"]
    assert run(d.execute("MEASure:EYE:TDEQ?")) == ["3.25"]
    assert run(d.execute(":SOURce:PATTern:TYPE SSPRQ;:SOUR:PATT:TYPE?")) == ["SSPRQ"]
    assert ctx.params["pattern"] == "ssprq"
    assert run(d.execute("SOUR:JITT:SJ:FREQ 2.5e8; SOUR:JITT:SJ:FREQ?")) == ["250000000"]
    assert ctx.params["tx_pj_freq_mhz"] == pytest.approx(250.0)
    assert run(d.execute('CONF:PAR "prbs_order", 15; CONF:PAR? "prbs_order"')) == ["15"]
    assert run(d.execute("ACQ:RUN; ACQ:STAT?")) == ["1"]
    assert run(d.execute("SENS:MEAS:STOP; SENS:MEAS:STAT?")) == ["STOPPED"]
    assert run(d.execute('CALC:DATA:EAL? "CURRent:EC:TOTal"')) == ["3"]
    assert json.loads(run(d.execute("TRAF:STAT?"))[0]) == {"frames_ok": 10}
    assert run(d.execute("SYST:ERR?")) == ['0,"No error"']


def test_error_queue_and_async_experiments():
    ctx = FakeCtx()
    d = scpi.build_dispatcher(ctx)
    assert run(d.execute("MEAS:NOPE?")) == []
    assert run(d.execute("SYST:ERR?")) == ['-113,"Undefined header; MEAS:NOPE"']
    run(d.execute("SOUR:OUTP:DATA:ENAB MAYBE"))
    err = run(d.execute("SYST:ERR?"))[0]
    assert err.startswith("-224,")
    run(d.execute('CONF:PAR "no_such_field", 1'))
    assert run(d.execute("SYST:ERR?"))[0].startswith("-222,")
    assert run(d.execute("SYST:ERR?")) == ['0,"No error"']
    assert run(d.execute("TRAF:RFC2544:RUN 64, 512; *OPC?")) == ["1"]
    assert ctx.experiments == [("rfc2544", [64, 512])]
    assert json.loads(run(d.execute('TRAF:RFC2544:RES? "MD"'))[0]) == {"kind": "rfc2544", "fmt": "md"}
    helps = json.loads(run(d.execute("SYST:HELP?"))[0])
    assert "MEASure:EYE:TDEQ?" in helps and "*RST" in helps


def test_tcp_session_like_pyvisa_socket():
    async def session():
        ctx = FakeCtx()
        server = await scpi.start_server(ctx, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)

        async def ask(cmd):
            writer.write((cmd + "\n").encode())
            await writer.drain()
            return (await asyncio.wait_for(reader.readline(), 5)).decode().strip()

        idn = await ask("*IDN?")
        tdecq = await ask("MEAS:EYE:TDEQ?")
        await ask("SOUR:PATT:PRBS:LENG 31; SOUR:PATT:PRBS:LENG?")
        length = ctx.params["prbs_order"]
        writer.write(b"BAD:CMD\n")
        await writer.drain()                                    # nessuna risposta
        err = await ask("SYST:ERR?")
        writer.close()
        server.close()
        await server.wait_closed()
        return idn, tdecq, length, err

    idn, tdecq, length, err = run(session())
    assert idn.startswith("SerDes Optical Lab PRO,LabPro,")
    assert tdecq == "3.25" and length == 31
    assert err.startswith("-113,")


def test_version_matches_pyproject():
    import re
    import labpro
    text = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()
    assert re.search(r'^version = "([^"]+)"', text, re.M).group(1) == labpro.__version__


def test_real_context_config_and_measurements_without_running_bench():
    """ScpiContext vero sopra il banco fermo: configurazione e misure
    sull'ultimo record acquisito on demand."""
    from labpro import server
    cfg_before = server.BENCH.cfg
    profile_before = server.PROFILE["name"]
    persist_before = server.PERSIST
    running_before = server.BENCH.running
    server.BENCH.stop()
    server.PERSIST = None
    ctx = server.ScpiContext()
    d = scpi.build_dispatcher(ctx)
    try:
        assert run(d.execute("*IDN?"))[0].endswith(labpro_version())
        assert run(d.execute('CONF:PAR "prbs_order", 15; CONF:PAR? "prbs_order"')) == ["15"]
        assert run(d.execute("SOUR:PATT:PRBS:LENG 13; SOUR:PATT:PRBS:LENG?")) == ["13"]
        run(d.execute('CONF:PAR "no_such", 1'))
        assert run(d.execute("SYST:ERR?"))[0].startswith("-222,")
        names = json.loads(run(d.execute("CONF:PAR:LIST?"))[0])
        assert "tx_si_amp_pct" in names and "l2_workload" in names
        assert run(d.execute("SOUR:SI:AMPL 3; SOUR:SI:AMPL?")) == ["3"]
        run(d.execute("SOUR:SI:AMPL 0"))
        # ACQ:SINGLE really produces one fresh record while leaving a
        # previously stopped bench stopped.
        assert run(d.execute("ACQ:SING")) == []
        assert int(run(d.execute("ACQ:REC?"))[0]) >= 1
        assert server.BENCH.running is False
        tdecq = run(d.execute("MEAS:EYE:TDEQ? OPTICAL"))
        assert len(tdecq) == 1 and float(tdecq[0]) > 0
        assert run(d.execute("SYST:ERR?")) == ['0,"No error"']
    finally:
        server.BENCH.stop()
        server.BENCH.set_config(cfg_before)
        server.PROFILE["name"] = profile_before
        server.PERSIST = persist_before
        if running_before:
            server.BENCH.start()


def test_real_scpi_context_shares_the_global_experiment_lock():
    from labpro import server
    ctx = server.ScpiContext()
    d = scpi.build_dispatcher(ctx)
    evt = server.EXPERIMENT.begin("HTTP procedure")
    assert evt is not None
    try:
        assert run(d.execute("TRAF:RFC2544:RUN 64")) == []
        assert run(d.execute("SYST:ERR?"))[0].startswith("-221,")
    finally:
        server.EXPERIMENT.end()


def labpro_version():
    import labpro
    return labpro.__version__
