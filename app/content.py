"""Testi didattici del simulatore (italiano, con LaTeX inline)."""

SEVEN_QUESTIONS = """
Per **ogni blocco** rispondi sempre alle stesse sette domande:

1. Qual è l'ingresso e in quale dominio si trova?
2. Qual è l'uscita, con quale unità e sample rate?
3. Quale reference plane separa i due blocchi?
4. Quale equazione è identità e quale è approssimazione?
5. Quale rumore o non linearità è inclusa?
6. Quale grafico o metrica può falsificare il modello?
7. Che cosa **non** può essere recuperato dal DSP?
"""

VALIDITY = """
**Confine di validità.** Questo è un framework system-level per imparare e fare
sensitivity analysis. *Non* è un tester TDECQ/SECQ/COM conforme: una misura
normativa richiede clause, pattern, filtri, equalizzatore, clock recovery,
calibrazione e decision rule prescritti. Ogni metrica non normativa è
etichettata **proxy**.
"""

STIMULUS_THEORY = r"""
PAM4 porta **2 bit per simbolo** prima dell'overhead: dire "112G" senza
specificare gross/net, FEC e protocollo è ambiguo. Qui 56 GBd ⇒ 112 Gb/s raw.

Il polinomio pubblico associato a PRBS13Q è

$$G(x)=1+x+x^{2}+x^{12}+x^{13}$$

con periodo massimale $2^{13}-1 = 8191$. Prendendo coppie di bit consecutive e
mappandole sui livelli Gray $\{-1,\,-1/3,\,+1/3,\,+1\}$ si ottengono 8191
simboli con occupazione 2047/2048/2048/2048.

Con $N$ bit e zero errori osservati, l'upper bound one-sided al 95% è
$p_u \approx 3/N$: **zero errori osservati non significa BER zero**.
"""

TX_THEORY = r"""
**TX FFE.** Con coefficienti $c_m$: $x_k=\sum_m c_m a_{k-m}$. I tap non creano
SNR: pre-distorcono lo spettro **consumando swing** — il rapporto di picco
misura l'headroom perso nel DAC/driver.

**DAC.** Quattro trasformazioni separate per non confonderne gli effetti:
$$x[k]\to x_{ZOH}[n]\to Q(x)[n]\to H_{DAC}(f)\,Q(x)[n]$$
Il filtro è una Butterworth in magnitudine a fase zero: isola la banda, non
studia causalità o ritardo assoluto.

**Driver.** Il clipping è **non invertibile**: un equalizzatore può compensare
ISI lineare, non ricostruire i valori cancellati dalle rail.
"""

CHANNEL_THEORY = r"""
Il modello analitico S21-equivalente contiene: perdita skin-like $\propto\sqrt f$
e dielectric-like $\propto f$, ritardo medio causale, ripple di group delay e
un **eco coerente** da mismatch (return loss dichiarato).

La **pulse response** è la risposta a un rettangolo di 1 UI; i sample a distanza
intera di UI separano main cursor, precursor e postcursor — è la base per capire
ISI e per dimensionare FFE/DFE.

Un canale misurato va importato da **Touchstone** e controllato per port order,
impedenza, passività, causalità, reciprocità e uniformità della griglia — la
scheda S2P qui sotto fa questa diagnostica.
"""

MZM_THEORY = r"""
Il laser è CW con la convenzione $P(t)=|E(t)|^2$: un'attenuazione di $L$ dB in
potenza moltiplica il **campo** per $10^{-L/20}$.

MZM push-pull system-level:

$$\Delta\phi(t)=\phi_b+\pi \frac{V(t)}{V_\pi},\qquad
E_o=E_i\,10^{-IL/20}\cos\!\Big(\frac{\Delta\phi}{2}\Big)\,
e^{\,j\alpha\Delta\phi/2}$$

La cosenoide è **non lineare** (compressione verso i picchi); il termine
$e^{j\alpha\Delta\phi/2}$ rende visibile il **chirp**. Prima della fibra il
photodiode non vede la fase; la dispersione può convertirla in distorsione
d'ampiezza.
"""

FIBER_THEORY = r"""
La dispersione cromatica agisce sul **campo**, non sulla potenza:

$$H_{CD}(\omega)=e^{-j\beta_2 L \omega^2/2},\qquad
\beta_2=-\frac{\lambda^2}{2\pi c}D$$

(conversione $\mathrm{ps/(nm\cdot km)}\to\mathrm{s/m^2}$: fattore $10^{-6}$).

Per IM/DD double-sideband chirp-free, in small-signal:

$$H_{IM/DD}(f)\approx\cos\!\Big[\frac{\beta_2 L}{2}(2\pi f)^2\Big]$$

Un **notch dentro Nyquist** è molto più grave di un droop invertibile: nessun
equalizzatore lineare recupera una frequenza che il canale ha annullato. Il
percorso principale propaga il campo complesso e applica square-law al PD; la
formula small-signal serve da controllo fisico.
"""

RX_THEORY = r"""
**Photodiode** — transizione irreversibile:
$$E(t)\to P(t)=|E(t)|^2 \to I(t)=R\,P(t)+I_d$$
Dopo direct detection la fase ottica non è più osservabile.

**Noise budget** (PSD one-sided all'ingresso TIA):
$$S_{shot}=2qI,\qquad S_{TIA}=i_n^2,\qquad S_{RIN}=I^2\cdot 10^{RIN/10}$$
Filtrato dal TIA, l'RMS di ciascuna sorgente è $\sqrt{S\cdot ENBW}$ — la
**equivalent noise bandwidth**, non la banda a −3 dB
(per un polo: $ENBW=\pi f_p/2$).

**CTLE**:
$$H(s)=\frac{1+s/\omega_z}{1+s/\omega_p}\cdot\frac{1}{1+s/\omega_h},
\qquad \omega_z<\omega_p<\omega_h$$
Il rumore che entra *prima* del CTLE viene enfatizzato insieme al segnale:
flatness non è gratis.
"""

ADC_THEORY = r"""
Con $M$ sub-ADC, il sample $n$ usa la lane $m=n \bmod M$. Il modello include
per-lane **gain** $g_m$, **offset** $o_m$, **skew** $\tau_m$, più aperture
jitter sample-to-sample, un TIE comune sinusoidale, quantizzazione e clipping.

Regola architetturale: il DSP userà **solo** `adc_samples_v` — una volta
attraversato l'ADC, quantizzazione e mismatch non possono scomparire dal
percorso. Interpolare in DSP ricombina campioni già degradati.

Nel tone-lab: offset ⇒ righe a $k f_s/M$; gain e skew ⇒ immagini attorno al
tono. $ENOB=(SNDR-1.76)/6.02$ è un indicatore **sinusoidale**, non i bit utili
garantiti per PAM4.
"""

TIMING_THEORY = r"""
**Acquisition**: si prova congiuntamente un intervallo di ritardi interi e fasi
frazionarie interpolando fra i campioni ADC a 2 sps; il minimo dell'MSE residuo
(fit affine solo sul training) dà il punto di lavoro.

**Gardner TED** (2 sps, non richiede decisioni):
$$e_k=(y_{late}-y_{early})\,y_{mid}$$

**Mueller–Müller** lavora a baud rate usando le decisioni: è sensibile a error
propagation. Prima di chiudere un loop, la **S-curve** media verifica segno,
zero e range di cattura. Il loop first-order mostrato rende visibile la
causalità `TED → loop gain → fase`; non modella NCO quantizzato né loop type-II.
"""

EQ_THEORY = r"""
**FSE** (fractionally spaced, 0.5 UI): assorbe errore di fase residuo e
distorsione meglio di un equalizzatore a baud rate. Adattamento NLMS:
$$\mathbf w\leftarrow\mathbf w+\mu\,\frac{e_k\,\mathbf x_k}{\epsilon+\|\mathbf x_k\|^2}$$
Dopo il training i tap sono **congelati**: la valutazione è onesta solo sulla
porzione non vista (validation).

**DFE**: $z_k=y_k-\sum_{m} b_m\hat a_{k-m}$. Non amplifica il rumore, ma una
decisione errata entra nella feedback history — la demo di error propagation
inietta un errore e mostra la risposta causale.
"""

BER_THEORY = r"""
**Hard decision su validation set**: si riportano error count e bit totali, non
solo il rapporto. Con zero errori si riporta l'upper bound $p_u\approx 3/N$
al 95%.

**LLR calibrati** (media e varianza per livello stimate sul training):
$$LLR_b=\log\frac{\sum_{a:b=0}p(y|a)}{\sum_{a:b=1}p(y|a)}$$
LLR positivo = evidenza per bit 0. La **GMI** misura l'informazione soft
raggiungibile sotto il modello del detector — non è automaticamente il
throughput netto dopo un FEC reale.

**Bathtub**: con un record finito il floor statistico è ~$1/N$; il modello
dual-Dirac
$$TJ(BER)=DJ_{pp}+2\,Q^{-1}(1-BER)\,\sigma_{RJ}$$
è un'**estrapolazione dichiarata**, difendibile solo se l'ipotesi di due
cluster gaussiani regge.
"""

EXERCISE_A = """
**Esercizio A — diagnosi del canale.** Prima di muovere gli slider, prevedi il segno dell'effetto:
1. Porta il return loss da 24 a 12 dB: quale cursor cresce?
2. Porta l'eco da 1.35 a 0.4 UI: il danno resta su un solo postcursor?
3. Aumenta solo il ripple di group delay: l'IL cambia? La pulse response cambia?
4. Perché un CTLE non può invertire in modo robusto un notch profondo?
"""

EXERCISE_B = """
**Esercizio B — budget ottico e receiver.**
1. Raddoppia la fibra: separa loss di potenza e penalty da CD.
2. Cambia segno al chirp α: la potenza prima della fibra cambia molto?
3. Aumenta il rumore TIA: quale riga domina il noise budget?
4. Aumenta il peaking CTLE: il canale si appiattisce, ma cosa succede a ENBW e BER?
5. Porta PD o TIA in saturazione: perché l'AGC può nascondere l'overload nell'eye?
"""

EXERCISE_C = """
**Esercizio C — adaptation e interazione dei loop.**
1. Riduci il training a 300 simboli (training_stop=550): i tap generalizzano?
2. Aumenta i tap FSE: l'MSE scende sempre, ma la BER di validation migliora sempre?
3. Disattiva il CTLE (zero≈polo) e osserva quale blocco assorbe il costo.
4. CTLE, CDR e DFE inseguono la stessa metrica: loop simultanei possono
   diventare instabili anche se ciascuno, isolato, è stabile.
"""

GLOSSARY = {
    "UI": "Unit Interval, 1/baud rate. A 56 GBd: 17.86 ps.",
    "Reference plane": "Punto fisico/logico a cui è riferita una misura: il nome del nodo non basta.",
    "ISI": "Inter-Symbol Interference: energia di un simbolo che cade nei sample di altri simboli (cursor).",
    "ENBW": "Equivalent Noise Bandwidth: ∫|H|²df. Per un polo singolo = π·f₃dB/2 ≠ banda a −3 dB.",
    "OMA": "Optical Modulation Amplitude: P(livello alto) − P(livello basso).",
    "RIN": "Relative Intensity Noise del laser, PSD relativa alla potenza media [dB/Hz].",
    "Chirp (α)": "Modulazione di fase parassita che accompagna la modulazione di ampiezza; con la CD diventa distorsione.",
    "CD": "Chromatic Dispersion: velocità di gruppo dipendente da λ; sul campo H=exp(−jβ₂Lω²/2).",
    "TIA": "Transimpedance Amplifier: converte la fotocorrente in tensione (Z_T in Ω).",
    "CTLE": "Continuous-Time Linear Equalizer: zero+polo che alzano le alte frequenze (e il rumore).",
    "FSE": "Fractionally-Spaced Equalizer: FFE con tap a frazione di UI (qui 0.5 UI).",
    "DFE": "Decision-Feedback Equalizer: sottrae postcursor ISI usando le decisioni già emesse.",
    "TED / S-curve": "Timing Error Detector; la S-curve è la sua media vs fase: segno, zero, range di cattura.",
    "BER / SER": "Bit/Symbol Error Ratio, sempre con conteggio errori e intervallo di confidenza.",
    "LLR": "Log-Likelihood Ratio per bit; positivo = evidenza per bit 0.",
    "GMI": "Generalized Mutual Information: bit/simbolo raggiungibili con quel detector soft.",
    "Bathtub": "BER vs fase di campionamento; con record finito il floor è ~1/N.",
    "Dual-Dirac": "Modello RJ gaussiano + DJ a due delta per estrapolare il total jitter.",
    "PRBS13Q": "Pattern PAM4 da PRBS13 (periodo 8191) usato per test 112G.",
    "RLM": "Ratio of Level Mismatch: uniformità delle spaziature PAM4 (qui solo proxy).",
    "TDECQ": "Transmitter Dispersion Eye Closure Quaternary: metrica normativa NON implementata qui (proxy dichiarati).",
}
