"""Contratti bilingui delle azioni del banco LabPro.

Le manopole descrivono una grandezza fisica; i pulsanti descrivono invece una
transazione.  Questo catalogo rende espliciti piano osservato, effetto atteso,
stato modificato e confine del risultato per ogni azione importante della UI.
"""

from __future__ import annotations


ACTION_HELP: dict[str, dict[str, str]] = {}


def _a(action, title_it, title_en, block, plane, it, en, observe_it,
       observe_en, boundary_it, boundary_en, endpoint="", mutates=""):
    ACTION_HELP[action] = {
        "title_it": title_it, "title_en": title_en,
        "block": block, "plane": plane, "it": it, "en": en,
        "observe_it": observe_it, "observe_en": observe_en,
        "boundary_it": boundary_it, "boundary_en": boundary_en,
        "endpoint": endpoint, "mutates": mutates,
    }


_a("bench_run", "RUN / STOP", "RUN / STOP", "LiveBench", "acquisition scheduler",
   "Avvia o ferma l'acquisizione continua senza cambiare la LinkConfig.",
   "Starts or stops continuous acquisition without changing LinkConfig.",
   "Controlla LED, record/s e avanzamento dei contatori.",
   "Check the LED, records/s, and accumulating counters.",
   "STOP congela nuovi record; non cancella quelli accumulati.",
   "STOP freezes new records; it does not clear accumulated data.",
   "/api/run", "running state")
_a("tx_output", "TX OUTPUT on/off", "TX OUTPUT on/off",
   "BERT · PPG", "driver output stage",
   "Accende/spegne l'uscita dello stadio TX come il tasto Output di un PPG: "
   "OFF = mute elettrico (P/N al solo common-mode), sorgente ottica accesa.",
   "Toggles the TX output stage like a PPG's Output key: OFF = electrical "
   "mute (P/N at common-mode only), optical source still on.",
   "Con OUTPUT OFF: scope piatto al nodo driver, CDR senza lock, LINK DOWN "
   "in topbar e SYNC LOSS all'ED; alla riaccensione il lock torna da solo.",
   "With OUTPUT OFF: flat scope at the driver node, no CDR lock, LINK DOWN "
   "in the topbar and ED SYNC LOSS; lock returns on its own at re-enable.",
   "È un mute del DRIVE elettrico, non lo spegnimento del laser. laser_dbm "
   "arriva solo a -6 dBm: LASER OFF non è modellato. Cambio config: "
   "l'accumulo riparte.",
   "It mutes the electrical DRIVE, it does not turn the laser off. "
   "laser_dbm only reaches -6 dBm: LASER OFF is not modeled. Config change: "
   "accumulators restart.",
   "/api/config", "tx_output_on")
_a("panel_export", "Esporta card", "Export card",
   "UI", "browser download",
   "Scarica i grafici della card come PNG (scala 2×), il canvas dello "
   "Scope come PNG e le tabelle come CSV.",
   "Downloads the card's plots as PNG (2× scale), the Scope canvas as PNG, "
   "and its tables as CSV.",
   "Un file per ogni grafico/tabella presente; il browser può chiedere il "
   "permesso per download multipli.",
   "One file per plot/table present; the browser may ask permission for "
   "multiple downloads.",
   "Fotografa ciò che la card mostra ORA (stesso record/fonte dichiarati "
   "dal badge LIVE/REF); non modifica il banco.",
   "Snapshots what the card shows NOW (same record/source declared by the "
   "LIVE/REF badge); the bench is not modified.",
   "", "report only")
_a("bert_sensitivity", "RX sensitivity search", "RX sensitivity search",
   "BERT · ED", "optical power → counted BER",
   "Bisezione sulla potenza ottica lanciata (a seed fisso) per trovare la "
   "minima potenza al PD con BER contata ≤ target e link UP; target di "
   "default = soglia pre-FEC iid del FEC in-path.",
   "Bisection on the launched optical power (fixed seed) to find the "
   "minimum PD power with counted BER ≤ target and link UP; default "
   "target = iid pre-FEC threshold of the in-path FEC.",
   "Soglia in dBm al PD, margine rispetto al punto operativo, traiettoria "
   "della bisezione e bit/durata per confermare il target a CL95.",
   "Threshold in dBm at the PD, margin vs the operating point, bisection "
   "trail, and bits/duration to confirm the target at CL95.",
   "Potenza MEDIA, non OMA_outer: la sensitivity di clause richiede "
   "stressed RX calibrato e procedura prescritta. Solo mezzo ottico. "
   "Il banco non viene modificato.",
   "AVERAGE power, not OMA_outer: clause sensitivity requires a calibrated "
   "stressed RX and a prescribed procedure. Optical medium only. "
   "The bench is not modified.",
   "/api/experiment/sensitivity", "report only")
_a("bert_stress_cal", "Stressed-eye calibration", "Stressed-eye calibration",
   "BERT · stress", "TX PJ → slicer eye opening",
   "Bisezione sull'ampiezza del PJ al TX PLL fino a portare l'apertura "
   "d'occhio misurata allo slicer (q_min) appena sopra il target: è la "
   "calibrazione dello stress prima di un test del ricevitore.",
   "Bisection on the TX-PLL PJ amplitude until the measured slicer eye "
   "opening (q_min) sits just above the target: stress calibration before "
   "a receiver test.",
   "Ricetta (UI/ps @ freq), Q calibrato vs Q senza stress e traiettoria; "
   "con la spunta la ricetta viene applicata a tx_pj_amp_ui.",
   "Recipe (UI/ps @ freq), calibrated Q vs unstressed Q, and the trail; "
   "when ticked the recipe is applied to tx_pj_amp_ui.",
   "Solo PJ: la ricetta di clause combina SJ+RJ+interferenza con strumento "
   "e maschera prescritti. Esiti dichiarati: già sotto target / stress "
   "insufficiente al cap.",
   "PJ only: the clause recipe combines SJ+RJ+interference with a "
   "prescribed instrument and mask. Declared outcomes: already below "
   "target / stress insufficient at the cap.",
   "/api/experiment/stresscal",
   "report; tx_pj_amp_ui when 'apply recipe' is checked")
_a("config_export", "Esporta configurazione", "Export configuration",
   "Bench", "LinkConfig snapshot",
   "Scarica un file JSON versionato con tutti i campi del banco e le "
   "impostazioni della camera climatica.",
   "Downloads a versioned JSON file with all bench fields and the "
   "climate-chamber settings.",
   "Il file deve contenere version, cfg completa e chamber; rimportandolo "
   "il banco torna identico.",
   "The file must contain version, the full cfg, and chamber; re-importing "
   "it restores the identical bench.",
   "Non modifica nulla: è una fotografia della configurazione corrente.",
   "Changes nothing: it is a snapshot of the current configuration.",
   "/api/config/export", "report only")
_a("config_import", "Importa configurazione", "Import configuration",
   "Bench", "LinkConfig snapshot",
   "Carica un file esportato dal banco: la config viene validata, i campi "
   "non più esistenti scartati con nota, poi applicata e persistita.",
   "Loads a bench-exported file: the config is validated, removed fields "
   "are dropped with a note, then applied and persisted.",
   "Manopole e chip devono riflettere il file; il toast elenca gli "
   "eventuali campi scartati.",
   "Knobs and chips must reflect the file; the toast lists any dropped "
   "fields.",
   "Sostituisce TUTTA la configurazione (accumulo azzerato, come ogni "
   "cambio config); un file non valido viene rifiutato senza toccare nulla.",
   "Replaces the WHOLE configuration (accumulators reset, as with any "
   "config change); an invalid file is rejected without touching anything.",
   "/api/config/import", "full LinkConfig + chamber")
_a("experiment_cancel", "Annulla esperimento", "Cancel experiment",
   "Experiment", "worker pool scheduler",
   "Chiede l'interruzione cooperativa dell'esperimento in corso: si ferma "
   "al confine del record successivo, mai a metà di una simulate.",
   "Requests cooperative cancellation of the running experiment: it stops "
   "at the next record boundary, never mid-simulate.",
   "Il chip ⏳ deve sparire e il pannello dell'esperimento mostrare "
   "l'annullamento; il bench riparte se era in RUN.",
   "The ⏳ chip must disappear and the experiment panel must report the "
   "cancellation; the bench restarts if it was running.",
   "I punti già misurati vengono scartati: l'esperimento annullato non "
   "produce un report parziale.",
   "Already-measured points are discarded: a cancelled experiment does not "
   "produce a partial report.",
   "/api/experiment/cancel", "report only")
_a("bench_reset", "Azzera statistiche", "Reset statistics", "LiveBench", "accumulators",
   "Azzera BER, FEC, frame, istogrammi e history del banco.",
   "Clears BER, FEC, frame, histogram, and bench-history accumulators.",
   "La configurazione e i valori delle manopole devono restare identici.",
   "Configuration and knob values must remain identical.",
   "Non è un reset fisico del link o del modello CDR.",
   "This is not a physical link or CDR-model reset.",
   "/api/reset", "accumulators only")
_a("anlt_apply", "AN/LT con applicazione", "AN/LT and apply", "AN/LT", "partner + TX/RX",
   "Negozia l'HCD, esegue training bidirezionale e applica i tap solo dopo holdout.",
   "Resolves the HCD, runs bidirectional training, and applies taps only after holdout.",
   "Verifica HCD, CDR lock, both-ready, Q prima/dopo e flag applied.",
   "Verify HCD, CDR lock, both-ready, Q before/after, and the applied flag.",
   "Protocollo didattico Clause 73/72-136: niente segnalazione DME reale.",
   "Educational Clause 73/72-136 protocol: no real DME signalling.",
   "/api/experiment/anlt", "TX FIR/CTLE only when holdout passes")
_a("scope_pause", "Pausa display", "Pause display", "Scope", "browser display",
   "Congela solo la persistenza dello Scope.", "Freezes Scope persistence only.",
   "I contatori topbar devono continuare ad avanzare mentre il canvas resta fermo.",
   "Top-bar counters must keep advancing while the canvas stays frozen.",
   "Non ferma il LiveBench e non congela un record globale.",
   "It does not stop LiveBench or freeze a global record.", mutates="local UI only")
_a("scope_coherent", "P/N · Diff · CM", "P/N · Diff · CM", "Scope", "driver pin planes",
   "Configura CH A-D sui quattro piani coerenti dello stesso record.",
   "Maps CH A-D to four coherent planes from the same record.",
   "Controlla seed/record uguale e identità Vdiff=Vp−Vn, Vcm=(Vp+Vn)/2.",
   "Check equal seed/record and Vdiff=Vp−Vn, Vcm=(Vp+Vn)/2 identities.",
   "È una configurazione di probe, non una modifica del trasmettitore.",
   "This is a probe configuration, not a transmitter change.", mutates="local Scope routing")
_a("eye_contour", "Contour BER 2D", "2D BER contour", "Scope", "selected CH A plane",
   "Calcola una mappa fase/ampiezza della BER estrapolata.",
   "Computes a phase/amplitude map of extrapolated BER.",
   "Devono apparire isolinee chiuse e assi coerenti col nodo scelto.",
   "Closed contours and axes consistent with the selected node must appear.",
   "Code gaussiane dichiarate: non è una mask o contour normativa.",
   "Declared Gaussian tails: not a normative mask or contour.",
   "/api/panel/eyecontour", "report only")
_a("ctle_preset", "Preset CTLE", "CTLE preset", "CTLE", "CTLE transfer",
   "Carica una topologia zero/polo predefinita nell'editor.",
   "Loads a predefined zero/pole topology into the editor.",
   "Verifica ordine dei corner e risposta in frequenza dopo l'applicazione.",
   "Verify corner ordering and frequency response after applying it.",
   "Il click del preset applica la topologia al banco; non è auto-tuning.",
   "The preset click applies the topology to the bench; it is not auto-tuning.",
   "/api/config", "ctle_zeros_hz + ctle_poles_hz")
_a("ctle_apply", "Applica CTLE", "Apply CTLE", "CTLE", "CTLE transfer",
   "Valida e applica le liste GHz inserite nell'editor.",
   "Validates and applies the GHz lists entered in the editor.",
   "La curva deve cambiare; valori non ordinati o non numerici devono essere rifiutati.",
   "The curve must change; unordered or non-numeric values must be rejected.",
   "Modifica il datapath condiviso e azzera gli accumulatori.",
   "Changes the shared datapath and clears accumulators.",
   "/api/config", "ctle_zeros_hz + ctle_poles_hz")
_a("pattern_apply", "Applica pattern HEX", "Apply HEX pattern", "PPG", "serialized PPG bits",
   "Normalizza e applica 1..4096 byte HEX ciclici MSB-first.",
   "Normalizes and applies 1..4096 cyclic MSB-first HEX bytes.",
   "Controlla periodo, byte normalizzati e digest/readout del PPG.",
   "Check period, normalized bytes, and the PPG digest/readout.",
   "Pattern di laboratorio; non sostituisce SSPRQ/QPRBS di clause.",
   "Lab pattern; it does not replace clause SSPRQ/QPRBS.",
   "/api/config", "pattern + custom_pattern_hex")
_a("tx_tap_count", "Numero tap TX FIR", "TX FIR tap count", "TX FIR", "pre-DAC symbols",
   "Commuta in modo reversibile fra FIR a 3 e 5 tap mantenendo il main cursor.",
   "Reversibly switches between 3- and 5-tap FIR while preserving the main cursor.",
   "Verifica H(0), H(Nyquist), swing cost e clipping.",
   "Verify H(0), H(Nyquist), swing cost, and clipping.",
   "Aggiungere zeri non deve cambiare la waveform; tap non nulli sì.",
   "Zero padding must not change the waveform; non-zero taps must.",
   "/api/config", "tx_ffe_taps")
_a("s2p_use", "Usa Touchstone", "Use Touchstone", "Channel", "measured S21/SDD21",
   "Carica il file selezionato e sostituisce il canale analitico nel datapath.",
   "Loads the selected file and replaces the analytic channel in the datapath.",
   "Controlla nome sorgente, IL/phase/pulse e BER a valle; il TX a monte non cambia.",
   "Check source name, IL/phase/pulse, and downstream BER; upstream TX must not change.",
   "Serve un file S2P/S4P valido; mapping delle coppie obbligatorio per S4P.",
   "Requires a valid S2P/S4P file; pair mapping is mandatory for S4P.",
   "/api/s2p", "s2p payload + use_s2p_channel")
_a("s2p_model", "Torna al canale analitico", "Return to analytic channel", "Channel", "channel S21",
   "Disabilita l'uso del Touchstone senza cancellarne il contenuto salvato.",
   "Disables Touchstone use without deleting its saved content.",
   "Il badge sorgente deve tornare a model e l'S21 alla parametrizzazione del banco.",
   "The source badge must return to model and S21 to bench parameters.",
   "Il file resta disponibile per una riattivazione successiva.",
   "The file remains available for later reactivation.",
   "/api/config", "use_s2p_channel=false")
_a("jtf", "Misura jitter transfer", "Measure jitter transfer", "CDR", "TX TIE → recovered clock",
   "Inietta toni PJ e misura il rapporto di ampiezza sul clock recuperato.",
   "Injects PJ tones and measures recovered-clock amplitude ratio.",
   "La JTF deve essere vicina a 0 dB in banda e attenuarsi fuori banda.",
   "JTF should be near 0 dB in-band and attenuate out-of-band.",
   "Record finito e fit sinusoidale: diagnostica, non maschera normativa.",
   "Finite record and sine fit: diagnostic, not a normative mask.",
   "/api/experiment/jtf", "report only")
_a("dr4", "Procedura DR4 completa", "Full DR4 procedure", "DR4 TDECQ", "PPG → TX → fiber → RX/DSP",
   "Esegue il periodo SSPRQ completo su loss, CD e DGD della procedura versionata.",
   "Runs the complete SSPRQ period over versioned loss, CD, and DGD stress.",
   "Controlla pattern exact, due endpoint, link/BER, TDECQ e u_grid.",
   "Check exact pattern, both endpoints, link/BER, TDECQ, and u_grid.",
   "MODEL PASS/FAIL resta separato da IEEE NOT ASSESSED.",
   "MODEL PASS/FAIL remains separate from IEEE NOT ASSESSED.",
   "/api/experiment/dr4-tdecq", "report only")
_a("academy_open", "Apri pannello associato", "Open associated panel", "Academy", "workspace layout",
   "Apre la card operativa collegata alla lezione selezionata.",
   "Opens the operational panel linked to the selected lesson.",
   "La card deve comparire una sola volta e mantenere l'ordine di flusso.",
   "The card must appear once and retain signal-flow ordering.",
   "Cambia solo il layout, non la fisica.", "Changes layout only, not physics.",
   mutates="layout only")
_a("bert_inject", "Inserisci errori", "Insert errors", "BERT PPG + ED",
   "coded TX bits → physical RX → pre/post-FEC checker",
   "Inverte bit di linea dopo l'encoder FEC al TX. Il record attraversa "
   "l'unico RX fisico (AFE/ADC/CDR/FSE/DFE); l'ED confronta il tap pre-FEC e, "
   "se attivo, quello post-FEC.",
   "Flips coded line bits after the TX FEC encoder. The record crosses the "
   "single physical RX (AFE/ADC/CDR/FSE/DFE); the ED checks the pre-FEC tap "
   "and, when enabled, the post-FEC tap.",
   "Il risultato latched deve mostrare bit TX inseriti, lock RX, errori "
   "pre-FEC, frame/simboli corretti o persi ed errori post-FEC.",
   "The latched result must show inserted TX bits, RX lock, pre-FEC errors, "
   "corrected/lost frames or symbols, and post-FEC errors.",
   "Transazione single-flight sul prossimo record. Con FEC=none il tap "
   "post-FEC è BYPASS; senza lock l'ED non dichiara una BER valida.",
   "Single-flight transaction on the next record. With FEC=none the post-FEC "
   "tap is BYPASS; without lock the ED reports no valid BER.",
   "/api/inject", "one physical record + latched report")
_a("bert_gate", "Gate START / STOP", "Gate START / STOP", "BERT", "ED accumulation window",
   "Apre o chiude una finestra statistica indipendente dai contatori globali.",
   "Opens or closes a statistical window independent of global counters.",
   "Controlla bit/errori gated e intervallo di confidenza 95%.",
   "Check gated bits/errors and the 95% confidence interval.",
   "Non interrompe il segnale e non resetta il banco.",
   "It neither interrupts the signal nor resets the bench.", mutates="local BERT gate")
_a("bert_phase", "Auto-search fase", "Phase auto-search", "BERT", "ADC sampling phase",
   "Scansiona la fase e applica quella con BER migliore.",
   "Scans sampling phase and applies the one with best BER.",
   "La tabella deve mostrare tutti i candidati, inclusi eventuali LINK DOWN.",
   "The table must show every candidate, including any LINK DOWN point.",
   "Ricerca su record finiti; può sovra-adattare al seed corrente.",
   "Finite-record search; it can overfit the current seed.",
   "/api/experiment/sweep", "adc_phase_ui")
_a("stressed_rx", "Stressed RX (SECQ)", "Stressed RX (SECQ)", "BERT · procedures",
   "TX stress → reference receiver → RX/DSP",
   "Calibra una ricetta di stress (SJ dichiarato + RIN alla sorgente per "
   "bisezione) finché il SECQ al ricevitore di riferimento raggiunge il target "
   "del registro, poi misura la BER del RX su un record lungo con verdetto "
   "Clopper-Pearson.",
   "Calibrates a stress recipe (declared SJ + RIN at the source by bisection) "
   "until the SECQ at the reference receiver reaches the registry target, then "
   "measures the RX BER on a long record with a Clopper-Pearson verdict.",
   "Guarda la traccia della bisezione, il SECQ calibrato contro il limite e la "
   "BER del RX; 'already_above' significa che il TX da solo eccede il target.",
   "Watch the bisection trail, the calibrated SECQ against the limit and the RX "
   "BER; 'already_above' means the TX alone exceeds the target.",
   "Non modifica il banco; SI di clausola e incertezza strumentale restano "
   "NOT ASSESSED: è un criterio del modello, non una conformità.",
   "Does not modify the bench; clause SI and instrument uncertainty stay NOT "
   "ASSESSED: a model criterion, not compliance.",
   "/api/experiment/stressed-rx", "report only")
_a("golden_load", "Carica dataset golden", "Load golden dataset", "DR4 · golden",
   "instrument waveform → LabPro measures",
   "Carica un JSON labpro-golden/1 (waveform ottica, simboli, riferimenti "
   "TDECQ/OMA/ER dello strumento) e confronta le misure LabPro sulla stessa "
   "waveform con i valori dichiarati.",
   "Loads a labpro-golden/1 JSON (optical waveform, symbols, instrument "
   "TDECQ/OMA/ER references) and compares the LabPro measures on the same "
   "waveform with the declared values.",
   "Tabella LabPro vs strumento con Δ e tolleranza; source=instrument chiude "
   "lo step 'correlation' della DR4 alla prossima esecuzione.",
   "LabPro vs instrument table with Δ and tolerance; source=instrument closes "
   "the DR4 'correlation' step at the next run.",
   "Il file è letto in memoria e non salvato; il verdetto è del modello, la "
   "conformità resta NOT ASSESSED.",
   "The file is read in memory and not stored; the verdict is the model's, "
   "compliance stays NOT ASSESSED.",
   "/api/golden", "last golden dataset (in memory)")
_a("golden_example", "Esempio sintetico", "Synthetic example", "DR4 · golden",
   "self-generated waveform",
   "Genera dal banco stesso un dataset golden di esempio e lo correla: serve "
   "a esercitare la pipeline, per costruzione i Δ sono ~0.",
   "Generates an example golden dataset from the bench itself and correlates "
   "it: it exercises the pipeline, by construction the Δ are ~0.",
   "Verdetto PROXY (auto-correlazione) e Δ nulli.",
   "PROXY verdict (self-correlation) and zero Δ.",
   "Non è una correlazione strumentale: non chiude lo step della DR4.",
   "Not an instrument correlation: it does not close the DR4 step.",
   "/api/golden", "last golden dataset (in memory)")
_a("traffic_benchmark", "Benchmark frame size", "Frame-size benchmark", "Traffic", "MAC → PHY → analyzer",
   "Esegue frame reali a più dimensioni attraverso la catena completa.",
   "Runs real frames of several sizes through the complete chain.",
   "Controlla expected/detected/FCS/lost e dipendenza dalla dimensione.",
   "Check expected/detected/FCS/lost and frame-size dependence.",
   "PHY benchmark dichiarato; non è RFC 2544.",
   "Declared PHY benchmark; it is not RFC 2544.",
   "/api/experiment/traffic", "report only")
_a("ont", "ONT load ramp e latenza", "ONT load ramp and latency", "Traffic", "offered load → RX frames",
   "Varia IPG e misura throughput, loss e budget di latenza.",
   "Varies IPG and measures throughput, loss, and latency budget.",
   "Più IPG deve ridurre il carico; la latenza analogica è xcorr, le altre voci budget.",
   "More IPG must reduce load; analog latency is xcorr, other entries are budgeted.",
   "Non è Y.1564/RFC con timestamp nel payload.",
   "Not Y.1564/RFC with payload timestamps.",
   "/api/experiment/ont", "report only")
_a("disrupt", "Service disruption", "Service disruption", "Traffic", "laser/channel continuity",
   "Interrompe un record e misura il tempo fino al recupero del lock.",
   "Interrupts one record and measures time until lock recovery.",
   "SYNC LOSS deve incrementare e l'outage comparire nel pannello.",
   "SYNC LOSS must increment and outage must appear in the panel.",
   "Azione volutamente distruttiva sul prossimo record, ma reversibile automaticamente.",
   "Intentionally disrupts the next record but recovers automatically.",
   "/api/disrupt", "one-record impairment")
_a("anlt_panel", "Esegui AN + LT", "Run AN + LT", "AN/LT", "partner + TX/RX",
   "Esegue il protocollo; con la checkbox attiva applica i tap negoziati dopo il holdout.",
   "Runs the protocol; when checked, it applies negotiated taps after holdout.",
   "Controlla pagine base, timeline, richieste, both-ready, holdout e flag applied.",
   "Check base pages, timeline, requests, both-ready, holdout, and the applied flag.",
   "Ottica: risultato contestuale; Clause 73 appartiene a KR/CR.",
   "Optics: contextual result; Clause 73 belongs to KR/CR.",
   "/api/experiment/anlt",
   "report; TX FIR/CTLE when ‘apply negotiated taps’ is checked")
_a("local_train", "Training locale", "Local training", "Optimizer", "full TX → RX chain",
   "Ottimizza CTLE e FIR con coordinate descent e verifica su holdout.",
   "Optimizes CTLE and FIR by coordinate descent and verifies on holdout.",
   "Score e BER holdout devono migliorare prima di accettare la configurazione.",
   "Holdout score and BER must improve before accepting configuration.",
   "Non è link training di clause e modifica il banco se accettato.",
   "Not clause link training; changes the bench when accepted.",
   "/api/experiment/train", "CTLE + TX FIR when accepted")
_a("sweep", "Sweep end-to-end", "End-to-end sweep", "Experiment", "selected knob → BER",
   "Esegue 3..15 simulazioni variando un solo parametro.",
   "Runs 3..15 simulations while varying one parameter only.",
   "La curva deve mostrare effective value, BER e punti LINK DOWN.",
   "The curve must show effective value, BER, and LINK DOWN points.",
   "Non modifica la configurazione finale del banco.",
   "Does not change the final bench configuration.",
   "/api/experiment/sweep", "report only")
_a("jtol", "Misura JTOL-lite", "Measure JTOL-lite", "CDR", "TX PJ → link BER",
   "Cerca per bisezione il PJ massimo tollerato a ogni frequenza.",
   "Binary-searches the maximum tolerated PJ at each frequency.",
   "La forma deve riflettere banda e peaking del CDR; i cap vanno marcati.",
   "Shape must reflect CDR bandwidth and peaking; capped points must be marked.",
   "Pattern, durata e maschera non sono quelli di una procedura normativa.",
   "Pattern, duration, and mask are not a normative procedure.",
   "/api/experiment/jtol", "report only")

# ---- workspace e report di conformità (iterazione 45) --------------------
_a("panel_pin", "Fissa nel dock", "Pin to dock", "Workspace", "layout only",
   "Tiene questo strumento visibile in un dock sotto il pannello attivo mentre "
   "si naviga nelle altre tab (uno solo alla volta): Scope + BER live come "
   "su un banco reale, senza tornare alla griglia di 20 grafici.",
   "Keeps this instrument visible in a dock below the active panel while you "
   "browse the other tabs (one at a time): Scope + live BER like on a real "
   "bench, without going back to the 20-plot grid.",
   "Il pannello fissato continua ad aggiornarsi con la stessa cadenza del "
   "pannello attivo; la tab mostra un quadratino ambra.",
   "The pinned panel keeps refreshing at the active panel's cadence; its tab "
   "shows an amber square.",
   "Solo layout: nessuna modifica alla LinkConfig né all'acquisizione.",
   "Layout only: no change to LinkConfig or to the acquisition.",
   "", "workspace layout (localStorage)")
_a("report_json", "Report di conformità (JSON)", "Compliance report (JSON)",
   "Compliance", "same record as the panels",
   "Scarica il report tracciabile: hash della config, seed e profondità del "
   "record, profilo attivo con i campi modificati, ogni contratto di misura "
   "con valore, limite del registro, verdetto del modello e conformità, "
   "invarianti fisici, checkpoint, ultima procedura DR4, versioni di "
   "LabPro/numpy/scipy.",
   "Downloads the traceable report: config hash, record seed and depth, "
   "active profile with modified fields, every measurement contract with "
   "value, registry limit, model verdict and compliance, physics invariants, "
   "checkpoints, last DR4 run, LabPro/numpy/scipy versions.",
   "Apri il file: la sezione contracts deve coincidere con le righe del "
   "pannello; compliance è sempre NOT_ASSESSED.",
   "Open the file: the contracts section must match the panel rows; "
   "compliance is always NOT_ASSESSED.",
   "Il report documenta verdetti del MODELLO contro limiti del registro; non "
   "è un certificato di conformità IEEE/OIF.",
   "The report documents MODEL verdicts against registry limits; it is not an "
   "IEEE/OIF compliance certificate.",
   "/api/report/standards?format=json", "")
_a("report_md", "Report di conformità (Markdown)", "Compliance report (Markdown)",
   "Compliance", "same record as the panels",
   "Stesso contenuto del report JSON reso in Markdown, pronto per una review "
   "o per essere allegato a un commit di laboratorio.",
   "Same content as the JSON report rendered as Markdown, ready for a review "
   "or a lab commit.",
   "Tabella dei contratti con valore, limite, verdetto e conformità; sezioni "
   "invarianti, checkpoint e DR4.",
   "Contracts table with value, limit, verdict and compliance; invariants, "
   "checkpoints and DR4 sections.",
   "Il report documenta verdetti del MODELLO contro limiti del registro; non "
   "è un certificato di conformità IEEE/OIF.",
   "The report documents MODEL verdicts against registry limits; it is not an "
   "IEEE/OIF compliance certificate.",
   "/api/report/standards?format=md", "")
