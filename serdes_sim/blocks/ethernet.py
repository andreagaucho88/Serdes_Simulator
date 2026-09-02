"""Livello L2 (MAC) e L1 (PCS) sopra il PHY simulato: generatore/analyzer
Ethernet stile Xena con scheduler multi-stream, emulatore di impairment e,
opzionalmente, PCS 64b/66b con block lock.

Il payload del link (al posto del PRBS) diventa un flusso di frame:
[preamble 7B + SFD][DA 6B][SA 6B][EtherType 2B][seq 4B + stream 1B + payload][FCS 4B][IPG]

Tre livelli visibili nel banco:

* **L2 · MAC**: scheduler (round-robin, weighted round-robin o IMIX-like),
  sequence number e stream-id nel payload, FCS CRC-32; l'analyzer ricostruisce
  per stream frame ok / FCS errati / persi / duplicati / fuori ordine e
  distingue le perdite EMULATE (impairment) da quelle del PHY.
* **impairment emulator** (fra MAC e PCS, deterministico): drop, duplicate,
  misorder (ritardo di una posizione), corrupt (un bit di payload invertito,
  quindi FCS errata al RX).
* **L1 · PCS**: ``scrambler`` = solo scrambler self-sync di Clause 49 sul
  flusso (baseline storica); ``64b66b`` = blocchi 66 bit con sync header,
  /S/ /T/ /I/, scrambler sul payload e block lock al RX (``pcs.py``).

Cosa NON è (dichiarato): niente alignment marker, 256b/257b, lane
distribution, MAC pause/QoS, RFC 2544 — vedi roadmap.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field

import numpy as np

from . import pcs

PREAMBLE = bytes([0x55] * 7 + [0xD5])
HEADER = bytes.fromhex("FFFFFFFFFFFF") + bytes.fromhex("021B331C0DA0") + b"\x88\xB5"
IPG = bytes(12)
OVERHEAD = len(PREAMBLE) + len(HEADER) + 4 + len(IPG)  # + FCS
SEQ_OFFSET = len(HEADER)               # posizione del sequence number nel body
STREAM_OFFSET = len(HEADER) + 4        # stream-id
IMPAIRMENT_SEED = 4242                 # emulatore deterministico per config

# dimensioni dei frame per stream nel generatore round-robin (stile Xena:
# ogni stream ha la sua size; lo stream 0 usa la size configurata)
STREAM_SIZES = (None, 64, 512, 1024)   # None = cfg.l2_frame_bytes
# distribuzione IMIX-like (7:4:1 su 64/576/1024 B; il classico 1500 B non
# rientra nel limite di 1024 B del generatore — dichiarato)
IMIX_SIZES = ((64, 7), (576, 4), (1024, 1))
SCHEDULERS = ("round_robin", "weighted", "imix")
PCS_CODINGS = ("scrambler", "64b66b")

# Profili di WORKLOAD (forma del traffico su una corsia seriale; dichiarato:
# niente switch, code, congestione o RDMA). sizes = (byte, peso); burst_on
# = frame consecutivi per burst; gap_ipg = IPG extra dopo il burst [byte];
# streams/weights = mix di flussi; kpi = nome del KPI di completamento.
WORKLOADS = {
    "custom": None,
    "ai_training": dict(sizes=((1024, 8), (576, 2)), burst_on=12, gap_ipg=2048,
                        streams=2, weights=(1, 1, 1, 1),
                        label="AI training · all-reduce collectives",
                        kpi="burst completion (collective step)"),
    "llm_inference": dict(sizes=((64, 3), (256, 5), (576, 2)), burst_on=6,
                          gap_ipg=512, streams=2, weights=(1, 3, 1, 1),
                          label="LLM inference · request / token replies",
                          kpi="reply latency (time-to-first-frame)"),
    "storage": dict(sizes=((1024, 9), (576, 1)), burst_on=64, gap_ipg=64,
                    streams=1, weights=(1, 1, 1, 1),
                    label="storage · RDMA-like bulk transfer",
                    kpi="sustained goodput"),
    "web": dict(sizes=((64, 6), (128, 3), (576, 1)), burst_on=4, gap_ipg=256,
                streams=4, weights=(4, 3, 2, 1),
                label="web · microservices (many small frames)",
                kpi="frames per second"),
    "video": dict(sizes=((576, 2), (1024, 3)), burst_on=8, gap_ipg=384,
                  streams=1, weights=(1, 1, 1, 1),
                  label="video streaming · constant-rate segments",
                  kpi="segment delivery (no loss)"),
}


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


def body_length(frame_bytes: int) -> int:
    """Lunghezza del body (header + payload + FCS) per una frame size."""
    return len(HEADER) + max(frame_bytes - len(HEADER) - 4, 8) + 4


def build_frame(seq: int, frame_bytes: int, ipg_bytes: int = 12,
                stream_id: int = 0, corrupt: bool = False) -> bytes:
    """Frame completo (preamble … FCS) + IPG.  ``corrupt`` inverte un bit del
    payload DOPO il calcolo dell'FCS: l'analyzer lo vedrà come FCS bad."""
    payload_len = max(frame_bytes - len(HEADER) - 4, 8)
    payload = (seq.to_bytes(4, "big") + bytes([stream_id & 0xFF])
               + bytes((seq + i) & 0xFF for i in range(payload_len - 5)))
    body = HEADER + payload
    fcs = zlib.crc32(body).to_bytes(4, "big")
    if corrupt:
        body = bytearray(body)
        body[STREAM_OFFSET + 1 + (seq % max(payload_len - 6, 1))] ^= 0x01
        body = bytes(body)
    return PREAMBLE + body + fcs + bytes(ipg_bytes)


# ---------------------------------------------------------------------------
# Scheduler + impairment emulator
# ---------------------------------------------------------------------------

@dataclass
class TxFrame:
    index: int                 # posizione di EMISSIONE sulla linea
    stream_id: int
    seq: int
    size_bytes: int
    line_bit_start: int = 0
    line_bit_end: int = 0      # fine IPG incluso
    line_bit_body_end: int = 0 # fine del frame (FCS) senza IPG/idle
    dropped: bool = False      # non emesso (drop emulato)
    duplicate: bool = False    # seconda copia emulata
    corrupted: bool = False    # bit di payload invertito (FCS bad emulata)
    reordered: bool = False    # emesso dopo il frame successivo
    extra_ipg: int = 0         # idle aggiuntivo dopo il frame (fine burst)
    burst: int = 0             # indice del burst di workload


@dataclass
class TxSchedule:
    frames: list = field(default_factory=list)     # tutti i frame logici
    coding: str = "scrambler"
    scheduler: str = "round_robin"
    weights: tuple = (1, 1, 1, 1)
    streams: int = 1
    total_line_bits: int = 0
    n_dropped: int = 0
    n_duplicated: int = 0
    n_corrupted: int = 0
    n_reordered: int = 0
    workload: str = "custom"
    workload_label: str = ""
    workload_kpi: str = ""
    burst_on: int = 0
    gap_ipg: int = 0

    def emitted(self):
        return [f for f in self.frames if not f.dropped]

    def lookup(self, stream_id: int, seq: int):
        return self._by_key.get((stream_id, seq))

    def finalize(self):
        self._by_key = {}
        for f in self.frames:
            self._by_key.setdefault((f.stream_id, f.seq), f)


def _stream_size(sid, cfg, sizes_rng, workload=None):
    if workload is not None:
        sizes, w = zip(*workload["sizes"])
        return int(sizes_rng.choice(sizes, p=np.asarray(w, float) / sum(w)))
    if cfg.l2_scheduler == "imix":
        sizes, w = zip(*IMIX_SIZES)
        return int(sizes_rng.choice(sizes, p=np.asarray(w, float) / sum(w)))
    return STREAM_SIZES[sid] or cfg.l2_frame_bytes


def _next_stream_wrr(credits, weights):
    """Weighted round robin "smooth": lo stream con più credito emette; il
    credito cala del totale dei pesi e tutti ricaricano del proprio peso."""
    total = float(sum(weights))
    for i, w in enumerate(weights):
        credits[i] += w
    sid = int(np.argmax(credits))
    credits[sid] -= total
    return sid


def schedule_frames(cfg, n_bits: int, seq0: int = 0,
                    seed: int = IMPAIRMENT_SEED) -> TxSchedule:
    """Sequenza logica dei frame (scheduler) + emulatore di impairment.

    Deterministico per configurazione: l'analyzer (che come un test set
    conosce il generatore) ricostruisce le attese frame per frame.
    """
    workload = WORKLOADS.get(cfg.l2_workload)
    if workload is not None:
        streams = int(workload["streams"])
        weights = tuple(workload["weights"])[:streams]
        scheduler = "weighted" if streams > 1 else "round_robin"
    else:
        streams = max(1, int(cfg.l2_streams))
        weights = tuple(int(max(1, w)) for w in
                        (tuple(cfg.l2_stream_weights) + (1, 1, 1, 1))[:streams])
        scheduler = cfg.l2_scheduler
    rng = np.random.default_rng(seed)
    sizes_rng = np.random.default_rng(seed + 1)
    sched = TxSchedule(coding=cfg.l2_pcs_coding, scheduler=scheduler,
                       weights=weights, streams=streams,
                       workload=cfg.l2_workload,
                       workload_label=(workload["label"] if workload else ""),
                       workload_kpi=(workload["kpi"] if workload else ""),
                       burst_on=(workload["burst_on"] if workload else 0),
                       gap_ipg=(workload["gap_ipg"] if workload else 0))
    seqs = [seq0] * streams
    credits = [0.0] * streams
    p_drop = cfg.l2_drop_pct / 100.0
    p_dup = cfg.l2_dup_pct / 100.0
    p_mis = cfg.l2_misorder_pct / 100.0
    p_cor = cfg.l2_corrupt_pct / 100.0
    # budget di byte: basta coprire n_bits (l'encoder aggiunge overhead)
    budget_bytes = int(n_bits / 8 * 1.2) + 4096
    total = 0
    k = 0
    held = None                     # frame in attesa (misorder di una posizione)
    burst_on = sched.burst_on
    while total < budget_bytes:
        if scheduler == "weighted" and streams > 1:
            sid = _next_stream_wrr(credits, weights)
        else:
            sid = k % streams
        size = _stream_size(sid, cfg, sizes_rng, workload)
        fr = TxFrame(index=-1, stream_id=sid, seq=seqs[sid], size_bytes=int(size))
        if burst_on:
            fr.burst = k // burst_on
            if (k + 1) % burst_on == 0:
                fr.extra_ipg = int(sched.gap_ipg)   # pausa fra i burst
        seqs[sid] += 1
        k += 1
        u = rng.random(4)
        if p_drop > 0 and u[0] < p_drop:
            fr.dropped = True
            sched.n_dropped += 1
            sched.frames.append(fr)
            continue
        if p_cor > 0 and u[1] < p_cor:
            fr.corrupted = True
            sched.n_corrupted += 1
        emit = []
        if held is not None and fr.stream_id == held.stream_id and not fr.corrupted:
            # il frame trattenuto esce DOPO il successivo (con FCS buona) del
            # suo stesso stream: solo così l'analyzer per-stream vede
            # l'inversione e il contatore out_of_order chiude sull'emulatore
            emit.append(fr)
            emit.append(held)
            held = None
        elif held is None and p_mis > 0 and u[2] < p_mis:
            fr.reordered = True
            sched.n_reordered += 1
            held = fr
            continue
        else:
            emit.append(fr)
        if p_dup > 0 and u[3] < p_dup:
            dup = TxFrame(index=-1, stream_id=fr.stream_id, seq=fr.seq,
                          size_bytes=fr.size_bytes, duplicate=True)
            sched.n_duplicated += 1
            emit.append(dup)
        for f in emit:
            f.index = len([x for x in sched.frames if not x.dropped])
            sched.frames.append(f)
            total += (len(PREAMBLE) + body_length(f.size_bytes)
                      + int(cfg.l2_ipg_bytes) + int(f.extra_ipg))
    if held is not None:
        # nessun successore: esce in ordine, quindi non è un misorder
        held.reordered = False
        sched.n_reordered -= 1
        held.index = len([x for x in sched.frames if not x.dropped])
        sched.frames.append(held)
    sched.finalize()
    return sched


def build_line_bits(cfg, n_bits: int, seq0: int = 0,
                    seed: int = IMPAIRMENT_SEED):
    """Bit di linea (già scramblati / codificati) per riempire n_bits.

    Ritorna (bits, schedule) con gli offset di linea di ogni frame emesso,
    così l'analyzer sa esattamente quali frame cadono nella finestra RX.
    """
    sched = schedule_frames(cfg, n_bits, seq0=seq0, seed=seed)
    emitted = sched.emitted()
    ipg = int(cfg.l2_ipg_bytes)
    if cfg.l2_pcs_coding == "64b66b":
        frames = [build_frame(f.seq, f.size_bytes, 0, stream_id=f.stream_id,
                              corrupt=f.corrupted) for f in emitted]
        enc = pcs.encode(frames, [ipg + f.extra_ipg for f in emitted])
        for f, (start, n_blk, n_body) in zip(emitted, enc.frame_blocks):
            f.line_bit_start = start * pcs.BLOCK_BITS
            f.line_bit_end = (start + n_blk) * pcs.BLOCK_BITS
            f.line_bit_body_end = (start + n_body) * pcs.BLOCK_BITS
        bits = enc.line_bits
    else:
        chunks = []
        pos = 0
        for f in emitted:
            raw = build_frame(f.seq, f.size_bytes, ipg + f.extra_ipg,
                              stream_id=f.stream_id, corrupt=f.corrupted)
            f.line_bit_start = pos * 8
            pos += len(raw)
            f.line_bit_end = pos * 8
            f.line_bit_body_end = (pos - ipg - int(f.extra_ipg)) * 8
            chunks.append(raw)
        bits = scramble(_bytes_to_bits(b"".join(chunks)))
    sched.total_line_bits = int(len(bits))
    # i frame DROPPATI non occupano bit di linea ma ricevono la posizione in
    # cui sarebbero usciti: così l'analyzer li conta fra gli attesi della
    # finestra (persi "dalla rete") e chiude lost = lost_emulated + lost_phy
    pos = 0
    for f in sched.frames:
        if f.dropped:
            f.line_bit_start = f.line_bit_end = f.line_bit_body_end = pos
        else:
            pos = f.line_bit_end
    return bits[:n_bits], sched


def build_stream_bits(n_bits: int, frame_bytes: int, seq0: int = 0,
                      ipg_bytes: int = 12, streams: int = 1):
    """API storica (round-robin, senza impairment, non scramblata): flusso
    di frame per riempire n_bits; ritorna (bits, n_frame, next_seq)."""
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


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

@dataclass
class StreamStats:
    stream_id: int
    detected: int
    ok: int
    fcs_bad: int
    lost: int          # attesi (nella finestra) mai ricevuti con FCS ok
    lost_emulated: int = 0
    duplicates: int = 0
    out_of_order: int = 0
    weight: int = 1
    size_bytes: int = 0
    expected: int = 0


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
    per_stream: list = None   # StreamStats per stream
    frames_duplicated: int = 0
    frames_out_of_order: int = 0
    lost_emulated: int = 0     # persi per drop emulato (impairment)
    lost_phy: int = 0          # persi per errori del PHY
    corrupt_emulated: int = 0  # FCS bad attese dall'emulatore
    window_s: float = 0.0      # durata della finestra analizzata [s]
    scheduler: str = "round_robin"
    coding: str = "scrambler"
    weights: tuple = (1,)
    offered_load_pct: float = 0.0
    window_frames: list = None   # (stream, seq) attesi nella finestra
    workload: str = "custom"
    workload_label: str = ""
    workload_kpi: str = ""
    bursts_in_window: int = 0
    burst_bytes: int = 0             # byte utili per burst (nominale)
    burst_completion_us: float = None   # burst_bytes / goodput
    tail_loss_pct: float = None      # peggior FLR fra i burst della finestra
    size_histogram: dict = None      # size → frame attesi


def delineate(data: bytes, sizes_by_stream, streams: int, lookup=None):
    """Caccia al preamble+SFD, verifica FCS, ritorna la lista dei frame
    trovati: (offset_byte, stream_id, seq, body_len, fcs_ok, body, fcs_rx).

    La lunghezza del body arriva dalla schedule (stream, seq) quando la
    coppia è nota, altrimenti dalla size dello stream; se nessuna delle due
    torna, si risincronizza sul preamble successivo."""
    found = []
    i = 0
    n = len(data)
    min_body = min(body_length(sz) for sz in sizes_by_stream)
    while i < n - min_body - 2:
        j = data.find(PREAMBLE, i)
        if j < 0:
            break
        start = j + len(PREAMBLE)
        if start + min_body > n:
            break
        seq = int.from_bytes(data[start + SEQ_OFFSET:start + SEQ_OFFSET + 4], "big")
        sid = data[start + STREAM_OFFSET] if streams > 1 else 0
        if sid >= streams:
            found.append((j, sid, seq, min_body, False, b"", b""))
            i = start
            continue
        known = lookup(sid, seq) if lookup is not None else None
        body_len = body_length(known.size_bytes if known else sizes_by_stream[sid])
        if start + body_len > n:
            break
        body = data[start:start + body_len - 4]
        fcs = data[start + body_len - 4:start + body_len]
        ok = zlib.crc32(body).to_bytes(4, "big") == fcs
        found.append((j, sid, seq, body_len, ok, body, fcs))
        i = start + body_len if ok else start
    return found


def analyze_line_bytes(cfg, data: bytes, schedule: TxSchedule,
                       window_line_start: int, window_line_end: int,
                       window_s: float, line_bits: int) -> L2Analysis:
    """Analyzer L2 sui byte ricostruiti (post-PCS o post-descrambler)."""
    streams = max(1, int(schedule.streams))
    sizes = [(STREAM_SIZES[i] or cfg.l2_frame_bytes) for i in range(streams)]
    # atteso = frame il cui corpo (preamble…FCS) sta interamente nella
    # finestra; l'IPG che segue può essere tagliato dal record
    expected_frames = [f for f in schedule.frames
                       if f.line_bit_start >= window_line_start
                       and (f.line_bit_body_end or f.line_bit_end) <= window_line_end]
    # attesi = frame logici nella finestra (dropped inclusi: dal punto di
    # vista dell'analyzer sono frame persi dalla "rete")
    logical = {}
    for f in expected_frames:
        if not f.duplicate:
            logical.setdefault((f.stream_id, f.seq), f)
    exp_per = {s: sum(1 for (sid, _) in logical if sid == s) for s in range(streams)}
    corrupt_emu = sum(1 for f in expected_frames if f.corrupted and not f.dropped)

    found = delineate(data, sizes, streams, lookup=schedule.lookup)
    detected = len(found)
    ok = sum(1 for f in found if f[4])
    bad = detected - ok
    per = [dict(detected=0, ok=0, fcs_bad=0, seqs=set(), dup=0, ooo=0, max_seq=-1)
           for _ in range(streams)]
    payload_bits_ok = 0
    seqs_all = set()
    for (_, sid, seq, body_len, fcs_ok, _body, _fcs) in found:
        if sid >= streams:
            continue
        st = per[sid]
        st["detected"] += 1
        if not fcs_ok:
            st["fcs_bad"] += 1
            continue
        st["ok"] += 1
        payload_bits_ok += (body_len - len(HEADER) - 4) * 8
        seqs_all.add((sid, seq))
        if seq in st["seqs"]:
            st["dup"] += 1
        else:
            if seq < st["max_seq"]:
                st["ooo"] += 1
            st["max_seq"] = max(st["max_seq"], seq)
            st["seqs"].add(seq)
    lost_total = lost_emu = 0
    per_stream = []
    for s in range(streams):
        st = per[s]
        exp_keys = [(sid, seq) for (sid, seq) in logical if sid == s]
        lost_s = sum(1 for (_, seq) in exp_keys if seq not in st["seqs"])
        # persi per impairment emulato: drop (mai emesso) o corruzione (FCS
        # bad → sequenza mai vista buona); il resto è perdita del PHY
        lost_e = sum(1 for key in exp_keys
                     if (logical[key].dropped or logical[key].corrupted)
                     and key[1] not in st["seqs"])
        lost_total += lost_s
        lost_emu += lost_e
        per_stream.append(StreamStats(
            stream_id=s, detected=st["detected"], ok=st["ok"],
            fcs_bad=st["fcs_bad"], lost=lost_s, lost_emulated=lost_e,
            duplicates=st["dup"], out_of_order=st["ooo"],
            weight=(schedule.weights[s] if s < len(schedule.weights) else 1),
            size_bytes=sizes[s], expected=exp_per.get(s, 0)))
    expected = len(logical)
    wire_bytes = sum(len(PREAMBLE) + body_length(f.size_bytes)
                     + int(cfg.l2_ipg_bytes) + int(f.extra_ipg)
                     for f in expected_frames if not f.dropped)
    offered = (100.0 * sum(len(PREAMBLE) + body_length(f.size_bytes)
                           for f in expected_frames if not f.dropped)
               / max(wire_bytes, 1))
    throughput = payload_bits_ok / max(window_s, 1e-15) / 1e9
    # KPI del workload: burst nella finestra, completamento, FLR di coda
    size_hist = {}
    for f in logical.values():
        size_hist[f.size_bytes] = size_hist.get(f.size_bytes, 0) + 1
    bursts = {}
    for key, f in logical.items():
        bursts.setdefault(f.burst, []).append(key)
    tail_loss = None
    burst_bytes = 0
    if schedule.burst_on:
        losses = []
        for keys in bursts.values():
            if len(keys) < max(2, schedule.burst_on // 2):
                continue      # burst tagliato dalla finestra
            lost_b = sum(1 for (sid, seq) in keys if seq not in per[sid]["seqs"])
            losses.append(100.0 * lost_b / len(keys))
        tail_loss = max(losses) if losses else None
        burst_bytes = int(sum(max(f.size_bytes - len(HEADER) - 4, 8)
                              for f in logical.values()) / max(len(bursts), 1))
    completion = ((8 * burst_bytes / max(throughput * 1e9, 1e-9)) * 1e6
                  if burst_bytes and throughput > 0 else None)
    return L2Analysis(
        frames_expected=expected, frames_detected=detected,
        frames_ok=ok, frames_fcs_bad=bad, frames_lost=lost_total,
        throughput_gbps=throughput,
        line_rate_gbps=line_bits / max(window_s, 1e-15) / 1e9,
        seq_seen=len(seqs_all),
        per_stream=per_stream if streams > 1 else None,
        frames_duplicated=sum(p["dup"] for p in per),
        frames_out_of_order=sum(p["ooo"] for p in per),
        lost_emulated=lost_emu, lost_phy=max(lost_total - lost_emu, 0),
        corrupt_emulated=corrupt_emu,
        window_s=float(window_s),
        scheduler=schedule.scheduler, coding=schedule.coding,
        weights=schedule.weights, offered_load_pct=offered,
        window_frames=[(k[0], k[1]) for k in list(logical)[:64]],
        workload=schedule.workload, workload_label=schedule.workload_label,
        workload_kpi=schedule.workload_kpi,
        bursts_in_window=len(bursts) if schedule.burst_on else 0,
        burst_bytes=burst_bytes, burst_completion_us=completion,
        tail_loss_pct=tail_loss,
        size_histogram={int(k): int(v) for k, v in sorted(size_hist.items())},
    )


def analyze_line_bits(cfg, rx_bits: np.ndarray, schedule: TxSchedule,
                      line_offset: int, window_s: float):
    """Dal flusso di bit RX (allineato al bit ``line_offset`` del TX) ai
    contatori L1/L2.  Ritorna (L2Analysis | None, PcsStats | None, bytes)."""
    rx = np.asarray(rx_bits, dtype=np.uint8)
    if cfg.l2_pcs_coding == "64b66b":
        data, stats = pcs.decode(rx, line_offset_bits=line_offset)
        if not stats.lock or len(data) < 64:
            return None, stats, data
        start = stats.first_block_index * pcs.BLOCK_BITS
        end = (stats.first_block_index + stats.blocks) * pcs.BLOCK_BITS
        l2 = analyze_line_bytes(cfg, data, schedule, start, end, window_s,
                                line_bits=len(rx))
        return l2, stats, data
    # scrambler self-sync: 58 bit di burn-in, poi allineamento al byte
    clear = descramble(rx)
    first = line_offset + 58
    skip = (8 - first % 8) % 8
    usable = clear[58 + skip:]
    data = _bits_to_bytes(usable)
    start = first + skip
    end = start + len(data) * 8
    l2 = analyze_line_bytes(cfg, data, schedule, start, end, window_s,
                            line_bits=len(rx))
    return l2, None, data


def analyze_stream_bits(rx_bits: np.ndarray, frame_bytes: int,
                        window_s: float, seq0: int = 0,
                        ipg_bytes: int = 12, streams: int = 1) -> L2Analysis:
    """API storica: analyzer round-robin senza schedule (attese dal conto
    dei byte).  Conservata per i test e gli strumenti che la usano."""
    from ..config import LinkConfig
    cfg = LinkConfig(pattern="eth", l2_frame_bytes=frame_bytes,
                     l2_ipg_bytes=ipg_bytes, l2_streams=streams)
    data = _bits_to_bytes(np.asarray(rx_bits, dtype=np.uint8))
    streams = max(1, int(streams))
    sizes = [(STREAM_SIZES[i] or frame_bytes) for i in range(streams)]
    sched = TxSchedule(streams=streams, weights=(1,) * streams)
    # round-robin frame per frame fino a riempire i byte disponibili (anche
    # l'ultimo giro parziale: un frame col corpo dentro il record è atteso)
    pos = 0
    r = 0
    done = False
    while not done:
        for sid in range(streams):
            size = sizes[sid]
            nb = len(PREAMBLE) + body_length(size) + ipg_bytes
            if pos + nb - ipg_bytes > len(data):
                done = True
                break
            sched.frames.append(TxFrame(index=len(sched.frames), stream_id=sid,
                                        seq=seq0 + r, size_bytes=size,
                                        line_bit_start=pos * 8,
                                        line_bit_end=(pos + nb) * 8,
                                        line_bit_body_end=(pos + nb - ipg_bytes) * 8))
            pos += nb
        r += 1
    sched.finalize()
    return analyze_line_bytes(cfg, data, sched, 0, len(data) * 8, window_s,
                              line_bits=len(rx_bits))
