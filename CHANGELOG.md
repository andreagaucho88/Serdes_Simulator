# Changelog

All notable public changes are documented here.

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
