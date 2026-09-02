"""Procedure fisiche versionate eseguite sopra il datapath LabPro.

Una procedura e diversa da un preset: congela pattern, piano di misura,
canale di test, reference receiver e criteri.  Il risultato separa sempre il
verdetto del modello dal claim di conformita.  La prima procedura coperta e il
TDECQ per-lane DR4, costruito solo da materiale pubblico IEEE; riflessione
ottica/polarizzazione worst-case, incertezza metrologica completa e
correlazione con un golden instrument restano blocchi espliciti, quindi il
claim IEEE rimane ``NOT_ASSESSED``.

Ogni passo della checklist porta uno stato della tassonomia chiusa di
``serdes_sim.standards`` e una ``basis`` che dice da dove viene il criterio:
``clause`` (numero della norma), ``model`` (criterio interno dichiarato),
``proxy`` (idealizzazione dichiarata) o ``blocker`` (requisito non coperto).
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
from .engine import check_cancel, simulate
from .standards import (FAIL, MARGINAL, NOT_ASSESSED, PASS, PROXY,
                        TDECQ_HISTOGRAM_CENTERS_UI, TDECQ_HISTOGRAM_WIDTH_UI,
                        TDECQ_Q_T, TDECQ_TARGET_SER, evaluate_limit,
                        limits_for_interface)


DR4_PROFILE_NAME = "IEEE 802.3bs — 400GBASE-DR4 · 100G/λ ottico 500 m"
DR4_INTERFACE = "400GBASE-DR4"
DR4_TDECQ_PUBLIC_DRAFT = (
    "https://www.ieee802.org/3/bs/public/16_06/mazzini_3bs_01_0616.pdf"
)
DR4_CHANNEL_PUBLIC_TABLE = (
    "https://www.ieee802.org/3/df/public/22_12/brown_3df_03c_2212.pdf"
)
DR4_LIMITS = limits_for_interface(DR4_INTERFACE)
DR4_TDECQ_LIMIT = DR4_LIMITS["tdecq"]


@dataclass(frozen=True)
class Dr4TdecqProcedure:
    procedure_id: str = "labpro-dr4-tdecq-public-v1"
    version: str = "1.1.0"
    target: str = "400GBASE-DR4 per-lane transmitter model"
    standard_context: str = (
        "IEEE 802.3bs · Clause 124.8.5 (metodo 121.8.5) · Table 124-6/124-11"
    )
    symbol_rate_hz: float = 53.125e9
    modulation: str = "PAM4 Gray"
    pattern: str = "SSPRQ Clause 120, full public vector"
    pattern_symbols: int = SSPRQ_PERIOD_SYMBOLS
    tdecq_limit_db: float = DR4_TDECQ_LIMIT.limit
    tdecq_limit_source: str = (f"{DR4_TDECQ_LIMIT.standard} · "
                               f"{DR4_TDECQ_LIMIT.clause} · {DR4_TDECQ_LIMIT.table}")
    target_ser: float = TDECQ_TARGET_SER
    q_t: float = TDECQ_Q_T
    reference_receiver: str = "BT4 0.5·Bd + 5-tap T-spaced FFE"
    histogram_centers_ui: tuple = TDECQ_HISTOGRAM_CENTERS_UI
    histogram_width_ui: float = TDECQ_HISTOGRAM_WIDTH_UI
    channel_insertion_loss_max_db: float = 3.0
    max_dgd_ps: float = 2.24
    channel_optical_return_loss_min_db: float = 37.0
    tx_return_loss_tolerance_db: float = 21.4
    numeric_grid_gate_db: float = 0.15    # criterio INTERNO del modello
    sigma_s_w: float = 0.0                # ricevitore numerico ideale
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


def _step(step_id, label_it, label_en, status, req_it, req_en, evidence,
          basis, source=None):
    return {
        "id": step_id, "label": {"it": label_it, "en": label_en},
        "status": status, "basis": basis,
        "requirement": {"it": req_it, "en": req_en},
        "evidence": evidence,
        "source": source or DR4_TDECQ_PUBLIC_DRAFT,
    }


def run_dr4_tdecq_e2e(seed: int = 500283, cancel=None) -> dict:
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
        check_cancel(cancel)
        cfg = test_cfg.with_updates(
            dispersion_ps_nm_km=total_dispersion / test_cfg.fiber_km)
        sim = simulate(cfg, seed=seed, depth="light")
        tdecq = tdecq_report(
            sim.optical.P_fiber_w, sim.pam4_symbols, sim.spec,
            cfg.analog_sps, cfg.symbol_rate_hz, cfg.fs_analog_hz,
            target_ser=spec.target_ser, q_t=spec.q_t,
            histogram_width_ui=spec.histogram_width_ui,
            sigma_s_w=spec.sigma_s_w)
        # Stima di convergenza numerica indipendente: stessa acquisizione
        # decimata 2:1, stesso reference receiver espresso a 8 sps.
        coarse = tdecq_report(
            sim.optical.P_fiber_w[::2], sim.pam4_symbols, sim.spec,
            cfg.analog_sps // 2, cfg.symbol_rate_hz, cfg.fs_analog_hz / 2,
            target_ser=spec.target_ser, q_t=spec.q_t,
            histogram_width_ui=spec.histogram_width_ui,
            sigma_s_w=spec.sigma_s_w)
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
            "tdecq_verdict": evaluate_limit(
                DR4_TDECQ_LIMIT, tdecq_db, uncertainty=grid_delta,
                fail_reason=(None if tdecq_db is not None
                             else "SER above target with no added noise"),
                evidence=(f"{label}: TDECQ {tdecq_db:.3f} dB"
                          if tdecq_db is not None else f"{label}: no finite TDECQ")),
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
    chain_ok = all(c["pattern_exact"] and c["link_up"]
                   and c["physical_checks_pass"] for c in cases)
    tdecq_verdict = evaluate_limit(
        DR4_TDECQ_LIMIT, worst_tdecq, uncertainty=numeric_uncertainty,
        fail_reason=(None if worst_tdecq is not None
                     else "SER above target with no added noise"),
        evidence=(f"worst TDECQ {worst_tdecq:.3f} dB ± {numeric_uncertainty:.3f} dB "
                  f"(numerical grid) vs ≤ {spec.tdecq_limit_db:g} dB"
                  if worst_tdecq is not None and numeric_uncertainty is not None
                  else "no finite TDECQ on at least one endpoint"))
    model_status = tdecq_verdict["model"]
    if model_status in (PASS, MARGINAL) and not chain_ok:
        model_status = FAIL

    rate_ok = abs(test_cfg.symbol_rate_hz - spec.symbol_rate_hz) < 1.0
    steps = [
        _step("identity", "Procedura e target versionati",
              "Versioned procedure and target", PASS,
              f"{spec.procedure_id} v{spec.version}",
              f"{spec.procedure_id} v{spec.version}", spec.target, "model"),
        _step("pattern", "Pattern completo bit-exact", "Complete bit-exact pattern",
              PASS if (digest == SSPRQ_SYMBOL_SHA256
                       and all(c["pattern_exact"] for c in cases)) else FAIL,
              f"SSPRQ {SSPRQ_PERIOD_SYMBOLS:,} simboli (Clause 120.5.11.2.3)",
              f"SSPRQ {SSPRQ_PERIOD_SYMBOLS:,} symbols (Clause 120.5.11.2.3)",
              f"SHA-256 {digest}", "clause", SSPRQ_SOURCE_URL),
        _step("rate", "Rate e modulazione per lane", "Per-lane rate and modulation",
              PASS if rate_ok and test_cfg.modulation == "PAM4" else FAIL,
              "53.125 GBd PAM4 Gray (Clause 124)", "53.125 GBd PAM4 Gray (Clause 124)",
              f"{test_cfg.symbol_rate_hz/1e9:g} GBd {test_cfg.modulation}", "clause"),
        _step("channel", "Due estremi del canale di dispersione",
              "Both channel CD endpoints",
              PASS if dispersion_bounds == (-0.93, 0.80) else FAIL,
              "Table 124-11: −0,93/+0,80 ps/nm totali",
              "Table 124-11: −0.93/+0.80 ps/nm total",
              ", ".join(f"{v:+.4f} ps/nm" for v in dispersion_bounds),
              "clause", spec.channel_source),
        _step("channel_loss", "Perdita del canale ottico",
              "Optical-channel insertion loss",
              PASS if channel_loss_db <= spec.channel_insertion_loss_max_db + 1e-12
              else FAIL,
              f"Table 124-11: IL ≤ {spec.channel_insertion_loss_max_db:g} dB",
              f"Table 124-11: IL ≤ {spec.channel_insertion_loss_max_db:g} dB",
              (f"coupling {test_cfg.coupling_il_db:.3f} dB + fiber "
               f"{fiber_loss_db:.3f} dB = {channel_loss_db:.3f} dB"),
              "clause", spec.channel_source),
        _step("dgd", "DGD del canale di test", "Test-channel DGD",
              PASS if all(c["dgd_ps"] <= spec.max_dgd_ps for c in cases) else FAIL,
              f"DGD_max ≤ {spec.max_dgd_ps:g} ps (Table 124-11)",
              f"DGD_max ≤ {spec.max_dgd_ps:g} ps (Table 124-11)",
              ", ".join(f"{c['dgd_ps']:.3f} ps" for c in cases),
              "clause", spec.channel_source),
        _step("reference_rx", "Reference receiver e TDECQ",
              "Reference receiver and TDECQ",
              PASS if worst_tdecq is not None else FAIL,
              (f"BT4 0.5·Bd + FFE 5 tap, Σc=1, finestre "
               f"{spec.histogram_centers_ui[0]}/{spec.histogram_centers_ui[1]} UI "
               f"× {spec.histogram_width_ui} UI (121.8.5.3)"),
              (f"BT4 0.5·Bd + 5-tap FFE, Σc=1, windows "
               f"{spec.histogram_centers_ui[0]}/{spec.histogram_centers_ui[1]} UI "
               f"× {spec.histogram_width_ui} UI (121.8.5.3)"),
              (f"worst TDECQ {worst_tdecq:.3f} dB"
               if worst_tdecq is not None else "SER above target"), "clause"),
        _step("calibration", "Calibrazione del ricevitore numerico",
              "Numerical receiver calibration", PROXY,
              "σS misurata con ingresso ottico nullo e identiche impostazioni (121.8.5.3)",
              "σS measured with zero optical input and identical settings (121.8.5.3)",
              f"σS = {spec.sigma_s_w:g} W RMS: ideal numerical O/E and scope, declared",
              "proxy"),
        _step("numeric_uncertainty", "Convergenza della griglia numerica",
              "Numerical-grid convergence",
              (PASS if numeric_uncertainty is not None
               and numeric_uncertainty <= spec.numeric_grid_gate_db
               else (MARGINAL if numeric_uncertainty is not None else NOT_ASSESSED)),
              f"|TDECQ(16 sps)−TDECQ(8 sps)| ≤ {spec.numeric_grid_gate_db:g} dB (criterio interno)",
              f"|TDECQ(16 sps)−TDECQ(8 sps)| ≤ {spec.numeric_grid_gate_db:g} dB (internal criterion)",
              (f"u_grid = {numeric_uncertainty:.3f} dB"
               if numeric_uncertainty is not None else "not available"), "model"),
        _step("tdecq_limit", "Limite TDECQ del modello", "Model TDECQ limit",
              tdecq_verdict["model"],
              f"TDECQ ± u_grid vs ≤ {spec.tdecq_limit_db:g} dB ({spec.tdecq_limit_source})",
              f"TDECQ ± u_grid vs ≤ {spec.tdecq_limit_db:g} dB ({spec.tdecq_limit_source})",
              (f"worst+u {guarded_tdecq:.3f} dB"
               if guarded_tdecq is not None else "no finite value"), "clause",
              DR4_TDECQ_LIMIT.source),
        _step("e2e", "Chiusura fisica TX→fibra→RX→DSP",
              "Physical TX→fiber→RX→DSP closure",
              PASS if all(c["link_up"] and c["physical_checks_pass"] for c in cases)
              else FAIL,
              "lock CDR, BER valida, checkpoint fisici senza FAIL",
              "CDR lock, valid BER, physical checkpoints without FAIL",
              "; ".join(f"{c['name']}: link={'UP' if c['link_up'] else 'DOWN'}, "
                        f"BER={c['ber_post_dfe']}" for c in cases), "model"),
        _step("reflection", "Return-loss e polarizzazione worst-case",
              "Worst-case return loss and polarization", NOT_ASSESSED,
              (f"ORL canale ≥ {spec.channel_optical_return_loss_min_db:g} dB; "
               f"tolleranza TX {spec.tx_return_loss_tolerance_db:g} dB; massima RIN"),
              (f"channel ORL ≥ {spec.channel_optical_return_loss_min_db:g} dB; "
               f"TX tolerance {spec.tx_return_loss_tolerance_db:g} dB; maximum RIN"),
              "optical reflector / laser feedback not yet in the model",
              "blocker", spec.channel_source),
        _step("uncertainty", "Sistematiche metrologiche esterne",
              "External metrology systematics", NOT_ASSESSED,
              "O/E, scope e fixture con taratura tracciabile",
              "O/E, scope and fixture with traceable calibration",
              "numerical convergence quantified; instrument systematics unavailable",
              "blocker"),
        _step("correlation", "Golden instrument correlation",
              "Golden-instrument correlation", NOT_ASSESSED,
              "waveform/reference result indipendente",
              "independent waveform/reference result",
              "no official dataset with a published TDECQ result", "blocker"),
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
        "limit": DR4_TDECQ_LIMIT.as_dict(),
        "verdict": dict(tdecq_verdict, model=model_status),
        "model_status": model_status,
        "compliance_status": NOT_ASSESSED,
        "allowed_claim": (
            "LabPro DR4 physical-model result only; no IEEE compliance claim"),
        "uncertainty_complete": False,
        "elapsed_s": time.perf_counter() - t0,
    }
