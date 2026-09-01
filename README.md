# SerDes Optical Lab — laboratorio didattico della catena elettro-ottica

Laboratorio interattivo 112G-class PAM4: il segnale dal bit al BER, senza salti.

> **Stato: laboratorio didattico avanzato con proxy dichiarati.**
> Il **CDR è nel datapath** (loop PI 2° ordine + NCO, Gardner o Mueller-Müller,
> pattern lock stile BERT; senza lock il link è DOWN e le metriche non
> esistono; "oracle" resta come modalità idealizzata dichiarata). Il **FEC può
> essere nel percorso** (encoder TX → decoder RX, KP4/KR4 reali, con categoria
> miscorrected) oppure fare analisi what-if del pattern. Le soglie da modello
> sono etichettate come tali: NON è uno strumento di conformità IEEE/OIF.
> Roadmap e limiti in `HANDOFF_CODEX.md`.

**bit → NRZ/PAM4 → TX FFE → DAC/driver P/N → canale →
MZM/EML/DML/VCSEL → SMF/MMF → PD/TIA/AGC/CTLE → ADC → CDR →
FSE/DFE → LLR, BER, GMI/FEC/L2.**

La fisica è quella (verificata) del notebook v7 del corso
(`codice/build_serdes_course_framework_v7.py`), riorganizzata in un motore
modulare (`serdes_sim/`). L'interfaccia attiva è **Lab PRO** (`labpro/`);
la GUI Streamlit (`app/`) è legacy congelata.

## Due interfacce

### Lab PRO (consigliata) — banco a pannelli con acquisizione continua

Doppio click su `avvia_labpro.command`, oppure:

```bash
cd simulatore
python -m labpro.server --port 8640
# → http://localhost:8640
```

Frontend custom (Tornado + WebSocket + canvas/plotly locale, niente CDN):

- **pannelli paralleli**: apri, chiudi, ridimensiona e riordina le schede
  (Scope DCA, Spettro, CTLE, FEC live, BER live, catena, ogni blocco…) una
  accanto all'altra — il layout si salva da solo;
- **acquisizione continua vera**: un motore server-side simula record dopo
  record (nuovo rumore a ogni record) e i contatori si riempiono nel tempo —
  bit, errori, IC della BER che si stringe, **frame FEC clean/corretti/persi
  che si accumulano** come su un analyzer reale;
- **FEC nel percorso**: encoder RS prima del mapper e decoder dopo lo slicer
  (KP4 RS(544,514) o KR4 RS(528,514), entrambi codec algebrici reali);
- **pannello CTLE dedicato**: zero/poli/gain DC, Bode + group delay, peaking
  e noise enhancement; topologia realmente variabile (1..4 zeri, 1..5 poli)
  con preset 1Z/1P, 1Z/2P e 2Z/3P;
- **DCA multicanale coerente**: fino a quattro eye dallo stesso record,
  quick-set P/N/differenziale/common-mode, eye a persistenza con overlay,
  height/width per occhio, Q, RLM, OMA/ER sui nodi ottici; TIE live con seed,
  trend, spettro e bathtub empirica;
- **BERT + traffic analyzer**: PPG/ED con stress RJ/PJ/DCD/rumore
  differenziale, BER/SER MSB-LSB, error insertion singola o burst, gating
  Start/Stop con BER gated e confidenza sul target (stile MP1900A); frame
  Ethernet L2 reali su **PCS scrambler Clause 49** (x⁵⁸+x³⁹+1), benchmark
  frame size e **test ONT-style** (load ramp via IPG, latency budget per
  blocco, service disruption dal lock CDR) — dichiarato non RFC 2544;
- **AN/LT**: Auto-Negotiation Clause 73 a livello protocollo (base page,
  priority resolution → HCD, timer di Table 73-7) e Link Training con
  l'handshake di Clause 72/136 (preset, inc/dec c(-1)/c(+1),
  updated/at_limit, receiver ready) su metrica misurata dal banco;
- **ottica configurabile e coerente**: CW-DFB+MZM, DFB-EML, DFB-DML e
  VCSEL/MMF; CD beta2, slope/beta3, linewidth, PMD, Kerr e modal bandwidth;
- **pannelli PD/TIA/AGC e pulse response**: waveform live, noise/ENBW,
  overload/headroom, impulso e cursor prima/dopo CTLE;
- **Academy IT/EN**: schede collegate a ogni blocco con fisica, formula,
  osservabili, esperimento e limite; catalogo di 17 contesti IEEE/OIF con
  manifest `standard / assumption / unsupported`;
- ogni modifica di parametro azzera l'accumulo e si propaga a tutti i
  pannelli via WebSocket (config versionata, hash in basso a destra).

### [LEGACY] Interfaccia Streamlit — congelata, non più sviluppata

Doppio click su `avvia_simulatore.command`, oppure:

L'interfaccia attiva e mantenuta è **Lab PRO** (sopra). La UI Streamlit
resta nel repo come riferimento didattico (teoria per stadio, esercizi
guidati) ma non riceve nuove funzionalità:

```bash
python -m streamlit run app/main.py  # legacy
```

Dipendenze (già presenti in anaconda3): numpy, scipy, pandas, streamlit ≥1.45,
plotly.

## Struttura

- `serdes_sim/` — motore fisico puro (nessuna dipendenza dalla GUI):
  - `config.py`: `LinkConfig` (immutabile), preset didattici e 17 profili
    IEEE/OIF dichiarati come contesti, non test di compliance;
  - `blocks/`: stimolo, TX, canale, ottica, ricevitore, ADC, DSP, metriche,
    **FEC RS(544,514) reale** su GF(2¹⁰);
  - `engine.py`: `simulate(cfg, seed, depth)` e `sweep(...)`;
  - `procedures.py`: procedure fisiche versionate sopra il datapath; DR4 v1
    usa il periodo SSPRQ completo e due estremi del canale di dispersione;
  - `ami.py`: loader IBIS-AMI via ctypes + modello demo compilabile;
  - `selftest.py`: `python -m serdes_sim.selftest` verifica tutta la catena.
- `app/` — GUI Streamlit, 21 pagine: panoramica, catena completa, 11 stadi
  (inclusa l'analisi FEC), **Scope live stile DCA**, **Spectrum analyzer**,
  eye lungo la catena, misure & definizioni, esperimenti, standard IEEE/OIF,
  IBIS-AMI, note. Lo schema della catena è **cliccabile** (ogni blocco porta
  alla sua pagina) e la configurazione è persistita su disco fra i reload.
- `tests/` — suite pytest (regressione numerica della baseline inclusa):
  `python -m pytest tests -q`.

Funzionalità principali:

- **Stimolo**: PRBS 7/9/11/13/15/23/31; NRZ, PAM4 Gray, PAM4 binario.
- **Canale misurato**: un Touchstone S2P caricato può sostituire il modello
  analitico nel percorso principale (pagina Canale elettrico).
- **FEC RS(544,514)**: codec algebrico reale (Berlekamp-Massey + Chien),
  banco di iniezione errori, analisi iid/burst del pattern del link.
- **Scope live (DCA)**: eye a persistenza di fosforo 60 fps con tracce reali,
  acquisizione continua, pannello misure (Vpp/OMA/ER/BER/SNR/Q) e analisi FEC
  con verdetto — riflette ogni modifica di configurazione.
- **SNR e definizioni**: SNR al slicer, Q per occhio, OMA/ER proxy; pagina
  "Misure & definizioni" con definizione operativa e formula di ogni numero.
- **Standard IEEE 802.3 / OIF-CEI**: mappa delle corsie 10G→200G/lane con la
  famiglia più vicina alla tua configurazione e il margine sulla soglia
  pre-FEC (modello binomiale dichiarato).
- **Procedura DR4 fisica end-to-end**: run on-demand e riproducibile su tutti
  i 65.535 simboli SSPRQ, ai due estremi pubblici di dispersione e con DGD
  stressato; il TDECQ usa finestre 0,45/0,55 UI, FFE 5 tap normalizzato e
  `Ceq` integrato sul rumore sagomato dal BT4. Gli stessi record chiudono
  PD/TIA/ADC/CDR/DSP e riportano lock/BER/checkpoint fisici.
- **Filtri causali** opzionali (fase reale) su DAC/driver/MZM/PD/TIA.
- **IBIS-AMI**: banco che carica vere librerie AMI vendor
  (AMI_Init/AMI_GetWave) e un modello demo in C compilabile al volo.
- Pacchetti di supporto installati: scikit-rf, serdespy (riferimento).

## Uso didattico (Lab PRO)

1. Scegli un **preset** e premi **RUN**: l'acquisizione continua parte e i
   contatori (bit, BER±IC, frame FEC) si riempiono nel tempo.
2. La **catena** in alto è cliccabile e mostra la salute dei blocchi: un
   checkpoint FAIL accende in rosso il blocco responsabile.
3. Ogni pannello ha le sue manopole (con **↺** per tornare ai default): ogni
   modifica azzera l'accumulo e si propaga a tutti i pannelli via WebSocket.
4. **Sweep parametrico** e **JTOL-lite** trasformano una manopola in una
   curva end-to-end (compresi i punti LINK DOWN).
5. Le **viste** nel topbar caricano layout ordinati per flusso del segnale.
6. Ogni manopola e ogni azione importante hanno un pulsante **?**: la scheda
   bilingue dichiara piano fisico, cosa osservare, verifica paired, condizioni
   di attivazione, limiti, API e stato modificato. Il **?** della card apre la
   relativa scheda Academy; **IT/EN** cambia lingua e resta persistente.
7. Il pannello **DR4 · procedura fisica** esegue il workflow versionato senza
   modificare la configurazione del banco e separa `MODEL PASS/FAIL` da
   `NOT ASSESSED` per la conformità.

> Confine di validità: framework system-level per apprendimento e sensitivity
> analysis. La procedura DR4 è completa nel perimetro del modello pubblico,
> ma reflection/polarization stress, incertezza strumentale tracciabile e
> correlazione con un golden instrument sono ancora mancanti: la conformità
> IEEE resta quindi **NOT ASSESSED**, mai inferita dal verdetto del modello.

## Manutenzione

- La fonte di verità della fisica resta il builder v7: non modificare i modelli
  senza confronto.
- Stato del progetto: `HANDOFF_CODEX.md`; review severa e roadmap pronta per
  il prossimo agente: `HANDOFF_CLAUDE.md`.
