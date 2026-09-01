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


def scramble(bits: np.ndarray) -> np.ndarray:
    """Scrambler self-synchronous del PCS (Clause 49): G(x)=1+x^39+x^58.

    s[n] = d[n] ^ s[n-39] ^ s[n-58]. È il motivo per cui l'idle (byte 0x00
    dell'IPG) NON produce run costanti sulla linea: senza scrambler un IPG
    lungo ammazza CDR e AGC — il banco lo mostra davvero se lo togli."""
    d = np.asarray(bits, dtype=np.uint8)
    out = np.empty(len(d) + 58, dtype=np.uint8)
    out[:58] = 1                              # stato iniziale non nullo
    for n in range(len(d)):                   # dipendenza sequenziale reale
        out[n + 58] = d[n] ^ out[n + 58 - 39] ^ out[n]
    return out[58:]


def descramble(bits: np.ndarray) -> np.ndarray:
    """Descrambler self-synchronous: d[n] = r[n] ^ r[n-39] ^ r[n-58].

    Si auto-sincronizza dopo 58 bit ricevuti (i primi 58 output sono
    spazzatura) e moltiplica ×3 ogni bit error — il classico costo del
    self-sync, ben visibile sull'FCS."""
    r = np.asarray(bits, dtype=np.uint8)
    pad = np.concatenate([np.ones(58, dtype=np.uint8), r])
    return (r ^ pad[58 - 39:58 - 39 + len(r)] ^ pad[:len(r)]).astype(np.uint8)


# dimensioni dei frame per stream nel generatore multi-stream (stile Xena:
# ogni stream ha la sua size; lo stream 0 usa la size configurata)
STREAM_SIZES = (None, 64, 512, 1024)   # None = cfg.l2_frame_bytes


def build_frame(seq: int, frame_bytes: int, ipg_bytes: int = 12,
                stream_id: int = 0) -> bytes:
    payload_len = max(frame_bytes - len(HEADER) - 4, 8)
    payload = (seq.to_bytes(4, "big") + bytes([stream_id & 0xFF])
               + bytes((seq + i) & 0xFF for i in range(payload_len - 5)))
    body = HEADER + payload
    fcs = zlib.crc32(body).to_bytes(4, "big")
    return PREAMBLE + body + fcs + bytes(ipg_bytes)


def build_stream_bits(n_bits: int, frame_bytes: int, seq0: int = 0,
                      ipg_bytes: int = 12, streams: int = 1):
    """Flusso di frame per riempire n_bits; ritorna (bits, n_frame, next_seq).

    Con streams>1 il generatore alterna round-robin `streams` flussi (stile
    Xena): ogni stream ha il suo stream-id nel payload, il suo spazio di
    sequence number e la sua frame size (STREAM_SIZES)."""
    chunks = []
    total = 0
    seqs = [seq0] * max(1, int(streams))
    k = 0
    while total < n_bits:
        sid = k % len(seqs)
        size = STREAM_SIZES[sid] or frame_bytes
        f = build_frame(seqs[sid], size, ipg_bytes, stream_id=sid)
        seqs[sid] += 1
        chunks.append(f)
        total += len(f) * 8
        k += 1
    bits = _bytes_to_bits(b"".join(chunks))[:n_bits]
    return bits, k, seqs[0]


@dataclass
class StreamStats:
    stream_id: int
    detected: int
    ok: int
    fcs_bad: int
    lost: int          # buchi di sequence fra il primo e l'ultimo visto


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
    per_stream: list = None   # StreamStats per il generatore multi-stream


def analyze_stream_bits(rx_bits: np.ndarray, frame_bytes: int,
                        window_s: float, seq0: int = 0,
                        ipg_bytes: int = 12, streams: int = 1) -> L2Analysis:
    """Delineazione tipo analyzer: caccia al preamble+SFD, verifica FCS,
    ricostruzione delle sequenze. rx_bits deve essere allineato al byte 0
    del flusso TX (l'allineamento arriva dal pattern lock del PHY).

    Multi-stream (stile Xena): l'analyzer CONOSCE la configurazione del
    generatore (come un test-set reale): lo stream-id nel payload seleziona
    la size attesa; su FCS errata si risincronizza sul preamble successivo."""
    data = _bits_to_bytes(np.asarray(rx_bits, dtype=np.uint8))
    streams = max(1, int(streams))
    sizes = [(STREAM_SIZES[i] or frame_bytes) for i in range(streams)]

    def body_len_of(size):
        return len(HEADER) + max(size - len(HEADER) - 4, 8) + 4

    round_bytes = sum(len(PREAMBLE) + body_len_of(sz) + ipg_bytes
                      for sz in sizes)
    expected = (len(data) // round_bytes) * streams
    min_body = min(body_len_of(sz) for sz in sizes)

    detected = ok = bad = 0
    seqs = set()
    per = [dict(detected=0, ok=0, fcs_bad=0, seqs=set())
           for _ in range(streams)]
    payload_bits_ok = 0
    i = 0
    sync = PREAMBLE
    while i < len(data) - min_body - 2:
        j = data.find(sync, i)
        if j < 0:
            break
        start = j + len(sync)
        if start + min_body > len(data):
            break
        sid = data[start + len(HEADER) + 4] if streams > 1 else 0
        if sid >= streams:
            # stream-id corrotto: frame conteggiato come FCS bad, resync
            detected += 1
            bad += 1
            i = start
            continue
        body_len = body_len_of(sizes[sid])
        if start + body_len > len(data):
            break
        detected += 1
        body = data[start:start + body_len - 4]
        fcs = data[start + body_len - 4:start + body_len]
        if zlib.crc32(body).to_bytes(4, "big") == fcs:
            ok += 1
            seq = int.from_bytes(body[len(HEADER):len(HEADER) + 4], "big")
            seqs.add(seq)
            per[sid]["ok"] += 1
            per[sid]["seqs"].add(seq)
            payload_bits_ok += (body_len - len(HEADER) - 4) * 8
            per[sid]["detected"] += 1
            i = start + body_len
        else:
            bad += 1
            per[sid]["fcs_bad"] += 1
            per[sid]["detected"] += 1
            i = start          # resync: riparte la caccia al preamble
    expected = max(expected, detected)
    exp_per_stream = max(expected // streams, 1)
    lost = sum(1 for s2 in range(seq0, seq0 + exp_per_stream)
               for st in per if s2 not in st["seqs"]) if streams > 1 else         sum(1 for s2 in range(seq0, seq0 + expected) if s2 not in seqs)
    per_stream = [StreamStats(stream_id=k, detected=st["detected"],
                              ok=st["ok"], fcs_bad=st["fcs_bad"],
                              lost=sum(1 for s2 in range(
                                  seq0, seq0 + exp_per_stream)
                                  if s2 not in st["seqs"]))
                  for k, st in enumerate(per)] if streams > 1 else None
    return L2Analysis(
        frames_expected=expected, frames_detected=detected,
        frames_ok=ok, frames_fcs_bad=bad, frames_lost=lost,
        throughput_gbps=payload_bits_ok / max(window_s, 1e-15) / 1e9,
        line_rate_gbps=len(rx_bits) / max(window_s, 1e-15) / 1e9,
        seq_seen=len(seqs), per_stream=per_stream,
    )