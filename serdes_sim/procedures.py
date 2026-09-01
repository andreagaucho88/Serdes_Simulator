"""Procedure fisiche versionate eseguite sopra il datapath LabPro.

Una procedura e diversa da un preset: congela pattern, piano di misura,
canale di test, reference receiver e criteri.  Il risultato separa sempre il
verdetto del modello dal claim di conformita.  La prima procedura coperta e il
TDECQ per-lane DR4, costruito solo da materiale pubblico IEEE; riflessione
ottica/polarizzazione worst-case, incertezza metrologica completa e
correlazione con un golden instrument restano blocchi espliciti, quindi il
claim IEEE rimane ``NOT ASSESSED``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
import time

import numpy as np

from .blocks.metrics import tdecq_report
from .blocks.ssprq_data import (SSPRQ_PERIOD_SYMBOLS, SSPRQ_SOURCE_URL,
                                SSPRQ_SYMBOL_SHA256)
from .blocks.stimulus import ssprq_symbol_indices
from .config import STANDARD_PROFILES
from .engine import simulate


DR4_PROFILE_NAME = "IEEE 802.3bs — 400GBASE-DR4 · 100G/λ ottico 500 m"
DR4_TDECQ_PUBLIC_DRAFT = (
    "https://www.ieee802.org/3/bs/public/16_06/mazzini_3bs_01_0616.pdf"
)
DR4_CHANNEL_PUBLIC_TABLE = (
    "https://www.ieee802.org/3/df/public/22_12/brown_3df_03c_2212.pdf"
)


@dataclass(frozen=True)
class Dr4TdecqProcedure:
    procedure_id: str = "labpro-dr4-tdecq-public-v1"
    version: str = "1.0.0"
    target: str = "400GBASE-DR4 per-lane transmitter model"
    standard_context: str = (
        "IEEE 802.3bs · Clause 124.8.5 (metodo 121.8.5)"
    )
    symbol_rate_hz: float = 53.125e9
    modulation: str = "PAM4 Gray"
    pattern: str = "SSPRQ Clause 120, full public vector"
    pattern_symbols: int = SSPRQ_PERIOD_SYMBOLS
    tdecq_limit_db: float = 3.4
    target_ser: float = 4.8e-4
    q_t: float = 3.414
    reference_receiver: str = "BT4 0.5·Bd + 5-tap T-spaced FFE"
    histogram_centers_ui: tuple = (0.45, 0.55)
    histogram_width_ui: float = 0.04
    channel_insertion_loss_max_db: float = 3.0
    max_mean_dgd_ps: float = 2.24
    channel_optical_return_loss_min_db: float = 37.0
    tx_return_loss_tolerance_db: float = 21.4
    source: str = DR4_TDECQ_PUBLIC_DRAFT
    channel_source: str = DR4_CHANNEL_PUBLIC_TABLE


DR4_TDECQ_V1 = Dr4TdecqProcedure()


def dr4_dispersion_bounds_ps_nm(wavelength_nm: float) -> tuple[float, float]:
    """Estremi di dispersione TOTALE della Table 124-11 pubblica.

    I valori sono quelli del canale 400GBASE-DR4 originale, non le formule
    della Table 121-11 per 200GBASE-DR4. ``wavelength_nm`` resta un argomento
    esplicito per impedire di applicare il contratto DR4 fuori dalla O-band.
    """
    lam = float(wavelength_nm)
    if not 1260.0 <= lam <= 1360.0:
        raise ValueError("il contratto DR4 pubblico e valido nella O-band")
    return -0.93, +0.80


def _step(step_id, label, status, requirement, evidence, source=None):
    return {
        "id": step_id, "label": label, "status": status,
        "requirement": requirement, "evidence": evidence,
        "source": source or DR4_TDECQ_PUBLIC_DRAFT,
    }


def run_dr4_tdecq_e2e(seed: int = 500283) -> dict:
    """Esegue la procedura DR4 v1 su entrambi gli estremi di dispersione.

    Ogni caso percorre davvero PPG → TX → canale elettrico → E/O → fibra di
    compliance → PD/TIA/AGC/ADC → CDR/FSE/DFE.  Il TDECQ usa la potenza al
    termine del canale di compliance; BER e lock chiudono invece la catena
    fisica completa.  Il banco dell'utente non viene modificato.
    """
    spec = DR4_TDECQ_V1
    t0 = time.perf_counter()
    profile = STANDARD_PROFILES[DR4_PROFILE_NAME][0]
    if profile.fiber_km <= 0:
        raise RuntimeError("il profilo DR4 non contiene il canale ottico")

    # Il pattern di test deve bypassare il FEC per restare bit-exact al PPG.
    # Loss ottica al massimo di tabella; DGD appena sotto il massimo pubblico
    # e ripartita 50/50 sui PSP.
    fiber_loss_db = profile.fiber_loss_db_km * profile.fiber_km
    coupling_loss_db = spec.channel_insertion_loss_max_db - fiber_loss_db
    if coupling_loss_db < 0:
        raise RuntimeError("la sola fibra supera la loss massima DR4")
    test_cfg = profile.with_updates(
        pattern="ssprq", fec_mode="none", n_symbols=SSPRQ_PERIOD_SYMBOLS,
        coupling_il_db=coupling_loss_db,
        pmd_ps_sqrt_km=(2.20 / math.sqrt(profile.fiber_km)),
        pmd_power_split=0.5,
    )
    channel_loss_db = (test_cfg.coupling_il_db
                       + test_cfg.fiber_loss_db_km * test_cfg.fiber_km)
    dispersion_bounds = dr4_dispersion_bounds_ps_nm(test_cfg.wavelength_nm)
    expected_indices = ssprq_symbol_indices()
    digest = hashlib.sha256(expected_indices.tobytes()).hexdigest()
    cases = []

    for label, total_dispersion in zip(("minimum", "maximum"),
                                       dispersion_bounds):
        cfg = test_cfg.with_updates(
            dispersion_ps_nm_km=total_dispersion / test_cfg.fiber_km)
        sim = simulate(cfg, seed=seed, depth="light")
        tdecq = tdecq_report(
            sim.optical.P_fiber_w, sim.pam4_symbols, sim.spec,
            cfg.analog_sps, cfg.symbol_rate_hz, cfg.fs_analog_hz,
            target_ser=spec.target_ser, q_t=spec.q_t,
            histogram_width_ui=spec.histogram_width_ui)
        # Stima di convergenza numerica indipendente: stessa acquisizione
        # decimata 2:1, stesso reference receiver espresso a 8 sps.
        coarse = tdecq_report(
            sim.optical.P_fiber_w[::2], sim.pam4_symbols, sim.spec,
            cfg.analog_sps // 2, cfg.symbol_rate_hz, cfg.fs_analog_hz / 2,
            target_ser=spec.target_ser, q_t=spec.q_t,
            histogram_width_ui=spec.histogram_width_ui)
        expected_symbols = sim.spec.levels_array[expected_indices]
        vector_ok = bool(np.array_equal(sim.pam4_symbols, expected_symbols))
        failed_checks = [c for c in sim.checks if c["status"] == "FAIL"]
        tdecq_db = tdecq.get("tdecq_db")
        coarse_db = coarse.get("tdecq_db")
        grid_delta = (abs(tdecq_db - coarse_db)
                      if tdecq_db is not None and coarse_db is not None
                      else None)
        cases.append({
            "name": label,
            "total_dispersion_ps_nm": total_dispersion,
            "dispersion_ps_nm_km": cfg.dispersion_ps_nm_km,
            "dgd_ps": sim.optical.pmd_dgd_ps,
            "pattern_exact": vector_ok,
            "tdecq": tdecq,
            "tdecq_8sps_db": coarse_db,
            "numeric_grid_delta_db": grid_delta,
            "tdecq_model_pass": bool(tdecq_db is not None
                                      and tdecq_db <= spec.tdecq_limit_db),
            "link_up": bool(sim.link_up),
            "ber_post_dfe": (float(sim.ber_post_dfe)
                             if sim.link_up else None),
            "physical_checks_pass": len(failed_checks) == 0,
            "failed_checks": failed_checks,
            "power_budget_dbm": sim.optical.power_budget_dbm,
        })

    finite_tdecq = [c["tdecq"]["tdecq_db"] for c in cases
                    if c["tdecq"].get("tdecq_db") is not None]
    worst_tdecq = max(finite_tdecq) if len(finite_tdecq) == len(cases) else None
    grid_deltas = [c["numeric_grid_delta_db"] for c in cases
                   if c["numeric_grid_delta_db"] is not None]
    numeric_uncertainty = (max(grid_deltas)
                           if len(grid_deltas) == len(cases) else None)
    guarded_tdecq = (worst_tdecq + numeric_uncertainty
                     if worst_tdecq is not None
                     and numeric_uncertainty is not None else None)
    model_pass = bool(
        guarded_tdecq is not None and guarded_tdecq <= spec.tdecq_limit_db
        and all(c["pattern_exact"] and c["link_up"]
                and c["physical_checks_pass"] for c in cases))

    steps = [
        _step("identity", "Procedura e target versionati", "PASS",
              f"{spec.procedure_id} v{spec.version}", spec.target),
        _step("pattern", "Pattern completo bit-exact", "PASS" if (
                  digest == SSPRQ_SYMBOL_SHA256
                  and all(c["pattern_exact"] for c in cases)) else "FAIL",
              f"SSPRQ {SSPRQ_PERIOD_SYMBOLS:,} simboli",
              f"SHA-256 {digest}", SSPRQ_SOURCE_URL),
        _step("rate", "Rate e modulazione per lane", "PASS",
              "53.125 GBd PAM4 Gray", f"{test_cfg.symbol_rate_hz/1e9:g} GBd"),
        _step("channel", "Due estremi del canale di dispersione", "PASS",
              "Table 124-11: −0,93/+0,80 ps/nm totali",
              ", ".join(f"{v:+.4f} ps/nm" for v in dispersion_bounds),
              spec.channel_source),
        _step("channel_loss", "Perdita del canale ottico", "PASS" if
              channel_loss_db <= spec.channel_insertion_loss_max_db + 1e-12
              else "FAIL",
              f"Table 124-11: IL ≤ {spec.channel_insertion_loss_max_db:g} dB",
              (f"coupling {test_cfg.coupling_il_db:.3f} dB + fibra "
               f"{fiber_loss_db:.3f} dB = {channel_loss_db:.3f} dB"),
              spec.channel_source),
        _step("dgd", "DGD del canale di test", "PASS" if all(
                  c["dgd_ps"] <= spec.max_mean_dgd_ps for c in cases)
              else "FAIL", f"≤ {spec.max_mean_dgd_ps:g} ps",
              ", ".join(f"{c['dgd_ps']:.3f} ps" for c in cases),
              spec.channel_source),
        _step("reference_rx", "Reference receiver e TDECQ", "PASS" if
              worst_tdecq is not None else "FAIL",
              "BT4 + FFE 5 tap, Σc=1, finestre 0.45/0.55 UI × 0.04 UI",
              (f"worst TDECQ {worst_tdecq:.3f} dB"
               if worst_tdecq is not None else "SER oltre il target")),
        _step("calibration", "Calibrazione del ricevitore numerico", "PASS",
              "σS con ingresso ottico nullo e identiche impostazioni",
              "σS=0 W RMS: O/E e scope numerici ideali, valore esplicito"),
        _step("numeric_uncertainty", "Convergenza della griglia numerica",
              "PASS" if numeric_uncertainty is not None
              and numeric_uncertainty <= 0.15 else "WARN",
              "|TDECQ(16 sps)−TDECQ(8 sps)| ≤ 0.15 dB",
              (f"u_grid={numeric_uncertainty:.3f} dB"
               if numeric_uncertainty is not None else "non disponibile")),
        _step("tdecq_limit", "Limite TDECQ del modello", "PASS" if (
                  guarded_tdecq is not None
                  and guarded_tdecq <= spec.tdecq_limit_db) else "FAIL",
              f"TDECQ + u_grid ≤ {spec.tdecq_limit_db:g} dB",
              (f"worst+u {guarded_tdecq:.3f} dB"
               if guarded_tdecq is not None else "nessun valore finito")),
        _step("e2e", "Chiusura fisica TX→fibra→RX→DSP", "PASS" if all(
                  c["link_up"] and c["physical_checks_pass"] for c in cases)
              else "FAIL", "lock CDR, BER valida, checkpoint fisici senza FAIL",
              "; ".join(f"{c['name']}: link={'UP' if c['link_up'] else 'DOWN'}, "
                        f"BER={c['ber_post_dfe']}" for c in cases)),
        _step("reflection", "Return-loss e polarizzazione worst-case", "WARN",
              (f"ORL canale ≥{spec.channel_optical_return_loss_min_db:g} dB; "
               f"tolleranza TX {spec.tx_return_loss_tolerance_db:g} dB; "
               "massima RIN"),
              "riflettore ottico/feedback laser non ancora nel modello",
              spec.channel_source),
        _step("uncertainty", "Sistematiche metrologiche esterne", "WARN",
              "O/E, scope e fixture con taratura tracciabile",
              "convergenza numerica quantificata; sistematiche strumentali non disponibili"),
        _step("correlation", "Golden instrument correlation", "WARN",
              "waveform/reference result indipendente",
              "manca un dataset ufficiale con risultato TDECQ pubblicato"),
    ]

    return {
        "procedure": asdict(spec),
        "seed": int(seed),
        "test_config": test_cfg.to_dict(),
        "cases": cases,
        "steps": steps,
        "worst_tdecq_db": worst_tdecq,
        "numerical_uncertainty_db": numeric_uncertainty,
        "guarded_tdecq_db": guarded_tdecq,
        "tdecq_limit_db": spec.tdecq_limit_db,
        "model_status": "PASS" if model_pass else "FAIL",
        "compliance_status": "NOT ASSESSED",
        "allowed_claim": (
            "LabPro DR4 physical-model result only; no IEEE compliance claim"),
        "uncertainty_complete": False,
        "elapsed_s": time.perf_counter() - t0,
    }
