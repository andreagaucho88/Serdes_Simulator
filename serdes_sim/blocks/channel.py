"""Canale elettrico: modello analitico S21-equivalente, pulse response/cursor,
parser Touchstone S2P con diagnostica."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..utils import apply_frequency_response


def analytic_electrical_channel(f_hz, cfg):
    """Perdita skin-like + dielectric-like, ritardo, ripple GD, eco da mismatch."""
    af = np.abs(np.asarray(f_hz))
    x = np.clip(af / cfg.nyquist_hz, 0, 5)
    il_db = cfg.channel_il_nyquist_db * (0.55 * np.sqrt(x) + 0.45 * x)
    il_db = np.minimum(il_db, 55)
    delay_s = cfg.channel_delay_ps * 1e-12
    gd_ripple_s = cfg.group_delay_ripple_ps * 1e-12
    phase = -2 * np.pi * f_hz * delay_s
    phase += -2 * np.pi * f_hz * gd_ripple_s * np.sin(2 * np.pi * af / (0.8 * cfg.nyquist_hz + 1))
    gamma = 10 ** (-cfg.return_loss_db / 20)
    echo_delay_s = cfg.echo_delay_ui * cfg.ui_s
    H_echo = 1 + gamma * np.exp(-1j * 2 * np.pi * f_hz * echo_delay_s)
    return 10 ** (-il_db / 20) * np.exp(1j * phase) * H_echo


def measured_channel_response(f_hz, cfg):
    """H(f) da S21 di un Touchstone S2P per il percorso principale.

    Ricostruzione dichiarata (non un de-embedding):
    - magnitudine: interpolazione lineare, hold verso DC e oltre f_max;
    - fase: unwrap, 0 a DC, estrapolazione oltre f_max con il group delay
      dell'ultimo tratto;
    - simmetria Hermitiana per garantire una risposta impulsiva reale.
    """
    f_s2p, S, _, n_ports = parse_touchstone_text(cfg.s2p_text)
    if n_ports == 4:
        s21, _ = s4p_mixed_mode_21(f_s2p, S, cfg.s4p_pairs)  # SDD21
    else:
        s21 = S[:, 1, 0]
    order = np.argsort(f_s2p)
    f_s2p, s21 = f_s2p[order], s21[order]

    mag = np.abs(s21)
    phase = np.unwrap(np.angle(s21))
    # ancoraggio a DC: mag hold, fase 0
    f_grid = np.concatenate(([0.0], f_s2p))
    mag_grid = np.concatenate(([mag[0]], mag))
    phase_grid = np.concatenate(([0.0], phase))

    af = np.abs(np.asarray(f_hz))
    mag_i = np.interp(af, f_grid, mag_grid)          # hold oltre f_max
    phase_i = np.interp(af, f_grid, phase_grid)
    beyond = af > f_s2p[-1]
    if np.any(beyond) and len(f_s2p) > 1:
        slope = (phase[-1] - phase[-2]) / (f_s2p[-1] - f_s2p[-2])
        phase_i[beyond] = phase[-1] + slope * (af[beyond] - f_s2p[-1])

    H = mag_i * np.exp(1j * phase_i)
    return np.where(np.asarray(f_hz) < 0, np.conj(H), H)


def channel_response(f_hz, cfg):
    """Selettore: canale misurato S2P se richiesto, altrimenti analitico."""
    if cfg.use_s2p_channel and cfg.s2p_text.strip():
        return measured_channel_response(f_hz, cfg)
    return analytic_electrical_channel(f_hz, cfg)


@dataclass
class ChannelResult:
    electrical_waveform_v: np.ndarray
    H_electrical: np.ndarray
    f_fft_hz: np.ndarray
    # pulse response
    pulse_time_ui: np.ndarray
    pulse_normalized: np.ndarray
    cursor_ui: np.ndarray
    cursor_values: np.ndarray
    source: str = "analitico"


def run_channel(cfg, driver_voltage_v) -> ChannelResult:
    electrical_waveform_v, H_electrical, f_fft_hz = apply_frequency_response(
        driver_voltage_v, cfg.fs_analog_hz, lambda f: channel_response(f, cfg))

    # Pulse response: rettangolo di 1 UI attraverso lo stesso canale.
    n_pulse_ui = 192
    pulse_in = np.zeros(n_pulse_ui * cfg.analog_sps)
    pulse_ui = n_pulse_ui // 3
    pulse_in[pulse_ui * cfg.analog_sps:(pulse_ui + 1) * cfg.analog_sps] = 1.0
    pulse_out_v, _, _ = apply_frequency_response(
        pulse_in, cfg.fs_analog_hz, lambda f: channel_response(f, cfg))

    use_measured = cfg.use_s2p_channel and cfg.s2p_text.strip()
    if use_measured:
        # il ritardo del canale misurato non è noto a priori: ricerca globale
        main_sample = int(np.argmax(np.abs(pulse_out_v)))
    else:
        center_guess = (pulse_ui * cfg.analog_sps + cfg.analog_sps // 2
                        + round(cfg.channel_delay_ps * 1e-12 * cfg.fs_analog_hz))
        search = slice(center_guess - 2 * cfg.analog_sps,
                       center_guess + 4 * cfg.analog_sps)
        main_sample = search.start + int(np.argmax(np.abs(pulse_out_v[search])))
    main_sample = int(np.clip(main_sample, 6 * cfg.analog_sps,
                              len(pulse_out_v) - 9 * cfg.analog_sps))
    cursor_ui = np.arange(-6, 9)
    cursor_values = np.array([pulse_out_v[main_sample + k * cfg.analog_sps] for k in cursor_ui])
    cursor_values = cursor_values / cursor_values[cursor_ui == 0][0]

    span = 8 * cfg.analog_sps
    pulse_time_ui = np.arange(-span, span) / cfg.analog_sps
    pulse_normalized = (pulse_out_v[main_sample - span:main_sample + span]
                        / np.max(np.abs(pulse_out_v)))

    return ChannelResult(
        electrical_waveform_v=electrical_waveform_v,
        H_electrical=H_electrical,
        f_fft_hz=f_fft_hz,
        pulse_time_ui=pulse_time_ui,
        pulse_normalized=pulse_normalized,
        cursor_ui=cursor_ui,
        cursor_values=cursor_values,
        source=(f"S2P misurato: {cfg.s2p_name or 'file caricato'}"
                if use_measured else "modello analitico"),
    )


# ---------------------------------------------------------------------------
# Touchstone S2P (didattico, Touchstone 1.x, RI/MA/DB, Hz..GHz)
# ---------------------------------------------------------------------------

def parse_touchstone_s2p_text(text):
    unit_scale = {"HZ": 1.0, "KHZ": 1e3, "MHZ": 1e6, "GHZ": 1e9}
    option = None
    rows = []
    for raw in text.splitlines():
        line = raw.split("!")[0].strip()
        if not line:
            continue
        if line.startswith("#"):
            tokens = line[1:].upper().split()
            if len(tokens) < 3 or tokens[1] != "S":
                raise ValueError("option line attesa: # <unit> S <RI|MA|DB> R <z0>")
            option = tokens
            continue
        if line.startswith("["):
            raise NotImplementedError("Touchstone 2.x block syntax: usare scikit-rf")
        rows.extend(float(v) for v in line.split())
    if option is None or len(rows) % 9:
        raise ValueError("S2P incompleto o senza option line")
    unit, fmt = option[0], option[2]
    if unit not in unit_scale or fmt not in {"RI", "MA", "DB"}:
        raise ValueError("unità/formato non supportati")
    z0 = float(option[option.index("R") + 1]) if "R" in option else 50.0
    a = np.asarray(rows).reshape(-1, 9)

    def pair(v1, v2):
        if fmt == "RI":
            return v1 + 1j * v2
        mag = v1 if fmt == "MA" else 10 ** (v1 / 20)
        return mag * np.exp(1j * np.deg2rad(v2))

    S = np.empty((len(a), 2, 2), dtype=complex)
    S[:, 0, 0] = pair(a[:, 1], a[:, 2])
    S[:, 1, 0] = pair(a[:, 3], a[:, 4])  # S21
    S[:, 0, 1] = pair(a[:, 5], a[:, 6])  # S12
    S[:, 1, 1] = pair(a[:, 7], a[:, 8])
    return a[:, 0] * unit_scale[unit], S, z0


def parse_touchstone_text(text):
    """Parser Touchstone 1.x generico a n porte (2 o 4).

    Ritorna (f_hz, S[punti, n, n], z0, n_ports). Per s4p il port order è
    quello Touchstone 1.x (column-major: S11 S21 ... SN1, S12 ...); il
    mapping fisico P/N è scelto altrove (s4p_pairs)."""
    unit_scale = {"HZ": 1.0, "KHZ": 1e3, "MHZ": 1e6, "GHZ": 1e9}
    option = None
    rows = []
    for raw in text.splitlines():
        line = raw.split("!")[0].strip()
        if not line:
            continue
        if line.startswith("#"):
            tokens = line[1:].upper().split()
            if len(tokens) < 3 or tokens[1] != "S":
                raise ValueError("option line attesa: # <unit> S <RI|MA|DB> R <z0>")
            option = tokens
            continue
        if line.startswith("["):
            raise NotImplementedError("Touchstone 2.x: usare scikit-rf")
        rows.extend(float(v) for v in line.split())
    if option is None:
        raise ValueError("file senza option line")
    unit, fmt = option[0], option[2]
    if unit not in unit_scale or fmt not in {"RI", "MA", "DB"}:
        raise ValueError("unità/formato non supportati")
    z0 = float(option[option.index("R") + 1]) if "R" in option else 50.0
    # inferenza porte: il conteggio può essere ambiguo (99 valori = 11 punti
    # s2p O 3 punti s4p) → si sceglie il candidato con frequenze crescenti
    arr = np.asarray(rows)
    candidates = []
    for n_try in (4, 2):
        per_point = 1 + 2 * n_try * n_try
        if len(arr) % per_point == 0 and len(arr) // per_point >= 2:
            freqs = arr.reshape(-1, per_point)[:, 0]
            if np.all(np.diff(freqs) > 0):
                candidates.append(n_try)
    if not candidates:
        raise ValueError("numero di valori non compatibile con s2p/s4p "
                         "(o griglia di frequenze non monotona)")
    n_ports = candidates[0]
    per_point = 1 + 2 * n_ports * n_ports
    a = arr.reshape(-1, per_point)

    def pair(v1, v2):
        if fmt == "RI":
            return v1 + 1j * v2
        mag = v1 if fmt == "MA" else 10 ** (v1 / 20)
        return mag * np.exp(1j * np.deg2rad(v2))

    vals = a[:, 1:]
    S = np.empty((len(a), n_ports, n_ports), dtype=complex)
    for i in range(n_ports):
        for j in range(n_ports):
            # Touchstone 1.x: varia prima la porta di uscita i, poi quella
            # d'ingresso j: S11,S21,...,SN1,S12,... (column-major).
            k = 2 * (j * n_ports + i)
            S[:, i, j] = pair(vals[:, k], vals[:, k + 1])
    if n_ports == 2:
        # Touchstone s2p: ordine S11 S21 S12 S22 (non row-major!)
        S2 = np.empty_like(S)
        S2[:, 0, 0] = pair(vals[:, 0], vals[:, 1])
        S2[:, 1, 0] = pair(vals[:, 2], vals[:, 3])
        S2[:, 0, 1] = pair(vals[:, 4], vals[:, 5])
        S2[:, 1, 1] = pair(vals[:, 6], vals[:, 7])
        S = S2
    return a[:, 0] * unit_scale[unit], S, z0, n_ports


def s4p_mixed_mode_21(f_hz, S4, pairs="13_24"):
    """SDD21 e SCD21 dal 4-porte single-ended (trasformazione mixed-mode).

    pairs "13_24": ingresso differenziale = porte (1,3), uscita = (2,4);
    pairs "12_34": ingresso = (1,2), uscita = (3,4)."""
    if pairs == "13_24":
        ip, im, op, om = 0, 2, 1, 3
    else:
        ip, im, op, om = 0, 1, 2, 3
    sdd21 = 0.5 * (S4[:, op, ip] - S4[:, op, im]
                   - S4[:, om, ip] + S4[:, om, im])
    scd21 = 0.5 * (S4[:, op, ip] + S4[:, op, im]
                   - S4[:, om, ip] - S4[:, om, im])
    return sdd21, scd21


def sparameter_diagnostics(f_hz, S):
    sigma_max = np.array([np.linalg.svd(m, compute_uv=False)[0] for m in S])
    reciprocity_error = np.max(np.abs(S[:, 1, 0] - S[:, 0, 1]))
    phase = np.unwrap(np.angle(S[:, 1, 0]))
    group_delay_s = -np.gradient(phase, 2 * np.pi * f_hz)
    return pd.Series({
        "max_singular_value": sigma_max.max(),
        "max_reciprocity_error": reciprocity_error,
        "group_delay_min_ps": group_delay_s.min() * 1e12,
        "group_delay_max_ps": group_delay_s.max() * 1e12,
        "uniform_frequency_grid": bool(np.allclose(np.diff(f_hz), np.diff(f_hz)[0])),
    })


DEMO_S2P = """! passive reciprocal demo, Touchstone 1.x
# GHZ S DB R 50
0.1  -40 0   -0.2 -1   -0.2 -1   -40 0
5.0  -40 4   -1.5 -8   -1.5 -8   -40 4
10.0 -40 9   -3.1 -16  -3.1 -16  -40 9
20.0 -40 18  -6.8 -32  -6.8 -32  -40 18
30.0 -40 28 -10.5 -49 -10.5 -49  -40 28
40.0 -40 38 -14.8 -67 -14.8 -67  -40 38
50.0 -40 48 -19.5 -86 -19.5 -86  -40 48
60.0 -40 58 -24.5 -106 -24.5 -106 -40 58
"""
