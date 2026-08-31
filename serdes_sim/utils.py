"""Funzioni di base condivise: dB, dBm, filtraggio FFT, quantizzazione, ENBW.

Le convenzioni seguono il builder v7 (fonte di verità):
- SI ovunque; i suffissi _hz, _s, _v, _a, _w rendono l'unità visibile nel nome;
- le waveform elettriche sono tensioni reali; il campo ottico è complesso e
  soddisfa |E|^2 = P in watt;
- il rumore bianco discreto con PSD one-sided S ha varianza S*fs/2.
"""

from __future__ import annotations

import numpy as np

C0_M_S = 299_792_458.0
Q_E_C = 1.602_176_634e-19


def db10(power_ratio):
    return 10 * np.log10(np.maximum(power_ratio, 1e-300))


def db20(amplitude_ratio):
    return 20 * np.log10(np.maximum(np.abs(amplitude_ratio), 1e-300))


def dbm_to_w(dbm):
    return 1e-3 * 10 ** (np.asarray(dbm) / 10)


def w_to_dbm(w):
    return 10 * np.log10(np.maximum(np.asarray(w), 1e-300) / 1e-3)


def rms_ac(x):
    x = np.asarray(x)
    return float(np.sqrt(np.mean(np.abs(x - np.mean(x)) ** 2)))


def butterworth_magnitude(f_hz, f3db_hz, order=3):
    """Magnitudine Butterworth a fase zero: isola la banda, non la causalità."""
    return 1 / np.sqrt(1 + (np.abs(f_hz) / f3db_hz) ** (2 * order))


_BUTTER_PROTO_CACHE = {}


def butterworth_response(f_hz, f3db_hz, order=3, causal=False):
    """Risposta Butterworth: |H| identica nei due modi; `causal=True` aggiunge
    la fase (e quindi il group delay) del filtro analogico reale."""
    if not causal:
        return butterworth_magnitude(f_hz, f3db_hz, order)
    from scipy import signal
    if order not in _BUTTER_PROTO_CACHE:
        _BUTTER_PROTO_CACHE[order] = signal.butter(order, 1.0, "low", analog=True)
    b, a = _BUTTER_PROTO_CACHE[order]
    s = 1j * np.asarray(f_hz) / f3db_hz
    return np.polyval(b, s) / np.polyval(a, s)


def apply_frequency_response(x, fs_hz, response_builder, force_real=None):
    """Applica H(f) via FFT. response_builder riceve le frequenze fftfreq."""
    x = np.asarray(x)
    f_hz = np.fft.fftfreq(len(x), d=1 / fs_hz)
    H = response_builder(f_hz)
    y = np.fft.ifft(np.fft.fft(x) * H)
    if force_real is True or (force_real is None and not np.iscomplexobj(x)):
        y = np.real(y)
    return y, H, f_hz


def quantize_bipolar(x, bits, full_scale_vpp):
    """Quantizzatore mid-tread con clipping; ritorna (y, code, lsb, clip_fraction)."""
    if bits < 2 or full_scale_vpp <= 0:
        raise ValueError("bits>=2 e full_scale_vpp>0")
    lo, hi = -full_scale_vpp / 2, full_scale_vpp / 2
    clipped = np.clip(np.asarray(x), lo, hi)
    lsb = full_scale_vpp / (2 ** bits - 1)
    code = np.rint((clipped - lo) / lsb).astype(int)
    reconstructed = lo + code * lsb
    clip_fraction = float(np.mean((np.asarray(x) < lo) | (np.asarray(x) > hi)))
    return reconstructed, code, lsb, clip_fraction


def white_noise_from_one_sided_psd(psd, count, fs_hz, rng):
    return rng.normal(0, np.sqrt(psd * fs_hz / 2), count)


def enbw_one_sided_hz(response_mag, f_hz):
    """Equivalent noise bandwidth numerica di |H(f)| su griglia one-sided."""
    return float(np.trapz(np.abs(response_mag) ** 2, f_hz))


def affine_fit(x, y):
    """Fit y ≈ gain*x + offset in forma chiusa (equivalente a lstsq)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mx, my = x.mean(), y.mean()
    vx = np.mean((x - mx) ** 2)
    gain = float(np.mean((x - mx) * (y - my)) / max(vx, 1e-30))
    offset = float(my - gain * mx)
    return gain, offset


def qfunc(x):
    from scipy.special import erfc
    return 0.5 * erfc(np.asarray(x) / np.sqrt(2))


def zero_error_upper_bound(n_bits, confidence=0.95):
    """Upper bound one-sided della BER con zero errori osservati su n_bits."""
    n = np.asarray(n_bits, dtype=float)
    return -np.expm1(np.log1p(-confidence) / n)
