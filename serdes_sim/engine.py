"""Orchestrazione della catena completa.

`simulate(cfg, seed, depth)` esegue la catena stadio per stadio e ritorna un
`SimResult` con tutti gli array intermedi, il signal ledger, i checkpoint e le
metriche. `depth="light"` salta le diagnostiche costose (S-curve, loop Gardner,
bathtub, tone-lab, error propagation) ed è pensata per gli sweep parametrici.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .blocks import adc as adc_block
from .blocks import cdr as cdr_block
from .blocks import channel as channel_block
from .blocks import fec as fec_block
from .blocks import optical as optical_block
from .blocks import receiver as receiver_block
from .blocks import stimulus, tx as tx_block
from .blocks import dsp as dsp_block
from .blocks import metrics as metrics_block
from .config import LinkConfig
from .utils import rms_ac


@dataclass
class SimResult:
    cfg: LinkConfig
    seed: int
    depth: str
    elapsed_s: float
    # stimolo
    spec: stimulus.ModulationSpec = None
    pam4_symbols: np.ndarray = None    # simboli trasmessi (nome storico v7)
    occupancy: np.ndarray = None
    transition_probability: np.ndarray = None
    # stadi
    tx: tx_block.TxResult = None
    channel: channel_block.ChannelResult = None
    optical: optical_block.OpticalResult = None
    receiver: receiver_block.ReceiverResult = None
    adc: adc_block.AdcResult = None
    tone_lab: adc_block.ToneLabResult = None
    timing: dsp_block.TimingResult = None
    eq: dsp_block.EqualizerResult = None
    # metriche
    metrics_rows: list = field(default_factory=list)
    level_stats: list = None
    eye_openings_3sigma: list = None
    llr: np.ndarray = None
    gmi_per_bit: list = None
    gmi_total: float = None
    waterfall: tuple = None
    bathtub: metrics_block.BathtubResult = None
    contour: tuple = None
    # decisioni e FEC
    confusion: np.ndarray = None            # livello tx × livello deciso (post-DFE)
    thresholds_mid: list = None             # soglie nominali (punto medio)
    thresholds_calibrated: list = None      # soglie pesate sulle sigma
    fec: fec_block.FecAnalysis = None       # analisi RS(544,514) sul pattern DFE
    snr: dict = None                        # SNR/Q al piano di decisione (FSE)
    snr_dfe: dict = None                    # idem dopo il DFE
    optical_levels: dict = None             # OMA/ER proxy al PD
    level_stats_dfe: list = None            # statistiche per livello POST-DFE
    thresholds_dfe: tuple = None            # (mid, calibrate) al piano DFE
    level_stats_baud: list = None           # statistiche baseline 1 sps pre-EQ
    thresholds_baud: tuple = None           # (mid, calibrate) al piano pre-EQ
    # FEC nel percorso (fec_mode != none)
    tx_bits: np.ndarray = None              # bit trasmessi (post-encoder)
    fec_codec_name: str = ""
    fec_n_frames_tx: int = 0
    fec_link: "fec_block.FecLinkResult" = None
    fec_frames_covered: tuple = ()          # indici dei frame decodati
    # CDR nel datapath
    cdr: "cdr_block.CdrResult" = None
    link_up: bool = False

    @property
    def rx_delay_ui(self) -> float:
        """Ritardo del campione dati rispetto al centro simbolo TX, nella
        convenzione degli eye (centro = (k+0.5+delay)·sps sull'asse analogico)."""
        if self.cdr is not None and self.cdr.locked:
            # pos è in campioni ADC; l'asse ADC parte a adc_phase_ui e il
            # pattern lock mappa k_tx = k_rx + lag
            lag = self.cdr.pattern_lag or 0
            return (self.cdr.delay_ui_est + self.cfg.adc_phase_ui
                    - lag - 0.5)
        if self.timing is not None:
            return self.timing.rx_integer_delay_ui + self.timing.best_phase_ui
        return 0.0

    @property
    def timing_is_supervised(self) -> bool:
        """La fase usata dal DSP viene dall'acquisition supervisionata (che usa
        la sequenza trasmessa come riferimento), NON dal loop Gardner."""
        return True
    # bookkeeping
    ledger: list = field(default_factory=list)
    checks: list = field(default_factory=list)

    @property
    def ber_pre_eq(self):
        return self.metrics_rows[0]["BER"] if self.metrics_rows else float("nan")

    @property
    def ber_post_fse(self):
        return self.metrics_rows[1]["BER"] if len(self.metrics_rows) > 1 else float("nan")

    @property
    def ber_post_dfe(self):
        return self.metrics_rows[2]["BER"] if len(self.metrics_rows) > 2 else float("nan")


def _register(result: SimResult, name, values, unit, domain, sample_rate_hz,
              reference_plane, note=""):
    x = np.asarray(values)
    result.ledger.append({
        "stage": name,
        "domain": domain,
        "unit": unit,
        "samples": len(x),
        "sample_rate_GSa_s": float("nan") if sample_rate_hz is None else sample_rate_hz / 1e9,
        "mean": float(np.mean(np.abs(x))) if np.iscomplexobj(x) else float(np.mean(x)),
        "ac_rms": rms_ac(x),
        "peak_abs": float(np.max(np.abs(x))),
        "reference_plane": reference_plane,
        "note": note,
    })


def _check(result: SimResult, condition, label, detail=""):
    ok = bool(condition)
    result.checks.append({"status": "PASS" if ok else "FAIL",
                          "check": label, "detail": detail})
    return ok


def simulate(cfg: LinkConfig = None, seed: int = 20240731,
             depth: str = "full") -> SimResult:
    """Esegue la catena completa. depth in {"light", "full"}."""
    if depth not in ("light", "full"):
        raise ValueError(f"depth deve essere 'light' o 'full', non {depth!r}")
    cfg = cfg or LinkConfig()
    problems = cfg.validate()
    if problems:
        raise ValueError("; ".join(problems))
    t0 = time.perf_counter()
    rng = np.random.default_rng(seed)
    result = SimResult(cfg=cfg, seed=seed, depth=depth, elapsed_s=0.0)

    # --- 1. Stimolo (con FEC opzionale NEL percorso TX) ---------------------
    spec = stimulus.get_modulation(cfg.modulation, cfg.pam4_mapping)
    result.spec = spec
    bps = spec.bits_per_symbol
    if cfg.fec_mode != "none":
        codec = fec_block.FEC_CODECS[cfg.fec_mode]
        frame_bits = codec.n * fec_block.GF_M
        total_bits = cfg.n_symbols * bps
        n_frames_tx = total_bits // frame_bits
        if n_frames_tx < 1:
            raise ValueError(f"record troppo corto per un frame {codec.name}")
        payload_need = n_frames_tx * codec.k * fec_block.GF_M
        # payload + filler PRBS per i bit oltre l'ultimo frame completo
        raw = stimulus.prbs_bits(cfg.prbs_order, payload_need + total_bits)
        coded = fec_block.encode_stream(raw[:payload_need], codec, n_frames_tx)
        filler = raw[payload_need:payload_need + (total_bits - len(coded))]
        tx_bits = np.concatenate([coded, filler])
        pam4 = stimulus.symbols_from_bits(tx_bits, spec)
        result.tx_bits = tx_bits
        result.fec_codec_name = codec.name
        result.fec_n_frames_tx = n_frames_tx
    else:
        pam4 = stimulus.generate_stimulus(cfg.n_symbols, cfg.prbs_order, spec)
        result.tx_bits = stimulus.symbols_to_bits(pam4, spec)
    result.pam4_symbols = pam4
    result.occupancy = stimulus.level_occupancy(pam4, spec.levels_array)
    _, result.transition_probability = stimulus.transition_matrix(
        pam4, spec.levels_array)
    _register(result, "symbols", pam4, "normalized amplitude", "symbol",
              cfg.symbol_rate_hz, "uscita mapper",
              f"{spec.label}, PRBS{cfg.prbs_order}"
              + (f" + {cfg.fec_mode.upper()} in-path" if cfg.fec_mode != "none" else ""))
    if (cfg.n_symbols == stimulus.PRBS13_PERIOD and cfg.prbs_order == 13
            and spec.name == "PAM4" and cfg.fec_mode == "none"):
        _check(result, np.array_equal(np.sort(result.occupancy), [2047, 2048, 2048, 2048]),
               "Occupazione PRBS13Q-style 2047/2048")
    else:
        balance = result.occupancy.min() / max(result.occupancy.max(), 1)
        _check(result, balance > 0.85, "Occupazione dei livelli bilanciata",
               f"min/max={balance:.3f} (PRBS{cfg.prbs_order}, {spec.label}"
               + (f", {cfg.fec_mode}" if cfg.fec_mode != "none" else "") + ")")

    # --- 2. TX elettrico (serializer/PLL con jitter iniettabile) ------------
    result.tx = tx_block.run_tx(cfg, pam4, rng=rng)
    _register(result, "tx_ffe_symbols", result.tx.tx_ffe_symbols,
              "normalized amplitude", "symbol", cfg.symbol_rate_hz, "uscita TX FFE")
    _register(result, "dac_waveform", result.tx.dac_waveform, "normalized amplitude",
              "sample", cfg.fs_analog_hz, "DAC output",
              f"{cfg.dac_bits} bit; LSB={result.tx.dac_lsb:.4g}")
    _register(result, "driver_voltage_v", result.tx.driver_voltage_v, "V",
              "electrical", cfg.fs_analog_hz, "driver output / channel input")
    _check(result, result.tx.swing_cost >= 1, "La pre-enfasi consuma headroom",
           f"peak ratio={result.tx.swing_cost:.3f}")
    _check(result, result.tx.driver_clip_fraction < 0.01,
           "Driver non dominato dal clipping",
           f"clip={100 * result.tx.driver_clip_fraction:.3f}%")

    # --- 3. Canale elettrico ------------------------------------------------
    result.channel = channel_block.run_channel(cfg, result.tx.driver_voltage_v)
    _register(result, "electrical_waveform_v", result.channel.electrical_waveform_v,
              "V", "electrical", cfg.fs_analog_hz, "channel output / MZM driver input",
              "analytic S21-equivalent")
    _check(result, abs(result.channel.cursor_values[result.channel.cursor_ui == 0][0] - 1) < 1e-9,
           "Main cursor normalizzato")

    # --- 4. Ottica ----------------------------------------------------------
    result.optical = optical_block.run_optical(cfg, result.channel.electrical_waveform_v)
    _register(result, "E_mzm", result.optical.E_mzm, "sqrt(W)", "optical field",
              cfg.fs_analog_hz, "MZM output", f"alpha={cfg.chirp_alpha:+.2f}")
    _register(result, "E_fiber", result.optical.E_fiber, "sqrt(W)", "optical field",
              cfg.fs_analog_hz, "fiber output / PD input",
              f"{cfg.fiber_km:g} km @ {cfg.wavelength_nm:g} nm")
    budget = result.optical.power_budget_dbm
    _check(result, abs((budget["fiber launch"] - budget["MZM output"]) + cfg.coupling_il_db) < 1e-6,
           "Loss campo/potenza coerente")

    # --- 5. Ricevitore ------------------------------------------------------
    result.receiver = receiver_block.run_receiver(cfg, result.optical.P_fiber_w, rng)
    _register(result, "i_pd_signal_a", result.receiver.i_pd_signal_a, "A",
              "photocurrent", cfg.fs_analog_hz, "PD output / TIA input",
              "before receiver noise")
    _register(result, "v_tia_v", result.receiver.v_tia_v, "V", "electrical",
              cfg.fs_analog_hz, "TIA output", "includes PD/TIA/RIN noise")
    _register(result, "v_agc_v", result.receiver.v_agc_v, "V", "electrical",
              cfg.fs_analog_hz, "AGC output / CTLE input", "DC removed")
    _register(result, "v_ctle_v", result.receiver.v_ctle_v, "V", "electrical",
              cfg.fs_analog_hz, "CTLE output / ADC input")
    _check(result, result.receiver.pd_sat_fraction < 1e-3, "Photodiode fuori saturazione",
           f"sat={100 * result.receiver.pd_sat_fraction:.4f}%")
    _check(result, result.receiver.tia_clip_fraction < 1e-3, "TIA fuori overload",
           f"clip={100 * result.receiver.tia_clip_fraction:.4f}%")

    # --- 6. ADC -------------------------------------------------------------
    result.adc = adc_block.run_adc(cfg, result.receiver.v_ctle_v, rng)
    _register(result, "adc_samples_v", result.adc.adc_samples_v, "V",
              "digital samples", cfg.fs_adc_hz, "ADC output / DSP input",
              f"{cfg.adc_bits} bit, {cfg.adc_interleaves}-way interleaved")
    _check(result, result.adc.adc_clip_fraction < 0.01, "ADC non dominato dal clipping",
           f"clip={100 * result.adc.adc_clip_fraction:.3f}%")

    # --- 7. Timing recovery + 8. Equalizzazione -----------------------------
    # cdr_mode gardner/mm: il loop PI+NCO decide DAVVERO gli istanti di
    # campionamento e l'allineamento viene dal pattern lock (BERT-style).
    # cdr_mode oracle: modalità idealizzata dichiarata (fase dal minimo MSE
    # con i simboli noti) — utile come riferimento, non è un ricevitore.
    result.link_up = False
    if cfg.cdr_mode == "oracle":
        n_phases = 121 if depth == "full" else 61
        result.timing = dsp_block.acquire_timing(
            cfg, result.adc.adc_samples_v, result.adc.adc_nominal_time_ui, pam4,
            n_phases=n_phases)
        _check(result, abs(result.timing.best_phase_ui) < 0.44,
               "Acquisition oracle (modalità idealizzata dichiarata)",
               f"delay={result.timing.rx_integer_delay_ui:+d} UI, "
               f"fase={result.timing.best_phase_ui:+.3f} UI")
        result.eq = dsp_block.run_equalizers(
            cfg, result.adc.adc_samples_v, result.adc.adc_nominal_time_ui, pam4,
            result.timing, full_depth=(depth == "full"), spec=spec)
        result.link_up = True
    else:
        result.cdr = cdr_block.run_cdr(cfg, result.adc.adc_samples_v,
                                       mode=cfg.cdr_mode,
                                       levels=spec.levels_array)
        c = result.cdr
        _check(result, c.locked, f"CDR {cfg.cdr_mode} in lock",
               c.detail + (f", lock al simbolo {c.lock_symbol}"
                           if c.lock_symbol is not None else ""))
        if c.locked:
            grid = np.arange(len(result.adc.adc_samples_v), dtype=float)
            adc_v = result.adc.adc_samples_v
            y_data = np.interp(c.pos_data_samples, grid, adc_v)
            lag, corr, _ = cdr_block.pattern_sync(y_data, pam4)
            # ambiguità dato/fronte del Gardner: prova l'ipotesi a mezza UI
            half = cfg.adc_sps / 2.0
            y_alt = np.interp(c.pos_data_samples + half, grid, adc_v)
            lag2, corr2, _ = cdr_block.pattern_sync(y_alt, pam4)
            if abs(corr2) > abs(corr) * 1.15:
                lag, corr = lag2, corr2
                c.pos_data_samples = c.pos_data_samples + half
                c.delay_ui_est += 0.5
                c.detail += " | lock sul fronte: dati a +0.5 UI (pattern sync)"
            c.pattern_lag, c.pattern_corr = lag, corr
            c.pattern_locked = bool(lag is not None and abs(corr) > 0.15)
            _check(result, c.pattern_locked, "Pattern lock (BERT-style)",
                   f"lag={lag}, |corr|={abs(corr):.3f}"
                   if lag is not None else "correlazione insufficiente")
            if c.pattern_locked:
                try:
                    result.eq = dsp_block.run_equalizers_timed(
                        cfg, result.adc.adc_samples_v, c.pos_data_samples,
                        lag, pam4, spec=spec,
                        full_depth=(depth == "full"))
                    result.link_up = True
                except ValueError as exc:
                    _check(result, False, "Equalizzazione dopo il lock",
                           str(exc))
        c.link_up = result.link_up
        # diagnostica di confronto con l'oracle (solo full, etichettata)
        if depth == "full":
            result.timing = dsp_block.acquire_timing(
                cfg, result.adc.adc_samples_v,
                result.adc.adc_nominal_time_ui, pam4, n_phases=61)

    if not result.link_up:
        _check(result, False, "LINK DOWN — metriche soppresse",
               "senza lock del CDR e del pattern non esistono BER/GMI/FEC: "
               "questo è il comportamento di un ricevitore reale")
        result.elapsed_s = time.perf_counter() - t0
        return result

    # --- 9. Metriche (solo con link up) -------------------------------------
    eq = result.eq
    result.metrics_rows = [
        metrics_block.stage_error_metrics(eq.rx_baud_norm, eq.truth_baud,
                                          eq.validation_baud, "ADC + timing",
                                          spec=spec),
        metrics_block.stage_error_metrics(eq.fse_output, eq.d_fse,
                                          eq.validation_fse, "FSE 2 sps",
                                          spec=spec),
        metrics_block.stage_error_metrics(eq.dfe_output, eq.d_fse,
                                          eq.validation_fse, "FSE + DFE",
                                          spec=spec),
    ]
    _check(result, result.metrics_rows[1]["BER"] <= result.metrics_rows[0]["BER"],
           "FSE migliora (o eguaglia) la BER di validation",
           f"{result.metrics_rows[0]['BER']:.2e} → {result.metrics_rows[1]['BER']:.2e}")
    _check(result, result.metrics_rows[2]["BER"] <= result.metrics_rows[1]["BER"] + 1e-12,
           "DFE non degrada la BER di validation")

    result.level_stats, result.eye_openings_3sigma = metrics_block.level_statistics(
        eq.fse_output[eq.train_fse], eq.d_fse[eq.train_fse], spec=spec)

    means = np.array([r["mean"] for r in result.level_stats])
    variances = np.maximum(np.array([r["sigma"] for r in result.level_stats]) ** 2, 1e-10)
    y_soft = eq.fse_output[eq.validation_fse]
    d_soft = eq.d_fse[eq.validation_fse]
    result.llr = metrics_block.calibrated_llr(y_soft, means, variances, spec=spec)
    true_bit_pairs = spec.bit_array[
        stimulus.nearest_level_index(d_soft, spec.levels_array)]
    result.gmi_per_bit, result.gmi_total = metrics_block.gmi_from_llr(
        result.llr, true_bit_pairs)
    _check(result, np.isfinite(result.gmi_total)
           and result.gmi_total <= spec.bits_per_symbol + 1e-6,
           "GMI numericamente valida", f"GMI={result.gmi_total:.4f} bit/simbolo "
           f"(max {spec.bits_per_symbol})")

    result.waterfall = metrics_block.detector_waterfall(y_soft, d_soft, rng,
                                                        spec=spec)

    # --- 9b. Decisioni, soglie e FEC RS(544,514) ---------------------------
    decided_val = stimulus.hard_slice(eq.dfe_output[eq.validation_fse],
                                      spec.levels_array)
    truth_val = eq.d_fse[eq.validation_fse]
    result.confusion = metrics_block.decision_confusion_matrix(
        decided_val, truth_val, spec.levels_array)
    result.thresholds_mid, result.thresholds_calibrated = \
        metrics_block.decision_thresholds(result.level_stats)
    result.fec = fec_block.analyze_link_fec(
        stimulus.symbols_to_bits(truth_val, spec),
        stimulus.symbols_to_bits(decided_val, spec))

    # --- 9b-bis. FEC nel percorso: decodifica dei frame coperti -------------
    if cfg.fec_mode != "none":
        codec = fec_block.FEC_CODECS[cfg.fec_mode]
        frame_syms = codec.n * fec_block.GF_M // spec.bits_per_symbol
        k0, k1 = int(eq.symbol_k_fse[0]), int(eq.symbol_k_fse[-1])
        # SOLO frame interamente in validation: niente dati di training
        # nella statistica FEC
        k_start = max(k0, cfg.training_stop + 200)
        covered = [f for f in range(result.fec_n_frames_tx)
                   if f * frame_syms >= k_start
                   and (f + 1) * frame_syms - 1 <= k1]
        if covered:
            decided_full = np.zeros(cfg.n_symbols)
            decided_full[eq.symbol_k_fse] = stimulus.hard_slice(
                eq.dfe_output, spec.levels_array)
            f_lo, f_hi = covered[0], covered[-1] + 1
            sl = slice(f_lo * frame_syms, f_hi * frame_syms)
            decided_bits_cov = stimulus.symbols_to_bits(decided_full[sl], spec)
            tx_bits_cov = result.tx_bits[sl.start * spec.bits_per_symbol:
                                         sl.stop * spec.bits_per_symbol]
            result.fec_link = fec_block.decode_stream(
                decided_bits_cov, tx_bits_cov, codec, len(covered))
            result.fec_frames_covered = tuple(covered)
            fl = result.fec_link
            _check(result,
                   fl.post_fec_ber <= fl.pre_fec_ber + 1e-12
                   or fl.frames_miscorrected > 0,
                   f"{codec.name} nel percorso: post-FEC ≤ pre-FEC",
                   f"{fl.pre_fec_ber:.2e} → {fl.post_fec_ber:.2e} "
                   f"({fl.frames_corrected} corretti, "
                   f"{fl.frames_uncorrectable} persi, "
                   f"{fl.frames_miscorrected} miscorretti su {fl.n_frames})")

    # --- 9c. SNR/Q e grandezze ottiche -------------------------------------
    # Ogni piano di osservazione ha le SUE statistiche/soglie: FSE, DFE e
    # baseline 1 sps non sono interscambiabili.
    result.snr = metrics_block.snr_report(y_soft, d_soft, result.level_stats)
    dfe_stats, _ = metrics_block.level_statistics(
        eq.dfe_output[eq.train_fse], eq.d_fse[eq.train_fse], spec=spec)
    result.level_stats_dfe = dfe_stats
    result.thresholds_dfe = metrics_block.decision_thresholds(dfe_stats)
    train_baud = (eq.symbol_k >= cfg.training_start) & (eq.symbol_k < cfg.training_stop)
    baud_stats, _ = metrics_block.level_statistics(
        eq.rx_baud_norm[train_baud], eq.truth_baud[train_baud], spec=spec)
    result.level_stats_baud = baud_stats
    result.thresholds_baud = metrics_block.decision_thresholds(baud_stats)
    result.snr_dfe = metrics_block.snr_report(
        eq.dfe_output[eq.validation_fse], truth_val, dfe_stats)
    result.optical_levels = metrics_block.optical_level_proxies(
        result.optical.P_fiber_w)

    # --- 10. Diagnostiche approfondite (solo depth full) --------------------
    if depth == "full":
        if result.timing is not None:
            dsp_block.compute_scurves(cfg, result.adc.adc_samples_v,
                                      result.adc.adc_nominal_time_ui, pam4,
                                      result.timing, levels=spec.levels_array)
            result.bathtub = metrics_block.empirical_bathtub(
                cfg, result.adc.adc_samples_v, result.adc.adc_nominal_time_ui,
                pam4, result.timing.rx_integer_delay_ui, spec=spec)
        if cfg.cdr_mode == "oracle" and result.timing is not None:
            # vecchio loop diagnostico: ha senso solo in modalità oracle
            dsp_block.run_gardner_loop(cfg, result.adc.adc_samples_v,
                                       result.adc.adc_nominal_time_ui,
                                       result.timing)
        result.tone_lab = adc_block.run_tone_lab(cfg, result.adc)
        result.contour = metrics_block.ber_contour(cfg)

    result.elapsed_s = time.perf_counter() - t0
    return result


# ---------------------------------------------------------------------------
# Sweep parametrici (per la pagina Esperimenti)
# ---------------------------------------------------------------------------

SWEEPABLE_FIELDS = {
    "fiber_km": ("Lunghezza fibra [km]", 0.0, 15.0),
    "laser_dbm": ("Potenza laser [dBm]", -6.0, 10.0),
    "channel_il_nyquist_db": ("IL canale @Nyquist [dB]", 4.0, 26.0),
    "ctle_zero_hz": ("Zero CTLE [Hz]", 3e9, 20e9),
    "tia_noise_a_rt_hz": ("Rumore TIA [A/√Hz]", 5e-12, 80e-12),
    "rin_db_hz": ("RIN [dB/Hz]", -160.0, -125.0),
    "chirp_alpha": ("Chirp α", -1.5, 1.5),
    "adc_bits": ("Bit ADC", 4, 10),
    "dispersion_ps_nm_km": ("D [ps/(nm·km)]", -20.0, 20.0),
    "tx_pj_amp_ui": ("PJ TX ampiezza [UI pk]", 0.0, 0.3),
    "tx_rj_rms_fs": ("RJ TX [fs rms]", 0.0, 1200.0),
    "cdr_bw": ("Banda loop CDR [·f_baud]", 0.0004, 0.005),
    "rx_ppm_offset": ("Offset clock RX [ppm]", -300.0, 300.0),
    "mzm_bias_rad": ("Bias MZM [rad]", 0.9, 2.2),
}


def jitter_tolerance(cfg: LinkConfig, freqs_mhz, target_ber=4e-2,
                     amp_max_ui=0.35, iters=6, seed=20240731,
                     progress_callback=None):
    """JTOL-lite (dichiaratamente NON normativa): per ogni frequenza di PJ,
    bisezione sull'ampiezza per trovare la massima con BER ≤ target e link UP.

    Un punto è None se il link fallisce già senza PJ aggiunto."""
    def passes(amp, f_mhz):
        r = simulate(cfg.with_updates(tx_pj_amp_ui=float(amp),
                                      tx_pj_freq_mhz=float(f_mhz)),
                     seed=seed, depth="light")
        return bool(r.link_up and r.ber_post_dfe <= target_ber)

    points = []
    total = len(freqs_mhz) * (iters + 2)
    done = 0
    for f_mhz in freqs_mhz:
        if not passes(0.0, f_mhz):
            points.append({"freq_mhz": float(f_mhz), "amp_ui": None})
            done += iters + 2
            if progress_callback:
                progress_callback(done / total)
            continue
        lo, hi = 0.0, amp_max_ui
        done += 1
        if passes(hi, f_mhz):
            points.append({"freq_mhz": float(f_mhz), "amp_ui": float(hi),
                           "capped": True})
            done += iters + 1
            if progress_callback:
                progress_callback(done / total)
            continue
        done += 1
        for _ in range(iters):
            mid = 0.5 * (lo + hi)
            if passes(mid, f_mhz):
                lo = mid
            else:
                hi = mid
            done += 1
            if progress_callback:
                progress_callback(done / total)
        points.append({"freq_mhz": float(f_mhz), "amp_ui": float(lo),
                       "capped": False})
    return points


def sweep(cfg: LinkConfig, field_name: str, values, seed=20240731,
          progress_callback=None):
    """Ripete la simulazione light variando un solo parametro."""
    if field_name not in SWEEPABLE_FIELDS:
        raise ValueError(f"campo non sweepable: {field_name}")
    rows = []
    for i, v in enumerate(values):
        v_cast = int(v) if field_name == "adc_bits" else float(v)
        c = cfg.with_updates(**{field_name: v_cast})
        r = simulate(c, seed=seed, depth="light")
        rows.append({
            field_name: v_cast,
            "link_up": r.link_up,
            "BER_pre_EQ": r.ber_pre_eq,
            "BER_FSE": r.ber_post_fse,
            "BER_FSE_DFE": r.ber_post_dfe,
            "GMI_bit_per_simbolo": (r.gmi_total if r.link_up else float("nan")),
            "P_PD_dBm": r.optical.power_budget_dbm["PD input"],
            "FER_RS544_iid": r.fec.fer_iid_model_qmeas if r.fec else float("nan"),
            "val_bits": (r.metrics_rows[2]["bits"] if r.link_up else 0),
            "checks_fail": sum(1 for ck in r.checks if ck["status"] == "FAIL"),
        })
        if progress_callback:
            progress_callback((i + 1) / len(values))
    return rows
