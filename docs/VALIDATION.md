# Validation report

This document separates verified software behavior, model evidence, and
standards compliance. Lab PRO is an educational system-level simulator; none
of the checks below turns it into a calibrated or traceable instrument.

## Current quality gate

- **502 automated tests** collected from the public repository;
- **13/13 physical self-test checkpoints**;
- all 32 Lab PRO panels exercised in Italian and English;
- browser checks for singleton tabs, BERT subviews, DCA EYE/WAVE, control
  propagation, Touchstone 2.x upload, and rapid WebSocket reloads;
- package build plus install/CLI/asset smoke tests on Linux, macOS, and
  Windows in GitHub Actions;
- Ruff, JavaScript syntax, Python compilation, CodeQL, and whitespace gates.

Run the reproducible local gate with:

~~~bash
python -m pytest tests -q
python -m serdes_sim.selftest
python -m ruff check .
node --check labpro/static/app.js
python -m compileall -q serdes_sim labpro
python -m build
git diff --check
~~~

`python -m build` is the clean-environment command. After installing the
`dev` extra, `python -m build --no-isolation` is supported as well because
setuptools and wheel are then present in the active interpreter.

## Frozen numerical baseline

The regression suite protects the notebook-v7 reference behavior, including
the oracle baseline and acquisition batches frozen for known seeds. Changes
to NumPy, SciPy, filters, timing, noise, or random-number ordering may move
those values and must be reviewed deliberately. Runtime dependencies are
pinned for this reason.

## Structural and runtime guarantees

Tests verify that:

- every one of the 136 `LinkConfig` fields has a bilingual help contract;
- every operational UI action has an effect, observable, endpoint, and model
  boundary;
- controls propagate from their physical plane downstream while unrelated
  upstream records remain unchanged;
- hidden tabs stay lazy and cannot display an obsolete configuration;
- one global experiment registry serializes HTTP and SCPI procedures, exposes
  progress, and supports cooperative cancellation;
- `ACQuire:SINGle` produces a fresh record and restores the previous RUN/STOP
  state;
- CDR lock and BERT pattern lock gate downstream metrics;
- KP4/KR4 FEC uses algebraic encoders and decoders in the datapath;
- configuration/profile/chamber imports validate completely before any state
  is committed;
- malformed, non-object, non-finite, oversized, or cross-origin payloads are
  rejected before reaching the simulation engine;
- session files are size-bounded, atomically written outside the package, and
  do not persist an implicit RUN state;
- health diagnostics report persistence and SCPI readiness without exposing
  a filesystem path;
- JSON responses escape HTML delimiters, generic public errors do not expose
  internal paths, and AMI discovery cannot escape its trusted root;
- bundled Plotly, fonts, fixtures, and golden data keep their third-party
  notices and are included in source and wheel artifacts.

## Instrument correlation

The package includes six decimated 53.125 GBd PAM4 optical waveforms from the
IEEE P802.3bs SMF ad hoc contribution, with original-source URLs, SHA-256
identities, capture metadata, and FlexDCA reference values. Tests verify:

- stored waveform and symbol arrays load with pickle disabled;
- software pattern lock recovers the documented PRBS11-derived PAM4 pattern;
- every dataset element, reference number, tolerance, bandwidth, and
  equalizer mode is finite and in its declared domain;
- Lab PRO TDECQ at the instrument receiver bandwidth falls inside, or within
  0.2 dB of, the reported FlexDCA 5-tap range for all six captures;
- the clause-bandwidth result is reported separately when it differs from the
  historical instrument configuration.

This is a model correlation against 2017 draft-era measurements, with a
declared 0.5 dB tolerance. It is not a calibration certificate and does not
establish traceable measurement uncertainty.

## Standards and procedure boundaries

The standards registry records interface, edition, clause/table, limit,
comparison direction, and whether the public value is published or still
requires verification. Model verdicts use a closed taxonomy: `PASS`, `FAIL`,
`MARGINAL`, `PROXY`, `NOT_APPLICABLE`, `NOT_ASSESSED`, and `ERROR`.
Compliance remains a separate result and defaults to `NOT_ASSESSED`.

Implemented procedure evidence includes:

- DR4 v1.2: dispersion × polarization cases, a coherent reflection pair,
  source-RIN stress, SSPRQ, golden correlation, and explicit finite/non-finite
  case reporting;
- stressed receiver v2: SJ plus RIN calibration to the SECQ target followed
  by an RX BER confidence verdict;
- RFC 2544-shaped throughput, latency/jitter, frame-loss, and back-to-back
  reports;
- ITU-T Y.1564-shaped service configuration/performance reports with IR, FTD,
  FDV, FLR, and availability;
- MP1900A-shaped PAM4 MSB/LSB errors and symbol-error matrix;
- COM and JTOL educational subsets with their assumptions attached to the
  output.

The remaining limits are intentional and visible in the reports: one serial
lane, no external packet DUT, switch queues, policer, payload timestamps,
traceable uncertainty, or full vendor command grammar. CMIS is a functional
subset. RFC 2544/Y.1564 structure does not imply conformance certification.

## Adding validation evidence

A new physical model or control should include:

1. a unit or golden-vector test;
2. a paired sensitivity test showing that the control changes the expected
   plane;
3. an invariant proving that unrelated upstream planes do not change;
4. a bilingual help contract and declared activation condition;
5. a documented limitation whenever the implementation is a proxy.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the complete change workflow.
