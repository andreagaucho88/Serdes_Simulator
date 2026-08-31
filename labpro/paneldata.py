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
from serdes_sim.blocks import stimulus
from serdes_sim.blocks.metrics import eye_density
from serdes_sim.blocks.receiver import ctle_response, ctle_peaking_db
from serdes_sim.utils import (apply_frequency_response, butterworth_magnitude,
                              butterworth_response, db10, db20, rms_ac,
                              w_to_dbm)
from labpro.education import TOPICS


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
    "driver": ("Uscita driver (diff. ideale)", "electrical", "V", "tx"),
    "vp": ("V_p (ramo positivo)", "electrical", "V", "tx"),
    "vn": ("V_n (ramo negativo)", "electrical", "V", "tx"),
    "vdiff": ("V_diff = Vp−Vn", "electrical", "V", "tx"),
    "vcm": ("V_cm (common-mode)", "electrical", "V", "tx"),
    "drive": ("Ingresso canale selezionato", "electrical", "V", "tx"),
    "chan": ("Uscita canale", "electrical", "V", "rx"),
    "pmzm": ("P ottica MZM", "optical", "mW", "tx"),
    "pfiber": ("P ottica al PD", "optical", "mW", "rx"),
    "vtia": ("Uscita TIA/AFE", "electrical", "V", "rx"),
    "vagc": ("Uscita AGC", "electrical", "V", "rx"),
    "vctle": ("Uscita CTLE", "electrical", "V", "rx"),
}


def get_wave(sim, node):
    if node == "driver":
        return sim.tx.driver_voltage_v
    if node == "vp":
        return sim.tx.vp_v
    if node == "vn":
        return sim.tx.vn_v
    if node == "vdiff":
        return sim.tx.v_diff_v
    if node == "vcm":
        return sim.tx.vcm_v
    if node == "drive":
        return sim.channel_input_v
    if node == "chan":
        return sim.channel.electrical_waveform_v
    if node in ("pmzm", "pfiber"):
        if sim.optical is None:
            raise ValueError("nodo ottico non disponibile in modalità copper")
        return (sim.optical.P_mzm_w if node == "pmzm"
                else sim.optical.P_fiber_w) * 1e3
    if node == "vtia":
        return sim.receiver.v_tia_v
    if node == "vagc":
        return sim.receiver.v_agc_v
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
    spacing_den = float(np.max(spacings)) if len(spacings) else 0.0
    rlm = (float(np.min(spacings) / spacing_den)
           if len(spacings) > 1 and abs(spacing_den) > 1e-15 else None)

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

    # EH estrapolata a BER target (Q-scale come su un DCA in eye mode):
    # EH@BER = (μ_b − Q·σ_b) − (μ_a + Q·σ_a) con Q = Φ⁻¹(1−BER).
    # DICHIARATO: estrapolazione con code gaussiane dei cluster misurati —
    # l'ISI multimodale reale può chiudere l'occhio prima.
    from scipy.stats import norm as sp_norm
    eh_at_ber = {}
    for blabel, btarget in (("2.4e-4", 2.4e-4), ("1e-6", 1e-6)):
        qv = float(sp_norm.isf(btarget))
        eh_at_ber[blabel] = [
            float((b["mean"] - qv * b["sigma"]) - (a["mean"] + qv * a["sigma"]))
            for a, b in zip(stats[:-1], stats[1:])]
    out = {"levels": stats, "eye_heights": heights,
           "eh_at_ber": eh_at_ber,
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

def _tie_tail_fit(tie_ui, ui_ps):
    """Tail-fit Q-scale dual-Dirac (come il jitter mode di un DCA):
    CDF empirica del TIE → asse Q gaussiano → fit lineare delle due code.
    Pendenza = σ (RJ), intercette = posizione delle due Dirac (DJ δδ).
    TJ@BER = DJ(δδ) + 2·Q(BER)·RJ. DICHIARATO: servono code campionate
    (≥400 edge) e il fit assume code gaussiane oltre l'ultimo percentile."""
    from scipy.stats import norm as sp_norm
    x = np.sort(np.asarray(tie_ui, dtype=float))
    n = len(x)
    if n < 400:
        return None
    pcs = (np.arange(n) + 0.5) / n
    qgrid = sp_norm.ppf(pcs)
    lo = (pcs > 2.0 / n) & (pcs < 0.08)
    hi = (pcs > 0.92) & (pcs < 1 - 2.0 / n)
    if lo.sum() < 12 or hi.sum() < 12:
        return None
    sig_l, mu_l = np.polyfit(qgrid[lo], x[lo], 1)
    sig_r, mu_r = np.polyfit(qgrid[hi], x[hi], 1)
    rj = 0.5 * (abs(float(sig_l)) + abs(float(sig_r)))
    dj = max(float(mu_r) - float(mu_l), 0.0)
    q12 = float(sp_norm.isf(1e-12))
    q4 = float(sp_norm.isf(2.4e-4))
    return {
        "rj_ps": rj * ui_ps, "dj_dd_ps": dj * ui_ps,
        "sigma_left_ps": abs(float(sig_l)) * ui_ps,
        "sigma_right_ps": abs(float(sig_r)) * ui_ps,
        "tj_1e12_ps": (dj + 2 * q12 * rj) * ui_ps,
        "tj_2p4e4_ps": (dj + 2 * q4 * rj) * ui_ps,
        "ew_2p4e4_ui": 1.0 - (dj + 2 * q4 * rj),
    }


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
    sub = max(1, int(np.ceil(len(t.tie_ui) / 600)))
    sf = t.spec_freq_mhz[keep][1:]
    sm = t.spec_mag_ui[keep][1:]
    # JSON live compatto senza perdere le righe strette di PJ: per ogni bin
    # si conserva il massimo, non un semplice downsample che potrebbe saltare
    # proprio il tono iniettato.
    if len(sf) > 900:
        groups = np.array_split(np.arange(len(sf)), 900)
        pick = np.array([g[np.argmax(sm[g])] for g in groups])
        sf, sm = sf[pick], sm[pick]
    return J({
        "label": NODES[node][0],
        "edge_sym": t.edge_symbol[::sub], "tie_ui": t.tie_ui[::sub],
        "hist_x_ui": 0.5 * (edges[:-1] + edges[1:]), "hist": h,
        "spec_f_mhz": sf,
        "spec_mag_mui": 1e3 * sm,
        "bathtub_x_ui": t.bathtub_offset_ui,
        "bathtub_ber_proxy": t.bathtub_ber_proxy,
        "bathtub_floor": 0.5 / max(t.n_edges, 1),
        "tie_rms_ps": t.tie_rms_ui * ui_ps,
        "tie_pp_ps": t.tie_pp_ui * ui_ps,
        "rj_est_ps": t.rj_rms_ui_est * ui_ps,
        "dj_est_ps": t.dj_pp_ui_est * ui_ps,
        "tail_fit": _tie_tail_fit(t.tie_ui, ui_ps),
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
    zeros = cfg.ctle_zeros_effective_hz
    poles = cfg.ctle_poles_effective_hz
    H = ctle_response(f, dc_gain_db=cfg.ctle_dc_gain_db,
                      zeros_hz=zeros, poles_hz=poles)
    phase = np.unwrap(np.angle(H))
    gd_ps = -np.gradient(phase, 2 * np.pi * f) * 1e12
    peaking, f_peak = ctle_peaking_db(
        dc_gain_db=cfg.ctle_dc_gain_db, zeros_hz=zeros, poles_hz=poles)
    mask = (sim.receiver.f_fft_hz >= 1e7) & (sim.receiver.f_fft_hz <= 80e9)
    fch = sim.receiver.f_fft_hz[mask]
    Hch = sim.channel.H_electrical[mask]
    Hct = ctle_response(fch, dc_gain_db=cfg.ctle_dc_gain_db,
                        zeros_hz=zeros, poles_hz=poles)
    order = np.argsort(fch)
    return J({
        "f_ghz": f / 1e9, "mag_db": db20(H), "phase_deg": np.degrees(phase),
        "gd_ps": gd_ps, "peaking_db": peaking, "f_peak_ghz": f_peak / 1e9,
        "noise_enh_db": sim.receiver.ctle_noise_enhancement_db,
        "fch_ghz": fch[order] / 1e9, "chan_db": db20(Hch[order]),
        "combo_db": db20((Hch * Hct)[order]),
        "zeros_ghz": np.asarray(zeros) / 1e9,
        "poles_ghz": np.asarray(poles) / 1e9,
        "topology": f"{len(zeros)}Z/{len(poles)}P",
        "dc_db": cfg.ctle_dc_gain_db,
        "nyquist_ghz": cfg.nyquist_hz / 1e9,
    })


def channel_panel(sim, cfg):
    mask = (sim.channel.f_fft_hz >= 0) & (sim.channel.f_fft_hz <= 1.4 * cfg.nyquist_hz)
    # Pulse response isolata dello stesso Hchannel*Hctle del main path. Non
    # include AGC/clip (non lineari): i cursor dichiarano quindi il piano.
    from serdes_sim.blocks.channel import channel_response
    n_ui = 192
    pulse_in = np.zeros(n_ui * cfg.analog_sps)
    k0 = n_ui // 3
    pulse_in[k0 * cfg.analog_sps:(k0 + 1) * cfg.analog_sps] = 1.0
    pulse_combo, _, _ = apply_frequency_response(
        pulse_in, cfg.fs_analog_hz,
        lambda f: channel_response(f, cfg) * ctle_response(
            f, dc_gain_db=cfg.ctle_dc_gain_db,
            zeros_hz=cfg.ctle_zeros_effective_hz,
            poles_hz=cfg.ctle_poles_effective_hz))
    main = int(np.argmax(np.abs(pulse_combo)))
    span = 8 * cfg.analog_sps
    main = int(np.clip(main, span, len(pulse_combo) - span - 1))
    pulse_combo_crop = pulse_combo[main - span:main + span]
    pulse_combo_crop /= max(float(np.max(np.abs(pulse_combo_crop))), 1e-30)
    cursor_ui = np.arange(-6, 9)
    cursor_combo = np.array([pulse_combo[main + k * cfg.analog_sps]
                             for k in cursor_ui])
    cursor_combo /= max(abs(float(cursor_combo[cursor_ui == 0][0])), 1e-30)
    isi_rms = float(np.sqrt(np.sum(cursor_combo[cursor_ui != 0] ** 2)))
    return J({
        "f_ghz": sim.channel.f_fft_hz[mask] / 1e9,
        "s21_db": db20(sim.channel.H_electrical[mask]),
        "pulse_t_ui": sim.channel.pulse_time_ui,
        "pulse": sim.channel.pulse_normalized,
        "pulse_combo": pulse_combo_crop,
        "cursor_ui": sim.channel.cursor_ui,
        "cursor_val": sim.channel.cursor_values,
        "cursor_combo": cursor_combo,
        "isi_rms_combo": isi_rms,
        "pulse_plane": "channel × CTLE (linear, before AGC/clip/ADC)",
        "source": sim.channel.source,
        "nyquist_ghz": cfg.nyquist_hz / 1e9,
    })


def _wave_window(wave, cfg, start_ui=80, span_ui=32, max_points=1200):
    """Finestra compatta ma temporalmente coerente per i pannelli RX."""
    a = int(start_ui * cfg.analog_sps)
    b = min(len(wave), a + int(span_ui * cfg.analog_sps))
    x = np.asarray(wave[a:b], dtype=float)
    sub = max(1, int(np.ceil(len(x) / max_points)))
    return (np.arange(a, b, sub) / cfg.analog_sps, x[::sub])


def pd_panel(sim, cfg):
    if sim.optical is None:
        return {"inactive": True,
                "reason": "link_medium=copper: PD bypassato, usa il pannello TIA/AFE"}
    rx = sim.receiver
    t_ui, clean = _wave_window(rx.i_pd_signal_a * 1e3, cfg)
    _, noisy = _wave_window(rx.i_pd_noisy_a * 1e3, cfg)
    return J({
        "t_ui": t_ui, "clean_ma": clean, "noisy_ma": noisy,
        "responsivity_a_w": cfg.pd_responsivity_a_w,
        "bandwidth_ghz": cfg.pd_bw_hz / 1e9,
        "mean_ma": 1e3 * float(np.mean(rx.i_pd_signal_a)),
        "rms_ac_ma": 1e3 * rms_ac(rx.i_pd_signal_a),
        "saturation_ma": 1e3 * cfg.pd_saturation_a,
        "sat_pct": 100 * rx.pd_sat_fraction,
        "noise_psd": {"shot": rx.S_shot_a2_hz,
                      "RIN": rx.S_rin_a2_hz,
                      "TIA input": rx.S_tia_a2_hz},
        "input_dbm": sim.optical.power_budget_dbm["PD input"],
    })


def tia_panel(sim, cfg):
    rx = sim.receiver
    t_ui, out = _wave_window(rx.v_tia_v, cfg)
    f = np.linspace(0, min(cfg.fs_analog_hz / 2, 1.5 * cfg.nyquist_hz), 600)
    mag = butterworth_magnitude(f, cfg.tia_bw_hz, order=3)
    return J({
        "medium": cfg.link_medium,
        "t_ui": t_ui, "vout": out,
        "transimpedance_ohm": (cfg.tia_transimpedance_ohm
                                if cfg.link_medium == "optical" else None),
        "bandwidth_ghz": cfg.tia_bw_hz / 1e9,
        "enbw_ghz": rx.tia_enbw_hz / 1e9,
        "clip_v": cfg.tia_clip_v,
        "clip_pct": 100 * rx.tia_clip_fraction,
        "out_rms_v": rms_ac(rx.v_tia_v),
        "noise_rms": rx.noise_rms_after_tia_a,
        "f_ghz": f / 1e9, "response_db": db20(np.maximum(mag, 1e-12)),
    })


def agc_panel(sim, cfg):
    rx = sim.receiver
    t_ui, vin = _wave_window(rx.v_tia_v - np.mean(rx.v_tia_v), cfg)
    _, vout = _wave_window(rx.v_agc_v, cfg)
    return J({
        "t_ui": t_ui, "vin": vin, "vout": vout,
        "gain": rx.agc_gain, "gain_db": db20(max(rx.agc_gain, 1e-30)),
        "input_rms_v": rms_ac(rx.v_tia_v),
        "target_rms_v": cfg.agc_target_rms_v,
        "output_rms_v": rms_ac(rx.v_agc_v),
        "headroom_to_adc_v": cfg.adc_full_scale_vpp / 2 - np.max(np.abs(rx.v_agc_v)),
    })


def optical_panel(sim, cfg):
    if sim.optical is None:
        return {"inactive": True,
                "reason": "link_medium=copper: la catena ottica è bypassata"}
    from serdes_sim.blocks.optical import imdd_small_signal_response
    o = sim.optical
    f = np.linspace(0, 1.5 * cfg.nyquist_hz, 800)
    return J({
        "modulator": o.modulator,
        "laser_type": cfg.laser_type,
        "fiber_type": cfg.fiber_type,
        "v_static": o.v_static, "p_static": o.p_static,
        "drive_peak_v": float(np.max(np.abs(o.mzm_drive_v))),
        "vpi": cfg.vpi_v if o.modulator == "mzm" else None,
        "er_set_db": (cfg.eml_er_db if o.modulator == "eml" else
                      cfg.direct_laser_er_db if o.modulator in ("dml", "vcsel")
                      else None),
        "fade_f_ghz": f / 1e9,
        "fade_db": db20(np.maximum(np.abs(
            imdd_small_signal_response(cfg, f, alpha=0.0)), 1e-5)),
        "f_null_ghz": (o.f_null_hz / 1e9 if np.isfinite(o.f_null_hz) else None),
        "budget": o.power_budget_dbm,
        "beta2_s2_m": o.beta2_s2_m,
        "beta3_s3_m": o.beta3_s3_m,
        "pmd_dgd_ps": o.pmd_dgd_ps,
        "modal_bw_ghz": (o.modal_bw_hz / 1e9
                         if np.isfinite(o.modal_bw_hz) else None),
        "nonlinear_phase_peak_rad": o.nonlinear_phase_peak_rad,
        "laser_linewidth_mhz": cfg.laser_linewidth_mhz,
        "nyquist_ghz": cfg.nyquist_hz / 1e9,
        # --- vista "seria": dove lavora il modulatore, budget, livelli ottici
        "drive_hist": _drive_histogram(o),
        "budget_steps": _budget_steps(o.power_budget_dbm),
        "chirp_t_ps": (np.arange(10 * cfg.analog_sps) / cfg.fs_analog_hz * 1e12),
        "chirp_ghz": o.inst_freq_shift_hz[:10 * cfg.analog_sps] / 1e9,
        "p_levels": _optical_levels_dbm(sim, cfg),
    })


def _drive_histogram(o):
    """Istogramma del drive effettivo, nel dominio della transfer statica:
    mostra DOVE il modulatore viene esercitato (compressione ai bordi)."""
    drive = np.asarray(o.mzm_drive_v)
    lo, hi = float(np.min(o.v_static)), float(np.max(o.v_static))
    h, edges = np.histogram(np.clip(drive, lo, hi), bins=70, range=(lo, hi))
    return {"x": 0.5 * (edges[:-1] + edges[1:]),
            "h": h / max(h.max(), 1)}


def _budget_steps(budget):
    """Waterfall del link budget: piani + perdita di ciascun segmento."""
    names = list(budget.keys())
    vals = [budget[k] for k in names]
    steps = []
    for i, (name, val) in enumerate(zip(names, vals)):
        steps.append({"plane": name, "dbm": float(val),
                      "delta_db": (float(val - vals[i - 1]) if i else 0.0)})
    return steps


def _optical_levels_dbm(sim, cfg):
    """Potenze ottiche per livello al PD (P0..P3 per PAM4): la grandezza con
    cui le spec ottiche definiscono OMA/ER/RLM."""
    try:
        m = eye_measures(sim, cfg, node="pfiber")
    except Exception:
        return None
    levels_mw = [st["mean"] for st in m["levels"]]
    if any(v <= 0 for v in levels_mw):
        return None
    dbm = [10 * np.log10(v) for v in levels_mw]   # mW → dBm
    oma_outer = levels_mw[-1] - levels_mw[0]
    inner = (levels_mw[2] - levels_mw[1]) if len(levels_mw) == 4 else None
    return {
        "p_dbm": dbm, "p_mw": levels_mw,
        "oma_outer_mw": oma_outer,
        "oma_inner_mw": inner,
        "er_db": 10 * np.log10(levels_mw[-1] / levels_mw[0]),
        "rlm_proxy": m["rlm_proxy"],
    }


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


def _error_analysis(err_sym):
    """Analisi errori stile ED (Anritsu): burst vs isolati (gap ≤ 8 simboli
    = stesso burst, tipico del DFE), error-free intervals."""
    err = np.sort(np.asarray(err_sym))
    if len(err) == 0:
        return {"n_bursts": 0, "n_isolated": 0, "max_burst": 0,
                "burst_gap_sym": 8, "efi_mean_sym": None, "efi_min_sym": None}
    gaps = np.diff(err)
    burst_gap = 8
    lengths = []
    cur = 1
    for g in gaps:
        if g <= burst_gap:
            cur += 1
        else:
            lengths.append(cur)
            cur = 1
    lengths.append(cur)
    efi = gaps[gaps > burst_gap]
    return {
        "burst_gap_sym": burst_gap,
        "n_bursts": int(sum(1 for v in lengths if v >= 2)),
        "n_isolated": int(sum(1 for v in lengths if v == 1)),
        "max_burst": int(max(lengths)),
        "burst_err_pct": (100.0 * sum(v for v in lengths if v >= 2)
                          / max(len(err), 1)),
        "efi_mean_sym": (float(np.mean(efi)) if len(efi) else None),
        "efi_min_sym": (int(np.min(efi)) if len(efi) else None),
    }


def bert_panel(sim, cfg):
    """Error detector: mappa degli errori sulla validation + inserzioni."""
    if not sim.link_up:
        return {"link_down": True}
    from serdes_sim.blocks.stimulus import hard_slice
    eq = sim.eq
    spec = sim.spec
    decided = hard_slice(eq.dfe_output, spec.levels_array)
    valid = eq.validation_fse
    decided_bits = stimulus.symbols_to_bits(decided[valid], spec).reshape(-1, spec.bits_per_symbol)
    truth_bits = stimulus.symbols_to_bits(eq.d_fse[valid], spec).reshape(-1, spec.bits_per_symbol)
    bit_err_cols = np.sum(decided_bits != truth_bits, axis=0)
    symbol_err = np.any(decided_bits != truth_bits, axis=1)
    err_sym = eq.symbol_k_fse[decided != eq.d_fse]
    err_val = err_sym[err_sym >= cfg.training_stop + 200]
    # densità per bin da 256 simboli
    nbins = max(cfg.n_symbols // 256, 1)
    hist, edges = np.histogram(err_val, bins=nbins, range=(0, cfg.n_symbols))
    out = {
        "err_positions_sym": err_val[:3000],
        "hist_x": 0.5 * (edges[:-1] + edges[1:]),
        "hist": hist,
        "n_errors": int(len(err_val)),
        "n_bits": int(decided_bits.size),
        "n_symbols": int(len(decided_bits)),
        "bit_errors": int(np.sum(bit_err_cols)),
        "symbol_errors": int(np.sum(symbol_err)),
        "bit_errors_by_lane": bit_err_cols,
        "ber": float(np.mean(decided_bits != truth_bits)),
        "ser": float(np.mean(symbol_err)),
        "pattern": cfg.pattern,
        "error_analysis": _error_analysis(err_val),
        "sync": bool(sim.cdr.pattern_locked) if sim.cdr is not None else True,
        "validation_start": cfg.training_stop + 200,
        "inserted": (sim.err_positions // spec.bits_per_symbol
                     if sim.err_positions is not None else []),
    }
    return J(out)


def l2_panel(sim, cfg):
    if cfg.pattern != "eth":
        return {"inactive": True}
    if not sim.link_up:
        return {"link_down": True}
    if sim.l2 is None:
        return {"inactive": True, "reason": "finestra troppo corta"}
    l2 = sim.l2
    return J({
        "frames_expected": l2.frames_expected,
        "frames_detected": l2.frames_detected,
        "frames_ok": l2.frames_ok,
        "frames_fcs_bad": l2.frames_fcs_bad,
        "frames_lost": l2.frames_lost,
        "throughput_gbps": l2.throughput_gbps,
        "line_rate_gbps": l2.line_rate_gbps,
        "frame_bytes": cfg.l2_frame_bytes,
        "fec": cfg.fec_mode,
    })



def cmis_panel(sim, cfg):
    """CMIS-lite: gestione modulo stile QSFP-DD/OSFP (subset dichiarato).

    Ispirato a CMIS 5.x (MSA pubblico): Module State Machine, DataPath state,
    flag di lane (LOS/LOL/TX fault) e monitor DOM/VDM — tutti DERIVATI dal
    banco reale (potenze da MZM/PD, LOL dal lock del CDR, BER dai contatori).
    NON è la register map completa: niente pagine/byte, I2C, CDB, firmware.
    """
    optical = sim.optical is not None
    if optical:
        tx_power_dbm = float(w_to_dbm(np.mean(sim.optical.P_mzm_w)))
        rx_power_dbm = float(w_to_dbm(np.mean(sim.optical.P_fiber_w)))
    else:
        tx_power_dbm = rx_power_dbm = None
    # flag di lane derivati dallo stato vero del banco
    rx_los = (rx_power_dbm is not None and rx_power_dbm < -14.0) or \
             (not optical and float(np.std(sim.receiver.v_ctle_v)) < 5e-3)
    rx_lol = (sim.cdr is not None and not sim.cdr.locked)
    tx_fault = sim.tx.driver_clip_fraction > 0.01
    dp_state = ("DataPathActivated" if sim.link_up
                else ("DataPathInit" if not rx_los else "DataPathDeinit"))
    # DOM: temperatura/Vcc sintetiche ma stabili per seed (dichiarato)
    rng = np.random.default_rng(sim.seed)
    temp_c = 42.0 + float(rng.normal(0, 0.4))
    vcc = 3.28 + float(rng.normal(0, 0.005))
    laser_mw = (sim.optical.laser_power_w * 1e3 if optical else None)
    media = ("SMF" if optical and getattr(cfg, "fiber_type", "smf") != "mmf"
             else ("MMF" if optical else "passive copper"))

    def dom_row(name, value, unit, warn_lo, warn_hi):
        status = "ok"
        if value is None:
            status = "na"
        elif value < warn_lo or value > warn_hi:
            status = "warn"
        return {"name": name, "value": value, "unit": unit,
                "warn_lo": warn_lo, "warn_hi": warn_hi, "status": status}

    fa = sim.fec
    fl = sim.fec_link
    return J({
        "module": {
            "vendor": "LABPRO SIM", "part": "LP-1x112-EDU",
            "media": media, "lanes": 1,
            "form_factor": "QSFP-DD-like (didattico)",
            "cmis_note": "subset ispirato a CMIS 5.x — no register map/I2C",
        },
        "module_state": "ModuleReady",
        "datapath_state": dp_state,
        "lane_flags": [{
            "lane": 1,
            "rx_los": bool(rx_los),
            "rx_lol": bool(rx_lol),
            "tx_fault": bool(tx_fault),
            "tx_adaptive_eq_fault": False,
        }],
        "dom": [
            dom_row("Temperatura modulo", temp_c, "°C", 0.0, 70.0),
            dom_row("Vcc", vcc, "V", 3.14, 3.46),
            dom_row("TX bias (proxy)",
                    laser_mw * 12.0 if laser_mw is not None else None,
                    "mA", 10.0, 120.0),
            dom_row("TX power", tx_power_dbm, "dBm", -8.0, 6.0),
            dom_row("RX power", rx_power_dbm, "dBm", -12.0, 5.0),
        ],
        "vdm": [
            {"name": "Pre-FEC BER (record)",
             "value": (fa.pre_fec_ber if fa is not None else None)},
            {"name": "Post-FEC BER (record)",
             "value": (fl.post_fec_ber if fl is not None else None)},
            {"name": "FERC — frame persi (record)",
             "value": (fl.frames_uncorrectable if fl is not None else None)},
            {"name": "SNR slicer [dB]",
             "value": (sim.snr_dfe["snr_slicer_db"]
                       if sim.snr_dfe is not None else None)},
        ],
        "link_up": bool(sim.link_up),
    })


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
    from serdes_sim.config import STANDARD_PROFILES, STANDARD_PROFILE_META
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
    exact = [name for name, item in STANDARD_PROFILES.items() if item[0] == cfg]
    active_profile = exact[0] if exact else None
    active_meta = STANDARD_PROFILE_META.get(active_profile, {})
    tx_arch = (f"{len(cfg.tx_ffe_taps)}-tap FFE · {cfg.dac_bits}-bit DAC · "
               f"{cfg.electrical_drive_mode}")
    ctle_arch = (f"{len(cfg.ctle_zeros_effective_hz)}Z/"
                 f"{len(cfg.ctle_poles_effective_hz)}P · "
                 f"{cfg.ctle_dc_gain_db:+g} dB DC")
    manifest = [
        {"block": "interface / reference plane",
         "value": (f"{active_meta.get('interface', 'custom')} · "
                   f"{active_meta.get('plane', 'LabPro internal')}"),
         "basis": "standard" if active_profile else "custom",
         "note": "nome, mezzo, reach e piano del profilo pubblico"},
        {"block": "lane / modulation",
         "value": f"{gbd:.5g} GBd · {sim.spec.label}",
         "basis": "profile-anchor" if active_profile else "custom",
         "note": "valore di corsia usato dal banco"},
        {"block": "FEC", "value": cfg.fec_mode.upper(),
         "basis": "standard-context" if active_profile else "custom",
         "note": active_meta.get("fec", "configurazione utente")},
        {"block": "TX / serializer", "value": tx_arch,
         "basis": "LabPro assumption",
         "note": "IEEE/OIF non prescrivono l'architettura interna del SerDes"},
        {"block": "channel", "value": (
            f"{cfg.channel_il_nyquist_db:g} dB @Nyquist · {cfg.link_medium}"),
         "basis": "representative model",
         "note": "non e la mask/COM di clause"},
        {"block": "optical TX", "value": (
            "bypassed" if cfg.link_medium == "copper" else
            f"{cfg.laser_type} + {cfg.optical_modulator.upper()} · "
            f"{cfg.wavelength_nm:g} nm · {cfg.fiber_type.upper()}"),
         "basis": "LabPro assumption",
         "note": "il PMD standard non impone MZM vs EML"},
        {"block": "PD / TIA / AGC", "value": (
            f"PD {cfg.pd_bw_hz/1e9:g}G · TIA/AFE {cfg.tia_bw_hz/1e9:g}G · "
            f"AGC {cfg.agc_target_rms_v:g} Vrms"),
         "basis": "LabPro assumption",
         "note": "front-end parametrico, non circuit-level compliance"},
        {"block": "CTLE", "value": ctle_arch,
         "basis": "LabPro assumption",
         "note": "tutte le sezioni entrano nel datapath"},
        {"block": "ADC / timing", "value": (
            f"{cfg.adc_bits}-bit {cfg.adc_sps} sps · CDR {cfg.cdr_mode} "
            f"BW={cfg.cdr_bw:g}·baud"),
         "basis": "LabPro assumption",
         "note": "architettura RX scelta, non prescritta dall'interfaccia"},
        {"block": "DSP", "value": f"FSE {cfg.fse_taps} taps · DFE {cfg.dfe_taps} taps",
         "basis": "LabPro assumption",
         "note": "reference receiver didattico"},
    ]
    out = {"gbd": gbd, "lane_gbs": gbd * bps, "modulation": sim.spec.label,
           "active_profile": active_profile, "manifest": manifest,
           "family": fam[2] if fam else None,
           "family_gbd": fam[0] if fam else None,
           "deviation_pct": 100 * dev if dev is not None else None,
           "ber": ber, "link_up": bool(sim.link_up),
           "families": [{"gbd": f[0], "mod": f[1], "name": f[2]}
                        for f in fams],
           "profiles": [dict(name=name, description=item[1],
                             compatible=(item[0].modulation == cfg.modulation
                                         and item[0].link_medium == cfg.link_medium
                                         and abs(item[0].symbol_rate_hz
                                                 - cfg.symbol_rate_hz) < 1.0),
                             **STANDARD_PROFILE_META.get(name, {}))
                        for name, item in STANDARD_PROFILES.items()]}
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
    "cmis": cmis_panel,
    "eye": eye_panel,
    "bert": bert_panel,
    "l2": l2_panel,
    "jitter": jitter_panel,
    "spectrum": spectrum_panel,
    "ctle": ctle_panel,
    "channel": channel_panel,
    "pd": pd_panel,
    "tia": tia_panel,
    "agc": agc_panel,
    "optical": optical_panel,
    "adc": adc_panel,
    "timing": timing_panel,
    "eq": eq_panel,
    "decisions": decisions_panel,
    "stimulus": stimulus_panel,
    "standards": standards_panel,
    "checks": checks_panel,
    "education": lambda sim, cfg: {"topics": TOPICS},
}
