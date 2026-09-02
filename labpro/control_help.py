"""Metadati bilingui dei controlli del banco.

La GUI li usa per la card ``?`` accanto a ogni manopola.  Il catalogo copre
anche i campi non esposti come slider: una nuova opzione del motore non può
nascere senza piano di riferimento e spiegazione fisica.  Ogni scheda segue
lo stesso arco: MECCANISMO nel modello → numeri tipici del mondo reale →
"Sul banco:" cosa osservare e con quale verso atteso → limiti dichiarati.
"""

from __future__ import annotations


CONTROL_HELP: dict[str, dict[str, str]] = {}


def _add(names, block, plane, it, en, formula="", active="sempre / always"):
    for name in names.split():
        label = name.replace("_", " ")
        CONTROL_HELP[name] = {
            "block": block,
            "plane": plane,
            "it": f"{label}: {it}",
            "en": f"{label}: {en}",
            "formula": formula,
            "active": active,
        }


# ============================================================ STIMOLO / PPG
_add("symbol_rate_hz", "Stimulus / acquisition", "PPG → analog grid",
     "frequenza di simbolo della corsia: fissa la durata dell'UI (a 56 GBd "
     "l'UI dura 17.86 ps) e quindi riscala TUTTO ciò che è definito in "
     "UI o relativo a Nyquist: jitter in fs diventa una frazione d'UI "
     "diversa, la stessa banda analogica in Hz copre meno armoniche del "
     "segnale, la perdita del canale a Nyquist si sposta di frequenza. È la "
     "manopola col raggio d'azione più ampio del banco. Sul banco: raddoppia "
     "il rate a parità di banda TIA/driver e guarda gli edge afflosciarsi "
     "nello Scope WAVE e l'occhio chiudersi; i profili IEEE PAM4 usano "
     "26.5625 GBd (50G/lane, 802.3cd/bs), 53.125 GBd (100G/lane, "
     "802.3ck/cu/df) e 106.25 GBd (200G/lane, P802.3dj).",
     "lane symbol rate: it fixes the UI duration (at 56 GBd one UI lasts "
     "17.86 ps) and therefore rescales EVERYTHING defined in UI or relative "
     "to Nyquist: jitter in fs becomes a different UI fraction, the same "
     "analog bandwidth in Hz spans fewer signal harmonics, channel loss at "
     "Nyquist moves in frequency. It is the widest-reaching knob on the "
     "bench. On the bench: double the rate at fixed TIA/driver bandwidth "
     "and watch edges slump in the WAVE Scope and the eye close; IEEE "
     "PAM4 profiles use 26.5625 GBd (50G/lane, 802.3cd/bs), 53.125 GBd "
     "(100G/lane, 802.3ck/cu/df) and 106.25 GBd (200G/lane, P802.3dj).",
     "UI=1/Rs; f_Nyq=Rs/2")
_add("analog_sps", "Stimulus / acquisition", "PPG → analog grid",
     "campioni della griglia analogica per UI: è la risoluzione con cui il "
     "banco rappresenta la fisica continua (default 16 → a 56 GBd la "
     "griglia gira a 896 GS/s). Non è una manopola fisica: è il passo "
     "d'integrazione. Sotto ~8 sps i filtri ripidi e il jitter fine si "
     "quantizzano male (il DR4 usa una verifica di convergenza 16→8 sps "
     "proprio per stimare questo errore numerico). Sul banco: dimezzalo e "
     "verifica che BER e TDECQ si muovano poco — se si muovono tanto, il "
     "risultato era dominato dalla griglia, non dalla fisica.",
     "analog grid samples per UI: the resolution at which the bench "
     "represents continuous physics (default 16 → at 56 GBd the grid runs "
     "at 896 GS/s). Not a physical knob: it is the integration step. Below "
     "~8 sps steep filters and fine jitter quantize poorly (the DR4 "
     "procedure runs a 16→8 sps convergence check precisely to bound this "
     "numerical error). On the bench: halve it and verify BER and TDECQ "
     "barely move — if they move a lot, the result was grid-dominated, not "
     "physics-dominated.",
     "fs,analog=Rs·sps")
_add("n_symbols", "Stimulus / acquisition", "record length",
     "simboli per record: fissa la statistica di OGNI numero del banco. Con "
     "8191 simboli il record porta ~16k bit: una BER vera di 1e-4 produce "
     "in media 1.6 errori per record — il contatore live serve proprio ad "
     "accumulare record finché l'intervallo di confidenza si stringe "
     "(CL95 ≈ 3/BER bit). Record più lunghi servono anche a FEC "
     "interleaved (≥16k) e SSPRQ completo (65535). Sul banco: accorcia il "
     "record e guarda l'IC95 della BER in topbar allargarsi a parità di "
     "tutto il resto.",
     "symbols per record: it sets the statistics of EVERY number on the "
     "bench. With 8191 symbols a record carries ~16k bits: a true BER of "
     "1e-4 yields on average 1.6 errors per record — the live counters "
     "exist precisely to accumulate records until the confidence interval "
     "tightens (CL95 ≈ 3/BER bits). Long records are also needed by "
     "interleaved FEC (≥16k) and full SSPRQ (65535). On the bench: shorten "
     "the record and watch the topbar BER CI95 widen with everything else "
     "unchanged.",
     "bit/record=2·n_symbols (PAM4); CL95≈3/BER")
_add("prbs_order", "PPG", "PCS/PPG output",
     "ordine della PRBS: periodo 2ⁿ−1 e run massimo di n bit uguali. PRBS31 "
     "è lo stress classico dei BERT (run lunghi = più wander di baseline e "
     "più DDJ dai code lunghi del canale); PRBS13Q è il pattern corto di "
     "clause per le misure ottiche PAM4 (occupazione dei livelli "
     "2047/2048/2048/2048, verificata da un checkpoint quando il record "
     "coincide col periodo). Sul banco: passa da PRBS7 a PRBS31 su un "
     "canale con echo e guarda crescere DDJ nel pannello Jitter e la coda "
     "dell'istogramma TIE.",
     "PRBS order: period 2ⁿ−1 and maximum run of n equal bits. PRBS31 is "
     "the classic BERT stress (long runs = more baseline wander and more "
     "DDJ from the channel's long tails); PRBS13Q is the short clause "
     "pattern for PAM4 optical measurements (level occupancy "
     "2047/2048/2048/2048, checked when the record matches the period). On "
     "the bench: switch PRBS7 → PRBS31 on a channel with echo and watch "
     "DDJ grow in the Jitter panel and in the TIE histogram tail.",
     "period=2ⁿ−1; run max=n")
_add("pattern", "PPG", "PCS/PPG output",
     "sorgente del flusso serializzato: PRBS (stress statistico), clock "
     "0101/4+4 (righe spettrali pulite per debug di banda e skew), SSPRQ "
     "bit-exact di Clause 120 (i 65535 simboli pubblici IEEE per le misure "
     "TX PAM4: TDECQ/SNDR di clause lo prescrivono), frame Ethernet reali "
     "(L2 con preambolo/FCS per i pannelli traffic) o HEX utente. Il "
     "pattern determina spettro e ISI: non è un dettaglio cosmetico — le "
     "misure di clause specificano SEMPRE il pattern. Sul banco: con "
     "clock2 lo spettro collassa su una riga a Nyquist/2; con PRBS torna "
     "il sinc² continuo.",
     "source of the serialized stream: PRBS (statistical stress), 0101/4+4 "
     "clock (clean spectral lines for bandwidth and skew debug), Clause "
     "120 bit-exact SSPRQ (the public IEEE 65535 symbols for PAM4 TX "
     "measurements: clause TDECQ/SNDR prescribe it), real Ethernet frames "
     "(L2 with preamble/FCS for the traffic panels) or user HEX. The "
     "pattern sets spectrum and ISI: it is not cosmetic — clause "
     "measurements ALWAYS specify the pattern. On the bench: with clock2 "
     "the spectrum collapses onto a line at Nyquist/2; with PRBS the "
     "continuous sinc² returns.",
     "SSPRQ: 65535 simboli, Clause 120")
_add("custom_pattern_hex", "PPG pattern editor", "PCS/PPG output",
     "sequenza utente di 1..4096 byte esadecimali, ripetuta ciclicamente e "
     "serializzata MSB-first (spazi, underscore e due punti sono solo "
     "separatori). Utile per riprodurre pattern corti di debug (es. CJTPAT "
     "artigianali o burst di livelli estremi) e vedere l'effetto di run "
     "specifici su CDR e DDJ. È un pattern di laboratorio, non di clause. "
     "Sul banco: prova FF 00 ripetuto — run lunghissimi, il CDR perde "
     "densità di transizioni e il pattern lock si fa fragile.",
     "user sequence of 1..4096 hexadecimal bytes, cyclically repeated and "
     "serialized MSB first (spaces, underscores, and colons are separators "
     "only). Useful to reproduce short debug patterns (hand-made CJTPAT-"
     "style or extreme-level bursts) and see the effect of specific runs "
     "on CDR and DDJ. A lab pattern, not a clause pattern. On the bench: "
     "try repeated FF 00 — very long runs, the CDR loses transition "
     "density and pattern lock becomes fragile.",
     "period = 8·Nbyte bit", "pattern = custom_hex")
_add("modulation", "Mapper", "mapper output",
     "NRZ (2 livelli, 1 bit/simbolo) o PAM4 (4 livelli, 2 bit/simbolo). A "
     "parità di bit rate PAM4 dimezza il baud — e quindi la banda e la "
     "perdita di canale a Nyquist — ma paga ~9.5 dB di SNR perché "
     "l'apertura verticale fra livelli adiacenti è 1/3 del full swing. È "
     "il compromesso che ha deciso l'era 100G+/lane. Sul banco: stessa "
     "config, NRZ vs PAM4 — l'occhio singolo NRZ è enorme ma il baud "
     "raddoppia; il selftest verifica proprio che NRZ batta PAM4 a parità "
     "di canale e rate.",
     "NRZ (2 levels, 1 bit/symbol) or PAM4 (4 levels, 2 bits/symbol). At "
     "equal bit rate PAM4 halves the baud — hence Nyquist bandwidth and "
     "channel loss — but pays ~9.5 dB of SNR because the vertical opening "
     "between adjacent levels is 1/3 of full swing. This trade decided the "
     "100G+/lane era. On the bench: same config, NRZ vs PAM4 — the single "
     "NRZ eye is huge but baud doubles; the selftest explicitly verifies "
     "NRZ beats PAM4 at equal channel and rate.",
     "ΔSNR PAM4 ≈ 20·log10(3) ≈ 9.5 dB")
_add("pam4_mapping", "Mapper", "mapper output",
     "mappa bit→livello: Gray garantisce che livelli ADIACENTI differiscano "
     "di un solo bit, così l'errore dominante (scivolare di un livello) "
     "costa 1 bit invece di 2 — è il motivo per cui BER≈SER/2 in Gray "
     "mentre in binario BER→SER. Non cambia NULLA dell'occhio analogico: "
     "agisce solo su come gli errori di simbolo diventano errori di bit. "
     "Sul banco: passa a binary e guarda la BER contata salire (~×1.5) a "
     "SER identico — il selftest blocca proprio Gray ≤ binary.",
     "bit→level mapping: Gray guarantees ADJACENT levels differ by one bit "
     "only, so the dominant error (slipping one level) costs 1 bit instead "
     "of 2 — the reason BER≈SER/2 with Gray while binary pushes BER→SER. "
     "It changes NOTHING in the analog eye: it only shapes how symbol "
     "errors become bit errors. On the bench: switch to binary and watch "
     "counted BER rise (~×1.5) at identical SER — the selftest pins "
     "Gray ≤ binary.",
     "Gray: BER≈SER/2 (errori adiacenti)")

# =============================================================== FEC / L2
_add("fec_mode", "FEC", "PCS before mapper / after DEMUX",
     "inserisce DAVVERO encoder e decoder Reed-Solomon nel datapath (non un "
     "modello a formula): KP4 RS(544,514) su GF(2¹⁰) corregge fino a t=15 "
     "simboli per codeword ed è il FEC obbligatorio di tutte le interfacce "
     "PAM4 100G+/lane; KR4 RS(528,514), t=7, è la generazione 25G NRZ. Il "
     "requisito BER pre-FEC di clause dei PMD KP4 è 2.4e-4 (il modello iid "
     "del banco dà ≈2.1e-4 a FER 1e-13): sotto, il post-FEC crolla a zero; "
     "sopra, i frame persi esplodono — è il cliff del FEC. Sul banco: FEC "
     "live mostra l'istogramma "
     "errori-per-codeword; avvicinati alla soglia col canale e guarda la "
     "transizione clean→corrected→lost.",
     "TRULY inserts the Reed-Solomon encoder and decoder in the datapath "
     "(not a formula model): KP4 RS(544,514) over GF(2¹⁰) corrects up to "
     "t=15 symbols per codeword and is the mandatory FEC of every "
     "100G+/lane PAM4 interface; KR4 RS(528,514), t=7, is the 25G NRZ "
     "generation. The clause pre-FEC BER requirement of KP4 PMDs is 2.4e-4 "
     "(the bench iid model gives ≈2.1e-4 at FER 1e-13): below it post-FEC "
     "collapses to zero, above it lost frames explode — the FEC cliff. On "
     "the bench: FEC live "
     "shows the errors-per-codeword histogram; walk the channel toward the "
     "threshold and watch the clean→corrected→lost transition.",
     "KP4 RS(544,514) t=15; KR4 RS(528,514) t=7; overhead 544/514≈5.8%")
_add("fec_interleave", "FEC", "RS symbol mux on the line",
     "interleaving di codeword a livello di simbolo RS (802.3ck/dj): i "
     "simboli di 2/4 codeword si alternano sulla linea, così un burst di L "
     "simboli ne colpisce ~L/depth per codeword — il burst si spalma e la "
     "correggibilità t=15 va molto più lontano. È il motivo per cui il DFE "
     "(che propaga errori in burst) convive col KP4. Con depth>1 serve un "
     "record lungo (≥16k simboli) perché un gruppo intero cada in "
     "validation. Sul banco: inietta un burst da 60 bit con depth 1 vs 4 e "
     "confronta frame persi e corretti nel FEC live.",
     "codeword interleaving at the RS-symbol level (802.3ck/dj): symbols "
     "of 2/4 codewords alternate on the line, so an L-symbol burst hits "
     "~L/depth per codeword — the burst is spread and t=15 correctability "
     "goes much further. This is why the DFE (which propagates errors in "
     "bursts) coexists with KP4. With depth>1 a long record (≥16k symbols) "
     "is needed for a full group inside validation. On the bench: inject a "
     "60-bit burst with depth 1 vs 4 and compare lost vs corrected frames "
     "in FEC live.",
     "burst L → ~L/depth per codeword", "fec_mode ≠ none")
_add("l2_frame_bytes", "Ethernet traffic", "MAC/PCS stimulus",
     "dimensione dei frame L2 generati (preambolo+header+payload+FCS "
     "reali). I frame grandi massimizzano il goodput (meno overhead per "
     "byte) ma raccolgono più bit error per frame: a BER fissata, la frame "
     "loss cresce ~linearmente con la lunghezza — l'esatto trade-off che "
     "un traffic analyzer mappa col benchmark 64..1024 B. Sul banco: "
     "pannello L2, benchmark frame-size: guarda loss% salire e payload "
     "efficiency scendere ai due estremi opposti.",
     "size of generated L2 frames (real preamble+header+payload+FCS). "
     "Large frames maximize goodput (less per-byte overhead) but collect "
     "more bit errors per frame: at fixed BER, frame loss grows ~linearly "
     "with length — exactly the trade-off a traffic analyzer maps with the "
     "64..1024 B benchmark. On the bench: L2 panel, frame-size benchmark: "
     "watch loss% rise and payload efficiency fall at the two opposite "
     "ends.",
     "P(frame err) ≈ 1−(1−BER)^(8·bytes)")
_add("l2_ipg_bytes", "Ethernet traffic", "MAC/PCS stimulus",
     "inter-packet gap in byte: è la manopola del CARICO OFFERTO (lo "
     "standard minimo è 12 B; IPG grandi = linea quasi vuota). Il load "
     "ramp del pannello ONT la usa per tracciare goodput e loss in "
     "funzione dell'occupazione. Sul banco: IPG 12 vs 2000 — il goodput "
     "scende con l'occupazione, la BER di linea resta identica: separa "
     "concettualmente il PHY (bit) dal MAC (frame).",
     "inter-packet gap in bytes: the OFFERED-LOAD knob (the standard "
     "minimum is 12 B; large IPG = nearly idle line). The ONT panel's load "
     "ramp uses it to trace goodput and loss versus occupancy. On the "
     "bench: IPG 12 vs 2000 — goodput falls with occupancy while line BER "
     "stays identical: it conceptually separates the PHY (bits) from the "
     "MAC (frames).",
     "offered% = wire/(wire+IPG)", "pattern = eth")
_add("l2_streams", "Traffic generator", "PPG payload (frames)",
     "generatore multi-stream stile Xena: 1..4 flussi round-robin, ognuno "
     "con stream-id, sequence e frame size propri (64/512/1024 B per gli "
     "stream extra). L'analyzer attribuisce ok/FCS/persi PER stream — i "
     "frame grandi soffrono più bit error per frame, quindi a parità di "
     "linea gli stream non sono uguali. Con FEC in-path servono record "
     "lunghi perché un round intero cada in validation. Sul banco: 4 "
     "stream e confronta la loss% per stream nell'ispettore frame.",
     "Xena-style multi-stream generator: 1..4 round-robin flows, each "
     "with its own stream-id, sequence space, and frame size (64/512/1024 "
     "B for the extra streams). The analyzer attributes ok/FCS/lost PER "
     "stream — large frames take more bit errors per frame, so streams are "
     "not equal even on the same line. With in-path FEC, long records are "
     "needed for a full round inside validation. On the bench: enable 4 "
     "streams and compare per-stream loss% in the frame inspector.",
     "round = 1 frame per stream", "pattern = eth")

_add("l2_scheduler", "Traffic generator", "MAC scheduler (L2)",
     "scheduler dei frame fra gli stream (stile Xena): round_robin = un "
     "frame per stream a turno; weighted = weighted round-robin 'smooth' "
     "con i pesi l2_stream_weights (lo stream con più credito emette); "
     "imix = mix di size 64/576/1024 B in rapporto 7:4:1 (IMIX-like, "
     "dichiarato: il classico 1500 B non entra nel limite di 1024 B). "
     "Sul banco: pannello Traffic, tabella per stream (quota di frame ≈ "
     "pesi) e istogramma delle size.",
     "frame scheduler across streams (Xena-style): round_robin = one frame "
     "per stream in turn; weighted = smooth weighted round-robin with the "
     "l2_stream_weights (the stream with most credit transmits); imix = "
     "64/576/1024 B size mix at 7:4:1 (IMIX-like, declared: the classic "
     "1500 B does not fit the 1024 B cap). On the bench: Traffic panel, "
     "per-stream table (frame share ≈ weights) and size histogram.",
     "WRR: credit_i += w_i; emit argmax; credit -= Σw", "pattern = eth")
_add("l2_stream_weights", "Traffic generator", "MAC scheduler (L2)",
     "pesi degli stream 0..3 per lo scheduler weighted: la quota di frame "
     "di ogni stream è w_i/Σw (con 4:2:1:1 lo stream 0 emette la metà dei "
     "frame). Con round_robin o imix i pesi sono ignorati. Sul banco: "
     "confronta 'attesi' per stream nella tabella Traffic con i pesi.",
     "weights of streams 0..3 for the weighted scheduler: each stream's "
     "frame share is w_i/Σw (with 4:2:1:1 stream 0 sends half of the "
     "frames). Ignored by round_robin and imix. On the bench: compare the "
     "per-stream 'expected' column in the Traffic table with the weights.",
     "share_i = w_i / Σ w", "pattern = eth, l2_scheduler = weighted")
_add("l2_workload", "Traffic generator", "MAC scheduler (L2)",
     "profilo di WORKLOAD che impone mix di size e burst al generatore: "
     "ai_training = collettive all-reduce (frame grandi, burst lunghi "
     "sincroni con pause), llm_inference = richieste piccole e risposte "
     "medie a bassa latenza, storage = frame grandi continui, web = molti "
     "frame piccoli, video = frame medi a rate costante. custom = usa "
     "scheduler/size configurati. DICHIARATO: emulazione della FORMA del "
     "traffico su una singola corsia seriale — niente switch, code, "
     "congestione o RDMA. Sul banco: Traffic → KPI del workload (goodput, "
     "completamento burst, FLR di coda) e come le pause lunghe (idle "
     "scramblato) e i frame grandi reagiscono agli errori del PHY.",
     "WORKLOAD profile shaping size mix and bursts: ai_training = "
     "all-reduce collectives (large frames, long synchronous bursts with "
     "pauses), llm_inference = small requests and medium latency-sensitive "
     "replies, storage = continuous large frames, web = many small frames, "
     "video = medium frames at constant rate. custom = configured "
     "scheduler/size. DECLARED: emulation of the traffic SHAPE on one "
     "serial lane — no switch, queues, congestion or RDMA. On the bench: "
     "Traffic → workload KPIs (goodput, burst completion, tail FLR) and how "
     "long pauses (scrambled idle) and large frames react to PHY errors.",
     "burst on/off · size mix · streams", "pattern = eth")
_add("l2_drop_pct", "Impairment emulator", "between MAC and PCS",
     "percentuale di frame SCARTATI dall'emulatore di impairment prima del "
     "PCS (come il modulo impairment di un test set): il sequence number "
     "salta e l'analyzer li conta come 'persi (emulati)', separati dai "
     "persi per errori del PHY. Deterministico per configurazione.",
     "percentage of frames DROPPED by the impairment emulator before the "
     "PCS (like a test set's impairment module): the sequence number skips "
     "and the analyzer counts them as 'lost (emulated)', separate from "
     "PHY-error losses. Deterministic per configuration.",
     "P(drop) = pct/100", "pattern = eth")
_add("l2_dup_pct", "Impairment emulator", "between MAC and PCS",
     "percentuale di frame DUPLICATI (seconda copia con lo stesso sequence "
     "number): l'analyzer li conta come duplicati e non come frame ok in "
     "più. Sul banco: colonna 'dup' per stream.",
     "percentage of DUPLICATED frames (second copy with the same sequence "
     "number): the analyzer counts them as duplicates, not as extra good "
     "frames. On the bench: per-stream 'dup' column.",
     "P(dup) = pct/100", "pattern = eth")
_add("l2_misorder_pct", "Impairment emulator", "between MAC and PCS",
     "percentuale di frame RITARDATI di una posizione (escono dopo il frame "
     "successivo): l'analyzer li conta come fuori ordine (seq minore del "
     "massimo già visto sullo stesso stream).",
     "percentage of frames DELAYED by one position (sent after the next "
     "frame): the analyzer counts them as out-of-order (seq lower than the "
     "maximum already seen on the same stream).",
     "swap(f_i, f_{i+1})", "pattern = eth")
_add("l2_corrupt_pct", "Impairment emulator", "between MAC and PCS",
     "percentuale di frame CORROTTI: un bit di payload viene invertito DOPO "
     "il calcolo dell'FCS, quindi al RX la CRC-32 non torna. È il modo per "
     "vedere l'FCS lavorare senza errori del PHY: FCS bad ≥ corrotti emulati.",
     "percentage of CORRUPTED frames: one payload bit is flipped AFTER the "
     "FCS is computed, so the RX CRC-32 fails. It shows the FCS at work "
     "without PHY errors: FCS bad ≥ emulated corruptions.",
     "FCS ≠ CRC32(body)", "pattern = eth")
_add("l2_pcs_coding", "PCS (L1)", "between MAC frames and PMA",
     "livello L1 fra i frame e il PHY: scrambler = solo scrambler "
     "self-sync di Clause 49 sul flusso (baseline storica); 64b66b = "
     "codifica a blocchi di 66 bit con sync header 01/10, blocchi /S/ /D/ "
     "/T/ /I/, scrambler sul payload e BLOCK LOCK al RX (64 header validi "
     "consecutivi, hi_ber con ≥16 header errati). Overhead 66/64 = 3.125 % "
     "di bit di linea in più a parità di payload. DICHIARATO: niente "
     "alignment marker, 256b/257b, lane distribution. Sul banco: Traffic → "
     "sezione L1 (lock, offset, header errati, mix di blocchi) e "
     "checkpoint 'PCS 64b/66b block lock'.",
     "L1 layer between frames and PHY: scrambler = Clause 49 self-sync "
     "scrambler only (historic baseline); 64b66b = 66-bit block coding with "
     "01/10 sync headers, /S/ /D/ /T/ /I/ blocks, payload scrambler and RX "
     "BLOCK LOCK (64 consecutive valid headers, hi_ber with ≥16 bad "
     "headers). Overhead 66/64 = 3.125 % more line bits per payload. "
     "DECLARED: no alignment markers, 256b/257b or lane distribution. On "
     "the bench: Traffic → L1 section (lock, offset, header errors, block "
     "mix) and the 'PCS 64b/66b block lock' checkpoint.",
     "66 = 2 sync + 64 payload; lock: 64 valid headers", "pattern = eth")

# ==================================================== BERT error insertion
_add("err_insert_bits", "BERT PPG", "TX bits after reference copy",
     "numero di bit invertiti al TX DOPO aver conservato la copia di "
     "riferimento dell'error detector: gli errori attraversano l'intera "
     "catena fisica e vengono contati dall'ED come farebbe un BERT vero "
     "(è il test di sanità del contatore: inserted = counted su canale "
     "pulito). Con FEC attivo è lo strumento per esplorare la "
     "correggibilità: n bit sparsi toccano ~n simboli RS. Sul banco: "
     "inserisci 20 bit e verifica nel pannello BERT che la mappa errori "
     "mostri esattamente i marker attesi nella zona di validation.",
     "number of TX bits flipped AFTER the error detector's reference copy "
     "is taken: the errors traverse the whole physical chain and are "
     "counted by the ED exactly like a real BERT (the counter sanity "
     "check: inserted = counted on a clean channel). With FEC on it is the "
     "tool to explore correctability: n scattered bits touch ~n RS "
     "symbols. On the bench: insert 20 bits and verify the BERT error map "
     "shows exactly the expected markers inside the validation zone.",
     "one-shot sul prossimo record")
_add("err_insert_burst", "BERT PPG", "TX bits after reference copy",
     "raggruppa le inversioni in un burst CONSECUTIVO invece che sparso: a "
     "parità di bit, un burst concentra gli errori in pochi simboli RS "
     "adiacenti — è il caso che l'interleaving FEC esiste per spalmare, e "
     "il modo in cui un DFE reale sbaglia (propagazione di decisione). Sul "
     "banco: 60 bit sparsi vs burst con KP4 depth 1: il burst può bucare "
     "t=15 e perdere il frame dove gli sparsi vengono tutti corretti.",
     "groups the flips into one CONSECUTIVE burst instead of scattering "
     "them: at equal bit count, a burst concentrates errors into few "
     "adjacent RS symbols — the very case FEC interleaving exists to "
     "spread, and the way a real DFE fails (decision propagation). On the "
     "bench: 60 scattered vs burst bits with KP4 depth 1: the burst can "
     "break t=15 and lose the frame where scattered ones are all "
     "corrected.",
     "burst L simboli → L simboli RS adiacenti", "err_insert_bits > 0")
_add("err_insert_target", "BERT PPG", "TX bits after reference copy",
     "sceglie DOVE cadono i bit invertiti: random, solo lane MSB o LSB del "
     "simbolo PAM4 (il mapper è MSB-first), oppure rs_symbol — gruppi "
     "allineati GF(2¹⁰), così a parità di bit il FEC vede ~n/10 simboli RS "
     "errati invece di ~n: è il confronto sparsi-vs-concentrati fatto "
     "strumento. msb/lsb rendono visibile l'asimmetria del conteggio "
     "per-lane dell'ED. Sul banco: 30 bit random vs rs_symbol con KP4 e "
     "confronta simboli corretti e frame persi nel FEC live.",
     "chooses WHERE flipped bits land: random, MSB-only or LSB-only PAM4 "
     "lane (the mapper is MSB-first), or rs_symbol — GF(2¹⁰)-aligned "
     "groups, so for the same bit count the FEC sees ~n/10 wrong RS "
     "symbols instead of ~n: the scattered-vs-concentrated comparison as "
     "an instrument. msb/lsb expose the ED's per-lane counting asymmetry. "
     "On the bench: 30 random vs rs_symbol bits with KP4, compare "
     "corrected symbols and lost frames in FEC live.",
     active="err_insert_bits > 0 (msb/lsb: PAM4; burst ha precedenza)")
_add("tx_output_on", "TX driver", "driver output stage",
     "OUTPUT enable dello stadio TX come sul pannello di un PPG: OFF = il "
     "driver non pilota nulla (mute elettrico, P/N al solo common-mode). "
     "La sorgente ottica resta accesa: al PD arriva la CW filtrata dal "
     "bias, senza dati — il CDR perde l'aggancio e il link va DOWN "
     "davvero, con riaggancio automatico alla riaccensione. Sul banco: "
     "spegni e guarda in sequenza WAVE piatta al driver, SYNC LOSS "
     "all'ED, LINK DOWN in topbar. laser_dbm riduce la potenza solo fino "
     "a −6 dBm: un vero LASER OFF non è modellato da questo comando.",
     "TX OUTPUT enable as on a PPG front panel: OFF = the driver drives "
     "nothing (electrical mute, P/N at common-mode only). The optical "
     "source stays on: the PD receives bias-filtered CW light with no "
     "data — the CDR loses lock and the link goes truly DOWN, relocking "
     "on its own at re-enable. On the bench: switch it off and watch, in "
     "order, a flat WAVE at the driver, ED SYNC LOSS, topbar LINK DOWN. "
     "laser_dbm only reduces power down to −6 dBm: a true LASER OFF state "
     "is not modeled by this command.",
     active="sempre / always")

# ======================================================= TX PLL / SERIALIZER
_add("tx_rj_rms_fs", "TX PLL", "serializer time base",
     "aggiunge TIE gaussiano RMS indipendente a ogni UI; allarga le code "
     "senza limite deterministico. Sul Q-scale le code diventano rette di "
     "pendenza 1/σ e il TJ estrapola come TJ(p)=2·Q_p·σ+DJ(δδ); gli RJ "
     "indipendenti si sommano in quadratura, σ_tot=√Σσᵢ² (Derickson & "
     "Müller §2.4-2.5). Ordini di grandezza reali: un TX 112G di targa sta "
     "sotto ~200 fs rms integrati. Sul banco: 500 fs → nel pannello Jitter "
     "il tail-fit dual-Dirac deve restituire σ vicino al valore impostato, "
     "e il bathtub si allarga in proporzione.",
     "adds independent Gaussian RMS TIE to each UI; it broadens unbounded "
     "tails. On the Q scale the tails become straight lines of slope 1/σ "
     "and TJ extrapolates as TJ(p)=2·Q_p·σ+DJ(δδ); independent RJs add in "
     "quadrature, σ_tot=√Σσᵢ² (Derickson & Müller §2.4-2.5). Real orders "
     "of magnitude: a datasheet 112G TX stays below ~200 fs rms "
     "integrated. On the bench: set 500 fs → the Jitter panel's dual-Dirac "
     "tail fit must return σ close to the setting, and the bathtub widens "
     "in proportion.",
     "σUI=RJfs·10⁻¹⁵/UI; TJ(p)=2Q_p·σ+DJ(δδ)")
_add("tx_pj_amp_ui", "TX PLL", "serializer time base",
     "ampiezza di picco del jitter sinusoidale (SJ/PJ) iniettato sul time "
     "base: è il jitter DETERMINISTICO bounded per antonomasia, quello che "
     "le maschere JTOL prescrivono di tollerare. L'istogramma TIE di un PJ "
     "puro è la classica doppia gobba ad arcoseno. È anche la leva usata "
     "da stressed-eye cal e JTOL. Sul banco: 0.1 UI @ 20 MHz → il CDR (in "
     "banda) lo insegue quasi tutto; sposta la frequenza sopra la banda "
     "del loop e guarda lo stesso PJ mangiarsi l'occhio.",
     "peak amplitude of the sinusoidal jitter (SJ/PJ) injected on the "
     "time base: the canonical bounded DETERMINISTIC jitter, the one JTOL "
     "masks prescribe to tolerate. The TIE histogram of pure PJ is the "
     "classic arcsine double hump. It is also the lever used by "
     "stressed-eye cal and JTOL. On the bench: 0.1 UI @ 20 MHz → the CDR "
     "(in band) tracks most of it; move the frequency above the loop "
     "bandwidth and watch the same PJ eat the eye.",
     "TIE=A·sin(2πf·t); istogramma ad arcoseno")
_add("tx_pj_freq_mhz", "TX PLL", "serializer time base",
     "frequenza del tono PJ: è la variabile della JTOL. Sotto la banda del "
     "CDR (~cdr_bw·f_baud) il loop insegue e tollera ampiezze enormi; "
     "vicino al corner compare il jitter peaking del 2° ordine (il minimo "
     "locale della curva JTOL); sopra, il PJ passa quasi intero "
     "all'occhio. Sul banco: JTOL a 4 frequenze — la forma della curva È "
     "la firma della banda del loop; poi verifica il tono alla stessa "
     "frequenza nello spettro TIE del pannello Jitter.",
     "PJ tone frequency: the JTOL variable. Below the CDR bandwidth "
     "(~cdr_bw·f_baud) the loop tracks and tolerates huge amplitudes; near "
     "the corner the 2nd-order jitter peaking appears (the JTOL curve's "
     "local minimum); above it, PJ passes almost fully into the eye. On "
     "the bench: run JTOL at 4 frequencies — the curve's shape IS the loop "
     "bandwidth signature; then verify the tone at the same frequency in "
     "the Jitter panel's TIE spectrum.",
     "f_corner ≈ cdr_bw·f_baud", "tx_pj_amp_ui > 0")
_add("tx_dcd_pct", "TX PLL", "serializer edges",
     "duty-cycle distortion: alterna gli edge di ±DCD/2, separando le "
     "popolazioni pari/dispari del TIE — è il DJ correlato al mezzo-rate "
     "(la riga a f_baud/2 nello spettro TIE) tipico dei serializer 2:1 con "
     "mismatch dei rami. Nel dual-Dirac è la componente δδ più pulita. Sul "
     "banco: 10% → istogramma TIE bimodale netto nel pannello Jitter e "
     "riga a Nyquist/2 nello spettro; l'occhio si sdoppia orizzontalmente.",
     "duty-cycle distortion: alternates edges by ±DCD/2, splitting the "
     "even/odd TIE populations — the half-rate-correlated DJ (the "
     "f_baud/2 line in the TIE spectrum) typical of 2:1 serializers with "
     "leg mismatch. In dual-Dirac terms it is the cleanest δδ component. "
     "On the bench: 10% → sharply bimodal TIE histogram in the Jitter "
     "panel and a Nyquist/2 line in the spectrum; the eye splits "
     "horizontally.",
     "TIE=±DCD/2 alternato; riga a f_baud/2")
_add("tx_buj_amp_ui", "TX PLL / BERT", "serializer time base",
     "bounded-uncorrelated jitter: PRBS indipendente dai dati, filtrato "
     "passa-basso e scalato — il modo standard (dai BERT) di modellare "
     "aggressori tipo crosstalk di alimentazione: deterministico e "
     "bounded, ma senza correlazione col pattern, quindi non è DDJ. Nel "
     "dual-Dirac finisce nella componente bounded allargando il centro "
     "dell'istogramma. Sul banco: confrontalo col PJ a parità di ampiezza "
     "— niente riga spettrale, solo una collina larga nello spettro TIE.",
     "bounded-uncorrelated jitter: a data-independent PRBS, low-pass "
     "filtered and scaled — the standard (BERT-style) way to model "
     "aggressors like supply crosstalk: deterministic and bounded but "
     "uncorrelated with the pattern, hence not DDJ. In dual-Dirac terms "
     "it lands in the bounded component, widening the histogram core. On "
     "the bench: compare it with PJ at equal amplitude — no spectral "
     "line, just a broad hill in the TIE spectrum.",
     "PRBS7 indip. filtrata ~0.05·f_baud")
_add("tx_si_amp_pct", "TX driver / BERT", "driver output",
     "interferenza sinusoidale (SI) dello stressed-eye: un tono additivo "
     "sull'uscita del driver, ampiezza in percento dell'ampiezza di picco del "
     "segnale. È uno degli ingredienti del segnale di stress del ricevitore "
     "(121.8.9.2: SJ + SI + rumore) che l'MP1900A aggiunge con il suo "
     "generatore. 0 = spento. DICHIARATO: ampiezza e frequenza sono parametri "
     "dichiarati, la tabella SI di clausola non è trascritta. Sul banco: "
     "BERT → Stressed RX (SECQ) con SI, scope al driver per vedere il tono.",
     "sinusoidal interference (SI) of the stressed eye: an additive tone at the "
     "driver output, amplitude in percent of the signal peak amplitude. One of "
     "the ingredients of the receiver stress signal (121.8.9.2: SJ + SI + noise) "
     "that the MP1900A adds with its generator. 0 = off. DECLARED: amplitude and "
     "frequency are declared parameters, the clause SI table is not transcribed. "
     "On the bench: BERT → Stressed RX (SECQ) with SI, scope at the driver to see the tone.",
     "v += A·sin(2π f t), A = pct/100 · V_pk", "valore > 0")
_add("tx_si_freq_mhz", "TX driver / BERT", "driver output",
     "frequenza del tono di interferenza sinusoidale: bassa (decine di MHz) "
     "= modulazione lenta del baseline che il CDR/AGC possono inseguire, alta "
     "(GHz) = interferenza in banda che chiude l'occhio. Sul banco: cambia f a "
     "pari ampiezza e guarda l'EH@BER.",
     "frequency of the sinusoidal interference tone: low (tens of MHz) = slow "
     "baseline modulation the CDR/AGC can track, high (GHz) = in-band "
     "interference closing the eye. On the bench: change f at equal amplitude "
     "and watch EH@BER.",
     "f [MHz]", "tx_si_amp_pct > 0")

_add("tx_ssc_ppm", "TX PLL", "serializer frequency/phase",
     "profondità del down-spread: la frequenza viene modulata a triangolo "
     "verso il basso (mai sopra il nominale, per non violare i limiti "
     "EMI) di ppm picco. Il TIE è l'INTEGRALE della deviazione di "
     "frequenza: pochi kHz di modulazione su migliaia di ppm producono "
     "escursioni di fase di decine di UI che il CDR DEVE inseguire col "
     "registro di frequenza. Tipico PCIe/SATA: 3000-5000 ppm. Sul banco: "
     "pannello Timing → il registro di frequenza del loop disegna il "
     "triangolo; se il record è corto ne vedi un segmento.",
     "down-spread depth: frequency is triangle-modulated downward (never "
     "above nominal, to respect EMI limits) by peak ppm. TIE is the "
     "INTEGRAL of the frequency deviation: a few kHz of modulation over "
     "thousands of ppm produces tens of UI of phase excursion the CDR "
     "MUST track with its frequency register. PCIe/SATA typical: "
     "3000-5000 ppm. On the bench: Timing panel → the loop's frequency "
     "register draws the triangle; with a short record you see one "
     "segment.",
     "TIE(t)=∫Δf/f₀ dt/UI")
_add("tx_ssc_khz", "TX PLL", "serializer frequency/phase",
     "frequenza della modulazione SSC (tipico 30-33 kHz): più è lenta, più "
     "il CDR la insegue facilmente ma più lunga è l'escursione di fase "
     "accumulata per ciclo. Il rapporto fra banda del loop e f_SSC decide "
     "il residuo di tracking che finisce nell'occhio. Sul banco: alza "
     "f_SSC verso la banda del loop e guarda crescere l'errore di fase "
     "residuo nell'istogramma del pannello Timing.",
     "SSC modulation frequency (typical 30-33 kHz): the slower it is, the "
     "easier the CDR tracks it, but the longer the phase excursion "
     "accumulated per cycle. The loop-bandwidth to f_SSC ratio decides "
     "the tracking residual that lands in the eye. On the bench: raise "
     "f_SSC toward the loop bandwidth and watch the residual phase error "
     "grow in the Timing panel's histogram.",
     "residuo ∝ f_SSC/f_loop", "tx_ssc_ppm > 0")

# ============================================================ TX FIR / DAC
_add("tx_ffe_taps", "TX FIR", "symbol stream before DAC",
     "coefficienti reali pre/main/post-cursor del FIR di trasmissione (3 o "
     "5 tap): l'enfasi scava via l'ISI ATTESA del canale prima che accada, "
     "al prezzo di swing — la somma |c_i| è vincolata, quindi ogni dB di "
     "de-enfasi toglie ampiezza al main cursor (il costo è mostrato come "
     "swing cost). È l'oggetto negoziato dal link training di Clause "
     "72/136 (richieste increment/decrement per coefficiente). Sul banco: "
     "su canale con echo, sposta il post-cursor e guarda l'occhio pre-DSP "
     "aprirsi mentre lo swing scende; AN/LT lo fa da solo, tap per tap.",
     "real pre/main/post-cursor coefficients of the transmit FIR (3 or 5 "
     "taps): emphasis digs out the channel's EXPECTED ISI before it "
     "happens, at the price of swing — the |c_i| sum is constrained, so "
     "every dB of de-emphasis takes amplitude from the main cursor (shown "
     "as swing cost). It is the object negotiated by Clause 72/136 link "
     "training (per-coefficient increment/decrement requests). On the "
     "bench: on an echoey channel move the post-cursor and watch the "
     "pre-DSP eye open while swing drops; AN/LT does it for you, tap by "
     "tap.",
     "H(eʲω)=Σ c[k]e⁻ʲωk; Σ|c|≤vincolo")
_add("dac_bits", "DAC", "DAC output",
     "risoluzione del DAC di trasmissione: i TX PAM4 reali usano 7-8 bit "
     "per avere margine su FIR (che consuma livelli) e nonlinearità. Il "
     "rumore di quantizzazione scala −6 dB/bit; sotto ~5 bit i gradini "
     "diventano visibili sugli edge e l'SNDR del TX crolla. Sul banco: "
     "scendi a 4-5 bit e guarda l'SNDR nello Scope e i gradini nella "
     "vista WAVE del nodo driver.",
     "transmit DAC resolution: real PAM4 TXs use 7-8 bits to leave margin "
     "for the FIR (which consumes levels) and nonlinearity. Quantization "
     "noise scales −6 dB/bit; below ~5 bits the steps become visible on "
     "edges and TX SNDR collapses. On the bench: drop to 4-5 bits and "
     "watch SNDR in the Scope and the staircase in the driver-node WAVE "
     "view.",
     "SQNR≈6.02·N+1.76 dB")
_add("dac_full_scale_vpp", "DAC", "DAC output",
     "fondo scala del DAC: fissa il rapporto fra il segnale (post-FIR, che "
     "può superare 1 in picco) e le soglie di clipping del convertitore. "
     "Poco fondo scala clippa i picchi dell'enfasi — una nonlinearità "
     "dura, non recuperabile; troppo fondo scala butta bit di risoluzione "
     "sul rumore. Sul banco: con FIR aggressivo, riduci il FS e guarda "
     "salire la clip fraction del DAC e comparire compressione sui "
     "livelli esterni.",
     "DAC full scale: sets the ratio between the (post-FIR, possibly "
     ">1-peak) signal and the converter's clipping thresholds. Too little "
     "full scale clips emphasis peaks — a hard, unrecoverable "
     "nonlinearity; too much wastes resolution bits on noise. On the "
     "bench: with an aggressive FIR, reduce FS and watch the DAC clip "
     "fraction rise and outer-level compression appear.",
     "clip se |v|>FS/2")
_add("dac_bw_hz", "TX analog", "DAC output",
     "banda −3 dB (Butterworth 3° ordine) dello stadio d'uscita DAC: con "
     "lo zero-order hold già attenua sin(x)/x, questo polo arrotonda "
     "ulteriormente gli edge. Regola pratica: serve ≥0.5·f_baud per non "
     "pagare ISI significativa; i TX reali stanno a ~0.6-0.75·f_baud. Sul "
     "banco: 22 GHz su 56 GBd (0.39·baud) → edge lenti nella WAVE, "
     "SNDR/TDECQ peggiorano; il TX FIR può compensarne una parte.",
     "−3 dB bandwidth (3rd-order Butterworth) of the DAC output stage: on "
     "top of the zero-order hold's sin(x)/x, this pole further rounds the "
     "edges. Rule of thumb: ≥0.5·f_baud is needed to avoid significant "
     "ISI; real TXs sit at ~0.6-0.75·f_baud. On the bench: 22 GHz at 56 "
     "GBd (0.39·baud) → slow edges in WAVE, SNDR/TDECQ degrade; the TX "
     "FIR can compensate part of it.",
     "consiglio: BW ≥ 0.5·f_baud")
_add("driver_bw_hz", "TX analog", "driver output",
     "banda −3 dB del driver (il secondo polo analogico del TX, in cascata "
     "al DAC): le bande si compongono, 1/BW²tot ≈ 1/BW²dac+1/BW²drv, "
     "quindi due stadi da 0.6·baud equivalgono a uno da ~0.42·baud. Sul "
     "banco: stringila da sola e poi insieme a dac_bw_hz — l'effetto "
     "composto sugli edge della WAVE è più che additivo.",
     "driver −3 dB bandwidth (the TX's second analog pole, cascaded after "
     "the DAC): bandwidths compose, 1/BW²tot ≈ 1/BW²dac+1/BW²drv, so two "
     "0.6·baud stages equal one at ~0.42·baud. On the bench: narrow it "
     "alone and then together with dac_bw_hz — the composite effect on "
     "WAVE edges is more than additive.",
     "1/BW²tot≈Σ1/BWᵢ²")
_add("driver_gain_v_per_unit", "Driver", "driver differential output",
     "guadagno del driver in volt per unità di segnale normalizzato: fissa "
     "lo swing differenziale lanciato nel canale (o nel modulatore). Più "
     "swing = più SNR a valle finché non si toccano le rail: da lì in poi "
     "ogni dB in più è distorsione, non segnale. Sul banco: alzalo fino a "
     "vedere la clip fraction del driver diventare non-zero — quello è il "
     "punto di compressione del tuo TX.",
     "driver gain in volts per normalized signal unit: sets the "
     "differential swing launched into the channel (or modulator). More "
     "swing = more downstream SNR until the rails are hit: beyond that, "
     "every extra dB is distortion, not signal. On the bench: raise it "
     "until the driver clip fraction goes non-zero — that is your TX's "
     "compression point.",
     "Vout=G·v(t), poi clip alle rail")
_add("driver_clip_v", "Driver", "driver differential output",
     "rail di uscita del driver: il clipping è una nonlinearità DURA che "
     "taglia i picchi (prima quelli dell'enfasi FIR) e genera "
     "intermodulazione che nessun equalizzatore lineare a valle può "
     "disfare. I livelli esterni PAM4 si comprimono → RLM peggiora. Sul "
     "banco: abbassa le rail e guarda insieme clip fraction, RLM proxy "
     "nello Scope e i livelli esterni schiacciarsi negli istogrammi.",
     "driver output rails: clipping is a HARD nonlinearity that cuts "
     "peaks (FIR emphasis peaks first) and creates intermodulation no "
     "downstream linear equalizer can undo. PAM4 outer levels compress → "
     "RLM degrades. On the bench: lower the rails and watch clip "
     "fraction, the Scope's RLM proxy, and the outer levels flattening in "
     "the histograms together.",
     "hard clip: v=±Vrail oltre soglia")
_add("causal_filters", "Analog filters", "all selected analog blocks",
     "sceglie fra fase zero didattica (magnitudine giusta, ritardo nullo — "
     "comodo per confrontare forme d'onda allineate) e risposta CAUSALE "
     "con la stessa magnitudine ma group delay fisico reale. Solo in "
     "modalità causale la latenza analogica misurata (xcorr del pannello "
     "ONT) ha senso fisico. Sul banco: attivalo e guarda le waveform "
     "WAVE spostarsi nel tempo mentre l'occhio resta praticamente "
     "identico — la fase minima ridistribuisce il ritardo, non la banda.",
     "chooses between educational zero phase (correct magnitude, zero "
     "delay — handy for aligned waveform comparisons) and a CAUSAL "
     "response with the same magnitude but real physical group delay. "
     "Only in causal mode does the measured analog latency (the ONT "
     "panel's xcorr) make physical sense. On the bench: enable it and "
     "watch WAVE waveforms shift in time while the eye stays essentially "
     "identical — minimum phase redistributes delay, not bandwidth.")

# ====================================================== COPPIA P/N / FIXTURE
_add("pn_skew_ps", "Differential fixture", "driver P/N pins",
     "ritardo fra i rami P e N della coppia differenziale: converte modo "
     "differenziale in modo comune e scava un NOTCH nel differenziale a "
     "f=1/(2τ) — 4 ps di skew mettono il notch a 125 GHz, 20 ps a 25 GHz, "
     "in piena banda. È il classico killer da connettore/fixture "
     "sbilanciata, ed è il motivo per cui i canali si misurano in "
     "mixed-mode (SDD21/SCD21). Sul banco: vista Scope P/N — con skew i "
     "singoli rami restano belli ma Vdiff si deforma; guarda SCD21 salire "
     "caricando un S4P col mapping sbagliato.",
     "delay between the P and N legs of the differential pair: it "
     "converts differential into common mode and digs a NOTCH in the "
     "differential at f=1/(2τ) — 4 ps of skew puts the notch at 125 GHz, "
     "20 ps at 25 GHz, right in band. The classic unbalanced "
     "connector/fixture killer, and the reason channels are measured in "
     "mixed-mode (SDD21/SCD21). On the bench: Scope P/N view — with skew "
     "the individual legs look fine while Vdiff warps; watch SCD21 rise "
     "when loading an S4P with the wrong mapping.",
     "f_notch=1/(2τ)")
_add("pn_gain_mismatch_pct", "Differential fixture", "driver P/N pins",
     "sbilanciamento di ampiezza fra i rami: da solo genera conversione "
     "DM→CM (il differenziale perde poco); diventa pericoloso nell'altra "
     "direzione, CM→DM, quando ESISTE un modo comune da convertire "
     "(offset o rumore CM) — allora il disturbo entra nel segnale utile. "
     "Sul banco: 10% di mismatch senza CM non fa quasi nulla; aggiungi "
     "vcm_offset_v e guarda il differenziale sporcarsi.",
     "amplitude imbalance between the legs: alone it creates DM→CM "
     "conversion (the differential barely suffers); it becomes dangerous "
     "in the other direction, CM→DM, when there IS common mode to convert "
     "(CM offset or noise) — then the disturbance enters the useful "
     "signal. On the bench: 10% mismatch with no CM does almost nothing; "
     "add vcm_offset_v and watch the differential get dirty.",
     "CM→DM ∝ ε·V_cm")
_add("vcm_offset_v", "Common-mode source", "driver P/N pins",
     "modo comune DC sui pin P/N: un ricevitore differenziale ideale lo "
     "cancella per definizione — diventa osservabile (e dannoso) solo "
     "attraverso i difetti: mismatch dei rami, sonde single-ended, range "
     "di ingresso dell'AFE. È il compagno di scena di "
     "pn_gain_mismatch_pct. Sul banco: guardalo direttamente sul nodo "
     "V_cm dello Scope coerente (P/N·Diff·CM) e verifica che Vdiff non "
     "cambi finché il mismatch è zero.",
     "DC common mode on the P/N pins: an ideal differential receiver "
     "rejects it by definition — it becomes observable (and harmful) only "
     "through imperfections: leg mismatch, single-ended probing, AFE "
     "input range. The scene partner of pn_gain_mismatch_pct. On the "
     "bench: watch it directly on the coherent Scope's V_cm node "
     "(P/N·Diff·CM) and verify Vdiff does not move while mismatch is "
     "zero.",
     "vp,vn += V_cm; Vdiff invariato se bilanciato")
_add("vcm_noise_mv", "Common-mode source", "driver P/N pins",
     "rumore di modo comune (alimentazioni, ground bounce): stessa fisica "
     "dell'offset ma stocastico — reiettato dal differenziale perfetto, "
     "convertito in rumore differenziale dai mismatch. Il CMRR di un "
     "front-end reale è finito proprio per questo. Sul banco: rumore CM "
     "20 mV + mismatch 10% → guarda salire il floor negli istogrammi "
     "dello slicer; senza mismatch, non succede nulla.",
     "common-mode noise (supplies, ground bounce): same physics as the "
     "offset but stochastic — rejected by a perfect differential, "
     "converted into differential noise by mismatches. This is exactly "
     "why a real front-end's CMRR is finite. On the bench: 20 mV CM noise "
     "+ 10% mismatch → the slicer histograms' floor rises; with zero "
     "mismatch, nothing happens.",
     "σ_DM ≈ ε·σ_CM")
_add("tx_diff_noise_mv", "BERT stress", "driver differential pins",
     "rumore bianco DIFFERENZIALE iniettato dopo il driver ideale: è la "
     "manopola di interferenza degli stressed test (nei BERT reali: "
     "sinusoidal interference / broadband noise). A differenza del rumore "
     "CM entra dritto nel segnale utile, indipendentemente dal "
     "bilanciamento. Iniettato dopo il nodo diagnostico del driver, così "
     "il suo reference plane a monte resta pulito. Sul banco: è il "
     "compagno del PJ nella ricetta stressed-eye — alzalo e guarda "
     "l'occhio riempirsi verticalmente (il PJ lo mangia in orizzontale).",
     "DIFFERENTIAL white noise injected after the ideal driver: the "
     "interference knob of stressed tests (in real BERTs: sinusoidal "
     "interference / broadband noise). Unlike CM noise it enters the "
     "useful signal directly, regardless of balance. Injected after the "
     "driver's diagnostic node, so its upstream reference plane stays "
     "clean. On the bench: it is PJ's partner in the stressed-eye recipe "
     "— raise it and watch the eye fill vertically (PJ eats it "
     "horizontally).")
_add("electrical_drive_mode", "Probe / drive selector", "channel or modulator input",
     "sceglie quale segnale della coppia consuma DAVVERO il blocco "
     "successivo: Vp−Vn (differenziale, il caso normale), oppure il solo "
     "ramo P o N (single-ended, metà ampiezza e nessuna reiezione CM). "
     "Serve a toccare con mano PERCHÉ il differenziale vince: stesso "
     "canale, stesso rumore CM, metti single-ended e guarda entrare tutto "
     "il modo comune. Sul banco: con vcm_noise attivo, differenziale vs "
     "single-ended è una dimostrazione da manuale.",
     "chooses which pair signal the next block ACTUALLY consumes: Vp−Vn "
     "(differential, the normal case) or the P or N leg alone "
     "(single-ended, half amplitude and no CM rejection). It lets you "
     "touch WHY differential wins: same channel, same CM noise, go "
     "single-ended and watch all the common mode walk in. On the bench: "
     "with vcm_noise on, differential vs single-ended is a textbook "
     "demonstration.")

# ========================================================= CANALE ELETTRICO
_add("link_medium", "Link topology", "channel output",
     "commuta atomicamente l'intera topologia: rame (canale elettrico "
     "dritto nell'AFE — il mondo KR/CR/C2M dei backplane e dei cavi) "
     "oppure ottico (driver → modulatore → fibra → PD → TIA). Cambiano i "
     "blocchi attivi, i nodi osservabili dello Scope, le manopole "
     "pertinenti e perfino quali protocolli hanno senso (Clause 73 AN "
     "esiste solo su rame; sull'ottica la gestione è CMIS). Sul banco: al "
     "cambio, la catena SVG si ridisegna e i pannelli ottici si dichiarano "
     "inattivi sul rame.",
     "atomically switches the whole topology: copper (electrical channel "
     "straight into the AFE — the KR/CR/C2M world of backplanes and "
     "cables) or optical (driver → modulator → fiber → PD → TIA). It "
     "changes the active blocks, the Scope's observable nodes, the "
     "relevant knobs, and even which protocols make sense (Clause 73 AN "
     "exists only on copper; optics is managed via CMIS). On the bench: "
     "on switch, the chain SVG redraws and optical panels declare "
     "themselves inactive on copper.")
_add("channel_il_nyquist_db", "Electrical channel", "smooth channel S21",
     "perdita di inserzione della componente LISCIA del canale alla "
     "frequenza di Nyquist: è IL numero con cui si classificano i canali "
     "elettrici (una scheda host C2M sta sotto ~11-13 dB, un backplane "
     "KR arriva a 28-30 dB e oltre). La pendenza ~√f tipo skin effect è "
     "modellata; l'S21 totale aggiunge l'eco da return loss. Ogni dB in "
     "più a Nyquist è ISI che TX FIR + CTLE + DSP devono ripagare. Sul "
     "banco: 8→18 dB e guarda in sequenza occhio pre-DSP chiudersi, la "
     "CTLE arrampicarsi, il COM scendere.",
     "insertion loss of the channel's SMOOTH component at Nyquist: THE "
     "number electrical channels are classified by (a C2M host board "
     "stays below ~11-13 dB, a KR backplane reaches 28-30 dB and beyond). "
     "The skin-effect-like ~√f slope is modeled; total S21 adds the "
     "return-loss echo. Every extra dB at Nyquist is ISI that TX FIR + "
     "CTLE + DSP must pay back. On the bench: sweep 8→18 dB and watch, in "
     "order, the pre-DSP eye close, the CTLE climb, COM drop.",
     "IL(f)≈IL_Nyq·√(f/f_Nyq) (liscia)")
_add("channel_delay_ps", "Electrical channel", "channel S21 phase",
     "ritardo di gruppo nominale del canale (fase lineare): da solo "
     "trasla il segnale nel tempo senza toccare l'occhio — il CDR lo "
     "assorbe nel suo delay stimato. Conta come base d'appoggio per "
     "l'eco (echo_delay_ui è relativo) e per la latenza analogica "
     "misurata nel pannello ONT. Sul banco: cambialo e guarda la latenza "
     "xcorr spostarsi di pari passo, con l'occhio identico.",
     "the channel's nominal group delay (linear phase): alone it shifts "
     "the signal in time without touching the eye — the CDR absorbs it in "
     "its estimated delay. It matters as the reference for the echo "
     "(echo_delay_ui is relative) and for the measured analog latency in "
     "the ONT panel. On the bench: change it and watch the xcorr latency "
     "move in step, with an identical eye.")
_add("group_delay_ripple_ps", "Electrical channel", "channel S21 phase",
     "ripple del ritardo di gruppo (fase NON lineare a perdita "
     "invariata): frequenze diverse arrivano in tempi diversi → "
     "dispersione elettrica, DDJ e code ISI asimmetriche che l'occhio "
     "mostra come bordi sfrangiati. È il difetto tipico di via stub e "
     "discontinuità. Sul banco: alzalo tenendo fissa la IL e guarda il "
     "DDJ crescere nel pannello Jitter mentre la perdita non cambia — "
     "fase e ampiezza sono degradazioni indipendenti.",
     "group-delay ripple (NONlinear phase at unchanged loss): different "
     "frequencies arrive at different times → electrical dispersion, DDJ "
     "and asymmetric ISI tails the eye shows as frayed edges. The typical "
     "defect of via stubs and discontinuities. On the bench: raise it at "
     "fixed IL and watch DDJ grow in the Jitter panel while loss stays "
     "put — phase and amplitude are independent degradations.")
_add("return_loss_db", "Electrical channel", "channel S21 mismatch term",
     "quanto ogni discontinuità riflette: due riflessioni successive "
     "creano un'ECO che viaggia avanti sommandosi ritardata al segnale "
     "(|Γ|²), cioè ripple in frequenza e un cursore ISI isolato nel "
     "tempo. RL basso (8-10 dB) = connettori scadenti; le clause "
     "prescrivono maschere di RL proprio per limitare queste eco. Sul "
     "banco: peggioralo e guarda comparire il ripple nell'S21 del "
     "pannello Canale e un post-cursore isolato nel pulse response del "
     "COM.",
     "how much each discontinuity reflects: two successive reflections "
     "create an ECHO that travels forward, adding delayed to the signal "
     "(|Γ|²) — frequency ripple and one isolated ISI cursor in time. Low "
     "RL (8-10 dB) = poor connectors; clauses prescribe RL masks "
     "precisely to bound these echoes. On the bench: worsen it and watch "
     "ripple appear in the Channel panel's S21 and an isolated "
     "post-cursor in COM's pulse response.",
     "|Γ|=10^(−RL/20); eco ∝ |Γ|²")
_add("echo_delay_ui", "Electrical channel", "channel S21 mismatch term",
     "ritardo dell'eco di mismatch in UI: fissa DOVE cade il cursore ISI "
     "riflesso e il passo del ripple in frequenza (Δf=1/τ_eco). Un'eco a "
     "2.5 UI mette un post-cursore che un DFE con ≥3 tap può cancellare; "
     "a 20 UI serve memoria che il DFE non ha. Sul banco: sposta il "
     "ritardo e osserva il post-cursore migrare nel pulse response — poi "
     "verifica se i tap DFE riescono ancora a coprirlo.",
     "mismatch-echo delay in UI: it sets WHERE the reflected ISI cursor "
     "lands and the frequency-ripple pitch (Δf=1/τ_echo). An echo at 2.5 "
     "UI creates a post-cursor a ≥3-tap DFE can cancel; at 20 UI it needs "
     "memory the DFE does not have. On the bench: move the delay and "
     "watch the post-cursor migrate in the pulse response — then check "
     "whether the DFE taps still reach it.",
     "ripple: Δf=1/τ_eco", "return_loss_db attivo")
_add("xtalk_next_db", "Aggressor", "channel near end",
     "crosstalk NEAR-END: l'aggressore accoppia vicino al ricevitore, "
     "quindi arriva NON attenuato dal canale mentre il segnale utile è "
     "già stanco — è per questo che il NEXT è il crosstalk cattivo (in "
     "COM pesa nel rumore integrato alla DER target). Valore = "
     "accoppiamento a Nyquist relativo; 0 nella UI = OFF. Sorgente PRBS "
     "indipendente, non cancellabile dal DSP. Sul banco: −30 dB di NEXT "
     "su un canale da 18 dB e guarda il floor di rumore salire negli "
     "istogrammi slicer e il COM scendere.",
     "NEAR-END crosstalk: the aggressor couples near the receiver, so it "
     "arrives UNattenuated by the channel while the victim signal is "
     "already tired — this is why NEXT is the nasty crosstalk (COM "
     "weighs it in the DER-target integrated noise). Value = relative "
     "coupling at Nyquist; UI 0 = OFF. Independent PRBS source, not "
     "cancellable by the DSP. On the bench: −30 dB NEXT on an 18 dB "
     "channel — the slicer histograms' noise floor rises and COM drops.",
     "vicino al RX: non filtrato dal canale", "valore < 0 dB")
_add("xtalk_fext_db", "Aggressor", "channel far end",
     "crosstalk FAR-END: l'aggressore percorre il canale INSIEME alla "
     "vittima, quindi arriva filtrato e attenuato dalla stessa perdita — "
     "a parità di accoppiamento è molto più mite del NEXT. Sul banco: "
     "stesso valore in NEXT e in FEXT, confronta l'effetto su Q e COM: "
     "la differenza che vedi è esattamente la perdita del canale "
     "applicata all'aggressore.",
     "FAR-END crosstalk: the aggressor travels the channel WITH the "
     "victim, so it arrives filtered and attenuated by the same loss — "
     "at equal coupling it is far milder than NEXT. On the bench: set "
     "the same value in NEXT and FEXT and compare the effect on Q and "
     "COM: the difference you see is exactly the channel loss applied to "
     "the aggressor.",
     "attraversa il canale: filtrato", "valore < 0 dB")
_add("s2p_text", "Measured channel", "channel S-parameter plane",
     "contenuto Touchstone (S2P o S4P) del canale MISURATO: quando è "
     "attivo, il datapath usa S21/SDD21 vero — con tutte le sue "
     "risonanze, il ripple e la fase reale — al posto del modello "
     "sintetico liscio+eco. È il ponte fra il banco e un VNA: incolla la "
     "misura di un tuo canale e la catena la attraversa davvero. Sul "
     "banco: carica l'esempio dal pannello Canale e confronta l'S21 "
     "misurato col sintetico a pari IL di targa.",
     "Touchstone content (S2P or S4P) of a MEASURED channel: when "
     "active, the datapath uses the true S21/SDD21 — with all its "
     "resonances, ripple, and real phase — instead of the smooth+echo "
     "synthetic model. The bridge between the bench and a VNA: paste "
     "your own channel's measurement and the chain actually traverses "
     "it. On the bench: load the example from the Channel panel and "
     "compare measured S21 with the synthetic one at equal nameplate "
     "IL.",
     active="use_s2p_channel = true")
_add("s2p_name", "Measured channel", "channel S-parameter plane",
     "etichetta del file Touchstone caricato: puro metadato di "
     "provenienza mostrato nel pannello Canale — serve alla "
     "tracciabilità della misura (quale canale sto usando?), non alla "
     "fisica.",
     "label of the loaded Touchstone file: pure provenance metadata "
     "shown in the Channel panel — it serves measurement traceability "
     "(which channel am I using?), not physics.",
     active="use_s2p_channel = true")
_add("use_s2p_channel", "Measured channel", "channel S-parameter plane",
     "interruttore fra modello sintetico e canale misurato: separa il "
     "CONTENUTO del Touchstone (s2p_text) dalla decisione di usarlo. "
     "Spegnerlo con un file caricato è il confronto A/B istantaneo "
     "sintetico-vs-misurato a parità di tutto il resto. Sul banco: "
     "toggle e guarda S21, pulse response e BER cambiare insieme.",
     "switch between synthetic model and measured channel: it separates "
     "the Touchstone CONTENT (s2p_text) from the decision to use it. "
     "Turning it off with a file loaded is the instant synthetic-vs-"
     "measured A/B at everything-else-equal. On the bench: toggle it and "
     "watch S21, pulse response, and BER move together.")
_add("s4p_pairs", "Measured channel", "channel S-parameter plane",
     "mapping delle porte del Touchstone a 4 porte: 13_24 (1→3, 2→4) o "
     "12_34. Sbagliarlo NON è innocuo: le coppie differenziali risultano "
     "incrociate, l'SDD21 si calcola su rami sbagliati e l'SCD21 "
     "(conversione di modo) esplode — il classico errore di laboratorio "
     "con un VNA a 4 porte. Sul banco: carica un S4P e prova entrambi i "
     "mapping: quello giusto minimizza SCD21.",
     "port mapping of the 4-port Touchstone: 13_24 (1→3, 2→4) or 12_34. "
     "Getting it wrong is NOT harmless: differential pairs end up "
     "crossed, SDD21 is computed on the wrong legs and SCD21 (mode "
     "conversion) explodes — the classic 4-port VNA lab mistake. On the "
     "bench: load an S4P and try both mappings: the correct one "
     "minimizes SCD21.",
     active="file S4P caricato")

# ============================================================= TX OTTICO
_add("optical_modulator", "Optical transmitter", "E/O",
     "architettura elettro-ottica: MZM (CW esterno + interferometro — il "
     "riferimento di linearità per DR/FR), EML (elettroassorbimento "
     "integrato — compatto, ER finito, chirp proprio), DML (laser "
     "modulato direttamente — economico, chirp forte) o VCSEL (multimodo "
     "850 nm per corto raggio). Il selettore è ATOMICO: cambia anche la "
     "sorgente compatibile e, per il VCSEL, forza fibra MMF a 850 nm. "
     "Cambia la legge large-signal, il chirp e quindi come la dispersione "
     "morde. Sul banco: stessa fibra, MZM vs DML — guarda il TDECQ "
     "divergere con i km.",
     "electro-optic architecture: MZM (external CW + interferometer — "
     "the linearity reference for DR/FR), EML (integrated "
     "electro-absorption — compact, finite ER, its own chirp), DML "
     "(directly modulated laser — cheap, strong chirp) or VCSEL "
     "(multimode 850 nm short reach). The selector is ATOMIC: it also "
     "switches the compatible source and, for VCSEL, forces MMF fiber at "
     "850 nm. It changes the large-signal law, the chirp, and hence how "
     "dispersion bites. On the bench: same fiber, MZM vs DML — watch "
     "TDECQ diverge with the kilometers.")
_add("laser_type", "Optical transmitter", "optical source",
     "sorgente ottica accoppiata all'architettura: CW DFB per MZM "
     "esterno, DFB integrato per EML, DFB diretto per DML, VCSEL "
     "multimodo. È l'altra faccia del selettore di modulatore (i due si "
     "muovono insieme per restare fisicamente coerenti): determina "
     "linewidth tipica, potenza disponibile e lunghezza d'onda sensata.",
     "optical source paired with the architecture: CW DFB for external "
     "MZM, integrated DFB for EML, direct DFB for DML, multimode VCSEL. "
     "The other face of the modulator selector (they move together to "
     "stay physically consistent): it determines typical linewidth, "
     "available power, and the sensible wavelength.")
_add("laser_dbm", "Laser", "laser output",
     "potenza ottica media della sorgente PRIMA di ogni perdita: il "
     "budget di potenza parte da qui e scende dB per dB attraverso "
     "IL del modulatore, accoppiamenti e fibra fino al 'PD input' (il "
     "pannello Ottica lo mostra passo-passo, e il cascade audit verifica "
     "che sia esattamente dB-per-dB). Nota la doppia pendenza: la "
     "fotocorrente scala linearmente coi dBm, ma la potenza ELETTRICA "
     "del segnale col QUADRATO — per questo 3 dB ottici valgono ~6 dB "
     "elettrici di SNR (finché non domina il RIN). Sul banco: è la "
     "manopola della sensitivity search del BERT.",
     "average optical source power BEFORE any loss: the power budget "
     "starts here and steps down dB by dB through modulator IL, "
     "couplings, and fiber to 'PD input' (the Optics panel shows it step "
     "by step, and the cascade audit verifies it is exactly dB-per-dB). "
     "Note the double slope: photocurrent scales linearly with dBm, but "
     "the signal's ELECTRICAL power with its SQUARE — hence 3 optical dB "
     "are worth ~6 electrical dB of SNR (until RIN dominates). On the "
     "bench: this is the BERT sensitivity search's lever.",
     "P[W]=1mW·10^(dBm/10); ΔSNRel≈2·ΔdBopt")
_add("laser_linewidth_mhz", "Laser", "optical field phase",
     "linewidth Lorentziana della sorgente (fase Wiener): il rumore di "
     "fase da solo è invisibile a un PD (che rileva intensità) — diventa "
     "rumore di INTENSITÀ quando la dispersione della fibra converte "
     "FM/PM in AM. Un DFB sta a ~1-10 MHz. Sul banco: con fibra a "
     "dispersione alta, alza la linewidth e guarda il floor salire; a "
     "0 km l'effetto sparisce — la conversione richiede la dispersione.",
     "the source's Lorentzian linewidth (Wiener phase): phase noise "
     "alone is invisible to a PD (which detects intensity) — it becomes "
     "INTENSITY noise when fiber dispersion converts FM/PM into AM. A "
     "DFB sits at ~1-10 MHz. On the bench: with high-dispersion fiber, "
     "raise the linewidth and watch the floor rise; at 0 km the effect "
     "vanishes — the conversion requires dispersion.",
     "PM→AM via dispersione")
_add("optical_drive_vpp_v", "EML / laser direct", "electrical-to-optical transfer",
     "escursione elettrica picco-picco che porta la transfer normalizzata "
     "di EML, DML o VCSEL da minimo a massimo: e la sensibilita FISSA del "
     "modulatore, non una normalizzazione ricavata dal record. Ridurla a "
     "swing driver costante aumenta OMA fino alla saturazione; aumentarla "
     "riduce la profondita di modulazione. Sul banco: dimezzala con EML "
     "attivo e osserva drive, OMA, PD e BER cambiare lungo tutta la catena.",
     "the peak-to-peak electrical excursion that moves the normalized EML, "
     "DML, or VCSEL transfer from minimum to maximum: it is the modulator's "
     "FIXED sensitivity, not a normalization inferred from each record. "
     "Reducing it at constant driver swing increases OMA up to saturation; "
     "increasing it reduces modulation depth. On the bench: halve it with "
     "EML active and watch drive, OMA, PD, and BER change down the chain.",
     "u=clip(1/2+Vdrive/Vpp, 0, 1)",
     "optical_modulator=eml/dml/vcsel")
_add("vpi_v", "MZM", "modulator transfer",
     "tensione di mezz'onda del Mach-Zehnder: quanta tensione serve per "
     "spostare la trasmissione di π. Fissa la profondità di modulazione "
     "raggiunta dallo swing del driver: swing/Vπ piccolo = modulazione "
     "lineare ma poco contrasto (ER e OMA bassi); grande = più OMA ma "
     "compressione cos² sui livelli esterni (RLM giù). I Vπ reali: 2-4 V "
     "(LiNbO₃/TFLN più bassi, silicio più alti). Sul banco: dimezza Vπ "
     "a driver fisso e guarda OMA salire e RLM peggiorare insieme.",
     "the Mach-Zehnder's half-wave voltage: how much drive moves "
     "transmission by π. It sets the modulation depth reached by the "
     "driver swing: small swing/Vπ = linear modulation but little "
     "contrast (low ER and OMA); large = more OMA but cos² compression "
     "of the outer levels (RLM down). Real Vπ: 2-4 V (LiNbO₃/TFLN lower, "
     "silicon higher). On the bench: halve Vπ at fixed driver and watch "
     "OMA rise and RLM worsen together.",
     "Pout∝cos²[(bias+πV/Vπ)/2]", "optical_modulator=mzm")
_add("mzm_bias_rad", "MZM", "modulator transfer",
     "punto di lavoro sull'interferogramma cos²: la QUADRATURA (π/2) è "
     "il punto di massima pendenza — massima linearità small-signal, "
     "potenza media a metà. Spostarsi verso il picco dà PIÙ potenza "
     "media ma MENO pendenza e più distorsione: il cascade audit "
     "verifica proprio che fuori quadratura il PD riceva più dBm mentre "
     "il Q scende. Il bias drift termico è il motivo per cui gli MZM "
     "reali hanno un controllo di bias attivo. Sul banco: muovilo e "
     "guarda P_PD e Q andare in direzioni opposte.",
     "operating point on the cos² interferogram: QUADRATURE (π/2) is "
     "the maximum-slope point — best small-signal linearity, half "
     "average power. Moving toward the peak gives MORE average power "
     "but LESS slope and more distortion: the cascade audit verifies "
     "exactly that off-quadrature the PD receives more dBm while Q "
     "drops. Thermal bias drift is why real MZMs ship an active bias "
     "controller. On the bench: move it and watch P_PD and Q go in "
     "opposite directions.",
     "quadratura: bias=π/2", "optical_modulator=mzm")
_add("mzm_bw_hz", "MZM", "MZM output field",
     "banda elettro-ottica del modulatore (elettrodi + velocità di "
     "gruppo): è un polo in cascata a DAC e driver, ma sul dominio "
     "OTTICO. I MZM DR/FR reali stanno a ~0.7-1×f_baud. Sotto, gli edge "
     "ottici si allungano e il TDECQ paga. Sul banco: stringila e "
     "confronta la WAVE del nodo P ottico prima e dopo: la banda manca "
     "proprio dove il PAM4 ha i suoi fronti.",
     "the modulator's electro-optic bandwidth (electrodes + group-"
     "velocity matching): a pole cascaded after DAC and driver, but in "
     "the OPTICAL domain. Real DR/FR MZMs sit at ~0.7-1×f_baud. Below "
     "that, optical edges stretch and TDECQ pays. On the bench: narrow "
     "it and compare the optical-P node WAVE before/after: the missing "
     "bandwidth is exactly where PAM4 keeps its edges.",
     active="optical_modulator=mzm")
_add("mzm_il_db", "MZM", "MZM output field",
     "perdita di inserzione del modulatore: primo gradino del budget "
     "ottico dopo il laser (i MZM reali costano 4-7 dB, il TFLN meno). "
     "Pura sottrazione di dBm: non tocca la forma, solo il livello — "
     "guarda il budget del pannello Ottica scalare di pari passo.",
     "the modulator's insertion loss: the optical budget's first step "
     "after the laser (real MZMs cost 4-7 dB, TFLN less). Pure dBm "
     "subtraction: it does not touch the shape, only the level — watch "
     "the Optics panel budget step down in lockstep.",
     active="optical_modulator=mzm")
_add("chirp_alpha", "MZM", "MZM output field",
     "parametro di Henry α del modulatore: lega la modulazione di "
     "intensità a una modulazione di FASE parassita. Da solo è "
     "invisibile al PD; CON la dispersione diventa il fattore che "
     "decide se le frequenze 'anticipate' si comprimono (α·D<0, "
     "l'occhio può perfino migliorare a corta distanza) o si allargano "
     "(α·D>0, penalità che esplode coi km). Un MZM push-pull vero sta "
     "vicino a 0. Sul banco: ±α a pari fibra — il segno cambia il "
     "verso della penalità: è la firma della fisica del chirp.",
     "the modulator's Henry α parameter: it ties intensity modulation "
     "to a parasitic PHASE modulation. Alone it is invisible to the "
     "PD; WITH dispersion it decides whether the 'advanced' "
     "frequencies compress (α·D<0, the eye can even improve at short "
     "reach) or spread (α·D>0, a penalty exploding with km). A true "
     "push-pull MZM sits near 0. On the bench: ±α at equal fiber — the "
     "sign flips the penalty direction: the signature of chirp "
     "physics.",
     "penalità ∝ segno(α·D·L)", "optical_modulator=mzm")
_add("eml_bw_hz", "EML", "EML output field",
     "banda dell'elettroassorbitore: il vantaggio storico dell'EML è "
     "proprio una banda alta in un package piccolo (35-50+ GHz reali). "
     "Stesso ruolo del polo MZM ma sulla transfer EA. Sul banco: come "
     "per l'MZM, la WAVE ottica mostra subito gli edge rallentare.",
     "the electro-absorption bandwidth: the EML's historical advantage "
     "is precisely high bandwidth in a small package (35-50+ GHz real). "
     "Same role as the MZM pole but on the EA transfer. On the bench: "
     "as with the MZM, the optical WAVE immediately shows edges slowing "
     "down.",
     active="optical_modulator=eml")
_add("eml_er_db", "EML", "EML output field",
     "extinction ratio dell'EML: il rapporto fra il livello ottico alto "
     "e il basso. ER finito = il livello 'zero' trasporta ancora "
     "potenza → i quattro livelli PAM4 si comprimono verso l'alto e "
     "l'OMA cala a parità di potenza media (il TDECQ contiene proprio "
     "questo trade). EML tipici: 4-8 dB dinamici. Sul banco: abbassa "
     "l'ER e guarda P0..P3 avvicinarsi nel pannello Scope ottico.",
     "the EML's extinction ratio: the high-to-low optical level ratio. "
     "Finite ER = the 'zero' level still carries power → the four PAM4 "
     "levels compress upward and OMA drops at equal average power "
     "(TDECQ embeds exactly this trade). Typical EML: 4-8 dB dynamic. "
     "On the bench: lower ER and watch P0..P3 huddle together in the "
     "optical Scope panel.",
     "OMA=P3−P0; ER=P3/P0", "optical_modulator=eml")
_add("eml_il_db", "EML", "EML output field",
     "perdita di inserzione dell'EML (assorbimento residuo nello stato "
     "trasparente): gradino del budget ottico, come l'IL del MZM.",
     "the EML's insertion loss (residual absorption in the transparent "
     "state): an optical-budget step, like the MZM's IL.",
     active="optical_modulator=eml")
_add("eml_chirp_alpha", "EML", "EML output field",
     "chirp di Henry dell'elettroassorbitore: tipicamente 0.5-1.5 e "
     "dipendente dal bias — peggiore del push-pull MZM, meglio del DML. "
     "Stessa fisica di chirp_alpha: serve la dispersione per vederlo. "
     "Sul banco: EML vs MZM a α diversi sulla stessa fibra è il "
     "confronto classico di penalità di dispersione.",
     "the electro-absorber's Henry chirp: typically 0.5-1.5 and "
     "bias-dependent — worse than a push-pull MZM, better than a DML. "
     "Same physics as chirp_alpha: dispersion is needed to see it. On "
     "the bench: EML vs MZM at different α on the same fiber is the "
     "classic dispersion-penalty comparison.",
     "penalità ∝ segno(α·D·L)", "optical_modulator=eml")
_add("direct_laser_bw_hz", "DML / VCSEL", "direct laser output",
     "banda di modulazione del laser diretto: fisicamente è la "
     "frequenza di rilassamento della cavità (fotoni↔portatori), che "
     "cresce con la corrente di bias. DML/VCSEL reali: 15-30 GHz — è "
     "il motivo per cui la modulazione diretta fatica oltre 50G/lane "
     "PAM4. Sul banco: portala sotto 0.4·f_baud e guarda l'occhio "
     "ottico impastarsi.",
     "the direct laser's modulation bandwidth: physically the cavity's "
     "relaxation-oscillation frequency (photons↔carriers), rising with "
     "bias current. Real DML/VCSEL: 15-30 GHz — the reason direct "
     "modulation struggles past 50G/lane PAM4. On the bench: push it "
     "below 0.4·f_baud and watch the optical eye smear.",
     active="optical_modulator=dml|vcsel")
_add("direct_laser_er_db", "DML / VCSEL", "direct laser output",
     "extinction ratio del laser diretto: modulare la corrente attorno "
     "alla soglia dà ER modesti (3-6 dB tipici) perché spegnere davvero "
     "il laser costerebbe il tempo di riaccensione. Stessa aritmetica "
     "OMA/livelli dell'EML.",
     "the direct laser's extinction ratio: modulating current around "
     "threshold yields modest ER (3-6 dB typical) because truly turning "
     "the laser off would cost the turn-on delay. Same OMA/level "
     "arithmetic as the EML.",
     active="optical_modulator=dml|vcsel")
_add("direct_laser_chirp_alpha", "DML / VCSEL", "direct laser output",
     "chirp del laser diretto: modulando la corrente moduli anche la "
     "densità di portatori, quindi l'indice → α tipici 3-6, i più alti "
     "della famiglia. È il motivo per cui il DML vive a 1310 nm (D≈0) o "
     "su tratte cortissime. Sul banco: DML con α=5 su 2 km a 1550-style "
     "D=17: la penalità è già feroce.",
     "the direct laser's chirp: modulating current also modulates "
     "carrier density, hence index → typical α of 3-6, the family's "
     "highest. The reason DML lives at 1310 nm (D≈0) or on very short "
     "reaches. On the bench: a DML with α=5 over 2 km at 1550-style "
     "D=17: the penalty is already savage.",
     "penalità ∝ segno(α·D·L)", "optical_modulator=dml|vcsel")

# ================================================================ FIBRA
_add("coupling_il_db", "Optical path", "fiber launch → PD",
     "perdite concentrate di accoppiamento (lenti, connettori, splice): "
     "puro gradino del budget in dBm, tipicamente 1-3 dB per interfaccia "
     "nei moduli reali. Nella procedura DR4 è la manopola usata per "
     "portare la loss totale di canale ESATTAMENTE al massimo di tabella. "
     "Sul banco: il budget del pannello Ottica la mostra come voce "
     "separata dalla fibra distribuita.",
     "lumped coupling losses (lenses, connectors, splices): a pure dBm "
     "budget step, typically 1-3 dB per interface in real modules. In the "
     "DR4 procedure it is the knob used to bring total channel loss "
     "EXACTLY to the table maximum. On the bench: the Optics panel budget "
     "lists it separately from the distributed fiber loss.",
     "P_pd = P_launch − IL_coup − α·L")
_add("fiber_loss_db_km", "Optical path", "fiber launch → PD",
     "attenuazione distribuita della fibra: ~0.32-0.35 dB/km a 1310 nm, "
     "~0.18-0.20 a 1550 nm (il minimo assoluto del quarzo). Sui 500 m di "
     "un DR è quasi irrilevante (~0.2 dB); su 10 km di FR/LR è la voce "
     "che decide il budget. Sul banco: moltiplicata per fiber_km scala il "
     "'PD input' dB per dB — verificato dal cascade audit.",
     "the fiber's distributed attenuation: ~0.32-0.35 dB/km at 1310 nm, "
     "~0.18-0.20 at 1550 nm (silica's absolute minimum). Over a DR's "
     "500 m it is nearly irrelevant (~0.2 dB); over an FR/LR's 10 km it "
     "decides the budget. On the bench: multiplied by fiber_km it scales "
     "'PD input' dB per dB — pinned by the cascade audit.",
     "loss = α·L [dB]")
_add("fiber_km", "Optical path", "fiber propagation",
     "lunghezza della tratta: scala INSIEME attenuazione (α·L), "
     "dispersione cromatica accumulata (D·L, che chiude l'occhio col "
     "quadrato del baud), DGD della PMD (∝√L), nonlinearità Kerr e — su "
     "MMF — la banda modale. È la manopola 'reach' delle classi DR "
     "(500 m), FR (2 km), LR (10 km). Sul banco: con D=15 l'audit di "
     "cascata mostra q monotono in discesa già fra 0.5 e 3.5 km; a "
     "grandi D·L compare il fading IM/DD non equalizzabile.",
     "span length: it scales TOGETHER attenuation (α·L), accumulated "
     "chromatic dispersion (D·L, closing the eye with the square of the "
     "baud), PMD's DGD (∝√L), Kerr nonlinearity and — on MMF — modal "
     "bandwidth. It is the 'reach' knob of the DR (500 m), FR (2 km), LR "
     "(10 km) classes. On the bench: with D=15 the cascade audit shows q "
     "falling monotonically between 0.5 and 3.5 km; at large D·L the "
     "non-equalizable IM/DD fading appears.",
     "CD: β2·L; PMD: DGD∝√L; loss: α·L")
_add("optical_return_loss_db", "Optical link", "fiber launch (MPI)",
     "return loss di CIASCUNA delle due discontinuità che formano una coppia "
     "di riflessioni (multipath interference): l'eco che rientra nel verso "
     "di propagazione è riflessa due volte, quindi sta 2·RL sotto il segnale "
     "(campo 10^(−RL/10)), ritardata di optical_reflection_delay_ns e con "
     "fase casuale per record. 0 = spenta. Nella procedura DR4 è lo stress "
     "'reflection' alla tolleranza ORL del TX (21.4 dB per discontinuità → "
     "eco a −42.8 dB, penalità di frazioni di dB come le allocazioni MPI di "
     "clausola); con 10-15 dB l'eco batte contro il segnale e chiude "
     "l'occhio in modo pattern-dipendente. DICHIARATO: eco singola coerente, "
     "non cavità né feedback nel laser (quello è RIN_21.4OMA → rin_at_source). "
     "Sul banco: Optical → P al PD e TDECQ; DR4 → caso 'reflection'.",
     "return loss of EACH of the two discontinuities forming a reflection "
     "pair (multipath interference): the echo re-entering the propagation "
     "direction is reflected twice, so it sits 2·RL below the signal (field "
     "10^(−RL/10)), delayed by optical_reflection_delay_ns and with a random "
     "phase per record. 0 = off. In the DR4 procedure it is the 'reflection' "
     "stress at the TX ORL tolerance (21.4 dB per discontinuity → echo at "
     "−42.8 dB, fractions of a dB of penalty like the clause MPI allocations); "
     "at 10-15 dB the echo beats against the signal and closes the eye "
     "pattern-dependently. DECLARED: single coherent echo, no cavity or laser "
     "feedback (that is RIN_21.4OMA → rin_at_source). On the bench: Optical → "
     "PD power and TDECQ; DR4 → 'reflection' case.",
     "E' = E + 10^(−2·RL/20)·E(t−τ)·e^{jφ}", "valore > 0 dB")
_add("optical_reflection_delay_ns", "Optical link", "fiber launch (MPI)",
     "ritardo dell'eco riflessa: pochi ns = riflessione su un connettore "
     "vicino (eco entro la coerenza del laser → interferenza coerente). "
     "Con delay lungo rispetto al record l'eco esce dalla finestra.",
     "delay of the reflected echo: a few ns = reflection at a nearby "
     "connector (echo within the laser coherence → coherent interference). "
     "With a delay long compared with the record the echo leaves the "
     "window.",
     "τ [ns]", "optical_return_loss_db > 0")
_add("rin_at_source", "Optical link", "laser intensity",
     "dove vive il RIN del laser: OFF = modello storico della baseline, "
     "corrente di rumore bianca al fotodiodo con PSD I_media²·10^(RIN/10) "
     "(non tocca la forma d'onda ottica, quindi TDECQ/SECQ non lo vedono); "
     "ON = rumore d'intensità moltiplicativo all'uscita del modulatore, "
     "bianco sulla banda analogica, con la definizione di clausola RIN_xOMA: "
     "al livello alto σ² = 10^(RIN/10)·OMA²·BW, agli altri livelli scala con "
     "la potenza istantanea; entra nel campo ottico e arriva al PD via "
     "square-law (il termine al ricevitore viene azzerato: mai contato due "
     "volte). Serve alla calibrazione stressed-RX sul SECQ e al caso 'rin' "
     "della DR4 (RIN_21.4OMA, misurato dallo standard con 21.4 dB di return "
     "loss verso il laser). Sul banco: ON + RIN −128 dB/Hz → Optical/TDECQ "
     "peggiora, Noise budget mostra RIN 0 al PD.",
     "where the laser RIN lives: OFF = the baseline's historical model, a "
     "white noise current at the photodiode with PSD I_mean²·10^(RIN/10) (it "
     "does not touch the optical waveform, so TDECQ/SECQ cannot see it); ON = "
     "multiplicative intensity noise at the modulator output, white over the "
     "analog band, with the clause RIN_xOMA definition: at the high level "
     "σ² = 10^(RIN/10)·OMA²·BW, at the other levels it scales with the "
     "instantaneous power; it enters the optical field and reaches the PD via "
     "the square law (the receiver term is zeroed: never counted twice). Needed "
     "by the SECQ stressed-RX calibration and by the DR4 'rin' case "
     "(RIN_21.4OMA, which the standard measures with 21.4 dB return loss "
     "toward the laser). On the bench: ON + RIN −128 dB/Hz → Optical/TDECQ "
     "degrades, Noise budget shows RIN 0 at the PD.",
     "P(t)·(1 + n(t)·OMA/P_high), S_n = 10^(RIN/10) 1/Hz", "link ottico / optical link")
_add("wavelength_nm", "SMF dispersion", "optical field in fiber",
     "lunghezza d'onda operativa: fissa D(λ) tramite pendenza e zero di "
     "dispersione della G.652 (zero a ~1310 nm — la banda O di DR/FR/LR "
     "esiste per questo; a 1550 nm D≈+17 ps/nm/km ma perdita minima). "
     "Cambiarla sposta l'intero compromesso CD-vs-loss. Sul banco: "
     "1310 → 1550 a pari fibra e guarda la penalità di dispersione "
     "comparire mentre il budget in dB migliora.",
     "operating wavelength: it sets D(λ) through G.652's dispersion "
     "slope and zero (zero near 1310 nm — the O-band of DR/FR/LR exists "
     "for this; at 1550 nm D≈+17 ps/nm/km but minimum loss). Changing it "
     "moves the whole CD-vs-loss trade. On the bench: 1310 → 1550 at "
     "equal fiber and watch the dispersion penalty appear while the dB "
     "budget improves.",
     "D(λ)≈S0/4·(λ−λ0⁴/λ³)", "fiber_type=smf")
_add("dispersion_ps_nm_km", "SMF dispersion", "optical field in fiber",
     "dispersione cromatica per km: frequenze diverse viaggiano a "
     "velocità diverse (β2), gli impulsi si allargano e sull'IM/DD "
     "compare anche il FADING — un nullo di risposta a "
     "f≈√(c/(2λ²|D|L)) che NESSUN equalizzatore lineare può invertire "
     "(è uno zero vero del canale). Il segno conta solo col chirp "
     "(α·D·L). Sul banco: alza |D| coi km e osserva prima l'occhio "
     "ottico allargarsi, poi il nullo entrare in banda nello Spectrum.",
     "chromatic dispersion per km: different frequencies travel at "
     "different speeds (β2), pulses spread, and on IM/DD links FADING "
     "also appears — a response null at f≈√(c/(2λ²|D|L)) that NO linear "
     "equalizer can invert (a true channel zero). Sign matters only "
     "with chirp (α·D·L). On the bench: raise |D| with km and watch "
     "first the optical eye spread, then the null walk into band in the "
     "Spectrum panel.",
     "f_null≈√[c/(2λ²|D|L)]", "fiber_type=smf")
_add("dispersion_slope_ps_nm2_km", "SMF dispersion", "optical field in fiber",
     "pendenza S0 della dispersione (β3): curva D(λ) attorno allo zero — "
     "conta per capire quanto D cambia spostando λ di pochi nm (i "
     "quattro laser di un FR4 CWDM vedono D diverse proprio per questo) "
     "e ai bordi banda dei segnali larghissimi. Effetto secondario "
     "rispetto a D, ma è fisica di targa della G.652 (S0≈0.09).",
     "the dispersion slope S0 (β3): it curves D(λ) around the zero — it "
     "matters to know how much D shifts when λ moves by a few nm (the "
     "four lasers of a CWDM FR4 see different D exactly for this) and "
     "at the band edges of very wide signals. Second-order versus D, "
     "but genuine G.652 nameplate physics (S0≈0.09).",
     "β3 → D(λ) curvatura", "fiber_type=smf")
_add("pmd_ps_sqrt_km", "SMF PMD", "two polarization powers",
     "coefficiente PMD: le due polarizzazioni principali viaggiano con "
     "un ritardo differenziale DGD=D_PMD·√L (√ perché il mode coupling "
     "è casuale lungo la tratta). Nel proxy di 1° ordine il segnale si "
     "sdoppia in due repliche ritardate pesate dallo split. Fibra "
     "moderna: ≤0.1 ps/√km (irrilevante a 500 m); il DR4 della "
     "procedura usa deliberatamente un DGD vicino al massimo pubblico. "
     "Sul banco: DGD≈0.3-0.5 UI con split 50/50 è un ISI bimodale che "
     "il DFE fatica a pulire.",
     "the PMD coefficient: the two principal polarization states travel "
     "with a differential delay DGD=D_PMD·√L (√ because mode coupling "
     "is random along the span). In the 1st-order proxy the signal "
     "splits into two delayed replicas weighted by the power split. "
     "Modern fiber: ≤0.1 ps/√km (irrelevant at 500 m); the DR4 "
     "procedure deliberately uses a DGD near the public maximum. On "
     "the bench: DGD≈0.3-0.5 UI at 50/50 split is a bimodal ISI the "
     "DFE struggles to clean.",
     "DGD=D_PMD·√L", "fiber_type=smf")
_add("pmd_power_split", "SMF PMD", "two polarization powers",
     "ripartizione di potenza fra i due PSP: 0 o 1 = tutta la luce su "
     "uno stato, DGD invisibile; 0.5 = worst case, le due repliche "
     "pesano uguale e l'ISI bimodale è massimo. Nella realtà lo split "
     "vaga lentamente col tempo/temperatura — è il motivo per cui la "
     "PMD si tratta statisticamente. Sul banco: a DGD fisso, spazzala "
     "0→0.5 e guarda il q_min scendere fino al minimo a metà.",
     "power split between the two PSPs: 0 or 1 = all light on one "
     "state, DGD invisible; 0.5 = worst case, equal-weight replicas "
     "and maximum bimodal ISI. In reality the split wanders slowly "
     "with time/temperature — the reason PMD is treated statistically. "
     "On the bench: at fixed DGD, sweep it 0→0.5 and watch q_min fall "
     "to its midpoint minimum.",
     "worst case: split=0.5", "pmd_ps_sqrt_km > 0")
_add("fiber_gamma_w_inv_km", "SMF Kerr", "optical field phase",
     "coefficiente nonlineare γ (effetto Kerr): l'indice dipende "
     "dall'intensità → automodulazione di fase φ_NL=γ·L_eff·P, con "
     "L_eff limitata dall'attenuazione. Ai livelli interconnect "
     "(≤10 dBm, km) φ_NL è piccolissima — il campo è lì per mostrare "
     "QUANDO inizia a contare (potenze alte + dispersione che converte "
     "PM in AM). Sul banco: serve forzare potenza e γ ben oltre il "
     "realistico per vedere l'effetto: fallo, e dichiara il perché.",
     "the nonlinear coefficient γ (Kerr effect): index depends on "
     "intensity → self-phase modulation φ_NL=γ·L_eff·P, with L_eff "
     "capped by attenuation. At interconnect levels (≤10 dBm, km) φ_NL "
     "is tiny — the field exists to show WHEN it starts to matter "
     "(high power + dispersion converting PM to AM). On the bench: you "
     "must push power and γ well beyond realistic to see it: do it, "
     "and declare why.",
     "φ_NL=γ·L_eff·P; L_eff=(1−e^{−αL})/α", "fiber_type=smf")
_add("fiber_type", "Fiber", "fiber propagation",
     "SMF (monomodale: dispersione cromatica, PMD, Kerr — il mondo "
     "DR/FR/LR) o MMF (multimodale: la banda è limitata dal prodotto "
     "banda·distanza modale — il mondo SR/VCSEL a 850 nm). Il proxy "
     "MMF è dichiarato: un filtro equivalente dalla banda modale, non "
     "un modello DMD/launch completo. Sul banco: passa a MMF e guarda "
     "la penalità crescere linearmente con la lunghezza invece che col "
     "quadrato D·L.",
     "SMF (single-mode: chromatic dispersion, PMD, Kerr — the DR/FR/LR "
     "world) or MMF (multimode: bandwidth limited by the modal "
     "bandwidth·distance product — the SR/VCSEL 850 nm world). The MMF "
     "proxy is declared: an equivalent filter from modal bandwidth, "
     "not a full DMD/launch model. On the bench: switch to MMF and "
     "watch the penalty grow linearly with length instead of with the "
     "D·L square.")
_add("mmf_modal_bw_mhz_km", "Fiber", "fiber propagation",
     "prodotto banda·distanza della fibra multimodale: OM3=2000, "
     "OM4=4700, OM5≈OM4 a 850 nm (MHz·km). La banda effettiva della "
     "tratta è BW/L: 100 m di OM4 danno 47 GHz, 300 m solo 15.7 — ecco "
     "perché l'SR moderno muore oltre i 100 m. Sul banco: allunga la "
     "tratta MMF e guarda la banda equivalente strozzare gli edge come "
     "un TIA lento.",
     "the multimode fiber's bandwidth·distance product: OM3=2000, "
     "OM4=4700, OM5≈OM4 at 850 nm (MHz·km). The span's effective "
     "bandwidth is BW/L: 100 m of OM4 gives 47 GHz, 300 m only 15.7 — "
     "why modern SR dies past 100 m. On the bench: stretch the MMF "
     "span and watch the equivalent bandwidth choke the edges like a "
     "slow TIA.",
     "BW_eff=BW·km/L", "fiber_type=mmf")

# ================================================================== RX
_add("pd_responsivity_a_w", "Photodiode", "PD current",
     "responsivity del fotodiodo: ampere di fotocorrente per watt "
     "ottico. Il limite quantico a 1310 nm è ~1.06 A/W (η=1); i PIN "
     "reali stanno a 0.8-1.0. È IL fattore di conversione del link "
     "budget ottico→elettrico: a parità di rumore TIA, meno "
     "responsivity = meno segnale = SNR giù (cascade audit: q monotono "
     "1.0→0.4 A/W). Sul banco: è equivalente a perdere dB ottici, ma "
     "SENZA cambiare lo shot noise per watt ricevuto.",
     "the photodiode's responsivity: amperes of photocurrent per "
     "optical watt. The quantum limit at 1310 nm is ~1.06 A/W (η=1); "
     "real PINs sit at 0.8-1.0. THE optical→electrical conversion "
     "factor of the link budget: at equal TIA noise, less responsivity "
     "= less signal = lower SNR (cascade audit: q monotone from 1.0 to "
     "0.4 A/W). On the bench: it is equivalent to losing optical dB, "
     "but WITHOUT changing the shot noise per received watt.",
     "I=R·P; R_max=ηqλ/hc")
_add("pd_dark_current_a", "Photodiode", "PD current",
     "corrente di buio del PD: scorre anche senza luce, porta il suo "
     "shot noise (2qI_d per Hz) e cresce ESPONENZIALMENTE con la "
     "temperatura (Arrhenius, ~raddoppia ogni 8-10 °C — è collegata "
     "alla camera climatica del banco). A temperatura ambiente è "
     "trascurabile (nA); a 85-105 °C su un ricevitore sensibile "
     "comincia a pesare. Sul banco: camera a 100 °C e guarda il floor "
     "del rumore salire nel pannello PD.",
     "the PD's dark current: it flows without light, carries its own "
     "shot noise (2qI_d per Hz) and grows EXPONENTIALLY with "
     "temperature (Arrhenius, ~doubling every 8-10 °C — tied to the "
     "bench's climate chamber). At room temperature it is negligible "
     "(nA); at 85-105 °C on a sensitive receiver it starts to matter. "
     "On the bench: chamber at 100 °C and watch the noise floor rise "
     "in the PD panel.",
     "S_shot=2q(I_ph+I_d); I_d(T)~Arrhenius")
_add("pd_bw_hz", "Photodiode", "PD current",
     "banda del fotodiodo (transito dei portatori + RC della "
     "giunzione): il PRIMO polo della catena di ricezione. I PIN "
     "50G-class stanno a 35-45 GHz. Da qui in poi banda e rumore si "
     "intrecciano: ogni polo taglia segnale E limita la ENBW del "
     "rumore che integra. Sul banco: stringila e guarda gli edge nel "
     "nodo pfiber→vtia della WAVE.",
     "the photodiode bandwidth (carrier transit + junction RC): the "
     "receive chain's FIRST pole. 50G-class PINs sit at 35-45 GHz. "
     "From here on, bandwidth and noise intertwine: every pole cuts "
     "signal AND bounds the noise ENBW it integrates. On the bench: "
     "narrow it and watch the edges at the pfiber→vtia node in WAVE.",
     "polo RC+transito")
_add("pd_saturation_a", "Photodiode", "PD current",
     "corrente di saturazione del PD: oltre, lo space-charge screening "
     "comprime la risposta — i livelli ALTI del PAM4 si schiacciano "
     "prima degli altri (compressione asimmetrica, RLM giù), classico "
     "dei ricevitori sovrailluminati. Sul banco: alza la potenza fino "
     "a superarla e guarda P2/P3 avvicinarsi negli istogrammi mentre "
     "P0/P1 restano al loro posto.",
     "the PD's saturation current: beyond it, space-charge screening "
     "compresses the response — PAM4's HIGH levels squash before the "
     "others (asymmetric compression, RLM down), classic of "
     "over-illuminated receivers. On the bench: raise power past it "
     "and watch P2/P3 close in on the histograms while P0/P1 stay "
     "put.",
     "compressione soft oltre I_sat")
_add("rin_db_hz", "RX noise", "TIA input-referred current",
     "relative intensity noise del laser: fluttuazione di potenza "
     "PROPORZIONALE alla potenza — per questo, a differenza del "
     "termico, alzare la potenza NON lo migliora (l'SNR da RIN è un "
     "tetto). RIN=−140 dB/Hz su ~40 GHz di banda dà già σ≈1% della "
     "potenza. DFB buoni: −150/−155. Sul banco: il cascade audit lo "
     "verifica monotono; portalo a −135 e guarda l'occhio riempirsi "
     "in verticale proporzionalmente ai livelli.",
     "the laser's relative intensity noise: power fluctuation "
     "PROPORTIONAL to power — hence, unlike thermal noise, raising "
     "power does NOT help (RIN-limited SNR is a ceiling). RIN=−140 "
     "dB/Hz over ~40 GHz of bandwidth already gives σ≈1% of power. "
     "Good DFBs: −150/−155. On the bench: the cascade audit pins it "
     "monotone; set −135 and watch the eye fill vertically in "
     "proportion to the levels.",
     "σ²_RIN=P²·10^(RIN/10)·ENBW")
_add("tia_noise_a_rt_hz", "RX noise", "TIA input-referred current",
     "densità di rumore di corrente input-referred del TIA: il numero "
     "di targa che decide la sensitivity di un ricevitore (i TIA "
     "50G-class dichiarano 15-25 pA/√Hz medi). Integrata sulla ENBW "
     "reale della catena diventa il floor contro cui il segnale "
     "combatte: è il rumore DOMINANTE dei ricevitori PIN (senza APD). "
     "Sul banco: il cascade audit mostra 10→80 pA/√Hz spazzare il "
     "link da BER 0 a 0.19 — la manopola di rumore più potente del "
     "banco.",
     "the TIA's input-referred current-noise density: the nameplate "
     "number deciding a receiver's sensitivity (50G-class TIAs quote "
     "15-25 pA/√Hz average). Integrated over the chain's real ENBW it "
     "becomes the floor the signal fights: the DOMINANT noise of PIN "
     "receivers (no APD). On the bench: the cascade audit shows "
     "10→80 pA/√Hz sweeping the link from BER 0 to 0.19 — the most "
     "powerful noise knob on the bench.",
     "σ²=∫S_i|Z_T·H(f)|²df")
_add("tia_transimpedance_ohm", "TIA VGA", "TIA output",
     "transimpedenza MASSIMA del TIA (V d'uscita per A di "
     "fotocorrente): insieme al VGA definisce quanto guadagno è "
     "disponibile. Z_T alta = più segnale ma, nei TIA reali, meno "
     "banda (il prodotto guadagno-banda si paga): qui i due sono "
     "manopole separate PER SCELTA didattica — dichiarato. Sul banco: "
     "con poca luce, alzala e guarda l'AGC rilassarsi; oltre il range "
     "VGA scatta l'overload reale.",
     "the TIA's MAXIMUM transimpedance (output V per photocurrent A): "
     "with the VGA it defines the available gain. High Z_T = more "
     "signal but, in real TIAs, less bandwidth (the gain-bandwidth "
     "product must be paid): here the two are separate knobs BY "
     "didactic choice — declared. On the bench: at low light, raise "
     "it and watch the AGC relax; past the VGA range the real "
     "overload kicks in.",
     "V=Z_T·I (fino a headroom/rail)")
_add("tia_vga_range_db", "TIA VGA", "TIA output",
     "escursione del VGA interno al TIA: quanti dB di attenuazione "
     "servono fra 'poca luce' (tutta la Z_T) e 'troppa luce' "
     "(attenua per non saturare). Fuori range il TIA satura DAVVERO: "
     "è il guasto classico del ricevitore sovraccarico, che nessun "
     "AGC a valle ripara. Sul banco: potenza alta + range VGA basso → "
     "overload con compressione dei livelli; il pannello TIA lo "
     "dichiara.",
     "the TIA's internal VGA range: how many dB of attenuation exist "
     "between 'low light' (full Z_T) and 'too much light' (attenuate "
     "to avoid saturation). Out of range the TIA truly saturates: the "
     "classic overloaded-receiver failure no downstream AGC can fix. "
     "On the bench: high power + small VGA range → overload with "
     "level compression; the TIA panel declares it.",
     active="alta potenza o Z_T alta")
_add("tia_headroom_ratio", "TIA VGA", "TIA output",
     "frazione delle rail a cui il VGA cerca di tenere il picco del "
     "segnale: il target di lavoro del primo stadio. Alto = sfrutta "
     "la dinamica ma rischia clip sui picchi; basso = margine ma "
     "butta SNR (il rumore del TIA non scala col target). Sul banco: "
     "osserva sul nodo vtia la WAVE cambiare ampiezza e la clip "
     "fraction reagire agli estremi.",
     "the rail fraction at which the VGA tries to keep the signal "
     "peak: the first stage's operating target. High = uses the "
     "dynamic range but risks clipping peaks; low = margin but wastes "
     "SNR (TIA noise does not scale with the target). On the bench: "
     "watch the vtia node's WAVE change amplitude and the clip "
     "fraction react at the extremes.")
_add("tia_bw_hz", "TIA / AFE", "TIA/AFE output",
     "banda −3 dB del TIA/AFE: il polo di ricezione più importante — "
     "segnale e RUMORE passano dallo stesso filtro, quindi c'è una "
     "banda OTTIMA: troppo stretta = ISI, troppo larga = integri "
     "rumore inutile oltre Nyquist. La regola dei ricevitori: "
     "~0.6-0.75·f_baud. Sul banco: spazzala nei due sensi e trova il "
     "minimo di BER — è uno dei sweep più istruttivi del banco.",
     "the TIA/AFE −3 dB bandwidth: the most important receive pole — "
     "signal and NOISE share the same filter, so an OPTIMUM bandwidth "
     "exists: too narrow = ISI, too wide = useless noise integrated "
     "past Nyquist. The receiver rule: ~0.6-0.75·f_baud. On the "
     "bench: sweep it both ways and find the BER minimum — one of the "
     "bench's most instructive sweeps.",
     "ottimo ≈ 0.6-0.75·f_baud")
_add("tia_clip_v", "TIA / AFE", "TIA/AFE output",
     "rail d'uscita del TIA: il clipping qui è il famigerato overload "
     "del ricevitore — nonlineare, asimmetrico sui livelli alti, e "
     "IRREVERSIBILE per il DSP a valle (che è lineare). Sul banco: "
     "abbassale con potenza alta e guarda i livelli esterni sparire "
     "negli istogrammi mentre il pannello TIA marca l'overload.",
     "the TIA's output rails: clipping here is the notorious receiver "
     "overload — nonlinear, asymmetric on the upper levels, and "
     "IRREVERSIBLE for the (linear) downstream DSP. On the bench: "
     "lower them at high power and watch the outer levels vanish from "
     "the histograms while the TIA panel flags the overload.",
     "hard clip alle rail")
_add("agc_target_rms_v", "AGC", "AGC output",
     "RMS d'uscita richiesto all'AGC: il suo compito è consegnare "
     "all'ADC un segnale che riempia il full-scale SENZA clipparlo, "
     "qualunque cosa succeda a monte. Il target ottimo dipende dal "
     "full-scale ADC (~FS/4-FS/3 di RMS per un PAM4). L'AGC ideale "
     "del banco applica G=V_target/V_rms entro limiti REALI di "
     "guadagno. Sul banco: muovilo e guarda l'istogramma dei codici "
     "ADC allargarsi fino a toccare le righe rosse di clip.",
     "the RMS requested at the AGC output: its job is delivering to "
     "the ADC a signal that fills the full scale WITHOUT clipping, "
     "whatever happens upstream. The optimum target depends on the "
     "ADC full scale (~FS/4-FS/3 RMS for PAM4). The bench's ideal AGC "
     "applies G=V_target/V_rms within REAL gain limits. On the bench: "
     "move it and watch the ADC code histogram widen until it touches "
     "the red clip lines.",
     "G=clip(V_t/V_rms, G_min, G_max)")
_add("agc_min_gain_db", "AGC", "AGC output",
     "guadagno minimo del VGA dell'AGC: con segnale FORTE l'AGC "
     "vorrebbe attenuare oltre il possibile — al limite inferiore il "
     "target diventa irraggiungibile e l'ADC riceve troppo (clip). La "
     "card AGC segnala LIMIT. Sul banco: potenza alta + G_min alto = "
     "clip fraction ADC su, un guasto realistico da ricevitore "
     "vicino.",
     "the AGC VGA's minimum gain: with a STRONG signal the AGC would "
     "attenuate beyond what it can — at the lower limit the target "
     "becomes unreachable and the ADC receives too much (clip). The "
     "AGC card flags LIMIT. On the bench: high power + high G_min = "
     "ADC clip fraction up, a realistic near-end receiver failure.",
     active="segnale forte (limite basso attivo)")
_add("agc_max_gain_db", "AGC", "AGC output",
     "guadagno massimo dell'AGC: con segnale DEBOLE il target diventa "
     "irraggiungibile verso l'alto — l'ADC lavora sotto-range, i "
     "codici si concentrano al centro e la quantizzazione pesa di "
     "più. È la faccia 'sensitivity' del limite. Sul banco: poca luce "
     "+ G_max basso → istogramma codici stretto e ENOB effettivo giù.",
     "the AGC's maximum gain: with a WEAK signal the target becomes "
     "unreachable upward — the ADC runs under-range, codes bunch at "
     "the center and quantization weighs more. The 'sensitivity' face "
     "of the limit. On the bench: low light + low G_max → narrow code "
     "histogram and lower effective ENOB.",
     active="segnale debole (limite alto attivo)")

# ============================================================ CTLE / ADC
_add("ctle_zero_hz", "CTLE", "CTLE output",
     "zero della CTLE legacy a sezione singola: da qui in su il "
     "guadagno SALE (+20 dB/dec) fino al polo — è il boost che "
     "ricompensa la perdita ~√f del canale. La posizione giusta "
     "dipende dal canale: zero basso = tanto boost già a metà banda "
     "(rischio: amplifichi rumore); zero alto = boost tardivo. Con la "
     "topologia multi-sezione attiva, questo campo muove il PRIMO "
     "zero della lista reale (dichiarato nello sweep come effective "
     "value). Sul banco: spazzalo e guarda il trade ISI-vs-rumore "
     "nel minimo della BER.",
     "the single-section legacy CTLE zero: from here up the gain "
     "RISES (+20 dB/dec) until the pole — the boost repaying the "
     "channel's ~√f loss. The right position depends on the channel: "
     "low zero = strong boost already at mid-band (risk: you amplify "
     "noise); high zero = late boost. With the multi-section topology "
     "active, this field moves the FIRST zero of the real list "
     "(declared in the sweep as effective value). On the bench: sweep "
     "it and watch the ISI-vs-noise trade in the BER minimum.",
     "H(s)=G_DC·(1+s/ωz)/[(1+s/ωp1)(1+s/ωp2)]")
_add("ctle_pole_hz", "CTLE", "CTLE output",
     "primo polo della CTLE: ferma il boost dello zero e definisce, "
     "col rapporto polo/zero, il PEAKING in dB (≈20·log10(fp/fz) per "
     "la sezione singola). Le CTLE reali dichiarano proprio 'peaking "
     "a Nyquist' su una manciata di step. Sul banco: avvicina il polo "
     "allo zero e guarda il peaking sparire dalla risposta nel "
     "pannello CTLE.",
     "the CTLE's first pole: it stops the zero's boost and, through "
     "the pole/zero ratio, defines the PEAKING in dB "
     "(≈20·log10(fp/fz) for the single section). Real CTLEs are "
     "specified exactly as 'peaking at Nyquist' over a handful of "
     "steps. On the bench: bring the pole toward the zero and watch "
     "the peaking vanish from the response in the CTLE panel.",
     "peaking≈20·log10(fp/fz) dB")
_add("ctle_hf_pole_hz", "CTLE", "CTLE output",
     "secondo polo ad alta frequenza: chiude la risposta oltre il "
     "boost (ogni stadio reale ha una banda finita) e protegge "
     "l'ADC dal rumore fuori banda. Se scende troppo diventa lui il "
     "collo di bottiglia della catena RX. Sul banco: portalo sotto "
     "Nyquist e guarda la CTLE trasformarsi da equalizzatore in "
     "filtro passa-basso.",
     "the second high-frequency pole: it closes the response past "
     "the boost (every real stage has finite bandwidth) and shields "
     "the ADC from out-of-band noise. Too low, and it becomes the RX "
     "chain's bottleneck itself. On the bench: push it below Nyquist "
     "and watch the CTLE morph from equalizer into low-pass filter.",
     "polo di chiusura dello stadio")
_add("ctle_zeros_hz", "CTLE", "CTLE output",
     "lista degli zeri della topologia multi-sezione (prodotto di "
     "sezioni reali): più sezioni = boost distribuito e controllo "
     "fine della forma, come le CTLE a 2-3 stadi dei RX reali. Quando "
     "la lista è attiva SOSTITUISCE i campi legacy (il manifest del "
     "pannello CTLE dichiara quale topologia è in uso). L'editor del "
     "pannello CTLE è il modo comodo di modificarla.",
     "the multi-section topology's zero list (a product of real "
     "sections): more sections = distributed boost and fine shape "
     "control, like the 2-3 stage CTLEs of real RXs. When the list "
     "is active it REPLACES the legacy fields (the CTLE panel "
     "manifest declares which topology is in use). The CTLE panel "
     "editor is the convenient way to edit it.",
     "H=G_DC·Π(1+s/ωzᵢ)/Π(1+s/ωpⱼ)", "lista non vuota")
_add("ctle_poles_hz", "CTLE", "CTLE output",
     "lista dei poli della topologia multi-sezione: accoppiata agli "
     "zeri definisce il profilo completo di boost. Vincolo pratico: "
     "ogni zero deve stare sotto il polo che lo chiude, e il banco "
     "lo protegge (clamp dichiarato nello sweep del primo zero).",
     "the multi-section topology's pole list: paired with the zeros "
     "it defines the full boost profile. Practical constraint: each "
     "zero must sit below the pole that closes it, and the bench "
     "enforces it (declared clamp in the first-zero sweep).",
     active="lista non vuota")
_add("ctle_dc_gain_db", "CTLE", "CTLE output",
     "guadagno DC della CTLE (tipicamente ≤0 dB): le CTLE reali "
     "ATTENUANO in bassa frequenza invece di amplificare l'alta — "
     "stesso rapporto spettrale, meno rumore attivo. È anche la leva "
     "che l'adattazione RX di AN/LT tocca. Sul banco: a peaking "
     "fisso, alzarlo verso 0 dB carica di più l'ADC; abbassarlo "
     "lascia margine ma butta segnale — il minimo BER sta nel mezzo.",
     "the CTLE's DC gain (typically ≤0 dB): real CTLEs ATTENUATE low "
     "frequencies rather than amplifying high ones — same spectral "
     "ratio, less active noise. Also the lever AN/LT's RX adaptation "
     "touches. On the bench: at fixed peaking, raising it toward "
     "0 dB loads the ADC harder; lowering it leaves margin but "
     "throws signal away — the BER minimum sits in between.",
     "boost = peaking − |G_DC|")
_add("adc_sps", "ADC", "A/D sampling plane",
     "campioni ADC per UI: 2 sps è LO standard dei ricevitori "
     "ADC-based (serve al Gardner e dà al FSE frazionario T/2 le "
     "bande laterali per correggere il timing); 1 sps è il mondo "
     "baud-rate (MM) che risparmia metà ADC ma pretende più "
     "dall'anello di clock. Sul banco: è il rapporto fra fs_adc e "
     "baud — a 2 sps l'ADC di un 56 GBd gira a 112 GS/s: il motivo "
     "per cui esistono 32-64 vie interleaved.",
     "ADC samples per UI: 2 sps is THE standard of ADC-based "
     "receivers (Gardner needs it, and the fractional T/2 FSE gets "
     "the sidebands to fix timing); 1 sps is the baud-rate (MM) "
     "world that saves half the ADC but demands more from the clock "
     "loop. On the bench: it is the fs_adc-to-baud ratio — at 2 sps "
     "a 56 GBd ADC runs at 112 GS/s: the reason 32-64 interleaved "
     "lanes exist.",
     "fs_adc=Rs·sps")
_add("adc_bits", "ADC", "A/D sampling plane",
     "risoluzione fisica dell'ADC: i ricevitori 112/224G usano 7-8 "
     "bit — non di più, perché oltre non serve: il rumore ANALOGICO "
     "della catena domina e l'ENOB effettivo si ferma comunque a "
     "~5.5-6. Il cascade audit lo dimostra: 5→7 bit migliora, 7→9 "
     "satura DAVVERO (Δq<0.05). Sotto ~6 bit la quantizzazione "
     "morde il PAM4 (12 soglie da distinguere!). Sul banco: 5 bit e "
     "guarda gli istogrammi DATA sgranarsi.",
     "the ADC's physical resolution: 112/224G receivers use 7-8 "
     "bits — no more, because beyond that the chain's ANALOG noise "
     "dominates and effective ENOB stalls at ~5.5-6 anyway. The "
     "cascade audit proves it: 5→7 bits improves, 7→9 TRULY "
     "saturates (Δq<0.05). Below ~6 bits quantization bites PAM4 "
     "(12 thresholds to resolve!). On the bench: set 5 bits and "
     "watch the DATA histograms pixelate.",
     "SQNR≈6.02·N+1.76 dB; LSB=FS/2^N")
_add("adc_full_scale_vpp", "ADC", "A/D sampling plane",
     "full-scale dell'ADC: il contratto con l'AGC. Segnale piccolo "
     "rispetto a FS = butti codici (ENOB effettivo giù); segnale "
     "oltre FS = clip duro. L'istogramma dei codici nel pannello ADC "
     "è la diagnosi: deve riempire il range senza toccare le righe "
     "rosse. Sul banco: muovi FS o il target AGC — sono la stessa "
     "trattativa vista dai due lati.",
     "the ADC full scale: the contract with the AGC. Signal small "
     "versus FS = codes wasted (effective ENOB down); signal beyond "
     "FS = hard clip. The ADC panel's code histogram is the "
     "diagnosis: it must fill the range without touching the red "
     "lines. On the bench: move FS or the AGC target — the same "
     "negotiation seen from either side.",
     "LSB=FS/2^N; clip oltre ±FS/2")
_add("adc_phase_ui", "ADC", "A/D sampling plane",
     "offset statico di fase di campionamento rispetto al centro "
     "occhio: dove l'ADC campiona davvero. Il CDR ne recupera la "
     "gran parte, ma l'offset residuo sposta il punto di lavoro "
     "sulla curva BER-vs-fase (il bathtub). È la manopola che l'auto "
     "search del BERT ottimizza. Sul banco: spazzala ±0.3 UI — la "
     "curva che ottieni È il bathtub del tuo link.",
     "static sampling-phase offset from eye center: where the ADC "
     "actually samples. The CDR recovers most of it, but the "
     "residual offset moves the operating point along the "
     "BER-vs-phase curve (the bathtub). The knob the BERT's auto "
     "search optimizes. On the bench: sweep it ±0.3 UI — the curve "
     "you get IS your link's bathtub.",
     "BER(φ): il bathtub")
_add("adc_jitter_rms_fs", "ADC", "A/D sampling plane",
     "aperture jitter del sample&hold: incertezza gaussiana "
     "sull'ISTANTE di campionamento. Il suo effetto cresce con la "
     "slew del segnale: SNR_j=−20log10(2π·f·σ_t) — a 50 GHz, 90 fs "
     "danno ~31 dB (ENOB ~4.9): è il muro dei convertitori veloci, "
     "e il tone-lab del banco lo riproduce ESATTAMENTE (verificato "
     "3.11 vs 3.11 bit a 300 fs). Clock 112G reali: 50-90 fs "
     "integrati. Sul banco: guarda l'ENOB@Nyq del pannello ADC "
     "inseguire la formula.",
     "the sample&hold's aperture jitter: Gaussian uncertainty on the "
     "sampling INSTANT. Its effect grows with signal slew: "
     "SNR_j=−20log10(2π·f·σ_t) — at 50 GHz, 90 fs gives ~31 dB "
     "(ENOB ~4.9): the wall of fast converters, and the bench's "
     "tone lab reproduces it EXACTLY (verified 3.11 vs 3.11 bits at "
     "300 fs). Real 112G clocks: 50-90 fs integrated. On the bench: "
     "watch the ADC panel's ENOB@Nyq chase the formula.",
     "SNR_j=−20log10(2πfσ_t)")
_add("adc_interleaves", "Time-interleaved ADC", "ADC sub-converters",
     "numero di sub-ADC alternati nel tempo: OGNI convertitore oltre "
     "~10 GS/s è un array (a 112 GS/s con SAR da ~2 GS/s servono "
     "32-64 vie). Il prezzo dell'interleaving sono le spur a k·fs/M "
     "da ogni mismatch fra vie — più vie = più righe, singolarmente "
     "più deboli. Sul banco: passa 4→32 vie a mismatch fissi e "
     "guarda lo spettro del tone-lab cambiare pettine; con i rank "
     "attivi la struttura si raggruppa a k·fs/R.",
     "the number of time-interleaved sub-ADCs: EVERY converter past "
     "~10 GS/s is an array (at 112 GS/s with ~2 GS/s SARs you need "
     "32-64 lanes). Interleaving's price is spurs at k·fs/M from "
     "every lane mismatch — more lanes = more lines, individually "
     "weaker. On the bench: go 4→32 lanes at fixed mismatch and "
     "watch the tone-lab spectrum change its comb; with ranks on, "
     "the structure regroups at k·fs/R.",
     "spur a k·fs/M; M=vie")
_add("adc_gain_mismatch_rms", "Time-interleaved ADC", "ADC sub-converters",
     "mismatch RMS di guadagno fra i sub-ADC: modula l'ampiezza a "
     "periodo M campioni → spur di AMPIEZZA alle righe k·fs/M, "
     "indipendenti dalla frequenza del segnale (a differenza dello "
     "skew). Residui calibrati reali: 0.2-0.6%. È uno dei tre "
     "bersagli della calibrazione (adc_cal_mode). Sul banco: "
     "alzalo con cal off e guarda le righe salire nel tone-lab a "
     "TONO BASSO — la firma che lo distingue dallo skew.",
     "RMS gain mismatch across sub-ADCs: it modulates amplitude "
     "with period M samples → AMPLITUDE spurs at the k·fs/M lines, "
     "independent of signal frequency (unlike skew). Real "
     "calibrated residuals: 0.2-0.6%. One of calibration's three "
     "targets (adc_cal_mode). On the bench: raise it with cal off "
     "and watch the lines grow in the LOW-tone lab — the signature "
     "separating it from skew.",
     "spur ∝ mismatch, indip. da f_in")
_add("adc_offset_mismatch_rms_v", "Time-interleaved ADC", "ADC sub-converters",
     "mismatch RMS di offset fra i sub-ADC: somma un pattern FISSO "
     "di periodo M → righe a k·fs/M che esistono ANCHE SENZA "
     "segnale (è l'unico mismatch visibile a ingresso spento). "
     "Residui reali: frazioni di mV. Sul banco: nel tone-lab le sue "
     "righe non scalano con l'ampiezza del tono — abbassa il "
     "segnale e restano lì.",
     "RMS offset mismatch across sub-ADCs: it adds a FIXED pattern "
     "of period M → k·fs/M lines that exist EVEN WITHOUT signal "
     "(the only mismatch visible with the input off). Real "
     "residuals: fractions of a mV. On the bench: in the tone lab "
     "its lines do not scale with tone amplitude — lower the signal "
     "and they stay.",
     "righe fisse a k·fs/M (anche a vuoto)")
_add("adc_skew_mismatch_rms_fs", "Time-interleaved ADC", "ADC sub-converters",
     "skew RMS dei clock di campionamento fra le vie: ogni via "
     "campiona un filo prima o dopo → errore ∝ slew del segnale, "
     "quindi spur che CRESCONO con la frequenza d'ingresso — a "
     "Nyquist è il mismatch dominante (per questo il tone-lab ha il "
     "tono alto). Residui calibrati reali: decine di fs. Con i rank "
     "attivi la componente di rank si somma. Sul banco: confronta "
     "ENOB tono basso vs Nyquist alzando solo lo skew: il divario "
     "che si apre è la sua firma.",
     "RMS sampling-clock skew across lanes: each lane samples "
     "slightly early or late → error ∝ signal slew, hence spurs "
     "GROWING with input frequency — at Nyquist it is the dominant "
     "mismatch (why the tone lab has the high tone). Real "
     "calibrated residuals: tens of fs. With ranks on, the rank "
     "component adds. On the bench: compare low-tone vs Nyquist "
     "ENOB while raising only skew: the widening gap is its "
     "signature.",
     "err ∝ 2πf·Δt: spur cresce con f_in")

# ========================================= ADC nuova generazione (SOTA)
_add("adc_ranks", "Time-interleaved ADC", "T/H front-end ranks",
     "rank di track&hold davanti all'array SAR (architettura 112/224G: "
     "pochi T/H veloci, molti SAR lenti): i lane di un rank CONDIVIDONO "
     "skew e banda del rank, concentrando le spur alle righe k·fs/R "
     "invece di k·fs/M — nei die reali sono le righe di rank a dominare "
     "lo spettro. 1 = array flat (storico). Deve dividere le vie di "
     "interleave. Sul banco: 32×4R con skew alto → nel tone-lab le "
     "righe si raggruppano sulle frequenze di rank.",
     "track&hold ranks in front of the SAR array (112/224G "
     "architecture: a few fast T/Hs, many slow SARs): lanes in a rank "
     "SHARE the rank's skew and bandwidth, concentrating spurs at "
     "k·fs/R lines instead of k·fs/M — in real dies the rank lines "
     "dominate the spectrum. 1 = flat array (legacy). Must divide the "
     "interleave count. On the bench: 32×4R with high skew → tone-lab "
     "lines regroup onto the rank frequencies.",
     "spur di rank: k·fs/R", "adc_ranks > 1 (skew/banda per rank)")
_add("adc_frontend_bw_hz", "Time-interleaved ADC", "T/H input bandwidth",
     "banda del front-end T/H (polo 1° ordine) prima del campionamento: "
     "limita il contenuto ad alta frequenza che l'ADC vede davvero — è "
     "il polo d'ingresso dichiarato nei datasheet dei RX ADC-based "
     "(~0.5-0.7·f_baud tipico). 0 = disattivo (storico). Sul banco: il "
     "cascade audit la verifica monotona (45→30→20 GHz: q sempre giù); "
     "è anche sweepable per tracciare la curva banda→BER.",
     "the T/H front-end bandwidth (1st-order pole) before sampling: it "
     "limits the high-frequency content the ADC actually sees — the "
     "input pole quoted in ADC-based RX datasheets (~0.5-0.7·f_baud "
     "typical). 0 = off (legacy). On the bench: the cascade audit pins "
     "it monotone (45→30→20 GHz: q always down); it is also sweepable "
     "to trace the bandwidth→BER curve.",
     "polo 1° ordine; tipico 0.5-0.7·f_baud", "adc_frontend_bw_hz > 0")
_add("adc_bw_mismatch_pct", "Time-interleaved ADC", "per-rank bandwidth spread",
     "spread rms della banda fra i rank T/H: un mismatch DIPENDENTE "
     "dalla frequenza (ampiezza E fase insieme) che la calibrazione "
     "gain/offset/skew NON può correggere — servirebbero equalizzatori "
     "per-lane. È la firma spettrale dominante degli interleaved reali "
     "vicino a Nyquist, e il motivo per cui i 224G integrano FFE "
     "per-slice. Sul banco: verificato che 10% di spread costa >3 dB "
     "di SNDR a Nyquist ma quasi nulla sul tono basso.",
     "rms bandwidth spread across T/H ranks: a frequency-DEPENDENT "
     "mismatch (amplitude AND phase together) that gain/offset/skew "
     "calibration canNOT correct — per-lane equalizers would be "
     "needed. The dominant spectral signature of real interleaved "
     "ADCs near Nyquist, and the reason 224G parts embed per-slice "
     "FFEs. On the bench: verified that 10% spread costs >3 dB of "
     "Nyquist SNDR but almost nothing on the low tone.",
     "H_r=1/(1+jf/bw_r): ampiezza+fase", "adc_frontend_bw_hz > 0")
_add("adc_cal_mode", "Time-interleaved ADC", "array calibration loop",
     "quanto mismatch residuo resta nell'array e se insegue il PVT: "
     "foreground = residui statici calibrati a nominale (col PVT il "
     "residuo scala — comportamento storico del banco, default); "
     "background = la calibrazione insegue lentamente PVT/temperatura "
     "(residuo di targa anche a caldo — lo stato dell'arte); off = SAR "
     "grezzo, mismatch ×8 DICHIARATO (ordine di grandezza da "
     "letteratura). Sul banco: a 85 °C con mismatch amplificati "
     "l'ordinamento misurato è q 1.76 (bg) > 1.75 (fg) > 1.18 (off) — "
     "scalda la camera e guardalo dal vivo.",
     "how much residual mismatch remains in the array and whether it "
     "tracks PVT: foreground = static residuals calibrated at nominal "
     "(residual scales with PVT — the bench's legacy behavior, "
     "default); background = the calibration slowly tracks "
     "PVT/temperature (nameplate residual even hot — the state of the "
     "art); off = raw SAR, ×8 mismatch DECLARED (literature order of "
     "magnitude). On the bench: at 85 °C with amplified mismatches the "
     "measured ordering is q 1.76 (bg) > 1.75 (fg) > 1.18 (off) — heat "
     "the chamber and watch it live.",
     "off=8×·PVT; fg=1×·PVT; bg=1×", "sempre / always")
_add("adc_noise_rms_mv", "Time-interleaved ADC", "input-referred noise",
     "rumore termico input-referred dell'ADC (kT/C del sampling cap + "
     "comparatore + reference): si somma PRIMA della quantizzazione e "
     "trascina l'ENOB effettivo sotto il limite di quantizzazione, "
     "come in ogni convertitore reale (è il motivo per cui un '8 bit' "
     "consegna ~5.5-6 ENOB). Ordine reale: 0.5-1.5 mV rms su FS ~1 V. "
     "0 = disattivo (storico). Sul banco: entra sia nel datapath (BER, "
     "cascade audit monotono) sia nel tone-lab (ENOB effettivo).",
     "the ADC's input-referred thermal noise (sampling-cap kT/C + "
     "comparator + reference): it adds BEFORE quantization and drags "
     "effective ENOB below the quantization limit, as in every real "
     "converter (why an '8-bit' part delivers ~5.5-6 ENOB). Real "
     "order: 0.5-1.5 mV rms on ~1 V FS. 0 = off (legacy). On the "
     "bench: it enters both the datapath (BER, monotone cascade "
     "audit) and the tone lab (effective ENOB).",
     "ENOB_eff=(SNDR−1.76)/6.02", "adc_noise_rms_mv > 0")

# ================================================================ CDR
_add("cdr_mode", "CDR", "recovered sampling clock",
     "sceglie il TED del loop: Gardner (2 sps, non richiede decisioni "
     "— robusto in acquisizione, lo standard dei RX ADC-based in "
     "bring-up) o Mueller-Müller (baud-rate, decision-directed — metà "
     "campioni, il tracking di regime dei 112G reali). 'oracle' è il "
     "riferimento ideale DICHIARATO: timing perfetto senza loop, utile "
     "solo per isolare il resto della catena. Il guadagno del TED è "
     "stimato con probe cieco della S-curve, mai dall'oracolo. Sul "
     "banco: pannello Timing — riga TED col guadagno misurato e le due "
     "S-curve a confronto.",
     "selects the loop's TED: Gardner (2 sps, no decisions needed — "
     "robust in acquisition, the ADC-based RX standard at bring-up) or "
     "Mueller-Müller (baud-rate, decision-directed — half the samples, "
     "the steady-state tracking of real 112G parts). 'oracle' is the "
     "DECLARED ideal reference: perfect timing with no loop, useful "
     "only to isolate the rest of the chain. The TED gain is estimated "
     "with a blind S-curve probe, never from the oracle. On the bench: "
     "Timing panel — the TED row with measured gain and both S-curves "
     "side by side.",
     "Gardner: (y_l−y_e)·y_m; MM: d_{k-1}y_k−d_k y_{k-1}")
_add("cdr_bw", "CDR", "recovered sampling clock",
     "banda del loop in frazione del baud (es. 0.002 = ~112 MHz a "
     "56 GBd): decide COSA il CDR insegue e cosa lascia passare. "
     "Larga = insegue SSC/wander e PJ basso ma lascia entrare il "
     "rumore di fase del loop; stretta = filtro pulito ma tracking "
     "lento (lock più lungo, SSC a rischio). La curva JTOL ha il "
     "ginocchio ESATTAMENTE qui. Sul banco: misura la JTOL, poi "
     "cambia cdr_bw e rimisura — il ginocchio si sposta con la "
     "manopola.",
     "the loop bandwidth as a baud fraction (e.g. 0.002 = ~112 MHz "
     "at 56 GBd): it decides WHAT the CDR tracks and what it lets "
     "through. Wide = tracks SSC/wander and low-frequency PJ but "
     "admits loop phase noise; narrow = clean filter but slow "
     "tracking (longer lock, SSC at risk). The JTOL curve's knee "
     "sits EXACTLY here. On the bench: measure JTOL, change cdr_bw, "
     "measure again — the knee moves with the knob.",
     "f_loop≈cdr_bw·f_baud")
_add("cdr_damping", "CDR", "recovered sampling clock",
     "smorzamento ζ del loop PI di 2° ordine: sotto ~0.7 il loop "
     "risuona e compare il JITTER PEAKING — amplificazione >0 dB del "
     "jitter vicino al corner (il picco della JTF e l'avvallamento "
     "della JTOL). Gli standard limitano il peaking a frazioni di dB "
     "proprio per evitare che si accumuli in cascata. Sul banco: "
     "ζ=0.3 e misura la JTF — il picco che vedi è da manuale; "
     "riportalo a 1 e sparisce.",
     "the 2nd-order PI loop's damping ζ: below ~0.7 the loop "
     "resonates and JITTER PEAKING appears — >0 dB amplification of "
     "jitter near the corner (the JTF's peak and the JTOL's dip). "
     "Standards cap peaking at fractions of a dB precisely so it "
     "cannot accumulate through cascades. On the bench: set ζ=0.3 "
     "and measure the JTF — the peak you see is textbook; return to "
     "1 and it vanishes.",
     "peaking ↑ per ζ<0.7")
_add("rx_ppm_offset", "CDR", "recovered sampling clock",
     "offset di frequenza fra clock RX e TX in ppm: i due riferimenti "
     "sono oscillatori DIVERSI (±100 ppm ciascuno da standard "
     "Ethernet, quindi fino a ±200 di delta). Il loop lo assorbe nel "
     "registro di FREQUENZA (l'integratore del PI): senza integratore "
     "la fase scapperebbe di un UI ogni 1/ppm simboli. Sul banco: "
     "il segno e (f_RX−f_TX)/f_TX: positivo significa RX piu veloce. "
     "±100 ppm → nel pannello Timing il registro di frequenza si "
     "assesta sul valore impostato (linea tratteggiata di "
     "verifica).",
     "the RX-vs-TX clock frequency offset in ppm: the two references "
     "are DIFFERENT oscillators (±100 ppm each per Ethernet "
     "standards, so up to ±200 delta). The loop absorbs it in its "
     "FREQUENCY register (the PI integrator): without the integrator, "
     "phase would run away one UI every 1/ppm symbols. On the bench: "
     "the sign is (f_RX−f_TX)/f_TX: positive means a faster RX clock. "
     "Set ±100 ppm → the Timing panel's frequency register settles "
     "on the set value (dashed verification line).",
     "t_RX=n/[f_TX·(1+ppm·10⁻⁶)]; f̂ → ppm_set")

# ============================================================== RX DSP
_add("fse_taps", "RX DSP", "post-ADC equalization",
     "tap del feed-forward equalizer frazionario T/2: il "
     "raddrizzatore LINEARE del canale — corregge ISI pre e "
     "post-cursore e, lavorando a 2 sps, ripulisce anche l'errore di "
     "fase residuo del CDR. Più tap = più memoria (in UI: tap/2) per "
     "canali lunghi, ma adattamento più lento e più rumore "
     "amplificato sulle celle esterne. RX reali: 16-32 tap. Sul "
     "banco: pannello EQ — i pesi adattati DISEGNANO l'inverso del "
     "canale; con l'eco spostata vedi il tap corrispondente "
     "accendersi.",
     "the fractional T/2 feed-forward equalizer taps: the channel's "
     "LINEAR straightener — it corrects pre and post-cursor ISI and, "
     "running at 2 sps, also cleans the CDR's residual phase error. "
     "More taps = more memory (in UI: taps/2) for long channels, but "
     "slower adaptation and more amplified noise on the outer cells. "
     "Real RXs: 16-32 taps. On the bench: EQ panel — the adapted "
     "weights DRAW the channel inverse; move the echo and watch the "
     "matching tap light up.",
     "y=Σw_k·x(t−kT/2); copertura=tap/2 UI")
_add("dfe_taps", "RX DSP", "post-ADC equalization",
     "tap del decision-feedback equalizer: cancella l'ISI "
     "post-cursore usando le DECISIONI passate — sottrae repliche "
     "PULITE, quindi non amplifica il rumore come farebbe un FFE "
     "sullo stesso cursore. Il rovescio: una decisione sbagliata "
     "inietta ISI sbagliata → burst di errori (il motivo "
     "dell'interleaving FEC). Cascade audit: più tap → BER giù "
     "sull'eco del canale. Sul banco: 1 vs 8 tap con echo_delay a "
     "2.5 UI, poi sposta l'eco oltre la memoria del DFE e guardalo "
     "perdere la presa.",
     "the decision-feedback equalizer taps: it cancels post-cursor "
     "ISI using past DECISIONS — subtracting CLEAN replicas, so it "
     "does not amplify noise as an FFE would on the same cursor. The "
     "flip side: one wrong decision injects wrong ISI → error bursts "
     "(the reason FEC interleaving exists). Cascade audit: more taps "
     "→ lower BER on the channel echo. On the bench: 1 vs 8 taps "
     "with echo_delay at 2.5 UI, then push the echo past the DFE "
     "memory and watch it lose grip.",
     "y_k=x_k−Σb_i·d_{k−i}")
_add("training_start", "RX DSP", "post-ADC equalization",
     "simbolo d'inizio dell'adattamento LMS: prima di questo punto "
     "l'equalizzatore non tocca i pesi — lascia al CDR il tempo di "
     "agganciare (adattare su campioni non allineati insegna "
     "spazzatura). È la coreografia di bring-up reale: prima il "
     "clock, poi l'EQ. Sul banco: pannello EQ, curva di learning "
     "MSE — parte esattamente da qui.",
     "the LMS adaptation start symbol: before this point the "
     "equalizer leaves its weights alone — giving the CDR time to "
     "lock (adapting on misaligned samples teaches garbage). The "
     "real bring-up choreography: clock first, then EQ. On the "
     "bench: EQ panel, MSE learning curve — it starts exactly here.")
_add("training_stop", "RX DSP", "post-ADC equalization",
     "fine del training e inizio della zona di VALIDATION: da qui in "
     "poi i pesi sono congelati e ogni bit contato è 'onesto' — "
     "misurare la BER sui simboli usati per adattare darebbe un "
     "risultato ottimisticamente contaminato (in-sample). La "
     "separazione train/validation è la stessa igiene statistica del "
     "machine learning, applicata a un ricevitore. Sul banco: la "
     "mappa errori del BERT marca l'inizio validation con la linea "
     "tratteggiata.",
     "the training end and start of the VALIDATION zone: from here "
     "the weights are frozen and every counted bit is 'honest' — "
     "measuring BER on the symbols used for adaptation would give an "
     "optimistically contaminated (in-sample) result. The "
     "train/validation split is the same statistical hygiene as "
     "machine learning, applied to a receiver. On the bench: the "
     "BERT error map marks validation start with the dashed line.")

# ================================================================ PVT
_add("pvt_process", "RX PVT", "TIA/CTLE/ADC/CDR (receiver only)",
     "corner di processo del die RX: SS (transistor lenti, −15% di "
     "banda sui blocchi analogici, mismatch peggiore), TT (tipico, "
     "fattori identità — baseline intatta), FF (veloci, banda in "
     "più). È la lotteria del silicio che il collaudo industriale "
     "deve coprire: un design va chiuso al corner SS-caldo, non al "
     "tipico. Sul banco: SS + 105 °C + VDD −10% è il worst case "
     "classico — la CTLE perde peaking proprio dove serve.",
     "the RX die's process corner: SS (slow transistors, −15% "
     "analog-block bandwidth, worse mismatch), TT (typical, identity "
     "factors — baseline intact), FF (fast, extra bandwidth). The "
     "silicon lottery industrial qualification must cover: a design "
     "closes at the SS-hot corner, not at typical. On the bench: "
     "SS + 105 °C + VDD −10% is the classic worst case — the CTLE "
     "loses peaking exactly where it is needed.",
     "bw=corner·(1−0.0015ΔT)·(1+0.005ΔV%)")
_add("pvt_vdd_pct", "RX PVT", "TIA/CTLE/ADC/CDR (receiver only)",
     "variazione percentuale della supply del RX: −10% di VDD costa "
     "~−5% di banda ai blocchi analogici (headroom e g_m calano) e "
     "stringe le rail. Gli standard di alimentazione garantiscono "
     "±5-10%: il ricevitore deve chiudere il link su tutto il range. "
     "Sul banco: combinala col corner e la temperatura per "
     "riprodurre lo screening PVT completo.",
     "the RX supply variation in percent: −10% VDD costs ~−5% "
     "analog bandwidth (headroom and g_m drop) and tightens the "
     "rails. Supply standards guarantee ±5-10%: the receiver must "
     "close the link across the whole range. On the bench: combine "
     "it with corner and temperature to reproduce a full PVT "
     "screening.",
     "ΔBW≈+0.5%·ΔVDD%")
_add("pvt_temp_c", "RX PVT", "TIA/CTLE/ADC/CDR (receiver only)",
     "temperatura del die RX: la mobilità cala (~−0.15%/°C di banda), "
     "il rumore termico cresce con √T assoluta, la dark current del "
     "PD raddoppia ogni ~8-10 °C (Arrhenius) e i mismatch ADC "
     "peggiorano con |ΔT| — a meno che la cal background non li "
     "insegua (adc_cal_mode). È la manopola pilotata dalla camera "
     "climatica: coi profili cycle/ramp/soak il die la insegue col "
     "suo lag termico. Sul banco: rampa 25→105 °C e guarda q_min "
     "scivolare nella strip-chart temp/Q del pannello RX front-end.",
     "the RX die temperature: mobility drops (~−0.15%/°C of "
     "bandwidth), thermal noise grows with absolute √T, PD dark "
     "current doubles every ~8-10 °C (Arrhenius) and ADC mismatches "
     "worsen with |ΔT| — unless background cal tracks them "
     "(adc_cal_mode). The knob the climate chamber drives: with "
     "cycle/ramp/soak profiles the die follows with its thermal lag. "
     "On the bench: ramp 25→105 °C and watch q_min slide in the RX "
     "front-end panel's temp/Q strip chart.",
     "noise∝√T; I_dark~Arrhenius; bw −0.15%/°C")
