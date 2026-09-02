"""Configurazione del link e preset didattici.

`LinkConfig` è frozen (immutabile e hashable) così la GUI può usarla come
chiave di cache. I default coincidono con il builder v7.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, replace, fields


@dataclass(frozen=True)
class LinkConfig:
    # Stimolo / simulazione
    symbol_rate_hz: float = 56e9
    analog_sps: int = 16
    n_symbols: int = 8191
    prbs_order: int = 13          # 7, 9, 11, 13, 15, 23, 31
    pattern: str = "prbs"         # prbs | ssprq | custom_hex | clock* | eth
    custom_pattern_hex: str = "A5C3F00F"  # byte PPG utente, trasmessi MSB-first
    l2_frame_bytes: int = 256     # dimensione frame per pattern "eth"
    l2_ipg_bytes: int = 12        # inter-packet gap (rate control del PPG)
    l2_streams: int = 1           # generatore multi-stream stile Xena (1..4)
    modulation: str = "PAM4"      # "PAM4" | "NRZ"
    pam4_mapping: str = "gray"    # "gray" | "binary" (ignorato per NRZ)
    fec_mode: str = "none"        # "none" | "kp4" RS(544,514) | "kr4" RS(528,514)
    fec_interleave: int = 1       # codeword interleaving 1|2|4 (802.3ck/dj)
                                  # con kp4/kr4 l'encoder è NEL percorso TX e il
                                  # decoder gira sui frame interamente coperti

    # TX clock (PLL/serializer) — jitter iniettato sul time base del DAC
    tx_rj_rms_fs: float = 0.0     # random jitter RMS [fs]
    tx_pj_amp_ui: float = 0.0     # periodic jitter, ampiezza picco [UI]
    tx_pj_freq_mhz: float = 200.0  # frequenza del PJ sinusoidale
    tx_dcd_pct: float = 0.0       # duty-cycle distortion [% di UI, alternato ±/2]
    tx_buj_amp_ui: float = 0.0    # BUJ: jitter bounded non correlato (PRBS filtrata) [UI pk]
    tx_ssc_ppm: float = 0.0       # SSC down-spread [ppm picco] (triangolare)
    tx_ssc_khz: float = 33.0      # frequenza di modulazione SSC

    # TX
    tx_ffe_taps: tuple = (-0.08, 1.00, -0.08)
    dac_bits: int = 8
    dac_full_scale_vpp: float = 2.6
    dac_bw_hz: float = 35e9
    driver_gain_v_per_unit: float = 0.65
    driver_bw_hz: float = 40e9
    driver_clip_v: float = 0.95

    # Coppia differenziale P/N all'uscita del driver (default: ideale)
    pn_skew_ps: float = 0.0            # ritardo N rispetto a P
    pn_gain_mismatch_pct: float = 0.0  # sbilanciamento di ampiezza P vs N
    vcm_offset_v: float = 0.0          # common-mode DC
    vcm_noise_mv: float = 0.0          # rumore common-mode bianco (RMS)
    tx_diff_noise_mv: float = 0.0      # stress white-noise differenziale RMS

    # Reference plane che alimenta davvero canale/modulatore. Il default
    # differenziale conserva la baseline storica; i due modi single-ended
    # usano il ramo fisico P o N, quindi includono offset/rumore common-mode.
    electrical_drive_mode: str = "differential"  # differential | single_ended_p | single_ended_n

    # Mezzo del link: "optical" = catena completa MZM/fibra/PD;
    # "copper" = elettrico puro (KR/CR/C2M): canale → RX AFE, niente ottica
    link_medium: str = "optical"

    # Crosstalk da aggressore sullo stesso connettore (0 = off)
    xtalk_next_db: float = 0.0     # accoppiamento NEXT @Nyquist [dB, >0 = off]
    xtalk_fext_db: float = 0.0     # accoppiamento FEXT @Nyquist [dB, >0 = off]

    # OUTPUT enable dello stadio TX (stile PPG/MP1900A): False = il driver
    # non pilota nulla (mute elettrico); la sorgente ottica resta accesa
    tx_output_on: bool = True

    # BERT: bit del pattern invertiti al TX rispetto al riferimento dell'ED
    err_insert_bits: int = 0
    err_insert_burst: bool = False   # True: bit consecutivi (burst singolo)
    # dove cadono i bit invertiti: random | msb | lsb (lane PAM4) |
    # rs_symbol (gruppi allineati GF(2^10): 1 simbolo RS per gruppo)
    err_insert_target: str = "random"

    # Canale elettrico
    channel_il_nyquist_db: float = 12.0
    channel_delay_ps: float = 18.0
    group_delay_ripple_ps: float = 1.2
    return_loss_db: float = 18.0
    echo_delay_ui: float = 1.35

    # Trasmettitore ottico e fibra
    optical_modulator: str = "mzm"     # mzm | eml | dml | vcsel
    laser_type: str = "cw_dfb_external"  # accoppiato all'architettura sopra
    laser_dbm: float = 3.0
    laser_linewidth_mhz: float = 0.0  # Lorentzian linewidth; 0 conserva baseline
    vpi_v: float = 3.5
    mzm_bias_rad: float = 1.5707963267948966  # pi/2, quadratura
    mzm_bw_hz: float = 40e9
    mzm_il_db: float = 4.5
    chirp_alpha: float = 0.4
    eml_bw_hz: float = 42e9
    # Escursione elettrica picco-picco che porta la transfer normalizzata
    # EML/DML/VCSEL da 0 a 1.  E una sensibilita di sistema esplicita: non
    # va stimata dal record, altrimenti il gain del driver si cancella e
    # l'OMA resta invariata anche cambiando realmente lo swing TX.
    optical_drive_vpp_v: float = 0.55
    eml_er_db: float = 6.0
    eml_il_db: float = 3.0
    eml_chirp_alpha: float = 2.0
    direct_laser_bw_hz: float = 32e9
    direct_laser_er_db: float = 5.0
    direct_laser_chirp_alpha: float = 3.0
    coupling_il_db: float = 2.0
    wavelength_nm: float = 1550.0
    fiber_km: float = 2.0
    dispersion_ps_nm_km: float = 17.0
    dispersion_slope_ps_nm2_km: float = 0.08
    pmd_ps_sqrt_km: float = 0.05
    pmd_power_split: float = 0.5
    fiber_gamma_w_inv_km: float = 1.3
    fiber_loss_db_km: float = 0.20
    fiber_type: str = "smf"            # smf | mmf
    mmf_modal_bw_mhz_km: float = 4700.0

    # Ricevitore ottico
    pd_responsivity_a_w: float = 0.80
    pd_dark_current_a: float = 2e-9
    pd_bw_hz: float = 42e9
    pd_saturation_a: float = 1.5e-3
    rin_db_hz: float = -145.0
    tia_noise_a_rt_hz: float = 28e-12
    tia_transimpedance_ohm: float = 2500.0
    tia_vga_range_db: float = 10.0
    tia_headroom_ratio: float = 0.70
    tia_bw_hz: float = 35e9
    tia_clip_v: float = 0.8
    agc_target_rms_v: float = 0.22
    # PVT del ricevitore (process corner, supply, temperatura). Default =
    # TT / 0% / 25 °C: fattori identità, baseline intatta. Le sensibilità
    # sono del PRIMO ORDINE e dichiarate (i valori veri sono design-specific)
    pvt_process: str = "tt"       # "ss" | "tt" | "ff"
    pvt_vdd_pct: float = 0.0      # deviazione supply [-10..+10] %
    pvt_temp_c: float = 25.0      # temperatura die [-40..125] °C
    agc_min_gain_db: float = -12.0
    agc_max_gain_db: float = 24.0

    # CTLE / ADC
    ctle_zero_hz: float = 9e9
    ctle_pole_hz: float = 28e9
    ctle_hf_pole_hz: float = 55e9
    ctle_dc_gain_db: float = 0.0
    # Topologia CTLE estesa. Tuple vuote = usa i tre campi legacy sopra
    # (1 zero / 2 poli), cosi preset e sessioni precedenti restano identici.
    # Se valorizzate, il prodotto di tutte le sezioni entra davvero nel path.
    ctle_zeros_hz: tuple = ()
    ctle_poles_hz: tuple = ()
    adc_sps: int = 2
    adc_bits: int = 7
    adc_full_scale_vpp: float = 1.4
    adc_phase_ui: float = 0.08
    adc_jitter_rms_fs: float = 90.0
    adc_interleaves: int = 4
    adc_gain_mismatch_rms: float = 0.006
    adc_offset_mismatch_rms_v: float = 1.2e-3
    adc_skew_mismatch_rms_fs: float = 35.0
    # --- architettura di nuova generazione (112G/224G ADC-based RX) --------
    # rank di track&hold in testa all'array SAR: i lane condividono skew e
    # banda del proprio rank (1 = array flat, comportamento storico)
    adc_ranks: int = 1
    # banda del front-end T/H (1° ordine); 0 = disattivo (storico)
    adc_frontend_bw_hz: float = 0.0
    # spread rms della banda fra i rank: mismatch DIPENDENTE dalla frequenza,
    # NON correggibile dalla calibrazione gain/offset/skew (servono FFE/lane)
    adc_bw_mismatch_pct: float = 0.0
    # calibrazione dell'array: foreground = residui statici che scalano col
    # PVT (storico); background = insegue PVT/temperatura; off = SAR grezzo
    adc_cal_mode: str = "foreground"
    # rumore termico input-referred dell'ADC (prima della quantizzazione)
    adc_noise_rms_mv: float = 0.0

    # CDR (timing recovery NEL datapath; "oracle" è la modalità idealizzata
    # dichiarata: fase dal minimo MSE con i simboli noti)
    cdr_mode: str = "gardner"     # "gardner" | "mm" | "oracle"
    cdr_bw: float = 0.0015        # banda del loop normalizzata al baud rate
    cdr_damping: float = 1.0      # smorzamento zeta del loop PI
    # (f_RX-f_TX)/f_TX in ppm: positivo = clock RX fisicamente piu veloce.
    rx_ppm_offset: float = 0.0

    # DSP
    fse_taps: int = 17
    dfe_taps: int = 5
    training_start: int = 250
    training_stop: int = 3000

    # Canale elettrico misurato (Touchstone S2P): se use_s2p_channel=True e
    # s2p_text non vuoto, S21 sostituisce il modello analitico nel main path.
    s2p_text: str = ""
    s2p_name: str = ""
    use_s2p_channel: bool = False
    s4p_pairs: str = "13_24"      # mapping porte s4p: "13_24" o "12_34"

    # Filtri DAC/driver/MZM/PD/TIA: False = solo magnitudine (fase zero,
    # scelta didattica del v7); True = Butterworth causale con fase reale.
    causal_filters: bool = False

    @property
    def pvt_factors(self):
        """Fattori PVT del ricevitore (primo ordine, dichiarati):
        - bw: velocità dei device — corner (SS −15% / FF +15%), mobilità
          ∝ T^-1.5 (≈ −0.15%/°C) e supply (−10% VDD ≈ −5% BW);
        - noise: termico ∝ √T assoluta (4kTR);
        - mismatch: offset/gain ADC peggiori ai corner e con |ΔT|;
        - cdr_gain: guadagno del loop (VCO/charge pump) coi device."""
        corner = {"ss": 0.85, "tt": 1.0, "ff": 1.15}[self.pvt_process]
        d_t = self.pvt_temp_c - 25.0
        bw = corner * (1.0 - 0.0015 * d_t) * (1.0 + 0.005 * self.pvt_vdd_pct)
        noise = (max(self.pvt_temp_c + 273.15, 1.0) / 298.15) ** 0.5
        mismatch = (1.0 + 0.006 * abs(d_t)) * (
            1.3 if self.pvt_process != "tt" else 1.0)
        # dark current del PD: Arrhenius, raddoppia ogni ~9 °C (fisica
        # standard dei fotodiodi InGaAs) — a 125 °C vale ~×2000
        dark = 2.0 ** (d_t / 9.0)
        return {"bw": bw, "noise": noise, "mismatch": mismatch, "dark": dark,
                "cdr_gain": corner * (1.0 + 0.004 * self.pvt_vdd_pct)}

    @property
    def ui_s(self):
        return 1.0 / self.symbol_rate_hz

    @property
    def nyquist_hz(self):
        return 0.5 * self.symbol_rate_hz

    @property
    def fs_analog_hz(self):
        return self.symbol_rate_hz * self.analog_sps

    @property
    def fs_adc_hz(self):
        return self.symbol_rate_hz * self.adc_sps

    @property
    def ctle_zeros_effective_hz(self):
        return (tuple(float(v) for v in self.ctle_zeros_hz)
                if self.ctle_zeros_hz else (float(self.ctle_zero_hz),))

    @property
    def ctle_poles_effective_hz(self):
        return (tuple(float(v) for v in self.ctle_poles_hz)
                if self.ctle_poles_hz else
                (float(self.ctle_pole_hz), float(self.ctle_hf_pole_hz)))

    def validate(self):
        problems = _validate_types_and_ranges(self)
        if problems:
            # Con un tipo sbagliato le regole semantiche sotto lancerebbero
            # TypeError: si riporta prima il problema di schema.
            return problems
        if self.analog_sps % self.adc_sps:
            problems.append("analog_sps deve essere multiplo di adc_sps")
        if self.prbs_order not in (7, 9, 11, 13, 15, 23, 31):
            problems.append("prbs_order deve essere 7/9/11/13/15/23/31")
        if self.modulation not in ("PAM4", "NRZ"):
            problems.append("modulation deve essere PAM4 o NRZ")
        if self.pam4_mapping not in ("gray", "binary"):
            problems.append("pam4_mapping deve essere gray o binary")
        if self.fec_mode not in ("none", "kp4", "kr4"):
            problems.append("fec_mode deve essere none/kp4/kr4")
        if not (1 <= self.l2_streams <= 4):
            problems.append("l2_streams fuori range [1, 4]")
        if self.fec_interleave not in (1, 2, 4):
            problems.append("fec_interleave deve essere 1, 2 o 4")
        if len(self.tx_ffe_taps) not in (3, 5, 7):
            problems.append("tx_ffe_taps: FIR TX a 3, 5 o 7 tap "
                            "(main cursor al centro)")
        if self.use_s2p_channel and not self.s2p_text.strip():
            problems.append("use_s2p_channel richiede un file S2P caricato")
        zeros = self.ctle_zeros_effective_hz
        poles = self.ctle_poles_effective_hz
        if not zeros or not poles or len(zeros) > 4 or len(poles) > 5:
            problems.append("CTLE richiede 1..4 zeri e 1..5 poli")
        if any(v <= 0 for v in zeros + poles):
            problems.append("frequenze di zeri/poli CTLE devono essere > 0")
        if tuple(sorted(zeros)) != zeros or tuple(sorted(poles)) != poles:
            problems.append("zeri e poli CTLE devono essere in ordine crescente")
        if not self.ctle_zeros_hz and not (
                self.ctle_zero_hz < self.ctle_pole_hz < self.ctle_hf_pole_hz):
            problems.append("topologia CTLE legacy: richiesto zero < polo < polo alto")
        if self.training_stop >= self.n_symbols - 500:
            problems.append("training_stop troppo vicino a n_symbols (serve validation)")
        if self.n_symbols < 2000:
            problems.append("n_symbols troppo basso per statistiche sensate (>=2000)")
        if self.fse_taps % 2 == 0:
            problems.append("fse_taps deve essere dispari (finestra simmetrica)")
        positive_fields = (
            "symbol_rate_hz", "dac_bw_hz", "driver_bw_hz", "mzm_bw_hz",
            "eml_bw_hz", "optical_drive_vpp_v", "direct_laser_bw_hz",
            "mmf_modal_bw_mhz_km",
            "pd_bw_hz", "tia_bw_hz", "vpi_v", "dac_full_scale_vpp",
            "adc_full_scale_vpp", "tia_transimpedance_ohm",
            "pd_responsivity_a_w", "agc_target_rms_v")
        for name in positive_fields:
            if getattr(self, name) <= 0:
                problems.append(f"{name} deve essere > 0")
        if self.adc_sps < 1 or self.adc_interleaves < 1:
            problems.append("adc_sps e adc_interleaves devono essere >= 1")
        if self.adc_ranks < 1 or self.adc_interleaves % self.adc_ranks:
            problems.append("adc_ranks >= 1 e divisore di adc_interleaves")
        if self.adc_cal_mode not in ("background", "foreground", "off"):
            problems.append("adc_cal_mode deve essere background/foreground/off")
        if self.adc_frontend_bw_hz < 0:
            problems.append("adc_frontend_bw_hz deve essere >= 0 (0 = off)")
        if not 0 <= self.adc_bw_mismatch_pct <= 30:
            problems.append("adc_bw_mismatch_pct fuori range [0, 30]")
        if not 0 <= self.adc_noise_rms_mv <= 20:
            problems.append("adc_noise_rms_mv fuori range [0, 20] mV")
        if self.dfe_taps < 1:
            problems.append("dfe_taps deve essere >= 1")
        if not (0 <= self.tx_rj_rms_fs <= 2000):
            problems.append("tx_rj_rms_fs fuori range [0, 2000] fs")
        if not (0 <= self.tx_pj_amp_ui <= 0.4):
            problems.append("tx_pj_amp_ui fuori range [0, 0.4] UI")
        if not (1 <= self.tx_pj_freq_mhz <= 5000):
            problems.append("tx_pj_freq_mhz fuori range [1, 5000] MHz")
        if not (0 <= self.tx_dcd_pct <= 30):
            problems.append("tx_dcd_pct fuori range [0, 30] %")
        if self.cdr_mode not in ("gardner", "mm", "oracle"):
            problems.append("cdr_mode deve essere gardner/mm/oracle")
        if not (1e-4 <= self.cdr_bw <= 0.05):
            problems.append("cdr_bw fuori range [1e-4, 0.05]")
        if not (0.3 <= self.cdr_damping <= 3.0):
            problems.append("cdr_damping fuori range [0.3, 3]")
        if abs(self.rx_ppm_offset) > 500:
            problems.append("rx_ppm_offset fuori range ±500 ppm")
        if self.rx_ppm_offset != 0 and self.cdr_mode == "oracle":
            problems.append("con rx_ppm_offset l'oracle a fase fissa non è "
                            "definito: usa cdr_mode gardner o mm")
        patterns = ("prbs", "ssprq", "custom_hex", "clock2", "clock8",
                    "eth", "ssprq_like")
        if self.pattern not in patterns:
            problems.append("pattern PPG non supportato")
        compact_hex = ("".join(c for c in self.custom_pattern_hex
                               if not c.isspace() and c not in "_:")
                       if isinstance(self.custom_pattern_hex, str) else "")
        if compact_hex.lower().startswith("0x"):
            compact_hex = compact_hex[2:]
        if (not compact_hex or len(compact_hex) % 2
                or len(compact_hex) > 8192
                or any(c not in "0123456789abcdefABCDEF"
                       for c in compact_hex)):
            problems.append("custom_pattern_hex: servono 1..4096 byte HEX "
                            "(numero pari di cifre; separatori spazio/_/: ammessi)")
        if self.pattern == "ssprq" and (
                self.modulation != "PAM4" or self.pam4_mapping != "gray"):
            problems.append("SSPRQ di Clause 120 richiede PAM4 Gray")
        if self.pattern in ("clock2", "clock8", "ssprq", "ssprq_like",
                            "custom_hex") and self.fec_mode != "none":
            problems.append("il FEC in-path richiede un payload prbs/eth; "
                            "i pattern PPG di test devono restare bit-exact")
        if not (8 <= self.l2_ipg_bytes <= 2000):
            problems.append("l2_ipg_bytes fuori range [8, 2000]")
        if not (64 <= self.l2_frame_bytes <= 1024):
            problems.append("l2_frame_bytes fuori range [64, 1024]")
        if self.link_medium not in ("optical", "copper"):
            problems.append("link_medium deve essere optical o copper")
        if self.electrical_drive_mode not in (
                "differential", "single_ended_p", "single_ended_n"):
            problems.append("electrical_drive_mode deve essere differential/"
                            "single_ended_p/single_ended_n")
        if self.optical_modulator not in ("mzm", "eml", "dml", "vcsel"):
            problems.append("optical_modulator deve essere mzm/eml/dml/vcsel")
        if self.laser_type not in ("cw_dfb_external", "dfb_eml_integrated",
                                   "dfb_direct", "vcsel_direct"):
            problems.append("laser_type non supportato")
        compatible_optics = {
            "mzm": "cw_dfb_external",
            "eml": "dfb_eml_integrated",
            "dml": "dfb_direct",
            "vcsel": "vcsel_direct",
        }
        if self.laser_type != compatible_optics.get(self.optical_modulator):
            problems.append("catena ottica incoerente: MZM richiede CW DFB "
                            "esterno; EML DFB+EAM; DML DFB-direct; VCSEL "
                            "VCSEL-direct")
        if not (0.5 <= self.eml_er_db <= 20):
            problems.append("eml_er_db fuori range [0.5, 20] dB")
        if not (0 <= self.eml_il_db <= 15):
            problems.append("eml_il_db fuori range [0, 15] dB")
        if not (-5 <= self.eml_chirp_alpha <= 8):
            problems.append("eml_chirp_alpha fuori range [-5, 8]")
        if not (0.5 <= self.direct_laser_er_db <= 20):
            problems.append("direct_laser_er_db fuori range [0.5, 20] dB")
        if not (-5 <= self.direct_laser_chirp_alpha <= 10):
            problems.append("direct_laser_chirp_alpha fuori range [-5, 10]")
        if not (0 <= self.laser_linewidth_mhz <= 1000):
            problems.append("laser_linewidth_mhz fuori range [0, 1000]")
        if not (0 <= self.pmd_ps_sqrt_km <= 10):
            problems.append("pmd_ps_sqrt_km fuori range [0, 10]")
        if not (0 <= self.pmd_power_split <= 1):
            problems.append("pmd_power_split fuori range [0, 1]")
        if not (0 <= self.fiber_gamma_w_inv_km <= 100):
            problems.append("fiber_gamma_w_inv_km fuori range [0, 100]")
        if self.fiber_type not in ("smf", "mmf"):
            problems.append("fiber_type deve essere smf o mmf")
        if self.optical_modulator == "vcsel" and self.fiber_type != "mmf":
            problems.append("VCSEL richiede fiber_type=mmf in questo modello")
        if not (0 <= self.pn_skew_ps <= 10):
            problems.append("pn_skew_ps fuori range [0, 10] ps")
        if not (0 <= self.pn_gain_mismatch_pct <= 30):
            problems.append("pn_gain_mismatch_pct fuori range [0, 30] %")
        if not (0 <= self.vcm_noise_mv <= 200):
            problems.append("vcm_noise_mv fuori range [0, 200] mV")
        if not (0 <= self.tx_diff_noise_mv <= 200):
            problems.append("tx_diff_noise_mv fuori range [0, 200] mV")
        if not (0 <= self.tia_vga_range_db <= 30):
            problems.append("tia_vga_range_db fuori range [0, 30] dB")
        if not (0.2 <= self.tia_headroom_ratio <= 0.95):
            problems.append("tia_headroom_ratio fuori range [0.2, 0.95]")
        if self.pvt_process not in ("ss", "tt", "ff"):
            problems.append("pvt_process deve essere ss/tt/ff")
        if not (-10 <= self.pvt_vdd_pct <= 10):
            problems.append("pvt_vdd_pct fuori range [-10, 10] %")
        if not (-40 <= self.pvt_temp_c <= 125):
            problems.append("pvt_temp_c fuori range [-40, 125] °C")
        if not (-40 <= self.agc_min_gain_db <= self.agc_max_gain_db <= 60):
            problems.append("richiesto -40 <= agc_min_gain_db <= "
                            "agc_max_gain_db <= 60")
        if not (0 <= self.err_insert_bits <= 200):
            problems.append("err_insert_bits fuori range [0, 200]")
        if self.err_insert_target not in ("random", "msb", "lsb", "rs_symbol"):
            problems.append("err_insert_target deve essere "
                            "random/msb/lsb/rs_symbol")
        if self.s4p_pairs not in ("13_24", "12_34"):
            problems.append("s4p_pairs deve essere 13_24 o 12_34")
        return problems

    def with_updates(self, **kwargs) -> "LinkConfig":
        return replace(self, **kwargs)

    def to_dict(self):
        return asdict(self)


def field_names():
    return [f.name for f in fields(LinkConfig)]


# ---------------------------------------------------------------------------
# Schema dichiarativo: tipo e range di OGNI campo. Le regole semantiche in
# validate() presuppongono tipi corretti; prima di questo schema 41 campi
# accettavano None, stringhe, NaN o valori assurdi (fiber_km=-5, adc_bits=0)
# che uccidevano in silenzio il thread di acquisizione.
# ---------------------------------------------------------------------------
_STRING_FIELDS = {
    "pattern", "custom_pattern_hex", "modulation", "pam4_mapping", "fec_mode",
    "electrical_drive_mode", "link_medium", "err_insert_target",
    "optical_modulator", "laser_type", "fiber_type", "pvt_process",
    "adc_cal_mode", "cdr_mode", "s2p_text", "s2p_name", "s4p_pairs",
}
_BOOL_FIELDS = {"tx_output_on", "err_insert_burst", "use_s2p_channel",
                "causal_filters"}
_TUPLE_FIELDS = {"tx_ffe_taps", "ctle_zeros_hz", "ctle_poles_hz"}
_INT_FIELDS = {
    "analog_sps", "n_symbols", "prbs_order", "l2_frame_bytes", "l2_ipg_bytes",
    "l2_streams", "fec_interleave", "dac_bits", "err_insert_bits", "adc_sps",
    "adc_bits", "adc_interleaves", "adc_ranks", "fse_taps", "dfe_taps",
    "training_start", "training_stop",
}
# (lo, hi) inclusivi. Range generosi: devono contenere preset, profili e
# valori di stress dei test, ma escludere l'assurdo.
_NUMERIC_RANGES = {
    "symbol_rate_hz": (1e9, 400e9), "analog_sps": (4, 64),
    "n_symbols": (2000, 400_000), "l2_frame_bytes": (64, 1024),
    "l2_ipg_bytes": (8, 2000), "l2_streams": (1, 4), "fec_interleave": (1, 4),
    "tx_rj_rms_fs": (0, 2000), "tx_pj_amp_ui": (0, 0.4),
    "tx_pj_freq_mhz": (1, 5000), "tx_dcd_pct": (0, 30),
    "tx_buj_amp_ui": (0, 0.5), "tx_ssc_ppm": (0, 20000), "tx_ssc_khz": (1, 1000),
    "dac_bits": (3, 16), "dac_full_scale_vpp": (0.01, 20), "dac_bw_hz": (1e8, 1e12),
    "driver_gain_v_per_unit": (0.001, 20), "driver_bw_hz": (1e8, 1e12),
    "driver_clip_v": (0.01, 20), "pn_skew_ps": (0, 10),
    "pn_gain_mismatch_pct": (0, 30), "vcm_offset_v": (-5, 5),
    "vcm_noise_mv": (0, 200), "tx_diff_noise_mv": (0, 200),
    "xtalk_next_db": (-120, 120), "xtalk_fext_db": (-120, 120),
    "err_insert_bits": (0, 200), "channel_il_nyquist_db": (0, 80),
    "channel_delay_ps": (0, 1e5), "group_delay_ripple_ps": (0, 500),
    "return_loss_db": (0, 200), "echo_delay_ui": (0, 100),
    "laser_dbm": (-60, 30), "laser_linewidth_mhz": (0, 1000),
    "vpi_v": (0.01, 100), "mzm_bias_rad": (-7, 7), "mzm_bw_hz": (1e8, 1e12),
    "mzm_il_db": (0, 40), "chirp_alpha": (-20, 20), "eml_bw_hz": (1e8, 1e12),
    "optical_drive_vpp_v": (0.001, 20), "eml_er_db": (0.5, 20),
    "eml_il_db": (0, 15), "eml_chirp_alpha": (-5, 8),
    "direct_laser_bw_hz": (1e8, 1e12), "direct_laser_er_db": (0.5, 20),
    "direct_laser_chirp_alpha": (-5, 10), "coupling_il_db": (0, 40),
    "wavelength_nm": (600, 2100), "fiber_km": (0, 500),
    "dispersion_ps_nm_km": (-200, 200), "dispersion_slope_ps_nm2_km": (-5, 5),
    "pmd_ps_sqrt_km": (0, 10), "pmd_power_split": (0, 1),
    "fiber_gamma_w_inv_km": (0, 100), "fiber_loss_db_km": (0, 20),
    "mmf_modal_bw_mhz_km": (1, 1e6), "pd_responsivity_a_w": (0.001, 2),
    "pd_dark_current_a": (0, 1e-2), "pd_bw_hz": (1e8, 1e12),
    "pd_saturation_a": (1e-7, 1), "rin_db_hz": (-220, -60),
    "tia_noise_a_rt_hz": (0, 1e-8), "tia_transimpedance_ohm": (1, 1e6),
    "tia_vga_range_db": (0, 30), "tia_headroom_ratio": (0.2, 0.95),
    "tia_bw_hz": (1e8, 1e12), "tia_clip_v": (0.001, 50),
    "agc_target_rms_v": (1e-4, 10), "pvt_vdd_pct": (-10, 10),
    "pvt_temp_c": (-40, 125), "agc_min_gain_db": (-40, 60),
    "agc_max_gain_db": (-40, 60), "ctle_zero_hz": (1e6, 1e12),
    "ctle_pole_hz": (1e6, 1e12), "ctle_hf_pole_hz": (1e6, 1e12),
    "ctle_dc_gain_db": (-40, 40), "adc_sps": (1, 8), "adc_bits": (2, 16),
    "adc_full_scale_vpp": (0.01, 20), "adc_phase_ui": (-1, 1),
    "adc_jitter_rms_fs": (0, 10000), "adc_interleaves": (1, 128),
    "adc_gain_mismatch_rms": (0, 0.5), "adc_offset_mismatch_rms_v": (0, 1),
    "adc_skew_mismatch_rms_fs": (0, 10000), "adc_ranks": (1, 64),
    "adc_frontend_bw_hz": (0, 1e12), "adc_bw_mismatch_pct": (0, 30),
    "adc_noise_rms_mv": (0, 20), "cdr_bw": (1e-4, 0.05),
    "cdr_damping": (0.3, 3.0), "rx_ppm_offset": (-500, 500),
    "fse_taps": (1, 255), "dfe_taps": (1, 64), "training_start": (0, 400_000),
    "training_stop": (0, 400_000), "prbs_order": (7, 31),
}


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _validate_types_and_ranges(cfg):
    import math as _math
    problems = []
    for f in fields(LinkConfig):
        name = f.name
        v = getattr(cfg, name)
        if name in _STRING_FIELDS:
            if not isinstance(v, str):
                problems.append(f"{name} deve essere una stringa")
            elif name == "s2p_name" and len(v) > 200:
                problems.append("s2p_name troppo lungo (max 200 caratteri)")
            continue
        if name in _BOOL_FIELDS:
            if not isinstance(v, bool):
                problems.append(f"{name} deve essere true/false")
            continue
        if name in _TUPLE_FIELDS:
            if not isinstance(v, (tuple, list)) or not all(
                    _is_number(x) and _math.isfinite(x) for x in v):
                problems.append(f"{name} deve essere una tupla di numeri finiti")
            elif name == "tx_ffe_taps" and any(abs(x) > 4 for x in v):
                problems.append("tx_ffe_taps: tap fuori range ±4")
            continue
        if not _is_number(v) or not _math.isfinite(v):
            problems.append(f"{name} deve essere un numero finito")
            continue
        if name in _INT_FIELDS and int(v) != v:
            problems.append(f"{name} deve essere intero")
            continue
        rng = _NUMERIC_RANGES.get(name)
        if rng is not None and not (rng[0] <= v <= rng[1]):
            problems.append(f"{name} fuori range [{rng[0]:g}, {rng[1]:g}]")
    return problems


def field_schema():
    """Schema pubblico (tipo + range) condiviso con UI e sweep."""
    out = {}
    for f in fields(LinkConfig):
        name = f.name
        if name in _STRING_FIELDS:
            out[name] = {"type": "str"}
        elif name in _BOOL_FIELDS:
            out[name] = {"type": "bool"}
        elif name in _TUPLE_FIELDS:
            out[name] = {"type": "tuple"}
        else:
            lo, hi = _NUMERIC_RANGES.get(name, (None, None))
            out[name] = {"type": "int" if name in _INT_FIELDS else "float",
                         "lo": lo, "hi": hi}
    return out


# ---------------------------------------------------------------------------
# Preset didattici. Ogni preset è (config, descrizione breve).
# ---------------------------------------------------------------------------

PRESETS: dict[str, tuple[LinkConfig, str]] = {
    "112G didattico — 2 km @1550 nm": (
        LinkConfig(),
        "Profilo principale del corso: 56 GBd PAM4, fibra 2 km in C-band, "
        "dispersione deliberatamente stressante. Uguale al notebook v7.",
    ),
    "Back-to-back (senza fibra)": (
        LinkConfig(fiber_km=0.0, chirp_alpha=0.0),
        "MZM collegato direttamente al PD: isola canale elettrico, rumore RX e "
        "DSP dalla dispersione cromatica. Riferimento per misurare la penalty.",
    ),
    "Stress 10 km — fading CD": (
        LinkConfig(fiber_km=10.0, laser_dbm=6.0),
        "Il primo nullo IM/DD entra nella banda del segnale: il DSP lineare "
        "non può invertire un notch. Osserva la BER degradare.",
    ),
    "100GBASE-LR1 context — 53.125 GBd O-band": (
        LinkConfig(symbol_rate_hz=53.125e9, wavelength_nm=1310.0,
                   dispersion_ps_nm_km=1.5, fiber_km=10.0,
                   fiber_loss_db_km=0.35, laser_dbm=4.0),
        "Contesto pubblico (non compliance): O-band vicino allo zero di "
        "dispersione, 10 km, loss/km maggiore che in C-band.",
    ),
    "Canale elettrico severo — 20 dB @Nyquist": (
        LinkConfig(channel_il_nyquist_db=20.0, return_loss_db=12.0),
        "Backplane lungo con eco forte: guarda i cursor ISI crescere e il "
        "lavoro spostarsi su CTLE + FSE + DFE.",
    ),
    "RX rumoroso — TIA economico": (
        LinkConfig(tia_noise_a_rt_hz=55e-12, rin_db_hz=-138.0, laser_dbm=1.0),
        "Sensitivity limitata dal rumore: il noise budget mostra chi domina e "
        "la waterfall si sposta.",
    ),
    "Link con margine — FEC al lavoro": (
        LinkConfig(fiber_km=0.0, chirp_alpha=0.0, channel_il_nyquist_db=6.0,
                   fec_mode="kp4"),
        "BER pre-FEC ~5e-4: la zona dove il RS(544,514) corregge davvero. "
        "Guarda i frame accumularsi 'clean/corretti' nel pannello FEC live.",
    ),
}


DEFAULT_PRESET = "112G didattico — 2 km @1550 nm"


# ---------------------------------------------------------------------------
# Profili standard a 4 assi: standard/clause · reference plane/reach · mezzo ·
# FEC. L'architettura interna resta la reference implementation didattica di
# questo banco: IEEE/OIF specificano le interfacce, non l'interno del SerDes.
# I numeri di canale/loss sono RAPPRESENTATIVI del reach, non maschere di
# clause. Stato aggiornato alla stesura (2026).
# ---------------------------------------------------------------------------

STANDARD_PROFILES: dict[str, tuple[LinkConfig, str]] = {
    "IEEE 802.3ae — 10GBASE-LR · PMD ottico 10 km (NRZ)": (
        LinkConfig(symbol_rate_hz=10.3125e9, modulation="NRZ", fec_mode="none",
                   optical_modulator="eml", laser_type="dfb_eml_integrated",
                   electrical_drive_mode="single_ended_p",
                   eml_bw_hz=15e9, eml_er_db=7.0,
                   wavelength_nm=1310.0, dispersion_ps_nm_km=1.5,
                   fiber_km=10.0, fiber_loss_db_km=0.35,
                   channel_il_nyquist_db=4.0, laser_dbm=2.0,
                   dac_bw_hz=15e9, driver_bw_hz=20e9,
                   pd_bw_hz=20e9, tia_bw_hz=15e9,
                   ctle_zero_hz=3e9, ctle_pole_hz=9e9,
                   ctle_hf_pole_hz=18e9),
        "10.3125 GBd NRZ · O-band 10 km · nessun FEC nel profilo — pubblicato."),
    "IEEE 802.3cc — 25GBASE-LR · PMD ottico 10 km (NRZ)": (
        LinkConfig(symbol_rate_hz=25.78125e9, modulation="NRZ", fec_mode="none",
                   optical_modulator="eml", laser_type="dfb_eml_integrated",
                   electrical_drive_mode="single_ended_p",
                   eml_bw_hz=25e9, eml_er_db=6.0,
                   wavelength_nm=1310.0, dispersion_ps_nm_km=1.5,
                   fiber_km=10.0, fiber_loss_db_km=0.35,
                   channel_il_nyquist_db=6.0, laser_dbm=4.0),
        "25.78125 GBd NRZ · O-band 10 km · profilo corretto da 802.3by a "
        "802.3cc; Clause 74 FEC non modellato."),
    "IEEE 802.3by — 25GBASE-CR · twinax 3 m (NRZ)": (
        LinkConfig(symbol_rate_hz=25.78125e9, modulation="NRZ", fec_mode="none",
                   link_medium="copper", channel_il_nyquist_db=12.0,
                   return_loss_db=12.0),
        "25.78125 GBd NRZ · twinax corto · Clause 74 FEC non modellato."),
    "IEEE 802.3bm — 100GBASE-SR4 · 4×25G MMF 100 m": (
        LinkConfig(symbol_rate_hz=25.78125e9, modulation="NRZ", fec_mode="kr4",
                   optical_modulator="vcsel", laser_type="vcsel_direct",
                   electrical_drive_mode="single_ended_p", wavelength_nm=850.0,
                   fiber_type="mmf", fiber_km=0.1, fiber_loss_db_km=3.5,
                   dispersion_ps_nm_km=0.0, dispersion_slope_ps_nm2_km=0.0,
                   pmd_ps_sqrt_km=0.0, fiber_gamma_w_inv_km=0.0,
                   mmf_modal_bw_mhz_km=4700.0, direct_laser_bw_hz=28e9,
                   direct_laser_er_db=3.0, laser_dbm=0.0),
        "4 × 25.78125 GBd NRZ · VCSEL/MMF 100 m · KR4 RS(528,514)."),
    "IEEE 802.3cd — 50GBASE-KR · backplane 1 lane (PAM4)": (
        LinkConfig(symbol_rate_hz=26.5625e9, fec_mode="kp4",
                   link_medium="copper", channel_il_nyquist_db=15.0,
                   return_loss_db=10.0),
        "26.5625 GBd PAM4 · backplane · RS(544,514) nel percorso."),
    "IEEE 802.3bs — 400GBASE-FR8 · 50G/λ ottico 2 km (PAM4)": (
        LinkConfig(symbol_rate_hz=26.5625e9, fec_mode="kp4",
                   wavelength_nm=1310.0, dispersion_ps_nm_km=1.5,
                   fiber_km=2.0, fiber_loss_db_km=0.35,
                   channel_il_nyquist_db=6.0, laser_dbm=3.0),
        "26.5625 GBd PAM4 per corsia · RS(544,514) — pubblicato."),
    "IEEE 802.3bs — 400GBASE-DR4 · 100G/λ ottico 500 m": (
        LinkConfig(symbol_rate_hz=53.125e9, fec_mode="kp4",
                   optical_modulator="eml", laser_type="dfb_eml_integrated",
                   electrical_drive_mode="single_ended_p",
                   eml_bw_hz=42e9, eml_er_db=5.0,
                   optical_drive_vpp_v=0.50,
                   wavelength_nm=1310.0, dispersion_ps_nm_km=1.5,
                   fiber_km=0.5, fiber_loss_db_km=0.35,
                   channel_il_nyquist_db=8.0, laser_dbm=3.0),
        "4 × 53.125 GBd PAM4 · SMF 500 m · EML 0.50 Vpp full-scale "
        "dichiarato · RS(544,514) — pubblicato."),
    "IEEE 802.3cu — 100GBASE-FR1 · PMD ottico 2 km": (
        LinkConfig(symbol_rate_hz=53.125e9, fec_mode="kp4",
                   optical_modulator="eml", laser_type="dfb_eml_integrated",
                   electrical_drive_mode="single_ended_p",
                   eml_bw_hz=42e9, eml_er_db=6.0,
                   wavelength_nm=1310.0, dispersion_ps_nm_km=1.5,
                   fiber_km=2.0, fiber_loss_db_km=0.35,
                   channel_il_nyquist_db=8.0, laser_dbm=3.0),
        "53.125 GBd PAM4 · O-band 2 km · RS(544,514) — pubblicato."),
    "IEEE 802.3cu — 100GBASE-LR1 · PMD ottico 10 km": (
        LinkConfig(symbol_rate_hz=53.125e9, fec_mode="kp4",
                   optical_modulator="eml", laser_type="dfb_eml_integrated",
                   electrical_drive_mode="single_ended_p",
                   eml_bw_hz=42e9, eml_er_db=6.0, eml_il_db=3.0,
                   wavelength_nm=1310.0, dispersion_ps_nm_km=1.5,
                   fiber_km=10.0, fiber_loss_db_km=0.35,
                   channel_il_nyquist_db=8.0, laser_dbm=6.0),
        "53.125 GBd PAM4 · EML O-band 10 km (come i moduli reali) · "
        "RS(544,514) — pubblicato."),
    "IEEE 802.3db — 100GBASE-SR1 · PAM4 MMF 100 m": (
        LinkConfig(symbol_rate_hz=53.125e9, fec_mode="kp4",
                   optical_modulator="vcsel", laser_type="vcsel_direct",
                   electrical_drive_mode="single_ended_p", wavelength_nm=850.0,
                   fiber_type="mmf", fiber_km=0.1, fiber_loss_db_km=3.5,
                   dispersion_ps_nm_km=0.0, dispersion_slope_ps_nm2_km=0.0,
                   pmd_ps_sqrt_km=0.0, fiber_gamma_w_inv_km=0.0,
                   mmf_modal_bw_mhz_km=4700.0, direct_laser_bw_hz=42e9,
                   direct_laser_er_db=3.5, laser_dbm=1.0),
        "53.125 GBd PAM4 · VCSEL/MMF 100 m · RS(544,514) — pubblicato."),
    "IEEE 802.3ck — 100G/lane C2M (AUI) · elettrico corto": (
        LinkConfig(symbol_rate_hz=53.125e9, fec_mode="kp4",
                   link_medium="copper", channel_il_nyquist_db=10.0,
                   return_loss_db=14.0),
        "53.125 GBd PAM4 chip-to-module · rame corto · KP4 — pubblicato."),
    "IEEE 802.3ck — 100GBASE-KR1 · backplane elettrico": (
        LinkConfig(symbol_rate_hz=53.125e9, fec_mode="kp4",
                   link_medium="copper", channel_il_nyquist_db=16.0,
                   return_loss_db=10.0, tia_noise_a_rt_hz=20e-12),
        "53.125 GBd PAM4 backplane · loss rappresentativa (non è la maschera "
        "COM di clause) · KP4 — pubblicato."),
    "IEEE 802.3df — 800GBASE-DR8 · 8×100G ottico 500 m": (
        LinkConfig(symbol_rate_hz=53.125e9, fec_mode="kp4",
                   optical_modulator="eml", laser_type="dfb_eml_integrated",
                   electrical_drive_mode="single_ended_p",
                   eml_bw_hz=42e9, eml_er_db=5.0, eml_il_db=3.0,
                   wavelength_nm=1310.0, dispersion_ps_nm_km=1.5,
                   fiber_km=0.5, fiber_loss_db_km=0.35,
                   channel_il_nyquist_db=8.0, laser_dbm=3.0),
        "8 × 53.125 GBd PAM4 · SMF 500 m · RS(544,514) — pubblicato."),
    "OIF CEI-56G-LR · interfaccia elettrica long reach": (
        LinkConfig(symbol_rate_hz=28.0e9, fec_mode="none",
                   link_medium="copper", channel_il_nyquist_db=18.0,
                   return_loss_db=10.0),
        "28 GBd PAM4 electrical LR · la CEI non prescrive il FEC Ethernet."),
    "OIF CEI-112G-VSR · modulo elettrico": (
        LinkConfig(symbol_rate_hz=56.0e9, fec_mode="none",
                   link_medium="copper", channel_il_nyquist_db=9.0),
        "56 GBd PAM4 very-short-reach · rame · IA OIF-CEI-5.3; FEC esterno."),
    "OIF CEI-224G-LR · interfaccia elettrica": (
        LinkConfig(symbol_rate_hz=106.25e9, fec_mode="none",
                   link_medium="copper", channel_il_nyquist_db=16.0,
                   return_loss_db=10.0, dac_bw_hz=60e9, driver_bw_hz=70e9,
                   tia_bw_hz=60e9,
                   tx_ffe_taps=(0.0, -0.10, 1.0, -0.22, 0.0),
                   ctle_zeros_hz=(14e9, 26e9),
                   ctle_poles_hz=(22e9, 44e9, 80e9),
                   adc_bits=8, fse_taps=25, dfe_taps=8),
        "106.25 GBd PAM4 electrical LR · CEI-224G draft: TX FIR 5 tap + "
        "CTLE 2Z/3P; pre-FEC ~3e-3 = regime del FEC concatenato di "
        "P802.3dj (soglia ~5e-3), FEC fuori dalla CEI."),
    "P802.3dj (draft) — 200G/lane · elettrico C2C": (
        LinkConfig(symbol_rate_hz=106.25e9, fec_mode="none",
                   link_medium="copper", channel_il_nyquist_db=12.0,
                   dac_bw_hz=55e9, driver_bw_hz=60e9, tia_bw_hz=55e9,
                   pd_bw_hz=70e9, mzm_bw_hz=60e9, ctle_pole_hz=40e9,
                   ctle_hf_pole_hz=80e9, adc_full_scale_vpp=1.8),
        "106.25 GBd PAM4 · PROGETTO IN CORSO: FEC concatenato draft non "
        "modellato; ADC 1.8 Vpp per conservare headroom col CTLE 106G, "
        "numeri non definitivi."),
}


# Metadati mostrati nel catalogo. ``claim`` e deliberatamente esplicito:
# questi profili configurano un contesto per-lane, non eseguono la procedura
# di conformita della clause/IA.
_IEEE = "https://www.ieee802.org/3/"
_OIF = "https://www.oiforum.com/technical-work/implementation-agreements-ias/"
STANDARD_PROFILE_META = {
    "IEEE 802.3ae — 10GBASE-LR · PMD ottico 10 km (NRZ)":
        dict(standard="IEEE 802.3ae", interface="10GBASE-LR", reach="10 km",
             medium="optical", lanes="1×10G", status="published", fec="none",
             plane="optical PMD", source=_IEEE, claim="context"),
    "IEEE 802.3cc — 25GBASE-LR · PMD ottico 10 km (NRZ)":
        dict(standard="IEEE 802.3cc", interface="25GBASE-LR", reach="10 km",
             medium="optical", lanes="1×25G", status="published",
             fec="Clause 74 not modeled", plane="optical PMD", source=_IEEE+"cc/", claim="context"),
    "IEEE 802.3by — 25GBASE-CR · twinax 3 m (NRZ)":
        dict(standard="IEEE 802.3by", interface="25GBASE-CR", reach="3 m",
             medium="copper", lanes="1×25G", status="published",
             fec="Clause 74 not modeled", plane="cable MDI", source=_IEEE+"by/", claim="context"),
    "IEEE 802.3bm — 100GBASE-SR4 · 4×25G MMF 100 m":
        dict(standard="IEEE 802.3bm", interface="100GBASE-SR4", reach="100 m",
             medium="optical MMF", lanes="4×25G", status="published",
             fec="RS(528,514)", plane="optical PMD", source=_IEEE+"bm/", claim="context"),
    "IEEE 802.3cd — 50GBASE-KR · backplane 1 lane (PAM4)":
        dict(standard="IEEE 802.3cd", interface="50GBASE-KR", reach="backplane",
             medium="copper", lanes="1×50G", status="published", fec="RS(544,514)",
             plane="backplane MDI", source=_IEEE+"cd/", claim="context"),
    "IEEE 802.3bs — 400GBASE-FR8 · 50G/λ ottico 2 km (PAM4)":
        dict(standard="IEEE 802.3bs", interface="400GBASE-FR8", reach="2 km",
             medium="optical", lanes="8×50G", status="published", fec="RS(544,514)",
             plane="optical PMD", source=_IEEE+"bs/", claim="context"),
    "IEEE 802.3bs — 400GBASE-DR4 · 100G/λ ottico 500 m":
        dict(standard="IEEE 802.3bs", interface="400GBASE-DR4", reach="500 m",
             medium="optical", lanes="4×100G", status="published", fec="RS(544,514)",
             plane="optical PMD", source=_IEEE+"bs/", claim="context"),
    "IEEE 802.3cu — 100GBASE-FR1 · PMD ottico 2 km":
        dict(standard="IEEE 802.3cu", interface="100GBASE-FR1", reach="2 km",
             medium="optical", lanes="1×100G", status="published", fec="RS(544,514)",
             plane="optical PMD", source=_IEEE+"cu/", claim="context"),
    "IEEE 802.3cu — 100GBASE-LR1 · PMD ottico 10 km":
        dict(standard="IEEE 802.3cu", interface="100GBASE-LR1", reach="10 km",
             medium="optical", lanes="1×100G", status="published", fec="RS(544,514)",
             plane="optical PMD", source=_IEEE+"cu/", claim="context"),
    "IEEE 802.3db — 100GBASE-SR1 · PAM4 MMF 100 m":
        dict(standard="IEEE 802.3db", interface="100GBASE-SR1", reach="100 m",
             medium="optical MMF", lanes="1×100G", status="published",
             fec="RS(544,514)", plane="optical PMD", source=_IEEE+"db/", claim="context"),
    "IEEE 802.3ck — 100G/lane C2M (AUI) · elettrico corto":
        dict(standard="IEEE 802.3ck", interface="100GAUI-1 C2M", reach="C2M",
             medium="copper", lanes="1×100G", status="published", fec="PCS context",
             plane="AUI C2M", source=_IEEE+"ck/", claim="context"),
    "IEEE 802.3ck — 100GBASE-KR1 · backplane elettrico":
        dict(standard="IEEE 802.3ck", interface="100GBASE-KR1", reach="backplane",
             medium="copper", lanes="1×100G", status="published", fec="RS(544,514)",
             plane="backplane MDI", source=_IEEE+"ck/", claim="context"),
    "IEEE 802.3df — 800GBASE-DR8 · 8×100G ottico 500 m":
        dict(standard="IEEE 802.3df", interface="800GBASE-DR8", reach="500 m",
             medium="optical", lanes="8×100G", status="published", fec="RS(544,514)",
             plane="optical PMD", source=_IEEE+"df/", claim="context"),
    "OIF CEI-56G-LR · interfaccia elettrica long reach":
        dict(standard="OIF CEI-5.3", interface="CEI-56G-LR", reach="LR",
             medium="copper", lanes="1×56G", status="published", fec="outside CEI",
             plane="CEI electrical", source=_OIF, claim="context"),
    "OIF CEI-112G-VSR · modulo elettrico":
        dict(standard="OIF CEI-5.3", interface="CEI-112G-VSR", reach="VSR",
             medium="copper", lanes="1×112G", status="published", fec="outside CEI",
             plane="CEI electrical", source=_OIF, claim="context"),
    "OIF CEI-224G-LR · interfaccia elettrica":
        dict(standard="OIF CEI-224G (draft)", interface="CEI-224G-LR", reach="LR",
             medium="copper", lanes="1×224G", status="draft", fec="outside CEI",
             plane="CEI electrical", source=_OIF, claim="draft-context"),
    "P802.3dj (draft) — 200G/lane · elettrico C2C":
        dict(standard="IEEE P802.3dj", interface="200G/lane C2C", reach="C2C",
             medium="copper", lanes="1×200G", status="draft", fec="draft, not modeled",
             plane="AUI C2C", source=_IEEE+"dj/public/", claim="draft-context"),
}
