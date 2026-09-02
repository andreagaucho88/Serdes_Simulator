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
                        TDECQ_Q_T, TDECQ_TARGET_SER, ber_verdict,
                        evaluate_limit, limits_for_interface, verdict)


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
# Spazio di stress della procedura: split di polarizzazione, riflessione
# (return loss della tolleranza TX) e RIN di stress (valore dichiarato).
DR4_POLARIZATION_SPLITS = (0.0, 0.5, 1.0)
DR4_STRESS_RIN_DB_HZ = -136.0          # RIN alla sorgente; dichiarato: RIN_21.4OMA
                                       # (max) di clausola da verificare sul testo
DR4_REFLECTION_DELAY_NS = 5.0


@dataclass(frozen=True)
class Dr4TdecqProcedure:
    procedure_id: str = "labpro-dr4-tdecq-public-v1"
    version: str = "1.2.0"
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
    polarization_splits: tuple = DR4_POLARIZATION_SPLITS
    stress_rin_db_hz: float = DR4_STRESS_RIN_DB_HZ
    reflection_delay_ns: float = DR4_REFLECTION_DELAY_NS
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


def run_dr4_tdecq_e2e(seed: int = 500283, cancel=None, golden=None,
                      progress=None) -> dict:
    """Esegue la procedura DR4 v1.2 sullo spazio di stress completo.

    Casi: due estremi di dispersione × tre split di polarizzazione (DGD al
    massimo pubblico), più il caso di riflessione (return loss alla
    tolleranza TX, eco coerente) e il caso RIN di stress.  Ogni caso
    percorre davvero PPG → TX → canale elettrico → E/O → fibra di
    compliance → PD/TIA/AGC/ADC → CDR/FSE/DFE.  Il TDECQ usa la potenza al
    termine del canale di compliance; BER e lock chiudono invece la catena
    fisica completa.  Il banco dell'utente non viene modificato.
    ``golden`` è l'ultimo risultato di correlazione (serdes_sim.golden), che
    chiude lo step corrispondente quando la sorgente è uno strumento.
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

    grid = []
    for label, total_dispersion in zip(("minimum", "maximum"), dispersion_bounds):
        for split in spec.polarization_splits:
            grid.append({"name": f"{label}·pol{split:g}", "endpoint": label,
                         "dispersion": total_dispersion, "split": split,
                         "stress": "polarization"})
    grid.append({"name": "maximum·reflection", "endpoint": "maximum",
                 "dispersion": dispersion_bounds[1], "split": 0.5,
                 "stress": "reflection"})
    grid.append({"name": "maximum·rin", "endpoint": "maximum",
                 "dispersion": dispersion_bounds[1], "split": 0.5,
                 "stress": "rin"})
    for i, case_def in enumerate(grid):
        check_cancel(cancel)
        if progress is not None:
            progress(i, len(grid), case_def["name"])
        label = case_def["name"]
        total_dispersion = case_def["dispersion"]
        updates = dict(dispersion_ps_nm_km=total_dispersion / test_cfg.fiber_km,
                       pmd_power_split=case_def["split"])
        if case_def["stress"] == "reflection":
            updates.update(optical_return_loss_db=spec.tx_return_loss_tolerance_db,
                           optical_reflection_delay_ns=spec.reflection_delay_ns)
        if case_def["stress"] == "rin":
            updates.update(rin_db_hz=spec.stress_rin_db_hz, rin_at_source=True)
        cfg = test_cfg.with_updates(**updates)
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
            "endpoint": case_def["endpoint"], "stress": case_def["stress"],
            "polarization_split": case_def["split"],
            "return_loss_db": (cfg.optical_return_loss_db or None),
            "rin_db_hz": cfg.rin_db_hz,
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
    # peggior TDECQ FINITO; i casi senza valore finito (SER oltre il target
    # anche senza rumore aggiunto) sono elencati e forzano il FAIL del limite
    worst_tdecq = max(finite_tdecq) if finite_tdecq else None
    missing_tdecq = [c["name"] for c in cases if c["tdecq"].get("tdecq_db") is None]
    all_finite = not missing_tdecq
    worst_case = (max(cases, key=lambda c: c["tdecq"].get("tdecq_db") or -1)["name"]
                  if finite_tdecq else None)
    baseline = [c for c in cases if c["stress"] == "polarization" and c["polarization_split"] == 0.5]
    base_max = max((c["tdecq"]["tdecq_db"] for c in baseline
                    if c["tdecq"].get("tdecq_db") is not None), default=None)
    pol_cases = [c for c in cases if c["stress"] == "polarization"]
    pol_worst = max((c["tdecq"]["tdecq_db"] for c in pol_cases
                     if c["tdecq"].get("tdecq_db") is not None), default=None)
    refl = next((c for c in cases if c["stress"] == "reflection"), None)
    rin_case = next((c for c in cases if c["stress"] == "rin"), None)
    refl_db = refl["tdecq"].get("tdecq_db") if refl else None
    rin_db = rin_case["tdecq"].get("tdecq_db") if rin_case else None
    grid_deltas = [c["numeric_grid_delta_db"] for c in cases
                   if c["numeric_grid_delta_db"] is not None]
    numeric_uncertainty = max(grid_deltas) if grid_deltas else None
    guarded_tdecq = (worst_tdecq + numeric_uncertainty
                     if worst_tdecq is not None
                     and numeric_uncertainty is not None else None)
    chain_ok = all(c["pattern_exact"] and c["link_up"]
                   and c["physical_checks_pass"] for c in cases)
    tdecq_verdict = evaluate_limit(
        DR4_TDECQ_LIMIT, worst_tdecq if all_finite else None,
        uncertainty=numeric_uncertainty,
        fail_reason=(None if all_finite
                     else "SER above target with no added noise on "
                          + ", ".join(missing_tdecq)),
        evidence=(f"worst TDECQ {worst_tdecq:.3f} dB ± {numeric_uncertainty:.3f} dB "
                  f"(numerical grid) vs ≤ {spec.tdecq_limit_db:g} dB"
                  if all_finite and worst_tdecq is not None
                  and numeric_uncertainty is not None
                  else "no finite TDECQ on " + ", ".join(missing_tdecq)
                  + (f"; worst finite {worst_tdecq:.3f} dB" if worst_tdecq is not None else "")))
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
              f"{cases[0]['dgd_ps']:.3f} ps on every case", "clause", spec.channel_source),
        _step("polarization", "Spazio di polarizzazione (split PSP)",
              "Polarization space (PSP power split)",
              (PASS if pol_worst is not None and pol_worst <= spec.tdecq_limit_db
               else (FAIL if pol_worst is not None else NOT_ASSESSED)),
              f"split {'/'.join(f'{v:g}' for v in spec.polarization_splits)} a DGD massimo, TDECQ ≤ limite",
              f"splits {'/'.join(f'{v:g}' for v in spec.polarization_splits)} at maximum DGD, TDECQ ≤ limit",
              (f"worst over splits {pol_worst:.3f} dB (50/50: {base_max:.3f} dB)"
               if pol_worst is not None and base_max is not None else "no finite value"),
              "model"),
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
              PASS if all(c["link_up"] and c["physical_checks_pass"]
                          for c in cases if c["stress"] == "polarization")
              else FAIL,
              "lock CDR, BER valida, checkpoint fisici senza FAIL sulla griglia "
              "dispersione × polarizzazione (i casi di stress hanno il proprio passo)",
              "CDR lock, valid BER, physical checkpoints without FAIL over the "
              "dispersion × polarization grid (stress cases have their own step)",
              "; ".join(f"{c['name']}: link={'UP' if c['link_up'] else 'DOWN'}, "
                        f"BER={c['ber_post_dfe']}" for c in cases), "model"),
        _step("reflection", "MPI alla tolleranza ORL del TX (coppia di riflessioni)",
              "MPI at the TX ORL tolerance (reflection pair)",
              (PASS if refl_db is not None and refl_db <= spec.tdecq_limit_db
               else (FAIL if refl_db is not None else NOT_ASSESSED)),
              (f"due discontinuità a {spec.tx_return_loss_tolerance_db:g} dB ciascuna "
               f"(eco coerente a −{2 * spec.tx_return_loss_tolerance_db:g} dB), ritardo "
               f"{spec.reflection_delay_ns:g} ns, fase casuale; TDECQ ≤ limite"),
              (f"two discontinuities at {spec.tx_return_loss_tolerance_db:g} dB each "
               f"(coherent echo at −{2 * spec.tx_return_loss_tolerance_db:g} dB), "
               f"{spec.reflection_delay_ns:g} ns delay, random phase; TDECQ ≤ limit"),
              (f"TDECQ {refl_db:.3f} dB with reflection vs {base_max:.3f} dB without "
               f"(Δ {refl_db - base_max:+.3f} dB)" if refl_db is not None and base_max is not None
               else "no finite value"),
              "model", spec.channel_source),
        _step("rin", "RIN di stress alla sorgente", "Stress RIN at the source",
              (PASS if rin_db is not None and rin_db <= spec.tdecq_limit_db
               else (FAIL if rin_db is not None else NOT_ASSESSED)),
              (f"RIN {spec.stress_rin_db_hz:g} dB/Hz nel campo ottico (valore di stress "
               f"dichiarato; RIN_21.4OMA di clausola da verificare); TDECQ ≤ limite"),
              (f"RIN {spec.stress_rin_db_hz:g} dB/Hz in the optical field (declared stress "
               f"value; clause RIN_21.4OMA to verify); TDECQ ≤ limit"),
              (f"TDECQ {rin_db:.3f} dB with stress RIN vs {base_max:.3f} dB "
               f"(Δ {rin_db - base_max:+.3f} dB)"
               if rin_db is not None and base_max is not None else "no finite value"),
              "proxy"),
        _step("uncertainty", "Sistematiche metrologiche esterne",
              "External metrology systematics", NOT_ASSESSED,
              "O/E, scope e fixture con taratura tracciabile",
              "O/E, scope and fixture with traceable calibration",
              "numerical convergence quantified; instrument systematics unavailable",
              "blocker"),
        _golden_step(golden),
    ]

    return {
        "procedure": asdict(spec),
        "seed": int(seed),
        "test_config": test_cfg.to_dict(),
        "cases": cases,
        "steps": steps,
        "worst_tdecq_db": worst_tdecq,
        "worst_case": worst_case,
        "all_finite": all_finite,
        "cases_without_tdecq": missing_tdecq,
        "baseline_tdecq_db": base_max,
        "stress_space": {"polarization_splits": list(spec.polarization_splits),
                         "reflection_return_loss_db": spec.tx_return_loss_tolerance_db,
                         "reflection_delay_ns": spec.reflection_delay_ns,
                         "stress_rin_db_hz": spec.stress_rin_db_hz,
                         "cases": len(cases)},
        "golden": golden,
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


def _golden_step(golden):
    if not golden or not golden.get("ok"):
        return _step("correlation", "Golden instrument correlation",
                     "Golden-instrument correlation", NOT_ASSESSED,
                     "waveform/reference result indipendente (carica un dataset golden)",
                     "independent waveform/reference result (load a golden dataset)",
                     "no golden dataset loaded", "blocker")
    v = golden["verdict"]
    if golden.get("source") != "instrument":
        return _step("correlation", "Golden instrument correlation",
                     "Golden-instrument correlation", PROXY,
                     "dataset sintetico: esercita la pipeline, non correla uno strumento",
                     "synthetic dataset: exercises the pipeline, does not correlate an instrument",
                     v.get("evidence", ""), "proxy")
    return _step("correlation", "Golden instrument correlation",
                 "Golden-instrument correlation", v["model"],
                 f"|Δ| ≤ {golden.get('tolerance_db', 0.3):g} dB vs {golden.get('instrument') or 'instrument'}",
                 f"|Δ| ≤ {golden.get('tolerance_db', 0.3):g} dB vs {golden.get('instrument') or 'instrument'}",
                 v.get("evidence", ""), "model")


# ---------------------------------------------------------------------------
# Stressed receiver calibration (SECQ) — versione 2
# ---------------------------------------------------------------------------
STRESSED_RX_VERSION = "2.0.0"
STRESSED_SJ_UI = 0.05          # dichiarato: ampiezza SJ di stress
STRESSED_SJ_MHZ = 100.0        # dichiarato: frequenza SJ di stress
STRESSED_RIN_RANGE = (-165.0, -118.0)
STRESSED_RX_FINAL_SYMBOLS = 32768       # record del test BER finale (PRBS)


def run_stressed_receiver(cfg, profile=None, seed: int = 500283,
                          sj_ui: float = STRESSED_SJ_UI,
                          sj_mhz: float = STRESSED_SJ_MHZ, si_pct: float = 0.0,
                          si_mhz: float = 1000.0,
                          target_secq_db=None, iters: int = 8, cancel=None) -> dict:
    """Calibrazione dello stressed eye sul SECQ (struttura 802.3 stressed
    receiver sensitivity): SJ + rumore gaussiano (RIN) calibrati finché il
    SECQ misurato con il ricevitore di riferimento TDECQ all'ingresso RX
    raggiunge il target del registro, poi test del RX in quelle condizioni
    con verdetto BER contro il requisito PMD.

    DICHIARATO: niente interferenza sinusoidale (SI) né strumenti calibrati;
    SJ e range del rumore sono parametri dichiarati.  Solo mezzo ottico.
    """
    from .config import STANDARD_PROFILE_META
    from .standards import limits_for_interface as _lims
    t0 = time.perf_counter()
    if cfg.link_medium != "optical" or cfg.modulation != "PAM4":
        raise ValueError("stressed receiver (SECQ): richiede link ottico PAM4")
    meta = STANDARD_PROFILE_META.get(profile, {}) if profile else {}
    lims = _lims(meta.get("interface"))
    lim = lims.get("tdecq")
    if target_secq_db is None:
        if lim is not None and lim.limit is not None and lim.confidence == "published":
            target = float(lim.limit)
            target_basis = "clause"
        else:
            target = 3.4
            target_basis = "model"
    else:
        target = float(target_secq_db)
        target_basis = "model"
    base = cfg.with_updates(tx_pj_amp_ui=float(sj_ui), tx_pj_freq_mhz=float(sj_mhz),
                            tx_si_amp_pct=float(si_pct), tx_si_freq_mhz=float(si_mhz),
                            rin_at_source=True,
                            fec_mode="none" if cfg.pattern != "prbs" else cfg.fec_mode)
    trail = []

    def run_at(rin, n_symbols=None):
        check_cancel(cancel)
        c = base.with_updates(rin_db_hz=float(rin),
                              **({"n_symbols": int(n_symbols)} if n_symbols else {}))
        sim = simulate(c, seed=seed, depth="light")
        rep = tdecq_report(sim.optical.P_fiber_w, sim.pam4_symbols, sim.spec,
                           c.analog_sps, c.symbol_rate_hz, c.fs_analog_hz)
        return rep.get("tdecq_db"), sim

    def secq_at(rin):
        val, sim = run_at(rin)
        trail.append({"rin_db_hz": float(rin), "secq_db": val,
                      "link_up": bool(sim.link_up),
                      "ber": (float(sim.ber_post_dfe) if sim.link_up else None)})
        return val, sim

    lo, hi = STRESSED_RIN_RANGE
    s_lo, _ = secq_at(lo)
    status = "ok"
    if s_lo is None or s_lo >= target:
        status = "already_above"        # il TX da solo eccede il target
        rin_cal, secq_cal, sim_cal = lo, s_lo, None
    else:
        s_hi, _ = secq_at(hi)
        if s_hi is not None and s_hi < target:
            status = "stress_insufficient"
            rin_cal, secq_cal, sim_cal = hi, s_hi, None
        else:
            for _ in range(int(iters)):
                mid = 0.5 * (lo + hi)
                s_mid, _ = secq_at(mid)
                if s_mid is None or s_mid >= target:
                    hi = mid
                else:
                    lo = mid
            rin_cal = lo                       # SECQ appena SOTTO il target
            secq_cal = next((t["secq_db"] for t in reversed(trail)
                             if t["rin_db_hz"] == rin_cal), None)
    # Test finale del RX alla ricetta calibrata su un record LUNGO (PRBS):
    # con ~10 kbit e zero errori il bound Clopper-Pearson resta sopra la
    # soglia KP4 (MARGINAL); con ≥ 60 kbit il bound può chiudere il PASS.
    final_n = (max(int(base.n_symbols), STRESSED_RX_FINAL_SYMBOLS)
               if base.pattern == "prbs" else int(base.n_symbols))
    secq_final, sim_cal = run_at(rin_cal, final_n)
    secq_calibration_db = secq_cal
    secq_cal = secq_final if secq_final is not None else secq_cal
    row = sim_cal.metrics_rows[2] if sim_cal.link_up and len(sim_cal.metrics_rows) > 2 else None
    ber_lim = lims.get("ber_prefec")
    if row is not None:
        clause_v, model_v = ber_verdict(int(row["bit_errors"]), int(row["bits"]), ber_lim)
    else:
        clause_v = verdict(NOT_ASSESSED, basis="none", evidence="LINK DOWN under stress")
        model_v = None
    secq_v = evaluate_limit(lim, secq_cal, evidence=(f"SECQ {secq_cal:.3f} dB at RIN {rin_cal:.1f} dB/Hz"
                                                     if secq_cal is not None else "no finite SECQ"))
    fl = sim_cal.fec_link
    steps = [
        _step("target", "Target SECQ del profilo", "Profile SECQ target",
              PASS if target_basis == "clause" else PROXY,
              f"SECQ target = limite TDECQ del registro ({target:g} dB)" if target_basis == "clause"
              else f"target dichiarato {target:g} dB (nessun limite pubblicato)",
              f"SECQ target = registry TDECQ limit ({target:g} dB)" if target_basis == "clause"
              else f"declared target {target:g} dB (no published limit)",
              (f"{lim.standard} · {lim.clause}" if lim else "no profile"),
              "clause" if target_basis == "clause" else "proxy"),
        _step("sj", "Jitter sinusoidale di stress", "Stress sinusoidal jitter", PROXY,
              f"SJ {sj_ui:g} UI @ {sj_mhz:g} MHz (parametri dichiarati)",
              f"SJ {sj_ui:g} UI @ {sj_mhz:g} MHz (declared parameters)",
              "applied at the TX PLL; clause SJ table not transcribed", "proxy"),
        _step("calibration", "Calibrazione del rumore al target SECQ",
              "Noise calibration to the SECQ target",
              PASS if status == "ok" else FAIL,
              f"bisezione RIN in [{STRESSED_RIN_RANGE[0]:g}, {STRESSED_RIN_RANGE[1]:g}] dB/Hz, {iters} iterazioni",
              f"RIN bisection in [{STRESSED_RIN_RANGE[0]:g}, {STRESSED_RIN_RANGE[1]:g}] dB/Hz, {iters} iterations",
              {"ok": f"RIN {rin_cal:.2f} dB/Hz → SECQ {secq_cal:.3f} dB",
               "already_above": f"SECQ {s_lo:.3f} dB without added noise already ≥ target: TX exceeds the limit",
               "stress_insufficient": "even the maximum RIN does not reach the target SECQ"}[status]
              if secq_cal is not None or status != "ok" else "n/a",
              "model"),
        _step("secq", "SECQ al ricevitore di riferimento", "SECQ at the reference receiver",
              secq_v["model"],
              "stesso ricevitore di riferimento del TDECQ (BT4 + FFE 5 tap) sul segnale "
              "stressato, confrontato col limite del registro"
              + (" — con un target dichiarato sopra il limite il FAIL è atteso: lo stress "
                 "è oltre la clausola" if lim is not None and lim.limit is not None
                 and target > float(lim.limit) else ""),
              "same reference receiver as TDECQ (BT4 + 5-tap FFE) on the stressed signal, "
              "compared with the registry limit"
              + (" — with a declared target above the limit the FAIL is expected: the "
                 "stress is beyond the clause" if lim is not None and lim.limit is not None
                 and target > float(lim.limit) else ""),
              secq_v.get("evidence", "") + f" · final record {final_n:,} symbols",
              "clause" if lim else "model"),
        _step("rx_ber", "BER del RX sotto stress", "RX BER under stress", clause_v["model"],
              (f"BER pre-FEC ≤ {ber_lim.limit:g} (requisito PMD)" if ber_lim else "requisito PMD non trascritto"),
              (f"pre-FEC BER ≤ {ber_lim.limit:g} (PMD requirement)" if ber_lim else "PMD requirement not transcribed"),
              clause_v.get("evidence", ""), "clause" if ber_lim else "model"),
        _step("fec", "Codeword FEC sotto stress", "FEC codewords under stress",
              (PASS if fl is not None and fl.frames_uncorrectable == 0 else
               (FAIL if fl is not None else NOT_ASSESSED)),
              "nessun codeword non correggibile sul record",
              "no uncorrectable codeword on the record",
              (f"{fl.frames_uncorrectable} uncorrectable · post-FEC BER {fl.post_fec_ber:.3g}"
               if fl is not None else "FEC not in path"), "model"),
        _step("si", "Interferenza sinusoidale (SI)", "Sinusoidal interference (SI)",
              PROXY if si_pct > 0 else NOT_ASSESSED,
              (f"SI {si_pct:g} % @ {si_mhz:g} MHz sul driver (parametri dichiarati)" if si_pct > 0
               else "SI non applicata (imposta si_pct > 0); tabella SI di clausola non trascritta"),
              (f"SI {si_pct:g} % @ {si_mhz:g} MHz at the driver (declared parameters)" if si_pct > 0
               else "SI not applied (set si_pct > 0); clause SI table not transcribed"),
              ("additive tone at the TX driver output" if si_pct > 0
               else "no sinusoidal interference in this run"), "proxy"),
        _step("instruments", "Calibrazione strumentale", "Instrument calibration", NOT_ASSESSED,
              "O/E, scope, sorgenti di stress tracciabili", "traceable O/E, scope and stress sources",
              "numerical bench: no instrument uncertainty", "blocker"),
    ]
    model = (FAIL if status != "ok" or clause_v["model"] == FAIL
             else (clause_v["model"] if clause_v["model"] in (PASS, MARGINAL) else NOT_ASSESSED))
    return {
        "procedure": {"procedure_id": "labpro-stressed-rx-secq", "version": STRESSED_RX_VERSION,
                      "target": "stressed receiver calibration on SECQ",
                      "profile": profile, "interface": meta.get("interface")},
        "status": status, "target_secq_db": target, "target_basis": target_basis,
        "recipe": {"rin_db_hz": float(rin_cal), "tx_pj_amp_ui": float(sj_ui),
                   "tx_pj_freq_mhz": float(sj_mhz), "tx_si_amp_pct": float(si_pct),
                   "tx_si_freq_mhz": float(si_mhz)},
        "secq_db": secq_cal, "secq_verdict": secq_v,
        "secq_calibration_db": secq_calibration_db,
        "final_record_symbols": int(final_n),
        "rx": {"link_up": bool(sim_cal.link_up),
               "ber_post_dfe": (float(sim_cal.ber_post_dfe) if sim_cal.link_up else None),
               "bits": (int(row["bits"]) if row else 0),
               "errors": (int(row["bit_errors"]) if row else 0),
               "verdict": clause_v, "model_verdict": model_v,
               "fec_uncorrectable": (fl.frames_uncorrectable if fl is not None else None)},
        "trail": trail, "steps": steps,
        "model_status": model, "compliance_status": NOT_ASSESSED,
        "allowed_claim": "LabPro stressed-RX model result; no IEEE compliance claim",
        "seed": int(seed), "elapsed_s": time.perf_counter() - t0,
    }
