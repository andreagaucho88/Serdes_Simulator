"""DSP del ricevitore: acquisition di ritardo/fase dai campioni ADC,
S-curve Gardner e Mueller–Müller, loop Gardner first-order,
baseline 1 sps, FSE NLMS a 2 sps, DFE con demo di error propagation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..utils import affine_fit
from .stimulus import GRAY_LEVELS, PAM4_GRAY, hard_slice


def sample_adc_at_ui(adc_samples, nominal_time_ui, query_time_ui):
    return np.interp(query_time_ui, nominal_time_ui, adc_samples)


# ---------------------------------------------------------------------------
# Acquisition: ritardo intero + fase frazionaria (MSE con fit affine su training)
# ---------------------------------------------------------------------------

@dataclass
class TimingResult:
    phase_grid_ui: np.ndarray
    integer_delay_grid_ui: np.ndarray
    delay_phase_mse: np.ndarray
    rx_integer_delay_ui: int
    best_phase_ui: float
    phase_mse: np.ndarray            # riga MSE al ritardo migliore
    # S-curve (solo depth full)
    gardner_scurve: np.ndarray | None = None
    mm_scurve: np.ndarray | None = None
    ted_slope: float | None = None
    loop_phase_trace_ui: np.ndarray | None = None
    loop_ted_trace: np.ndarray | None = None
    gardner_locked: bool | None = None   # loop coerente con l'acquisition?

    @property
    def gardner_offset_ui(self) -> float:
        """Offset fra il punto di lock del Gardner e la fase dell'acquisition."""
        if self.loop_phase_trace_ui is None:
            return float("nan")
        tail = self.loop_phase_trace_ui[-max(len(self.loop_phase_trace_ui) // 4, 50):]
        return float(np.mean(tail) - self.best_phase_ui)

    @property
    def lock_label(self) -> str:
        if self.gardner_locked is None:
            return "acquisition supervisionata (loop non eseguito)"
        if self.gardner_locked:
            return (f"Gardner LOCKED (offset {self.gardner_offset_ui:+.3f} UI "
                    "dalla fase di acquisition)")
        return "Gardner UNLOCKED (non assestato o al rail)"


def acquire_timing(cfg, adc_samples_v, adc_nominal_time_ui, pam4_symbols,
                   n_phases=121) -> TimingResult:
    phase_grid_ui = np.linspace(-0.45, 0.45, n_phases)
    integer_delay_grid_ui = np.arange(-3, 6)
    k_train = np.arange(cfg.training_start, cfg.training_stop)
    truth_train = pam4_symbols[k_train]

    mse = np.empty((len(integer_delay_grid_ui), len(phase_grid_ui)))
    for row, delay_ui in enumerate(integer_delay_grid_ui):
        for col, phase_ui in enumerate(phase_grid_ui):
            y = sample_adc_at_ui(adc_samples_v, adc_nominal_time_ui,
                                 k_train + 0.5 + delay_ui + phase_ui)
            gain, offset = affine_fit(truth_train, y)
            mse[row, col] = np.mean((y - (gain * truth_train + offset)) ** 2)

    best_row, best_col = np.unravel_index(np.argmin(mse), mse.shape)
    return TimingResult(
        phase_grid_ui=phase_grid_ui,
        integer_delay_grid_ui=integer_delay_grid_ui,
        delay_phase_mse=mse,
        rx_integer_delay_ui=int(integer_delay_grid_ui[best_row]),
        best_phase_ui=float(phase_grid_ui[best_col]),
        phase_mse=mse[best_row],
    )


def compute_scurves(cfg, adc_samples_v, adc_nominal_time_ui, pam4_symbols,
                    timing: TimingResult, levels=GRAY_LEVELS):
    """S-curve medie Gardner e Mueller–Müller sull'intera griglia di fase."""
    k_ted = np.arange(300, cfg.n_symbols - 300)
    delay = timing.rx_integer_delay_ui
    gardner_mean, mm_mean = [], []
    for phase_ui in timing.phase_grid_ui:
        early = sample_adc_at_ui(adc_samples_v, adc_nominal_time_ui, k_ted + delay + phase_ui)
        mid = sample_adc_at_ui(adc_samples_v, adc_nominal_time_ui, k_ted + delay + 0.5 + phase_ui)
        late = sample_adc_at_ui(adc_samples_v, adc_nominal_time_ui, k_ted + delay + 1.0 + phase_ui)
        gardner_mean.append(np.mean((late - early) * mid))

        gain, offset = affine_fit(pam4_symbols[k_ted], mid)
        y_norm = (mid - offset) / gain
        decisions = hard_slice(y_norm, levels)
        mm_error = decisions[:-1] * y_norm[1:] - decisions[1:] * y_norm[:-1]
        mm_mean.append(np.mean(mm_error))

    timing.gardner_scurve = np.asarray(gardner_mean)
    timing.mm_scurve = np.asarray(mm_mean)

    local = np.abs(timing.phase_grid_ui - timing.best_phase_ui) < 0.08
    timing.ted_slope = float(np.polyfit(timing.phase_grid_ui[local],
                                        timing.gardner_scurve[local], 1)[0])


def run_gardner_loop(cfg, adc_samples_v, adc_nominal_time_ui, timing: TimingResult,
                     max_symbols=4000):
    """Loop Gardner first-order didattico (TED → gain → fase)."""
    ted_slope = timing.ted_slope if timing.ted_slope else 1e-9
    loop_mu = 0.018 / max(abs(ted_slope), 1e-9)
    phase_estimate_ui = timing.best_phase_ui
    delay = timing.rx_integer_delay_ui
    phase_trace, ted_trace = [], []
    k_stop = min(cfg.n_symbols - 350, 350 + max_symbols)
    for k in range(350, k_stop):
        base = k + delay + phase_estimate_ui
        early, middle, late = np.interp(
            [base, base + 0.5, base + 1.0],
            adc_nominal_time_ui,
            adc_samples_v,
        )
        ted = (late - early) * middle
        phase_estimate_ui -= np.sign(ted_slope) * loop_mu * ted
        phase_estimate_ui = float(np.clip(phase_estimate_ui, -0.35, 0.35))
        phase_trace.append(phase_estimate_ui)
        ted_trace.append(ted)
    timing.loop_phase_trace_ui = np.asarray(phase_trace)
    timing.loop_ted_trace = np.asarray(ted_trace)
    # lock: il loop deve ASSESTARSI (bassa varianza della coda) lontano dai
    # rail di clip (±0.35 UI). Nota: il Gardner aggancia sullo zero della SUA
    # S-curve, che in generale NON coincide col minimo MSE dell'acquisition —
    # l'offset fra i due è riportato ed è un'osservabile didattica.
    tail = timing.loop_phase_trace_ui[-max(len(phase_trace) // 4, 50):]
    # soglia 0.08 UI: sopra il self-noise tipico di un TED first-order (~0.05)
    settled = float(np.std(tail)) < 0.08
    railed = float(np.mean(np.abs(np.abs(tail) - 0.35) < 1e-3)) > 0.5
    timing.gardner_locked = bool(settled and not railed)


# ---------------------------------------------------------------------------
# Baseline 1 sps + FSE NLMS + DFE
# ---------------------------------------------------------------------------

@dataclass
class EqualizerResult:
    symbol_k: np.ndarray
    rx_baud_norm: np.ndarray
    truth_baud: np.ndarray
    validation_baud: np.ndarray      # maschera
    rx_gain: float
    rx_offset: float
    # FSE
    symbol_k_fse: np.ndarray
    fse_taps_w: np.ndarray
    fse_learning_error: np.ndarray
    fse_output: np.ndarray
    d_fse: np.ndarray
    train_fse: np.ndarray            # maschera
    validation_fse: np.ndarray       # maschera
    # DFE
    dfe_coeff: np.ndarray
    dfe_output: np.ndarray
    dfe_decisions: np.ndarray
    # error propagation demo (solo full)
    inject_at: int | None = None
    dfe_forced: np.ndarray | None = None
    propagation_span: np.ndarray | None = None
    # adaptation DD-LMS demo (solo full)
    dfe_dd_output: np.ndarray | None = None
    dfe_tap_trace: np.ndarray | None = None


def nlms_train(X, desired, mu=0.18, epochs=3, epsilon=1e-6):
    w = np.zeros(X.shape[1])
    w[X.shape[1] // 2] = 1.0
    errors = []
    for _ in range(epochs):
        for u, d in zip(X, desired):
            e = d - np.dot(w, u)
            w += mu * e * u / (epsilon + np.dot(u, u))
            errors.append(e)
    return w, np.asarray(errors)


def run_dfe(samples, coeff, initial_truth, force_wrong_at=None, levels=None):
    out = np.zeros_like(samples)
    decisions = np.zeros_like(samples)
    history = list(initial_truth[-len(coeff):])
    ncoef = len(coeff)
    levels = GRAY_LEVELS if levels is None else np.asarray(levels)
    for j, value in enumerate(samples):
        correction = np.dot(coeff, np.asarray(history[-ncoef:][::-1]))
        z = value - correction
        decision = float(levels[int(np.argmin(np.abs(z - levels)))])
        if force_wrong_at is not None and j == force_wrong_at:
            alternatives = levels[levels != decision]
            decision = float(alternatives[np.argmin(np.abs(alternatives - decision))])
        out[j] = z
        decisions[j] = decision
        history.append(decision)
    return out, decisions


def dfe_dd_lms(samples, truth, train_mask, n_taps, levels, mu=0.01):
    """DFE adattato con LMS: supervisionato sul training, poi decision-directed.

    Ritorna (uscita, traiettoria dei tap sottocampionata ogni 16 simboli).
    Dimostra l'adaptation continua (contro la stima one-shot ai minimi quadrati)
    e il rischio del decision-directed: i tap inseguono le decisioni, giuste o no.
    """
    samples = np.asarray(samples)
    levels = np.asarray(levels)
    b = np.zeros(n_taps)
    history = list(levels[[0] * n_taps])
    out = np.zeros_like(samples)
    trace = []
    for j, value in enumerate(samples):
        h = np.asarray(history[-n_taps:][::-1])
        z = value - np.dot(b, h)
        out[j] = z
        decision = float(levels[int(np.argmin(np.abs(z - levels)))])
        reference = float(truth[j]) if train_mask[j] else decision
        error = z - reference
        b += mu * error * h
        history.append(reference)
        if j % 16 == 0:
            trace.append(b.copy())
    return out, np.asarray(trace)


def run_equalizers_timed(cfg, adc_samples_v, pos_data_samples, pattern_lag,
                         pam4_symbols, spec=PAM4_GRAY,
                         full_depth=False) -> EqualizerResult:
    """Equalizzazione con gli istanti decisi dal CDR (nessun oracle).

    pos_data_samples[k_rx] è la posizione frazionaria (in campioni ADC)
    dell'istante dati del simbolo RX k_rx; pattern_lag mappa k_tx = k_rx + lag
    (dal pattern lock stile BERT). Le maschere di training/validation usano
    gli indici TX, come nel percorso oracle."""
    levels = spec.levels_array
    adc = np.asarray(adc_samples_v, dtype=float)
    pos = np.asarray(pos_data_samples, dtype=float)
    grid = np.arange(len(adc), dtype=float)

    k_rx = np.arange(len(pos))
    k_tx = k_rx + pattern_lag
    ok = (k_tx >= 0) & (k_tx < cfg.n_symbols)
    k_rx, k_tx, pos = k_rx[ok], k_tx[ok], pos[ok]

    # --- baseline 1 sps agli istanti CDR ------------------------------------
    rx_baud_v = np.interp(pos, grid, adc)
    train_mask = (k_tx >= cfg.training_start) & (k_tx < cfg.training_stop)
    if train_mask.sum() < 200:
        raise ValueError("training insufficiente dopo il pattern lock")
    rx_gain, rx_offset = affine_fit(pam4_symbols[k_tx[train_mask]],
                                    rx_baud_v[train_mask])
    rx_baud_norm = (rx_baud_v - rx_offset) / rx_gain
    truth_baud = pam4_symbols[k_tx]
    validation_baud = k_tx >= cfg.training_stop + 200

    # --- FSE a 2 sps con tap a 0.5 UI attorno all'istante CDR ---------------
    FSE_TAPS = cfg.fse_taps | 1
    FSE_HALF = FSE_TAPS // 2
    step = cfg.adc_sps / 2.0  # 0.5 UI in campioni ADC
    offs = (np.arange(FSE_TAPS) - FSE_HALF)[::-1] * step
    valid_fse = (pos + offs.min() >= 0) & (pos + offs.max() < len(adc) - 1)
    k_tx_f, pos_f = k_tx[valid_fse], pos[valid_fse]
    X_fse = np.interp((pos_f[:, None] + offs[None, :]).ravel(), grid,
                      adc).reshape(len(pos_f), FSE_TAPS)
    d_fse = pam4_symbols[k_tx_f]
    train_fse = (k_tx_f >= cfg.training_start) & (k_tx_f < cfg.training_stop)

    fse_taps_w, fse_learning_error = nlms_train(X_fse[train_fse], d_fse[train_fse])
    fse_output = X_fse @ fse_taps_w
    fse_gain, fse_offset = affine_fit(d_fse[train_fse], fse_output[train_fse])
    fse_output = (fse_output - fse_offset) / fse_gain
    validation_fse = k_tx_f >= cfg.training_stop + 200

    # --- DFE ----------------------------------------------------------------
    DFE_TAPS = cfg.dfe_taps
    train_idx = np.flatnonzero(train_fse)
    rows, residuals = [], []
    for j in train_idx:
        if j < DFE_TAPS:
            continue
        rows.append(d_fse[j - DFE_TAPS:j][::-1])
        residuals.append(fse_output[j] - d_fse[j])
    dfe_coeff = np.linalg.lstsq(np.asarray(rows), np.asarray(residuals),
                                rcond=None)[0]
    lo = k_tx_f[0] - DFE_TAPS
    initial_truth = (pam4_symbols[lo:k_tx_f[0]] if lo >= 0
                     else np.zeros(DFE_TAPS))
    dfe_output, dfe_decisions = run_dfe(fse_output, dfe_coeff, initial_truth,
                                        levels=levels)

    result = EqualizerResult(
        symbol_k=k_tx, rx_baud_norm=rx_baud_norm, truth_baud=truth_baud,
        validation_baud=validation_baud, rx_gain=rx_gain, rx_offset=rx_offset,
        symbol_k_fse=k_tx_f, fse_taps_w=fse_taps_w,
        fse_learning_error=fse_learning_error, fse_output=fse_output,
        d_fse=d_fse, train_fse=train_fse, validation_fse=validation_fse,
        dfe_coeff=dfe_coeff, dfe_output=dfe_output, dfe_decisions=dfe_decisions,
    )
    if full_depth:
        inject_at = min(4100, len(fse_output) - 200)
        dfe_forced, _ = run_dfe(fse_output, dfe_coeff, initial_truth,
                                force_wrong_at=inject_at, levels=levels)
        result.inject_at = inject_at
        result.dfe_forced = dfe_forced
        result.propagation_span = np.flatnonzero(
            np.abs(dfe_forced - dfe_output) > 1e-9)
        dd_out, tap_trace = dfe_dd_lms(fse_output, d_fse, train_fse,
                                       DFE_TAPS, levels)
        result.dfe_dd_output = dd_out
        result.dfe_tap_trace = tap_trace
    return result


def run_equalizers(cfg, adc_samples_v, adc_nominal_time_ui, pam4_symbols,
                   timing: TimingResult, full_depth=False,
                   spec=PAM4_GRAY) -> EqualizerResult:
    delay = timing.rx_integer_delay_ui
    phase = timing.best_phase_ui
    levels = spec.levels_array

    # --- baseline 1 sps -----------------------------------------------------
    symbol_k = np.arange(30, cfg.n_symbols - 30)
    rx_baud_v = sample_adc_at_ui(adc_samples_v, adc_nominal_time_ui,
                                 symbol_k + delay + 0.5 + phase)
    train_mask = (symbol_k >= cfg.training_start) & (symbol_k < cfg.training_stop)
    rx_gain, rx_offset = affine_fit(pam4_symbols[symbol_k[train_mask]],
                                    rx_baud_v[train_mask])
    rx_baud_norm = (rx_baud_v - rx_offset) / rx_gain
    truth_baud = pam4_symbols[symbol_k]
    validation_baud = symbol_k >= cfg.training_stop + 200

    # --- FSE NLMS a 2 sps ---------------------------------------------------
    FSE_TAPS = cfg.fse_taps | 1  # la finestra è simmetrica: forza dispari
    FSE_HALF = FSE_TAPS // 2
    center_adc_n = np.rint((symbol_k + delay + 0.5 + phase - cfg.adc_phase_ui)
                           * cfg.adc_sps).astype(int)
    valid_fse = (center_adc_n - FSE_HALF >= 0) & (center_adc_n + FSE_HALF < len(adc_samples_v))
    symbol_k_fse = symbol_k[valid_fse]
    center_adc_n = center_adc_n[valid_fse]
    idx = center_adc_n[:, None] + np.arange(FSE_HALF, -FSE_HALF - 1, -1)[None, :]
    X_fse = adc_samples_v[idx]
    d_fse = pam4_symbols[symbol_k_fse]
    train_fse = (symbol_k_fse >= cfg.training_start) & (symbol_k_fse < cfg.training_stop)

    fse_taps_w, fse_learning_error = nlms_train(X_fse[train_fse], d_fse[train_fse])
    fse_output = X_fse @ fse_taps_w
    fse_gain, fse_offset = affine_fit(d_fse[train_fse], fse_output[train_fse])
    fse_output = (fse_output - fse_offset) / fse_gain
    validation_fse = symbol_k_fse >= cfg.training_stop + 200

    # --- DFE ----------------------------------------------------------------
    DFE_TAPS = cfg.dfe_taps
    train_idx = np.flatnonzero(train_fse)
    rows, residuals = [], []
    for j in train_idx:
        if j < DFE_TAPS:
            continue
        rows.append(d_fse[j - DFE_TAPS:j][::-1])
        residuals.append(fse_output[j] - d_fse[j])
    dfe_coeff = np.linalg.lstsq(np.asarray(rows), np.asarray(residuals), rcond=None)[0]

    initial_truth = pam4_symbols[symbol_k_fse[0] - DFE_TAPS:symbol_k_fse[0]]
    dfe_output, dfe_decisions = run_dfe(fse_output, dfe_coeff, initial_truth,
                                        levels=levels)

    result = EqualizerResult(
        symbol_k=symbol_k, rx_baud_norm=rx_baud_norm, truth_baud=truth_baud,
        validation_baud=validation_baud, rx_gain=rx_gain, rx_offset=rx_offset,
        symbol_k_fse=symbol_k_fse, fse_taps_w=fse_taps_w,
        fse_learning_error=fse_learning_error, fse_output=fse_output,
        d_fse=d_fse, train_fse=train_fse, validation_fse=validation_fse,
        dfe_coeff=dfe_coeff, dfe_output=dfe_output, dfe_decisions=dfe_decisions,
    )

    if full_depth:
        inject_at = min(4100, len(fse_output) - 200)
        dfe_forced, _ = run_dfe(fse_output, dfe_coeff, initial_truth,
                                force_wrong_at=inject_at, levels=levels)
        result.inject_at = inject_at
        result.dfe_forced = dfe_forced
        result.propagation_span = np.flatnonzero(np.abs(dfe_forced - dfe_output) > 1e-9)

        dd_out, tap_trace = dfe_dd_lms(fse_output, d_fse, train_fse,
                                       DFE_TAPS, levels)
        result.dfe_dd_output = dd_out
        result.dfe_tap_trace = tap_trace

    return result
