# Complete reference for all 32 Lab PRO panels

This guide documents every public instrument in signal-flow order. Return to
the [product overview and quick start](../README.md), or launch Lab PRO and use
the **?** control beside any knob for its bilingual physical contract.

### Overview

#### 1. Signal chain

Maps the real datapath from PPG to decoder. It distinguishes digital,
electrical, optical, and clock domains; shows the TX PLL, E/O and A/D
boundaries, active or bypassed FEC, and DCA markers. Every block is a
navigable link.

The health strip is derived from the current record checkpoints and localizes
driver, PD, TIA, ADC, CDR, equalizer, and slicer failures.

**Suggested experiment:** open one Scope on <code>Vdiff</code> and a second
one on <code>Vctle</code>, then increase channel loss. The markers identify
both reference planes and the ledger shows where degradation appears.

#### 2. Academy: block guide

A contextual IT/EN manual containing physics, formula, observables, guided
experiment, limitations, and relationships between blocks. The selector
follows the source panel, while **Open bench** returns directly to its
instrument.

### Source and transmitter

#### 3. BERT: TX generator and error analyzer

The one-box BERT contains four mutually exclusive subviews:

- **Generator / PPG:** PRBS 7/9/11/13/15/23/31, SSPRQ, custom hexadecimal
  data, clock patterns, and Ethernet; NRZ or Gray/binary PAM4; TX output and
  pattern preview.
- **Error detector:** BER/SER, PAM4 MSB/LSB lanes, pre/post-FEC taps, single
  or burst error insertion, and random/MSB/LSB/RS-symbol targeting.
- **Stress:** RJ, PJ, DCD, BUJ, SSC, and differential noise applied to the
  real TX time base or output.
- **Control and procedures:** gated start/stop, target BER, confidence
  interval, pattern lock, synchronization, JTF, and sensitivity workflows,
  plus the **stressed receiver (SECQ)** calibration: declared sinusoidal
  jitter at the TX PLL and RIN at the optical source bisected until the SECQ
  at the TDECQ reference receiver reaches the registry target (or a declared
  one), then the RX BER on a long record with a Clopper-Pearson verdict
  against the PMD pre-FEC limit. `already_above` means the TX alone exceeds
  the target; clause SI and instrument uncertainty stay
  <code>NOT_ASSESSED</code>.

The ED is a digital checker connected to the same physical RX. It is not a
second hidden analog receiver.

#### 4. TX: FIR, DAC, and driver

Controls FFE taps, DAC resolution and full scale, bandwidth, driver gain and
clipping, P/N skew and gain mismatch, common-mode offset and noise,
differential noise, differential or single-ended drive, and causal filters.

The panel exposes waveforms, swing, headroom, clipping, and the effective TX
response.

**Suggested experiment:** introduce P/N skew and compare the Scope quick sets
for P, N, differential, and common-mode signals.

### Channel and optics

#### 5. Electrical channel

The analytical model exposes insertion loss at Nyquist, return loss, delay,
group-delay ripple, echo, NEXT, and FEXT. A measured Touchstone file can
replace it in the main datapath.

Supported measured-channel inputs:

- Touchstone 1.x and 2.x;
- single-ended S2P;
- S4P converted to mixed mode with <code>13_24</code> or
  <code>12_34</code> port pairing;
- RI, MA, and DB data formats;
- a real, uniform reference impedance.

The picker accepts <code>.s2p</code>, <code>.s4p</code>, <code>.ts</code>,
and <code>.txt</code>. Invalid, non-monotonic, non-finite, or incompatible-Z0
files are rejected with an explicit error. **Return to model** disables the
measured S-parameter without disturbing unrelated settings.

#### 6. COM: IEEE 802.3 Annex 93A

Computes a declared Channel Operating Margin proxy from the measured
electrical chain. It separates available signal, ISI, crosstalk, and noise,
and reports response/cursors, noise denominator, and margin.

It is useful for understanding methodology and comparing configurations. It
does not replace the normative COM spreadsheet/package or a compliance
correlation.

#### 7. Optics: modulator and fiber

Selects CW-DFB plus MZM, DFB-EML, DFB-DML, or VCSEL/MMF. Controls include
laser power and linewidth, Vπ and bias or extinction ratio, chirp, bandwidth,
insertion loss, fiber type and length, loss, chromatic dispersion and slope,
PMD, Kerr nonlinearity, and modal bandwidth.

Changing architecture synchronizes the laser, modulator, fiber, drive mode,
and wavelength so the bench does not silently create impossible
combinations.

### Receiver and DSP

#### 8. RX front end: PD, TIA, and AGC

An aggregate analog budget showing PD power/current, noise, transimpedance,
automatic gain, clipping, and headroom. It is the fastest place to determine
whether a link is sensitivity-limited, overload-limited, or constrained by
ADC range.

#### 9. Photodiode

Controls responsivity, dark current, bandwidth, saturation current, and RIN.
Shot noise uses the actual current. PVT and temperature change dark current
and bandwidth according to the declared first-order assumptions.

Readouts include received optical power, photocurrent, noise density, and
saturation margin.

#### 10. TIA / electrical AFE

Controls transimpedance, input-referred noise density, VGA range, bandwidth,
headroom, and clipping. In an optical link it receives PD current; in a
copper link it represents the electrical AFE.

Impulse response and the noise budget separate bandwidth limitations from
sensitivity limitations.

#### 11. AGC: gain and headroom

Controls target RMS and minimum/maximum gain. The panel reports selected
gain, target residual, headroom, and saturation. The selected gain is applied
to the actual record passed to the CTLE and ADC.

#### 12. Configurable CTLE

Implements 1Z/1P, 1Z/2P, and 2Z/3P topologies, or explicit tuples containing
up to four zeros and five poles, together with DC gain.

Bode response, group delay, peaking, and noise enhancement use the same
transfer function as the datapath. Pulse/cursor plots expose the ISI versus
noise tradeoff.

#### 13. Interleaved ADC

Controls samples/symbol, resolution, full scale, phase, jitter, interleave
count, track-and-hold ranks, front-end bandwidth, gain/offset/skew/bandwidth
mismatch, input noise, and off/foreground/background calibration.

Readouts include range utilization, clipping, ENOB/SNDR proxies, and
PVT-dependent residual mismatch.

#### 14. Timing and CDR

Compares Gardner, Mueller-Müller, and a declared oracle mode. The second-order
PI loop uses normalized bandwidth, damping, and RX clock offset in ppm.

The panel shows CDR lock, BERT-style pattern lock, phase, frequency error,
TIE, and loop traces. Without lock the link is <code>DOWN</code>; downstream
metrics are intentionally unavailable rather than fabricated.

#### 15. RX FFE (FSE) and DFE

A T/2 fractionally spaced equalizer followed by a decision-feedback
equalizer. Controls select tap counts and the training window.

Coefficient, response/cursor, MSE, and before/after plots show what each
equalizer contributes. Checkpoints verify that the FSE improves the result
and the DFE does not statistically degrade it.

#### 16. Decisions and slicer

Shows NRZ/PAM4 histograms and thresholds, symbol decisions, LLRs, confusion
matrix, BER/SER, GMI, and link state.

This is the boundary between analog/digital DSP and FEC. It distinguishes an
ugly reference-plane eye that remains recoverable from a truly unlocked
link.

### Instruments and live analysis

#### 17. Scope / DCA

A coherent, multi-instance, multichannel instrument. Each card can acquire up
to four nodes from the same record:

- ideal driver;
- P and N driver legs;
- differential and common-mode voltage;
- electrical channel output;
- optical power at the modulator or PD;
- TIA/AFE and CTLE outputs.

The **EYE** view provides persistence, overlays, eye height and width, Q, RLM,
and OMA/ER at optical nodes. The **WAVE** view displays synchronized time
traces.

Additional functions include P/N/Diff/CM quick sets, persistent Plotly camera,
per-channel scale/offset/deskew, masks, and automatic DCA markers in the
Signal chain panel.

**Fixture and de-embedding.** The scope bar declares a measurement fixture
between DUT and DCA (0, 3, 6 or 10 dB at Nyquist, √f loss with a 50 ps delay)
and a regularized inverse filter <code>H*/(|H|²+ε)</code> with a 30 dB floor.
Both are evaluated by the server on the same record (EYE and WAVE) and never
touch the datapath: the "embedded" eye is what the DCA would see without
correction, the de-embedded one recovers the DUT plane up to the
regularization floor.

#### 18. Jitter and TIE

Analyzes time-interval error for the selected record through trend,
histogram, spectrum, RJ/PJ/DCD estimates, and an empirical bathtub curve.

The dual-Dirac tail fit also reports the DCA jitter-mode pair **J2 / J9**:
total jitter at BER 2.5e-3 and 2.5e-10. J2 is measured directly from the TIE
percentiles when at least 2000 crossings are available (shown next to the
extrapolated value), J9 is always extrapolated from the RJ/DJ(δδ) fit.

The seed makes stress comparisons reproducible. The measurement plane remains
consistent with the selected node and CDR state.

#### 19. Spectrum analyzer

Displays PSD and frequency-domain behavior for the selected node, with
controllable axis and span. It reveals bandwidth roll-off, dispersion notches,
CTLE peaking, PJ/SSC spurs, and front-end limits.

The spectrum comes from the current physical record; it is not a decorative
FFT detached from the simulation.

#### 20. Live BER

Accumulates bits and errors across compatible records and reports BER,
confidence limits, target status, and lock state. A physical configuration
change invalidates the accumulation. STOP freezes the total without losing
its context.

#### 21. Live FEC

KP4 RS(544,514) and KR4 RS(528,514) are algebraic encoders and decoders in
the signal path, not only what-if formulas.

The panel accumulates clean, corrected, uncorrectable, and miscorrected
codewords; pre/post-FEC BER; and interleave 1/2/4 behavior. Bypass mode clearly
separates data that was not decoded.

#### 22. Ethernet traffic · PHY · L1 · L2

Three layers on the same record, each with its own card and counters:

- **L2 · MAC** — real Ethernet frames (preamble/SFD, DA/SA, EtherType,
  sequence number, CRC-32 FCS) from one to four streams. The scheduler is
  round-robin, smooth weighted round-robin (per-stream weights) or IMIX
  (7:4:1 mix of 64/576/1024 B). Workload profiles fix sizes, burst length,
  inter-burst gap, stream mix and a completion KPI: *AI training*
  (all-reduce collectives, 576/1024 B bursts of 12), *LLM inference*
  (token streams, 64/256/576 B, 4:1 weights), *storage* (long 1024 B bursts),
  *web* (short 64/128 B bursts) and *video* (paced 1024 B bursts). The
  impairment emulator drops, duplicates, misorders (one position, within the
  stream) or corrupts (FCS) a declared percentage of frames with a fixed seed,
  so the analyzer can be checked against the schedule.
- **L1 · PCS** — Clause 49 scrambler <code>x^58 + x^39 + 1</code> on the
  whole stream, or a 64b/66b block coding: /S/, /D/, /T0…T7/ and /I/ blocks,
  scrambled payload, RX block lock over the 66 offsets (64 consecutive valid
  sync headers), sync-header error monitor with the 16-error hi_ber
  threshold and the 66/64 overhead. No alignment markers, 256b/257b
  transcoding or lane distribution (declared).
- **PHY** — line rate, pre/post-FEC BER, CDR and pattern lock.

The analyzer works on the bytes decoded from the last RX record (after FEC and
PCS): frames expected in the window, detected, FCS-good, lost (split into
emulated and PHY losses), duplicates, out-of-order, goodput, offered load,
burst completion time and tail loss for the workload, a per-stream table and a
frame inspector with the real bytes. The **audit rows** close accounting
identities across the layers on every record — frame conservation
(expected = unique OK + lost), detected = OK + bad FCS, emulated losses ⊆
losses, FCS catches every emulated corruption, WRR share ≈ weights, PCS block
lock, PCS overhead 66/64 — and go to <code>NOT_ASSESSED</code> with a
suggested record length when no complete frame fits the window.

Frame-size benchmark, ONT-style load ramp with latency budget and service
disruption from CDR lock are kept. Declared: one serial lane, no switch,
queues or congestion, no header modifiers or payload timestamps, not RFC 2544
or Y.1564.

#### 23. Module / CMIS-lite

Represents a module consistent with the selected optical architecture:
application advertisement, datapath state, laser/Tx disable, Rx power,
temperature, and principal alarms.

It is an educational control-plane model, not a complete CMIS memory-map
implementation.

#### 24. Parametric sweep

Sweeps an allowed configuration field end to end and returns BER, GMI, eye,
lock state, and explicit <code>LINK DOWN</code> points.

Jobs are versioned and cancellable. If the configuration changes, an obsolete
result cannot overwrite the current bench.

#### 25. JTOL-lite

Sweeps periodic-jitter frequency and amplitude to estimate CDR tolerance. It
exposes jitter peaking near the loop bandwidth and record-length limits at
low frequency.

This is an educational procedure, not a normative clause mask.

#### 26. Link training

Runs coordinate descent on TX taps using a metric measured by the receiver.
Every iteration, coefficient update, improvement, and stopping condition is
shown.

The result is not silently committed to the shared configuration; the user
chooses whether to apply it.

#### 27. AN/LT: Clause 73

Models base pages, priority resolution to the highest common denominator,
Table 73-7 timers, and a Clause 72/136-style training handshake.

The workflow includes presets, increment/decrement requests for
<code>c(-1)</code> and <code>c(+1)</code>, <code>updated</code>,
<code>at_limit</code>, and <code>receiver_ready</code>. Its training metric
comes from the active bench.

#### 28. Compliance · IEEE/OIF

The active profile (name, interface, standard, status) with the list of
knobs modified since it was loaded, followed by one measurement row per
contract: measure and reference plane, value measured on the current record,
registry limit with clause/table/edition, margin bar with the declared
uncertainty, and two separate chips — the **model** verdict
(<code>PASS</code>, <code>FAIL</code>, <code>MARGINAL</code>,
<code>PROXY</code>, <code>NOT_APPLICABLE</code>, <code>NOT_ASSESSED</code>,
<code>ERROR</code>) and the **compliance** claim, which is always
<code>NOT_ASSESSED</code> because LabPro runs no certified procedure with
traceable instruments.

Every limit comes from the single registry in
<code>serdes_sim/standards.py</code> (per-interface limits with a
<code>published</code> / <code>to-verify</code> confidence flag); a limit
that has not been checked against the licensed text never produces a
pass/fail. The manifest (what is clause and what is a LabPro assumption), the
17-profile catalog and the verdict legend live in collapsible sections; the
JSON/Markdown buttons download a traceable report built from the same record
(config hash, seed, profile, contracts, physics invariants, checkpoints, last
DR4 run, library versions).

Loading a profile configures the complete bench rather than changing only a
label; touching a knob keeps the profile and marks it as modified.

#### 29. DR4 physical procedure (v1.2)

An on-demand, reproducible workflow over the complete 65,535-symbol SSPRQ
period on an eight-case stress space: the two public dispersion extremes ×
three polarization splits (0, 0.5, 1 of the DGD power split), an MPI case
(two discontinuities at the 21.4 dB TX return-loss tolerance, coherent echo at
−42.8 dB with random phase) and a stress-RIN case (−136 dB/Hz at the source,
declared value; the clause RIN_21.4OMA is still to be verified against the
text).

TDECQ uses 0.45/0.55 UI windows, a normalized five-tap FFE, and
<code>Ceq</code> integrated over BT4-shaped noise; the worst finite TDECQ,
the 50/50 baseline, the polarization/reflection/RIN deltas and the numerical
grid uncertainty are reported per step. The same records close through PD,
TIA, ADC, CDR, and DSP (closure evaluated on the un-stressed grid; the stress
cases carry their own steps).

**Golden correlation.** A <code>labpro-golden/1</code> JSON (optical
waveform, transmitted symbols, instrument references for TDECQ/OMA/ER) can be
loaded from the panel; LabPro measures the same waveform and reports the
deltas with a tolerance. A dataset exported from a real DCA
(<code>source = instrument</code>) closes the correlation step with a
PASS/FAIL model verdict; the built-in synthetic example only exercises the
pipeline (<code>PROXY</code>). Traceable instrument uncertainty remains out of
scope, so compliance stays <code>NOT ASSESSED</code>.

#### 30. Instrument alignment

Maps workbench concepts and functions to real DCA, BERT, and traffic-generator
terminology, indicating what is implemented and what is not: J2/J9 and
fixture de-embedding on the DCA row, the SECQ stressed-receiver calibration
on the BERT row, scheduler/workloads/impairments/PCS on the traffic row.

External links are learning references, not endorsements or claims of
proprietary emulation.

#### 31. Checkpoints and signal ledger

Lists the automatic checks and reference planes produced by the engine,
including dimensions, units, health, causality, equalizer improvement, range
utilization, lock, FEC, and metrics.

This is the first panel to inspect when a result appears inconsistent.

#### 32. Physics audit and invariants

Runs paired checks and invariants. Examples include:

- increasing noise must not systematically improve quality;
- changing loss must propagate downstream;
- disabling TX must collapse the link;
- FEC and CDR must honor their activation conditions;
- upstream planes must not depend on downstream controls.

Results distinguish <code>PASS</code>, <code>FAIL</code>, and not assessable
conditions.
