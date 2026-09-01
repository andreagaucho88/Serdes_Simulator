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
from .blocks import ethernet
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
    channel_input_v: np.ndarray = None
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
    # BERT / L2
    err_positions: np.ndarray = None        # bit invertiti al TX (riferimento ED)
    l2: "ethernet.L2Analysis" = None        # analisi frame (pattern eth)
    l2_window_bits: np.ndarray = None       # finestra RX descramblata (ispettore)
    l2_seq0: int = 0

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
        """True solo per la modalita oracle idealizzata.

        Gardner/MM usano nel datapath gli istanti decisi da TED+PI+NCO; il
        pattern noto serve dopo, per il lock/allineamento del BERT.
        """
        return self.cfg.cdr_mode == "oracle"
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

    # --- 1. Stimolo: PPG (prbs/clock/eth) + FEC opzionale + error insertion --
    spec = stimulus.get_modulation(cfg.modulation, cfg.pam4_mapping)
    result.spec = spec
    bps = spec.bits_per_symbol
    total_bits = cfg.n_symbols * bps

    # sorgente del payload (stile PPG di un BERT)
    def _payload_bits(n):
        if cfg.pattern == "eth":
            bits, _, _ = ethernet.build_stream_bits(
                n, cfg.l2_frame_bytes, ipg_bytes=cfg.l2_ipg_bytes,
                streams=cfg.l2_streams)
            # scrambler PCS (Clause 49): senza, l'idle 0x00 di un IPG lungo
            # produce run costanti che ammazzano CDR e AGC
            return ethernet.scramble(bits)
        if cfg.pattern == "ssprq_like":
            return stimulus.ssprq_like_bits(n, spec)
        if cfg.pattern == "ssprq":
            return stimulus.ssprq_bits(n, spec)
        if cfg.pattern == "custom_hex":
            return stimulus.custom_hex_bits(cfg.custom_pattern_hex, n)
        if cfg.pattern == "clock2":
            return stimulus.clock_pattern_bits(n, spec, 1)
        if cfg.pattern == "clock8":
            return stimulus.clock_pattern_bits(n, spec, 4)
        return stimulus.prbs_bits(cfg.prbs_order, n)

    if cfg.fec_mode != "none":
        codec = fec_block.FEC_CODECS[cfg.fec_mode]
        frame_bits = codec.n * fec_block.GF_M
        n_frames_tx = total_bits // frame_bits
        if n_frames_tx < 1:
            raise ValueError(f"record troppo corto per un frame {codec.name}")
        payload_need = n_frames_tx * codec.k * fec_block.GF_M
        raw = _payload_bits(payload_need + total_bits)
        coded = fec_block.encode_stream(raw[:payload_need], codec, n_frames_tx)
        coded = fec_block.interleave_symbols(coded, codec,
                                             cfg.fec_interleave)
        filler = raw[payload_need:payload_need + (total_bits - len(coded))]
        tx_bits = np.concatenate([coded, filler])
        result.fec_codec_name = codec.name
        result.fec_n_frames_tx = n_frames_tx
    else:
        tx_bits = _payload_bits(total_bits)
    result.tx_bits = tx_bits          # riferimento PULITO dell'error detector

    # error insertion stile BERT: il TX modula bit corrotti, l'ED confronta
    # col riferimento pulito (le inserzioni cadono nella zona validation)
    pam4 = stimulus.symbols_from_bits(tx_bits, spec)   # riferimento DSP/ED
    if cfg.err_insert_bits > 0:
        lo = (cfg.training_stop + 300) * bps
        n_ins = cfg.err_insert_bits
        if cfg.err_insert_burst:
            start = int(rng.integers(lo, total_bits - n_ins))
            pos = np.arange(start, start + n_ins)
        elif cfg.err_insert_target in ("msb", "lsb") and bps == 2:
            # una sola lane del simbolo PAM4: il mapper è MSB-first, quindi
            # colonna 0 (posizione pari) = MSB, colonna 1 (dispari) = LSB
            cand = np.arange(lo, total_bits)
            cand = cand[cand % 2 == (0 if cfg.err_insert_target == "msb"
                                     else 1)]
            pos = rng.choice(cand, min(n_ins, len(cand)), replace=False)
        elif cfg.err_insert_target == "rs_symbol":
            # bit raggruppati in simboli GF(2^10) ALLINEATI: a parità di bit
            # inseriti il FEC vede ~n/10 simboli errati invece di ~n — è il
            # confronto didattico fra errori sparsi e errori concentrati
            m = fec_block.GF_M
            n_grp = max(1, -(-n_ins // m))
            starts = rng.choice(np.arange(lo // m + 1, total_bits // m - 1),
                                n_grp, replace=False) * m
            pos = np.concatenate([np.arange(s, s + m)
                                  for s in starts])[:n_ins]
        else:
            pos = rng.choice(np.arange(lo, total_bits), n_ins,
                             replace=False)
        mod_bits = tx_bits.copy()
        mod_bits[pos] ^= 1
        result.err_positions = np.sort(pos)
        pam4_phys = stimulus.symbols_from_bits(mod_bits, spec)
    else:
        pam4_phys = pam4
    result.pam4_symbols = pam4_phys
    result.occupancy = stimulus.level_occupancy(pam4_phys, spec.levels_array)
    _, result.transition_probability = stimulus.transition_matrix(
        pam4_phys, spec.levels_array)
    _register(result, "symbols", pam4_phys, "normalized amplitude", "symbol",
              cfg.symbol_rate_hz, "uscita mapper",
              f"{spec.label}, {cfg.pattern}"
              + (f"/PRBS{cfg.prbs_order}" if cfg.pattern == "prbs" else "")
              + (f" + {cfg.fec_mode.upper()} in-path" if cfg.fec_mode != "none" else ""))
    if (cfg.n_symbols == stimulus.PRBS13_PERIOD and cfg.prbs_order == 13
            and spec.name == "PAM4" and cfg.fec_mode == "none"
            and cfg.pattern == "prbs" and cfg.err_insert_bits == 0):
        _check(result, np.array_equal(np.sort(result.occupancy), [2047, 2048, 2048, 2048]),
               "Occupazione PRBS13Q-style 2047/2048")
    elif cfg.pattern not in ("clock2", "clock8"):
        balance = result.occupancy.min() / max(result.occupancy.max(), 1)
        _check(result, balance > 0.80, "Occupazione dei livelli bilanciata",
               f"min/max={balance:.3f} ({cfg.pattern}, {spec.label}"
               + (f", {cfg.fec_mode}" if cfg.fec_mode != "none" else "") + ")")

    # --- 2. TX elettrico (serializer/PLL con jitter, uscita P/N) ------------
    result.tx = tx_block.run_tx(cfg, pam4_phys, rng=rng)
    _register(result, "tx_ffe_symbols", result.tx.tx_ffe_symbols,
              "normalized amplitude", "symbol", cfg.symbol_rate_hz, "uscita TX FIR")
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

    # --- 3. Canale elettrico: reference plane selezionabile -----------------
    # Single-ended P/N non e una mera visualizzazione: include davvero CM,
    # mismatch e skew del ramo scelto nel segnale che percorre il canale.
    channel_inputs = {
        "differential": result.tx.v_diff_v,
        "single_ended_p": result.tx.vp_v,
        "single_ended_n": result.tx.vn_v,
    }
    result.channel_input_v = channel_inputs[cfg.electrical_drive_mode]
    _register(result, "vp_v", result.tx.vp_v, "V", "electrical",
              cfg.fs_analog_hz, "driver P output")
    _register(result, "vn_v", result.tx.vn_v, "V", "electrical",
              cfg.fs_analog_hz, "driver N output")
    _register(result, "vcm_v", result.tx.vcm_v, "V", "common mode",
              cfg.fs_analog_hz, "driver common-mode")
    _register(result, "channel_input_v", result.channel_input_v, "V",
              "electrical", cfg.fs_analog_hz, "channel input",
              cfg.electrical_drive_mode)
    result.channel = channel_block.run_channel(cfg, result.channel_input_v)
    _register(result, "electrical_waveform_v", result.channel.electrical_waveform_v,
              "V", "electrical", cfg.fs_analog_hz,
              "channel output", result.channel.source)
    _check(result, abs(result.channel.cursor_values[result.channel.cursor_ui == 0][0] - 1) < 1e-9,
           "Main cursor normalizzato")

    # --- 3b. Crosstalk NEXT/FEXT da aggressore (stesso connettore) ----------
    elec_out = result.channel.electrical_waveform_v
    if cfg.xtalk_next_db < 0 or cfg.xtalk_fext_db < 0:
        # aggressore: PRBS indipendente (seed diverso), stesso TX
        aggr_bits = stimulus.prbs_bits(cfg.prbs_order, total_bits,
                                       seed=[1, 0] * (cfg.prbs_order // 2)
                                       + [1] * (cfg.prbs_order % 2))
        aggr_sym = stimulus.symbols_from_bits(aggr_bits, spec)
        aggr_wave = np.repeat(aggr_sym, cfg.analog_sps) * cfg.driver_gain_v_per_unit
        from .utils import apply_frequency_response, butterworth_response
        aggr_wave, _, _ = apply_frequency_response(
            aggr_wave, cfg.fs_analog_hz,
            lambda f: butterworth_response(f, cfg.driver_bw_hz, 3,
                                           causal=cfg.causal_filters))
        xt_total = np.zeros_like(elec_out)
        if cfg.xtalk_next_db < 0:
            # NEXT: accoppiamento capacitivo/induttivo crescente con f (√f)
            xt, _, _ = apply_frequency_response(
                aggr_wave, cfg.fs_analog_hz,
                lambda f: 10 ** (cfg.xtalk_next_db / 20)
                * np.sqrt(np.clip(np.abs(f) / cfg.nyquist_hz, 0, 1)))
            xt_total += xt
        if cfg.xtalk_fext_db < 0:
            # FEXT: accoppiamento ∝ f che viaggia col canale (attenuato)
            xt, _, _ = apply_frequency_response(
                aggr_wave, cfg.fs_analog_hz,
                lambda f: 10 ** (cfg.xtalk_fext_db / 20)
                * np.clip(np.abs(f) / cfg.nyquist_hz, 0, 1)
                * channel_block.channel_response(f, cfg))
            xt_total += xt
        elec_out = elec_out + xt_total
        _register(result, "xtalk_v", xt_total, "V", "electrical",
                  cfg.fs_analog_hz, "aggressore al piano RX/driver",
                  f"NEXT {cfg.xtalk_next_db:g} dB, FEXT {cfg.xtalk_fext_db:g} dB")

    # --- 4-5. Mezzo: catena ottica completa oppure link elettrico puro ------
    if cfg.link_medium == "optical":
        result.optical = optical_block.run_optical(cfg, elec_out, rng=rng)
        alpha = (cfg.chirp_alpha if cfg.optical_modulator == "mzm"
                 else cfg.eml_chirp_alpha)
        _register(result, "E_modulator", result.optical.E_mzm, "sqrt(W)",
                  "optical field", cfg.fs_analog_hz,
                  f"{cfg.optical_modulator.upper()} output", f"alpha={alpha:+.2f}")
        _register(result, "E_fiber", result.optical.E_fiber, "sqrt(W)",
                  "optical field", cfg.fs_analog_hz, "fiber output / PD input",
                  f"{cfg.fiber_km:g} km @ {cfg.wavelength_nm:g} nm")
        budget = result.optical.power_budget_dbm
        _check(result, abs((budget["fiber launch"] - budget["modulator output"])
                           + cfg.coupling_il_db) < 1e-6,
               "Loss campo/potenza coerente")
        result.receiver = receiver_block.run_receiver(
            cfg, result.optical.P_fiber_w, rng)
        _register(result, "i_pd_signal_a", result.receiver.i_pd_signal_a, "A",
                  "photocurrent", cfg.fs_analog_hz, "PD output / TIA input",
                  "before receiver noise")
        _check(result, result.receiver.pd_sat_fraction < 1e-3,
               "Photodiode fuori saturazione",
               f"sat={100 * result.receiver.pd_sat_fraction:.4f}%")
    else:
        # copper (KR/CR/C2M): canale → AFE elettrico, niente ottica
        result.optical = None
        result.receiver = receiver_block.run_receiver_copper(cfg, elec_out, rng)
    _register(result, "v_tia_v", result.receiver.v_tia_v, "V", "electrical",
              cfg.fs_analog_hz,
              "TIA output" if cfg.link_medium == "optical" else "AFE output",
              "includes receiver noise")
    _register(result, "v_agc_v", result.receiver.v_agc_v, "V", "electrical",
              cfg.fs_analog_hz, "AGC output / CTLE input", "DC removed")
    _register(result, "v_ctle_v", result.receiver.v_ctle_v, "V", "electrical",
              cfg.fs_analog_hz, "CTLE output / ADC input")
    _check(result, result.receiver.tia_clip_fraction < 1e-3,
           ("TIA fuori overload" if cfg.link_medium == "optical"
            else "AFE fuori overload"),
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
        # con l'interleaving il gruppo di `depth` codeword è l'unità di
        # linea: la copertura si restringe a gruppi interi
        d_int = cfg.fec_interleave
        if d_int > 1 and covered:
            lo = ((covered[0] + d_int - 1) // d_int) * d_int
            hi = ((covered[-1] + 1) // d_int) * d_int
            covered = list(range(lo, hi))
        if covered:
            decided_full = np.zeros(cfg.n_symbols)
            decided_full[eq.symbol_k_fse] = stimulus.hard_slice(
                eq.dfe_output, spec.levels_array)
            f_lo, f_hi = covered[0], covered[-1] + 1
            sl = slice(f_lo * frame_syms, f_hi * frame_syms)
            decided_bits_cov = stimulus.symbols_to_bits(decided_full[sl], spec)
            tx_bits_cov = result.tx_bits[sl.start * spec.bits_per_symbol:
                                         sl.stop * spec.bits_per_symbol]
            if d_int > 1:
                decided_bits_cov = fec_block.deinterleave_symbols(
                    decided_bits_cov, codec, d_int)
                tx_bits_cov = fec_block.deinterleave_symbols(
                    tx_bits_cov, codec, d_int)
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
    result.snr = metrics_block.snr_report(y_soft, d_soft, result.level_stats,
                                          spec=spec)
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
        eq.dfe_output[eq.validation_fse], truth_val, dfe_stats, spec=spec)
    if result.optical is not None:
        result.optical_levels = metrics_block.optical_level_proxies(
            result.optical.P_fiber_w)

    # --- 9d. Analyzer L2 (pattern eth): delineazione frame e contatori ------
    if cfg.pattern == "eth":
        def _frame_bits(sz):
            return (len(ethernet.PREAMBLE) + len(ethernet.HEADER)
                    + max(sz - len(ethernet.HEADER) - 4, 8) + 4
                    + cfg.l2_ipg_bytes) * 8
        if cfg.l2_streams > 1:
            # multi-stream: l'unità di allineamento è il ROUND (un frame
            # per stream, round-robin) — seq del round = indice del round
            sizes = [(ethernet.STREAM_SIZES[i] or cfg.l2_frame_bytes)
                     for i in range(cfg.l2_streams)]
            flb = sum(_frame_bits(sz) for sz in sizes)
        else:
            flb = _frame_bits(cfg.l2_frame_bytes)          # bit per frame
        if result.fec_link is not None and result.fec_link.post_payload_bits is not None:
            codec = fec_block.FEC_CODECS[cfg.fec_mode]
            stream = result.fec_link.post_payload_bits
            offset = result.fec_frames_covered[0] * codec.k * fec_block.GF_M
            payload_rate = (cfg.symbol_rate_hz * bps) * codec.k / codec.n
        else:
            decided = stimulus.hard_slice(eq.dfe_output, spec.levels_array)
            stream = stimulus.symbols_to_bits(decided, spec)
            offset = int(eq.symbol_k_fse[0]) * bps
            payload_rate = cfg.symbol_rate_hz * bps
        # descrambler self-sync: servono 58 bit di burn-in prima del primo
        # frame che vogliamo delineare
        stream = ethernet.descramble(stream)
        seq0 = int(np.ceil((offset + 58) / flb))
        skip = seq0 * flb - offset
        window = stream[skip:]
        result.l2_window_bits = window[:60000]   # per l'ispettore frame
        result.l2_seq0 = seq0
        if len(window) > flb + 64:
            result.l2 = ethernet.analyze_stream_bits(
                window, cfg.l2_frame_bytes,
                window_s=len(window) / payload_rate, seq0=seq0,
                ipg_bytes=cfg.l2_ipg_bytes, streams=cfg.l2_streams)
            _check(result, result.l2.frames_detected > 0,
                   "Analyzer L2: frame delineati",
                   f"{result.l2.frames_ok} ok / {result.l2.frames_fcs_bad} FCS "
                   f"bad / {result.l2.frames_lost} persi su "
                   f"{result.l2.frames_expected} attesi · "
                   f"throughput {result.l2.throughput_gbps:.2f} Gb/s")

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
    "adc_phase_ui": ("Fase di campionamento ADC [UI]", -0.35, 0.35),
    "pvt_temp_c": ("Temperatura die RX [°C]", -40.0, 125.0),
    "pvt_vdd_pct": ("Supply RX [Δ%]", -10.0, 10.0),
    "rx_ppm_offset": ("Offset clock RX [ppm]", -300.0, 300.0),
    "mzm_bias_rad": ("Bias MZM [rad]", 0.9, 2.2),
}



class ExperimentCancelled(RuntimeError):
    """Esperimento interrotto dal token di cancellazione cooperativo."""


def check_cancel(cancel):
    """Solleva ExperimentCancelled se il token (threading.Event) è settato.

    Le procedure lunghe lo controllano fra una simulate e l'altra: la
    cancellazione è cooperativa, mai a metà di un record."""
    if cancel is not None and cancel.is_set():
        raise ExperimentCancelled("esperimento annullato dall'utente")


def jitter_transfer(cfg: LinkConfig, freqs_mhz=(10, 30, 60, 120, 300, 800),
                    amp_ui=0.04, seed=20240731, progress_callback=None,
                    cancel=None):
    """OJTF misurata del CDR: inietta un PJ piccolo al TX e misura quanto il
    clock recuperato (la traccia di fase del NCO) lo insegue.

    JTF(f) = ampiezza del tono a f nella fase del NCO / ampiezza iniettata.
    Sotto la banda del loop ≈ 0 dB (il CDR insegue), sopra crolla; il picco
    vicino al corner è il jitter peaking del 2° ordine. NON normativa."""
    if cfg.cdr_mode == "oracle":
        raise ValueError("la JTF richiede il CDR reale (gardner/mm)")
    points = []
    for i, f_mhz in enumerate(freqs_mhz):
        check_cancel(cancel)
        r = simulate(cfg.with_updates(tx_pj_amp_ui=float(amp_ui),
                                      tx_pj_freq_mhz=float(f_mhz)),
                     seed=seed, depth="light")
        if r.cdr is None or not r.cdr.locked:
            points.append({"freq_mhz": float(f_mhz), "jtf_db": None,
                           "locked": False})
        else:
            tau = np.asarray(r.cdr.tau_trace_ui, dtype=float)
            tau = tau - np.polyval(np.polyfit(np.arange(len(tau)), tau, 1),
                                   np.arange(len(tau)))
            win = np.hanning(len(tau))
            spec = np.abs(np.fft.rfft(tau * win)) / max(np.sum(win) / 2, 1)
            bin_f = f_mhz * 1e6 / cfg.symbol_rate_hz * len(tau)
            b0 = int(round(bin_f))
            lo, hi = max(b0 - 2, 1), min(b0 + 3, len(spec))
            amp_meas = float(spec[lo:hi].max()) if hi > lo else 0.0
            points.append({
                "freq_mhz": float(f_mhz),
                "jtf_db": float(20 * np.log10(max(amp_meas, 1e-6) / amp_ui)),
                "locked": True,
            })
        if progress_callback:
            progress_callback((i + 1) / len(freqs_mhz))
    return points


def jitter_tolerance(cfg: LinkConfig, freqs_mhz, target_ber=4e-2,
                     amp_max_ui=0.35, iters=6, seed=20240731,
                     progress_callback=None, cancel=None):
    """JTOL-lite (dichiaratamente NON normativa): per ogni frequenza di PJ,
    bisezione sull'ampiezza per trovare la massima con BER ≤ target e link UP.

    Un punto è None se il link fallisce già senza PJ aggiunto."""
    def passes(amp, f_mhz):
        check_cancel(cancel)
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


def stressed_eye_calibrate(cfg: LinkConfig, target_q=3.0, seed=20240731,
                           iters=7, amp_max_ui=0.35, cancel=None):
    """Stressed-eye calibration (DICHIARATA, non normativa): bisezione
    sull'ampiezza del PJ iniettato al TX PLL per portare l'apertura d'occhio
    misurata allo slicer (q_min, unità σ) al target richiesto.

    È il calco del flusso reale "calibra lo stress finché l'occhio al
    reference plane raggiunge il valore prescritto, poi testa il RX in
    quelle condizioni". La ricetta di clause (SJ+RJ+interferenza con
    strumento e maschera prescritti) NON è questa; la ricetta trovata non
    viene applicata al banco — il report la restituisce soltanto."""
    target_q = float(target_q)
    trail = []

    def measure(amp_ui):
        check_cancel(cancel)
        r = simulate(cfg.with_updates(tx_pj_amp_ui=float(amp_ui)),
                     seed=seed, depth="light")
        locked = r.link_up and (r.cdr is None or r.cdr.locked)
        q = (float(r.snr_dfe["q_min"])
             if locked and r.snr_dfe is not None else None)
        trail.append({"pj_amp_ui": float(amp_ui), "q": q,
                      "ber": (float(r.ber_post_dfe) if r.link_up else None),
                      "link_up": bool(r.link_up)})
        return q

    q0 = measure(0.0)
    base = {"target_q": target_q, "pj_freq_mhz": float(cfg.tx_pj_freq_mhz),
            "q_unstressed": q0, "points": trail,
            "metric": ("q_min allo slicer [σ] con PJ al TX PLL — ricetta "
                       "dichiarata, non calibrazione di clause")}
    if q0 is None or q0 <= target_q:
        # l'occhio è già al/sotto il target senza stress aggiunto
        return {**base, "status": "already_below", "recipe": None}
    q_max = measure(amp_max_ui)
    if q_max is not None and q_max > target_q:
        return {**base, "status": "stress_insufficient",
                "recipe": {"tx_pj_amp_ui": float(amp_max_ui), "q": q_max}}
    lo, hi = 0.0, float(amp_max_ui)   # lo: q > target; hi: q ≤ target/no lock
    for _ in range(int(iters)):
        mid = 0.5 * (lo + hi)
        qm = measure(mid)
        if qm is not None and qm > target_q:
            lo = mid
        else:
            hi = mid
    q_lo = measure(lo)                # ricetta conservativa: q appena SOPRA
    return {**base, "status": "ok",
            "recipe": {"tx_pj_amp_ui": float(lo), "q": q_lo,
                       "upper_bound_ui": float(hi)}}


def rx_sensitivity_search(cfg: LinkConfig, target_ber=None, seed=20240731,
                          iters=7, span_db=20.0, cancel=None):
    """BERT RX sensitivity (DICHIARATA, non normativa): bisezione sulla
    potenza ottica lanciata (laser_dbm) per trovare la potenza minima con
    BER contata ≤ target e link UP.

    - target di default: soglia pre-FEC iid del FEC in-path (KP4/KR4);
      senza FEC, 1e-4 dichiarato.
    - la sensitivity è riportata come POTENZA MEDIA al piano "PD input" del
      power budget: NON è la OMA_outer di clause (che prescrive pattern,
      stressed eye calibrato e procedura di misura).
    - il report include i bit necessari a confermare il target a CL95
      (~3/BER, modello iid): è la "durata guidata dalla confidenza".
    Solo mezzo ottico: sul rame una sensitivity in potenza lanciata non è
    definita in questo modello."""
    if cfg.link_medium != "optical":
        raise ValueError(
            "sensitivity search: richiede link_medium=optical (sul rame "
            "l'ampiezza al RX non è una potenza ottica lanciata)")
    if target_ber is None:
        from .blocks import fec as fec_block
        if cfg.fec_mode == "kp4":
            target_ber = fec_block.prefec_ber_threshold(1e-13, n=544, t=15,
                                                        m=10)
        elif cfg.fec_mode == "kr4":
            target_ber = fec_block.prefec_ber_threshold(1e-13, n=528, t=7,
                                                        m=10)
        else:
            target_ber = 1e-4
    target_ber = float(target_ber)

    trail = []

    def measure(launch_dbm):
        check_cancel(cancel)
        r = simulate(cfg.with_updates(laser_dbm=float(launch_dbm)),
                     seed=seed, depth="light")
        ber = float(r.ber_post_dfe) if r.link_up else None
        pd_dbm = (r.optical.power_budget_dbm.get("PD input")
                  if r.optical is not None else None)
        ok = bool(r.link_up and ber is not None and ber <= target_ber)
        trail.append({"launch_dbm": float(launch_dbm), "pd_dbm": pd_dbm,
                      "ber": ber, "link_up": bool(r.link_up), "pass": ok})
        return ok, pd_dbm

    line_rate = cfg.symbol_rate_hz * (2 if cfg.modulation == "PAM4" else 1)
    cl95_bits = 3.0 / target_ber
    base = {
        "target_ber": target_ber,
        "current_launch_dbm": float(cfg.laser_dbm),
        "cl95_bits": cl95_bits,
        "cl95_seconds": cl95_bits / line_rate,
        "metric": ("potenza MEDIA al PD, seed fisso "
                   "(dichiarata: non OMA_outer di clause)"),
    }
    hi = float(cfg.laser_dbm)
    ok_hi, pd_now = measure(hi)
    base["current_pd_dbm"] = pd_now
    if not ok_hi:
        return {**base, "status": "fail_at_current",
                "threshold_launch_dbm": None, "sensitivity_pd_dbm": None,
                "margin_db": None, "points": trail}
    lo = hi - float(span_db)
    ok_lo, _ = measure(lo)
    if ok_lo:
        status, threshold = "capped", lo    # passa anche a fondo scala
    else:
        for _ in range(int(iters)):
            mid = 0.5 * (lo + hi)
            ok_mid, _ = measure(mid)
            if ok_mid:
                hi = mid
            else:
                lo = mid
        status, threshold = "ok", hi
    _, pd_thr = measure(threshold)          # potenza al PD alla soglia
    return {**base, "status": status,
            "threshold_launch_dbm": float(threshold),
            "sensitivity_pd_dbm": pd_thr,
            "margin_db": float(cfg.laser_dbm) - float(threshold),
            "points": trail}


def link_train(cfg: LinkConfig, seeds=(1101, 2202), progress_callback=None,
               verification_seeds=(3303, 4404), cancel=None):
    """Link training didattico: coordinate descent multi-seed su CTLE
    (zero, gain DC) e TX FFE (pre, post). NON è l'AN/LT di clause (nessuno
    scambio di coefficienti col partner): è un tuning locale onesto.

    Ritorna (cfg_ottimizzata, steps, score_iniziale, score_finale) dove lo
    score è la BER media sui seed (0.5 per i record LINK DOWN)."""
    state = {"done": 0}
    plan = [
        ("ctle_zero_hz", "CTLE zero",
         [5e9, 7e9, 9e9, 12e9, 15e9]),
        ("ctle_dc_gain_db", "CTLE gain DC", [-4.0, -2.0, 0.0]),
        ("ffe_pre", "TX FIR pre-cursor", [-0.15, -0.08, -0.02]),
        ("ffe_post", "TX FIR post-cursor", [-0.15, -0.08, -0.02]),
    ]
    total = (sum(len(g) for _, _, g in plan) + 1) * len(seeds)

    def apply(c, field, v):
        if field in ("ffe_pre", "ffe_post"):
            t = list(c.tx_ffe_taps)
            main = len(t) // 2
            t[main - 1 if field == "ffe_pre" else main + 1] = v
            return c.with_updates(tx_ffe_taps=tuple(t))
        if field == "ctle_zero_hz":
            if c.ctle_zeros_hz:
                z = list(c.ctle_zeros_effective_hz)
                upper = 0.95 * z[1] if len(z) > 1 else float("inf")
                z[0] = min(v, upper)
                return c.with_updates(ctle_zeros_hz=tuple(z))
            v = min(v, 0.85 * c.ctle_pole_hz)
        return c.with_updates(**{field: v})

    def score(c):
        check_cancel(cancel)
        tot = 0.0
        for s in seeds:
            r = simulate(c, seed=s, depth="light")
            tot += (r.ber_post_dfe if r.link_up else 0.5)
            state["done"] += 1
            if progress_callback:
                progress_callback(min(state["done"] / total, 1.0))
        return tot / len(seeds)

    cur = cfg
    base = score(cur)
    best_score = base
    steps = []
    for field, label, grid in plan:
        tried = []
        best_v, best_s = None, best_score
        for v in grid:
            cand = apply(cur, field, v)
            s = score(cand)
            tried.append({"value": float(v), "score": s})
            if s < best_s:
                best_s, best_v = s, v
        if best_v is not None:
            cur = apply(cur, field, best_v)
            best_score = best_s
        steps.append({"param": label, "field": field, "tried": tried,
                      "chosen": (float(best_v) if best_v is not None else None),
                      "score_after": best_score})
    # Holdout indipendente: non applicare un tuning che ha semplicemente
    # overfittato i seed usati dal coordinate descent.
    def verify(c):
        vals = []
        for s in verification_seeds:
            r = simulate(c, seed=s, depth="light")
            vals.append(r.ber_post_dfe if r.link_up else 0.5)
        return float(np.mean(vals))

    holdout_before, holdout_after = verify(cfg), verify(cur)
    accepted = holdout_after <= holdout_before + 1e-12
    if not accepted:
        cur, best_score = cfg, base
    if steps:
        steps[-1].update({"verification_before": holdout_before,
                          "verification_after": holdout_after,
                          "accepted": accepted,
                          "verification_seeds": list(verification_seeds)})
    return cur, steps, base, best_score


def anlt_session(cfg: LinkConfig, partner_abilities=None, partner_fec=(),
                 seed=1101, lt_rounds=8, lt_step=0.02, cancel=None):
    """AN/LT: Auto-Negotiation Clause 73 (protocollo) + Link Training con
    handshake dei coefficienti in stile Clause 72/136.

    DICHIARATO — cosa è vero e cosa è modellato:
    - AN: base page, priority resolution, timer e macchina a stati sono
      quelli di clause (sottoinsieme di Table 73-4 fino ad A18); NON c'è la
      segnalazione DME elettrica. Su mezzo ottico l'AN di Clause 73 NON
      esiste (la gestione modulo è CMIS) e la sessione lo dichiara.
    - LT: il protocollo è quello vero (richieste increment/decrement/hold
      per c(-1)/c(0)/c(+1), risposte updated/at_limit, preset iniziale,
      receiver ready), ma la decisione del ricevitore usa la metrica
      MISURATA sul banco (SNR allo slicer da una simulate light), non un
      DFE hardware: è un LT "protocol-shaped" con metrica onesta.
    """
    from .blocks import autoneg as an_block

    local = an_block.local_abilities_from_cfg(cfg)
    local_fec = ("F2",) if cfg.fec_mode != "none" else ()
    if partner_abilities is None:
        partner_abilities = list(local)
    an = an_block.an_session(local, partner_abilities, local_fec,
                             partner_fec or local_fec, seed=seed)
    an["medium_note"] = (
        "link_medium = optical: Clause 73 AN NON esiste sull'ottica "
        "(gestione via CMIS); sessione mostrata a scopo didattico come se "
        "il lane fosse KR/CR." if cfg.link_medium == "optical" else
        "link_medium = copper: contesto KR/CR corretto per Clause 73.")

    # --- LT (PMD control): handshake su un FIR TX a 5 tap ------------------
    # Metrica di training: Q minimo fra gli occhi allo slicer = apertura
    # dell'occhio in unità sigma (per gaussiane BER_occhio ~ Q(q_min)).
    # La metrica esiste SOLO con CDR agganciato: senza lock non c'è occhio.
    def pad5(taps):
        t = list(taps)
        while len(t) < 5:
            t = [0.0] + t + [0.0]
        return tuple(t)

    # preset iniziali stile clause; il training lavora su c(-2)..c(+2):
    # è quello che permette il bring-up dei canali dove 3 tap non bastano
    lt_presets = [
        ("preset 1 (no eq)", (0.0, 0.0, 1.0, 0.0, 0.0)),
        ("preset 2 (post emphasis)", (0.0, -0.10, 1.0, -0.22, 0.0)),
        ("preset 3 (pre+post)", (-0.05, -0.15, 1.0, -0.15, -0.05)),
        ("initialize (hold current)", pad5(cfg.tx_ffe_taps)),
    ]
    frame_us = 23552 / cfg.symbol_rate_hz * 1e6  # ordine di grandezza del
    # training frame PAM4 (frame marker + control channel + payload PRBS13Q)
    lim = 0.35

    def lt_direction(seed_dir, rounds):
        """Una direzione di training (Clause 72/136 è simmetrico: ogni RX
        allena il TX del partner). La direzione inversa usa lo stesso
        canale (dichiarato simmetrico) con rumore indipendente."""
        def lt_metric(c):
            check_cancel(cancel)
            r = simulate(c, seed=seed_dir, depth="light")
            locked = r.link_up and (r.cdr is None or r.cdr.locked)
            if not locked or r.snr_dfe is None:
                return None, r
            return float(r.snr_dfe["q_min"]), r

        frames = []
        t_us = 0.0
        exchange = 0
        rx_notes = []
        cur = best = None
        for name, taps in lt_presets:
            cand = cfg.with_updates(tx_ffe_taps=taps)
            m, _ = lt_metric(cand)
            exchange += 1
            t_us += frame_us * 32
            frames.append({"t_us": t_us, "coeff": "preset", "request": name,
                           "status": ("updated" if m is not None else "no lock"),
                           "taps": list(taps), "q": m})
            if m is not None and (best is None or m > best):
                cur, best = cand, m
        if cur is None:
            # nessun preset aggancia: adattazione RX locale (banda del loop
            # CDR), poi si riprovano i preset — bring-up da ricevitore vero
            for bw in (0.0005, 0.003):
                for name, taps in lt_presets[:3]:
                    cand = cfg.with_updates(cdr_bw=bw, tx_ffe_taps=taps)
                    m, _ = lt_metric(cand)
                    exchange += 1
                    t_us += frame_us * 32
                    if m is not None and (best is None or m > best):
                        cur, best = cand, m
                if cur is not None:
                    rx_notes.append(f"RX adapt: cdr_bw → {bw:g}")
                    frames.append({"t_us": t_us, "coeff": "RX",
                                   "request": f"RX adapt: cdr_bw {bw:g}",
                                   "status": "updated",
                                   "taps": list(cur.tx_ffe_taps), "q": best})
                    break
        if cur is None:
            cur = cfg.with_updates(tx_ffe_taps=lt_presets[0][1])
            best = None

        hold_streak = 0
        main = len(cur.tx_ffe_taps) // 2
        coeff_ids = [i for i in range(len(cur.tx_ffe_taps)) if i != main]
        labels = {i: f"c({i - main:+d})" for i in coeff_ids}
        for _rnd in range(rounds):
            improved_round = False
            for idx in coeff_ids:
                taps = list(cur.tx_ffe_taps)
                cands = []
                for req, delta in (("decrement", -lt_step),
                                   ("increment", lt_step)):
                    v = taps[idx] + delta
                    t2 = list(taps)
                    t2[idx] = v
                    # vincolo di picco stile clause: somma |c_i| limitata;
                    # violarlo produce status = at_limit, non un update
                    if abs(v) > lim or sum(abs(x) for x in t2) > 1.55:
                        cands.append((req, None, None))
                        continue
                    cand = cur.with_updates(tx_ffe_taps=tuple(t2))
                    mm, _ = lt_metric(cand)
                    cands.append((req, cand, mm))
                req, cand, mm = max(
                    cands, key=lambda c2: (-1e9 if c2[2] is None else c2[2]))
                exchange += 1
                t_us += frame_us * 32
                if (cand is not None and mm is not None
                        and (best is None or mm > best + 0.02)):
                    cur, best = cand, mm
                    status = "updated"
                    hold_streak = 0
                    improved_round = True
                else:
                    req = "hold"
                    status = ("at_limit"
                              if all(c2[1] is None for c2 in cands)
                              else "not_updated")
                    hold_streak += 1
                frames.append({"t_us": t_us, "coeff": labels[idx],
                               "request": req, "status": status,
                               "taps": list(cur.tx_ffe_taps), "q": best})
            if hold_streak >= len(coeff_ids):   # un giro intero senza update
                break
            if not improved_round and best is not None:
                # adattazione RX locale: il CTLE ritocca il gain DC mentre
                # il partner tiene fermi i coefficienti (dichiarato: locale)
                for g in (cur.ctle_dc_gain_db - 2.0,
                          cur.ctle_dc_gain_db + 2.0):
                    g = float(np.clip(g, -8.0, 0.0))
                    if abs(g - cur.ctle_dc_gain_db) < 0.5:
                        continue
                    cand = cur.with_updates(ctle_dc_gain_db=g)
                    mm, _ = lt_metric(cand)
                    exchange += 1
                    if mm is not None and mm > best + 0.05:
                        cur, best = cand, mm
                        rx_notes.append(f"RX adapt: CTLE gain → {g:+.1f} dB")
                        frames.append({"t_us": t_us, "coeff": "RX",
                                       "request": f"RX adapt: CTLE {g:+.1f} dB",
                                       "status": "updated",
                                       "taps": list(cur.tx_ffe_taps),
                                       "q": best})
                        break

        m_final, r_final = lt_metric(cur)
        locked_final = m_final is not None
        eye_open = bool(locked_final and m_final > 0.0)
        if locked_final and eye_open:
            frames.append({"t_us": t_us + frame_us * 16, "coeff": "—",
                           "request": "local receiver ready",
                           "status": "ready",
                           "taps": list(cur.tx_ffe_taps), "q": m_final})
        else:
            # niente lock/occhio → link_fail_inhibit_timer e restart AN
            frames.append({"t_us": t_us + frame_us * 16, "coeff": "—",
                           "request": "training failure",
                           "status": "link_fail_inhibit_timer → restart AN",
                           "taps": list(cur.tx_ffe_taps), "q": m_final})
        return {"frames": frames, "q_after": m_final,
                "taps_after": list(cur.tx_ffe_taps),
                "cdr_locked": locked_final, "eye_open": eye_open,
                "rx_notes": rx_notes, "exchanges": exchange,
                "duration_us": frames[-1]["t_us"],
                "ber_after": (r_final.ber_post_dfe if r_final.link_up
                              else float("nan")),
                "ready": bool(locked_final and eye_open),
                "cfg_final": cur}

    fwd = lt_direction(seed, lt_rounds)
    # direzione inversa (il partner allena il NOSTRO ricevitore → il suo TX):
    # canale dichiarato simmetrico, rumore indipendente, meno round
    rev = lt_direction(seed + 7777, min(lt_rounds, 1))
    cur = fwd.pop("cfg_final")
    rev.pop("cfg_final")
    rev.pop("frames")               # nel report basta il riassunto

    # HOLDOUT su seed indipendente: il training su un solo seed può
    # overfittare (osservato: preset 2 vinceva al seed di training e
    # peggiorava la BER vera del profilo). Come un PHY reale che dopo il
    # training ri-verifica il frame lock, i coefficienti si accettano solo
    # se sul seed di verifica non peggiorano la configurazione di partenza.
    def q_holdout(c):
        r = simulate(c, seed=seed + 31337, depth="light")
        locked = r.link_up and (r.cdr is None or r.cdr.locked)
        return (float(r.snr_dfe["q_min"])
                if locked and r.snr_dfe is not None else None)
    q_new = q_holdout(cur)
    q_old = q_holdout(cfg)
    holdout_ok = (q_new is not None
                  and (q_old is None or q_new >= q_old - 0.1))
    if not holdout_ok:
        cur = cfg                    # si tengono i valori correnti
    holdout = {"accepted": bool(holdout_ok),
               "q_trained": q_new, "q_current": q_old,
               "verify_seed_note": "seed indipendente dal training"}

    lt = {"metric": "q_min (apertura occhio, unità σ)",
          "holdout": holdout,
          "q_preset": fwd["frames"][0]["q"],
          "taps_before": list(fwd["frames"][0]["taps"]),
          **fwd,
          "reverse": rev,
          "both_ready": bool(fwd["ready"] and rev["ready"]),
          "link_up_after": bool(fwd["cdr_locked"])}
    return {"an": an, "lt": lt, "cfg_after": cur}


def l2_ont_report(cfg: LinkConfig, ipg_grid=(12, 96, 384, 1024, 2000),
                  seed=73101, cancel=None):
    """Test L2 in stile ONT (Viavi/EXFO): load ramp via IPG, latency budget
    deterministico e service-disruption proxy dal lock del CDR.

    DICHIARATO: non c'è un DUT di rete — la perdita di frame viene dai bit
    error del PHY, non da congestione/coda; la latenza è un BUDGET calcolato
    dai blocchi (serializzazione, FEC store&forward, fibra, DSP), non una
    misura round-trip con timestamp nel payload."""
    bps = 2 if cfg.modulation == "PAM4" else 1
    line_gbps = cfg.symbol_rate_hz * bps / 1e9

    # --- load ramp: IPG grande = offered load piccolo ----------------------
    ramp = []
    for ipg in ipg_grid:
        check_cancel(cancel)
        c = cfg.with_updates(pattern="eth", l2_ipg_bytes=int(ipg))
        r = simulate(c, seed=seed + int(ipg), depth="light")
        l2 = r.l2
        wire = (8 + len(ethernet.HEADER)
                + max(cfg.l2_frame_bytes - len(ethernet.HEADER) - 4, 8) + 4)
        offered_pct = 100.0 * wire / (wire + ipg)
        ramp.append({
            "ipg_bytes": int(ipg), "offered_pct": offered_pct,
            "link_up": bool(r.link_up),
            "frames_ok": (l2.frames_ok if l2 else 0),
            "frames_lost": (l2.frames_lost if l2 else 0),
            "loss_pct": (100 * l2.frames_lost / max(l2.frames_expected, 1)
                         if l2 else float("nan")),
            "goodput_gbps": (l2.throughput_gbps if l2 else float("nan")),
        })

    # --- latency budget (one-way, deterministico) --------------------------
    r0 = simulate(cfg.with_updates(pattern="eth"), seed=seed, depth="light")
    frame_bits = (8 + len(ethernet.HEADER)
                  + max(cfg.l2_frame_bytes - len(ethernet.HEADER) - 4, 8)
                  + 4) * 8
    items = [("serializzazione frame",
              frame_bits / (line_gbps * 1e9) * 1e9,
              f"{frame_bits} bit a {line_gbps:.0f} Gb/s")]
    if cfg.fec_mode != "none":
        codec = fec_block.FEC_CODECS[cfg.fec_mode]
        fec_ns = 2 * codec.n * fec_block.GF_M / (line_gbps * 1e9) * 1e9
        items.append(("FEC store&forward (enc+dec)", fec_ns,
                      f"2 × {codec.n * fec_block.GF_M} bit "
                      f"RS({codec.n},{codec.k})"))
    if cfg.link_medium == "optical" and cfg.fiber_km > 0:
        items.append(("propagazione fibra", cfg.fiber_km * 4890.0,
                      f"{cfg.fiber_km:g} km × 4.89 µs/km (n_g≈1.468)"))
    ui_ns = 1.0 / cfg.symbol_rate_hz * 1e9
    dsp_ns = (cfg.fse_taps / 2 + cfg.dfe_taps) * ui_ns
    items.append(("pipeline DSP (FSE+DFE)", dsp_ns,
                  f"{cfg.fse_taps} tap T/2 + {cfg.dfe_taps} tap DFE"))
    budget = [{"item": n, "ns": v, "detail": d} for n, v, d in items]
    total_ns = float(sum(b["ns"] for b in budget))

    # --- latenza MISURATA: ritardo di gruppo end-to-end via correlazione ---
    # fra il drive TX e l'uscita CTLE (dove la fisica analogica è tutta
    # attraversata). DICHIARATO: la pipeline DIGITALE del banco (FSE/DFE/
    # FEC) è istantanea nel simulatore — la sua latenza resta da budget.
    x = np.asarray(r0.channel_input_v, dtype=float)
    yv = np.asarray(r0.receiver.v_ctle_v, dtype=float)
    n_x = min(len(x), len(yv), 60000)
    xd = x[:n_x] - x[:n_x].mean()
    yd = yv[:n_x] - yv[:n_x].mean()
    corr = np.correlate(yd, xd[: n_x // 2], mode="valid")
    lag_samples = int(np.argmax(np.abs(corr)))
    latency_meas_ns = lag_samples / cfg.fs_analog_hz * 1e9

    # --- service disruption proxy: tempo di lock del CDR -------------------
    lock_us = None
    if (r0.cdr is not None and getattr(r0.cdr, "lock_symbol", None)
            is not None):
        lock_us = r0.cdr.lock_symbol / cfg.symbol_rate_hz * 1e6
    return {"ramp": ramp, "latency_budget": budget, "latency_total_ns":
            total_ns, "latency_measured_analog_ns": float(latency_meas_ns),
            "cdr_lock_us": lock_us,
            "line_rate_gbps": line_gbps,
            "frame_bytes": cfg.l2_frame_bytes}


def acquisition_batch(cfg: LinkConfig, seeds=(500283, 500354, 500401)):
    """Batch di acquisizione CONGELATA per seed: stessa config, seed
    dichiarati, metriche deterministiche per record. È l'ancora di
    regressione del banco (il collaudo "freeze" della roadmap): ogni
    modifica al motore che cambia questi numeri deve dichiararlo."""
    from .blocks.jitter import tie_analysis
    rows = []
    for sd in seeds:
        r = simulate(cfg, seed=int(sd), depth="light")
        row = {"seed": int(sd), "link_up": bool(r.link_up)}
        if r.link_up:
            t = tie_analysis(r.receiver.v_ctle_v, cfg.analog_sps,
                             cfg.symbol_rate_hz, delay_ui=r.rx_delay_ui)
            row.update({
                "ber": float(r.ber_post_dfe),
                "q_min": float(r.snr_dfe["q_min"]),
                "snr_db": float(r.snr_dfe["snr_slicer_db"]),
                "tie_rms_ps": float(t.tie_rms_ui * 1e12
                                    / cfg.symbol_rate_hz),
            })
        rows.append(row)
    return rows


def traffic_sweep(cfg: LinkConfig, frame_sizes=(64, 128, 256, 512, 1024),
                  seed=73001, cancel=None):
    """Benchmark L2/PHY sulla frame size, ispirato al workflow di un traffic
    analyzer ma deliberatamente NON chiamato RFC 2544.

    Ogni punto attraversa davvero L2 -> FEC opzionale -> PHY -> ED/FEC -> L2.
    Non essendoci un DUT packet-switching non esistono forwarding latency,
    multi-stream, QoS o una ricerca normativa del throughput.
    """
    rows = []
    for size in frame_sizes:
        check_cancel(cancel)
        size = int(size)
        if not 64 <= size <= 1024:
            raise ValueError("frame size fuori range [64, 1024] B")
        run_cfg = cfg.with_updates(pattern="eth", l2_frame_bytes=size)
        r = simulate(run_cfg, seed=seed + size, depth="light")
        l2 = r.l2
        rows.append({
            "frame_bytes": size,
            "link_up": bool(r.link_up),
            "frames_expected": (l2.frames_expected if l2 else 0),
            "frames_detected": (l2.frames_detected if l2 else 0),
            "frames_ok": (l2.frames_ok if l2 else 0),
            "frames_fcs_bad": (l2.frames_fcs_bad if l2 else 0),
            "frames_lost": (l2.frames_lost if l2 else 0),
            "loss_pct": (100 * l2.frames_lost / max(l2.frames_expected, 1)
                         if l2 else float("nan")),
            "throughput_gbps": (l2.throughput_gbps if l2 else float("nan")),
            "line_rate_gbps": (l2.line_rate_gbps if l2 else float("nan")),
            "payload_efficiency_pct": (
                100 * l2.throughput_gbps / max(l2.line_rate_gbps, 1e-30)
                if l2 else float("nan")),
            "ber": (r.ber_post_dfe if r.link_up else float("nan")),
        })
    return rows


def sweep(cfg: LinkConfig, field_name: str, values, seed=20240731,
          progress_callback=None, cancel=None):
    """Ripete la simulazione light variando un solo parametro effettivo.

    ``ctle_zero_hz`` è il nome pubblico storico dello sweep. Se è attiva una
    topologia multi-sezione, deve muovere il primo zero della lista realmente
    consumata dal datapath, non il campo legacy inattivo.
    """
    if field_name not in SWEEPABLE_FIELDS:
        raise ValueError(f"campo non sweepable: {field_name}")
    rows = []
    for i, v in enumerate(values):
        check_cancel(cancel)
        v_cast = int(v) if field_name == "adc_bits" else float(v)
        if field_name == "ctle_zero_hz" and cfg.ctle_zeros_hz:
            zeros = list(cfg.ctle_zeros_effective_hz)
            upper = 0.95 * zeros[1] if len(zeros) > 1 else float("inf")
            zeros[0] = min(v_cast, upper)
            c = cfg.with_updates(ctle_zeros_hz=tuple(zeros))
        else:
            c = cfg.with_updates(**{field_name: v_cast})
        r = simulate(c, seed=seed, depth="light")
        rows.append({
            field_name: v_cast,
            # Il valore richiesto puo essere limitato o tradotto nel
            # parametro realmente consumato dal datapath (oggi accade per
            # il primo zero delle topologie CTLE multi-sezione). Esporlo
            # impedisce che GUI e optimizer dichiarino uno sweep fantasma.
            "effective_value": (c.ctle_zeros_effective_hz[0]
                                if field_name == "ctle_zero_hz" else
                                getattr(c, field_name)),
            "link_up": r.link_up,
            "BER_pre_EQ": r.ber_pre_eq,
            "BER_FSE": r.ber_post_fse,
            "BER_FSE_DFE": r.ber_post_dfe,
            "GMI_bit_per_simbolo": (r.gmi_total if r.link_up else float("nan")),
            "P_PD_dBm": (r.optical.power_budget_dbm["PD input"]
                         if r.optical is not None else float("nan")),
            "FER_RS544_iid": r.fec.fer_iid_model_qmeas if r.fec else float("nan"),
            "val_bits": (r.metrics_rows[2]["bits"] if r.link_up else 0),
            "checks_fail": sum(1 for ck in r.checks if ck["status"] == "FAIL"),
        })
        if progress_callback:
            progress_callback((i + 1) / len(values))
    return rows
