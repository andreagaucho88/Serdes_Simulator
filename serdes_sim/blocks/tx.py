"""Trasmettitore elettrico: TX FFE, DAC (ZOH/quantizzazione/banda), driver."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import signal

from ..utils import apply_frequency_response, butterworth_response, quantize_bipolar


@dataclass
class TxResult:
    tx_ffe_symbols: np.ndarray      # ampiezza normalizzata, 1 sps
    swing_cost: float               # rapporto di picco FFE/PAM4
    ffe_freq_norm: np.ndarray       # f/Nyquist per la risposta FFE
    ffe_response: np.ndarray        # H(f) complesso del FFE
    dac_zoh: np.ndarray             # zero-order hold, analog sps
    dac_quantized: np.ndarray
    dac_waveform: np.ndarray        # dopo banda DAC
    dac_lsb: float
    dac_clip_fraction: float
    driver_filtered_v: np.ndarray   # prima delle rail
    driver_voltage_v: np.ndarray    # uscita driver ideale differenziale [V]
    driver_clip_fraction: float
    tx_tie_ui: np.ndarray | None = None  # jitter iniettato dal clock TX [UI/simbolo]
    # coppia differenziale P/N (v. run_differential)
    vp_v: np.ndarray | None = None
    vn_v: np.ndarray | None = None
    vcm_v: np.ndarray | None = None
    v_diff_v: np.ndarray | None = None   # ciò che il canale vede davvero


def tx_clock_tie_ui(cfg, rng):
    """TIE del clock TX (PLL/serializer) per simbolo: RJ + PJ + DCD.

    Modello dichiarato: il time base del DAC viene modulato con un offset
    costante per UI (edge jitter), non un phase noise a PSD completa."""
    k = np.arange(cfg.n_symbols)
    tie = np.zeros(cfg.n_symbols)
    if cfg.tx_rj_rms_fs > 0:
        tie += rng.normal(0, cfg.tx_rj_rms_fs * 1e-15 / cfg.ui_s, cfg.n_symbols)
    if cfg.tx_pj_amp_ui > 0:
        f_norm = cfg.tx_pj_freq_mhz * 1e6 / cfg.symbol_rate_hz  # cicli per UI
        tie += cfg.tx_pj_amp_ui * np.sin(2 * np.pi * f_norm * k)
    if cfg.tx_dcd_pct > 0:
        tie += (cfg.tx_dcd_pct / 100 / 2) * np.where(k % 2 == 0, 1.0, -1.0)
    return tie


def run_tx(cfg, pam4_symbols, rng=None) -> TxResult:
    taps = np.asarray(cfg.tx_ffe_taps, dtype=float)
    tx_ffe_symbols = np.convolve(pam4_symbols, taps, mode="same")
    swing_cost = float(np.max(np.abs(tx_ffe_symbols)) / np.max(np.abs(pam4_symbols)))
    w, H_ffe = signal.freqz(taps, worN=1024)

    dac_zoh = np.repeat(tx_ffe_symbols, cfg.analog_sps)
    dac_quantized, _, dac_lsb, dac_clip_fraction = quantize_bipolar(
        dac_zoh, cfg.dac_bits, cfg.dac_full_scale_vpp)
    dac_waveform, _, _ = apply_frequency_response(
        dac_quantized, cfg.fs_analog_hz,
        lambda f: butterworth_response(f, cfg.dac_bw_hz, order=3,
                                       causal=cfg.causal_filters))

    # jitter del clock TX: resampling del time base (solo se iniettato,
    # così la baseline senza jitter resta bit-esatta)
    tx_tie_ui = None
    jitter_on = (cfg.tx_rj_rms_fs > 0 or cfg.tx_pj_amp_ui > 0
                 or cfg.tx_dcd_pct > 0)
    if jitter_on and rng is not None:
        tx_tie_ui = tx_clock_tie_ui(cfg, rng)
        tie_analog = np.repeat(tx_tie_ui, cfg.analog_sps) * cfg.analog_sps
        idx = np.arange(len(dac_waveform), dtype=float)
        dac_waveform = np.interp(idx - tie_analog, idx, dac_waveform)

    driver_linear_v = cfg.driver_gain_v_per_unit * dac_waveform
    driver_filtered_v, _, _ = apply_frequency_response(
        driver_linear_v, cfg.fs_analog_hz,
        lambda f: butterworth_response(f, cfg.driver_bw_hz, order=3,
                                       causal=cfg.causal_filters))
    driver_voltage_v = np.clip(driver_filtered_v, -cfg.driver_clip_v, cfg.driver_clip_v)
    driver_clip_fraction = float(np.mean(np.abs(driver_filtered_v) > cfg.driver_clip_v))

    result = TxResult(
        tx_ffe_symbols=tx_ffe_symbols,
        swing_cost=swing_cost,
        ffe_freq_norm=w / np.pi,
        ffe_response=H_ffe,
        dac_zoh=dac_zoh,
        dac_quantized=dac_quantized,
        dac_waveform=dac_waveform,
        dac_lsb=float(dac_lsb),
        dac_clip_fraction=dac_clip_fraction,
        tx_tie_ui=tx_tie_ui,
        driver_filtered_v=driver_filtered_v,
        driver_voltage_v=driver_voltage_v,
        driver_clip_fraction=driver_clip_fraction,
    )
    run_differential(cfg, result, rng)
    return result


def run_differential(cfg, tx: TxResult, rng=None):
    """Coppia P/N all'uscita del driver.

    vp = +(1+ε/2)·v/2 + vcm ;  vn = −(1−ε/2)·v(t−τ)/2 + vcm
    Il ricevitore differenziale vede v_diff = vp − vn: lo skew τ filtra il
    modo differenziale (notch a 1/(2τ)) e lo sbilanciamento ε fa trapelare il
    common-mode nel differenziale. Con tutto a zero: v_diff ≡ v (bit-esatto)."""
    v = tx.driver_voltage_v
    if cfg.tx_diff_noise_mv > 0 and rng is not None:
        # Stress source differenziale al reference plane di uscita PPG. Non
        # modifica il nodo driver ideale a monte, ma entra davvero in P/N e
        # quindi nel canale, come una voltage-noise addition di un BERT.
        v = v + rng.normal(0, cfg.tx_diff_noise_mv * 1e-3, len(v))
    skew_on = cfg.pn_skew_ps > 0
    mism_on = cfg.pn_gain_mismatch_pct > 0
    cm_on = cfg.vcm_offset_v != 0 or cfg.vcm_noise_mv > 0
    if not (skew_on or mism_on or cm_on or cfg.tx_diff_noise_mv > 0):
        tx.vp_v = v / 2
        tx.vn_v = -v / 2
        tx.vcm_v = np.zeros_like(v)
        tx.v_diff_v = v
        return
    vcm = np.full_like(v, cfg.vcm_offset_v)
    if cfg.vcm_noise_mv > 0 and rng is not None:
        vcm = vcm + rng.normal(0, cfg.vcm_noise_mv * 1e-3, len(v))
    if skew_on:
        tau_samples = cfg.pn_skew_ps * 1e-12 * cfg.fs_analog_hz
        idx = np.arange(len(v), dtype=float)
        v_n_arm = np.interp(idx - tau_samples, idx, v)
    else:
        v_n_arm = v
    # il guadagno di ciascun ramo moltiplica TUTTO il ramo (segnale + CM):
    # è così che lo sbilanciamento converte il common-mode in differenziale
    eps = cfg.pn_gain_mismatch_pct / 100
    tx.vp_v = (1 + eps / 2) * (v / 2 + vcm)
    tx.vn_v = (1 - eps / 2) * (-v_n_arm / 2 + vcm)
    # I nodi scope devono rispettare la definizione elettrica, non mostrare
    # solo la sorgente CM iniettata: il mismatch genera common-mode anche con
    # vcm sorgente nullo, e skew/mismatch ne rendono il contenuto data-dependent.
    tx.vcm_v = 0.5 * (tx.vp_v + tx.vn_v)
    tx.v_diff_v = tx.vp_v - tx.vn_v
