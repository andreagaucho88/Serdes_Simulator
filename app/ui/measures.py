"""Pagina misure: tutte le grandezze del run corrente, ciascuna con
definizione operativa, formula e piano di riferimento."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from serdes_sim.blocks.receiver import ctle_peaking_db
from serdes_sim.utils import w_to_dbm

from .. import common
from .. import theme as T
from ..state import get_cfg, run_sim


def _rows_to_df(rows):
    return pd.DataFrame(rows, columns=["grandezza", "valore", "definizione e formula"])


def page_measures():
    common.page_header("DIAGNOSTICA · MISURE", "Misure & definizioni",
                       None, None,
                       "Le grandezze principali del run, ognuna con definizione "
                       "operativa e reference plane (l'elenco cresce: non è "
                       "ancora esaustivo).")

    cfg = get_cfg()
    sim = run_sim()
    if not common.require_link(sim):
        return
    spec = sim.spec
    bps = spec.bits_per_symbol
    n_bits_val = sim.metrics_rows[0]["bits"]

    st.subheader("Stimolo e rate")
    st.dataframe(_rows_to_df([
        ("Baud rate", f"{cfg.symbol_rate_hz / 1e9:.3f} GBd",
         "Simboli al secondo. 1 GBd = 10⁹ simboli/s."),
        ("Bit rate raw", f"{bps * cfg.symbol_rate_hz / 1e9:.2f} Gb/s",
         "bit/simbolo × baud rate, prima di FEC e overhead di protocollo."),
        ("UI (Unit Interval)", f"{cfg.ui_s * 1e12:.3f} ps",
         "Durata di un simbolo: UI = 1/baud rate."),
        ("Nyquist", f"{cfg.nyquist_hz / 1e9:.3f} GHz",
         "Metà del baud rate: la prima frequenza a cui lo spettro dati si annulla."),
    ]), use_container_width=True, hide_index=True)

    st.subheader(f"Ottica al PD  ·  piano: fiber output / PD input")
    ol = sim.optical_levels
    st.dataframe(_rows_to_df([
        ("P media", f"{w_to_dbm(ol['p_avg_w']):.2f} dBm",
         "Potenza ottica media ⟨P(t)⟩. dBm = 10·log₁₀(P/1 mW)."),
        ("P_high / P_low (proxy)",
         f"{1e3 * ol['p_high_w']:.3f} / {1e3 * ol['p_low_w']:.3f} mW",
         "Media dei percentili estremi (≥90° / ≤10°) della potenza istantanea. "
         "PROXY: una misura vera richiede clock alignment e filtro di riferimento."),
        ("OMA outer (proxy)", f"{1e3 * ol['oma_outer_w']:.3f} mW",
         "Optical Modulation Amplitude: P_high − P_low fra i livelli esterni. "
         "È l'ampiezza che il RX può davvero usare (la potenza media no)."),
        ("Extinction ratio (proxy)", f"{ol['extinction_ratio_db']:.2f} dB",
         "ER = 10·log₁₀(P_high/P_low). ER basso = potenza sprecata in DC."),
        ("Dispersione accumulata D·L",
         f"{cfg.dispersion_ps_nm_km * cfg.fiber_km:.1f} ps/nm",
         "Ritardo di gruppo differenziale per nm di larghezza spettrale."),
    ]), use_container_width=True, hide_index=True)

    st.subheader("Rumore e banda al ricevitore  ·  piano: ingresso TIA")
    rx = sim.receiver
    total_noise_rms = float(np.sqrt(sum(v ** 2 for v in rx.noise_rms_after_tia_a.values())))
    i_signal_rms = float(np.std(rx.i_pd_signal_a))
    peaking_db, f_peak = ctle_peaking_db(cfg.ctle_zero_hz, cfg.ctle_pole_hz,
                                         cfg.ctle_hf_pole_hz, cfg.ctle_dc_gain_db)
    st.dataframe(_rows_to_df([
        ("ENBW del TIA", f"{rx.tia_enbw_hz / 1e9:.2f} GHz",
         "Equivalent Noise Bandwidth: ∫|H(f)|²df. Per un singolo polo = π·f₃dB/2. "
         "È la banda che conta per il rumore, NON la banda a −3 dB."),
        ("PSD shot", f"{rx.S_shot_a2_hz:.3e} A²/Hz",
         "S_shot = 2·q·I: rumore quantistico della fotocorrente (one-sided)."),
        ("PSD TIA", f"{rx.S_tia_a2_hz:.3e} A²/Hz",
         "Rumore di corrente input-referred dell'amplificatore: iₙ²."),
        ("PSD RIN", f"{rx.S_rin_a2_hz:.3e} A²/Hz",
         "S_RIN = I²·10^(RIN/10): rumore relativo d'intensità del laser."),
        ("Rumore totale RMS dopo TIA", f"{1e6 * total_noise_rms:.2f} µA",
         "√(Σ PSD · ENBW), somma in potenza delle sorgenti indipendenti."),
        ("SNR elettrico al TIA (modello)",
         f"{20 * np.log10(max(i_signal_rms, 1e-30) / max(total_noise_rms, 1e-30)):.2f} dB",
         "20·log₁₀(RMS AC segnale / RMS rumore) alla stessa banda: modello dal "
         "noise budget, non include l'ISI."),
        ("Peaking CTLE", f"{peaking_db:.2f} dB @ {f_peak / 1e9:.1f} GHz",
         "max|H| − |H(DC)|: quanto il CTLE alza le alte frequenze rispetto al DC."),
        ("Noise enhancement CTLE", f"{rx.ctle_noise_enhancement_db:+.2f} dB",
         "10·log₁₀ della potenza media di |H|² su 0..fs/2: il costo in rumore "
         "della flatness."),
    ]), use_container_width=True, hide_index=True)

    st.subheader("Piano di decisione  ·  dopo FSE (e dopo DFE)")
    snr, snr_dfe = sim.snr, sim.snr_dfe
    eye_names = ["basso", "medio", "alto"][:len(snr["q_per_eye"])]
    q_str = " · ".join(f"{n}: {q:.2f}" for n, q in zip(eye_names, snr["q_per_eye"]))
    q_str_dfe = " · ".join(f"{n}: {q:.2f}" for n, q in zip(eye_names, snr_dfe["q_per_eye"]))
    st.dataframe(_rows_to_df([
        ("SNR al slicer (FSE)", f"{snr['snr_slicer_db']:.2f} dB",
         "10·log₁₀(E[d²]/E[(y−d)²]) su validation: include rumore, ISI residua "
         "e non linearità (di fatto un SNDR del campione di decisione)."),
        ("SNR al slicer (FSE+DFE)", f"{snr_dfe['snr_slicer_db']:.2f} dB",
         "Stessa definizione dopo la cancellazione dei postcursor del DFE."),
        (f"Q-factor per occhio (FSE)", q_str,
         "Q = (μ₊−μ₋)/(σ₊+σ₋) fra livelli adiacenti. Per rumore gaussiano "
         "BER_occhio ≈ Q(Q-factor) con Q(x) = 0.5·erfc(x/√2)."),
        ("Q-factor per occhio (FSE+DFE)", q_str_dfe,
         "Il DFE alza il Q degli occhi dominati dai postcursor."),
        ("Q minimo (FSE+DFE)", f"{snr_dfe['q_min']:.2f} → BER gauss "
         f"{snr_dfe['ber_from_qmin_gaussian']:.1e}",
         "L'occhio peggiore limita il link; la BER gaussiana da Q_min è un "
         "MODELLO da confrontare con la BER contata."),
        ("Error RMS al slicer", f"{snr_dfe['error_rms']:.4f}",
         "√E[(y−d)²] in unità normalizzate dei livelli (±1)."),
        ("Stato timing",
         (f"CDR {cfg.cdr_mode} LOCKED · pattern lag {sim.cdr.pattern_lag} "
          f"(|corr| {abs(sim.cdr.pattern_corr):.2f})"
          if sim.cdr is not None else "oracle (modalità idealizzata dichiarata)"),
         "Con cdr_mode gardner/mm la fase viene dal loop PI+NCO nel datapath e "
         "l'allineamento dal pattern lock stile BERT; 'oracle' usa il minimo "
         "MSE con i simboli noti (riferimento ideale, non un ricevitore)."),
        ("Clipping ADC", f"{100 * sim.adc.adc_clip_fraction:.3f} %",
         "Frazione di campioni oltre il full scale: non recuperabile dal DSP."),
    ]), use_container_width=True, hide_index=True)

    st.subheader("Informazione e conteggi  ·  validation set")
    m = sim.metrics_rows[2]
    fa = sim.fec
    st.dataframe(_rows_to_df([
        ("BER (contata)", f"{m['BER']:.3e}  ({m['bit_errors']}/{m['bits']} bit)",
         "Bit errati / bit totali sulla sola validation (mai sul training). "
         "Sempre con il conteggio: il rapporto da solo non basta."),
        ("Intervallo 95% sulla BER",
         f"[{m['BER_95pct_low']:.2e}, {m['BER_95pct_high']:.2e}]",
         "Intervallo binomiale Clopper-Pearson SOTTO IPOTESI IID: con burst "
         "(error propagation DFE) l'intervallo reale è più largo."),
        ("GMI per bit",
         " · ".join(f"{g:.4f}" for g in sim.gmi_per_bit),
         "Contributo di ciascun bit (MSB…LSB): con PAM4 Gray il bit 'esterno' "
         "è tipicamente più robusto di quello 'interno'."),
        ("SER (simboli)", f"{m['SER']:.3e}",
         "Simboli errati / simboli totali. Con Gray, 1 errore di simbolo "
         "adiacente = 1 bit errato su bps."),
        ("GMI", f"{sim.gmi_total:.4f} / {bps} bit/simbolo",
         "Generalized Mutual Information dai LLR calibrati: informazione "
         "raggiungibile da un decoder soft con QUESTO detector. Non è il "
         "throughput garantito di un FEC reale."),
        ("Limite zero-errori", f"{3 / n_bits_val:.1e} (95%)",
         "Con N bit e 0 errori, p_u ≈ 3/N al 95%: zero errori osservati non "
         "significa BER zero."),
        ("SER simboli FEC 10b", f"{fa.symbol_error_rate:.3e}",
         "Frazione di simboli RS da 10 bit con ≥1 bit errato."),
        ("FER RS(544,514) modello iid", f"{fa.fer_iid_model_qmeas:.3e}",
         "P[X>15], X~Binomial(544, q) con q misurata: vale solo se gli errori "
         "sono indipendenti (controlla la burstiness nella pagina FEC)."),
    ]), use_container_width=True, hide_index=True)

    st.markdown(T.warn(
        "Tutto ciò che è etichettato <b>proxy</b> o <b>modello</b> non è una "
        "misura normativa: TDECQ, COM e le maschere di clause richiedono "
        "procedure prescritte (pattern, filtri, equalizzatore e decision rule "
        "specificati dalla clause)."), unsafe_allow_html=True)
