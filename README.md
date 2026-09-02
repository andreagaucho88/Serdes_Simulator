# SerDes Optical Lab PRO

Laboratorio interattivo bilingue per studiare, misurare e stressare una catena
SerDes elettrica o elettro-ottica fino a 224G-class:

```text
bit / frame → PRBS o Ethernet → FEC TX → mapper NRZ/PAM4 → TX FIR
→ DAC → driver P/N → canale S-parameter → modulatore / fibra
→ PD → TIA / AFE → AGC → CTLE → ADC → CDR → FSE → DFE
→ slicer → FEC RX → BER, GMI, traffico L2 e checkpoint
```

L'interfaccia mantenuta è **Lab PRO** (`labpro/`), un banco custom
Tornado + WebSocket con 32 pannelli. Il motore numerico (`serdes_sim/`) è
indipendente dalla GUI. La vecchia interfaccia Streamlit (`app/`) è
conservata come riferimento, ma è congelata.

> **Perimetro corretto.** Questo è un framework didattico system-level per
> apprendimento, debug e sensitivity analysis. Le procedure e i profili
> IEEE/OIF dichiarano esplicitamente assunzioni e parti non supportate:
> `MODEL PASS/FAIL` non equivale mai a conformità certificata.

## Tour visuale

Le GIF seguenti sono registrazioni riproducibili della UI reale. Ogni cambio di
scheda richiama gli endpoint del banco, non usa immagini o risultati fittizi.

### 1. Workspace, catena, Academy e standard

![Tour del workspace, della catena e delle guide](docs/media/01-workspace-overview.gif)

La catena è navigabile: un click su un blocco apre il pannello corrispondente.
I checkpoint falliti colorano il blocco responsabile; i triangoli ambra
indicano i reference plane acquisiti dagli Scope.

### 2. Sorgente, BERT e trasmettitore

![Tour di BERT, generatore e TX](docs/media/02-source-and-tx.gif)

Il BERT riunisce quattro viste: generatore PPG, analizzatore errori, stress e
controllo. Lo stato è condiviso con FIR, DAC, driver P/N, TX PLL e inserzione
degli errori.

### 3. Canale, COM e ottica

![Tour di canale, COM e ottica](docs/media/03-channel-and-optics.gif)

Il canale può essere analitico o importato da Touchstone; COM, modulatore,
fibra e CMIS-lite espongono i rispettivi piani e limiti.

### 4. Ricevitore e DSP

![Tour di ricevitore, ADC, CDR ed equalizzazione](docs/media/04-rx-and-dsp.gif)

PD, TIA, AGC, CTLE, ADC interleaved, CDR, FSE/DFE e slicer usano lo stesso
record end-to-end: non sono demo scollegate.

### 5. Strumenti live

![Tour di Scope, jitter, spettro, BER e FEC live](docs/media/05-live-instruments.gif)

Scope EYE/WAVE, TIE, spettro, BER e FEC si aggiornano durante l'acquisizione.
I contatori crescono record dopo record e si azzerano quando cambia la fisica.

### 6. Procedure, training e audit

![Tour di procedure L2, JTOL, AN/LT e audit](docs/media/06-procedures-and-audit.gif)

Sweep, JTOL-lite, link training, AN/LT, DR4, instrument alignment, ledger e
audit fisico rendono verificabili sia il risultato sia il percorso che lo ha
prodotto.

## Avvio rapido

### Requisiti

- Python 3.10 o successivo;
- NumPy, SciPy, pandas, Tornado, Plotly, pytest;
- scikit-rf per Touchstone 2.x;
- un browser moderno;
- facoltativi: Playwright e ImageMagick per rigenerare le GIF.

Nell'ambiente di sviluppo del progetto:

```bash
cd simulatore
python -m labpro.server --port 8640
```

Poi aprire [http://localhost:8640](http://localhost:8640). Su macOS è anche
possibile fare doppio click su `avvia_labpro.command`.

Per usare un ambiente Python generico:

```bash
python -m pip install numpy scipy pandas tornado plotly scikit-rf pytest
python -m labpro.server --port 8640
```

Il server ascolta solo in locale per impostazione normale. Interromperlo con
`Ctrl+C`.

## Come si usa il banco

### Barra superiore

- **Preset** carica uno dei sette scenari didattici o uno dei 17 contesti
  IEEE/OIF.
- **RUN / STOP** avvia o sospende l'acquisizione server-side.
- **Record** mostra il numero di acquisizioni accumulate.
- **Seed** rende riproducibile rumore, pattern e stress.
- **IT / EN** cambia lingua per pannelli, tooltip, Academy e messaggi.
- **Viste** carica un workspace tematico: Banco completo, Essenziale,
  Sorgente e TX, Canale e ottica, RX e DSP, Analisi live, BERT e traffico,
  Scope P/N o Academy.
- **Reset** ripristina il preset e invalida gli accumuli dipendenti.

### Workspace a gruppi e schede

La palette a sinistra è ordinata secondo il flusso del segnale. Un click apre
il blocco come scheda; i pannelli singleton già aperti vengono attivati invece
di essere duplicati. Scope è volutamente multiistanza per confrontare fino a
quattro reference plane coerenti.

- trascinare una scheda per riordinarla;
- trascinare un gruppo per cambiare l'ordine delle sezioni;
- usare i pulsanti della card per Academy, reset locale o chiusura;
- usare `←` e `→` da tastiera per cambiare scheda nel gruppo attivo;
- il workspace, la scheda attiva, la lingua e la camera dei grafici sono
  persistiti e ripristinati al reload.

### Contratto comune dei controlli

Ogni slider o selettore modifica il `LinkConfig` condiviso. Il server
incrementa la versione della configurazione, annulla il worker ormai obsoleto,
svuota i contatori che non sarebbero più confrontabili e trasmette il nuovo
stato via WebSocket. Il piccolo hash in basso consente di verificare che due
pannelli stiano osservando la stessa configurazione.

Il pulsante **?** accanto a un controllo spiega:

1. piano fisico interessato;
2. effetto atteso;
3. readout da osservare;
4. test paired suggerito;
5. condizioni di attivazione;
6. limite del modello;
7. campo API effettivamente modificato.

Il **?** nel titolo della card apre invece la scheda Academy del blocco.

## Riferimento completo dei 32 pannelli

### Panoramica

#### 1. Catena del segnale

Mappa il datapath reale dal PPG al decoder. Distingue dominio digitale,
elettrico, ottico e clock; mostra TX PLL, confini E/O e A/D, FEC bypassato o
attivo e marker DCA. I blocchi sono link navigabili. La barra di salute deriva
dai checkpoint del record corrente e localizza failure di driver, PD, TIA,
ADC, CDR, equalizzatori e slicer.

**Esperimento:** aprire uno Scope su `Vdiff`, un altro su `Vctle`, poi
aumentare la loss del canale. I marker si spostano sui due reference plane e
il ledger consente di seguire la degradazione.

#### 2. Academy · guida ai blocchi

Manuale contestuale IT/EN con fisica, formula, osservabili, prova guidata,
limiti e collegamenti tra blocchi. Il selettore segue il pannello di
provenienza; il pulsante “Apri banco” torna direttamente allo strumento.

### Sorgente e trasmettitore

#### 3. BERT · generatore TX e analizzatore errori

Quattro sottoviste mutuamente esclusive:

- **Generator/PPG:** PRBS 7/9/11/13/15/23/31, SSPRQ, custom hex, clock ed
  Ethernet; NRZ o PAM4 Gray/binario; output TX e pattern preview.
- **Error detector:** BER/SER, lane MSB/LSB, pre/post-FEC, error insertion
  singola o burst e destinazione random/MSB/LSB/simbolo RS.
- **Stress:** RJ, PJ, DCD, BUJ, SSC e rumore differenziale sul time base o
  sull'uscita reale del TX.
- **Control:** start/stop gated, target BER, intervallo di confidenza,
  lock del pattern e riepilogo di sincronizzazione.

L'ED è un checker digitale sullo stesso RX fisico, non un secondo ricevitore
analogico.

#### 4. TX · FIR, DAC e driver

Controlla tap FFE, risoluzione e full-scale del DAC, bandwidth, gain e clipping
del driver, skew/gain mismatch P/N, offset e rumore common-mode, drive
differenziale o single-ended e filtri causali. Visualizza waveform, swing,
headroom, clipping e risposta del percorso TX.

**Esperimento:** introdurre skew P/N e confrontare nello Scope le quick-set
P, N, differenziale e common-mode.

### Canale e ottica

#### 5. Canale elettrico

Il modello analitico espone insertion loss a Nyquist, return loss, ritardo,
group-delay ripple, eco, NEXT e FEXT. In alternativa il file picker porta nel
datapath un Touchstone:

- Touchstone 1.x o 2.x;
- S2P single-ended;
- S4P convertito in mixed-mode con coppie porte `13_24` o `12_34`;
- formati RI, MA o DB;
- impedenza di riferimento reale e uniforme.

Sono accettati `.s2p`, `.s4p`, `.ts` e `.txt`. Se il file è invalido,
non monotono, non finito o con Z0 incompatibili viene rifiutato con un errore
esplicito. Il pulsante **Torna al modello** disattiva l'S-parameter senza
cancellare gli altri controlli.

#### 6. COM · IEEE 802.3 Annex 93A

Calcola un proxy dichiarato di Channel Operating Margin sulla catena elettrica
misurata, separando segnale, ISI, crosstalk e rumore. Riporta response/cursor,
denominatore di rumore e margine. Serve a capire la metodologia e confrontare
configurazioni, non sostituisce foglio COM normativo, package ufficiale o
correlazione di compliance.

#### 7. Ottica · modulatore e fibra

Seleziona CW-DFB+MZM, DFB-EML, DFB-DML o VCSEL/MMF. Espone potenza e linewidth
laser, Vπ/bias o extinction ratio, chirp, bandwidth e insertion loss;
lunghezza/tipo fibra, loss, dispersione β2 e slope/β3, PMD, Kerr e modal
bandwidth. Il cambio di architettura sincronizza laser, modulatore, fibra e
lunghezza d'onda per evitare combinazioni fisicamente impossibili.

### Ricevitore e DSP

#### 8. RX front-end · PD, TIA e AGC

Vista aggregata del budget analogico: potenza al PD, corrente, rumore,
transimpedenza, gain automatico, clipping e headroom. È il punto più rapido
per capire se il link è limitato da sensibilità, overload o ampiezza ADC.

#### 9. Photodiode · PD

Mostra responsivity, dark current, bandwidth, saturazione e RIN. Il rumore
shot usa la corrente reale, mentre PVT/temperatura modifica dark current e
banda secondo le assunzioni dichiarate. Readout: potenza ricevuta, corrente,
noise density e saturation margin.

#### 10. TIA / electrical AFE

Controlla transimpedenza, input-noise density, VGA range, bandwidth, headroom
e clip. Per un link copper rappresenta l'AFE elettrico; per un link optical
riceve la corrente del PD. La risposta impulsiva e il budget di rumore
permettono di separare limite di banda e limite di sensibilità.

#### 11. AGC · gain e headroom

Regola target RMS, gain minimo/massimo e mostra gain scelto, residuo rispetto
al target, headroom e saturazione. Il guadagno applicato entra davvero nel
record inviato a CTLE e ADC.

#### 12. CTLE configurabile

Implementa topologie 1Z/1P, 1Z/2P e 2Z/3P, oppure tuple esplicite fino a
quattro zeri e cinque poli, con gain DC. Bode, group delay, peaking e noise
enhancement sono calcolati dalla stessa funzione di trasferimento usata nel
datapath. Il grafico pulse/cursor mostra il compromesso ISI-rumore.

#### 13. ADC interleaved

Configura sample/symbol, bit, full-scale, fase, jitter, interleave, rank di
track-and-hold, bandwidth front-end, mismatch di gain/offset/skew/banda,
rumore e calibrazione off/foreground/background. Readout: occupazione,
clipping, ENOB/SNDR proxy e residui dipendenti da PVT.

#### 14. Timing · CDR

Confronta Gardner, Mueller-Müller e oracle dichiarato. Il loop PI di secondo
ordine usa banda normalizzata, damping e offset clock RX in ppm. Il pannello
mostra lock, pattern lock, fase, frequency error, TIE e andamento del loop.
Senza lock il link è `DOWN` e le metriche downstream non vengono inventate.

#### 15. RX FFE (FSE) + DFE

Equalizzatore fractionally spaced T/2 seguito da DFE. Controlla numero di tap
e finestra di training; mostra coefficienti, response/cursor, MSE e confronto
prima/dopo. I checkpoint verificano che FSE migliori e DFE non degradi.

#### 16. Decisioni · slicer

Visualizza istogrammi e soglie NRZ/PAM4, simboli stimati, LLR, confusion
matrix, BER/SER, GMI e stato link. È il confine tra DSP analogico/digitale e
FEC: qui si può distinguere un occhio brutto ma decodificabile da un link
realmente fuori lock.

### Strumenti e analisi live

#### 17. Scope · DCA

Strumento multiistanza e multicanale coerente. Ogni card può acquisire fino a
quattro nodi dello stesso record: driver ideale, P, N, differenziale,
common-mode, canale, potenza al modulatore, potenza al PD, TIA o CTLE.

- **EYE:** persistenza, overlay, height/width, Q, RLM e, sui nodi ottici,
  OMA/ER.
- **WAVE:** waveform nel tempo con canali sincronizzati.
- quick-set P/N/Diff/CM;
- camera Plotly persistente;
- marker automatici nella Catena del segnale.

#### 18. Jitter · TIE

Analizza la time-interval error del record selezionato: trend, istogramma,
spettro, RJ/PJ/DCD e bathtub empirica. Il seed rende confrontabili due stress;
la selezione del piano è coerente con il CDR e con il nodo osservato.

#### 19. Spectrum analyzer

PSD/frequency response sul nodo scelto, con asse e span controllabili. Serve a
vedere roll-off, notch da dispersione, peaking CTLE, spur PJ/SSC e bandwidth
del front-end; non è un FFT decorativa separata dal record.

#### 20. BER live

Accumula bit ed errori tra record compatibili, riportando BER, limiti di
confidenza, target e stato lock. Cambiando configurazione l'accumulo viene
invalidato; STOP congela il totale senza perdere il contesto.

#### 21. FEC live

KP4 RS(544,514) e KR4 RS(528,514) sono encoder/decoder algebrici nel percorso,
non solo formule what-if. Il pannello accumula codeword clean, corrette,
uncorrectable e miscorrected, pre/post-FEC BER e interleave 1/2/4. In bypass
separa chiaramente ciò che non è stato decodificato.

#### 22. Ethernet · Traffic L2

Genera frame Ethernet reali con PCS scrambler Clause 49
`x^58 + x^39 + 1`, dimensione frame, IPG e 1–4 stream. Offre benchmark per
frame size e test ONT-style con load ramp, latency budget per blocco e service
disruption derivata dal lock CDR. È intenzionalmente **L2-lite** e non dichiara
RFC 2544.

#### 23. Module · CMIS-lite

Rappresenta un modulo coerente con l'architettura ottica scelta: application
advertisement, datapath state, laser/Tx disable, Rx power, temperatura e
allarmi principali. È un modello didattico del control plane, non una
implementazione completa della memory map CMIS.

#### 24. Sweep parametrico

Esegue uno sweep end-to-end di un campo ammesso e restituisce BER, GMI, eye,
lock e punti `LINK DOWN`. Il job è versionato e cancellabile: se la
configurazione cambia, un risultato vecchio non può sovrascrivere il banco.

#### 25. JTOL-lite

Varia frequenza e ampiezza del periodic jitter per stimare la tolleranza del
CDR. Evidenzia jitter peaking vicino alla banda del loop e limiti imposti dalla
durata del record. È una procedura educativa, non la maschera normativa di una
clause.

#### 26. Link training

Coordinate descent sui tap TX con metrica misurata dal ricevitore. Mostra ogni
iterazione, coefficienti, miglioramento e condizione di arresto; non modifica
silenziosamente la configurazione finché non si applica il risultato.

#### 27. AN/LT · Clause 73

Modella base page, priority resolution verso l'HCD, timer di Table 73-7 e
handshake Clause 72/136: preset, increment/decrement dei coefficienti
`c(-1)` e `c(+1)`, `updated`, `at_limit` e `receiver_ready`. La
metrica di training proviene dal banco corrente.

#### 28. Standard IEEE/OIF

Catalogo di 17 profili che specifica standard/clause, reference plane/reach,
mezzo, modulazione e FEC. Ogni scheda espone:

- cosa è pubblicato;
- quali numeri sono rappresentativi;
- quale claim è supportato;
- cosa resta `unsupported` o `NOT ASSESSED`.

Caricare un profilo configura l'intero banco, non solo l'etichetta.

#### 29. DR4 · procedura fisica

Workflow on-demand riproducibile sul periodo SSPRQ completo di 65.535 simboli,
ai due estremi pubblici di dispersione e con DGD stressato. TDECQ usa finestre
0,45/0,55 UI, FFE 5 tap normalizzato e `Ceq` integrato sul rumore sagomato
BT4. Gli stessi record attraversano PD/TIA/ADC/CDR/DSP. Reflection,
polarization stress, uncertainty tracciabile e correlazione con golden
instrument restano fuori perimetro: conformità = `NOT ASSESSED`.

#### 30. Instrument alignment

Mappa concetti e funzioni del banco verso DCA, BERT e traffic generator reali,
indicando cosa è implementato e cosa no. I collegamenti sono riferimenti per
imparare la terminologia, non endorsement né emulazione proprietaria.

#### 31. Checkpoint & ledger

Tabella dei controlli automatici e dei reference plane prodotti dal motore:
dimensioni, unità, salute, causalità, miglioramento equalizzatori, occupancy,
lock, FEC e metriche. È il primo posto da consultare quando un risultato
sembra incoerente.

#### 32. Audit fisico · invarianti

Esegue paired checks e invarianti: aumentare rumore non deve migliorare la
qualità in modo sistematico, cambiare loss deve propagarsi, disabilitare TX
deve abbattere il link, FEC e CDR devono rispettare le proprie condizioni.
I risultati distinguono `PASS`, `FAIL` e non valutabile.

## Preset didattici

| Preset | Uso consigliato |
| --- | --- |
| 112G didattico — 2 km @1550 nm | baseline del corso, 56 GBd PAM4 in C-band |
| Back-to-back | riferimento senza penalty di fibra |
| Stress 10 km — fading CD | notch IM/DD e limite dell'equalizzazione |
| 100GBASE-LR1 context | O-band, 53.125 GBd, 10 km |
| Canale elettrico severo | CTLE/FSE/DFE contro 20 dB a Nyquist |
| RX rumoroso | sensitivity e noise budget del TIA |
| Link con margine — FEC al lavoro | osservare codeword KP4 corrette |

I 17 profili standard aggiungono contesti 10G/25G/50G/100G/400G/800G,
CEI-56G/112G/224G e P802.3dj. Non sono preset di certificazione.

## Persistenza e coerenza

- `LinkConfig` è una dataclass immutabile con 123 campi serializzabili.
- Il server salva configurazione, preset e stato RUN nella directory utente
  del laboratorio.
- Il browser salva layout, lingua, tab attivo e camera localmente.
- Ogni risposta include versione/hash della configurazione e identità record.
- I worker lunghi sono associati alla versione che li ha avviati.
- Una disconnessione WebSocket o un rapido reload viene assorbito senza lasciare
  future asincrone non gestite.

Per una sessione pulita usare Reset dalla UI. Prima di cancellare manualmente
file di stato, fermare il server e conservarne una copia se la configurazione
è importante.

## API locale

La UI usa la stessa API disponibile per ispezione e automazione locale:

| Endpoint | Metodo | Scopo |
| --- | --- | --- |
| `/api/state` | GET | configurazione, preset, lingua e stato RUN |
| `/api/config` | POST | patch atomica dei campi di `LinkConfig` |
| `/api/preset` | POST | carica preset o profilo standard |
| `/api/run` | POST | start/stop acquisizione |
| `/api/panel/<name>` | GET | payload del pannello richiesto |
| `/api/experiment/<name>` | POST | sweep, training, JTOL e procedure |
| `/ws` | WebSocket | stato, invalidazioni e progress live |

Esempio:

```bash
curl -s http://localhost:8640/api/state
curl -s -X POST http://localhost:8640/api/config \
  -H 'Content-Type: application/json' \
  -d '{"channel_il_nyquist_db": 16.0, "fec_mode": "kp4"}'
```

L'API è locale e non include autenticazione, multi-tenancy o garanzie di
stabilità da prodotto pubblico.

## Uso diretto del motore Python

```python
from dataclasses import replace

from serdes_sim import LinkConfig, simulate, sweep

cfg = replace(
    LinkConfig(),
    link_medium="copper",
    channel_il_nyquist_db=16.0,
    fec_mode="kp4",
)

result = simulate(cfg, seed=7, depth="full")
print(result.metrics)
print(result.checkpoints)

curve = sweep(
    cfg,
    field="channel_il_nyquist_db",
    values=[8.0, 12.0, 16.0, 20.0],
    seed=7,
)
```

Il risultato contiene record ai reference plane, metriche, metadati, ledger e
checkpoint. Per il contratto esatto usare i type e i test del repository.

## Struttura del repository

```text
simulatore/
├── labpro/                  server Tornado e frontend Lab PRO
│   ├── server.py
│   └── static/              HTML, CSS, JavaScript e Plotly locale
├── serdes_sim/              motore fisico indipendente dalla GUI
│   ├── blocks/              TX, channel, optics, RX, ADC, DSP, FEC, metriche
│   ├── engine.py            simulate() e sweep()
│   ├── procedures.py        DR4 e procedure versionate
│   ├── config.py            LinkConfig, preset e profili standard
│   ├── ami.py               loader IBIS-AMI e modello demo
│   └── selftest.py          smoke test end-to-end
├── tests/                   regressione numerica, API e contratti UI
├── tools/
│   └── capture_readme_gifs.py
├── docs/media/              sei tour GIF della UI reale
├── app/                     Streamlit legacy, congelata
├── HANDOFF_CODEX.md         registro tecnico delle iterazioni
└── PROMPT_CODEX.md          stato operativo per manutenzione
```

## Verifica e quality gate

Eseguire dalla directory `simulatore`:

```bash
python -m pytest tests -q
python -m serdes_sim.selftest
node --check labpro/static/app.js
python -m compileall -q serdes_sim labpro
git diff --check
```

Stato validato dell'iterazione 36: **374/374 test PASS**, selftest fisico
**13/13**, sintassi JavaScript, compileall e controllo whitespace puliti.

L'audit browser aggiuntivo attraversa tutti i 32 pannelli in IT e EN, verifica
singleton/tab attivo, quattro viste BERT, EYE/WAVE, propagazione dei controlli,
upload Touchstone 2.x e reload rapidi. I test numerici preservano anche la
baseline del notebook v7.

## Rigenerare le GIF

Con il server in ascolto sulla porta 8640:

```bash
python tools/capture_readme_gifs.py --base http://127.0.0.1:8640
```

Lo script:

1. usa Playwright sul browser disponibile;
2. salva configurazione e stato RUN correnti, usando un profilo browser isolato;
3. visita realmente le schede e acquisisce i frame a 1440×900;
4. costruisce sei GIF ottimizzate a 1000×625 con ImageMagick;
5. ripristina lo stato iniziale anche in caso di errore.

Opzioni:

```bash
python tools/capture_readme_gifs.py --help
```

Non modificare manualmente le GIF senza aggiornare anche lo script: il tour
deve restare riproducibile e fedele alla versione della UI.

## Risoluzione dei problemi

### La pagina non si apre

Verificare che la porta sia libera e che il processo sia attivo:

```bash
curl -s http://localhost:8640/api/state
```

Se la porta 8640 è occupata, avviare con un'altra porta e usare lo stesso URL
nel browser.

### Un pannello mostra dati vecchi

Controllare hash/config version nel footer, attendere la fine del record e
ricaricare la pagina. Un cambio di parametro invalida intenzionalmente
l'accumulo. Se il problema persiste, STOP → Reset → RUN.

### Il link è DOWN

Aprire nell'ordine Catena, Checkpoint & ledger, Timing/CDR e Decisioni.
Verificare output TX, occupancy ADC, clipping, pattern lock e lock CDR. BER,
GMI o post-FEC assenti durante `DOWN` sono comportamento corretto.

### Un Touchstone non viene accettato

Verificare estensione/numero porte, frequenze crescenti, formato RI/MA/DB,
reference impedance uniforme e mappatura delle coppie S4P. Touchstone 2.x usa
scikit-rf: controllare che sia installato nello stesso interprete del server.

### Le GIF non si rigenerano

Installare Playwright e ImageMagick, oppure rendere disponibile un Chromium
Playwright nella cache standard. Lo script stampa un errore esplicito se non
trova `magick`.

## Limiti noti

- non è uno strumento di conformità né sostituisce un golden instrument;
- il modello è system-level e non transistor/layout-level;
- COM e JTOL sono proxy educativi con perimetro dichiarato;
- CMIS e traffic test sono subset funzionali;
- la procedura DR4 non include uncertainty tracciabile, reflection e tutti gli
  stress di polarizzazione;
- IBIS-AMI dipende dal contratto e dalla libreria del vendor;
- la UI Streamlit è legacy e non riceve nuove funzioni.

Roadmap, decisioni e cronologia delle verifiche sono in
[`HANDOFF_CODEX.md`](HANDOFF_CODEX.md).

## Licenza e uso

Usare secondo la licenza e le policy del repository. Per decisioni di
progetto, procurement o conformità, correlare sempre il modello con specifica
applicabile, dati del componente e misura tracciabile.
