"""Channel Operating Margin (COM), IEEE 802.3 Annex 93A subset.

The implementation follows the public IEEE 802.3ck COM 3.70 configuration
for 100GBASE-KR1 where the LabPro model has the required information:

* Clause 93A package transmission-line equations (93A-9 .. 93A-14);
* reference TX transition-time filter, CTLE and TX FFE search;
* pulse-response sampling, bounded DFE and FOM optimization;
* statistical ISI/xtalk PDFs and Gaussian noise at DER_0;
* COM = 20 log10(A_s/A_ni).

This is deliberately *not* labelled a compliance implementation.  LabPro
currently accepts one victim S2P/S4P response, rather than the complete set of
victim, NEXT and FEXT multiport files and terminations consumed by the IEEE
reference program.  The package loss/delay is normative-equation shaped, but
pad/ball capacitances and multiple-reflection cascade are not yet modelled.
Those deviations are returned in every report so the UI cannot silently turn
an engineering estimate into an IEEE pass/fail claim.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache

import numpy as np
from scipy import signal, stats

from ..standards import (COM_DER0, COM_KR1_THRESHOLD_DB, ERROR, FAIL,
                         NOT_APPLICABLE, NOT_ASSESSED, PASS, RLM_MIN_8023CK,
                         evaluate_limit, limits_for_interface, verdict)
from .channel import channel_response


@dataclass(frozen=True)
class Clause93aKr1Parameters:
    """100GBASE-KR1 COM parameter set (IEEE 802.3ck Clause 162).

    Values are those of the public COM 3.70 configuration published with
    the 802.3ck D3.1 KR draft; table numbers of the ratified text are not
    re-verified here (see ``parameter_provenance`` in the report).
    """

    standard: str = "IEEE 802.3ck"
    clause: str = "Annex 93A (100GBASE-KR1 parameter set, Clause 162)"
    source_version: str = ("IEEE Std 802.3ck-2022 Clause 162 parameter set as "
                           "published in COM 3.70 / D3.1 KR (2022-03-23); "
                           "table numbers to verify")
    symbol_rate_hz: float = 53.125e9
    levels: int = 4
    samples_per_ui: int = 32
    der0: float = COM_DER0
    pass_threshold_db: float = COM_KR1_THRESHOLD_DB
    victim_amplitude_v: float = 0.413
    fext_amplitude_v: float = 0.413
    next_amplitude_v: float = 0.608
    tx_transition_time_s: float = 7.5e-12
    rx_bt_fraction_baud: float = 0.75
    eta0_v2_per_ghz: float = 8.2e-9
    tx_sndr_db: float = 33.0
    sigma_rj_ui: float = 0.01
    a_dd_ui: float = 0.02
    r_lm: float = RLM_MIN_8023CK
    dfe_taps: int = 12
    ctle_zero_hz: float = 21.25e9
    ctle_pole1_hz: float = 21.25e9
    ctle_pole2_hz: float = 53.125e9
    # Low-frequency CTLE stage of the 802.3ck reference receiver
    # (Equation 93A-22 as amended): (g_DC2 + j f/f_LF)/(1 + j f/f_LF).
    ctle_gdc2_db_min: float = -6.0
    ctle_gdc2_db_max: float = 0.0
    ctle_gdc2_step_db: float = 1.0
    ctle_f_lf_hz: float = 53.125e9 / 40.0
    ctle_gdc_db_min: float = -20.0
    ctle_gdc_db_max: float = 0.0
    ctle_gdc_step_db: float = 1.0
    # Two-stage equalizer search: every (g_DC, g_DC2) point is ranked with
    # the vectorized nominal-phase FOM; only the leaders get the fine search.
    search_keep_combos: int = 4
    package_gamma0_per_mm: float = 0.0
    package_a1_ns_half_per_mm: float = 0.0009909
    package_a2_ns_per_mm: float = 0.0002772
    package_tau_ns_per_mm: float = 6.141e-3


KR1_93A = Clause93aKr1Parameters()


def package_s21(f_hz, length_mm, zc_ohm=87.5, z0_ohm=50.0,
                params: Clause93aKr1Parameters = KR1_93A):
    """Transmission-line S21 from IEEE 802.3 equations 93A-9..93A-14.

    ``zc_ohm`` is the differential package-line impedance.  Annex 93A uses
    two single-ended ``z0`` ports, hence rho=(Zc-2Z0)/(Zc+2Z0).
    """
    f = np.asarray(f_hz, dtype=float)
    fg = np.abs(f) / 1e9
    safe_fg = np.maximum(fg, np.finfo(float).tiny)
    g1 = params.package_a1_ns_half_per_mm * (1.0 + 1.0j)
    g2 = (params.package_a2_ns_per_mm
          * (1.0 - 2.0j / np.pi * np.log(safe_fg))
          + 2.0j * np.pi * params.package_tau_ns_per_mm)
    gamma = params.package_gamma0_per_mm + g1 * np.sqrt(fg) + g2 * fg
    gamma = np.where(fg == 0, params.package_gamma0_per_mm, gamma)
    if length_mm == 0:
        return np.ones_like(f, dtype=complex)
    rho = (zc_ohm - 2.0 * z0_ohm) / (zc_ohm + 2.0 * z0_ohm)
    e = np.exp(-float(length_mm) * gamma)
    s21 = (1.0 - rho ** 2) * e / (1.0 - rho ** 2 * e ** 2)
    return np.where(f < 0, np.conj(s21), s21)


def _reference_tx_filter(f_hz, p=KR1_93A):
    """Gaussian transmitter filter, Equation 93A-46.

    A Gaussian impulse response with 20–80 % rise time T_r has
    sigma_t = T_r/1.6832, hence |H(f)| = exp(-2·(pi·f·T_r/1.6832)^2).  The
    factor 2 was missing in earlier LabPro releases (which made the filter
    the response of a rise time T_r/sqrt(2)); it is restored here and the
    equation form is what the registry test guards.
    """
    f_ghz = np.abs(np.asarray(f_hz)) / 1e9
    tr_ns = p.tx_transition_time_s * 1e9
    return np.exp(-2.0 * (np.pi * f_ghz * tr_ns / 1.6832) ** 2)


def _reference_rx_filter(f_hz, p=KR1_93A):
    """Causal fourth-order Bessel-Thomson receiver at 0.75 baud."""
    # scipy's norm="mag" normalizes the analog prototype at -3 dB for w=1.
    b, a = signal.bessel(4, 1.0, analog=True, norm="mag")
    s = 1j * np.asarray(f_hz) / (p.rx_bt_fraction_baud * p.symbol_rate_hz)
    return np.polyval(b, s) / np.polyval(a, s)


def _ctle(f_hz, gdc_db, p=KR1_93A, gdc2_db=0.0):
    """Reference CTLE (Equation 93A-22 with the 802.3ck low-frequency stage)."""
    f = np.asarray(f_hz)
    hf = ((10 ** (gdc_db / 20) + 1j * f / p.ctle_zero_hz)
          / ((1 + 1j * f / p.ctle_pole1_hz)
             * (1 + 1j * f / p.ctle_pole2_hz)))
    lf = ((10 ** (gdc2_db / 20) + 1j * f / p.ctle_f_lf_hz)
          / (1 + 1j * f / p.ctle_f_lf_hz))
    return hf * lf


def _tx_ffe_candidates():
    """Prescribed 802.3ck KR grid, pruned only by the c(0)>=0.54 rule."""
    out = []
    for cm3 in np.arange(-0.06, 0.0001, 0.02):
        for cm2 in np.arange(0.0, 0.1201, 0.02):
            for cm1 in np.arange(-0.34, 0.0001, 0.02):
                for cp1 in np.arange(-0.20, 0.0001, 0.02):
                    c0 = 1.0 - sum(abs(v) for v in (cm3, cm2, cm1, cp1))
                    if c0 >= 0.54 - 1e-12:
                        out.append((cm3, cm2, cm1, c0, cp1))
    return np.asarray(out)


_FFE_GRID = _tx_ffe_candidates()


def _dfe_limits(n):
    # b_max(1), b_max(2..N_b) from the public 3ck D3.1 KR config.
    v = np.r_[0.85, 0.30, np.full(5, 0.20), np.full(max(n - 7, 0), 0.10)]
    return v[:n]


def _pulse_from_response(H_pos, n, samples_per_ui):
    """One-UI pulse response with enough guard time for package delay."""
    x = np.zeros(n)
    start = n // 4
    x[start:start + samples_per_ui] = 1.0
    return np.fft.irfft(np.fft.rfft(x) * H_pos, n=n)


def _sample_cursors(pulse, samples_per_ui, main, pre_ui=28, post_ui=80):
    ks = np.arange(-pre_ui, post_ui + 1)
    idx = main + ks * samples_per_ui
    ok = (idx >= 1) & (idx < len(pulse) - 1)
    return ks[ok], pulse[idx[ok]]


def _candidate_metrics(pulse, taps, p=KR1_93A):
    """Return Annex-93A FOM ingredients for one CTLE/TX-FFE candidate."""
    sps = p.samples_per_ui
    # The FFE taps correspond to c(-3),c(-2),c(-1),c(0),c(+1).
    eq = np.zeros_like(pulse)
    for rel, tap in zip((-3, -2, -1, 0, 1), taps):
        eq += tap * np.roll(pulse, rel * sps)
    # Search sampling phase around the largest pulse cursor, as Annex 93A
    # does during equalizer optimization.
    peak = int(np.argmax(np.abs(eq)))
    best = None
    for off in range(-sps // 2, sps // 2 + 1):
        main = peak + off
        ks, cur = _sample_cursors(eq, sps, main)
        if not len(cur) or 0 not in ks:
            continue
        cursor = float(cur[ks == 0][0])
        if cursor < 0:
            cur = -cur
            cursor = -cursor
        if cursor <= 0:
            continue
        a_s = p.r_lm * cursor / (p.levels - 1)
        pre = cur[ks < 0]
        post = cur[ks > 0]
        nb = min(p.dfe_taps, len(post))
        cancelled = np.clip(post[:nb], -cursor * _dfe_limits(nb),
                            cursor * _dfe_limits(nb))
        residual_post = np.r_[post[:nb] - cancelled, post[nb:]]
        residual = np.r_[pre, residual_post]
        sigma_x = np.sqrt((p.levels ** 2 - 1)
                          / (3 * (p.levels - 1) ** 2))
        sigma_isi = sigma_x * float(np.linalg.norm(residual))
        # Equation 93A-28: one-sample finite-difference jitter sensitivity.
        idx = main + ks * sps
        h_j = (eq[idx + 1] - eq[idx - 1]) * sps / 2.0
        sigma_rjit = p.sigma_rj_ui * sigma_x * float(np.linalg.norm(h_j))
        # Equation 93A-30 form: transmitter noise referred to one level
        # step h(0)/(L-1), not to the full cursor amplitude.
        sigma_tx = cursor / (p.levels - 1) * 10 ** (-p.tx_sndr_db / 20)
        score = a_s / max(np.linalg.norm([sigma_isi, sigma_rjit, sigma_tx]), 1e-30)
        row = dict(main=main, a_s=a_s, cursor=cursor, residual=residual,
                   h_j=h_j, sigma_isi=sigma_isi,
                   sigma_rjit=sigma_rjit, sigma_tx=sigma_tx,
                   dfe_taps=(cancelled / cursor), score=score, eq=eq)
        if best is None or score > best["score"]:
            best = row
    return best


def _rank_ffe_candidates(pulse, p=KR1_93A, keep=18):
    """Vectorized full-grid FOM preselection at the nominal cursor phase."""
    return _rank_ffe_candidates_scored(pulse, p, keep)[0]


# Coarse sub-grid (every 9th prescribed point, ~480 rows) used only to rank
# the CTLE (g_DC, g_DC2) combinations; the full grid is re-run on the leaders.
_FFE_GRID_COARSE = np.ascontiguousarray(_FFE_GRID[::9])


def _rank_ffe_candidates_scored(pulse, p=KR1_93A, keep=18, grid=None):
    """Vectorized full-grid FOM preselection at the nominal cursor phase.

    Annex 93A uses FOM to choose equalizer candidates before the final PDF.
    All prescribed tap-grid points are evaluated here.  The best candidates
    then receive the fine 1/32-UI sampling-phase search in
    :func:`_candidate_metrics`.  Returns ``(leaders, best_score)`` so the
    same ranking can order the CTLE (g_DC, g_DC2) grid.
    """
    grid = _FFE_GRID if grid is None else grid
    sps = p.samples_per_ui
    peak = int(np.argmax(np.abs(pulse)))
    ks = np.arange(-28, 81)
    rels = np.asarray([-3, -2, -1, 0, 1])
    idx = peak + ks[None, :] * sps - rels[:, None] * sps
    if np.any(idx < 1) or np.any(idx >= len(pulse) - 1):
        return grid[:keep], -np.inf
    # Fresh contiguous copies + np.dot: numpy's matmul dispatch (and dot on
    # fancy-indexed operands) is ~100x slower for these K=5 shapes on
    # OpenBLAS (10 ms vs 0.07 ms) and used to dominate the COM search.
    basis = np.array(pulse[idx], order="C")
    curs = np.dot(grid, basis)
    main_col = int(np.flatnonzero(ks == 0)[0])
    cursor = curs[:, main_col]
    sign = np.where(cursor < 0, -1.0, 1.0)
    curs = curs * sign[:, None]
    cursor = np.abs(cursor)
    pre = curs[:, ks < 0]
    post = curs[:, ks > 0]
    nb = min(p.dfe_taps, post.shape[1])
    caps = cursor[:, None] * _dfe_limits(nb)[None, :]
    cancelled = np.clip(post[:, :nb], -caps, caps)
    residual = np.c_[pre, post[:, :nb] - cancelled, post[:, nb:]]
    sigma_x = np.sqrt((p.levels ** 2 - 1)
                      / (3 * (p.levels - 1) ** 2))
    sigma_isi = sigma_x * np.linalg.norm(residual, axis=1)

    early = np.dot(grid, np.array(pulse[idx - 1], order="C"))
    late = np.dot(grid, np.array(pulse[idx + 1], order="C"))
    h_j = (late - early) * (sps / 2.0) * sign[:, None]
    sigma_rjit = p.sigma_rj_ui * sigma_x * np.linalg.norm(h_j, axis=1)
    a_s = p.r_lm * cursor / (p.levels - 1)
    sigma_tx = cursor / (p.levels - 1) * 10 ** (-p.tx_sndr_db / 20)
    denom = np.sqrt(sigma_isi ** 2 + sigma_rjit ** 2 + sigma_tx ** 2)
    score = np.where(cursor > 0, a_s / np.maximum(denom, 1e-30), -np.inf)
    take = np.argpartition(score, -min(keep, len(score)))[-keep:]
    take = take[np.argsort(score[take])[::-1]]
    return grid[take], float(score[take[0]])


def _quantized_pmf(cursors, levels=4, bin_size=1e-5):
    """Equation-93A-39 discrete interference PDF by delta-set convolution."""
    cur = np.asarray(cursors, dtype=float)
    cur = cur[np.abs(cur) >= bin_size]
    if not len(cur):
        return np.asarray([0.0]), np.asarray([1.0])
    values = np.linspace(-1.0, 1.0, levels)
    pmf = np.asarray([1.0])
    zero = 0
    for c in cur:
        shifts = np.rint(c * values / bin_size).astype(int)
        lo, hi = int(shifts.min()), int(shifts.max())
        new = np.zeros(len(pmf) + hi - lo)
        for sh in shifts:
            start = int(sh - lo)
            new[start:start + len(pmf)] += pmf / levels
        pmf, zero = new, zero - lo
        # Numerical noise from long shift/add chains should not change mass.
        pmf /= np.sum(pmf)
    x = (np.arange(len(pmf)) - zero) * bin_size
    return x, pmf


def _tail_amplitude(discrete_cursors, sigma_gaussian, der0, levels=4,
                    bin_size=1e-5):
    """Magnitude A where P(I+G <= -A)=DER0 for symmetric interference."""
    x, prob = _quantized_pmf(discrete_cursors, levels, bin_size)
    sigma = float(sigma_gaussian)
    if sigma <= 0:
        cdf = np.cumsum(prob)
        i = int(np.searchsorted(cdf, der0, side="left"))
        return abs(float(x[min(i, len(x) - 1)]))

    def tail(a):
        return float(np.sum(prob * stats.norm.cdf((-a - x) / sigma)))

    hi = max(float(np.max(np.abs(x))) + stats.norm.isf(der0) * sigma,
             bin_size)
    lo = 0.0
    for _ in range(55):
        mid = 0.5 * (lo + hi)
        if tail(mid) > der0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def margin_from_components(signal_v, gaussian_sigma_v, discrete_cursors_v=(),
                           der0=1e-4, levels=4, bin_size_v=1e-5):
    """Small independently-testable core of equations 93A-39/45 and COM."""
    ani = _tail_amplitude(discrete_cursors_v, gaussian_sigma_v, der0,
                          levels, bin_size_v)
    com_db = 20 * np.log10(float(signal_v) / max(ani, 1e-30))
    return {"a_ni_v": float(ani), "com_db": float(com_db)}


def _xtalk_cursors(cfg, f_pos, rx, ctle, tx, tx_ffe, n, p=KR1_93A):
    """LabPro aggressor responses, kept separate as Clause-93A contributions."""
    out = []
    fny = p.symbol_rate_hz / 2
    if cfg.xtalk_next_db < 0:
        h = (10 ** (cfg.xtalk_next_db / 20)
             * np.sqrt(np.clip(f_pos / fny, 0, 1)) * rx * ctle)
        pr = _pulse_from_response(h * p.next_amplitude_v, n, p.samples_per_ui)
        main = int(np.argmax(np.abs(pr)))
        _, c = _sample_cursors(pr, p.samples_per_ui, main, 8, 24)
        out.extend(c)
    if cfg.xtalk_fext_db < 0:
        h = (10 ** (cfg.xtalk_fext_db / 20)
             * np.clip(f_pos / fny, 0, 1) * channel_response(f_pos, cfg)
             * rx * ctle * tx * tx_ffe)
        pr = _pulse_from_response(h * p.fext_amplitude_v, n, p.samples_per_ui)
        main = int(np.argmax(np.abs(pr)))
        _, c = _sample_cursors(pr, p.samples_per_ui, main, 8, 24)
        out.extend(c)
    return np.asarray(out)


def _default_com_limit(interface):
    """Registry limit governing the COM verdict.

    Without an active profile the 100GBASE-KR1 entry applies, because that
    is the only parameter set implemented; the report says so explicitly.
    """
    lims = limits_for_interface(interface)
    if "com" in lims:
        return lims["com"], bool(interface)
    return limits_for_interface("100GBASE-KR1")["com"], False


@lru_cache(maxsize=24)
def com_report(cfg, p: Clause93aKr1Parameters = KR1_93A, interface=None):
    """Return a standards-scoped COM report for a :class:`LinkConfig`.

    ``interface`` is the active profile interface name (``"100GBASE-KR1"``,
    ``"100GAUI-1 C2M"``, ...).  It selects the registry limit and blocks the
    computation where the clause does not use COM at all.
    """
    lim, from_profile = _default_com_limit(interface)
    rate_ok = abs(cfg.symbol_rate_hz / p.symbol_rate_hz - 1) < 1e-6
    medium_ok = cfg.link_medium == "copper" and cfg.modulation == "PAM4"
    clause_blocks = lim.implementation == "not-applicable"
    applicable = bool(medium_ok and rate_ok and not clause_blocks)
    base = {
        "standard": p.standard, "clause": p.clause,
        "source_version": p.source_version,
        "applicable": applicable, "normative": False,
        "compliance_result": NOT_ASSESSED if applicable else NOT_APPLICABLE,
        "parameters": asdict(p),
        "parameter_provenance": [
            {"name": "der0 / threshold / R_LM", "source": "registry (standards.py)",
             "confidence": "published"},
            {"name": "A_v, A_fe, A_ne, T_r, eta0, SNR_TX, sigma_RJ, A_DD, N_b, "
                     "package a1/a2/tau, f_z/f_p1/f_p2, g_DC range",
             "source": "COM 3.70 configuration published with 802.3ck D3.1 KR",
             "confidence": "to-verify"},
            {"name": "g_DC2 range, f_LF", "source": "802.3ck reference receiver "
             "low-frequency stage (public presentations)", "confidence": "to-verify"},
        ],
        "reference_plane": "passive electrical channel, package TX to package RX",
        "limit": lim.as_dict(), "limit_from_profile": from_profile,
        "interface": interface,
    }
    if not applicable:
        if clause_blocks:
            reason = {"it": lim.note_it, "en": lim.note_en}
        elif not medium_ok:
            reason = {"it": "COM Annex 93A vale per canali elettrici PAM4: carica "
                            "un profilo 802.3ck 100GBASE-KR1 o un banco copper.",
                      "en": "Annex 93A COM applies to PAM4 electrical channels: load "
                            "the IEEE 802.3ck 100GBASE-KR1 profile or a copper bench."}
        else:
            reason = {"it": "Il set di parametri implementato è quello 100GBASE-KR1 "
                            "a 53.125 GBd; a questo rate il calcolo non è applicabile.",
                      "en": "The implemented parameter set is the 53.125 GBd "
                            "100GBASE-KR1 one; at this rate the computation is not "
                            "applicable."}
        base.update({"reason": reason, "model_result": NOT_APPLICABLE,
                     "verdict": evaluate_limit(lim, None, applicable=False,
                                               evidence=reason["en"])})
        return base

    sps = p.samples_per_ui
    n = 16384
    fs = p.symbol_rate_hz * sps
    f_pos = np.fft.rfftfreq(n, 1 / fs)
    h_tx = _reference_tx_filter(f_pos, p)
    h_rx = _reference_rx_filter(f_pos, p)
    h_ch = channel_response(f_pos, cfg)
    package_cases = [
        {"name": "short", "tx_mm": 12.0, "rx_mm": 12.0, "zc_ohm": 87.5},
        {"name": "long", "tx_mm": 31.0, "rx_mm": 29.0, "zc_ohm": 92.5},
    ]
    gdc_grid = np.arange(p.ctle_gdc_db_min, p.ctle_gdc_db_max + 1e-9,
                         p.ctle_gdc_step_db)
    gdc2_grid = np.arange(p.ctle_gdc2_db_min, p.ctle_gdc2_db_max + 1e-9,
                          p.ctle_gdc2_step_db)
    reports = []
    for case in package_cases:
        h_pkg = (package_s21(f_pos, case["tx_mm"], case["zc_ohm"], params=p)
                 * package_s21(f_pos, case["rx_mm"], case["zc_ohm"], params=p))
        base_resp = h_tx * h_pkg * h_ch * h_rx * p.victim_amplitude_v
        # Stage 1: rank the whole (g_DC, g_DC2) grid with the vectorized
        # nominal-phase FOM (all prescribed TX-FFE points evaluated).
        combos = []
        for gdc in gdc_grid:
            for gdc2 in gdc2_grid:
                h_ct = _ctle(f_pos, float(gdc), p, float(gdc2))
                pulse0 = _pulse_from_response(base_resp * h_ct, n, sps)
                _, score = _rank_ffe_candidates_scored(
                    pulse0, p, keep=1, grid=_FFE_GRID_COARSE)
                combos.append((score, float(gdc), float(gdc2), h_ct, pulse0))
        combos.sort(key=lambda c: -c[0])
        # Stage 2: full prescribed TX-FFE grid on the leading CTLE settings,
        # then the fine 1/32-UI phase search for their FOM leaders.
        best = None
        for _score, gdc, gdc2, h_ct, pulse0 in combos[:p.search_keep_combos]:
            leaders, _ = _rank_ffe_candidates_scored(pulse0, p)
            for taps in leaders:
                row = _candidate_metrics(pulse0, taps, p)
                if row is not None and (best is None or row["score"] > best["score"]):
                    best = dict(row, taps=taps, gdc_db=gdc, gdc2_db=gdc2, h_ct=h_ct)
        if best is None:
            reports.append(dict(case=case, error="no valid equalizer setting"))
            continue

        # Receiver eta0 noise, Equation 93A-36 support.  eta0 is V^2/GHz.
        df_ghz = (f_pos[1] - f_pos[0]) / 1e9
        sigma_n = float(np.sqrt(p.eta0_v2_per_ghz * np.sum(
            np.abs(h_rx[1:] * best["h_ct"][1:]) ** 2) * df_ghz))
        # Random jitter, receiver and TX noise are Gaussian.  Bounded DD and
        # residual ISI use the Annex-93A discrete PDF construction.
        sigma_g = float(np.linalg.norm([
            best["sigma_rjit"], sigma_n, best["sigma_tx"]]))
        h_ffe = np.zeros_like(f_pos, dtype=complex)
        for rel, tap in zip((-3, -2, -1, 0, 1), best["taps"]):
            h_ffe += tap * np.exp(-1j * 2 * np.pi * f_pos * rel / p.symbol_rate_hz)
        xtalk = _xtalk_cursors(cfg, f_pos, h_rx, best["h_ct"], h_tx,
                               h_ffe, n, p)
        discrete = np.r_[best["residual"], p.a_dd_ui * best["h_j"], xtalk]
        bin_size = min(max(best["a_s"] / 1000, 1e-6), 1e-5)
        final = margin_from_components(best["a_s"], sigma_g, discrete,
                                       p.der0, p.levels, bin_size)
        q = float(stats.norm.isf(p.der0))
        peak_isi = _tail_amplitude(best["residual"], 0.0, p.der0,
                                   p.levels, bin_size)
        peak_xtalk = _tail_amplitude(xtalk, 0.0, p.der0,
                                     p.levels, bin_size) if len(xtalk) else 0.0
        reports.append({
            "case": case, "com_db": final["com_db"],
            "fom_db": float(20 * np.log10(best["score"])),
            "a_s_mv": 1e3 * best["a_s"],
            "a_ni_mv": 1e3 * final["a_ni_v"],
            "peak_isi_at_der_mv": 1e3 * peak_isi,
            "peak_xtalk_at_der_mv": 1e3 * peak_xtalk,
            "gaussian_at_der_mv": 1e3 * q * sigma_g,
            "sigma_receiver_mv": 1e3 * sigma_n,
            "sigma_tx_mv": 1e3 * best["sigma_tx"],
            "sigma_rj_mv": 1e3 * best["sigma_rjit"],
            "ctle_gdc_db": best["gdc_db"], "ctle_gdc2_db": best["gdc2_db"],
            "tx_ffe": [float(v) for v in best["taps"]],
            "dfe_taps": [float(v) for v in best["dfe_taps"]],
            "pulse_t_ui": ((np.arange(-10 * sps, 18 * sps) / sps)).tolist(),
            "pulse_v": best["eq"][best["main"] - 10 * sps:
                                  best["main"] + 18 * sps].tolist(),
        })

    valid = [r for r in reports if "com_db" in r]
    if not valid:
        base.update({"model_result": ERROR, "package_cases": reports,
                     "reason": {"it": "la ricerca dell'equalizzatore non ha prodotto casi validi",
                                "en": "equalizer search produced no valid case"},
                     "verdict": verdict(ERROR, basis="model-limit",
                                        evidence="equalizer search produced no valid case")})
        return base
    worst = min(valid, key=lambda r: r["com_db"])
    threshold = (float(lim.limit) if lim.limit is not None
                 and lim.confidence == "published" else p.pass_threshold_db)
    v = evaluate_limit(
        lim, float(worst["com_db"]),
        evidence=(f"worst package case '{worst['case']['name']}': "
                  f"COM {worst['com_db']:.2f} dB vs ≥ {threshold:g} dB "
                  f"(DER₀ {p.der0:g})"))
    base.update({
        "com_db": worst["com_db"], "fom_db": worst["fom_db"],
        "threshold_db": threshold,
        "margin_to_threshold_db": worst["com_db"] - threshold,
        "model_result": PASS if worst["com_db"] >= threshold else FAIL,
        "verdict": v,
        "worst_case": worst, "package_cases": reports,
        "input_kind": ("measured Touchstone victim" if cfg.use_s2p_channel
                       and cfg.s2p_text.strip() else "analytic victim channel"),
        "deviations": [
            "single victim response; no independent NEXT/FEXT S-parameter files",
            "package pad/ball capacitances and full multi-reflection cascade omitted",
            "two-stage search: every (g_DC, g_DC2, TX-FFE) grid point is ranked at "
            "nominal phase; only the FOM leaders receive the fine phase search",
            "asymmetric/floating DFE groups from the reference program are reduced to the prescribed magnitude caps",
            "LabPro analytic aggressors are used only when NEXT/FEXT knobs are enabled",
            "g_DC2/f_LF stage values and the 802.3ck table numbers are quoted from public material (to verify)",
            "no external golden channel with a published COM value has been correlated",
            "therefore the 3 dB comparison is a model diagnostic, never compliance",
        ],
    })
    return base
