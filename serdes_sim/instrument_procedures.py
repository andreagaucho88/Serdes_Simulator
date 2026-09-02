"""Procedure in stile strumento reale (Xena2544, VIAVI SAMComplete Y.1564,
Anritsu MP1900A) eseguite sulla catena LabPro.

Le strutture dei risultati riproducono i campi dei report degli strumenti
(sezioni e nomi di colonna del report Valkyrie2544, KPI e passi del test
Y.1564 di SAMComplete, riquadro "Result PAM4" dell'ED MP1900A) così che un
export LabPro sia confrontabile riga per riga con un report vero.

DICHIARATO: la catena LabPro è una sola corsia seriale senza DUT di rete
(nessuna coda, nessun policer, nessun timestamp nel payload).  Le perdite
di frame vengono dagli errori di bit del PHY; la latenza è un budget per
blocco più il ritardo di gruppo analogico misurato; la variazione di
ritardo viene dalla traccia di fase del CDR.  Di conseguenza il throughput
RFC 2544 è "tutto o niente" (100 % oppure perdita indipendente dal rate),
il policing Y.1564 è NOT_APPLICABLE e l'availability dipende solo dal link.
Ogni riga dice da dove viene il numero.
"""

from __future__ import annotations

import time

import numpy as np

from .blocks import ethernet
from .blocks import fec as fec_block
from .config import LinkConfig
from .engine import check_cancel, simulate
from .standards import FAIL, NOT_APPLICABLE, NOT_ASSESSED, PASS, verdict

RFC2544_VERSION = "1.0.0"
Y1564_VERSION = "1.0.0"
BERT_RESULT_VERSION = "1.0.0"
MIN_IPG_BYTES = 12


# ---------------------------------------------------------------------------
# utilità comuni
# ---------------------------------------------------------------------------

def _wire_bytes(cfg: LinkConfig, frame_bytes: int) -> int:
    """Byte sul filo di un frame: preamble+SFD (8) + header + payload + FCS."""
    body = max(int(frame_bytes) - len(ethernet.HEADER) - 4, 8)
    return 8 + len(ethernet.HEADER) + body + 4


def _ipg_for_rate(cfg: LinkConfig, frame_bytes: int, rate_pct: float) -> int:
    """IPG che realizza l'offered rate richiesto.  Come sugli strumenti,
    100 % è il port rate con l'IPG minimo di 12 byte (frame back-to-back):
    rate = (wire + 12) / (wire + ipg)."""
    wire = _wire_bytes(cfg, frame_bytes)
    rate_pct = max(min(float(rate_pct), 100.0), 0.01)
    ipg = (wire + MIN_IPG_BYTES) * 100.0 / rate_pct - wire
    return int(max(MIN_IPG_BYTES, min(2000, round(ipg))))


def _l2_frame_bytes(cfg: LinkConfig, frame_bytes: int) -> int:
    """Byte del frame L2 (header … FCS, senza preamble/SFD): il livello a
    cui Y.1564/MEF definiscono CIR, EIR e IR."""
    return _wire_bytes(cfg, frame_bytes) - 8


def _ipg_for_l2_rate(cfg: LinkConfig, frame_bytes: int, l2_bps: float) -> int:
    """IPG che realizza un Information Rate L2 (bit di frame L2 al secondo)."""
    wire = _wire_bytes(cfg, frame_bytes)
    l2b = _l2_frame_bytes(cfg, frame_bytes) * 8
    per_frame_s = l2b / max(float(l2_bps), 1.0)
    slot_bytes = per_frame_s * _line_rate_bps(cfg) / 8
    return int(max(MIN_IPG_BYTES, min(2000, round(slot_bytes - wire))))


def _offered_pct(cfg: LinkConfig, frame_bytes: int, ipg: int) -> float:
    """Offered rate in percento del port rate (100 % = IPG minimo)."""
    wire = _wire_bytes(cfg, frame_bytes)
    return 100.0 * (wire + MIN_IPG_BYTES) / (wire + ipg)


def _line_rate_bps(cfg: LinkConfig) -> float:
    bps = 2 if cfg.modulation == "PAM4" else 1
    return cfg.symbol_rate_hz * bps


def latency_budget_ns(cfg: LinkConfig, frame_bytes: int) -> tuple[list[dict], float]:
    """Budget di latenza one-way per blocco (stessa formula dell'ONT)."""
    line_bps = _line_rate_bps(cfg)
    frame_bits = _wire_bytes(cfg, frame_bytes) * 8
    items = [("serializzazione frame", frame_bits / line_bps * 1e9,
              f"{frame_bits} bit a {line_bps / 1e9:.0f} Gb/s")]
    if cfg.fec_mode != "none":
        codec = fec_block.FEC_CODECS[cfg.fec_mode]
        fec_ns = 2 * codec.n * fec_block.GF_M / line_bps * 1e9
        items.append(("FEC store&forward (enc+dec)", fec_ns,
                      f"2 × {codec.n * fec_block.GF_M} bit RS({codec.n},{codec.k})"))
    if cfg.link_medium == "optical" and cfg.fiber_km > 0:
        items.append(("propagazione fibra", cfg.fiber_km * 4890.0,
                      f"{cfg.fiber_km:g} km × 4.89 µs/km (n_g≈1.468)"))
    ui_ns = 1.0 / cfg.symbol_rate_hz * 1e9
    items.append(("pipeline DSP (FSE+DFE)", (cfg.fse_taps / 2 + cfg.dfe_taps) * ui_ns,
                  f"{cfg.fse_taps} tap T/2 + {cfg.dfe_taps} tap DFE"))
    budget = [{"item": n, "ns": float(v), "detail": d} for n, v, d in items]
    return budget, float(sum(b["ns"] for b in budget))


def measured_analog_delay_ns(cfg: LinkConfig, sim) -> float:
    """Ritardo di gruppo end-to-end (drive TX → uscita CTLE) per correlazione."""
    x = np.asarray(sim.channel_input_v, dtype=float)
    yv = np.asarray(sim.receiver.v_ctle_v, dtype=float)
    n_x = min(len(x), len(yv), 60000)
    xd = x[:n_x] - x[:n_x].mean()
    yd = yv[:n_x] - yv[:n_x].mean()
    corr = np.correlate(yd, xd[: n_x // 2], mode="valid")
    return float(int(np.argmax(np.abs(corr))) / cfg.fs_analog_hz * 1e9)


def delay_variation_ns(cfg: LinkConfig, sim) -> dict:
    """Variazione di ritardo dei frame dalla traccia di fase del CDR
    (DICHIARATO: proxy della FDV, non timestamp nel payload)."""
    ui_ns = 1.0 / cfg.symbol_rate_hz * 1e9
    tau = None
    if getattr(sim, "cdr", None) is not None and getattr(sim.cdr, "tau_trace_ui", None) is not None:
        tau = np.asarray(sim.cdr.tau_trace_ui, dtype=float)
        if len(tau) > 400:
            tau = tau[len(tau) // 2:]          # coda dopo il transitorio di lock
    if tau is None or len(tau) < 8 or not np.all(np.isfinite(tau)):
        return {"avg_ns": 0.0, "max_ns": 0.0, "source": "no CDR trace (timing ideale)"}
    tau = tau - np.mean(tau)
    return {"avg_ns": float(np.std(tau) * ui_ns),
            "max_ns": float((np.max(tau) - np.min(tau)) * ui_ns),
            "source": "CDR phase trace (std / peak-to-peak)"}


def _frame_row(cfg: LinkConfig, sim, frame_bytes: int, ipg: int, rate_pct: float,
               acceptable_loss_pct: float) -> dict:
    """Riga di risultato con i campi del report Xena2544 (Detailed Test
    Results): Tx/Rx frame e rate L1/L2, perdita, BER stimato."""
    l2 = sim.l2
    line_bps = _line_rate_bps(cfg)
    window_s = (l2.window_s if l2 is not None and getattr(l2, "window_s", None) else
                cfg.n_symbols / cfg.symbol_rate_hz)
    tx = int(l2.frames_expected) if l2 else 0
    rx = int(l2.frames_ok) if l2 else 0
    lost = int(l2.frames_lost) if l2 else tx
    loss_pct = 100.0 * lost / max(tx, 1)
    wire = _wire_bytes(cfg, frame_bytes)
    # rate geometrico dello scheduler (la finestra del record è troppo corta
    # per contare i frame senza l'errore di bordo): fps = line rate / slot
    fps = line_bps / ((wire + ipg) * 8.0)
    l1_bps = fps * (wire + ipg) * 8           # con IPG: rate L1 (bit fisici)
    l2_bps = fps * wire * 8                   # frame sul filo, senza IPG
    ber_est = float(sim.ber_post_dfe) if sim.link_up else None
    state = PASS if (sim.link_up and loss_pct <= acceptable_loss_pct + 1e-12) else FAIL
    return {
        "Frame Size": int(frame_bytes), "Result State": state,
        "Tx Off.Rate (Percent)": round(rate_pct, 3),
        "Tx (Frames)": tx, "Tx Rate (L1) (Bit/s)": l1_bps, "Tx Rate (L2) (Bit/s)": l2_bps,
        "Tx Rate (Fps)": fps, "Rx (Frames)": rx,
        "Rx Rate (L1) (Bit/s)": l1_bps * (1.0 - loss_pct / 100.0),
        "Rx Rate (Fps)": fps * (1.0 - loss_pct / 100.0),
        "Loss (Frames)": lost, "Loss Rate (Percent)": loss_pct, "BER (est)": ber_est,
        "IPG (Bytes)": int(ipg), "Link": "UP" if sim.link_up else "DOWN",
        "window_s": window_s, "line_rate_bps": line_bps,
    }


# ---------------------------------------------------------------------------
# RFC 2544 in stile Xena2544 / Valkyrie2544
# ---------------------------------------------------------------------------

def rfc2544_report(cfg: LinkConfig, frame_sizes=(64, 128, 256, 512, 1024),
                   acceptable_loss_pct: float = 0.0, resolution_pct: float = 0.5,
                   initial_rate_pct: float = 100.0, minimum_rate_pct: float = 0.1,
                   loss_rates_pct=(100.0, 50.0), max_iterations: int = 5,
                   seed: int = 73201, profile: str | None = None,
                   cancel=None, progress=None) -> dict:
    """Le quattro prove RFC 2544 con la struttura del report Valkyrie2544.

    Throughput: ricerca binaria dell'offered rate (via IPG) fino alla
    risoluzione, con perdita accettabile; Latency/Jitter al rate di
    throughput (budget + ritardo analogico misurato; jitter dal CDR);
    Frame Loss ai rate elencati; Back-to-Back = burst massimo senza
    perdita nella finestra del record.  Tutto DICHIARATO: nessun DUT.
    """
    t0 = time.perf_counter()
    started = time.strftime("%Y-%m-%d, %H:%M")
    sizes = [int(v) for v in frame_sizes]
    n_steps = len(sizes) * (2 + len(loss_rates_pct))
    step = 0
    thr_rows, lat_rows, loss_rows, b2b_rows = [], [], [], []
    for size in sizes:
        if not 64 <= size <= 1024:
            raise ValueError("frame size fuori range [64, 1024] B")
        base = cfg.with_updates(pattern="eth", l2_frame_bytes=size, l2_workload="custom")
        # --- throughput: ricerca binaria -----------------------------------
        check_cancel(cancel)
        if progress is not None:
            progress(step, n_steps, f"throughput {size} B")
        step += 1
        trail = []
        lo, hi = float(minimum_rate_pct), float(initial_rate_pct)
        rate = hi
        best = None
        for it in range(int(max_iterations) + 1):
            ipg = _ipg_for_rate(base, size, rate)
            sim = simulate(base.with_updates(l2_ipg_bytes=ipg), seed=seed + size + it, depth="light")
            row = _frame_row(base, sim, size, ipg, _offered_pct(base, size, ipg), acceptable_loss_pct)
            trail.append({"iteration": it, "rate_pct": row["Tx Off.Rate (Percent)"],
                          "loss_pct": row["Loss Rate (Percent)"], "state": row["Result State"]})
            if row["Result State"] == PASS:
                best = row
                if it == 0 or (hi - lo) <= resolution_pct:
                    break
                lo = rate
            else:
                hi = rate
                if best is None and it == 0 and row["Loss Rate (Percent)"] > 0 and row["Link"] == "UP":
                    # perdita al 100 %: nella corsia senza code la perdita
                    # dipende dal BER, non dal rate → una sola verifica al
                    # rate minimo basta a dimostrarlo
                    pass
            if (hi - lo) <= resolution_pct:
                break
            rate = 0.5 * (lo + hi)
        if best is None:
            best = dict(trail and row or {})
            best["Result State"] = FAIL
        best["search_trail"] = trail
        best["rate_independent_loss"] = bool(
            len(trail) >= 2 and all(t["state"] == FAIL for t in trail)
            and max(t["loss_pct"] for t in trail) - min(t["loss_pct"] for t in trail) < 2.0)
        thr_rows.append(best)
        thr_rate = best["Tx Off.Rate (Percent)"]
        # --- latency & jitter al rate di throughput -------------------------
        check_cancel(cancel)
        if progress is not None:
            progress(step, n_steps, f"latency {size} B")
        step += 1
        ipg = _ipg_for_rate(base, size, thr_rate)
        sim = simulate(base.with_updates(l2_ipg_bytes=ipg), seed=seed + 7 * size, depth="light")
        budget, total_ns = latency_budget_ns(base, size)
        meas_ns = measured_analog_delay_ns(base, sim)
        dv = delay_variation_ns(base, sim)
        lat_avg = (total_ns + meas_ns) / 1e3
        lat_rows.append({
            "Frame Size": size, "Result State": PASS if sim.link_up else FAIL,
            "Tx Off.Rate (Percent)": round(_offered_pct(base, size, ipg), 3),
            "Tx (Frames)": int(sim.l2.frames_expected) if sim.l2 else 0,
            "Rx (Frames)": int(sim.l2.frames_ok) if sim.l2 else 0,
            "Avg Latency (micsec)": lat_avg,
            "Min Latency (micsec)": lat_avg - dv["avg_ns"] / 1e3,
            "Max Latency (micsec)": lat_avg + dv["max_ns"] / 2e3,
            "Avg Jitter (micsec)": dv["avg_ns"] / 1e3, "Min Jitter (micsec)": 0.0,
            "Max Jitter (micsec)": dv["max_ns"] / 1e3,
            "latency_budget": budget, "latency_budget_ns": total_ns,
            "latency_measured_analog_ns": meas_ns, "jitter_source": dv["source"],
            "Latency Mode": "Last-To-Last (budget + measured analog group delay)",
        })
        # --- frame loss ai rate elencati ------------------------------------
        for r_pct in loss_rates_pct:
            check_cancel(cancel)
            if progress is not None:
                progress(step, n_steps, f"frame loss {size} B @ {r_pct:g} %")
            step += 1
            ipg = _ipg_for_rate(base, size, r_pct)
            sim = simulate(base.with_updates(l2_ipg_bytes=ipg), seed=seed + 11 * size + int(r_pct), depth="light")
            row = _frame_row(base, sim, size, ipg, _offered_pct(base, size, ipg), acceptable_loss_pct)
            row["Rate (Percent)"] = float(r_pct)
            loss_rows.append(row)
        # --- back-to-back: burst massimo senza perdita nel record -----------
        full = next((r for r in loss_rows if r["Frame Size"] == size and r["Rate (Percent)"] == 100.0), None)
        if full is not None:
            burst = int(full["Rx (Frames)"]) if full["Loss (Frames)"] == 0 else 0
            b2b_rows.append({
                "Frame Size": size, "Result State": PASS if burst > 0 else FAIL,
                "Tx Burst (Frames)": burst, "Tx Burst (Bytes)": burst * _wire_bytes(base, size),
                "Max Offered Rate (Fps)": full["Tx Rate (Fps)"],
                "Max Offered Rate (Bit/s)": full["Tx Rate (L1) (Bit/s)"],
                "note": "burst limited to the record window (no DUT buffer)",
            })
    all_rows = thr_rows + lat_rows + loss_rows + b2b_rows
    n_fail = sum(1 for r in all_rows if r["Result State"] != PASS)
    overall = PASS if n_fail == 0 else FAIL
    line_bps = _line_rate_bps(cfg)
    return {
        "procedure": {"procedure_id": "labpro-rfc2544-xena2544-style", "version": RFC2544_VERSION,
                      "reference": "RFC 2544 / RFC 1242 · report structure after Valkyrie2544 v2.87 example"},
        "test_summary": {"Test company": "SerDes Optical Lab PRO", "Customer": "",
                         "Test Date and Time": started,
                         "Test Duration (h:m:s)": time.strftime("%H:%M:%S", time.gmtime(time.perf_counter() - t0)),
                         "Generated By": "LabPro instrument_procedures (numerical bench, one serial lane, no DUT)"},
        "test_setup": {"Topology": "Pair-to-Pair (one serial lane)", "Direction": "Unidirectional",
                       "Frame Size Type": "Custom Sizes", "Frame Sizes Used": sizes,
                       "Toggle Port Sync": "No", "Flow Creation Type": "Stream-based",
                       "Enable Multi-Stream": "No",
                       "Throughput Test": "Enabled", "Latency and Jitter Test": "Enabled",
                       "Frame Loss Rate Test": "Enabled", "Back-to-Back Test": "Enabled"},
        "port_configuration": {"Used Port Count": 1, "Port ID": "P-0-0-0",
                               "Interface Type": f"{cfg.link_medium} {cfg.modulation} lane"
                               + (f" · {profile}" if profile else ""),
                               "Port Speed": f"{line_bps / 1e9:.3f} G", "Port Rate": f"{line_bps / 1e9:.3f} G",
                               "Protocol Segment Profile": "1: Ethernet"},
        "throughput_setup": {"Time Duration": f"{cfg.n_symbols / cfg.symbol_rate_hz * 1e6:.3f} µs (record window)",
                             "Iterations": 1, "Initial Rate": f"{initial_rate_pct:.3f} %",
                             "Maximum Rate": "100.000 %", "Minimum Rate": f"{minimum_rate_pct:.3f} %",
                             "Resolution": f"{resolution_pct:.3f} %", "Use Pass Threshold": "No",
                             "Acceptable Loss": f"{acceptable_loss_pct:.4f} %",
                             "Rate Result Scope": "Common Result", "Use Fast Binary Search": "No"},
        "throughput": thr_rows, "latency_jitter": lat_rows, "frame_loss": loss_rows,
        "back_to_back": b2b_rows,
        "summary": {"Total tests executed": len(all_rows), "failed": n_fail,
                    "message": ("Success: All tests passed!" if overall == PASS
                                else f"{n_fail} test(s) failed")},
        "verdict": verdict(overall, basis="checkpoint",
                           evidence=f"{len(all_rows) - n_fail}/{len(all_rows)} rows PASS · acceptable loss {acceptable_loss_pct:g} %"),
        "declared": ("one serial lane, no packet DUT: losses come from PHY bit errors (rate-independent), "
                     "latency = block budget + measured analog group delay, jitter from the CDR phase "
                     "trace, back-to-back burst limited to the record window; not an RFC 2544 certification"),
        "elapsed_s": time.perf_counter() - t0,
    }


# ---------------------------------------------------------------------------
# ITU-T Y.1564 in stile VIAVI SAMComplete
# ---------------------------------------------------------------------------

def y1564_report(cfg: LinkConfig, services=None, cir_steps_pct=(25.0, 50.0, 75.0, 100.0),
                 eir_pct_of_cir: float = 25.0, policing_pct_of_cir: float = 25.0,
                 sla=None, seed: int = 73301, profile: str | None = None,
                 cancel=None, progress=None) -> dict:
    """Service Configuration Test + Service Performance Test (Y.1564) con i
    KPI e la terminologia MEF/SAMComplete: CIR, EIR, IR, FTD, FDV, FLR,
    Availability.  Ogni servizio è uno stream L2 del banco; il CIR di
    default divide l'80 % del line rate secondo i pesi degli stream.

    DICHIARATO: senza policer né code lo step di policing è
    NOT_APPLICABLE (l'IR segue l'offered load) e l'availability è 100 %
    finché il link è UP; FTD = budget + ritardo analogico, FDV dal CDR.
    """
    t0 = time.perf_counter()
    started = time.strftime("%Y-%m-%d, %H:%M")
    sla = dict(sla or {})
    sla.setdefault("FLR (%)", 0.1)
    sla.setdefault("FTD (µs)", 50.0)
    sla.setdefault("FDV (µs)", 1.0)
    sla.setdefault("Availability (%)", 99.999)
    line_mbps = _line_rate_bps(cfg) / 1e6
    n_streams = max(1, int(cfg.l2_streams))
    weights = tuple(cfg.l2_stream_weights)[:n_streams] or (1,)
    wsum = float(sum(weights)) or 1.0
    if not services:
        services = []
        for i in range(n_streams):
            size = ethernet.STREAM_SIZES[i] or cfg.l2_frame_bytes
            services.append({"name": f"Svc {i + 1}", "frame_bytes": int(size),
                             "cir_mbps": 0.8 * line_mbps * weights[i] / wsum,
                             "eir_mbps": 0.8 * line_mbps * weights[i] / wsum * eir_pct_of_cir / 100.0})
    n_steps = len(services) * (len(cir_steps_pct) + 2) + 1
    step = 0

    def run(size, l2_mbps, sd):
        ipg = _ipg_for_l2_rate(cfg, size, l2_mbps * 1e6)
        c = cfg.with_updates(pattern="eth", l2_frame_bytes=int(size), l2_ipg_bytes=ipg,
                             l2_streams=1, l2_workload="custom")
        sim = simulate(c, seed=sd, depth="light")
        l2 = sim.l2
        window_s = (l2.window_s if l2 is not None and getattr(l2, "window_s", None) else
                    cfg.n_symbols / cfg.symbol_rate_hz)
        flr = (100.0 * l2.frames_lost / max(l2.frames_expected, 1)) if l2 else 100.0
        # IR = Information Rate dei frame L2 con FCS buona (MEF): offered × (1 − FLR),
        # perché la finestra del record è troppo corta per contare i frame
        # senza l'errore di bordo (dichiarato)
        ir_mbps = (l2_mbps * (1.0 - flr / 100.0)) if (l2 and sim.link_up) else 0.0
        budget, total_ns = latency_budget_ns(c, size)
        ftd_us = (total_ns + measured_analog_delay_ns(c, sim)) / 1e3
        dv = delay_variation_ns(c, sim)
        return {"offered_pct": _offered_pct(c, size, ipg), "IR (Mbps)": ir_mbps,
                "FTD (µs)": ftd_us, "FDV (µs)": dv["avg_ns"] / 1e3, "FLR (%)": flr,
                "Tx (Frames)": int(l2.frames_expected) if l2 else 0,
                "Rx (Frames)": int(l2.frames_ok) if l2 else 0,
                "link_up": bool(sim.link_up), "window_s": window_s, "ipg": ipg}

    def kpi_pass(k, need_ir_mbps=None):
        ok = (k["link_up"] and k["FLR (%)"] <= sla["FLR (%)"] and k["FTD (µs)"] <= sla["FTD (µs)"]
              and k["FDV (µs)"] <= sla["FDV (µs)"])
        if need_ir_mbps is not None:
            ok = ok and k["IR (Mbps)"] >= 0.98 * need_ir_mbps
        return PASS if ok else FAIL

    config_rows = []
    for si, svc in enumerate(services):
        size = int(svc["frame_bytes"])
        cir, eir = float(svc["cir_mbps"]), float(svc.get("eir_mbps", 0.0))
        # IR massimo raggiungibile a L2 con IPG minimo (12 B) e preamble
        max_l2_mbps = line_mbps * _l2_frame_bytes(cfg, size) / (_wire_bytes(cfg, size) + MIN_IPG_BYTES)
        for pct in cir_steps_pct:
            check_cancel(cancel)
            if progress is not None:
                progress(step, n_steps, f"{svc['name']} CIR {pct:g} %")
            step += 1
            offered = min(cir * pct / 100.0, max_l2_mbps)
            k = run(size, offered, seed + 17 * si + int(pct))
            config_rows.append({"Service": svc["name"], "Step": f"CIR {pct:g} %",
                                "Frame Size": size, "CIR (Mbps)": cir, "EIR (Mbps)": eir,
                                "Offered (Mbps)": offered, **k,
                                "Result": kpi_pass(k, need_ir_mbps=offered)})
        # CIR + EIR: sul verde (CIR) valgono gli SLA, sul giallo solo IR ≥ CIR
        check_cancel(cancel)
        if progress is not None:
            progress(step, n_steps, f"{svc['name']} CIR+EIR")
        step += 1
        offered = min(cir + eir, max_l2_mbps)
        k = run(size, offered, seed + 17 * si + 101)
        config_rows.append({"Service": svc["name"], "Step": "CIR + EIR", "Frame Size": size,
                            "CIR (Mbps)": cir, "EIR (Mbps)": eir, "Offered (Mbps)": offered, **k,
                            "Result": PASS if (k["link_up"] and k["IR (Mbps)"] >= 0.98 * min(cir, max_l2_mbps)) else FAIL})
        # policing: senza policer l'IR segue l'offered → NOT_APPLICABLE dichiarato
        check_cancel(cancel)
        if progress is not None:
            progress(step, n_steps, f"{svc['name']} policing")
        step += 1
        offered = min(cir + eir + cir * policing_pct_of_cir / 100.0, max_l2_mbps)
        k = run(size, offered, seed + 17 * si + 202)
        config_rows.append({"Service": svc["name"], "Step": f"Traffic policing (CIR+EIR+{policing_pct_of_cir:g} %)",
                            "Frame Size": size, "CIR (Mbps)": cir, "EIR (Mbps)": eir,
                            "Offered (Mbps)": offered, **k,
                            "Result": NOT_APPLICABLE,
                            "note": "no policer in a serial lane: IR follows the offered load (declared)"})
    # --- service performance test: tutti i servizi al CIR insieme ---------
    check_cancel(cancel)
    if progress is not None:
        progress(step, n_steps, "service performance")
    total_cir = sum(float(s["cir_mbps"]) for s in services)
    sizes = [int(s["frame_bytes"]) for s in services]
    c = cfg.with_updates(pattern="eth", l2_streams=min(4, max(1, len(services))),
                         l2_frame_bytes=sizes[0], l2_workload="custom",
                         l2_ipg_bytes=_ipg_for_l2_rate(cfg, int(np.mean(sizes)), total_cir * 1e6))
    sim = simulate(c, seed=seed + 999, depth="light")
    perf_rows = []
    l2 = sim.l2
    per = {st.stream_id: st for st in (l2.per_stream if l2 else [])}
    for si, svc in enumerate(services):
        st = per.get(si)
        size = int(svc["frame_bytes"])
        flr = (100.0 * st.lost / max(st.expected, 1)) if st else 100.0
        ir = (float(svc["cir_mbps"]) * (1.0 - flr / 100.0)) if (st and sim.link_up) else 0.0
        budget, total_ns = latency_budget_ns(c, size)
        ftd = (total_ns + measured_analog_delay_ns(c, sim)) / 1e3
        dv = delay_variation_ns(c, sim)
        avail = 100.0 if (sim.link_up and flr <= sla["FLR (%)"]) else 0.0
        k = {"IR (Mbps)": ir, "FTD (µs)": ftd, "FDV (µs)": dv["avg_ns"] / 1e3, "FLR (%)": flr,
             "Availability (%)": avail, "link_up": bool(sim.link_up)}
        perf_rows.append({"Service": svc["name"], "Frame Size": size, "CIR (Mbps)": float(svc["cir_mbps"]),
                          "Tx (Frames)": int(st.expected) if st else 0, "Rx (Frames)": int(st.ok) if st else 0,
                          **k, "Result": PASS if (kpi_pass(k) == PASS and avail >= sla["Availability (%)"]) else FAIL})
    rows_eval = [r for r in config_rows if r["Result"] != NOT_APPLICABLE] + perf_rows
    n_fail = sum(1 for r in rows_eval if r["Result"] == FAIL)
    overall = PASS if n_fail == 0 and rows_eval else (FAIL if n_fail else NOT_ASSESSED)
    return {
        "procedure": {"procedure_id": "labpro-y1564-samcomplete-style", "version": Y1564_VERSION,
                      "reference": "ITU-T Y.1564 / MEF terminology · workflow after VIAVI SAMComplete"},
        "test_summary": {"Test Date and Time": started, "Tester": "SerDes Optical Lab PRO",
                         "Profile": profile or "custom",
                         "Test Duration (h:m:s)": time.strftime("%H:%M:%S", time.gmtime(time.perf_counter() - t0))},
        "sla": sla, "services": services,
        "service_configuration": config_rows, "service_performance": perf_rows,
        "summary": {"failed": n_fail, "evaluated": len(rows_eval),
                    "message": ("PASS: all services meet the SLA" if overall == PASS
                                else f"{n_fail} step(s) failed the SLA")},
        "verdict": verdict(overall, basis="checkpoint",
                           evidence=f"{len(rows_eval) - n_fail}/{len(rows_eval)} SLA rows PASS · policing NOT_APPLICABLE (no policer)"),
        "declared": ("services are L2 streams on one serial lane; CIR = 80 % of the line rate split by the "
                     "stream weights unless given; no policer, no queues, availability from link state; "
                     "FTD = block budget + measured analog delay, FDV from the CDR phase trace"),
        "elapsed_s": time.perf_counter() - t0,
    }


# ---------------------------------------------------------------------------
# Riquadro "Result PAM4" in stile Anritsu MP1900A (MU196040B)
# ---------------------------------------------------------------------------

_GRAY_BITS = {0: (0, 0), 1: (0, 1), 2: (1, 1), 3: (1, 0)}   # livello → (MSB, LSB)


def bert_pam4_result(sim, acc: dict | None = None, mapping: str = "gray") -> dict:
    """Errori PAM4 come li mostra l'ED MP1900A: ER/EC per MSB e LSB con
    Total / INS (0→1) / OMI (1→0), matrice dei 12 casi di errore di simbolo
    (Level i → Level j), Symbol ER, Clock Loss / Sync Loss e riepilogo FEC.

    La matrice viene dalla confusione livello trasmesso × livello deciso
    dell'ultimo record (post-DFE, finestra di validazione); i contatori
    cumulativi (bit, errori, sync loss, FEC) dall'accumulatore del banco.
    """
    conf = None if getattr(sim, "confusion", None) is None else np.asarray(sim.confusion, dtype=int)
    if conf is None or conf.shape != (4, 4):
        return {"available": False, "reason": "no PAM4 confusion matrix on this record (NRZ or link down)"}
    bits_map = _GRAY_BITS if mapping == "gray" else {i: (i >> 1, i & 1) for i in range(4)}
    lanes = {"MSB": {"Total": 0, "INS": 0, "OMI": 0}, "LSB": {"Total": 0, "INS": 0, "OMI": 0}}
    matrix = []
    sym_err = 0
    total = int(conf.sum())
    for tx in range(4):
        row = []
        for rx in range(4):
            n = int(conf[tx, rx])
            row.append(n)
            if tx == rx or n == 0:
                continue
            sym_err += n
            for lane, (bt, br) in zip(("MSB", "LSB"), zip(bits_map[tx], bits_map[rx])):
                if bt != br:
                    lanes[lane]["Total"] += n
                    lanes[lane]["INS" if (bt == 0 and br == 1) else "OMI"] += n
        matrix.append(row)
    for lane in lanes.values():
        for k in ("Total", "INS", "OMI"):
            lane[f"ER {k}"] = lane[k] / max(total, 1)
    acc = acc or {}
    out = {
        "available": True, "version": BERT_RESULT_VERSION,
        "style": "Anritsu MP1900A MU196040B 'Result PAM4' (labels), LabPro measurements",
        "mapping": mapping, "symbols_measured": total,
        "lanes": {lane: {"ER": v["ER Total"], "EC": v["Total"],
                         "INS": {"ER": v["ER INS"], "EC": v["INS"]},
                         "OMI": {"ER": v["ER OMI"], "EC": v["OMI"]}} for lane, v in lanes.items()},
        "symbol_error_matrix": {"levels": [0, 1, 2, 3], "counts": matrix,
                                "total_symbol_errors": sym_err,
                                "symbol_error_ratio": sym_err / max(total, 1)},
        "record": {"BER": (float(sim.ber_post_dfe) if sim.link_up else None),
                   "link_up": bool(sim.link_up)},
        "cumulative": {"Bit Count": acc.get("bits"), "Error Count": acc.get("errors"),
                       "Error Rate": acc.get("ber"), "Sync Loss": acc.get("sync_losses"),
                       "Clock Loss": acc.get("clock_losses"),
                       "FEC Symbol Error": acc.get("fec_symbol_errors"),
                       "Uncorr. Codeword Error": acc.get("fec_uncorrectable")},
        "declared": ("INS/OMI classify each bit error by direction (0→1 / 1→0) from the level confusion "
                     "matrix of the last record; the 12 PAM4 error cases follow Anritsu's table; "
                     "cumulative counters come from the live bench accumulator"),
    }
    return out
