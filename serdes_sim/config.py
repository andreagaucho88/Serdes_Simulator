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
    pattern: str = "prbs"         # prbs | clock2 | clock8 | eth | ssprq_like
    l2_frame_bytes: int = 256     # dimensione frame per pattern "eth"
    l2_ipg_bytes: int = 12        # inter-packet gap (rate control del PPG)
    modulation: str = "PAM4"      # "PAM4" | "NRZ"
    pam4_mapping: str = "gray"    # "gray" | "binary" (ignorato per NRZ)
    fec_mode: str = "none"        # "none" | "kp4" RS(544,514) | "kr4" RS(528,514)
                                  # con kp4/kr4 l'encoder è NEL percorso TX e il
                                  # decoder gira sui frame interamente coperti

    # TX clock (PLL/serializer) — jitter iniettato sul time base del DAC
    tx_rj_rms_fs: float = 0.0     # random jitter RMS [fs]
    tx_pj_amp_ui: float = 0.0     # periodic jitter, ampiezza picco [UI]
    tx_pj_freq_mhz: float = 200.0  # frequenza del PJ sinusoidale
    tx_dcd_pct: float = 0.0       # duty-cycle distortion [% di UI, alternato ±/2]

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

    # BERT: bit del pattern invertiti al TX rispetto al riferimento dell'ED
    err_insert_bits: int = 0
    err_insert_burst: bool = False   # True: bit consecutivi (burst singolo)

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
    tia_bw_hz: float = 35e9
    tia_clip_v: float = 0.8
    agc_target_rms_v: float = 0.22

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

    # CDR (timing recovery NEL datapath; "oracle" è la modalità idealizzata
    # dichiarata: fase dal minimo MSE con i simboli noti)
    cdr_mode: str = "gardner"     # "gardner" | "mm" | "oracle"
    cdr_bw: float = 0.0015        # banda del loop normalizzata al baud rate
    cdr_damping: float = 1.0      # smorzamento zeta del loop PI
    rx_ppm_offset: float = 0.0    # offset di frequenza clock RX vs TX [ppm]

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
        problems = []
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
            "eml_bw_hz", "direct_laser_bw_hz", "mmf_modal_bw_mhz_km",
            "pd_bw_hz", "tia_bw_hz", "vpi_v", "dac_full_scale_vpp",
            "adc_full_scale_vpp", "tia_transimpedance_ohm",
            "pd_responsivity_a_w", "agc_target_rms_v")
        for name in positive_fields:
            if getattr(self, name) <= 0:
                problems.append(f"{name} deve essere > 0")
        if self.adc_sps < 1 or self.adc_interleaves < 1:
            problems.append("adc_sps e adc_interleaves devono essere >= 1")
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
        if self.pattern not in ("prbs", "clock2", "clock8", "eth", "ssprq_like"):
            problems.append("pattern deve essere prbs/clock2/clock8/eth/ssprq_like")
        if self.pattern in ("clock2", "clock8", "ssprq_like") and self.fec_mode != "none":
            problems.append("il FEC in-path richiede un payload (prbs o eth)")
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
        if not (0 <= self.err_insert_bits <= 200):
            problems.append("err_insert_bits fuori range [0, 200]")
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
                   wavelength_nm=1310.0, dispersion_ps_nm_km=1.5,
                   fiber_km=0.5, fiber_loss_db_km=0.35,
                   channel_il_nyquist_db=8.0, laser_dbm=3.0),
        "4 × 53.125 GBd PAM4 · SMF 500 m · RS(544,514) — pubblicato."),
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
                   wavelength_nm=1310.0, dispersion_ps_nm_km=1.5,
                   fiber_km=10.0, fiber_loss_db_km=0.35,
                   channel_il_nyquist_db=8.0, laser_dbm=4.5),
        "53.125 GBd PAM4 · O-band 10 km · RS(544,514) — pubblicato."),
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
                   link_medium="copper", channel_il_nyquist_db=18.0,
                   return_loss_db=10.0, dac_bw_hz=60e9, driver_bw_hz=70e9,
                   tia_bw_hz=60e9, ctle_pole_hz=45e9,
                   ctle_hf_pole_hz=90e9, adc_bits=8, fse_taps=25,
                   dfe_taps=8),
        "106.25 GBd PAM4 electrical LR · CEI-224G; FEC fuori dalla CEI."),
    "P802.3dj (draft) — 200G/lane · elettrico C2C": (
        LinkConfig(symbol_rate_hz=106.25e9, fec_mode="none",
                   link_medium="copper", channel_il_nyquist_db=12.0,
                   dac_bw_hz=55e9, driver_bw_hz=60e9, tia_bw_hz=55e9,
                   pd_bw_hz=70e9, mzm_bw_hz=60e9, ctle_pole_hz=40e9,
                   ctle_hf_pole_hz=80e9),
        "106.25 GBd PAM4 · PROGETTO IN CORSO: FEC concatenato draft non "
        "modellato, numeri non definitivi."),
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
        dict(standard="OIF CEI-5.3", interface="CEI-224G-LR", reach="LR",
             medium="copper", lanes="1×224G", status="published", fec="outside CEI",
             plane="CEI electrical", source=_OIF, claim="context"),
    "P802.3dj (draft) — 200G/lane · elettrico C2C":
        dict(standard="IEEE P802.3dj", interface="200G/lane C2C", reach="C2C",
             medium="copper", lanes="1×200G", status="draft", fec="draft, not modeled",
             plane="AUI C2C", source=_IEEE+"dj/public/", claim="draft-context"),
}
