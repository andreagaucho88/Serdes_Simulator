"""Self-test headless del motore: python -m serdes_sim.selftest

Esegue la catena in depth light e full, stampa checkpoint e metriche chiave,
e verifica la coerenza con il notebook v7 (stessi ordini di grandezza).
"""

from __future__ import annotations

import sys
import time

import numpy as np

from .config import LinkConfig, PRESETS
from .engine import simulate, sweep


def main():
    print("=== serdes_sim selftest ===")

    t0 = time.perf_counter()
    light = simulate(LinkConfig(), depth="light")
    t_light = time.perf_counter() - t0
    print(f"[light] {t_light:.2f} s, BER pre-EQ={light.ber_pre_eq:.3e}, "
          f"FSE={light.ber_post_fse:.3e}, FSE+DFE={light.ber_post_dfe:.3e}, "
          f"GMI={light.gmi_total:.4f}")

    t0 = time.perf_counter()
    full = simulate(LinkConfig(), depth="full")
    t_full = time.perf_counter() - t0
    print(f"[full]  {t_full:.2f} s")

    n_fail = 0
    for ck in full.checks:
        mark = "✓" if ck["status"] == "PASS" else "✗"
        print(f"  {mark} {ck['check']}" + (f" — {ck['detail']}" if ck["detail"] else ""))
        n_fail += ck["status"] == "FAIL"

    print(f"checks: {len(full.checks)} totali, {n_fail} FAIL")
    for row in full.metrics_rows:
        print(f"  {row['stage']:<14} BER={row['BER']:.3e} "
              f"({row['bit_errors']}/{row['bits']} bit)")
    print(f"  GMI = {full.gmi_total:.4f} bit/simbolo "
          f"(A={full.gmi_per_bit[0]:.4f}, B={full.gmi_per_bit[1]:.4f})")
    print(f"  power budget: {full.optical.power_budget_dbm}")
    print(f"  timing: delay={full.timing.rx_integer_delay_ui:+d} UI, "
          f"fase={full.timing.best_phase_ui:+.4f} UI")
    print(f"  bathtub: floor={full.bathtub.plot_floor:.2e}, "
          f"min BER empirica={full.bathtub.empirical_ber.min():.2e}")
    print(f"  tone-lab: SNDR ideal={full.tone_lab.sndr_ideal_db:.1f} dB, "
          f"mismatch={full.tone_lab.sndr_mismatch_db:.1f} dB")

    # attese di coerenza con il notebook v7 (default 2 km)
    assert full.ber_post_fse <= full.ber_pre_eq, "FSE deve migliorare la BER"
    assert full.gmi_total > 1.0, "GMI implausibilmente bassa con i default"
    assert full.timing.gardner_scurve is not None
    assert full.eq.propagation_span is not None

    # ogni preset deve almeno girare in light senza eccezioni; con il CDR
    # reale un preset può legittimamente essere LINK DOWN
    for name, (cfg_preset, _) in PRESETS.items():
        r = simulate(cfg_preset, depth="light")
        if r.link_up:
            print(f"[preset] {name}: BER FSE+DFE={r.ber_post_dfe:.2e}, "
                  f"GMI={r.gmi_total:.3f}")
        else:
            print(f"[preset] {name}: LINK DOWN "
                  f"({r.cdr.detail if r.cdr else 'oracle'})")

    # sweep breve
    rows = sweep(LinkConfig(), "fiber_km", np.linspace(0, 4, 3))
    assert len(rows) == 3
    print("[sweep] fiber_km 0→4 km:", [f"{r['BER_FSE_DFE']:.1e}" for r in rows])

    # --- modulazioni e PRBS alternativi ------------------------------------
    from .blocks.stimulus import prbs_bits, PRBS_TAPS
    for order in PRBS_TAPS:
        period = 2 ** order - 1
        if order <= 15:
            two = prbs_bits(order, 2 * period)
            assert np.array_equal(two[:period], two[period:]), f"periodo PRBS{order}"
    print("[prbs] periodi verificati per ordini <= 15")

    for kwargs, label in [
        (dict(modulation="NRZ"), "NRZ"),
        (dict(modulation="PAM4", pam4_mapping="binary"), "PAM4 binary"),
        (dict(prbs_order=7), "PAM4 gray PRBS7"),
        (dict(prbs_order=31), "PAM4 gray PRBS31"),
    ]:
        r = simulate(LinkConfig(**kwargs), depth="light")
        if not r.link_up:
            print(f"[mod] {label}: LINK DOWN")
            continue
        assert r.gmi_total <= r.spec.bits_per_symbol + 1e-6
        print(f"[mod] {label}: BER FSE+DFE={r.ber_post_dfe:.2e}, "
              f"GMI={r.gmi_total:.3f}/{r.spec.bits_per_symbol}")

    # NRZ deve essere molto più robusto del PAM4 sullo stesso canale
    r_nrz = simulate(LinkConfig(modulation="NRZ"), depth="light")
    r_pam4 = simulate(LinkConfig(), depth="light")
    assert r_nrz.ber_post_dfe <= r_pam4.ber_post_dfe, "NRZ dovrebbe battere PAM4"

    # Gray deve dare BER <= binary a pari canale (errori fra livelli adiacenti)
    r_bin = simulate(LinkConfig(pam4_mapping="binary"), depth="light")
    print(f"[mapping] gray={r_pam4.ber_post_dfe:.3e} vs binary={r_bin.ber_post_dfe:.3e}")
    assert r_pam4.ber_post_dfe <= r_bin.ber_post_dfe * 1.05

    # --- canale S2P nel percorso principale --------------------------------
    from .blocks.channel import DEMO_S2P
    r_s2p = simulate(LinkConfig(s2p_text=DEMO_S2P, s2p_name="demo",
                                use_s2p_channel=True), depth="light")
    print(f"[s2p] canale misurato demo: BER FSE+DFE={r_s2p.ber_post_dfe:.2e}, "
          f"GMI={r_s2p.gmi_total:.3f}")

    # --- IBIS-AMI demo -----------------------------------------------------
    import tempfile
    from . import ami
    try:
        lib_path = ami.build_demo_model(tempfile.mkdtemp(prefix="ami_demo_"))
        model = ami.AmiModel(lib_path)
        cfg0 = LinkConfig()
        impulse = np.zeros(64 * cfg0.analog_sps)
        impulse[8 * cfg0.analog_sps] = 1.0
        res_init = model.init(impulse, 1 / cfg0.fs_analog_hz, cfg0.ui_s)
        assert res_init.ok and res_init.output is not None
        assert not np.allclose(res_init.output, impulse), "Init deve modificare l'impulso"
        wave = 0.9 * np.sin(np.linspace(0, 20 * np.pi, 512))
        res_wave = model.getwave(wave)
        assert res_wave.ok and np.max(np.abs(res_wave.output)) < np.max(np.abs(wave)) * 1.2
        model.close()
        tree = ami.parse_ami_tree("(demo_tx (ffe_taps 3) (mode \"init+getwave\"))")
        assert tree[0] == "demo_tx"
        print(f"[ami] demo model OK: Init msg='{res_init.msg}', "
              f"params_out='{res_init.params_out}'")
    except RuntimeError as exc:
        print(f"[ami] SKIP (compilatore non disponibile): {exc}")

    print("SELFTEST OK" if n_fail == 0 else "SELFTEST: alcuni check FAIL (vedi sopra)")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
