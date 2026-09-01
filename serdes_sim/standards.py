"""Standards contract for LabPro measurements.

There is no single IEEE 802.3 procedure that applies to every waveform and
diagnostic.  This registry makes the distinction explicit: a measure either
names its profile/clause and reference plane, or is labelled an instrument /
engineering diagnostic with no normative limit.  UI panels consume this data
instead of inferring compliance from a familiar metric name.
"""

from __future__ import annotations


IEEE_8023 = "https://www.ieee802.org/3/"
IEEE_COM = "https://www.ieee802.org/3/ad_hoc/COM/public/"


def measurement_contracts(cfg, active_profile=None, active_meta=None):
    active_meta = active_meta or {}
    interface = active_meta.get("interface")
    standard = active_meta.get("standard", "IEEE 802.3 profile required")
    optical_pam4 = cfg.link_medium == "optical" and cfg.modulation == "PAM4"
    electrical_pam4 = cfg.link_medium == "copper" and cfg.modulation == "PAM4"
    kr1_com = electrical_pam4 and abs(cfg.symbol_rate_hz - 53.125e9) < 1.0

    def row(mid, measure, reference, clause, plane, applicable, implementation,
            compliance, note, source=IEEE_8023):
        return {
            "id": mid, "measure": measure, "standard": reference,
            "clause": clause, "reference_plane": plane,
            "applicable": bool(applicable), "implementation": implementation,
            "compliance": compliance, "note": note, "source": source,
        }

    return [
        row("com", "COM", "IEEE 802.3ck", "Annex 93A · 100GBASE-KR1",
            "passive electrical channel incl. declared TX/RX package", kr1_com,
            "annex-subset",
            "not-assessed",
            "DER₀=1e-4, prescribed FFE/CTLE/DFE and package cases; a complete victim/NEXT/FEXT S-parameter set is still required for compliance.",
            IEEE_COM),
        row("tdecq", "TDECQ", "IEEE 802.3", "121.8.5.3",
            "optical PMD measurement point after the reference receiver",
            optical_pam4, "clause-structured", "not-assessed",
            "BT4 0.5·Bd, 5-tap reference FFE, DER target, and the public Clause 120 SSPRQ vector are implemented; forcing that pattern through the complete acquisition/calibration procedure and golden instrument correlation remain open."),
        row("sndr", "SNDR", "IEEE 802.3", "120D.3.1 / profile clause",
            "specified electrical or optical transmitter test point",
            cfg.modulation == "PAM4", "declared-proxy", "not-assessed",
            "Linear pulse fit removes linear ISI; the active profile must select its exact pattern, filter and observation plane before a limit can be used."),
        row("rlm", "RLM", "IEEE 802.3", "120D.3.1.2 where applicable",
            "transmitter output after the clause reference receiver",
            cfg.modulation == "PAM4", "proxy", "not-assessed",
            "Cluster-spacing proxy only; JP03B and the clause procedure are not yet implemented, so no pass/fail limit is exposed."),
        row("optical_levels", "OMA / ER / P0…P3", standard,
            "active PMD transmitter characteristics", "optical PMD TP",
            cfg.link_medium == "optical", "profile-context", "not-assessed",
            "Levels are measured on the physical waveform; exact averaging, pattern and reference filter remain profile-specific."),
        row("eye_opening", "EH / EW @ BER", "IEEE 802.3 profile required",
            "profile-specific stressed-eye / transmitter procedure",
            "selected DCA node after declared reference filter", True,
            "gaussian-tail-extrapolation", "not-assessed",
            "The BER target is explicit, but generic cluster-tail extrapolation is not a substitute for a clause mask or receiver calibration."),
        row("jitter", "RJ / DJ(δδ) / TJ", "IEEE 802.3 profile required",
            "profile-specific jitter output / tolerance clause",
            "selected clock or signal crossing plane", True,
            "dual-dirac-tail-fit", "not-assessed",
            "The decomposition follows a declared dual-Dirac model; a profile pattern, bandwidth and test duration are required before IEEE limits apply."),
        row("ber", "BER / SER", standard,
            "active PMA/PMD receiver test procedure", "post-slicer, pre-FEC",
            True, "counted-with-confidence", "not-assessed",
            "Clopper–Pearson confidence is reported; the current record length is educational and does not meet every clause observation-time requirement."),
        row("fec", "FEC corrected / uncorrectable codewords", standard,
            "active PCS/FEC clause", "RS decoder output", cfg.fec_mode != "none",
            "in-path-codec", "not-assessed",
            "The selected RS code is real; full PCS lane distribution, alignment markers and clause test vectors remain separate requirements."),
        row("jtol", "JTOL", "IEEE 802.3 profile required",
            "profile-specific jitter tolerance mask", "receiver input",
            electrical_pam4, "engineering-sweep", "not-assessed",
            "PJ bisection measures the model CDR response; it is not compared with a mask unless a complete profile procedure is available."),
        row("traffic", "throughput / FLR / latency", "IEEE 802.3 + IETF/ITU procedure required",
            "MAC/PCS plus selected traffic-test method", "L2 service interface",
            cfg.pattern == "eth", "engineering-benchmark", "not-assessed",
            "Ethernet frames traverse the model, but RFC 2544/Y.1564 procedures are not IEEE 802.3 PHY compliance measurements."),
    ]
