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
    pattern: str = "prbs"         # "prbs" | "clock2" | "clock8" | "eth" (frame L2)
    l2_frame_bytes: int = 256     # dimensione frame per pattern "eth"
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

    # Mezzo del link: "optical" = catena completa MZM/fibra/PD;
    # "copper" = elettrico puro (KR/CR/C2M): canale → RX AFE, niente ottica
    link_medium: str = "optical"

    # Crosstalk da aggressore sullo stesso connettore (0 = off)
    xtalk_next_db: float = 0.0     # accoppiamento NEXT @Nyquist [dB, >0 = off]
    xtalk_fext_db: float = 0.0     # accoppiamento FEXT @Nyquist [dB, >0 = off]

    # BERT: bit del pattern invertiti al TX rispetto al riferimento dell'ED
    err_insert_bits: int = 0

    # Canale elettrico
    channel_il_nyquist_db: float = 12.0
    channel_delay_ps: float = 18.0
    group_delay_ripple_ps: float = 1.2
    return_loss_db: float = 18.0
    echo_delay_ui: float = 1.35

    # Trasmettitore ottico e fibra
    laser_dbm: float = 3.0
    vpi_v: float = 3.5
    mzm_bias_rad: float = 1.5707963267948966  # pi/2, quadratura
    mzm_bw_hz: float = 40e9
    mzm_il_db: float = 4.5
    chirp_alpha: float = 0.4
    coupling_il_db: float = 2.0
    wavelength_nm: float = 1550.0
    fiber_km: float = 2.0
    dispersion_ps_nm_km: float = 17.0
    fiber_loss_db_km: float = 0.20

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
        if self.use_s2p_channel and not self.s2p_text.strip():
            problems.append("use_s2p_channel richiede un file S2P caricato")
        if not (0 < self.ctle_zero_hz < self.ctle_pole_hz < self.ctle_hf_pole_hz):
            problems.append("richiesto 0 < ctle_zero < ctle_pole < ctle_hf_pole")
        if self.training_stop >= self.n_symbols - 500:
            problems.append("training_stop troppo vicino a n_symbols (serve validation)")
        if self.n_symbols < 2000:
            problems.append("n_symbols troppo basso per statistiche sensate (>=2000)")
        if self.fse_taps % 2 == 0:
            problems.append("fse_taps deve essere dispari (finestra simmetrica)")
        positive_fields = (
            "symbol_rate_hz", "dac_bw_hz", "driver_bw_hz", "mzm_bw_hz",
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
        if self.pattern not in ("prbs", "clock2", "clock8", "eth"):
            problems.append("pattern deve essere prbs/clock2/clock8/eth")
        if self.pattern in ("clock2", "clock8") and self.fec_mode != "none":
            problems.append("il FEC in-path richiede un payload (prbs o eth)")
        if not (64 <= self.l2_frame_bytes <= 1024):
            problems.append("l2_frame_bytes fuori range [64, 1024]")
        if self.link_medium not in ("optical", "copper"):
            problems.append("link_medium deve essere optical o copper")
        if not (0 <= self.pn_skew_ps <= 10):
            problems.append("pn_skew_ps fuori range [0, 10] ps")
        if not (0 <= self.pn_gain_mismatch_pct <= 30):
            problems.append("pn_gain_mismatch_pct fuori range [0, 30] %")
        if not (0 <= self.vcm_noise_mv <= 200):
            problems.append("vcm_noise_mv fuori range [0, 200] mV")
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
    "IEEE 802.3by — 25GBASE-LR · PMD ottico 10 km (NRZ)": (
        LinkConfig(symbol_rate_hz=25.78125e9, modulation="NRZ", fec_mode="kr4",
                   wavelength_nm=1310.0, dispersion_ps_nm_km=1.5,
                   fiber_km=10.0, fiber_loss_db_km=0.35,
                   channel_il_nyquist_db=6.0, laser_dbm=4.0),
        "25.78125 GBd NRZ · O-band 10 km · RS(528,514) — pubblicato."),
    "IEEE 802.3bs — 400GBASE-FR8 · 50G/λ ottico 2 km (PAM4)": (
        LinkConfig(symbol_rate_hz=26.5625e9, fec_mode="kp4",
                   wavelength_nm=1310.0, dispersion_ps_nm_km=1.5,
                   fiber_km=2.0, fiber_loss_db_km=0.35,
                   channel_il_nyquist_db=6.0, laser_dbm=3.0),
        "26.5625 GBd PAM4 per corsia · RS(544,514) — pubblicato."),
    "IEEE 802.3cu — 100GBASE-FR1 · PMD ottico 2 km": (
        LinkConfig(symbol_rate_hz=53.125e9, fec_mode="kp4",
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
    "IEEE 802.3ck — 100G/lane C2M (AUI) · elettrico corto": (
        LinkConfig(symbol_rate_hz=53.125e9, fec_mode="kp4",
                   link_medium="copper", channel_il_nyquist_db=10.0,
                   return_loss_db=14.0),
        "53.125 GBd PAM4 chip-to-module · rame corto · KP4 — pubblicato."),
    "IEEE 802.3ck — 100GBASE-KR1-like · backplane elettrico": (
        LinkConfig(symbol_rate_hz=53.125e9, fec_mode="kp4",
                   link_medium="copper", channel_il_nyquist_db=16.0,
                   return_loss_db=10.0, tia_noise_a_rt_hz=20e-12),
        "53.125 GBd PAM4 backplane · loss rappresentativa (non è la maschera "
        "COM di clause) · KP4 — pubblicato."),
    "OIF CEI-112G-VSR-like · modulo elettrico": (
        LinkConfig(symbol_rate_hz=56.0e9, fec_mode="kp4",
                   link_medium="copper", channel_il_nyquist_db=9.0),
        "56 GBd PAM4 very-short-reach · rame · KP4 — IA OIF-CEI-5.x."),
    "P802.3dj (draft) — 200G/lane · elettrico C2C": (
        LinkConfig(symbol_rate_hz=106.25e9, fec_mode="kp4",
                   link_medium="copper", channel_il_nyquist_db=12.0,
                   dac_bw_hz=55e9, driver_bw_hz=60e9, tia_bw_hz=55e9,
                   pd_bw_hz=70e9, mzm_bw_hz=60e9, ctle_pole_hz=40e9,
                   ctle_hf_pole_hz=80e9),
        "106.25 GBd PAM4 · PROGETTO IN CORSO (draft): numeri non definitivi."),
}
