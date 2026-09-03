# Changelog

All notable public changes are documented here.

## Unreleased

- Rebuilt all seven README animations as annotated 16:9 product stories with
  branded chapter cards, large live-view titles, concise observation prompts,
  progress markers, and scene-specific timing. The hero now explicitly follows
  the real DCA eye/mask → waveform → cumulative BER → in-path FEC evidence
  chain; every generated application frame still comes from the live bench.
- Made the GIF generator declarative and reproducible: tours now carry their
  own narrative metadata, DCA EYE/MASK and WAVE modes are exercised
  automatically, repeated panels are deduplicated, live FEC is allowed to
  settle, and the original configuration and RUN state remain protected.

## 0.2.0 — 2026-09-02

- Completed a release-hardening review across HTTP, persistence, SCPI,
  golden-data validation, packaging, CI, and public documentation. Session and
  config imports now validate configuration/profile/chamber atomically;
  chamber types, modes, ranges, ordering, and unknown fields return structured
  400 errors without partial mutation.
- Aligned request limits with the 16 MiB server envelope (8 MiB Touchstone,
  15 MiB FlexDCA CSV), validate sizes in UTF-8 bytes, bound restored session
  files, reject non-finite golden arrays and references across the complete
  payload, and load bundled NPZ data with pickle disabled.
- Fixed the documented flat `/api/config` patch contract while preserving the
  legacy `{ "updates": ... }` form. SCPI `ACQuire:SINGle` now acquires a fresh
  record, HTTP and SCPI share the experiment lock/cancel token, and health
  reports actual SCPI readiness.
- Expanded the public gate to 502 tests, added Linux/macOS/Windows package
  smoke jobs, and made tagged releases fail before publishing when the Git tag
  and package version disagree.

- Golden-instrument correlation with real data: the six 53.125 GBd PAM4
  optical waveforms of the IEEE P802.3bs SMF ad hoc contribution (Cisco TX,
  Tektronix DSA8300/80C10, FlexDCA export) ship as a decimated library with
  provenance and SHA-256; software pattern lock identifies the generator
  pattern (PRBS11 MSB + delayed inverted copy on LSB, Gray), and LabPro TDECQ
  lands inside or within 0.2 dB of the FlexDCA 5-tap range on all six
  captures at the instrument's receiver bandwidth. FlexDCA CSV import
  (`WaveformXYValues` / `WaveformPattern`) and `/api/golden/library`.
- TDECQ reference equalizer optimized for minimum TDECQ (121.8.5.3) as an
  option next to the MMSE grid; instrument receiver-bandwidth override.
- Instrument-style reports: RFC 2544 with the Valkyrie2544 sections and
  columns (throughput binary search, latency/jitter, frame loss,
  back-to-back; Markdown/XML), ITU-T Y.1564 with the SAMComplete flow and
  MEF KPIs (Markdown/CSV), and the MP1900A "Result PAM4" box (MSB/LSB ER/EC
  with INS/OMI, 12-case symbol-error matrix; CSV).
- SCPI server on TCP 5025 (PyVISA `TCPIP::127.0.0.1::5025::SOCKET`) with a
  FlexDCA/MP1900A-flavoured command tree, IEEE 488.2 common commands and an
  error queue (`docs/SCPI.md`).
- Scope fixture from measured S-parameters (2- or 4-port Touchstone, mixed
  mode) with the IEEE P802.3ck module compliance board bundled.
- Stressed receiver: sinusoidal interference at the TX driver
  (`tx_si_amp_pct`, `tx_si_freq_mhz`) in the SECQ recipe.
- Panel catalog laid out per group; PyPI trusted publishing in the release
  workflow.

- Traffic panel rebuilt as PHY · L1 · L2 on the same record: real MAC frames
  with round-robin / weighted round-robin / IMIX scheduler, workload profiles
  (AI training, LLM inference, storage, web, video) with bursts and completion
  KPIs, drop/duplicate/misorder/corrupt impairment emulator with per-stream
  counters, Clause 49 64b/66b PCS with block lock and sync-header monitor,
  and audit rows that close accounting identities across the layers.
- DCA jitter mode J2/J9 (measured and dual-Dirac extrapolated), declared
  measurement fixture with regularized de-embedding on the scope (EYE/WAVE).
- Optics: coherent multipath reflection pair (return loss per discontinuity)
  and RIN at the source (clause RIN_xOMA definition) as an explicit,
  baseline-preserving alternative to the receiver noise-current model.
- DR4 procedure v1.2.0: eight-case stress space (dispersion × polarization
  split, MPI at the TX return-loss tolerance, stress RIN), worst finite TDECQ
  with the list of non-finite cases, golden-instrument correlation from a
  `labpro-golden/1` dataset (`/api/golden`).
- Stressed receiver v2 (`/api/experiment/stressed-rx`): SJ + RIN bisection to
  the registry SECQ target, RX BER on a long record with a Clopper-Pearson
  verdict.
- Engine: pattern-sync window now leaves room for every lag (fixes short
  records around 4k symbols).
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
