"""Livello L2-lite: traffic generator/analyzer Ethernet sopra il PHY simulato.

Il payload del link (al posto del PRBS) diventa un flusso di frame:
[preamble 7B + SFD][DA 6B][SA 6B][EtherType 2B][seq 4B + payload][FCS 4B][IPG 12B]

- FCS = CRC-32 (zlib) sui byte del frame (bit ordering semplificato, dichiarato);
- il numero di sequenza nel payload permette di contare i frame PERSI;
- al RX (dopo slicer ed eventuale FEC) l'analyzer DELINEA cercando il
  preamble+SFD (niente indice magico), verifica l'FCS e ricostruisce le
  sequenze → frame ok / FCS errati / persi / throughput.

Cosa NON è (dichiarato): niente 64b/66b, alignment marker, scrambler di
clause, MAC scheduling, QoS, RFC 2544, AN/LT, CMIS — vedi roadmap.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass

import numpy as np

PREAMBLE = bytes([0x55] * 7 + [0xD5])
HEADER = bytes.fromhex("FFFFFFFFFFFF") + bytes.fromhex("021B331C0DA0") + b"\x88\xB5"
IPG = bytes(12)
OVERHEAD = len(PREAMBLE) + len(HEADER) + 4 + len(IPG)  # + FCS


def _bytes_to_bits(data: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


def _bits_to_bytes(bits: np.ndarray) -> bytes:
    n = len(bits) // 8 * 8
    return np.packbits(bits[:n].astype(np.uint8)).tobytes()


def build_frame(seq: int, frame_bytes: int) -> bytes:
    payload_len = max(frame_bytes - len(HEADER) - 4, 8)
    payload = seq.to_bytes(4, "big") + bytes(
        (seq + i) & 0xFF for i in range(payload_len - 4))
    body = HEADER + payload
    fcs = zlib.crc32(body).to_bytes(4, "big")
    return PREAMBLE + body + fcs + IPG


def build_stream_bits(n_bits: int, frame_bytes: int, seq0: int = 0):
    """Flusso di frame per riempire n_bits; ritorna (bits, n_frame, next_seq)."""
    chunks = []
    total = 0
    seq = seq0
    frame_len_bits = (frame_bytes + OVERHEAD - len(HEADER) - 4) * 8
    while total < n_bits:
        f = build_frame(seq, frame_bytes)
        chunks.append(f)
        total += len(f) * 8
        seq += 1
    bits = _bytes_to_bits(b"".join(chunks))[:n_bits]
    return bits, seq - seq0, seq


@dataclass
class L2Analysis:
    frames_expected: int      # frame interamente contenuti nella finestra
    frames_detected: int      # preamble+SFD trovati
    frames_ok: int            # FCS corretto
    frames_fcs_bad: int
    frames_lost: int          # sequenze attese mai viste con FCS ok
    throughput_gbps: float    # payload utile / durata della finestra
    line_rate_gbps: float
    seq_seen: int


def analyze_stream_bits(rx_bits: np.ndarray, frame_bytes: int,
                        window_s: float, seq0: int = 0) -> L2Analysis:
    """Delineazione tipo analyzer: caccia al preamble+SFD, verifica FCS,
    ricostruzione delle sequenze. rx_bits deve essere allineato al byte 0
    del flusso TX (l'allineamento arriva dal pattern lock del PHY)."""
    data = _bits_to_bytes(np.asarray(rx_bits, dtype=np.uint8))
    body_len = len(HEADER) + max(frame_bytes - len(HEADER) - 4, 8) + 4
    frame_len = len(PREAMBLE) + body_len + len(IPG)
    expected = len(data) // frame_len

    detected = ok = bad = 0
    seqs = set()
    i = 0
    sfd = PREAMBLE[-2:]
    while i < len(data) - body_len - 2:
        j = data.find(sfd, i)
        if j < 0:
            break
        start = j + 2
        if start + body_len > len(data):
            break
        detected += 1
        body = data[start:start + body_len - 4]
        fcs = data[start + body_len - 4:start + body_len]
        if zlib.crc32(body).to_bytes(4, "big") == fcs:
            ok += 1
            seqs.add(int.from_bytes(body[len(HEADER):len(HEADER) + 4], "big"))
        else:
            bad += 1
        i = start + body_len
    expected = max(expected, detected)
    lost = sum(1 for s in range(seq0, seq0 + expected) if s not in seqs)
    payload_bits_ok = ok * (frame_bytes - len(HEADER) - 4) * 8
    return L2Analysis(
        frames_expected=expected, frames_detected=detected,
        frames_ok=ok, frames_fcs_bad=bad, frames_lost=lost,
        throughput_gbps=payload_bits_ok / max(window_s, 1e-15) / 1e9,
        line_rate_gbps=len(rx_bits) / max(window_s, 1e-15) / 1e9,
        seq_seen=len(seqs),
    )
