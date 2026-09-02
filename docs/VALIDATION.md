# Validation report

This document states what is tested, what is only modeled, and what is not a
compliance claim.

## Current quality gate

- **378 automated tests**
- **13/13 physical self-test checkpoints**
- all 32 Lab PRO panels exercised in Italian and English
- browser checks for singleton tabs, BERT subviews, DCA EYE/WAVE, control
  propagation, Touchstone 2.x upload, and rapid WebSocket reloads
- JavaScript syntax, Python compilation, package build, and link checks

Run the reproducible gate with:

~~~bash
python -m pytest tests -q
python -m serdes_sim.selftest
node --check labpro/static/app.js
python -m build
git diff --check
~~~

## Frozen numerical baseline

The regression suite protects the notebook-v7 reference behavior, including
the oracle baseline and acquisition batches frozen for known seeds. Changes
to NumPy, SciPy, filters, timing, noise, or random-number ordering may move
those values and must be reviewed deliberately.

Dependencies are pinned for this reason.

## Structural guarantees

Tests verify that:

- every <code>LinkConfig</code> field has a bilingual help contract;
- every operational UI action has an effect, observable, endpoint, and model
  boundary;
- controls propagate from the correct physical plane downstream;
- upstream records do not depend on downstream controls;
- hidden tabs remain lazy and cannot display a stale configuration;
- experiment workers are versioned, cancellable, and unable to overwrite a
  newer configuration;
- CDR lock and BERT pattern lock gate downstream metrics;
- KP4/KR4 FEC uses real algebraic encoders/decoders in the path;
- public text assets do not embed a developer home path.

## Standards and procedures

The repository contains educational contexts for IEEE 802.3 and OIF links.
Profiles configure symbol rate, medium, reach, modulation, FEC, and
representative channel conditions.

The following remain explicitly non-normative:

- COM is an Annex 93A-oriented educational subset;
- JTOL-lite does not reproduce a complete clause mask and dwell procedure;
- traffic procedures do not claim RFC 2544;
- CMIS-lite is not a complete memory-map implementation;
- DR4 lacks the complete reflection/polarization stress space, traceable
  uncertainty, and golden-instrument correlation.

Therefore model verdicts remain <code>MODEL PASS/FAIL</code>, while standards
compliance remains <code>NOT ASSESSED</code>.

## Adding validation evidence

A new physical model or control should include:

1. a unit or golden-vector test;
2. a paired sensitivity test showing that the control changes the expected
   plane;
3. an invariant proving that unrelated upstream planes do not change;
4. a bilingual help contract and declared activation condition;
5. a documented limitation if the implementation is a proxy.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the complete change workflow.
