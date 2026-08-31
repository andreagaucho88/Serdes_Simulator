"""Analisi jitter/TIE: crossing detection, istogramma, spettro, stime RJ/DJ.

Il TIE è misurato ai crossing di una soglia di riferimento (come su uno scope):
per PAM4 i crossing della soglia centrale portano un DDJ pattern-dependent
enorme — è fisica, non un bug — e l'istogramma multimodale lo mostra.
Le stime RJ/DJ sono un fit dual-Dirac dichiaratamente grezzo.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class TieResult:
    edge_symbol: np.ndarray     # indice UI (float) di ciascun crossing
    tie_ui: np.ndarray          # TIE in UI
    tie_rms_ui: float
    tie_pp_ui: float
    rj_rms_ui_est: float        # stima dual-Dirac grezza
    dj_pp_ui_est: float
    n_edges: int
    # spettro del TIE ricampionato per-UI
    spec_freq_mhz: np.ndarray
    spec_mag_ui: np.ndarray


def tie_analysis(wave, sps, symbol_rate_hz, threshold=None,
                 delay_ui=0.0) -> TieResult:
    x = np.asarray(wave, dtype=float)
    thr = float(np.mean(x)) if threshold is None else float(threshold)
    s = x - thr
    sign = s > 0
    idx = np.flatnonzero(sign[:-1] != sign[1:])
    if len(idx) < 8:
        raise ValueError("troppi pochi crossing per l'analisi TIE")
    frac = s[idx] / (s[idx] - s[idx + 1])
    t_cross_ui = (idx + frac) / sps            # tempo del crossing in UI
    # riferimento: i boundary di simbolo cadono a k + delay
    rel = t_cross_ui - delay_ui
    tie_ui = rel - np.round(rel)
    # scarta outlier estremi (crossing spuri da rumore lontani dal boundary)
    keep = np.abs(tie_ui) < 0.5
    t_cross_ui, tie_ui = t_cross_ui[keep], tie_ui[keep]

    tie_rms = float(np.std(tie_ui))
    tie_pp = float(np.max(tie_ui) - np.min(tie_ui))

    # stima dual-Dirac GREZZA: separa le due metà attorno alla mediana;
    # DJ = distanza dei baricentri, RJ = sigma media delle metà.
    med = np.median(tie_ui)
    left, right = tie_ui[tie_ui <= med], tie_ui[tie_ui > med]
    if len(left) > 4 and len(right) > 4:
        dj_pp = float(np.mean(right) - np.mean(left))
        rj = float(0.5 * (np.std(left) + np.std(right)))
    else:
        dj_pp, rj = 0.0, tie_rms

    # spettro: TIE medio per UI su griglia uniforme (buchi interpolati)
    n_ui = int(np.ceil(t_cross_ui.max())) + 1
    slot = np.round(t_cross_ui - delay_ui).astype(int)
    slot = np.clip(slot, 0, n_ui - 1)
    acc = np.zeros(n_ui)
    cnt = np.zeros(n_ui)
    np.add.at(acc, slot, tie_ui)
    np.add.at(cnt, slot, 1)
    have = cnt > 0
    series = np.interp(np.arange(n_ui), np.flatnonzero(have),
                       acc[have] / cnt[have])
    series = series - np.mean(series)
    win = np.hanning(len(series))
    spec = np.abs(np.fft.rfft(series * win)) / max(np.sum(win) / 2, 1)
    freqs = np.fft.rfftfreq(len(series), d=1.0) * symbol_rate_hz  # Hz

    return TieResult(
        edge_symbol=t_cross_ui, tie_ui=tie_ui,
        tie_rms_ui=tie_rms, tie_pp_ui=tie_pp,
        rj_rms_ui_est=rj, dj_pp_ui_est=dj_pp,
        n_edges=int(len(tie_ui)),
        spec_freq_mhz=freqs / 1e6, spec_mag_ui=spec,
    )
