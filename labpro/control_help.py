"""Metadati bilingui dei controlli del banco.

La GUI li usa per la card ``?`` accanto a ogni manopola.  Il catalogo copre
anche i campi non esposti come slider: in questo modo una nuova opzione del
motore non può nascere senza piano di riferimento e spiegazione fisica.
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


_add("symbol_rate_hz analog_sps n_symbols", "Stimulus / acquisition", "PPG → analog grid",
     "definisce la scala temporale e la lunghezza statistica del record; cambia risoluzione, UI e frequenze normalizzate, non una tensione fisica a monte.",
     "sets the time scale and record statistics; it changes resolution, UI, and normalized frequencies, not an upstream physical voltage.",
     "UI=1/Rs; fs,analog=Rs·sps")
_add("prbs_order pattern", "PPG", "PCS/PPG output",
     "sceglie la sequenza realmente serializzata. Periodo, run length e spettro modificano ISI, DDJ e pattern lock.",
     "selects the sequence actually serialized. Period, run length, and spectrum change ISI, DDJ, and pattern lock.",
     "PRBSn period=2ⁿ−1")
_add("custom_pattern_hex", "PPG pattern editor", "PCS/PPG output",
     "definisce una sequenza utente di 1..4096 byte esadecimali, ripetuta ciclicamente e serializzata MSB-first. Spazi, underscore e due punti sono solo separatori. È un pattern di laboratorio, non un pattern di clause.",
     "defines a user sequence of 1..4096 hexadecimal bytes, repeated cyclically and serialized MSB first. Spaces, underscores, and colons are visual separators only. It is a lab pattern, not a clause pattern.",
     "period = 8·Nbyte bit", "pattern = custom_hex")
_add("modulation pam4_mapping", "Mapper", "mapper output",
     "sceglie livelli e label di bit; Gray limita a un bit l'errore fra livelli adiacenti, ma non migliora l'occhio analogico.",
     "selects levels and bit labels; Gray limits adjacent-level errors to one bit but does not improve the analog eye.")
_add("l2_streams", "Traffic generator", "PPG payload (frames)",
     "generatore multi-stream stile Xena: 1..4 flussi round-robin, ognuno con stream-id, sequence e frame size propri (64/512/1024 B per gli stream extra). L'analyzer attribuisce ok/FCS/persi PER stream — i frame grandi soffrono più bit error per frame. Con FEC in-path servono record lunghi perché un round intero cada in validation.",
     "Xena-style multi-stream generator: 1..4 round-robin flows, each with its own stream-id, sequence space, and frame size (64/512/1024 B for the extra streams). The analyzer attributes ok/FCS/lost PER stream — large frames take more bit errors per frame. With in-path FEC, long records are needed for a full round to fall inside validation.",
     "round = 1 frame per stream", "pattern = eth")
_add("pvt_process pvt_vdd_pct pvt_temp_c", "RX PVT", "TIA/CTLE/ADC/CDR (receiver only)",
     "corner di processo (SS/TT/FF), supply e temperatura del die RX. Sensibilità del primo ordine dichiarate: banda dei device (SS −15%, mobilità ≈ −0.15%/°C, −10% VDD ≈ −5% BW), rumore termico ∝ √T assoluta, mismatch ADC peggiore ai corner e con |ΔT|, guadagno del loop CDR coi device. Il worst case classico è SS + caldo + VDD basso: la CTLE perde peaking proprio dove serve. Default TT/0%/25 °C = fattori identità (baseline intatta).",
     "RX die process corner (SS/TT/FF), supply, and temperature. Declared first-order sensitivities: device bandwidth (SS −15%, mobility ≈ −0.15%/°C, −10% VDD ≈ −5% BW), thermal noise ∝ √(absolute T), ADC mismatch worse at corners and with |ΔT|, CDR loop gain with device speed. The classic worst case is SS + hot + low VDD: the CTLE loses peaking exactly where it is needed. Default TT/0%/25 °C = identity factors (baseline intact).",
     "bw=corner·(1−0.0015ΔT)·(1+0.005ΔV%); noise=√(T/298K)")
_add("fec_interleave", "FEC", "RS symbol mux on the line",
     "interleaving di codeword a livello di simbolo RS (802.3ck/dj): i simboli di 2/4 codeword si alternano sulla linea, così un burst di L simboli ne colpisce ~L/depth per codeword. Con depth>1 serve un record lungo (≥16k simboli) perché un gruppo intero cada in validation.",
     "codeword interleaving at the RS-symbol level (802.3ck/dj): symbols of 2/4 codewords alternate on the line, so an L-symbol burst hits ~L/depth per codeword. With depth>1 a long record (≥16k symbols) is needed for a full group to fall inside validation.",
     "burst L → ~L/depth per codeword", "fec_mode ≠ none")
_add("fec_mode", "FEC", "PCS before mapper / after DEMUX",
     "inserisce davvero encoder e decoder nel datapath; cambia overhead, copertura dei codeword e BER post-FEC.",
     "inserts the encoder and decoder in the datapath; changes overhead, codeword coverage, and post-FEC BER.",
     "KP4 RS(544,514), t=15; KR4 RS(528,514), t=7")
_add("l2_frame_bytes l2_ipg_bytes", "Ethernet traffic", "MAC/PCS stimulus",
     "controlla serializzazione e carico offerto dei frame L2 con preambolo, sequence number e FCS reali.",
     "controls serialization and offered load of real L2 frames with preamble, sequence number, and FCS.")
_add("err_insert_bits err_insert_burst", "BERT PPG", "TX bits after reference copy",
     "inverte bit dopo aver conservato il riferimento dell'error detector; burst raggruppa le inversioni consecutive.",
     "flips bits after preserving the error-detector reference; burst mode groups flips consecutively.")

_add("tx_rj_rms_fs", "TX PLL", "serializer time base",
     "aggiunge TIE gaussiano RMS indipendente a ogni UI; allarga le code senza limite deterministico. Sul Q-scale le code diventano rette di pendenza 1/σ e il TJ estrapola come TJ(p)=2·Q_p·σ+DJ(δδ); gli RJ indipendenti si sommano in quadratura, σ_tot=√Σσᵢ² (Derickson & Müller §2.4-2.5).",
     "adds independent Gaussian RMS TIE to each UI; it broadens unbounded tails. On the Q scale the tails become straight lines of slope 1/σ and TJ extrapolates as TJ(p)=2·Q_p·σ+DJ(δδ); independent RJs add in quadrature, σ_tot=√Σσᵢ² (Derickson & Müller §2.4-2.5).",
     "σUI=RJfs·10⁻¹⁵/UI; TJ(p)=2Q_p·σ+DJ(δδ)")
_add("tx_pj_amp_ui tx_pj_freq_mhz", "TX PLL", "serializer time base",
     "imposta ampiezza e frequenza del tono sinusoidale di jitter; deve apparire alla stessa frequenza nello spettro TIE.",
     "sets sinusoidal jitter amplitude and frequency; the same tone must appear in the TIE spectrum.", "TIE=A·sin(2πfjt)")
_add("tx_dcd_pct", "TX PLL", "serializer edges",
     "alterna gli edge di ±DCD/2 e separa le popolazioni pari/dispari del TIE.",
     "alternates edges by ±DCD/2 and separates even/odd TIE populations.")
_add("tx_buj_amp_ui", "TX PLL / BERT", "serializer time base",
     "aggiunge jitter bounded non correlato, generato da PRBS indipendente e filtrato.",
     "adds bounded uncorrelated jitter from an independent filtered PRBS.")
_add("tx_ssc_ppm tx_ssc_khz", "TX PLL", "serializer frequency/phase",
     "modula lentamente la frequenza in down-spread; il TIE è l'integrale della deviazione e il CDR deve inseguirlo.",
     "slowly down-spreads frequency; TIE is the integrated deviation and the CDR must track it.")

_add("tx_ffe_taps", "TX FIR", "symbol stream before DAC",
     "pesa pre/main/post-cursor reali. Più enfasi riduce ISI ma consuma swing e può causare clipping.",
     "weights real pre/main/post-cursors. More emphasis reduces ISI but costs swing and can clip.",
     "H(eʲω)=Σ c[k]e⁻ʲωk")
_add("dac_bits dac_full_scale_vpp", "DAC", "DAC output",
     "imposta quantizzazione e fondo scala: pochi bit aumentano rumore di quantizzazione, poco headroom clippa.",
     "sets quantization and full scale: fewer bits add quantization noise, insufficient headroom clips.")
_add("dac_bw_hz driver_bw_hz", "TX analog", "DAC / driver output",
     "imposta la banda −3 dB del filtro analogico; ridurla rallenta gli edge e aumenta ISI.",
     "sets analog −3 dB bandwidth; reducing it slows edges and increases ISI.")
_add("driver_gain_v_per_unit driver_clip_v", "Driver", "driver differential output",
     "scala il drive e ne limita le rail. Il clipping è non lineare e non recuperabile a valle.",
     "scales the drive and limits its rails. Clipping is nonlinear and cannot be recovered downstream.")
_add("causal_filters", "Analog filters", "all selected analog blocks",
     "sceglie fase zero didattica o risposta causale con la stessa magnitudine; solo la modalità causale ha group delay fisico.",
     "selects educational zero phase or a causal response with the same magnitude; only causal mode has physical group delay.")

_add("pn_skew_ps pn_gain_mismatch_pct", "Differential fixture", "driver P/N pins",
     "introduce skew o sbilanciamento fra i rami; produce conversione DM↔CM e, con skew, un notch differenziale.",
     "introduces leg skew or imbalance; it creates DM↔CM conversion and, with skew, a differential notch.", "fnotch=1/(2τ)")
_add("vcm_offset_v vcm_noise_mv", "Common-mode source", "driver P/N pins",
     "aggiunge modo comune DC o casuale. In un ricevitore differenziale ideale si cancella; mismatch e single-ended lo rendono osservabile.",
     "adds DC or random common mode. An ideal differential receiver rejects it; mismatch and single-ended probing expose it.")
_add("tx_diff_noise_mv", "BERT stress", "driver differential pins",
     "inietta rumore bianco differenziale dopo il driver ideale, quindi non altera il suo nodo diagnostico a monte.",
     "injects differential white noise after the ideal driver, leaving its upstream diagnostic node unchanged.")
_add("electrical_drive_mode", "Probe / drive selector", "channel or modulator input",
     "sceglie Vp−Vn, Vp o Vn come segnale realmente consumato dal blocco successivo.",
     "selects Vp−Vn, Vp, or Vn as the signal actually consumed by the next block.")

_add("link_medium", "Link topology", "channel output",
     "commuta atomicamente tra percorso rame verso AFE e percorso ottico verso modulatore, fibra e PD.",
     "atomically switches between copper-to-AFE and optical modulator/fiber/PD paths.")
_add("channel_il_nyquist_db", "Electrical channel", "smooth channel S21",
     "imposta la perdita della componente liscia a Nyquist; l'S21 totale include anche l'eco da return loss e può differire.",
     "sets smooth-component loss at Nyquist; total S21 also contains return-loss echo and can differ.", "ILsmooth(fN)=setting")
_add("channel_delay_ps group_delay_ripple_ps", "Electrical channel", "channel S21 phase",
     "modifica fase e group delay senza cambiare la perdita liscia; il ripple crea DDJ/ISI dispersivo.",
     "changes phase and group delay without changing smooth loss; ripple creates dispersive DDJ/ISI.")
_add("return_loss_db echo_delay_ui", "Electrical channel", "channel S21 mismatch term",
     "controlla ampiezza e ritardo dell'eco di mismatch; modifica il ripple dell'S21 totale e i post/pre-cursor.",
     "controls mismatch-echo amplitude and delay; changes total-S21 ripple and pre/post-cursors.", "|Γ|=10⁻ᴿᴸ/²⁰")
_add("xtalk_next_db xtalk_fext_db", "Aggressor", "channel near/far end",
     "accoppia un PRBS indipendente. 0 dB nella UI significa OFF; valori negativi abilitano lo stress relativo a Nyquist.",
     "couples an independent PRBS. UI value 0 dB means OFF; negative values enable Nyquist-referenced stress.")
_add("s2p_text s2p_name use_s2p_channel s4p_pairs", "Measured channel", "channel S-parameter plane",
     "carica e seleziona S21/SDD21 misurato; il mapping S4P determina le coppie differenziali e la diagnostica SCD21.",
     "loads and selects measured S21/SDD21; S4P mapping determines differential pairs and SCD21 diagnostics.")

_add("optical_modulator laser_type", "Optical transmitter", "E/O",
     "seleziona atomicamente MZM+CW, EML, DML o VCSEL compatibili; cambia la legge large-signal, il chirp e la fibra ammessa.",
     "atomically selects compatible MZM+CW, EML, DML, or VCSEL; changes large-signal law, chirp, and allowed fiber.")
_add("laser_dbm", "Laser", "laser output",
     "imposta la potenza ottica media disponibile prima delle perdite; varia linearmente la fotocorrente e quadraticamente la potenza elettrica del segnale.",
     "sets optical power before losses; photocurrent changes linearly and electrical signal power quadratically.", "P[W]=1mW·10^(dBm/10)")
_add("laser_linewidth_mhz", "Laser", "optical field phase",
     "imposta la linewidth Lorentziana tramite fase Wiener; conta quando la dispersione converte fase/frequenza in intensità.",
     "sets Lorentzian linewidth through Wiener phase; matters when dispersion converts phase/frequency into intensity.")
_add("vpi_v mzm_bias_rad", "MZM", "modulator transfer",
     "controlla scala e punto di lavoro della transfer cos². La quadratura massimizza la linearità small-signal, non necessariamente ER.",
     "controls scale and bias of the cos² transfer. Quadrature maximizes small-signal linearity, not necessarily ER.", "Pout=Pin·IL·cos²[(bias+πV/Vπ)/2]", "optical_modulator=mzm")
_add("mzm_bw_hz mzm_il_db chirp_alpha", "MZM", "MZM output field",
     "controlla banda, perdita e chirp di fase del modulatore esterno.",
     "controls bandwidth, insertion loss, and phase chirp of the external modulator.", active="optical_modulator=mzm")
_add("eml_bw_hz eml_er_db eml_il_db eml_chirp_alpha", "EML", "EML output field",
     "controlla transfer a ER finito, perdita, banda e chirp Henry del modello EML large-signal.",
     "controls finite-ER transfer, loss, bandwidth, and Henry chirp in the EML large-signal model.", active="optical_modulator=eml")
_add("direct_laser_bw_hz direct_laser_er_db direct_laser_chirp_alpha", "DML / VCSEL", "direct laser output",
     "controlla banda, ER e chirp del laser direttamente modulato.",
     "controls bandwidth, ER, and chirp of the directly modulated laser.", active="optical_modulator=dml|vcsel")
_add("coupling_il_db fiber_loss_db_km fiber_km", "Optical path", "fiber launch → PD",
     "applica perdita di accoppiamento e attenuazione distribuita; la lunghezza scala anche CD, PMD, Kerr e banda modale.",
     "applies coupling and distributed attenuation; length also scales CD, PMD, Kerr, and modal bandwidth.", "Ploss,dB=ILcoupling+αL")
_add("wavelength_nm dispersion_ps_nm_km dispersion_slope_ps_nm2_km", "SMF dispersion", "optical field in fiber",
     "determina β2/β3 e il fading IM/DD; un nullo nella banda non è invertibile da un equalizzatore lineare.",
     "sets β2/β3 and IM/DD fading; an in-band null cannot be inverted by a linear equalizer.", "fnull≈√[c/(2λ²|D|L)]", "fiber_type=smf")
_add("pmd_ps_sqrt_km pmd_power_split", "SMF PMD", "two polarization powers",
     "imposta DGD RMS e ripartizione di potenza dei due PSP nel proxy di primo ordine.",
     "sets RMS DGD and principal-state power split in the first-order proxy.", "DGD=DPMD√L", "fiber_type=smf")
_add("fiber_gamma_w_inv_km", "SMF Kerr", "optical field phase",
     "imposta l'automodulazione di fase con effective length attenuata; ai livelli interconnect è normalmente piccola.",
     "sets self-phase modulation with attenuation-aware effective length; normally small at interconnect powers.", "φNL=γLeffP")
_add("fiber_type mmf_modal_bw_mhz_km", "Fiber", "fiber propagation",
     "sceglie SMF dispersiva o MMF con prodotto banda-distanza; il proxy MMF non sostituisce un modello DMD/launch completo.",
     "selects dispersive SMF or bandwidth-distance MMF; the MMF proxy does not replace a full DMD/launch model.", "BWmodal=(BW·km)/L")

_add("pd_responsivity_a_w pd_dark_current_a", "Photodiode", "PD current",
     "converte la potenza ottica rilevata in corrente e aggiunge la dark current prima di shot noise e saturazione.",
     "converts detected optical power to current and adds dark current before shot noise and saturation.", "I=R·P+Idark; Sshot=2qI")
_add("pd_bw_hz pd_saturation_a", "Photodiode", "PD current",
     "limita banda e corrente massima del PD; la saturazione schiaccia i livelli superiori prima del TIA.",
     "limits PD bandwidth and maximum current; saturation crushes upper levels before the TIA.")
_add("rin_db_hz tia_noise_a_rt_hz", "RX noise", "TIA input-referred current",
     "imposta densità RIN e rumore bianco input-referred, integrate sulla ENBW effettiva.",
     "sets RIN and input-referred white-noise density, integrated over actual ENBW.", "σ²=∫S(f)|H(f)|²df")
_add("tia_transimpedance_ohm tia_vga_range_db tia_headroom_ratio", "TIA VGA", "TIA output",
     "imposta ZT massima, attenuazione disponibile e target di rail. La ZT effettiva è mostrata e l'overload resta reale oltre il range.",
     "sets maximum ZT, available attenuation, and rail target. Effective ZT is reported and overload remains real beyond range.")
_add("tia_bw_hz tia_clip_v", "TIA / AFE", "TIA/AFE output",
     "imposta banda −3 dB e rail di uscita; rumore e segnale attraversano lo stesso filtro.",
     "sets −3 dB bandwidth and output rails; noise and signal traverse the same filter.")
_add("agc_target_rms_v agc_min_gain_db agc_max_gain_db", "AGC", "AGC output",
     "richiede un RMS ma applica limiti di guadagno reali; quando il target è irraggiungibile la card segnala LIMIT.",
     "requests an RMS while enforcing physical gain limits; the card reports LIMIT when target is unreachable.", "G=clip(Vtarget/Vrms,Gmin,Gmax)")

_add("ctle_zero_hz ctle_pole_hz ctle_hf_pole_hz ctle_zeros_hz ctle_poles_hz ctle_dc_gain_db", "CTLE", "CTLE output",
     "configura il prodotto reale di sezioni zero/polo e il guadagno DC. Il boost riduce ISI ma aumenta rumore e può peggiorare il link.",
     "configures the actual zero/pole product and DC gain. Boost reduces ISI but enhances noise and can worsen the link.", "H(s)=GDC·Π(1+s/fz)/Π(1+s/fp)")
_add("adc_sps adc_bits adc_full_scale_vpp adc_phase_ui adc_jitter_rms_fs", "ADC", "A/D sampling plane",
     "controlla rate, quantizzazione, full scale, fase e jitter di apertura del campionatore nel datapath.",
     "controls sample rate, quantization, full scale, phase, and aperture jitter in the datapath.")
_add("adc_interleaves adc_gain_mismatch_rms adc_offset_mismatch_rms_v adc_skew_mismatch_rms_fs", "Time-interleaved ADC", "ADC sub-converters",
     "imposta numero di slice e mismatch statici; genera spur periodici legati a fs/M.",
     "sets slice count and static mismatches; creates periodic spurs tied to fs/M.")
_add("cdr_mode cdr_bw cdr_damping rx_ppm_offset", "CDR", "recovered sampling clock",
     "sceglie TED/loop e clock offset. Banda e damping scambiano tracking, jitter transfer, peaking e rumore.",
     "selects TED/loop and clock offset. Bandwidth and damping trade tracking, jitter transfer, peaking, and noise.")
_add("fse_taps dfe_taps training_start training_stop", "RX DSP", "post-ADC equalization",
     "imposta memoria e finestra di adattamento; la validation resta separata dal training per evitare una BER ottimistica.",
     "sets equalizer memory and adaptation window; validation stays separate from training to avoid optimistic BER.")


# Ogni help di manopola include anche una procedura paired e il vincolo di
# località. Sono informazioni operative: aiutano a distinguere un effetto
# fisico reale da una variazione casuale fra seed o da una manopola scollegata.
for _field, _item in CONTROL_HELP.items():
    _plane = _item["plane"]
    _active = _item["active"]
    _item.update({
        "observe_it": (
            f"Osserva {_plane}: waveform, metrica primaria e checkpoint a "
            "valle devono reagire; i piani a monte devono restare invariati."),
        "observe_en": (
            f"Observe {_plane}: waveform, primary metric, and downstream "
            "checkpoints must react; upstream planes must remain unchanged."),
        "verify_it": (
            "Confronto paired: stesso seed e stessi prerequisiti, varia solo "
            f"{_field}; ripeti vicino al default e a un valore di stress."),
        "verify_en": (
            "Paired check: same seed and prerequisites, vary only "
            f"{_field}; repeat near default and at a stress value."),
        "boundary_it": (
            f"Attivo quando: {_active}. Il risultato è del modello system-level; "
            "un limite di standard vale solo dentro una procedura versionata."),
        "boundary_en": (
            f"Active when: {_active}. This is a system-level model result; a "
            "standard limit applies only inside a versioned procedure."),
    })
