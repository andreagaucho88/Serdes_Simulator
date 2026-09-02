"""LiveBench: acquisizione continua con accumulo statistico.

Un thread esegue simulazioni light back-to-back (nuovo seed a ogni record) e
accumula i contatori come un BERT/FEC-analyzer reale: bit totali, errori,
frame FEC clean/corretti/persi, istogramma errori-per-frame. I contatori si
riempiono nel tempo; un cambio di configurazione azzera l'accumulo (dichiarato)
e riparte.
"""

from __future__ import annotations

import logging
import threading
import time

import numpy as np
from scipy import stats as sp_stats

from .config import LinkConfig
from .engine import simulate

log = logging.getLogger("serdes_sim.livebench")


class BertNotRunning(RuntimeError):
    """Raised when an injection is requested without a live receiver."""


class InjectionInProgress(RuntimeError):
    """Raised when the single-flight injection slot is already occupied."""


class LiveBench:
    def __init__(self, cfg: LinkConfig = None, seed0: int = 500_000):
        self._lock = threading.RLock()
        self._cfg = cfg or LinkConfig()
        self._seed0 = seed0
        self._seed = seed0
        self._running = False
        self._thread = None
        self._gen = 0                  # generazione del thread di acquisizione
        self._stop_evt = threading.Event()
        self.on_record = None          # callback(snapshot) dopo ogni record
        self.latest = None             # ultimo SimResult (per scope/spettro)
        self._inject_seq = 0           # transaction id monotono del BERT
        # camera climatica: profilo di temperatura del RICEVITORE nel tempo.
        # Il die insegue la camera con un lag del 1° ordine (tau termico);
        # lo stato NON si azzera al cambio config (la camera è "fisica")
        self.chamber = {"on": False, "mode": "cycle", "t_min": -10.0,
                        "t_max": 85.0, "period_s": 180.0, "tau_s": 10.0}
        self._die_t = 25.0
        self._chamber_t0 = time.time()
        self._last_rec_t = time.time()
        self._reset_locked()

    def set_chamber(self, **kw):
        with self._lock:
            restart = kw.get("on") and not self.chamber["on"]
            for k, v in kw.items():
                if k in self.chamber:
                    self.chamber[k] = (bool(v) if k == "on" else
                                       str(v) if k == "mode" else float(v))
            self.chamber["t_min"] = max(-40.0, min(self.chamber["t_min"], 125.0))
            self.chamber["t_max"] = max(-40.0, min(self.chamber["t_max"], 125.0))
            self.chamber["period_s"] = max(10.0, self.chamber["period_s"])
            self.chamber["tau_s"] = max(1.0, self.chamber["tau_s"])
            if restart:
                self._chamber_t0 = time.time()

    def chamber_settings(self) -> dict:
        """Copia consistente delle impostazioni camera (per la persistenza)."""
        with self._lock:
            return dict(self.chamber)

    def _chamber_target(self, now):
        ch = self.chamber
        el = now - self._chamber_t0
        per = ch["period_s"]
        if ch["mode"] == "soak":
            return ch["t_max"]
        if ch["mode"] == "ramp":
            f = min(el / per, 1.0)
            return ch["t_min"] + f * (ch["t_max"] - ch["t_min"])
        frac = (el / per) % 1.0                     # cycle triangolare
        tri = 2 * frac if frac < 0.5 else 2 - 2 * frac
        return ch["t_min"] + tri * (ch["t_max"] - ch["t_min"])

    def _chamber_step(self, now):
        """Aggiorna la temperatura del die (lag 1° ordine verso la camera)."""
        dt = max(now - self._last_rec_t, 1e-3)
        self._last_rec_t = now
        target = self._chamber_target(now)
        import math
        alpha = 1.0 - math.exp(-dt / self.chamber["tau_s"])
        self._die_t += alpha * (target - self._die_t)
        return float(min(max(self._die_t, -40.0), 125.0))

    # ------------------------------------------------------------------ state
    def _reset_locked(self):
        # Non lasciare esposta una waveform appartenente alla configurazione
        # precedente: i pannelli live devono dichiarare/far vedere il record
        # che stanno realmente misurando.
        self.latest = None
        self.records = 0
        self.bits_total = 0
        self.bit_errors_total = 0
        self.sym_total = 0
        self.sym_errors_total = 0
        self.frames_total = 0
        self.frames_clean = 0
        self.frames_corrected = 0
        self.frames_lost = 0
        self.frames_miscorrected = 0
        self.symbols_corrected = 0
        self.link_down_records = 0
        self.sync_losses = 0        # transizioni lock→no-lock (ED)
        # L2 (pattern eth)
        self.l2_expected = 0
        self.l2_detected = 0
        self.l2_ok = 0
        self.l2_fcs_bad = 0
        self.l2_lost = 0
        self.l2_thr_sum = 0.0
        self.l2_records = 0
        self.l2_dup = 0
        self.l2_ooo = 0
        self.l2_lost_emu = 0
        self.l2_corrupt_emu = 0
        self.l1_records = 0
        self.l1_locked = 0
        self.l1_header_errors = 0
        self.l1_blocks = 0
        self.l1_hi_ber = 0
        # BERT error insertion: transazione single-flight sul prossimo record.
        # Il risultato resta latched: il record live successivo non deve far
        # sparire l'unica evidenza che l'errore ha attraversato il RX fisico.
        self._inject_pending = None
        self._inject_active = None
        self.last_injection = None
        self.last_injection_sim = None
        self._disrupt_pending = False
        self._disrupt_started = None
        self.last_disruption_ms = None
        self.injected_total = 0
        self.postfec_bits = 0
        self.postfec_errors = 0
        self.errors_per_frame = []     # storia recente (cap 2000)
        # istogramma ACCUMULATO: conteggio dei frame per numero di symbol
        # errors (bin 0..40, l'ultimo è overflow ">40") — cresce nel tempo
        self.epf_hist = np.zeros(41, dtype=np.int64)
        self.ber_history = []          # BER cumulativa nel tempo (cap 600)
        # strip-chart di acquisizione: un punto per record (None = LINK DOWN,
        # così i pannelli mostrano il buco invece di interpolare)
        self.hist = {"ber": [], "errors": [], "snr_db": [], "q_min": [],
                     "f_ppm": [], "tau_rms_ui": [], "temp_c": []}
        self._rec_t = []               # timestamp degli ultimi record (rate)
        self.started_at = time.time()

    def _hist_push(self, r, row):
        h = self.hist
        h["temp_c"].append(float(r.cfg.pvt_temp_c) if r is not None else None)
        if r is None or not r.link_up:
            for k in h:
                if k != "temp_c":
                    h[k].append(None)
        else:
            h["ber"].append(row["bit_errors"] / max(row["bits"], 1))
            h["errors"].append(int(row["bit_errors"]))
            h["snr_db"].append(float(r.snr_dfe["snr_slicer_db"])
                               if r.snr_dfe else None)
            h["q_min"].append(float(r.snr_dfe["q_min"])
                              if r.snr_dfe else None)
            if r.cdr is not None and len(r.cdr.freq_trace_ppm) > 8:
                f = np.asarray(r.cdr.freq_trace_ppm, dtype=float)
                h["f_ppm"].append(float(np.mean(f[-len(f) // 4:])))
                tau = np.asarray(r.cdr.tau_trace_ui, dtype=float)
                x = np.arange(len(tau))
                fit = np.polyval(np.polyfit(x, tau, 1), x)
                h["tau_rms_ui"].append(float(np.std(tau - fit)))
            else:
                h["f_ppm"].append(None)
                h["tau_rms_ui"].append(None)
        for k in h:
            del h[k][:-400]
        self._rec_t.append(time.time())
        del self._rec_t[:-30]

    def reset_stats(self):
        with self._lock:
            self._reset_locked()

    def disrupt(self):
        """ONT service disruption test: il prossimo record perde il segnale
        (laser spento / canale interrotto); si misura il tempo di outage
        fino al ritorno del lock — come l'interruzione di fibra su un ONT."""
        with self._lock:
            self._disrupt_pending = True

    def inject_errors(self, n_bits: int, burst: bool = False,
                      target: str = "random"):
        """Accoda una transazione BERT one-shot e ne restituisce il ticket.

        Il PPG inverte i bit di linea DOPO l'encoder FEC. Un solo RX fisico
        (AFE/ADC/CDR/FSE/DFE) li riceve; il checker BERT misura il tap pre-FEC
        e, quando il decoder è attivo, il tap post-FEC. Non esiste un secondo
        ricevitore analogico nascosto nel modello.
        """
        n_bits = int(n_bits)
        if not 1 <= n_bits <= 200:
            raise ValueError("bits deve essere un intero fra 1 e 200")
        if target not in ("random", "msb", "lsb", "rs_symbol"):
            raise ValueError("target deve essere random/msb/lsb/rs_symbol")
        with self._lock:
            if not self._running:
                raise BertNotRunning("BERT non in RUN: nessun RX fisico acquisisce")
            if self._inject_pending is not None or self._inject_active is not None:
                raise InjectionInProgress("error injection già in corso")
            self._inject_seq += 1
            request = {
                "id": self._inject_seq,
                "bits": n_bits,
                "burst": bool(burst),
                "target": target,
                "queued_at": time.time(),
            }
            self._inject_pending = request
            return dict(request)

    def _finish_injection_locked(self, request, result):
        """Latch del percorso TX → RX fisico → FEC per la transazione."""
        actual = (int(len(result.err_positions))
                  if result.err_positions is not None else 0)
        report = {
            **request,
            "status": "measured" if result.link_up else "sync_loss",
            "record": int(self.records),
            "seed": int(result.seed),
            "tx_inserted": actual,
            "tx_positions_bits": (result.err_positions.astype(int).tolist()
                                  if result.err_positions is not None else []),
            "physical_rx_locked": bool(result.link_up),
            "cdr_locked": bool(result.cdr is not None and result.cdr.locked),
            "pattern_locked": bool(result.cdr is not None
                                   and result.cdr.pattern_locked),
            "pre_fec_bits": None,
            "pre_fec_errors": None,
            "pre_fec_ber": None,
            "fec_mode": result.cfg.fec_mode,
            "fec_input_errors": None,
            "fec_frames": None,
            "fec_frames_corrected": None,
            "fec_frames_uncorrectable": None,
            "fec_frames_miscorrected": None,
            "fec_symbols_corrected": None,
            "post_fec_bits": None,
            "post_fec_errors": None,
            "post_fec_ber": None,
        }
        if result.link_up:
            row = result.metrics_rows[2]
            report.update({
                "pre_fec_bits": int(row["bits"]),
                "pre_fec_errors": int(row["bit_errors"]),
                "pre_fec_ber": float(row["BER"]),
            })
            fl = result.fec_link
            if fl is not None:
                report.update({
                    "fec_input_errors": int(fl.pre_fec_bit_errors),
                    "fec_frames": int(fl.n_frames),
                    "fec_frames_corrected": int(fl.frames_corrected),
                    "fec_frames_uncorrectable": int(fl.frames_uncorrectable),
                    "fec_frames_miscorrected": int(fl.frames_miscorrected),
                    "fec_symbols_corrected": int(fl.symbols_corrected),
                    "post_fec_bits": int(fl.n_frames * 5140),
                    "post_fec_errors": int(fl.post_fec_bit_errors),
                    "post_fec_ber": float(fl.post_fec_ber),
                })
        self.injected_total += actual
        self.last_injection = report
        self.last_injection_sim = result
        self._inject_active = None
        return report

    @property
    def cfg(self) -> LinkConfig:
        with self._lock:
            return self._cfg

    def set_config(self, cfg: LinkConfig):
        with self._lock:
            if cfg != self._cfg:
                cancelled = self._inject_active or self._inject_pending
                self._cfg = cfg
                self._reset_locked()
                if cancelled is not None:
                    # Una modifica della chain invalida il record one-shot,
                    # ma la transazione deve chiudersi esplicitamente: senza
                    # questo ACK negativo la UI restava "in attesa del RX".
                    self.last_injection = {
                        **cancelled,
                        "status": "discarded_config_change",
                        "record": 0,
                        "seed": None,
                        "tx_inserted": 0,
                    }

    # -------------------------------------------------------------- lifecycle
    def start(self):
        with self._lock:
            if self._running:
                return
            self._gen += 1
            self._running = True
            self._stop_evt.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True,
                                            name="livebench",
                                            args=(self._gen,))
            self._thread.start()

    def stop(self):
        with self._lock:
            self._running = False
            # invalida il thread corrente: uno stop()+start() ravvicinati non
            # devono lasciare DUE thread che incrementano gli stessi contatori
            self._gen += 1
            t = self._thread
        self._stop_evt.set()
        # chi chiama stop() vuole la CPU libera (sweep/procedure): attendi la
        # fine del record in corso invece di proseguire in sovrapposizione
        if t is not None and t is not threading.current_thread():
            t.join(timeout=3.0)

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def _loop(self, gen):
        while True:
            with self._lock:
                if not self._running or gen != self._gen:
                    return
                cfg = self._cfg
                self._seed += 1
                seed = self._seed
                inject_request = self._inject_pending
                if inject_request is not None:
                    self._inject_pending = None
                    self._inject_active = inject_request
            run_cfg = (cfg if inject_request is None else cfg.with_updates(
                err_insert_bits=inject_request["bits"],
                err_insert_burst=inject_request["burst"],
                err_insert_target=inject_request["target"]))
            with self._lock:
                die_t = (self._chamber_step(time.time())
                         if self.chamber["on"] else None)
            if die_t is not None:
                run_cfg = run_cfg.with_updates(pvt_temp_c=round(die_t, 2))
            with self._lock:
                if self._disrupt_pending:
                    self._disrupt_pending = False
                    self._disrupt_started = time.time()
                    run_cfg = (run_cfg.with_updates(laser_dbm=-30.0)
                               if run_cfg.link_medium == "optical" else
                               run_cfg.with_updates(
                                   channel_il_nyquist_db=60.0))
            try:
                r = simulate(run_cfg, seed=seed, depth="light")
            except Exception:
                # config al limite: ferma l'acquisizione invece di girare a
                # vuoto — con traceback nel log e stato RUN aggiornato in UI
                log.exception("livebench: record fallito (seed %d), "
                              "acquisizione fermata", seed)
                with self._lock:
                    if inject_request is not None:
                        self.last_injection = {
                            **inject_request, "status": "simulation_error",
                            "record": self.records, "seed": seed,
                        }
                        self._inject_active = None
                    self._running = False
                    snap = self._snapshot_locked()
                if self.on_record:
                    try:
                        self.on_record(snap)
                    except Exception:
                        pass
                return
            with self._lock:
                if cfg != self._cfg or gen != self._gen:
                    if (inject_request is not None
                            and self._inject_active is not None
                            and self._inject_active["id"] == inject_request["id"]):
                        self.last_injection = {
                            **inject_request, "status": "discarded",
                            "record": self.records, "seed": seed,
                        }
                        self._inject_active = None
                    continue  # config cambiata / stop a metà record: scarta
                if (self.latest is not None and self.latest.link_up
                        and not r.link_up):
                    self.sync_losses += 1     # SYNC LOSS stile ED
                if self._disrupt_started is not None and r.link_up:
                    self.last_disruption_ms = round(
                        (time.time() - self._disrupt_started) * 1e3, 1)
                    self._disrupt_started = None
                self.latest = r
                self.records += 1
                if inject_request is not None:
                    self._finish_injection_locked(inject_request, r)
                if not r.link_up:
                    # niente lock CDR/pattern: il record non produce bit validi
                    self.link_down_records += 1
                    self._hist_push(r, None)
                    snap = self._snapshot_locked()
                    if self.on_record:
                        try:
                            self.on_record(snap)
                        except Exception:
                            pass
                    if self._stop_evt.wait(0.05):
                        self._stop_evt.clear()
                    continue
                row = r.metrics_rows[2]
                self.bits_total += row["bits"]
                self.bit_errors_total += row["bit_errors"]
                self.sym_total += row["symbols"]
                self.sym_errors_total += row["symbol_errors"]
                if r.fec_link is not None:
                    fl = r.fec_link
                    self.frames_total += fl.n_frames
                    self.frames_clean += fl.frames_clean
                    self.frames_corrected += fl.frames_corrected
                    self.frames_lost += fl.frames_uncorrectable
                    self.frames_miscorrected += fl.frames_miscorrected
                    self.symbols_corrected += fl.symbols_corrected
                    self.postfec_bits += fl.n_frames * 5140  # k*10 payload
                    self.postfec_errors += fl.post_fec_bit_errors
                    self.errors_per_frame.extend(int(v) for v in fl.errors_per_frame)
                    del self.errors_per_frame[:-2000]
                    np.add.at(self.epf_hist,
                              np.minimum(fl.errors_per_frame, 40), 1)
                elif r.fec is not None and r.fec.n_frames:
                    fa = r.fec
                    self.frames_total += fa.n_frames
                    self.frames_lost += fa.frames_uncorrectable
                    self.frames_clean += int(np.sum(fa.errors_per_frame == 0))
                    self.frames_corrected += int(np.sum(
                        (fa.errors_per_frame > 0) & (fa.errors_per_frame <= 15)))
                    self.errors_per_frame.extend(int(v) for v in fa.errors_per_frame)
                    del self.errors_per_frame[:-2000]
                    np.add.at(self.epf_hist,
                              np.minimum(fa.errors_per_frame, 40), 1)
                if r.l2 is not None:
                    self.l2_expected += r.l2.frames_expected
                    self.l2_detected += r.l2.frames_detected
                    self.l2_ok += r.l2.frames_ok
                    self.l2_fcs_bad += r.l2.frames_fcs_bad
                    self.l2_lost += r.l2.frames_lost
                    self.l2_thr_sum += r.l2.throughput_gbps
                    self.l2_records += 1
                    self.l2_dup += r.l2.frames_duplicated
                    self.l2_ooo += r.l2.frames_out_of_order
                    self.l2_lost_emu += r.l2.lost_emulated
                    self.l2_corrupt_emu += r.l2.corrupt_emulated
                if r.l1 is not None:
                    self.l1_records += 1
                    self.l1_locked += int(bool(r.l1.lock))
                    self.l1_header_errors += int(r.l1.sync_header_errors)
                    self.l1_blocks += int(r.l1.blocks)
                    self.l1_hi_ber += int(bool(r.l1.hi_ber))
                self.ber_history.append(self.ber_cum)
                del self.ber_history[:-600]
                self._hist_push(r, row)
                snap = self._snapshot_locked()
            if self.on_record:
                try:
                    self.on_record(snap)
                except Exception:
                    pass
            if self._stop_evt.wait(0.05):
                self._stop_evt.clear()

    # ------------------------------------------------------------- reporting
    @property
    def ber_cum(self) -> float:
        return self.bit_errors_total / self.bits_total if self.bits_total else float("nan")

    def _snapshot_locked(self):
        ber = self.ber_cum
        if self.bits_total and self.bit_errors_total:
            lo = float(sp_stats.beta.ppf(0.025, self.bit_errors_total,
                                         self.bits_total - self.bit_errors_total + 1))
            hi = float(sp_stats.beta.ppf(0.975, self.bit_errors_total + 1,
                                         self.bits_total - self.bit_errors_total))
        elif self.bits_total:
            lo, hi = 0.0, float(-np.expm1(np.log(0.05) / self.bits_total))
        else:
            lo = hi = float("nan")
        r = self.latest
        return {
            "records": self.records,
            "elapsed_s": time.time() - self.started_at,
            "bits_total": self.bits_total,
            "bit_errors_total": self.bit_errors_total,
            "ber_cum": ber,
            "ber_ci95": [lo, hi],
            "ser_cum": (self.sym_errors_total / self.sym_total
                        if self.sym_total else float("nan")),
            "ber_history": list(self.ber_history[-240:]),
            "hist": {k: list(v[-240:]) for k, v in self.hist.items()},
            "records_per_s": (
                (len(self._rec_t) - 1) / (self._rec_t[-1] - self._rec_t[0])
                if len(self._rec_t) >= 2
                and self._rec_t[-1] > self._rec_t[0] else None),
            "fec": {
                "in_path": bool(r is not None and r.fec_link is not None),
                "codec": (r.fec_codec_name if r is not None else ""),
                "frames_total": self.frames_total,
                "frames_clean": self.frames_clean,
                "frames_corrected": self.frames_corrected,
                "frames_lost": self.frames_lost,
                "frames_miscorrected": self.frames_miscorrected,
                "symbols_corrected": self.symbols_corrected,
                "postfec_ber": (self.postfec_errors / self.postfec_bits
                                if self.postfec_bits else float("nan")),
                "postfec_bits": self.postfec_bits,
                "flr": (self.frames_lost / self.frames_total
                        if self.frames_total else float("nan")),
                "epf_hist": self.epf_hist.tolist(),
                "errors_per_frame": self.errors_per_frame[-120:],
                "t": 15 if (r is None or "528" not in (r.fec_codec_name or ""))
                     else 7,
            },
            "link_down_records": self.link_down_records,
            "sync_losses": self.sync_losses,
            "chamber": {**self.chamber, "die_t": round(self._die_t, 2)},
            "last_disruption_ms": self.last_disruption_ms,
            "injected_total": self.injected_total,
            "injection": {
                "pending": (dict(self._inject_pending)
                            if self._inject_pending is not None else None),
                "active": (dict(self._inject_active)
                           if self._inject_active is not None else None),
                "last": (dict(self.last_injection)
                         if self.last_injection is not None else None),
            },
            "l1": {
                "coding": self._cfg.l2_pcs_coding,
                "records": self.l1_records,
                "locked_records": self.l1_locked,
                "sync_header_errors": self.l1_header_errors,
                "blocks": self.l1_blocks,
                "hi_ber_records": self.l1_hi_ber,
            },
            "l2": {
                "active": bool(self._cfg.pattern == "eth"),
                "frames_expected": self.l2_expected,
                "frames_detected": self.l2_detected,
                "frames_ok": self.l2_ok,
                "frames_fcs_bad": self.l2_fcs_bad,
                "frames_lost": self.l2_lost,
                "frames_duplicated": self.l2_dup,
                "frames_out_of_order": self.l2_ooo,
                "lost_emulated": self.l2_lost_emu,
                "corrupt_emulated": self.l2_corrupt_emu,
                "workload": self._cfg.l2_workload,
                "scheduler": self._cfg.l2_scheduler,
                "loss_pct": (100.0 * self.l2_lost / self.l2_expected
                             if self.l2_expected else float("nan")),
                "throughput_gbps": (self.l2_thr_sum / self.l2_records
                                    if self.l2_records else float("nan")),
                "frame_bytes": self._cfg.l2_frame_bytes,
            },
            "last": {
                "seed": (int(r.seed) if r is not None else None),
                "depth": (r.depth if r is not None else None),
                "link_up": bool(r is not None and r.link_up),
                "cdr_locked": bool(r is not None and (
                    r.cdr.locked if r.cdr is not None else r.link_up)),
                "ber": (r.ber_post_dfe if r is not None and r.link_up
                        else float("nan")),
                "gmi": (r.gmi_total if r is not None and r.link_up
                        else float("nan")),
                "snr_db": (r.snr_dfe["snr_slicer_db"]
                           if r is not None and r.link_up else float("nan")),
                "q_min": (r.snr_dfe["q_min"]
                          if r is not None and r.link_up else float("nan")),
                "ber_qmin_gaussian": (r.snr_dfe["ber_from_qmin_gaussian"]
                                       if r is not None and r.link_up
                                       else float("nan")),
                "ber_levels_gaussian": (r.snr_dfe["ber_gaussian_levels"]
                                         if r is not None and r.link_up
                                         else float("nan")),
                "checks_fail": (sum(1 for c in r.checks if c["status"] == "FAIL")
                                if r is not None else 0),
                "p_pd_dbm": (r.optical.power_budget_dbm["PD input"]
                             if r is not None and r.optical is not None
                             else float("nan")),
            },
            "running": self._running,
        }

    def snapshot(self):
        with self._lock:
            return self._snapshot_locked()

    def capture(self):
        """Snapshot atomico del reference plane live.

        Tutti i canali di uno scope devono puntare allo stesso SimResult e allo
        stesso record counter; leggere cfg/latest/records separatamente poteva
        associare una waveform vecchia alla configurazione nuova.
        """
        with self._lock:
            return self._cfg, self.latest, self.records, self._running

    def capture_bert(self):
        """Record latched dell'ultima transazione BERT, se presente.

        I pannelli generici seguono `latest`; il BERT deve invece conservare
        la misura one-shot finché l'utente non lancia una nuova iniezione o
        azzera/cambia configurazione.
        """
        with self._lock:
            sim = self.last_injection_sim or self.latest
            source = "injection" if self.last_injection_sim is not None else "live"
            report = (dict(self.last_injection)
                      if self.last_injection is not None else None)
            return self._cfg, sim, self.records, self._running, source, report
