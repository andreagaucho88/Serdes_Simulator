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
  interval, pattern lock, synchronization, JTF, and sensitivity workflows.

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

#### 18. Jitter and TIE

Analyzes time-interval error for the selected record through trend,
histogram, spectrum, RJ/PJ/DCD estimates, and an empirical bathtub curve.

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

#### 22. Ethernet L2 traffic

Generates real Ethernet frames with the Clause 49 PCS scrambler
<code>x^58 + x^39 + 1</code>, selectable frame size and IPG, and one to four
streams.

It includes frame-size benchmarks and an ONT-style test with load ramp,
per-block latency budget, and service disruption derived from CDR lock. The
feature is deliberately labeled **L2-lite** and does not claim RFC 2544.

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

#### 28. IEEE/OIF standards

A catalog of 17 profiles specifying standard or clause, reference
plane/reach, medium, modulation, and FEC. Every profile states:

- what is published;
- which numbers are representative;
- which claim is supported;
- what remains unsupported or <code>NOT ASSESSED</code>.

Loading a profile configures the complete bench rather than changing only a
label.

#### 29. DR4 physical procedure

An on-demand, reproducible workflow over the complete 65,535-symbol SSPRQ
period, at both public dispersion extremes and with stressed DGD.

TDECQ uses 0.45/0.55 UI windows, a normalized five-tap FFE, and
<code>Ceq</code> integrated over BT4-shaped noise. The same records close
through PD, TIA, ADC, CDR, and DSP.

Reflection, full polarization stress, traceable measurement uncertainty, and
golden-instrument correlation remain out of scope; compliance therefore
remains <code>NOT ASSESSED</code>.

#### 30. Instrument alignment

Maps workbench concepts and functions to real DCA, BERT, and traffic-generator
terminology, indicating what is implemented and what is not.

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
