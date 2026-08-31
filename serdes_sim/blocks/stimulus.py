"""Stimolo: generatori PRBS (7/9/11/13/15/23/31) e modulazioni NRZ / PAM4.

PRBS13 usa il polinomio pubblico associato a PRBS13Q,
G(x)=1+x+x^2+x^12+x^13 (identico al notebook v7). Gli altri ordini usano i
polinomi ITU-T O.150 / uso comune indicati accanto ai tap.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

PRBS13_PERIOD = 2 ** 13 - 1

# offsets della ricorrenza: nuovo bit = XOR di out[i+off] con i = len(out)-ordine
# (forma delay-line; il primo offset è sempre 0)
PRBS_TAPS = {
    7: (0, 1),        # x^7 + x^6 + 1
    9: (0, 4),        # x^9 + x^5 + 1
    11: (0, 2),       # x^11 + x^9 + 1
    13: (0, 1, 2, 12),  # 1 + x + x^2 + x^12 + x^13 (PRBS13Q-style)
    15: (0, 1),       # x^15 + x^14 + 1
    23: (0, 5),       # x^23 + x^18 + 1
    31: (0, 3),       # x^31 + x^28 + 1
}

PRBS_POLY_LABEL = {
    7: "x⁷+x⁶+1",
    9: "x⁹+x⁵+1",
    11: "x¹¹+x⁹+1",
    13: "1+x+x²+x¹²+x¹³ (PRBS13Q)",
    15: "x¹⁵+x¹⁴+1",
    23: "x²³+x¹⁸+1",
    31: "x³¹+x²⁸+1",
}


def prbs_bits(order, n_bits, seed=None):
    """Ricorrenza PRBS generica; il seed tutto-zero non è valido."""
    if order not in PRBS_TAPS:
        raise ValueError(f"ordine PRBS non supportato: {order}")
    offsets = PRBS_TAPS[order]
    state = [1] * order if seed is None else [int(v) for v in seed]
    if len(state) != order or not any(state) or any(v not in (0, 1) for v in state):
        raise ValueError(f"seed: {order} bit binari, non tutti zero")
    out = state.copy()
    while len(out) < n_bits:
        i = len(out) - order
        bit = 0
        for off in offsets:
            bit ^= out[i + off]
        out.append(bit)
    return np.asarray(out[:n_bits], dtype=np.uint8)


def prbs13_bits(n_bits, seed=None):
    """Compatibilità con il notebook v7."""
    return prbs_bits(13, n_bits, seed)


# ---------------------------------------------------------------------------
# Modulazioni
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModulationSpec:
    name: str          # "NRZ" | "PAM4"
    mapping: str       # "gray" | "binary" | "" (NRZ)
    levels: tuple      # livelli normalizzati, crescenti
    bits: tuple        # per ciascun livello, la tupla di bit (MSB..LSB)

    @property
    def bits_per_symbol(self) -> int:
        return len(self.bits[0])

    @property
    def levels_array(self) -> np.ndarray:
        return np.asarray(self.levels)

    @property
    def bit_array(self) -> np.ndarray:
        return np.asarray(self.bits, dtype=np.uint8)

    @property
    def label(self) -> str:
        return self.name if not self.mapping else f"{self.name} {self.mapping}"


NRZ = ModulationSpec("NRZ", "", (-1.0, 1.0), ((0,), (1,)))
# livelli in ordine crescente; bits[i] = etichetta del livello i
PAM4_GRAY = ModulationSpec("PAM4", "gray", (-1.0, -1 / 3, 1 / 3, 1.0),
                           ((0, 0), (0, 1), (1, 1), (1, 0)))
PAM4_BINARY = ModulationSpec("PAM4", "binary", (-1.0, -1 / 3, 1 / 3, 1.0),
                             ((0, 0), (0, 1), (1, 0), (1, 1)))

MODULATIONS = {
    ("NRZ", ""): NRZ,
    ("PAM4", "gray"): PAM4_GRAY,
    ("PAM4", "binary"): PAM4_BINARY,
}


def get_modulation(name: str, mapping: str = "gray") -> ModulationSpec:
    if name == "NRZ":
        return NRZ
    spec = MODULATIONS.get((name, mapping))
    if spec is None:
        raise ValueError(f"modulazione non supportata: {name}/{mapping}")
    return spec


def symbols_from_bits(bits: np.ndarray, spec: ModulationSpec) -> np.ndarray:
    """Mappa il flusso binario sui livelli secondo la label bits di ciascun livello."""
    bps = spec.bits_per_symbol
    n_symbols = len(bits) // bps
    groups = bits[: n_symbols * bps].reshape(-1, bps)
    # indice binario del gruppo (MSB per primo)
    weights = 2 ** np.arange(bps - 1, -1, -1)
    binary_index = groups @ weights
    # lookup: per ogni pattern binario, quale livello lo porta
    lookup = np.empty(2 ** bps)
    for level_idx, pattern in enumerate(spec.bits):
        lookup[int(np.dot(pattern, weights))] = spec.levels[level_idx]
    return lookup[binary_index]


def generate_stimulus(n_symbols: int, prbs_order: int,
                      spec: ModulationSpec) -> np.ndarray:
    bits = prbs_bits(prbs_order, spec.bits_per_symbol * n_symbols)
    return symbols_from_bits(bits, spec)


def clock_pattern_bits(n_bits: int, spec: ModulationSpec,
                       half_period_ui: int = 1) -> np.ndarray:
    """Pattern clock da BERT: alterna livello minimo e massimo ogni
    half_period_ui simboli (clock2 = 0101…, clock8 = 4 bassi + 4 alti)."""
    bps = spec.bits_per_symbol
    lo = np.asarray(spec.bits[0], dtype=np.uint8)
    hi = np.asarray(spec.bits[-1], dtype=np.uint8)
    n_symbols = n_bits // bps + 1
    sym_bits = np.empty((n_symbols, bps), dtype=np.uint8)
    phase = (np.arange(n_symbols) // half_period_ui) % 2
    sym_bits[phase == 0] = lo
    sym_bits[phase == 1] = hi
    return sym_bits.reshape(-1)[:n_bits]


# ---------------------------------------------------------------------------
# Utility su simboli (parametrizzate sui livelli)
# ---------------------------------------------------------------------------

# Compatibilità v7 (PAM4 Gray)
GRAY_LEVELS = PAM4_GRAY.levels_array
GRAY_BITS = PAM4_GRAY.bit_array


def nearest_level_index(x, levels=GRAY_LEVELS):
    return np.argmin(np.abs(np.asarray(x)[..., None] - np.asarray(levels)), axis=-1)


def hard_slice(x, levels=GRAY_LEVELS):
    levels = np.asarray(levels)
    return levels[nearest_level_index(x, levels)]


def symbols_to_bits(symbols, spec: ModulationSpec) -> np.ndarray:
    return spec.bit_array[nearest_level_index(symbols, spec.levels_array)].reshape(-1)


def symbols_to_gray_bits(symbols):
    """Compatibilità v7."""
    return symbols_to_bits(symbols, PAM4_GRAY)


def level_occupancy(symbols, levels=GRAY_LEVELS):
    return np.array([(symbols == level).sum() for level in np.asarray(levels)])


def transition_matrix(symbols, levels=GRAY_LEVELS):
    """Matrice di probabilità di transizione fra livelli consecutivi."""
    levels = np.asarray(levels)
    n = len(levels)
    idx = nearest_level_index(symbols, levels)
    counts = np.zeros((n, n), dtype=int)
    np.add.at(counts, (idx[:-1], idx[1:]), 1)
    with np.errstate(invalid="ignore"):
        probability = counts / np.maximum(counts.sum(axis=1, keepdims=True), 1)
    return counts, probability
