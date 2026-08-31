"""LiveBench: acquisizione continua con accumulo statistico.

Un thread esegue simulazioni light back-to-back (nuovo seed a ogni record) e
accumula i contatori come un BERT/FEC-analyzer reale: bit totali, errori,
frame FEC clean/corretti/persi, istogramma errori-per-frame. I contatori si
riempiono nel tempo; un cambio di configurazione azzera l'accumulo (dichiarato)
e riparte.
"""

from __future__ import annotations

import threading
import time

import numpy as np
from scipy import stats as sp_stats

from .config import LinkConfig
from .engine import simulate


class LiveBench:
    def __init__(self, cfg: LinkConfig = None, seed0: int = 500_000):
        self._lock = threading.RLock()
        self._cfg = cfg or LinkConfig()
        self._seed0 = seed0
        self._seed = seed0
        self._running = False
        self._thread = None
        self._stop_evt = threading.Event()
        self.on_record = None          # callback(snapshot) dopo ogni record
        self.latest = None             # ultimo SimResult (per scope/spettro)
        self._reset_locked()

    # ------------------------------------------------------------------ state
    def _reset_locked(self):
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
        self.postfec_bits = 0
        self.postfec_errors = 0
        self.errors_per_frame = []     # storia recente (cap 2000)
        # istogramma ACCUMULATO: conteggio dei frame per numero di symbol
        # errors (bin 0..40, l'ultimo è overflow ">40") — cresce nel tempo
        self.epf_hist = np.zeros(41, dtype=np.int64)
        self.ber_history = []          # BER cumulativa nel tempo (cap 600)
        self.started_at = time.time()

    def reset_stats(self):
        with self._lock:
            self._reset_locked()

    @property
    def cfg(self) -> LinkConfig:
        with self._lock:
            return self._cfg

    def set_config(self, cfg: LinkConfig):
        with self._lock:
            if cfg != self._cfg:
                self._cfg = cfg
                self._reset_locked()

    # -------------------------------------------------------------- lifecycle
    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_evt.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True,
                                            name="livebench")
            self._thread.start()

    def stop(self):
        with self._lock:
            self._running = False
        self._stop_evt.set()

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def _loop(self):
        while True:
            with self._lock:
                if not self._running:
                    return
                cfg = self._cfg
                self._seed += 1
                seed = self._seed
            try:
                r = simulate(cfg, seed=seed, depth="light")
            except Exception:
                # config al limite: ferma l'acquisizione invece di girare a vuoto
                with self._lock:
                    self._running = False
                return
            with self._lock:
                if cfg != self._cfg:
                    continue  # config cambiata a metà record: scarta
                self.latest = r
                self.records += 1
                if not r.link_up:
                    # niente lock CDR/pattern: il record non produce bit validi
                    self.link_down_records += 1
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
                self.ber_history.append(self.ber_cum)
                del self.ber_history[:-600]
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
            "last": {
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
                "checks_fail": (sum(1 for c in r.checks if c["status"] == "FAIL")
                                if r is not None else 0),
                "p_pd_dbm": (r.optical.power_budget_dbm["PD input"]
                             if r is not None else float("nan")),
            },
            "running": self._running,
        }

    def snapshot(self):
        with self._lock:
            return self._snapshot_locked()
