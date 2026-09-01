"""FEC RS(544,514) su GF(2^10) — codec algebricamente reale (dal builder v7).

Implementa davvero: campo GF(2^10) con primitivo x^10+x^3+1, generatore
g(x)=prod_{j=0}^{29}(x-alpha^j), encoder sistematico, syndrome,
Berlekamp-Massey, Chien search e soluzione delle magnitudini, con correzione
verificata da 0 a 15 symbol errors.

NON implementa il PCS Ethernet (scrambler, AM, bit packing, interleaving):
è un codec RS reale, non una dichiarazione di conformità.

Per il link: lo stimolo PRBS non è RS-encoded, quindi l'analisi di link misura
il *pattern d'errore* e chiede "questo pattern sarebbe stato correggibile da
RS(544,514)?" — è lo stesso modo in cui si stima il FEC gain da una misura di
raw BER, e va dichiarato.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import stats

GF_M = 10
GF_SIZE = 1 << GF_M
GF_ORDER = GF_SIZE - 1
GF_PRIMITIVE = 0x409  # x^10 + x^3 + 1

_gf_exp = np.zeros(2 * GF_ORDER, dtype=np.int64)
_gf_log = np.full(GF_SIZE, -1, dtype=np.int64)
_x = 1
for _i in range(GF_ORDER):
    _gf_exp[_i] = _x
    _gf_log[_x] = _i
    _x <<= 1
    if _x & GF_SIZE:
        _x ^= GF_PRIMITIVE
    _x &= GF_ORDER
_gf_exp[GF_ORDER:] = _gf_exp[:GF_ORDER]

gf_exp = _gf_exp
gf_log = _gf_log


def gf_mul(a, b):
    a, b = int(a), int(b)
    return 0 if a == 0 or b == 0 else int(gf_exp[gf_log[a] + gf_log[b]])


def gf_div(a, b):
    a, b = int(a), int(b)
    if b == 0:
        raise ZeroDivisionError("GF division by zero")
    return 0 if a == 0 else int(gf_exp[(gf_log[a] - gf_log[b]) % GF_ORDER])


def gf_inverse(a):
    return gf_div(1, a)


def gf_alpha(power):
    return int(gf_exp[power % GF_ORDER])


def gf_poly_mul(p, q):
    out = [0] * (len(p) + len(q) - 1)
    for i, a in enumerate(p):
        for j, b in enumerate(q):
            out[i + j] ^= gf_mul(a, b)
    return out


def gf_poly_eval_desc(poly, value):
    y = 0
    for coefficient in poly:
        y = gf_mul(y, value) ^ int(coefficient)
    return y


def gf_poly_eval_asc(poly, value):
    y, power = 0, 1
    for coefficient in poly:
        y ^= gf_mul(coefficient, power)
        power = gf_mul(power, value)
    return y


RS_N, RS_K, RS_PARITY, RS_T = 544, 514, 30, 15


def rs_generator(nsym=RS_PARITY):
    g = [1]
    for j in range(nsym):
        g = gf_poly_mul(g, [1, gf_alpha(j)])
    return g


RS_GENERATOR = rs_generator()


def rs_encode(message):
    message = [int(v) for v in message]
    if len(message) != RS_K or any(v < 0 or v >= GF_SIZE for v in message):
        raise ValueError("message: 514 simboli GF(2^10)")
    work = message + [0] * RS_PARITY
    for i in range(RS_K):
        coefficient = work[i]
        if coefficient:
            for j in range(1, len(RS_GENERATOR)):
                work[i + j] ^= gf_mul(RS_GENERATOR[j], coefficient)
    return np.asarray(message + work[RS_K:], dtype=np.int64)


def rs_syndromes(codeword):
    return np.asarray([gf_poly_eval_desc(codeword, gf_alpha(j))
                       for j in range(RS_PARITY)], dtype=np.int64)


def berlekamp_massey(syndrome):
    N = len(syndrome)
    C = [1] + [0] * N
    B = [1] + [0] * N
    L, m, b = 0, 1, 1
    for n in range(N):
        discrepancy = int(syndrome[n])
        for i in range(1, L + 1):
            discrepancy ^= gf_mul(C[i], syndrome[n - i])
        if discrepancy == 0:
            m += 1
            continue
        T = C.copy()
        scale = gf_div(discrepancy, b)
        for i in range(N + 1 - m):
            C[i + m] ^= gf_mul(scale, B[i])
        if 2 * L <= n:
            L = n + 1 - L
            B, b, m = T, discrepancy, 1
        else:
            m += 1
    return C[:L + 1]


def find_error_positions(locator, n=RS_N):
    positions = []
    for position in range(n):
        X = gf_alpha(n - 1 - position)
        if gf_poly_eval_asc(locator, gf_inverse(X)) == 0:
            positions.append(position)
    return positions


def gf_solve(A, b):
    A = [[int(v) for v in row] for row in A]
    b = [int(v) for v in b]
    n = len(b)
    aug = [A[i] + [b[i]] for i in range(n)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if aug[r][col] != 0), None)
        if pivot is None:
            raise ValueError("singular GF system")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        inv = gf_inverse(aug[col][col])
        aug[col] = [gf_mul(v, inv) for v in aug[col]]
        for row in range(n):
            if row == col:
                continue
            factor = aug[row][col]
            if factor:
                aug[row] = [v ^ gf_mul(factor, p) for v, p in zip(aug[row], aug[col])]
    return [aug[i][-1] for i in range(n)]


def rs_decode(received):
    """Ritorna (codeword corretto, n errori corretti); solleva oltre capacità."""
    received = np.asarray(received, dtype=np.int64).copy()
    syndrome = rs_syndromes(received)
    if not np.any(syndrome):
        return received, 0
    locator = berlekamp_massey(syndrome)
    errors = len(locator) - 1
    if errors > RS_T:
        raise ValueError("oltre capacità t=15")
    positions = find_error_positions(locator, len(received))
    if len(positions) != errors:
        raise ValueError("Chien search incoerente: pattern non correggibile")
    X = [gf_alpha(len(received) - 1 - pos) for pos in positions]
    vandermonde = [[gf_alpha(0) if row == 0 else gf_alpha((gf_log[xv] * row) % GF_ORDER)
                    for xv in X] for row in range(errors)]
    magnitudes = gf_solve(vandermonde, syndrome[:errors])
    for position, magnitude in zip(positions, magnitudes):
        received[position] ^= magnitude
    if np.any(rs_syndromes(received)):
        raise ValueError("correzione fallita")
    return received, errors


# ---------------------------------------------------------------------------
# Demo del codec (per la GUI e il selftest)
# ---------------------------------------------------------------------------

def codec_demo(error_counts=(0, 1, 5, 10, 15, 16), seed=7):
    """Inietta N symbol errors e prova a decodificare. Oltre t=15 il decoder
    bounded-distance deve dichiarare failure (o, raramente, miscorreggere)."""
    rng = np.random.default_rng(seed)
    message = rng.integers(0, GF_SIZE, RS_K, dtype=np.int64)
    codeword = rs_encode(message)
    assert not np.any(rs_syndromes(codeword))
    rows = []
    for count in error_counts:
        corrupted = codeword.copy()
        positions = rng.choice(RS_N, count, replace=False)
        magnitudes = rng.integers(1, GF_SIZE, count)
        corrupted[positions] ^= magnitudes
        try:
            corrected, n_corrected = rs_decode(corrupted)
            rows.append({
                "symbol_errors_iniettati": int(count),
                "esito": "corretto" if np.array_equal(corrected, codeword)
                         else "MISCORREZIONE",
                "correzioni_riportate": int(n_corrected),
            })
        except ValueError as exc:
            rows.append({
                "symbol_errors_iniettati": int(count),
                "esito": f"failure dichiarata ({exc})",
                "correzioni_riportate": 0,
            })
    return rows


# ---------------------------------------------------------------------------
# Analisi di link: il pattern d'errore misurato sarebbe correggibile?
# ---------------------------------------------------------------------------

@dataclass
class FecAnalysis:
    n_bits: int
    bit_errors: int
    pre_fec_ber: float
    n_symbols_10b: int
    symbol_errors: int
    symbol_error_rate: float
    q_iid_from_ber: float          # q = 1-(1-p)^10 sotto ipotesi iid
    n_frames: int                  # frame completi da 544 simboli
    errors_per_frame: np.ndarray
    frames_uncorrectable: int      # frame con >15 symbol errors
    flr_measured: float            # frame loss ratio sul record
    fer_iid_model: float           # P[X>15], X~Bin(544, q_iid)
    fer_iid_model_qmeas: float     # idem con q misurata
    # burstiness del pattern d'errore
    error_gap_bits: np.ndarray = field(default_factory=lambda: np.array([]))
    max_consecutive_symbol_errors: int = 0

    @property
    def burstiness_ratio(self) -> float:
        """SER misurata / q attesa da BER iid.

        Se i bit errati si RAGGRUPPANO negli stessi simboli da 10 bit, la SER
        risulta più bassa dell'attesa iid → rapporto < 1 = bursty;
        ≈ 1 = compatibile con errori indipendenti."""
        if self.q_iid_from_ber <= 0:
            return float("nan")
        return self.symbol_error_rate / self.q_iid_from_ber


def analyze_link_fec(true_bits, decided_bits) -> FecAnalysis:
    true_bits = np.asarray(true_bits, dtype=np.uint8)
    decided_bits = np.asarray(decided_bits, dtype=np.uint8)
    error_pattern = (true_bits != decided_bits)
    n_bits = len(error_pattern)
    bit_errors = int(error_pattern.sum())
    p = bit_errors / max(n_bits, 1)

    # simboli RS da 10 bit
    n_sym = n_bits // GF_M
    sym_err = error_pattern[: n_sym * GF_M].reshape(-1, GF_M).any(axis=1)
    symbol_errors = int(sym_err.sum())
    ser = symbol_errors / max(n_sym, 1)
    q_iid = float(-np.expm1(GF_M * np.log1p(-p))) if p < 1 else 1.0

    # frame RS(544,...): il pattern d'errore per codeword
    n_frames = n_sym // RS_N
    if n_frames:
        errors_per_frame = sym_err[: n_frames * RS_N].reshape(-1, RS_N).sum(axis=1)
    else:
        errors_per_frame = np.zeros(0, dtype=int)
    frames_bad = int(np.sum(errors_per_frame > RS_T))

    # burst: gap fra bit errati e run di simboli errati consecutivi
    positions = np.flatnonzero(error_pattern)
    gaps = np.diff(positions) if len(positions) > 1 else np.array([])
    max_run = 0
    run = 0
    for e in sym_err:
        run = run + 1 if e else 0
        max_run = max(max_run, run)

    return FecAnalysis(
        n_bits=n_bits, bit_errors=bit_errors, pre_fec_ber=p,
        n_symbols_10b=n_sym, symbol_errors=symbol_errors,
        symbol_error_rate=ser, q_iid_from_ber=q_iid,
        n_frames=n_frames, errors_per_frame=errors_per_frame,
        frames_uncorrectable=frames_bad,
        flr_measured=frames_bad / n_frames if n_frames else float("nan"),
        fer_iid_model=float(stats.binom.sf(RS_T, RS_N, q_iid)),
        fer_iid_model_qmeas=float(stats.binom.sf(RS_T, RS_N, ser)),
        error_gap_bits=gaps,
        max_consecutive_symbol_errors=max_run,
    )


# ---------------------------------------------------------------------------
# Codec RS parametrico su GF(2^10): KP4 = RS(544,514), KR4 = RS(528,514)
# ---------------------------------------------------------------------------

class RSCodec:
    """Reed-Solomon (n, k) su GF(2^10), stessa algebra del codec KP4 sopra."""

    def __init__(self, n: int, k: int, name: str = ""):
        if not (0 < k < n <= GF_ORDER):
            raise ValueError("richiesto 0 < k < n <= 1023")
        self.n, self.k = n, k
        self.parity = n - k
        self.t = self.parity // 2
        self.name = name or f"RS({n},{k})"
        self.generator = rs_generator(self.parity)

    def encode(self, message):
        message = [int(v) for v in message]
        if len(message) != self.k or any(v < 0 or v >= GF_SIZE for v in message):
            raise ValueError(f"message: {self.k} simboli GF(2^10)")
        work = message + [0] * self.parity
        for i in range(self.k):
            coefficient = work[i]
            if coefficient:
                for j in range(1, len(self.generator)):
                    work[i + j] ^= gf_mul(self.generator[j], coefficient)
        return np.asarray(message + work[self.k:], dtype=np.int64)

    def syndromes(self, codeword):
        return np.asarray([gf_poly_eval_desc(codeword, gf_alpha(j))
                           for j in range(self.parity)], dtype=np.int64)

    def decode(self, received):
        """(codeword corretto, n correzioni); ValueError oltre capacità."""
        received = np.asarray(received, dtype=np.int64).copy()
        syndrome = self.syndromes(received)
        if not np.any(syndrome):
            return received, 0
        locator = berlekamp_massey(syndrome)
        errors = len(locator) - 1
        if errors > self.t:
            raise ValueError(f"oltre capacità t={self.t}")
        positions = find_error_positions(locator, self.n)
        if len(positions) != errors:
            raise ValueError("Chien search incoerente: pattern non correggibile")
        X = [gf_alpha(self.n - 1 - pos) for pos in positions]
        vandermonde = [[gf_alpha(0) if row == 0
                        else gf_alpha((gf_log[xv] * row) % GF_ORDER)
                        for xv in X] for row in range(errors)]
        magnitudes = gf_solve(vandermonde, syndrome[:errors])
        for position, magnitude in zip(positions, magnitudes):
            received[position] ^= magnitude
        if np.any(self.syndromes(received)):
            raise ValueError("correzione fallita")
        return received, errors


KP4 = RSCodec(544, 514, "RS(544,514) 'KP4'")
KR4 = RSCodec(528, 514, "RS(528,514) 'KR4'")

FEC_CODECS = {"kp4": KP4, "kr4": KR4}


# ---------------------------------------------------------------------------
# FEC nel percorso: encode del flusso TX, decode del flusso deciso al RX
# ---------------------------------------------------------------------------

def bits_to_gf_symbols(bits):
    bits = np.asarray(bits, dtype=np.int64)
    n_sym = len(bits) // GF_M
    weights = 1 << np.arange(GF_M - 1, -1, -1)
    return bits[: n_sym * GF_M].reshape(-1, GF_M) @ weights


def gf_symbols_to_bits(symbols):
    symbols = np.asarray(symbols, dtype=np.int64)
    out = np.zeros((len(symbols), GF_M), dtype=np.uint8)
    for b in range(GF_M):
        out[:, GF_M - 1 - b] = (symbols >> b) & 1
    return out.reshape(-1)


def encode_stream(payload_bits, codec: RSCodec, n_frames: int):
    """Codifica n_frames sistematici; ritorna i bit del flusso codificato.

    Serve k·10 bit di payload per frame; l'allineamento di frame è ideale
    (dichiarato: niente AM/scrambler di clause)."""
    need = n_frames * codec.k * GF_M
    payload_bits = np.asarray(payload_bits, dtype=np.uint8)
    if len(payload_bits) < need:
        raise ValueError(f"servono {need} bit di payload")
    messages = bits_to_gf_symbols(payload_bits[:need]).reshape(n_frames, codec.k)
    coded = np.concatenate([codec.encode(m) for m in messages])
    return gf_symbols_to_bits(coded)


@dataclass
class FecLinkResult:
    codec_name: str
    n_frames: int
    frames_clean: int          # syndrome nullo
    frames_corrected: int      # corretti E verificati identici al TX
    frames_uncorrectable: int  # failure dichiarata dal decoder
    frames_miscorrected: int   # il decoder ha "corretto" verso un ALTRO
                               # codeword valido (possibile oltre t, silenzioso
                               # per il decoder: rilevabile solo col TX noto)
    symbols_corrected: int
    pre_fec_bit_errors: int
    post_fec_bit_errors: int
    pre_fec_ber: float
    post_fec_ber: float
    errors_per_frame: np.ndarray   # symbol errors reali (dal confronto col TX)
    post_payload_bits: np.ndarray = None   # payload decodificato (per L2)


def interleave_symbols(coded_bits, codec: "RSCodec", depth: int):
    """Codeword interleaving a livello di simbolo RS (10 bit), come in
    802.3ck/dj: i simboli di `depth` codeword consecutive vengono alternati
    sulla linea (A0 B0 A1 B1 …). Un burst di linea lungo L simboli si
    ripartisce quindi in ~L/depth simboli per codeword: è ESATTAMENTE il
    motivo per cui lo standard interleava. I frame di coda oltre l'ultimo
    gruppo completo restano non interleavati (dichiarato)."""
    depth = int(depth)
    if depth <= 1:
        return np.asarray(coded_bits, dtype=np.uint8)
    bits = np.asarray(coded_bits, dtype=np.uint8)
    fb = codec.n * GF_M
    n_frames = len(bits) // fb
    g = n_frames // depth
    if g == 0:
        return bits
    head = bits[:g * depth * fb].reshape(g, depth, codec.n, GF_M)
    inter = head.transpose(0, 2, 1, 3).reshape(-1)
    return np.concatenate([inter, bits[g * depth * fb:]])


def deinterleave_symbols(line_bits, codec: "RSCodec", depth: int):
    """Inversa esatta di interleave_symbols (stessa geometria)."""
    depth = int(depth)
    if depth <= 1:
        return np.asarray(line_bits, dtype=np.uint8)
    bits = np.asarray(line_bits, dtype=np.uint8)
    fb = codec.n * GF_M
    n_frames = len(bits) // fb
    g = n_frames // depth
    if g == 0:
        return bits
    head = bits[:g * depth * fb].reshape(g, codec.n, depth, GF_M)
    deint = head.transpose(0, 2, 1, 3).reshape(-1)
    return np.concatenate([deint, bits[g * depth * fb:]])


def decode_stream(decided_bits, tx_coded_bits, codec: RSCodec,
                  n_frames: int) -> FecLinkResult:
    """Decodifica il flusso deciso frame per frame e confronta col trasmesso.

    La categoria `miscorrected` esiste solo perché il banco conosce il TX:
    su hardware reale una miscorrezione è indistinguibile da un frame buono
    (è il motivo per cui si parla di undetected error rate)."""
    frame_bits = codec.n * GF_M
    decided = np.asarray(decided_bits, dtype=np.uint8)[: n_frames * frame_bits]
    tx = np.asarray(tx_coded_bits, dtype=np.uint8)[: n_frames * frame_bits]
    rx_frames = bits_to_gf_symbols(decided).reshape(n_frames, codec.n)
    tx_frames = bits_to_gf_symbols(tx).reshape(n_frames, codec.n)

    clean = corrected = uncorrectable = miscorrected = sym_corr = 0
    post_bits = []
    errors_per_frame = np.zeros(n_frames, dtype=int)
    for i in range(n_frames):
        errors_per_frame[i] = int(np.count_nonzero(rx_frames[i] != tx_frames[i]))
        try:
            fixed, n_corr = codec.decode(rx_frames[i])
            if not np.array_equal(fixed, tx_frames[i]):
                miscorrected += 1     # codeword valido ma SBAGLIATO
            elif n_corr == 0:
                clean += 1
            else:
                corrected += 1
                sym_corr += n_corr
            post_bits.append(gf_symbols_to_bits(fixed[:codec.k]))
        except ValueError:
            uncorrectable += 1
            # bounded-distance failure: il frame passa non corretto
            post_bits.append(gf_symbols_to_bits(rx_frames[i][:codec.k]))
    post = np.concatenate(post_bits)
    payload_tx = np.concatenate([gf_symbols_to_bits(f[:codec.k])
                                 for f in tx_frames])
    pre_err = int(np.count_nonzero(decided != tx))
    post_err = int(np.count_nonzero(post != payload_tx))
    return FecLinkResult(
        codec_name=codec.name, n_frames=n_frames,
        frames_clean=clean, frames_corrected=corrected,
        frames_uncorrectable=uncorrectable,
        frames_miscorrected=miscorrected, symbols_corrected=sym_corr,
        pre_fec_bit_errors=pre_err, post_fec_bit_errors=post_err,
        pre_fec_ber=pre_err / max(len(tx), 1),
        post_fec_ber=post_err / max(len(payload_tx), 1),
        errors_per_frame=errors_per_frame,
        post_payload_bits=post,
    )


def fer_curve(raw_ber_grid, n=RS_N, t=RS_T, m=GF_M):
    """Curva teorica iid: raw BER -> (q simbolo, FER RS(n, n-2t) su GF(2^m)).

    Default RS(544,514); con n=528, t=7 modella RS(528,514) 'KR4'."""
    raw = np.asarray(raw_ber_grid)
    q = -np.expm1(m * np.log1p(-raw))
    return q, stats.binom.sf(t, n, q)


def prefec_ber_threshold(target_fer=1e-13, n=RS_N, t=RS_T, m=GF_M):
    """BER pre-FEC a cui la FER iid scende sotto target (modello binomiale)."""
    grid = np.logspace(-7, -1.2, 600)
    _, fer = fer_curve(grid, n=n, t=t, m=m)
    idx = int(np.searchsorted(fer, target_fer))
    return float(grid[min(idx, len(grid) - 1)])
