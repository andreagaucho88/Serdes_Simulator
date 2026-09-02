# SerDes Optical Lab PRO

An interactive bilingual laboratory for studying, measuring, and stressing an
electrical or electro-optical SerDes chain up to the 224G class.

~~~text
bits / frames → PRBS or Ethernet → TX FEC → NRZ/PAM4 mapper → TX FIR
→ DAC → P/N driver → S-parameter channel → modulator / fiber
→ PD → TIA / AFE → AGC → CTLE → ADC → CDR → FSE → DFE
→ slicer → RX FEC → BER, GMI, L2 traffic, and checkpoints
~~~

The maintained interface is **Lab PRO** in <code>labpro/</code>: a custom
Tornado and WebSocket workbench with 32 instrument panels. The numerical
engine in <code>serdes_sim/</code> is independent from the GUI. The former
Streamlit interface in <code>app/</code> is preserved as a reference but is
frozen.

> **Scope and validity.** This is a system-level educational framework for
> learning, debugging, and sensitivity analysis. IEEE/OIF procedures and
> profiles explicitly identify their assumptions and unsupported portions.
> A <code>MODEL PASS/FAIL</code> result is never presented as certified
> compliance.

## Instrument hero: DCA eye, live BER, and live FEC

![DCA eye diagram, live BER, and live FEC tour](docs/media/00-instruments-hero.gif)

This short tour puts the most instrument-like views first: a persistent DCA
eye, accumulated BER with confidence information, and real in-path FEC
codeword counters.

## Visual tour

Every GIF below is a reproducible recording of the real application. Each tab
change requests live bench data; none of the screens use mocked plots or
precomputed screenshots.

### 1. Workspace, signal chain, Academy, and standards

![Workspace, signal chain, and guides tour](docs/media/01-workspace-overview.gif)

The signal chain is navigable: clicking a block opens its instrument panel.
Failed checkpoints highlight the responsible block, while amber triangles
show the reference planes currently acquired by DCA scopes.

### 2. Source, BERT, and transmitter

![BERT, generator, and transmitter tour](docs/media/02-source-and-tx.gif)

The BERT combines four views: PPG source, TX stress, error checker, and RX
procedures. Its state is shared with the FIR, DAC, P/N driver, TX PLL, and
error-insertion path.

### 3. Channel, COM, and optics

![Channel, COM, and optics tour](docs/media/03-channel-and-optics.gif)

The channel can be analytical or imported from a Touchstone file. COM,
modulator, fiber, and CMIS-lite expose their own physical planes,
measurements, and declared limitations.

### 4. Receiver and DSP

![Receiver, ADC, CDR, and equalization tour](docs/media/04-rx-and-dsp.gif)

PD, TIA, AGC, CTLE, interleaved ADC, CDR, FSE/DFE, and slicer operate on the
same end-to-end record. They are not disconnected demonstrations.

### 5. Live instruments

![DCA, jitter, spectrum, BER, and FEC tour](docs/media/05-live-instruments.gif)

DCA EYE/WAVE, TIE, spectrum, BER, and FEC update while acquisition is
running. Counters grow record by record and reset whenever the underlying
physics changes.

### 6. Procedures, training, and audit

![L2, JTOL, AN/LT, training, and audit tour](docs/media/06-procedures-and-audit.gif)

Sweep, JTOL-lite, link training, AN/LT, DR4, instrument alignment, the signal
ledger, and the physics audit make both the result and the path that produced
it inspectable.

## Quick start

### Requirements

- Python 3.10 or newer;
- NumPy, SciPy, pandas, Tornado, Plotly, and pytest;
- scikit-rf for Touchstone 2.x;
- a modern web browser;
- optional: Playwright and ImageMagick to regenerate the GIFs.

In the project development environment:

~~~bash
cd simulatore
python -m labpro.server --port 8640
~~~

Then open [http://localhost:8640](http://localhost:8640). On macOS you can
also double-click <code>avvia_labpro.command</code>.

To use a generic Python environment:

~~~bash
python -m pip install numpy scipy pandas tornado plotly scikit-rf pytest
python -m labpro.server --port 8640
~~~

The server binds to localhost. Stop it with <code>Ctrl+C</code>; shutdown
stops the LiveBench cleanly without leaving a traceback.

## Using the workbench

### Top bar

- **Preset** loads one of seven educational scenarios or one of 17 IEEE/OIF
  contexts.
- **RUN / STOP** starts or pauses server-side acquisition.
- **Record** shows the number of accumulated acquisitions.
- **Seed** makes noise, pattern generation, and stress reproducible.
- **IT / EN** switches panels, tooltips, Academy content, and messages.
- **Views** loads a themed workspace: Full bench, Essential, Source and TX,
  Channel and optics, RX and DSP, Live analysis, BERT and traffic, P/N scope,
  or Academy.
- **Reset** restores the selected preset and invalidates dependent
  accumulations.

### Grouped tab workspace

The left palette follows signal flow. Clicking an entry opens it as a tab. A
singleton panel that is already open is activated instead of duplicated.
Scope is intentionally multi-instance so that up to four coherent reference
planes can be compared.

- Drag a tab to reorder it or move it to another group.
- Drag a group to change the section order.
- Use the card buttons to open Academy help, reset local state, or close it.
- Use the left and right arrow keys to move through the active tab group.
- Workspace order, collapsed groups, active tab, language, and plot camera
  survive reloads.
- Hidden panels are lazy: only the active instrument polls and renders.

### Shared control contract

Every slider or selector updates the shared <code>LinkConfig</code>. The
server increments the configuration version, cancels any obsolete worker,
clears counters that can no longer be compared, and broadcasts the new state
over WebSocket. The small hash in the status bar verifies that two panels are
observing the same configuration.

The **?** button next to a control explains:

1. the affected physical plane;
2. the expected effect;
3. the readout to observe;
4. a suggested paired experiment;
5. activation conditions;
6. the model boundary;
7. the API field actually changed.

The **?** button in a card title opens the corresponding Academy page.

## Complete reference for all 32 panels

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

## Educational presets

| Preset | Recommended use |
| --- | --- |
| 112G educational, 2 km at 1550 nm | Course baseline: 56 GBd PAM4 in C-band |
| Back-to-back | Reference without fiber penalty |
| 10 km stress: CD fading | IM/DD notch and equalization limit |
| 100GBASE-LR1 context | O-band, 53.125 GBd, 10 km |
| Severe electrical channel | CTLE/FSE/DFE against 20 dB at Nyquist |
| Noisy receiver | TIA sensitivity and noise budget |
| Link with margin: FEC at work | Observe corrected KP4 codewords |

The 17 standard profiles add 10G, 25G, 50G, 100G, 400G, and 800G Ethernet;
CEI-56G/112G/224G; and P802.3dj contexts. They are not certification presets.

## Persistence and coherence

- <code>LinkConfig</code> is an immutable dataclass with 123 serializable
  fields.
- The server saves configuration, preset, chamber state, and RUN state in the
  laboratory session file.
- The browser saves layout, language, active tab, and plot camera locally.
- Every response carries configuration version/hash and record identity.
- Long-running workers are tied to the version that started them.
- WebSocket disconnects and rapid reloads are consumed without orphaned
  asynchronous futures.
- Config import/export uses a versioned JSON contract.

Use Reset in the UI for a clean session. Before manually removing a session
file, stop the server and keep a copy if its configuration matters.

## Local API

The UI uses the same API that is available for local inspection and
automation:

| Endpoint | Method | Purpose |
| --- | --- | --- |
| <code>/api/state</code> | GET | Configuration, presets, language metadata, RUN state |
| <code>/api/config</code> | POST | Atomic patch of LinkConfig fields |
| <code>/api/config/export</code> | GET | Versioned configuration export |
| <code>/api/config/import</code> | POST | Versioned configuration restore |
| <code>/api/preset</code> | POST | Load an educational or standard profile |
| <code>/api/run</code> | POST | Start or stop acquisition |
| <code>/api/reset</code> | POST | Reset bench state |
| <code>/api/s2p</code> | POST | Validate and apply Touchstone text |
| <code>/api/panel/&lt;name&gt;</code> | GET | Build a panel payload |
| <code>/api/experiment/&lt;name&gt;</code> | POST | Sweep, training, JTOL, traffic, and procedures |
| <code>/ws</code> | WebSocket | State, invalidation, record, and progress updates |

Example:

~~~bash
curl -s http://localhost:8640/api/state
curl -s -X POST http://localhost:8640/api/config \
  -H 'Content-Type: application/json' \
  -d '{"channel_il_nyquist_db": 16.0, "fec_mode": "kp4"}'
~~~

The API is local, unauthenticated, single-user, and does not promise the
stability of a public product API.

## Using the Python engine directly

~~~python
from dataclasses import replace

from serdes_sim import LinkConfig, simulate, sweep

cfg = replace(
    LinkConfig(),
    link_medium="copper",
    channel_il_nyquist_db=16.0,
    fec_mode="kp4",
)

result = simulate(cfg, seed=7, depth="full")
print(result.metrics)
print(result.checkpoints)

curve = sweep(
    cfg,
    field="channel_il_nyquist_db",
    values=[8.0, 12.0, 16.0, 20.0],
    seed=7,
)
~~~

The result contains physical-plane records, metrics, metadata, the signal
ledger, and checkpoints. Source types and repository tests define the exact
contract.

## Repository layout

~~~text
simulatore/
├── labpro/                  Tornado server and Lab PRO frontend
│   ├── server.py
│   └── static/              HTML, CSS, JavaScript, local Plotly bundle
├── serdes_sim/              GUI-independent physical engine
│   ├── blocks/              TX, channel, optics, RX, ADC, DSP, FEC, metrics
│   ├── engine.py            simulate() and sweep()
│   ├── procedures.py        DR4 and versioned procedures
│   ├── config.py            LinkConfig, presets, standard profiles
│   ├── ami.py               IBIS-AMI loader and demo model
│   └── selftest.py          end-to-end smoke test
├── tests/                   numerical, API, UI-contract regression suite
├── tools/
│   └── capture_readme_gifs.py
├── docs/media/              seven real-UI animated tours
├── app/                     frozen legacy Streamlit interface
├── HANDOFF_CODEX.md         iteration-by-iteration engineering log
└── PROMPT_CODEX.md          maintenance state and invariants
~~~

## Verification and quality gates

Run from the <code>simulatore</code> directory:

~~~bash
python -m pytest tests -q
python -m serdes_sim.selftest
node --check labpro/static/app.js
python -m compileall -q serdes_sim labpro
git diff --check
~~~

Validated state after iteration 38: **376/376 tests pass**, physical self-test
**13/13**, JavaScript syntax, Python compilation, and whitespace checks clean.

The additional browser audit traverses all 32 panels in both IT and EN,
verifies singleton and active-tab behavior, all four BERT views, DCA EYE/WAVE,
control propagation, a real Touchstone 2.x upload, and rapid reloads. Numerical
tests also preserve the frozen notebook-v7 baseline.

## Regenerating the GIFs

With the server listening on port 8640:

~~~bash
python tools/capture_readme_gifs.py --base http://127.0.0.1:8640
~~~

The script:

1. launches Playwright using an available Chromium browser;
2. saves the current configuration and RUN state in an isolated browser
   profile;
3. switches the UI to English;
4. visits real tabs and captures 1440 by 900 frames;
5. builds seven optimized 1000 by 625 GIFs with ImageMagick;
6. restores the initial bench state even if capture fails.

Options:

~~~bash
python tools/capture_readme_gifs.py --help
~~~

Do not edit generated GIFs without updating the script. The tour must remain
reproducible and faithful to the current interface.

## Troubleshooting

### The page does not open

Check that the process is running and the port is available:

~~~bash
curl -s http://localhost:8640/api/state
~~~

If port 8640 is occupied, start the server on another port and use the
matching browser URL.

### A panel shows stale data

Check the configuration version/hash in the status bar, allow the current
record to complete, and reload. A parameter change intentionally invalidates
accumulation. If needed, use STOP, Reset, then RUN.

### The link is DOWN

Open Signal chain, Checkpoints and signal ledger, Timing/CDR, and Decisions in
that order. Verify TX output, ADC range utilization, clipping, pattern lock,
and CDR lock.

Missing BER, GMI, or post-FEC metrics while the link is down are correct
behavior.

### A Touchstone file is rejected

Check the extension and port count, strictly increasing frequencies, RI/MA/DB
format, uniform reference impedance, and S4P port-pair mapping. Touchstone 2.x
uses scikit-rf, which must be installed in the same interpreter as the
server.

### GIF regeneration fails

Install Playwright and ImageMagick, and make a Playwright Chromium browser
available in its standard cache. The script emits an explicit error if
<code>magick</code> is unavailable.

## Known limitations

- This is not a compliance instrument and does not replace a golden
  instrument.
- The model is system-level rather than transistor- or layout-level.
- COM and JTOL are educational proxies with declared boundaries.
- CMIS and traffic tests are functional subsets.
- DR4 does not include traceable uncertainty, reflection, or the complete
  polarization-stress space.
- IBIS-AMI behavior depends on each vendor library and contract.
- The Streamlit UI is legacy and receives no new features.

Roadmap, engineering decisions, and validation history are recorded in
[HANDOFF_CODEX.md](HANDOFF_CODEX.md).

## License and intended use

Use this project according to the repository license and policies. For design,
procurement, or compliance decisions, always correlate the model with the
applicable specification, component data, and traceable measurements.
