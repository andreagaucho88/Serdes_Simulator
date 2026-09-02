"""PCS 64b/66b (struttura di IEEE 802.3 Clause 49): codifica a blocchi,
scrambler sul payload a 64 bit, block lock e monitor dei sync header.

Livello L1 del banco, fra i frame MAC (L2) e il PMA/PHY:

* ogni blocco di 66 bit = sync header (2 bit) + payload (64 bit);
* sync ``01`` = blocco dati (8 ottetti), sync ``10`` = blocco di controllo
  con un byte di tipo: /S/ (0x78, start con 7 ottetti dati), /T0…T7/
  (terminate con k ottetti dati e 7−k idle), /I/ (0x1E, 8 idle);
* il payload dei blocchi è scramblato in modo continuo con il polinomio
  1+x^39+x^58 (49.2.6); i sync header restano in chiaro;
* al RX il block lock (49.2.13.2.2, struttura): si prova ogni offset di
  bit 0…65 e si dichiara lock dopo 64 sync header validi consecutivi; il
  monitor BER dichiara ``hi_ber`` se compaiono ≥16 header non validi nella
  finestra (qui la finestra è il record, non i 125 µs del timer di clause).

DICHIARATO: niente alignment marker, niente transcodifica 256b/257b,
niente distribuzione su più lane, nessun deficit idle counter (l'IPG viene
arrotondato a blocchi /I/ interi).  Il byte 0x55 sostituito dal /S/ viene
reinserito in ricezione, così il flusso di ottetti ricostruito coincide con
quello del MAC a meno degli idle di arrotondamento.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

SYNC_DATA = (0, 1)
SYNC_CTRL = (1, 0)
S_TYPE = 0x78
I_TYPE = 0x1E
T_TYPES = (0x87, 0x99, 0xAA, 0xB4, 0xCC, 0xD2, 0xE1, 0xFF)   # T0 … T7
BLOCK_BITS = 66
LOCK_BLOCKS = 64          # header validi consecutivi per il block lock
HI_BER_THRESHOLD = 16     # header non validi nella finestra → hi_ber


@dataclass
class PcsStats:
    coding: str = "64b66b"
    lock: bool = False
    lock_offset_bits: int = 0
    blocks: int = 0
    sync_header_errors: int = 0
    hi_ber: bool = False
    invalid_types: int = 0
    data_blocks: int = 0
    start_blocks: int = 0
    terminate_blocks: int = 0
    idle_blocks: int = 0
    overhead_pct: float = 100.0 * (BLOCK_BITS - 64) / 64
    first_block_index: int = 0     # indice TX del primo blocco decodificato
    decoded_bytes: int = 0
    note: str = ("64b/66b block lock (49.2.13.2.2 structure), payload scrambler "
                 "1+x^39+x^58; no AM/257b transcoding/lane distribution")


@dataclass
class EncodedStream:
    line_bits: np.ndarray                # header + payload scramblato, per blocco
    frame_blocks: list = field(default_factory=list)   # (start_block, n_blocks, n_body) per frame
    n_blocks: int = 0
    payload_bits_clear: np.ndarray = None


def _scramble_payload(bits: np.ndarray) -> np.ndarray:
    from .ethernet import scramble
    return scramble(bits)


def _descramble_payload(bits: np.ndarray) -> np.ndarray:
    from .ethernet import descramble
    return descramble(bits)


def _bytes_bits(data: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


def encode(frames: list[bytes], ipg_bytes) -> EncodedStream:
    """Codifica una lista di frame (preamble…FCS, senza IPG) in blocchi 66b.

    Ogni frame produce: un blocco /S/, blocchi /D/, un blocco /T_k/ e i
    blocchi /I/ dell'IPG.  Ritorna i bit di linea e, per ogni frame, il
    blocco iniziale e il numero di blocchi occupati (IPG incluso).
    """
    payload = bytearray()
    headers = []
    frame_blocks = []
    ipgs = (list(ipg_bytes) if isinstance(ipg_bytes, (list, tuple))
            else [int(ipg_bytes)] * len(frames))
    for f, ipg_f in zip(frames, ipgs):
        if len(f) < 8:
            raise ValueError("frame troppo corto per un blocco /S/")
        start = len(headers)
        # /S/: il primo ottetto del preamble (0x55) è sostituito dal tipo
        payload += bytes([S_TYPE]) + f[1:8]
        headers.append(SYNC_CTRL)
        rest = f[8:]
        full = len(rest) // 8
        for i in range(full):
            payload += rest[8 * i:8 * i + 8]
            headers.append(SYNC_DATA)
        k = len(rest) - 8 * full          # 0..7 ottetti residui → /T_k/
        payload += bytes([T_TYPES[k]]) + rest[8 * full:] + bytes(7 - k)
        headers.append(SYNC_CTRL)
        # ultimo blocco che porta byte del frame: /T_k/ se k>0, altrimenti
        # l'ultimo /D/ (il /T0/ segna solo la fine)
        n_body = len(headers) - start - (1 if k == 0 else 0)
        # IPG: ottetti idle già coperti dal /T_k/ (7−k), il resto in /I/
        remaining = max(int(ipg_f) - (7 - k), 0)
        n_idle = max(1, (remaining + 7) // 8)
        for _ in range(n_idle):
            payload += bytes([I_TYPE]) + bytes(7)
            headers.append(SYNC_CTRL)
        frame_blocks.append((start, len(headers) - start, n_body))
    clear = _bytes_bits(bytes(payload))
    scrambled = _scramble_payload(clear)
    n_blocks = len(headers)
    out = np.empty(n_blocks * BLOCK_BITS, dtype=np.uint8)
    for b, (h0, h1) in enumerate(headers):
        out[b * BLOCK_BITS] = h0
        out[b * BLOCK_BITS + 1] = h1
        out[b * BLOCK_BITS + 2:(b + 1) * BLOCK_BITS] = scrambled[64 * b:64 * b + 64]
    return EncodedStream(line_bits=out, frame_blocks=frame_blocks,
                         n_blocks=n_blocks, payload_bits_clear=clear)


def _valid_header(h0, h1) -> bool:
    return (h0, h1) in (SYNC_DATA, SYNC_CTRL)


def block_lock(line_bits: np.ndarray, line_offset_bits: int = 0):
    """Cerca l'allineamento dei blocchi (offset 0…65) con 64 header validi
    consecutivi; ritorna (offset, stats).  ``line_offset_bits`` è l'indice
    TX del primo bit ricevuto, per risalire all'indice del blocco."""
    x = np.asarray(line_bits, dtype=np.uint8)
    best = None
    for off in range(BLOCK_BITS):
        n = (len(x) - off) // BLOCK_BITS
        if n < LOCK_BLOCKS:
            break
        h0 = x[off:off + n * BLOCK_BITS:BLOCK_BITS]
        h1 = x[off + 1:off + 1 + n * BLOCK_BITS:BLOCK_BITS]
        valid = (h0 != h1)              # 01 o 10, mai 00/11
        # lock: prima finestra di 64 header validi consecutivi
        run = 0
        locked_at = None
        for i, v in enumerate(valid):
            run = run + 1 if v else 0
            if run >= LOCK_BLOCKS:
                locked_at = i - LOCK_BLOCKS + 1
                break
        errors = int(np.count_nonzero(~valid))
        if locked_at is not None and (best is None or errors < best[2]):
            best = (off, locked_at, errors, n)
            if errors == 0:
                break
    stats = PcsStats()
    if best is None:
        stats.lock = False
        stats.blocks = len(x) // BLOCK_BITS
        stats.sync_header_errors = stats.blocks
        stats.hi_ber = True
        return None, stats
    off, locked_at, errors, n = best
    stats.lock = True
    stats.lock_offset_bits = int(off)
    stats.blocks = int(n)
    stats.sync_header_errors = int(errors)
    stats.hi_ber = errors >= HI_BER_THRESHOLD
    # indice del primo blocco nel dominio TX: il bit di linea (offset+off)
    # cade su un confine di blocco del TX
    stats.first_block_index = int(round((line_offset_bits + off) / BLOCK_BITS))
    return off, stats


def decode(line_bits: np.ndarray, line_offset_bits: int = 0):
    """Block lock + decodifica: ritorna (bytes ricostruiti, PcsStats).

    Gli ottetti ricostruiti seguono il flusso MAC: /S/ → 0x55 + 7 dati,
    /D/ → 8 dati, /T_k/ → k dati + (7−k) zeri, /I/ → 8 zeri.  Header o
    tipi non validi producono 8 zeri (il frame verrà scartato dall'FCS).
    """
    off, stats = block_lock(line_bits, line_offset_bits)
    if off is None:
        return b"", stats
    x = np.asarray(line_bits, dtype=np.uint8)
    n = stats.blocks
    h0 = x[off:off + n * BLOCK_BITS:BLOCK_BITS]
    h1 = x[off + 1:off + 1 + n * BLOCK_BITS:BLOCK_BITS]
    payload = np.empty(n * 64, dtype=np.uint8)
    for b in range(n):
        s = off + b * BLOCK_BITS + 2
        payload[64 * b:64 * b + 64] = x[s:s + 64]
    clear = _descramble_payload(payload)
    data = np.packbits(clear).tobytes()
    out = bytearray()
    for b in range(n):
        blk = data[8 * b:8 * b + 8]
        if h0[b] == 0 and h1[b] == 1:
            out += blk
            stats.data_blocks += 1
        elif h0[b] == 1 and h1[b] == 0:
            t = blk[0]
            if t == S_TYPE:
                out += bytes([0x55]) + blk[1:8]
                stats.start_blocks += 1
            elif t == I_TYPE:
                out += bytes(8)
                stats.idle_blocks += 1
            elif t in T_TYPES:
                k = T_TYPES.index(t)
                out += blk[1:1 + k] + bytes(7 - k)
                stats.terminate_blocks += 1
            else:
                out += bytes(8)
                stats.invalid_types += 1
        else:
            out += bytes(8)
    stats.decoded_bytes = len(out)
    return bytes(out), stats
