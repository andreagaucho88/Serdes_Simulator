"""Catalogo didattico bilingue condiviso dalla UI LabPro.

Ogni scheda separa sempre: l'idea fisica, la spiegazione approfondita, i
NUMERI tipici del mondo reale (per calibrare l'intuizione), cosa misurare
sul banco, un esperimento concreto coi knob, e il confine del modello.
Nessuna scheda promette conformità normativa.
"""

from __future__ import annotations


def _topic(title_it, title_en, block, idea_it, idea_en, formula,
           observe_it, observe_en, experiment_it, experiment_en, limits_it,
           limits_en, course, deep_it="", deep_en="", numbers=(),
           actions=(), panel=None):
    return {
        "id": block,
        "title": {"it": title_it, "en": title_en},
        "idea": {"it": idea_it, "en": idea_en},
        "deep": {"it": deep_it, "en": deep_en},
        "formula": formula,
        "observe": {"it": observe_it, "en": observe_en},
        "experiment": {"it": experiment_it, "en": experiment_en},
        "limits": {"it": limits_it, "en": limits_en},
        "numbers": [{"l": n[0], "v": n[1]} for n in numbers],
        "actions": [{"do": {"it": a[0], "en": a[1]},
                     "see": {"it": a[2], "en": a[3]}} for a in actions],
        "panel": panel or block,
        "course": course,
    }


TOPICS = [
    _topic(
        "PPG, PRBS e mapper PAM4", "PPG, PRBS and the PAM4 mapper", "stimulus",
        "Il PPG genera il flusso di bit; il mapper lo trasforma in livelli: 1 bit/UI (NRZ) o 2 bit/UI (PAM4 Gray).",
        "The PPG generates the bit stream; the mapper turns it into levels: 1 bit/UI (NRZ) or 2 bits/UI (PAM4 Gray).",
        "R_b = R_s·log₂(M) ;  PRBS-n: periodo 2ⁿ−1",
        "Occupazione dei livelli (¼ ciascuno su PRBS lunga), matrice delle transizioni, spettro sinc² dello stimolo.",
        "Level occupancy (¼ each on a long PRBS), transition matrix, sinc² stimulus spectrum.",
        "Passa da PRBS13 a clock2: lo spettro collassa in una riga a f_baud/2 e il CDR ha transizioni a ogni UI. Poi prova il vettore SSPRQ e guarda il DCA.",
        "Switch from PRBS13 to clock2: the spectrum collapses to one line at f_baud/2 and the CDR gets a transition every UI. Then try the SSPRQ vector on the DCA.",
        "SSPRQ riproduce bit per bit il vettore machine-readable pubblico di Clause 120; questa esattezza del pattern, da sola, non rende normativa la misura DCA/TDECQ.",
        "SSPRQ reproduces the public Clause 120 machine-readable vector bit for bit; pattern exactness alone does not make the DCA/TDECQ measurement normative.",
        "ECEN 720",
        deep_it=("PAM4 dimezza il baud rate a parità di bit rate — 112 Gb/s in 56 GBd — e questo vale ~10 dB di "
                 "loss di canale in meno a Nyquist. Il prezzo: 3 occhi alti ⅓, cioè ~9.5 dB di SNR in meno, più la "
                 "sensibilità alla linearità (RLM). Il mapping Gray fa sì che un errore fra livelli adiacenti costi "
                 "1 solo bit: è il motivo per cui BER ≈ SER/2 in PAM4 Gray. La PRBS serve perché l'ED del BERT "
                 "può rigenerarla e confrontarla bit-a-bit senza un canale di riferimento."),
        deep_en=("PAM4 halves the baud rate at the same bit rate — 112 Gb/s in 56 GBd — worth ~10 dB less channel "
                 "loss at Nyquist. The price: 3 eyes at ⅓ height, i.e. ~9.5 dB less SNR, plus linearity (RLM) "
                 "sensitivity. Gray mapping makes an adjacent-level error cost exactly 1 bit: that is why "
                 "BER ≈ SER/2 in Gray PAM4. PRBS exists so a BERT ED can regenerate it and compare bit-by-bit "
                 "with no reference channel."),
        numbers=[("PAM4 vs NRZ SNR", "−9.5 dB (stessi livelli di picco)"),
                 ("PRBS13Q period", "8191 simboli (clause 120D)"),
                 ("PRBS31 period", "2³¹−1 ≈ 2.1e9 bit"),
                 ("RLM minimo tipico", "≥ 0.95 (802.3 TX specs)"),
                 ("Gray: bit/errore simbolo", "1 (adiacente)")],
        actions=[("Imposta modulation = NRZ", "Set modulation = NRZ",
                  "BER crolla: occhio unico alto 2, +9.5 dB di SNR", "BER collapses: one eye of height 2, +9.5 dB SNR"),
                 ("pattern = clock2 sul DCA", "pattern = clock2 on the DCA",
                  "niente ISI pattern-dependent: il 'eye' diventa una sinusoide a f_baud/2", "no pattern-dependent ISI: the 'eye' becomes a tone at f_baud/2")],
        panel="stimulus"),

    _topic(
        "FEC RS e reference plane", "RS FEC and the reference plane", "fec",
        "Il decoder RS corregge SIMBOLI da 10 bit, non bit sparsi: 15 simboli per codeword (KP4). Il burst del DFE 'costa' meno del previsto perché più bit errati cadono nello stesso simbolo.",
        "The RS decoder corrects 10-bit SYMBOLS, not scattered bits: 15 symbols per codeword (KP4). DFE bursts 'cost' less than expected because several bad bits fall in one symbol.",
        "RS(544,514), t=15 ;  FER_iid = P[X > t],  X~Bin(544, p_sym)",
        "Istogramma errori-per-frame accumulato, frame clean/corretti/persi/miscorretti, BER pre vs post-FEC.",
        "Accumulated errors-per-frame histogram, clean/corrected/lost/miscorrected frames, pre vs post-FEC BER.",
        "Porta la BER pre-FEC vicino a 2.4e-4 (alza IL canale) e guarda l'istogramma avvicinarsi a t=15: è il 'FEC cliff'.",
        "Push pre-FEC BER toward 2.4e-4 (raise channel IL) and watch the histogram approach t=15: the FEC cliff.",
        "Non ci sono PCS multilane, alignment marker e interleaving di clause; il gearbox è ideale.",
        "No multilane PCS, alignment markers, or clause interleaving; the gearbox is ideal.",
        "ECEN 720",
        deep_it=("Tutta l'industria 100G+/lane vive di questo compromesso: si accetta una BER 'pessima' (1e-4!) dal "
                 "canale e la si ripulisce col RS(544,514) — 5.8% di overhead per 8 ordini di grandezza di BER. "
                 "La soglia pre-FEC 2.4e-4 di KP4 è il numero singolo più importante del settore: sopra, la "
                 "probabilità di >15 simboli errati per codeword esplode (il 'cliff'). La categoria 'miscorretto' "
                 "esiste perché oltre t il decoder può CREDERE di aver corretto e consegnare dati sbagliati "
                 "con probabilità ~1/t! — per questo si monitora la FERC, non solo la BER."),
        deep_en=("The whole 100G+/lane industry lives on this trade: accept 'terrible' channel BER (1e-4!) and clean "
                 "it with RS(544,514) — 5.8% overhead buys ~8 orders of magnitude of BER. KP4's 2.4e-4 pre-FEC "
                 "threshold is the single most important number in the field: above it, the probability of >15 "
                 "symbol errors per codeword explodes (the cliff). 'Miscorrected' exists because beyond t the "
                 "decoder may BELIEVE it corrected and deliver wrong data with probability ~1/t! — which is why "
                 "you monitor FERC, not just BER."),
        numbers=[("KP4 overhead", "544/514 = 5.84%"),
                 ("soglia pre-FEC KP4", "≈ 2.4e-4 (per 1e-13 post)"),
                 ("KR4 t / soglia", "t=7 · ≈ 2e-5"),
                 ("latency FEC (store)", "≈ 51 ns/lato @ 106 Gb/s"),
                 ("simbolo RS", "10 bit = 5 simboli PAM4")],
        actions=[("Inietta 30 bit burst dal BERT", "Inject a 30-bit burst from the BERT",
                  "meno frame colpiti che con 30 bit sparsi: il RS è symbol-based", "fewer frames hit than with 30 scattered bits: RS is symbol-based"),
                 ("fec_mode = kr4 su link marginale", "fec_mode = kr4 on a marginal link",
                  "frame persi: t=7 non regge dove KP4 (t=15) sì", "lost frames: t=7 fails where KP4 (t=15) holds")],
        panel="feclive"),

    _topic(
        "Serializer, PLL e jitter TX", "Serializer, PLL and TX jitter", "serpll",
        "Il PLL del serializer È il clock trasmesso: RJ (gaussiano, illimitato), PJ/SJ (sinusoidale), DCD, BUJ e SSC si sommano nel TIE del segnale.",
        "The serializer PLL IS the transmitted clock: RJ (Gaussian, unbounded), PJ/SJ (sinusoidal), DCD, BUJ, and SSC all add into the signal TIE.",
        "TIE = RJ + A·sin(2πf_j t) + DCD·(−1)ᵏ + BUJ + ∫SSC dt",
        "TIE al driver, riga spettrale del PJ, istogramma bimodale del DCD, rampa di fase dell'SSC nel CDR.",
        "Driver TIE, PJ spectral line, bimodal DCD histogram, SSC phase ramp in the CDR.",
        "Metti PJ 0.1 UI a 30 MHz e misura la jitter transfer nel pannello timing: sotto la banda del loop il CDR lo insegue (0 dB), sopra lo attenua.",
        "Set 0.1 UI PJ at 30 MHz and measure jitter transfer in the timing panel: below the loop bandwidth the CDR tracks it (0 dB), above it attenuates.",
        "Modello edge-jitter per UI, non una PSD completa di phase noise; l'SSC parte a fase fissa nel record.",
        "Per-UI edge-jitter model, not a full phase-noise PSD; SSC starts at a fixed phase within the record.",
        "ECEN 720",
        deep_it=("A 56 GBd l'UI dura 17.9 ps: un RJ di 300 fs RMS è già il 1.7% dell'UI, e con TJ = DJ + 14.1·RJ "
                 "(a BER 1e-12) quei femtosecondi si mangiano l'occhio orizzontale. Il PJ è lo strumento "
                 "principe del test di tolleranza (JTOL): il ricevitore DEVE tollerare una maschera di ampiezza/frequenza. "
                 "L'SSC (down-spread 0.5% a 30-33 kHz) esiste per l'EMI: spalma la riga spettrale del clock; il "
                 "CDR lo vede come un offset di frequenza che cambia lentamente e lo insegue con l'integratore "
                 "del loop. Il BUJ modella il crosstalk di altri lane: bounded, non gaussiano, non correlato ai dati."),
        deep_en=("At 56 GBd the UI is 17.9 ps: 300 fs RMS of RJ is already 1.7% of the UI, and with TJ = DJ + "
                 "14.1·RJ (at 1e-12) those femtoseconds eat the horizontal eye. PJ is the workhorse of jitter "
                 "tolerance (JTOL) testing: a receiver MUST tolerate an amplitude/frequency mask. SSC (0.5% "
                 "down-spread at 30-33 kHz) exists for EMI: it smears the clock spectral line; the CDR sees a "
                 "slowly-varying frequency offset and tracks it with the loop integrator. BUJ models other-lane "
                 "crosstalk: bounded, non-Gaussian, uncorrelated with the data."),
        numbers=[("UI @ 56 GBd", "17.86 ps"),
                 ("RJ budget TX tipico", "≲ 300 fs RMS"),
                 ("TJ(p) dual-Dirac", "2·Q_p·σ + DJ(δδ) — Derickson 2-41"),
                 ("RJ di sistema", "σ_tot = √Σσᵢ² (indip., Derickson 2-42)"),
                 ("DJ di sistema", "DJ(δδ) ≈ Σ DJᵢ(δδ) (~10%, Derickson 2-45)"),
                 ("SSC standard", "−5000 ppm @ 30–33 kHz")],
        actions=[("RJ 500 fs, guarda jitter panel", "RJ 500 fs, watch the jitter panel",
                  "tail-fit RJ ≈ 0.5 ps e TJ@1e-12 cresce di 7 ps", "tail-fit RJ ≈ 0.5 ps and TJ@1e-12 grows by 7 ps"),
                 ("SSC 2500 ppm + strip CDR", "SSC 2500 ppm + CDR strip",
                  "la traccia di frequenza del CDR insegue la rampa", "the CDR frequency trace follows the ramp")],
        panel="serpll"),

    _topic(
        "TX FIR, DAC e driver", "TX FIR, DAC and driver", "tx",
        "Il FIR TX (pre/post-cursor negativi) scolpisce il simbolo PRIMA del canale: pre-enfasi delle transizioni = de-enfasi della bassa frequenza. DAC e driver mettono quantizzazione, banda e clipping.",
        "The TX FIR (negative pre/post-cursors) shapes the symbol BEFORE the channel: transition pre-emphasis = low-frequency de-emphasis. DAC and driver add quantization, bandwidth, and clipping.",
        "y[k] = Σ cᵢ·x[k−i],  Σ|cᵢ| ≤ 1 (vincolo di picco)",
        "Swing cost del FIR, spettro pre-enfatizzato, occhio al driver vs occhio al canale.",
        "FIR swing cost, pre-emphasized spectrum, driver eye vs channel-output eye.",
        "Su IL 16 dB: FIR (0,1,0) → occhio chiuso al canale; poi lancia AN/LT e guarda il preset 2 aprirlo.",
        "At 16 dB IL: FIR (0,1,0) → closed channel eye; then run AN/LT and watch preset 2 open it.",
        "Il vincolo di picco reale dipende dal DAC; qui è una somma |cᵢ| dichiarata. Il clipping è hard-limit ideale.",
        "The real peak constraint depends on the DAC; here it is a declared |cᵢ| sum. Clipping is an ideal hard limit.",
        "ECEN 720",
        deep_it=("Il FIR TX è l'unico equalizzatore che agisce PRIMA del rumore del ricevitore: attenua la bassa "
                 "frequenza invece di amplificare l'alta, quindi non amplifica il rumore (a differenza della CTLE). "
                 "Il costo è lo swing: con Σ|cᵢ|=1.3 il main cursor effettivo scende e il segnale medio si riduce. "
                 "È per questo che l'LT di clause negozia proprio questi coefficienti col link partner: solo il "
                 "ricevitore sa quale pre-distorsione serve al SUO canale. A 5 tap (c−2..c+2) si compensano "
                 "canali dove 3 tap non bastano — provato sul banco: IL 20 dB si aggancia solo col 5-tap."),
        deep_en=("The TX FIR is the only equalizer acting BEFORE receiver noise: it de-emphasizes low frequency "
                 "instead of boosting high frequency, so it does not amplify noise (unlike a CTLE). The cost is "
                 "swing: with Σ|cᵢ|=1.3 the effective main cursor drops. This is exactly why clause LT negotiates "
                 "these coefficients with the link partner: only the receiver knows what pre-distortion ITS channel "
                 "needs. With 5 taps (c−2..c+2) you can equalize channels 3 taps cannot — proven on this bench: "
                 "20 dB IL locks only with the 5-tap FIR."),
        numbers=[("tap tipici 802.3ck", "c(−2), c(−1), c(0), c(+1)"),
                 ("range coefficiente", "±0.35 circa"),
                 ("DAC 112G tipico", "7-8 bit ENOB ~5"),
                 ("swing driver", "0.8–1.2 Vppd"),
                 ("preset 2/3 LT", "post ~−0.2 / pre+post")],
        actions=[("FIR (0,1,0) su IL 16 dB", "FIR (0,1,0) at 16 dB IL",
                  "occhio 'chan' chiuso, BER sale di un ordine", "'chan' eye closed, BER up one order of magnitude"),
                 ("Bottone AN/LT nel topbar", "AN/LT button in the topbar",
                  "preset + handshake trovano i tap, occhio si apre", "presets + handshake find the taps, the eye opens")],
        panel="tx"),

    _topic(
        "Canale elettrico e crosstalk", "Electrical channel and crosstalk", "channel",
        "Il canale è un filtro passa-basso con perdita ∝ √f (skin) e ∝ f (dielettrico): a Nyquist mancano decine di dB, e le riflessioni (RL) aggiungono echi.",
        "The channel is a low-pass with loss ∝ √f (skin) and ∝ f (dielectric): tens of dB are missing at Nyquist, and reflections (RL) add echoes.",
        "IL(f) ≈ a√f + b·f ;  ISI = h(t) oltre il cursore",
        "SDD21 del modello o del Touchstone, pulse response, NEXT/FEXT e COM Annex 93A con contributi al DER₀.",
        "Model or Touchstone SDD21, pulse response, NEXT/FEXT, and Annex 93A COM contributions at DER₀.",
        "Carica il profilo 100GBASE-KR1, apri COM e confronta package corto/lungo; poi accendi FEXT −25 dB e osserva A_ni.",
        "Load the 100GBASE-KR1 profile, open COM and compare short/long packages; then enable −25 dB FEXT and watch A_ni.",
        "Il COM è un subset dichiarato: manca il set completo di S-parameter victim/NEXT/FEXT e il package multi-riflessione, quindi nessun claim di conformità.",
        "COM is a declared subset: the full victim/NEXT/FEXT S-parameter set and multi-reflection package are missing, so it makes no compliance claim.",
        "ECEN 720",
        deep_it=("La regola d'oro del settore: ogni raddoppio di baud rate costa ~2× dB di IL sullo stesso mezzo — "
                 "per questo 224G/lane spinge su PAM6/rame corto/ottica. A 28 GHz un backplane 'legacy' può fare "
                 "30+ dB: il budget COM di clause definisce quanto un ricevitore conforme deve recuperare (~20 dB "
                 "con FOM). Il crosstalk è spesso il vero assassino: il NEXT non passa per il canale (non è "
                 "attenuato!) e arriva 'fresco' sul RX; l'ICN si somma al rumore. I connettori dominano il RL."),
        deep_en=("The industry rule of thumb: each baud-rate doubling costs ~2× the dB of IL on the same medium — "
                 "why 224G/lane pushes PAM6/short copper/optics. At 28 GHz a legacy backplane can be 30+ dB: the "
                 "clause COM budget defines what a compliant receiver must recover. Crosstalk is often the real "
                 "killer: NEXT does not go through the channel (it is NOT attenuated!) and lands 'fresh' on the RX; "
                 "ICN adds to noise. Connectors dominate return loss."),
        numbers=[("CR cable 2 m", "~10-15 dB @ 26.6 GHz"),
                 ("backplane KR", "20-30 dB @ Nyquist"),
                 ("budget 802.3ck", "~28 dB con COM ≥ 3 dB"),
                 ("NEXT tipico conn.", "−35..−45 dB"),
                 ("skin effect", "IL ∝ √f (rame)")],
        actions=[("IL 6 → 20 dB, guarda 'chan'", "IL 6 → 20 dB, watch 'chan'",
                  "pulse response si allarga: post-cursori per il DFE", "pulse response spreads: post-cursors for the DFE"),
                 ("xtalk_next −25 dB", "xtalk_next −25 dB",
                  "SNR slicer scende ~2 dB: rumore bounded non equalizzabile", "slicer SNR drops ~2 dB: bounded, non-equalizable noise")],
        panel="channel"),

    _topic(
        "Ottica: MZM/EML, fibra, dispersione", "Optics: MZM/EML, fiber, dispersion", "optical",
        "Il modulatore trasforma volt in potenza ottica sulla sua curva (il MZM è un coseno: bias in quadratura, drive nel tratto lineare); la fibra aggiunge loss, CD e non-linearità.",
        "The modulator maps volts to optical power on its transfer curve (the MZM is a cosine: quadrature bias, drive on the linear part); fiber adds loss, CD, and nonlinearity.",
        "P = P₀·cos²(φ/2+bias/2) ;  CD: β₂ = −Dλ²/2πc",
        "Occupazione del drive sulla curva del MZM, link budget a cascata, livelli P0-P3 in dBm, OMA/ER, fading da CD.",
        "Drive occupancy on the MZM curve, waterfall link budget, P0-P3 levels in dBm, OMA/ER, CD fading.",
        "A 1550 nm porta la fibra a 10 km: il CD (17 ps/nm/km) chiude l'occhio; a 1310 nm (D≈0) no. Il chirp α cambia il segno del danno.",
        "At 1550 nm set 10 km of fiber: CD (17 ps/nm/km) closes the eye; at 1310 nm (D≈0) it does not. Chirp α flips the sign of the damage.",
        "Campo scalare, PMD a 2 modi, Kerr semplificato; TDECQ ha struttura di clause ma non calibrazione/pattern completi, quindi non è certificabile.",
        "Scalar field, 2-mode PMD, simplified Kerr; TDECQ has clause structure but lacks full calibration/patterns, so it is not certifiable.",
        "ECEN 721",
        deep_it=("Il PD misura POTENZA (|E|²): la fase ottica si perde, e la dispersione cromatica — che è un "
                 "ritardo di fase fra le bande laterali — diventa fading di ampiezza: a 56 GBd su 1550 nm bastano "
                 "pochi km. Per questo i datacenter usano 1310 nm (zero-dispersion) per 500 m-10 km, e il coherent "
                 "vince sulle lunghe distanze (recupera la fase e inverte il CD digitalmente). L'ER finito costa "
                 "potenza: il livello P0 'sporca' con luce residua, e il TDECQ misura proprio quanta potenza "
                 "extra serve rispetto a un occhio ideale."),
        deep_en=("The PD measures POWER (|E|²): optical phase is lost, and chromatic dispersion — a phase delay "
                 "between sidebands — becomes amplitude fading: at 56 GBd on 1550 nm a few km suffice. That is why "
                 "datacenters use 1310 nm (zero dispersion) for 500 m-10 km, and coherent wins at long reach "
                 "(it recovers phase and inverts CD digitally). Finite ER costs power: level P0 carries residual "
                 "light, and TDECQ measures exactly how much extra power you pay vs an ideal eye."),
        numbers=[("D @ 1550/1310 nm", "17 / ~0 ps/(nm·km)"),
                 ("loss SMF", "0.20 (1550) · 0.35 (1310) dB/km"),
                 ("ER tipico DR/FR", "3.5–6 dB"),
                 ("TDECQ limite", "≤ 3.4 dB (DR4)"),
                 ("Vπ MZM LiNbO₃/SiP", "2–5 V")],
        actions=[("bias MZM 1.57 → 2.2 rad", "MZM bias 1.57 → 2.2 rad",
                  "compressione asimmetrica: RLM peggiora, occhi diseguali", "asymmetric compression: RLM degrades, unequal eyes"),
                 ("fiber 10 km @ 1550", "10 km fiber @ 1550",
                  "fading CD visibile nello spettro e occhio chiuso", "CD fading visible in the spectrum, eye closed")],
        panel="optical"),

    _topic(
        "PD, TIA e AGC", "PD, TIA and AGC", "rxfe",
        "Il PD converte fotoni in corrente (R ≈ 0.8 A/W) col suo rumore shot; il TIA la converte in volt e domina il rumore del ricevitore; l'AGC normalizza lo swing per l'ADC.",
        "The PD converts photons to current (R ≈ 0.8 A/W) with shot noise; the TIA converts it to volts and dominates receiver noise; the AGC normalizes swing for the ADC.",
        "i = R·P + shot + dark ;  v = Z_T·i ;  SNR ∝ P²/(N_th+N_shot)",
        "PSD shot vs RIN vs termico, headroom del TIA, gain dell'AGC e clipping.",
        "Shot vs RIN vs thermal PSD, TIA headroom, AGC gain and clipping.",
        "Abbassa il laser di 6 dB: il rumore termico del TIA domina e l'SNR elettrico cala di 12 dB (legge quadratica!).",
        "Drop the laser by 6 dB: TIA thermal noise dominates and electrical SNR falls 12 dB (square law!).",
        "AGC statico per record (non dinamico), TIA lineare fino al clip ideale.",
        "AGC static per record (not dynamic), TIA linear up to an ideal clip.",
        "ECEN 721",
        deep_it=("La legge quadratica del PD è la tassa dell'ottica IM-DD: −1 dB ottico = −2 dB elettrico. La "
                 "sensibilità del ricevitore è decisa dal rumore in ingresso al TIA (~20-30 pA/√Hz): con "
                 "R=0.8 A/W e OMA −5 dBm hai ~250 µA di segnale contro ~5 µA RMS di rumore su 40 GHz. Il RIN "
                 "del laser scala col QUADRATO della potenza: sui link corti ad alta potenza diventa lui il "
                 "pavimento, non il termico — per questo il RIN spec è ~−140 dB/Hz."),
        deep_en=("The PD square law is the IM-DD tax: −1 optical dB = −2 electrical dB. Receiver sensitivity is set "
                 "by the TIA input-referred noise (~20-30 pA/√Hz): with R=0.8 A/W and −5 dBm OMA you get ~250 µA "
                 "of signal against ~5 µA RMS of noise over 40 GHz. Laser RIN scales with the SQUARE of power: on "
                 "short high-power links it becomes the floor instead of thermal noise — hence the ~−140 dB/Hz "
                 "RIN spec."),
        numbers=[("responsivity InGaAs", "0.7–1.0 A/W"),
                 ("TIA noise", "15–30 pA/√Hz"),
                 ("sensibilità tipica", "−8..−11 dBm OMA (con KP4)"),
                 ("RIN spec", "≲ −140 dB/Hz"),
                 ("legge quadratica", "1 dB opt = 2 dB el")],
        actions=[("laser −6 dB", "laser −6 dB",
                  "SNR slicer −12 dB circa: quadratica + termico", "slicer SNR down ~12 dB: square law + thermal"),
                 ("tia_noise ×3", "tia_noise ×3",
                  "il pavimento di rumore sale nel pannello TIA", "the noise floor rises in the TIA panel")],
        panel="pd"),

    _topic(
        "CTLE: zeri, poli, peaking", "CTLE: zeros, poles, peaking", "ctle",
        "La CTLE è un filtro analogico con uno zero prima dei poli: alza l'alta frequenza rispetto alla DC (peaking) per compensare il canale, ma alza anche il rumore lì.",
        "The CTLE is an analog filter with a zero before its poles: it boosts high frequency vs DC (peaking) to undo the channel, but boosts noise there too.",
        "H(s) = g·Π(1+s/ωz)/Π(1+s/ωp)",
        "Bode con peaking e frequenza di picco, group delay, noise enhancement in dB.",
        "Bode with peaking and peak frequency, group delay, noise enhancement in dB.",
        "Sposta lo zero da 9 a 5 GHz: più peaking a Nyquist, occhio più aperto MA rumore amplificato — trova l'ottimo con lo sweep.",
        "Move the zero from 9 to 5 GHz: more Nyquist peaking, wider eye BUT amplified noise — find the optimum with a sweep.",
        "Sezioni ideali in cascata, niente non-idealità transistor (offset, non-linearità, PVT).",
        "Ideal cascaded sections, no transistor non-idealities (offset, nonlinearity, PVT).",
        "ECEN 720",
        deep_it=("La CTLE esiste perché costa poco (mW e area minuscola) e riduce l'ISI PRIMA del campionamento: "
                 "senza, l'ADC sprecherebbe range sui cursori ISI e il FFE digitale amplificherebbe ancora più "
                 "rumore. Il design è un compromedio a tre: peaking sufficiente per il canale, noise enhancement "
                 "tollerabile, e group delay piatto (un GD storto crea ISI esso stesso). Nei ricevitori veri è "
                 "adattiva: 8-16 codici di peaking scelti dal training — è quello che fa l'RX adapt dell'AN/LT qui."),
        deep_en=("The CTLE exists because it is cheap (mW, tiny area) and removes ISI BEFORE sampling: without it "
                 "the ADC would waste range on ISI cursors and the digital FFE would amplify even more noise. The "
                 "design is a three-way trade: enough peaking for the channel, tolerable noise enhancement, and "
                 "flat group delay (bad GD creates ISI by itself). Real receivers make it adaptive: 8-16 peaking "
                 "codes chosen during training — which is what this bench's AN/LT RX-adapt does."),
        numbers=[("peaking tipico", "5–15 dB @ Nyquist"),
                 ("codici CTLE reali", "8–16 step da ~1 dB"),
                 ("noise enhancement", "≈ peaking − IL recuperata"),
                 ("zero utile", "~f_baud/6 .. f_baud/3"),
                 ("potenza", "~1-5 mW (vs ~100 mW DSP)")],
        actions=[("ctle_dc_gain −6 dB", "ctle_dc_gain −6 dB",
                  "più peaking relativo: occhio su, rumore su", "more relative peaking: eye up, noise up"),
                 ("Sweep ctle_zero_hz", "Sweep ctle_zero_hz",
                  "curva a U della BER: l'ottimo non è agli estremi", "U-shaped BER curve: the optimum is not at the edges")],
        panel="ctle"),

    _topic(
        "ADC interleaved e hard decision", "Interleaved ADC and hard decisions", "adc",
        "L'ADC a 2 campioni/UI trasforma il segnale in numeri: da qui in poi solo DSP. I campioni DATA mostrano i 4 modi PAM4, quelli EDGE le transizioni per il timing.",
        "The 2-samples/UI ADC turns the signal into numbers: everything after is DSP. DATA samples show the 4 PAM4 modes, EDGE samples the transitions for timing.",
        "SNDR = 6.02·ENOB + 1.76 dB ;  interleave spurs @ fs/M",
        "Istogramma DATA vs EDGE, scatter delle hard decision con le soglie, occupazione codici su full-scale, SNDR/ENOB del tone-lab.",
        "DATA vs EDGE histograms, hard-decision scatter with thresholds, code occupancy over full scale, tone-lab SNDR/ENOB.",
        "Scendi a 5 bit: i 4 modi si sgranano e la BER sale; poi alza il gain mismatch e cerca le righe di interleave nello spettro.",
        "Go down to 5 bits: the 4 modes get grainy and BER rises; then raise gain mismatch and find interleave spurs in the spectrum.",
        "Mismatch statici per lane; niente calibrazione adattiva né riferimenti reali.",
        "Static per-lane mismatch; no adaptive calibration or real references.",
        "ECEN 720",
        deep_it=("Un ADC 112G reale è ~32-64 SAR interleaved a ~1.7 GS/s l'uno: gain/offset/skew fra i lane creano "
                 "righe a fs/M che la calibrazione deve inseguire. I 7-8 bit nominali diventano ~5 ENOB a Nyquist — "
                 "abbastanza perché il rumore di quantizzazione stia sotto il termico. Guarda lo scatter: le hard "
                 "decision al piano ADC sono PEGGIO che allo slicer post-DSP — la differenza è esattamente il "
                 "guadagno di FFE+DFE. L'AGC serve a riempire il full-scale senza clippare: occupazione ~90%."),
        deep_en=("A real 112G ADC is ~32-64 interleaved SARs at ~1.7 GS/s each: per-lane gain/offset/skew create "
                 "spurs at fs/M that calibration must chase. The nominal 7-8 bits become ~5 ENOB at Nyquist — "
                 "enough to keep quantization noise below thermal. Look at the scatter: hard decisions at the ADC "
                 "plane are WORSE than at the post-DSP slicer — the difference is exactly the FFE+DFE gain. The "
                 "AGC's job is filling the full scale without clipping: ~90% occupancy."),
        numbers=[("architettura tipica", "32-64× SAR TI"),
                 ("ENOB @ Nyquist", "~5 (da 7-8 bit)"),
                 ("aperture jitter", "< 100 fs RMS"),
                 ("righe interleave", "k·fs/M ± f_in"),
                 ("potenza ADC 112G", "~150-300 mW")],
        actions=[("adc_bits 7 → 5", "adc_bits 7 → 5",
                  "istogramma DATA sgranato, BER su", "grainy DATA histogram, BER up"),
                 ("Auto search fase (BERT)", "Phase auto search (BERT)",
                  "la fase di campionamento ottima non è 0", "the optimum sampling phase is not 0")],
        panel="adc"),

    _topic(
        "CDR: Gardner, loop PI, lock", "CDR: Gardner, PI loop, lock", "timing",
        "Il CDR decide QUANDO campionare: un TED (Gardner/MM) misura l'errore di fase dalle transizioni, un loop PI + NCO lo azzera. Senza lock non esiste nessuna metrica.",
        "The CDR decides WHEN to sample: a TED (Gardner/MM) measures phase error from transitions, a PI loop + NCO drives it to zero. Without lock no metric exists.",
        "e = y_edge·(y[k]−y[k−1]) ;  Kp=2ζω_nT/K_ted, Ki=(ω_nT)²/K_ted",
        "Traccia di fase τ, traccia di frequenza in ppm, istogramma dell'errore di fase, S-curve del TED, OJTF misurata.",
        "Phase trace τ, frequency trace in ppm, phase-error histogram, TED S-curve, measured OJTF.",
        "Metti rx_ppm_offset −200: la traccia di frequenza converge a +200 ppm (il loop assorbe l'offset). Poi misura la OJTF e trova il −3 dB.",
        "Set rx_ppm_offset −200: the frequency trace converges to +200 ppm (the loop absorbs the offset). Then measure the OJTF and find the −3 dB point.",
        "Loop simbolo-per-simbolo su record finito: il lock time e il jitter peaking dipendono dal transitorio.",
        "Symbol-rate loop on a finite record: lock time and jitter peaking depend on the transient.",
        "ECEN 720",
        deep_it=("La banda del loop è IL compromesso del CDR: larga insegue il jitter del TX (bene) ma lascia "
                 "passare il rumore di fase del TED (male); tipica ~f_baud/1000-4000. Il 2° ordine serve per "
                 "l'offset di frequenza (±100 ppm di clock + SSC): l'integratore lo assorbe a regime. Il jitter "
                 "peaking vicino al corner (qui misurabile con la OJTF!) è il motivo per cui le catene di "
                 "repeater limitano il peaking a <0.1 dB. Il Gardner lavora a 2 sps e ha un'ambiguità dato/fronte "
                 "di mezzo UI: la risolve il pattern lock, come in un BERT."),
        deep_en=("Loop bandwidth is THE CDR trade-off: wide tracks TX jitter (good) but passes TED phase noise "
                 "(bad); typical ~f_baud/1000-4000. Second order exists for frequency offset (±100 ppm clocks + "
                 "SSC): the integrator absorbs it at steady state. Jitter peaking near the corner (measurable here "
                 "with the OJTF!) is why repeater chains cap peaking at <0.1 dB. Gardner runs at 2 sps with a "
                 "half-UI data/edge ambiguity: pattern lock resolves it, as in a BERT."),
        numbers=[("banda tipica", "f_baud/1000..4000"),
                 ("offset clock max", "±100 ppm (802.3)"),
                 ("peaking max (rete)", "< 0.1-1 dB"),
                 ("lock time", "~10³-10⁵ UI"),
                 ("ζ tipico", "0.7–1"),],
        actions=[("cdr_bw ×3", "cdr_bw ×3",
                  "σ(τ) sale (più rumore TED), JTOL a bassa f migliora", "σ(τ) up (more TED noise), low-f JTOL better"),
                 ("Misura jitter transfer", "Measure jitter transfer",
                  "0 dB in banda, peaking al corner, poi rolloff", "0 dB in-band, peaking at the corner, then rolloff")],
        panel="timing"),

    _topic(
        "RX FFE (FSE) + DFE", "RX FFE (FSE) + DFE", "eq",
        "L'FFE del ricevitore è un FIR T/2 adattato (NLMS) che inverte l'ISI lineare; il DFE sottrae i post-cursori usando i simboli GIÀ decisi: niente noise enhancement, ma error propagation.",
        "The receiver FFE is an adapted T/2 FIR (NLMS) inverting linear ISI; the DFE subtracts post-cursors using ALREADY-decided symbols: no noise enhancement, but error propagation.",
        "FFE: w ← w + µ·e·x/||x||² ;  DFE: y[k] − Σ bᵢ·d[k−i]",
        "Tap FFE/DFE adattati, MSE di apprendimento, BER per stadio (pre-EQ → FSE → DFE), burst dell'ED.",
        "Adapted FFE/DFE taps, learning MSE, per-stage BER (pre-EQ → FSE → DFE), ED bursts.",
        "Azzera i dfe_taps: la BER sale dei post-cursori non cancellati. Poi guarda l'error analysis del BERT: senza DFE spariscono i burst.",
        "Zero the dfe_taps: BER rises from uncancelled post-cursors. Then check the BERT error analysis: without DFE the bursts disappear.",
        "NLMS ideale float, niente quantizzazione dei tap né timing offset del DFE loop reale (1 UI di budget!).",
        "Ideal float NLMS, no tap quantization nor the real DFE loop timing budget (1 UI!).",
        "ECEN 720",
        deep_it=("La partizione è sempre la stessa in ogni SerDes moderno: il FIR TX toglie l'ISI 'facile' senza "
                 "rumore, la CTLE sgrossa in analogico, l'FFE RX inverte finemente il canale (e amplifica rumore "
                 "e crosstalk: guarda i tap crescere sui canali cattivi), il DFE toglie i post-cursori GRATIS in "
                 "rumore — ma un simbolo sbagliato inquina i successivi: i burst nell'error analysis sono la sua "
                 "firma, ed è per questo che il FEC è symbol-based. Il feedback del DFE deve chiudersi in 1 UI "
                 "(17.9 ps!): è il vincolo di timing più duro di tutto il chip — i DFE reali usano loop unrolling."),
        deep_en=("The split is the same in every modern SerDes: the TX FIR removes 'easy' ISI noise-free, the CTLE "
                 "does the analog rough cut, the RX FFE finely inverts the channel (amplifying noise and crosstalk: "
                 "watch the taps grow on bad channels), and the DFE removes post-cursors for FREE in noise — but "
                 "one wrong symbol pollutes the next ones: the bursts in the error analysis are its signature, and "
                 "the reason FEC is symbol-based. The DFE feedback must close in 1 UI (17.9 ps!): the hardest "
                 "timing constraint on the chip — real DFEs use loop unrolling."),
        numbers=[("FFE RX tipico", "8-24 tap T/2"),
                 ("DFE tipico", "1-8 tap (h1 dominante)"),
                 ("burst DFE", "run geometrici su h1"),
                 ("timing DFE", "1 UI = 17.9 ps @ 56 GBd"),
                 ("µ NLMS", "1e-3..1e-2")],
        actions=[("dfe_taps 5 → 0", "dfe_taps 5 → 0",
                  "BER su, burst spariti (error analysis)", "BER up, bursts gone (error analysis)"),
                 ("fse_taps 17 → 7", "fse_taps 17 → 7",
                  "ISI residua: tap troncati, occhio slicer più chiuso", "residual ISI: truncated taps, tighter slicer eye")],
        panel="eq"),

    _topic(
        "DCA: occhio, EH@BER, contour", "DCA: eye, EH@BER, contour", "scope",
        "Il DCA campiona in equivalent-time e accumula il diagramma a occhio: densità/fosforo, misure per occhio, statistiche per acquisizione, EH estrapolata a BER e contour 2D.",
        "The DCA samples in equivalent time and accumulates the eye: density/phosphor, per-eye measures, per-acquisition statistics, BER-extrapolated EH, and 2D contours.",
        "EH@BER = (μ_b−Qσ_b)−(μ_a+Qσ_a),  Q = Φ⁻¹(1−BER)",
        "Height/width per occhio, Q, RLM, rise/fall, maschera con hit count, statistiche cur/min/max/µ/σ, contour log-BER.",
        "Per-eye height/width, Q, RLM, rise/fall, mask with hit count, cur/min/max/µ/σ statistics, log-BER contours.",
        "Confronta l'occhio a 'chan' (chiuso: è NORMALE pre-EQ) con 'vctle' e con le decisioni post-DFE: la catena di equalizzazione in tre foto.",
        "Compare the eye at 'chan' (closed: NORMAL pre-EQ) with 'vctle' and the post-DFE decisions: the equalization chain in three pictures.",
        "Estrapolazioni con code gaussiane dichiarate; niente de-embedding, filtri di riferimento né trigger reali.",
        "Declared Gaussian-tail extrapolations; no de-embedding, reference filters, or real triggering.",
        "ECEN 721",
        deep_it=("Un occhio 'aperto' a occhio nudo non dice nulla a BER 1e-12: servono 10¹² UI per VEDERE un "
                 "errore. Per questo gli strumenti estrapolano: il Q-scale assume code gaussiane e proietta "
                 "l'apertura al BER target (qui EH@2.4e-4 = soglia KP4). Il contour è la stessa idea in 2D: le "
                 "curve chiuse concentriche sono 'l'occhio al BER x'. Attenzione all'ISI multimodale: le code NON "
                 "sono gaussiane vicino ai cursori, e l'estrapolazione è ottimista (da 1e-6 misurata a 1e-12 sono ≥6 ordini: Derickson §2.5.4) — il tail-fit dual-Dirac del "
                 "pannello jitter separa proprio RJ (gaussiano) da DJ (bounded)."),
        deep_en=("An eye that looks 'open' says nothing at 1e-12: you would need 10¹² UI to SEE one error. Hence "
                 "extrapolation: the Q-scale assumes Gaussian tails and projects the opening to the target BER "
                 "(here EH@2.4e-4 = the KP4 threshold). The contour is the same idea in 2D: the concentric closed "
                 "curves are 'the eye at BER x'. Beware multimodal ISI: tails are NOT Gaussian near cursors and "
                 "the extrapolation is optimistic (a measured 1e-6 to 1e-12 is a ≥6-order extrapolation: Derickson §2.5.4) — the jitter panel's dual-Dirac tail-fit separates exactly RJ "
                 "(Gaussian) from DJ (bounded)."),
        numbers=[("banda DCA reale", "50-70 GHz (+ SW 100G+)"),
                 ("EH@BER target", "2.4e-4 (KP4) · 1e-6"),
                 ("Q(1e-12)", "7.03"),
                 ("persistenza", "variabile / infinita"),
                 ("dark calib.", "de-embedding S-par")],
        actions=[("Contour BER su vctle", "BER contour on vctle",
                  "curve concentriche: l'occhio si restringe col BER", "concentric curves: the eye shrinks with BER"),
                 ("Mask test + PJ 0.05 UI", "Mask test + 0.05 UI PJ",
                  "gli hit compaiono ai bordi orizzontali", "hits appear at the horizontal edges")],
        panel="scope"),

    _topic(
        "BERT: PPG, ED, error analysis", "BERT: PPG, ED, error analysis", "bert",
        "Il PPG genera pattern e stress calibrati; l'ED riallinea la PRBS e conta OGNI bit errato: BER con intervallo di confidenza, gating, burst vs random, error-free intervals.",
        "The PPG generates calibrated patterns and stress; the ED realigns the PRBS and counts EVERY bit error: BER with confidence interval, gating, burst vs random, error-free intervals.",
        "CL95: N ≈ 3/BER (0 errori) ;  BER = N_err/N_bit",
        "BER/SER per lane MSB/LSB, mappa temporale degli errori, analisi burst (gap ≤ 8), CL95 sul target.",
        "Per-lane MSB/LSB BER/SER, temporal error map, burst analysis (gap ≤ 8), CL95 vs target.",
        "Con BER 0, quanti bit servono per dichiarare < 1e-9 al 95%? Usa il gating: 3e9 bit. È il tempo-costo di ogni misura seria.",
        "With zero errors, how many bits to claim < 1e-9 at 95%? Use gating: 3e9 bits. That is the time cost of any serious measurement.",
        "Un solo lane; l'editor HEX è MSB-first ma mancano de-emphasis di stress programmabile e calibrazione completa del stressed eye.",
        "Single lane; the HEX editor is MSB-first, but programmable stress de-emphasis and complete stressed-eye calibration are missing.",
        "ECEN 720",
        deep_it=("La statistica è spietata: senza errori osservati puoi solo dire BER < 3/N al 95% — misurare "
                 "1e-15 'vero' richiede giorni. Per questo il settore misura BER pre-FEC alte (1e-4/1e-6) e "
                 "ESTRAPOLA con bathtub e Q-scale. La distinzione burst/random non è pedanteria: i burst del DFE "
                 "colpiscono simboli RS consecutivi (il FEC li tollera), il rumore random sparso li spalma su più "
                 "codeword (peggio per il FEC). L'MSB e l'LSB del PAM4 Gray hanno BER diverse per costruzione: "
                 "l'LSB sbaglia su due soglie, l'MSB su una."),
        deep_en=("Statistics is merciless: with zero observed errors you can only claim BER < 3/N at 95% — truly "
                 "measuring 1e-15 takes days. Hence the industry measures high pre-FEC BERs (1e-4/1e-6) and "
                 "EXTRAPOLATES with bathtubs and Q-scales. Burst vs random is not pedantry: DFE bursts hit "
                 "consecutive RS symbols (FEC tolerates them), scattered random errors smear across codewords "
                 "(worse for FEC). Gray PAM4 MSB and LSB have different BERs by construction: the LSB fails on "
                 "two thresholds, the MSB on one."),
        numbers=[("CL95 zero errori", "N = 3/BER_target"),
                 ("1e-9 al 95%", "3e9 bit ≈ 27 ms @112G"),
                 ("BER LSB/MSB Gray", "≈ 2:1"),
                 ("burst gap ED", "≤ 8 simboli (firma DFE)"),
                 ("bathtub = BERT scan", "sample delay scan, Derickson cap. 5"),
                 ("MP1900A stress", "RJ+SJ+BUJ+SSC+CM/DM")],
        actions=[("Inietta 20 bit + burst", "Inject 20 bits + burst",
                  "error analysis: 1 burst lungo vs 20 isolati", "error analysis: 1 long burst vs 20 isolated"),
                 ("Gate 10 s su link pulito", "10 s gate on a clean link",
                  "CL95 cresce verso il target: il tempo È la misura", "CL95 grows toward target: time IS the measurement")],
        panel="bert"),

    _topic(
        "Ethernet L2: frame, FCS, ONT", "Ethernet L2: frames, FCS, ONT", "l2",
        "Frame veri (preamble/SFD, header, sequence, FCS CRC-32) attraversano FEC e PHY su PCS scramblato; l'analyzer delimita, verifica la FCS e conta i persi via sequence.",
        "Real frames (preamble/SFD, header, sequence, CRC-32 FCS) cross FEC and PHY on a scrambled PCS; the analyzer delineates, checks FCS, counts losses via sequence numbers.",
        "FCS = CRC32(header+payload) ;  offered = wire/(wire+IPG)",
        "Ispettore frame coi byte veri e la FCS ricalcolata, contatori ok/FCS-bad/persi, load ramp via IPG, latency budget.",
        "Frame inspector with real bytes and recomputed FCS, ok/FCS-bad/lost counters, IPG load ramp, latency budget.",
        "Guarda l'ispettore: cambia 1 bit (inietta dal BERT) e la FCS non torna più — il descrambler lo ha pure moltiplicato ×3.",
        "Watch the inspector: flip 1 bit (inject from the BERT) and the FCS no longer matches — the descrambler even multiplied it ×3.",
        "Niente DUT di rete: perdita solo da bit error (no code/congestione); MAC semplificato, non RFC 2544.",
        "No network DUT: loss only from bit errors (no queues/congestion); simplified MAC, not RFC 2544.",
        "ECEN 720",
        deep_it=("Il PCS scrambla (x⁵⁸+x³⁹+1) per una ragione fisica dimostrabile su questo banco: l'idle 0x00 di "
                 "un IPG lungo, non scramblato, produce run costanti che ammazzano CDR e AGC. Il prezzo del "
                 "self-sync è la moltiplicazione ×3 degli errori — visibile sull'FCS. Un ONT verifica i frame "
                 "esattamente così: delineazione, sequence numbers per i persi (non puoi contare ciò che non "
                 "arriva senza numerarlo!), CRC per la corruzione, e rate control via IPG per il load ramp."),
        deep_en=("The PCS scrambles (x⁵⁸+x³⁹+1) for a physical reason demonstrable on this bench: unscrambled 0x00 "
                 "idle in a long IPG produces constant runs that kill the CDR and AGC. The self-sync price is ×3 "
                 "error multiplication — visible on the FCS. An ONT verifies frames exactly like this: "
                 "delineation, sequence numbers for losses (you cannot count what never arrives without numbering "
                 "it!), CRC for corruption, and IPG rate control for the load ramp."),
        numbers=[("overhead minimo", "preamble 8 + IPG 12 + FCS 4"),
                 ("scrambler PCS", "x⁵⁸+x³⁹+1 self-sync"),
                 ("error multiplication", "×3"),
                 ("utilizzo max 64B", "64/(64+20) = 76%"),
                 ("fibra", "4.89 µs/km one-way")],
        actions=[("pattern = eth + RUN", "pattern = eth + RUN",
                  "ispettore live: byte, FCS, seq dei frame veri", "live inspector: real bytes, FCS, sequence numbers"),
                 ("ONT load ramp", "ONT load ramp",
                  "offered vs goodput + latency budget per blocco", "offered vs goodput + per-block latency budget")],
        panel="l2"),

    _topic(
        "AN/LT: Clause 73 + training", "AN/LT: Clause 73 + training", "anlt",
        "Prima di trasmettere dati, i due PHY negoziano CHI sono (Auto-Negotiation: base page, priorità → HCD) e allenano i TX FIR l'uno dell'altro (Link Training) finché entrambi i ricevitori sono pronti.",
        "Before any data, the two PHYs negotiate WHO they are (Auto-Negotiation: base pages, priority → HCD) and train each other's TX FIRs (Link Training) until both receivers are ready.",
        "HCD = max priorità comune ;  LT: inc/dec per c(−2)..c(+2)",
        "Base page a 48 bit, timeline della macchina a stati coi timer, richieste/status dei coefficienti, Q per scambio, both_ready.",
        "48-bit base pages, state-machine timeline with timers, coefficient requests/status, Q per exchange, both_ready.",
        "Rompi il link (IL 20 dB, CTLE off) e premi AN/LT: i preset non bastano? Parte l'RX adapt. Guarda i knob FIR/CTLE cambiare da soli.",
        "Break the link (20 dB IL, CTLE off) and press AN/LT: presets not enough? RX adapt kicks in. Watch the FIR/CTLE knobs change by themselves.",
        "Protocollo senza segnalazione DME; metrica del RX = Q misurato sul banco; canale inverso dichiarato simmetrico.",
        "Protocol without DME signalling; RX metric = bench-measured Q; reverse channel declared symmetric.",
        "802.3 C73/C72/C136",
        deep_it=("È il momento più sottovalutato di un link: quando 'l'Ethernet non viene su', nell'80% dei casi "
                 "è AN/LT che fallisce. L'AN scambia pagine a 312.5 MBd (robustissime) e risolve la tecnologia "
                 "comune a priorità massima; poi il PMD control training fa dialogare i due estremi: il MIO "
                 "ricevitore chiede al TUO trasmettitore 'increment c(+1)' finché il MIO occhio è aperto — e "
                 "viceversa, in parallelo. Solo con both_ready e dentro il link_fail_inhibit_timer (~510 ms) il "
                 "link va UP. Su questo banco la metrica del ricevitore è dichiarata (Q allo slicer) e si vede "
                 "ogni singolo scambio."),
        deep_en=("The most underrated moment of a link: when 'Ethernet won't come up', 80% of the time it is AN/LT "
                 "failing. AN exchanges pages at 312.5 MBd (extremely robust) and resolves the highest-priority "
                 "common technology; then PMD-control training makes the two ends talk: MY receiver asks YOUR "
                 "transmitter 'increment c(+1)' until MY eye is open — and vice versa, in parallel. Only with "
                 "both_ready inside the link_fail_inhibit_timer (~510 ms) does the link go UP. On this bench the "
                 "receiver metric is declared (slicer Q) and every single exchange is visible."),
        numbers=[("pagina AN", "48 bit, DME 312.5 MBd"),
                 ("break_link_timer", "60-75 ms"),
                 ("link_fail_inhibit", "~510 ms"),
                 ("coefficienti ck", "c(−2)..c(+1)"),
                 ("frame LT PAM4", "~23k simboli")],
        actions=[("Bottone AN/LT (topbar)", "AN/LT button (topbar)",
                  "HCD, timeline, scambi, e i knob si aggiornano", "HCD, timeline, exchanges, and knobs update"),
                 ("partner senza abilità comuni", "partner with no common ability",
                  "HCD nullo: si resta in ABILITY_DETECT", "null HCD: stuck in ABILITY_DETECT")],
        panel="anlt"),

    _topic(
        "Modulo ottico: CMIS e DOM", "Optical module: CMIS and DOM", "cmis",
        "Un modulo QSFP-DD/OSFP si gestisce via CMIS: state machine del modulo e dei DataPath, flag di lane (LOS/LOL/TX fault), telemetria DOM/VDM (potenze, bias, temperatura).",
        "A QSFP-DD/OSFP module is managed via CMIS: module and DataPath state machines, lane flags (LOS/LOL/TX fault), DOM/VDM telemetry (powers, bias, temperature).",
        "Module: Low-Pwr→Pwr-Up→Ready ;  DP: Deactivated→Init→Activated",
        "Stati modulo/DataPath, flag di lane derivati dal banco vero (RX-LOL = !CDR lock), DOM con soglie warn/alarm, VDM (BER, SNR).",
        "Module/DataPath states, lane flags derived from the real bench (RX-LOL = !CDR lock), DOM with warn/alarm thresholds, VDM (BER, SNR).",
        "Spegni il laser (−6 dBm): RX-LOS scatta, il DataPath degrada, e la VDM mostra la BER pre-FEC salire.",
        "Kill the laser (−6 dBm): RX-LOS trips, the DataPath degrades, and VDM shows pre-FEC BER rising.",
        "Sottoinsieme CMIS: niente register map I2C, CDB, firmware download o application advertising completo.",
        "CMIS subset: no I2C register map, CDB, firmware download, or full application advertising.",
        "CMIS 5.x",
        deep_it=("Nel mondo reale il 90% del debug di un link ottico parte da qui: leggere i flag CMIS del modulo "
                 "PRIMA di tirare fuori il BERT. RX-LOS = non arriva luce (fibra, connettore); RX-LOL = luce sì "
                 "ma il CDR non aggancia (dispersione, potenza marginale); TX-fault = il laser/driver ha un "
                 "problema. La telemetria VDM aggiunge le metriche del DSP (BER pre-FEC per lane, SNR): un "
                 "host può accorgersi del degrado PRIMA che il FEC ceda."),
        deep_en=("In the real world 90% of optical-link debug starts here: read the module's CMIS flags BEFORE "
                 "reaching for a BERT. RX-LOS = no light arriving (fiber, connector); RX-LOL = light present but "
                 "the CDR will not lock (dispersion, marginal power); TX-fault = laser/driver problem. VDM "
                 "telemetry adds DSP metrics (per-lane pre-FEC BER, SNR): a host can see degradation BEFORE the "
                 "FEC gives up."),
        numbers=[("form factor", "QSFP-DD / OSFP (8 lane)"),
                 ("gestione", "I2C, pagine CMIS"),
                 ("soglie DOM", "warn/alarm ×4 (hi/lo)"),
                 ("RX power tipico", "−8..+2 dBm"),
                 ("VDM", "BER, SNR, FERC per lane")],
        actions=[("laser_dbm → −6", "laser_dbm → −6",
                  "RX-LOS + DataPath giù, VDM in rosso", "RX-LOS + DataPath down, VDM red"),
                 ("fiber 10 km @1550", "10 km fiber @1550",
                  "RX-LOL con potenza OK: è il CD, non la luce", "RX-LOL with good power: it is CD, not light")],
        panel="cmis"),

    _topic(
        "Standard IEEE/OIF: leggerli", "IEEE/OIF standards: how to read them", "standards",
        "Ogni PHY è una clause: PMD (elettrico/ottico), PCS, FEC, AN. I profili del banco dichiarano per ogni valore se è di clause, un'assunzione o non supportato.",
        "Every PHY is a clause: PMD (electrical/optical), PCS, FEC, AN. The bench profiles declare, for each value, whether it is clause, an assumption, or unsupported.",
        "es: 100GBASE-DR = C140 PMD + C82 PCS + C91 RS(544)",
        "I 17 profili con i 4 assi (standard·reach·mezzo·FEC), il manifest standard/assunzione/unsupported, il margine sulla soglia pre-FEC.",
        "The 17 profiles with 4 axes (standard·reach·medium·FEC), the standard/assumption/unsupported manifest, the pre-FEC threshold margin.",
        "Carica 100GBASE-DR e verifica ogni numero contro la clause citata; poi guarda cosa il banco dichiara di NON coprire.",
        "Load 100GBASE-DR and check every number against the cited clause; then look at what the bench declares it does NOT cover.",
        "Nessun test di conformità: COM e TDECQ seguono subset/strutture di clause, ma senza input, calibrazione, uncertainty e golden vector completi il claim resta NOT ASSESSED.",
        "No compliance testing: COM and TDECQ follow clause subsets/structures, but without complete inputs, calibration, uncertainty, and golden vectors the claim stays NOT ASSESSED.",
        "IEEE 802.3 / OIF-CEI",
        deep_it=("Uno standard non è una tabella di numeri ma un CONTRATTO di interoperabilità: il TX promette una "
                 "maschera (TDECQ, OMA, RLM), il canale un budget (COM, IL), il RX una tolleranza (JTOL, "
                 "sensibilità) — se tutti onorano il contratto, vendor diversi interoperano. Le metriche "
                 "'strane' (TDECQ, COM) esistono perché le misure semplici non predicono la BER: TDECQ chiede "
                 "'quanta potenza extra serve rispetto a un occhio ideale, visto da un RX di riferimento con "
                 "equalizzatore?'. Leggere una clause = capire quale contratto firma ciascun blocco."),
        deep_en=("A standard is not a table of numbers but an interoperability CONTRACT: the TX promises a mask "
                 "(TDECQ, OMA, RLM), the channel a budget (COM, IL), the RX a tolerance (JTOL, sensitivity) — if "
                 "everyone honors the contract, different vendors interoperate. The 'weird' metrics (TDECQ, COM) "
                 "exist because simple measurements do not predict BER: TDECQ asks 'how much extra power vs an "
                 "ideal eye, as seen by a reference RX with an equalizer?'. Reading a clause = understanding which "
                 "contract each block signs."),
        numbers=[("100G/lane ottico", "C140 (DR), 53.125 GBd"),
                 ("100G/lane elettrico", "C162/C163 (ck)"),
                 ("TDECQ DR4", "≤ 3.4 dB"),
                 ("COM minimo", "≥ 3 dB"),
                 ("OIF-CEI", "112G-VSR/MR/LR")],
        actions=[("Profilo 100GBASE-DR", "100GBASE-DR profile",
                  "manifest: cosa è clause e cosa è assunzione", "manifest: what is clause and what is assumption"),
                 ("Margine pre-FEC nel pannello", "Pre-FEC margin in the panel",
                  "la distanza dal cliff KP4 del TUO banco", "your bench's distance from the KP4 cliff")],
        panel="standards"),
]


TOPICS_BY_ID = {t["id"]: t for t in TOPICS}
