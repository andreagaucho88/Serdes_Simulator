"""Costruzione dei dati JSON per i pannelli del Lab Pro.

Ogni funzione riceve un SimResult (di riferimento full-depth o l'ultimo del
LiveBench) e ritorna dict serializzabili. Le misure eye "da strumento" sono
calcolate con allineamento dichiarato: fase acquisita per i nodi RX, centro
nominale per i nodi TX.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
from scipy import signal as sp_signal

from serdes_sim import LinkConfig, simulate
from serdes_sim.blocks import fec as fec_block
from serdes_sim.blocks.metrics import eye_density
from serdes_sim.blocks.receiver import ctle_response, ctle_peaking_db
from serdes_sim.utils import butterworth_magnitude, db10, db20, w_to_dbm


def J(x):
    """Converte ricorsivamente numpy → tipi JSON."""
    if isinstance(x, dict):
        return {k: J(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [J(v) for v in x]
    if isinstance(x, np.ndarray):
        return [J(v) for v in x.tolist()]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        v = float(x)
        return v if np.isfinite(v) else None
    if isinstance(x, float) and not np.isfinite(x):
        return None
    return x


@lru_cache(maxsize=6)
def _ref_sim_cached(cfg_json: str):
    payload = json.loads(cfg_json)
    payload["tx_ffe_taps"] = tuple(payload["tx_ffe_taps"])
    return simulate(LinkConfig(**payload), seed=20240731, depth="full")


def ref_sim(cfg: LinkConfig):
    return _ref_sim_cached(json.dumps(cfg.to_dict()))


# ---------------------------------------------------------------------------
# Nodi osservabili
# ---------------------------------------------------------------------------

NODES = {
    "driver": ("Uscita driver", "electrical", "V", "tx"),
    "chan": ("Uscita canale", "electrical", "V", "rx"),
    "pmzm": ("P ottica MZM", "optical", "mW", "tx"),
    "pfiber": ("P ottica al PD", "optical", "mW", "rx"),
    "vtia": ("Uscita TIA", "electrical", "V", "rx"),
    "vctle": ("Uscita CTLE", "electrical", "V", "rx"),
}


def get_wave(sim, node):
    if node == "driver":
        return sim.tx.driver_voltage_v
    if node == "chan":
        return sim.channel.electrical_waveform_v
    if node == "pmzm":
        return sim.optical.P_mzm_w * 1e3
    if node == "pfiber":
        return sim.optical.P_fiber_w * 1e3
    if node == "vtia":
        return sim.receiver.v_tia_v
    return sim.receiver.v_ctle_v


def _node_delay_ui(sim, node):
    """Allineamento del centro simbolo per il nodo (dichiarato):
    nodi TX → centro nominale; nodi RX → ritardo stimato dal CDR (o
    dall'acquisition oracle in modalità oracle)."""
    if NODES[node][3] == "tx":
        return 0.0
    return sim.rx_delay_ui


# ---------------------------------------------------------------------------
# Eye + misure da strumento
# ---------------------------------------------------------------------------

def eye_panel(sim, cfg, node="vctle", n_traces=500):
    wave = np.asarray(get_wave(sim, node), dtype=float)
    meas = eye_measures(sim, cfg, node)
    if meas.get("inverted"):
        # funzione "invert" da scope: tracce e misure nello stesso dominio
        wave = -wave
    sps = cfg.analog_sps
    delay = _node_delay_ui(sim, node)
    shift = int(round(delay * sps))
    rows = []
    start = 80
    for k in range(start, min(len(wave) // sps - 3, start + n_traces)):
        c = k * sps + sps // 2 + shift
        if c - sps >= 0 and c + sps < len(wave):
            rows.append(wave[c - sps:c + sps])
    traces = np.asarray(rows)
    label, domain, unit, side = NODES[node]
    return J({
        "node": node, "label": label, "domain": domain, "unit": unit,
        "sps": sps, "traces": np.round(traces, 5),
        "align": ("ritardo CDR" if side == "rx" else "centro nominale TX")
                 + (" · INV" if meas.get("inverted") else ""),
        "meas": meas,
    })


def eye_measures(sim, cfg, node="vctle"):
    """Misure per occhio: livelli μ/σ, height 3σ, width alla soglia, Q, RLM.

    Proxy dichiarati: allineamento dal timing dell'acquisition, niente filtro
    di riferimento né procedure di clause (non è TDECQ)."""
    wave = np.asarray(get_wave(sim, node), dtype=float)
    sps = cfg.analog_sps
    spec = sim.spec
    levels = spec.levels_array
    delay = _node_delay_ui(sim, node)
    symbols = sim.pam4_symbols
    k = np.arange(200, cfg.n_symbols - 200)
    centers = ((k + 0.5 + delay) * sps).astype(int)
    valid = (centers > sps) & (centers < len(wave) - sps)
    k, centers = k[valid], centers[valid]
    y = wave[centers]
    truth = symbols[k]

    # POLARITÀ: la catena può invertire (MZM in quadratura, TIA...). Come su
    # uno scope reale, le misure si fanno sul segnale "raddrizzato": se la
    # pendenza truth→y è negativa, si inverte la forma d'onda per l'analisi.
    slope_pol = float(np.mean((truth - truth.mean()) * (y - y.mean())))
    inverted = slope_pol < 0
    if inverted:
        wave = -wave
        y = -y

    # AUTOCENTRAGGIO da strumento: il DCA sceglie da sé l'istante di misura
    # (massima apertura minima), indipendente dal CDR del ricevitore — il cui
    # istante è riportato a parte come marker.
    lo_lv0, hi_lv0 = levels[0], levels[-1]
    best_off, best_metric = 0.0, -np.inf
    for off in np.linspace(-0.35, 0.35, 15):
        cc = ((k + 0.5 + delay + off) * sps).astype(int)
        ok = (cc > sps) & (cc < len(wave) - sps)
        yy, tt = wave[cc[ok]], truth[ok]
        mins = []
        for a, b in zip(levels[:-1], levels[1:]):
            ya = yy[np.isclose(tt, a)]
            yb = yy[np.isclose(tt, b)]
            if len(ya) < 20 or len(yb) < 20:
                mins.append(-np.inf)
                continue
            mins.append(np.percentile(yb, 1) - np.percentile(ya, 99))
        metric = min(mins) if mins else -np.inf
        if metric > best_metric:
            best_metric, best_off = metric, float(off)
    centers = ((k + 0.5 + delay + best_off) * sps).astype(int)
    valid2 = (centers > sps) & (centers < len(wave) - sps)
    k, centers = k[valid2], centers[valid2]
    y = wave[centers]
    truth = truth[valid2]

    stats = []
    for lv in levels:
        x = y[np.isclose(truth, lv)]
        stats.append({"level": float(lv), "mean": float(np.mean(x)),
                      "sigma": float(np.std(x)), "n": int(len(x))})
    heights, widths, qs, thresholds = [], [], [], []
    for a, b in zip(stats[:-1], stats[1:]):
        # eye height al centro fra percentili p1/p99 dei due cluster: robusto
        # per distribuzioni ISI non gaussiane (il 3σ le sovrastima)
        ya = y[np.isclose(truth, a["level"])]
        yb = y[np.isclose(truth, b["level"])]
        heights.append(float(np.percentile(yb, 1) - np.percentile(ya, 99)))
        denom = a["sigma"] + b["sigma"]
        qs.append((b["mean"] - a["mean"]) / denom if denom > 0 else None)
        thr = ((a["mean"] * b["sigma"] + b["mean"] * a["sigma"]) / denom
               if denom > 0 else 0.5 * (a["mean"] + b["mean"]))
        thresholds.append(thr)
        # width: frazione di UI attorno al centro dove le classi restano separate
        lo_mask = np.isclose(truth, a["level"])
        hi_mask = np.isclose(truth, b["level"])
        open_phases = []
        for frac in np.linspace(-0.5, 0.5, 21):
            idx = centers + int(round(frac * sps))
            yl = wave[idx[lo_mask]]
            yh = wave[idx[hi_mask]]
            opening = np.percentile(yh, 1) - np.percentile(yl, 99)
            open_phases.append(opening > 0)
        widths.append(float(np.mean(open_phases)))  # frazione UI aperta (p1/p99)
    spacings = np.diff([s["mean"] for s in stats])
    rlm = float(spacings.min() / spacings.max()) if len(spacings) > 1 else None

    # rise/fall 20-80% sulle transizioni outer (min→max e max→min)
    lo_lv, hi_lv = levels[0], levels[-1]
    amp_lo, amp_hi = stats[0]["mean"], stats[-1]["mean"]
    v20 = amp_lo + 0.2 * (amp_hi - amp_lo)
    v80 = amp_lo + 0.8 * (amp_hi - amp_lo)

    def edge_time(rising):
        src, dst = (lo_lv, hi_lv) if rising else (hi_lv, lo_lv)
        picks = np.flatnonzero(np.isclose(truth[:-1], src)
                               & np.isclose(truth[1:], dst))[:200]
        times = []
        for j in picks:
            seg = wave[centers[j]:centers[j] + sps + 1]
            if len(seg) < sps:
                continue
            a, b = (v20, v80) if rising else (v80, v20)
            ia = np.flatnonzero((seg[:-1] < a) & (seg[1:] >= a)) if rising \
                else np.flatnonzero((seg[:-1] > a) & (seg[1:] <= a))
            ib = np.flatnonzero((seg[:-1] < b) & (seg[1:] >= b)) if rising \
                else np.flatnonzero((seg[:-1] > b) & (seg[1:] <= b))
            if len(ia) and len(ib) and ib[0] >= ia[0]:
                times.append((ib[0] - ia[0]) / sps)
        return float(np.mean(times)) if times else None

    ui_ps = 1e12 / cfg.symbol_rate_hz
    tr, tf = edge_time(True), edge_time(False)
    out = {"levels": stats, "eye_heights": heights,
           "eye_widths_ui": widths, "q_per_eye": qs,
           "thresholds": thresholds, "rlm_proxy": rlm,
           "t_rise_ps": tr * ui_ps if tr else None,
           "t_fall_ps": tf * ui_ps if tf else None,
           "inverted": bool(inverted),
           "center_offset_ui": best_off,   # istante scelto dallo strumento
           "cdr_offset_ui": 0.0}           # istante del CDR (riferimento eye)
    if node in ("pmzm", "pfiber"):
        ol = sim.optical_levels
        out["oma_outer_mw"] = 1e3 * ol["oma_outer_w"]
        out["er_db"] = ol["extinction_ratio_db"]
        out["p_avg_dbm"] = float(w_to_dbm(ol["p_avg_w"]))
    return out


# ---------------------------------------------------------------------------
# Altri pannelli
# ---------------------------------------------------------------------------

def jitter_panel(sim, cfg, node="vctle"):
    """TIE ai crossing della soglia media + istogramma + spettro + stime RJ/DJ."""
    from serdes_sim.blocks.jitter import tie_analysis
    wave = get_wave(sim, node)
    delay = _node_delay_ui(sim, node)
    t = tie_analysis(wave, cfg.analog_sps, cfg.symbol_rate_hz,
                     delay_ui=delay)
    h, edges = np.histogram(t.tie_ui, bins=90)
    ui_ps = 1e12 / cfg.symbol_rate_hz
    keep = t.spec_freq_mhz <= cfg.symbol_rate_hz / 2 / 1e6
    sub = max(1, len(t.tie_ui) // 2500)
    return J({
        "label": NODES[node][0],
        "edge_sym": t.edge_symbol[::sub], "tie_ui": t.tie_ui[::sub],
        "hist_x_ui": 0.5 * (edges[:-1] + edges[1:]), "hist": h,
        "spec_f_mhz": t.spec_freq_mhz[keep][1:],
        "spec_mag_mui": 1e3 * t.spec_mag_ui[keep][1:],
        "tie_rms_ps": t.tie_rms_ui * ui_ps,
        "tie_pp_ps": t.tie_pp_ui * ui_ps,
        "rj_est_ps": t.rj_rms_ui_est * ui_ps,
        "dj_est_ps": t.dj_pp_ui_est * ui_ps,
        "n_edges": t.n_edges,
        "injected": {
            "rj_fs": cfg.tx_rj_rms_fs,
            "pj_ui": cfg.tx_pj_amp_ui,
            "pj_mhz": cfg.tx_pj_freq_mhz,
            "dcd_pct": cfg.tx_dcd_pct,
            "adc_rj_fs": cfg.adc_jitter_rms_fs,
        },
        "ui_ps": ui_ps,
        "align": ("fase acquisita" if NODES[node][3] == "rx"
                  else "centro nominale TX"),
    })


def spectrum_panel(sim, cfg, node="vctle", nperseg=4096):
    wave = np.asarray(get_wave(sim, node), dtype=float)
    fs = cfg.fs_analog_hz
    nps = int(min(nperseg, len(wave) // 4))
    f, psd = sp_signal.welch(wave, fs=fs, window="hann", nperseg=nps,
                             noverlap=nps // 2, scaling="density")
    out = {"f_ghz": f / 1e9, "psd_db": db10(np.maximum(psd, 1e-30)),
           "rbw_mhz": 1.5 * fs / nps / 1e6, "unit": NODES[node][2] + "²/Hz",
           "nyquist_ghz": cfg.nyquist_hz / 1e9, "label": NODES[node][0]}
    if node == "vtia":
        rx = sim.receiver
        S = rx.S_shot_a2_hz + rx.S_tia_a2_hz + rx.S_rin_a2_hz
        model = S * cfg.tia_transimpedance_ohm ** 2 * \
            butterworth_magnitude(f, cfg.tia_bw_hz, 3) ** 2
        out["model_db"] = db10(np.maximum(model, 1e-30))
    return J(out)


def ctle_panel(sim, cfg):
    f = np.linspace(1e7, 80e9, 1200)
    H = ctle_response(f, cfg.ctle_zero_hz, cfg.ctle_pole_hz,
                      cfg.ctle_hf_pole_hz, cfg.ctle_dc_gain_db)
    phase = np.unwrap(np.angle(H))
    gd_ps = -np.gradient(phase, 2 * np.pi * f) * 1e12
    peaking, f_peak = ctle_peaking_db(cfg.ctle_zero_hz, cfg.ctle_pole_hz,
                                      cfg.ctle_hf_pole_hz, cfg.ctle_dc_gain_db)
    mask = (sim.receiver.f_fft_hz >= 1e7) & (sim.receiver.f_fft_hz <= 80e9)
    fch = sim.receiver.f_fft_hz[mask]
    Hch = sim.channel.H_electrical[mask]
    Hct = ctle_response(fch, cfg.ctle_zero_hz, cfg.ctle_pole_hz,
                        cfg.ctle_hf_pole_hz, cfg.ctle_dc_gain_db)
    order = np.argsort(fch)
    return J({
        "f_ghz": f / 1e9, "mag_db": db20(H), "phase_deg": np.degrees(phase),
        "gd_ps": gd_ps, "peaking_db": peaking, "f_peak_ghz": f_peak / 1e9,
        "noise_enh_db": sim.receiver.ctle_noise_enhancement_db,
        "fch_ghz": fch[order] / 1e9, "chan_db": db20(Hch[order]),
        "combo_db": db20((Hch * Hct)[order]),
        "zero_ghz": cfg.ctle_zero_hz / 1e9, "pole_ghz": cfg.ctle_pole_hz / 1e9,
        "hf_ghz": cfg.ctle_hf_pole_hz / 1e9, "dc_db": cfg.ctle_dc_gain_db,
        "nyquist_ghz": cfg.nyquist_hz / 1e9,
    })


def channel_panel(sim, cfg):
    mask = (sim.channel.f_fft_hz >= 0) & (sim.channel.f_fft_hz <= 1.4 * cfg.nyquist_hz)
    return J({
        "f_ghz": sim.channel.f_fft_hz[mask] / 1e9,
        "s21_db": db20(sim.channel.H_electrical[mask]),
        "pulse_t_ui": sim.channel.pulse_time_ui,
        "pulse": sim.channel.pulse_normalized,
        "cursor_ui": sim.channel.cursor_ui,
        "cursor_val": sim.channel.cursor_values,
        "source": sim.channel.source,
        "nyquist_ghz": cfg.nyquist_hz / 1e9,
    })


def optical_panel(sim, cfg):
    from serdes_sim.blocks.optical import imdd_small_signal_response
    o = sim.optical
    f = np.linspace(0, 1.5 * cfg.nyquist_hz, 800)
    return J({
        "v_static": o.v_static, "p_static": o.p_static,
        "drive_peak_v": float(np.max(np.abs(o.mzm_drive_v))),
        "vpi": cfg.vpi_v,
        "fade_f_ghz": f / 1e9,
        "fade_db": db20(np.maximum(np.abs(
            imdd_small_signal_response(cfg, f, alpha=0.0)), 1e-5)),
        "f_null_ghz": (o.f_null_hz / 1e9 if np.isfinite(o.f_null_hz) else None),
        "budget": o.power_budget_dbm,
        "nyquist_ghz": cfg.nyquist_hz / 1e9,
    })


def adc_panel(sim, cfg):
    tl = sim.tone_lab
    out = {
        "lanes": [{"gain_pct": 100 * g, "offset_mv": 1e3 * o, "skew_fs": 1e15 * s}
                  for g, o, s in zip(sim.adc.lane_gain, sim.adc.lane_offset_v,
                                     sim.adc.lane_skew_s)],
        "lsb_mv": sim.adc.adc_lsb_v * 1e3,
        "clip_pct": 100 * sim.adc.adc_clip_fraction,
    }
    if tl is not None:
        keep = slice(0, len(tl.freq_hz), 4)
        out.update({
            "tone_f_ghz": tl.freq_hz[keep] / 1e9,
            "tone_ideal_db": tl.spec_ideal_dbfs[keep],
            "tone_mm_db": tl.spec_mismatch_dbfs[keep],
            "sndr": [tl.sndr_ideal_db, tl.sndr_mismatch_db],
            "enob": [tl.enob_ideal, tl.enob_mismatch],
            "lines_ghz": tl.interleave_lines_hz / 1e9,
        })
    return J(out)


def timing_panel(sim, cfg):
    out = {"mode": cfg.cdr_mode, "link_up": bool(sim.link_up)}
    if sim.cdr is not None:
        c = sim.cdr
        sub = max(1, len(c.tau_trace_ui) // 1500)
        out.update({
            "cdr": {
                "locked": c.locked, "lock_symbol": c.lock_symbol,
                "cycle_slips": c.cycle_slips,
                "tau": c.tau_trace_ui[::sub],
                "fppm": c.freq_trace_ppm[::sub],
                "sub": sub,
                "pattern_lag": c.pattern_lag,
                "pattern_corr": c.pattern_corr,
                "pattern_locked": c.pattern_locked,
                "delay_ui": c.delay_ui_est,
                "detail": c.detail,
                "bw": cfg.cdr_bw, "damping": cfg.cdr_damping,
                "ppm_set": cfg.rx_ppm_offset,
            },
        })
    t = sim.timing
    if t is not None:
        out.update({
            "phase_ui": t.phase_grid_ui,
            "mse_db": db10(t.phase_mse / t.phase_mse.min()),
            "best_phase": t.best_phase_ui, "delay": t.rx_integer_delay_ui,
        })
        if t.gardner_scurve is not None:
            out.update({"gardner": t.gardner_scurve, "mm": t.mm_scurve})
    return J(out)


def eq_panel(sim, cfg):
    if not sim.link_up:
        return {"link_down": True}
    eq = sim.eq
    mse = np.convolve(eq.fse_learning_error ** 2, np.ones(120) / 120, "valid")
    out = {
        "fse_pos_ui": ((np.arange(len(eq.fse_taps_w)) - len(eq.fse_taps_w) // 2)
                       / cfg.adc_sps),
        "fse_taps": eq.fse_taps_w,
        "dfe_taps": eq.dfe_coeff,
        "mse": np.maximum(mse[::8], 1e-8),
        "ber_rows": [{k: (None if isinstance(v, float) and not np.isfinite(v)
                          else v) for k, v in row.items()}
                     for row in sim.metrics_rows],
    }
    if eq.dfe_tap_trace is not None:
        out["dd_trace"] = eq.dfe_tap_trace[::2]
        out["train_stop"] = cfg.training_stop
    return J(out)


def decisions_panel(sim, cfg):
    if not sim.link_up:
        return {"link_down": True}
    eq = sim.eq
    spec = sim.spec
    y = eq.dfe_output[eq.validation_fse]
    truth = eq.d_fse[eq.validation_fse]
    hists = []
    for lv in spec.levels_array:
        vals = y[np.isclose(truth, lv)]
        h, edges = np.histogram(vals, bins=70)
        hists.append({"level": float(lv), "h": h,
                      "x": 0.5 * (edges[:-1] + edges[1:])})
    out = {
        "confusion": sim.confusion,
        "levels": spec.levels_array,
        "hists": hists,
        "thr_mid": sim.thresholds_dfe[0], "thr_cal": sim.thresholds_dfe[1],
        "snr_db": sim.snr_dfe["snr_slicer_db"], "q_min": sim.snr_dfe["q_min"],
        "q_per_eye": sim.snr_dfe["q_per_eye"],
        "gmi": sim.gmi_total, "gmi_per_bit": sim.gmi_per_bit,
        "bps": spec.bits_per_symbol,
    }
    if sim.bathtub is not None:
        bt = sim.bathtub
        out["bathtub"] = {
            "phase": bt.phase_ui,
            "emp": np.maximum(bt.empirical_ber, bt.plot_floor),
            "model": np.maximum(bt.model_ber, 1e-18),
            "floor": bt.plot_floor,
        }
    return J(out)


def stimulus_panel(sim, cfg):
    return J({
        "symbols": sim.pam4_symbols[:64],
        "levels": sim.spec.levels_array,
        "occupancy": sim.occupancy,
        "transition": sim.transition_probability,
        "label": sim.spec.label,
        "prbs": cfg.prbs_order,
        "bps": sim.spec.bits_per_symbol,
    })


def standards_panel(sim, cfg):
    gbd = cfg.symbol_rate_hz / 1e9
    bps = sim.spec.bits_per_symbol
    fams = [
        (10.3125, "NRZ", "10G — 802.3ae/ap", "none"),
        (25.78125, "NRZ", "25G/lane — 802.3by/bj · CEI-28G", "kr4"),
        (26.5625, "PAM4", "50G/lane — 802.3bs/cd · CEI-56G", "kp4"),
        (53.125, "PAM4", "100G/lane — 802.3ck/cu/df · CEI-112G", "kp4"),
        (106.25, "PAM4", "200G/lane — P802.3dj (draft) · CEI-224G", "kp4"),
    ]
    cands = [(abs(f[0] - gbd) / f[0], f) for f in fams if f[1] == cfg.modulation]
    dev, fam = min(cands, key=lambda t: t[0]) if cands else (None, None)
    ber = sim.ber_post_dfe if sim.link_up else None
    out = {"gbd": gbd, "lane_gbs": gbd * bps, "modulation": sim.spec.label,
           "family": fam[2] if fam else None,
           "family_gbd": fam[0] if fam else None,
           "deviation_pct": 100 * dev if dev is not None else None,
           "ber": ber, "link_up": bool(sim.link_up),
           "families": [{"gbd": f[0], "mod": f[1], "name": f[2]}
                        for f in fams]}
    # il modello segue il FEC realmente attivo nella simulazione; quello di
    # famiglia è solo il default what-if quando non c'è FEC in-path
    if cfg.fec_mode != "none":
        kind, whatif = cfg.fec_mode, False
    elif fam and fam[3] != "none":
        kind, whatif = fam[3], True
    else:
        kind, whatif = None, True
    if kind is not None:
        p = dict(n=544, t=15) if kind == "kp4" else dict(n=528, t=7)
        thr = fec_block.prefec_ber_threshold(1e-13, m=10, **p)
        out.update({
            "fec_name": ("KP4 RS(544,514)" if kind == "kp4"
                         else "KR4 RS(528,514)") + (" — what-if" if whatif else " — in-path"),
            "threshold": thr,
            "ratio_db": (10 * np.log10(thr / max(ber, 1e-30))
                         if ber is not None else None),
            "below": (bool(ber <= thr) if ber is not None else None),
        })
    else:
        out.update({"fec_name": "nessun FEC obbligatorio", "threshold": None,
                    "ratio_db": None,
                    "below": (bool(ber <= 1e-12) if ber is not None else None)})
    return J(out)


def checks_panel(sim, cfg):
    return J({"checks": sim.checks, "ledger": sim.ledger})


PANEL_BUILDERS = {
    "eye": eye_panel,
    "jitter": jitter_panel,
    "spectrum": spectrum_panel,
    "ctle": ctle_panel,
    "channel": channel_panel,
    "optical": optical_panel,
    "adc": adc_panel,
    "timing": timing_panel,
    "eq": eq_panel,
    "decisions": decisions_panel,
    "stimulus": stimulus_panel,
    "standards": standards_panel,
    "checks": checks_panel,
}
