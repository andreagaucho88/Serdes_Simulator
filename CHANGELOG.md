# Changelog

All notable public changes are documented here.

## Unreleased

- Standards registry (`serdes_sim/standards.py`): per-interface limits with
  clause, table, edition and a published/to-verify confidence flag; a closed
  verdict taxonomy (PASS, FAIL, MARGINAL, PROXY, NOT_APPLICABLE, NOT_ASSESSED,
  ERROR) shared by COM, DR4, TDECQ, checkpoints, physics and CMIS; per-profile
  measurement contracts.
- New Compliance panel replacing the IEEE/OIF standards panel: active profile
  with modified knobs, one measurement row per contract (value, registry limit,
  margin bar with uncertainty, model verdict and separate compliance chip),
  collapsible manifest/catalog/legend, JSON and Markdown report export
  (`/api/report/standards`).
- COM: Equation 93A-46 Gaussian rise-time factor restored, σ_TX referred to one
  level step, 802.3ck low-frequency CTLE stage, two-stage equalizer search,
  profile-aware applicability (100GAUI-1 C2M is not COM-based).
- Clause-formula RLM, linear-fit SNDR (Np=200 UI), TDECQ σ_S term and TECQ,
  run-based optical levels, NRZ eye mask and JTOL mask served as data.
- Corrected help/Academy errors (lane rates, KP4 threshold, PRBS13Q clause,
  nonexistent profile), CEI-224G marked as draft.
- UI: verdict chips everywhere, pinned instrument dock, tab-strip overflow
  arrows and short names, background-tab startup fix, folded long notes,
  toast queue with severity, i18n sweep, accessible BERT tabs and sliders.
- Server: typed/ranged schema for every configuration field, 400 responses
  for bad parameters and NaN, Touchstone text kept out of broadcasts, profile
  tracker persisted with the session.

## 0.1.3 — 2026-09-02

- Moved Lab PRO session persistence out of the Python package into a private,
  platform-specific user state directory, with atomic writes, legacy-session
  migration, an environment/CLI override, and an opt-out mode.
- Added a path-safe <code>/api/health</code> readiness endpoint and changed the
  macOS launcher to wait for real server readiness instead of sleeping for a
  fixed interval, with signal-safe cleanup that cannot orphan the server.
- Rejected malformed and non-object JSON bodies before they can mutate bench
  state, and surfaced persistence failures in both health diagnostics and the
  running UI.
- Expanded the regression gate to 392 automated tests.

## 0.1.2 — 2026-09-02

- Closed the first CodeQL findings by HTML-safely encoding JSON responses,
  returning generic public errors while retaining server-side diagnostics,
  and restricting executable AMI discovery to a trusted local model folder.
- Limited push CI to `main` so tags and Dependabot pull requests do not run
  duplicate test jobs.

## 0.1.1 — 2026-09-02

- GitHub Actions uses an isolated package build and Node 24-based actions.
- Added complete Plotly.js, IBM Plex, and Space Grotesk redistribution notices
  to both source and installable artifacts.
- Clarified that public IEEE reference data is not relicensed by the project.
- Rejected non-loopback Host headers, cross-origin REST mutations, request
  bodies above 16 MiB, and Touchstone text above 8 MiB.
- Added Dependabot, CodeQL, and Ruff CI gates.
- Resolved all 45 existing Ruff findings without changing numerical baselines.
- Corrected the clean-environment build command in the contribution guide.
- Normalized public Git authorship to a GitHub `noreply` address.

## 0.1.0 — 2026-09-02

First public alpha release.

### Product

- 32-panel Lab PRO workbench with grouped, persistent, lazy tabs.
- Complete electrical/optical SerDes path through TX, channel, optics, RX,
  ADC, CDR, FSE/DFE, slicer, and in-path KP4/KR4 FEC.
- Coherent multichannel DCA, BERT, jitter/TIE, spectrum, live BER/FEC,
  Ethernet traffic, CMIS-lite, sweep, JTOL, training, AN/LT, and DR4 views.
- 123 bilingual physical controls with contextual help.
- Seven real-UI animated tours and a product-oriented README.

### Engineering

- Touchstone 1.x/2.x S2P and mixed-mode S4P support.
- Versioned configuration, cancellable experiment workers, WebSocket live
  acquisition, and clean shutdown.
- Installable Python package with the <code>serdes-lab</code> command.
- 378-test regression suite plus 13-checkpoint physical self-test.
- MIT license and public contribution/security documentation.

### Boundaries

This release is an educational system-level model. It does not claim
standards compliance or replace a traceable instrument.
