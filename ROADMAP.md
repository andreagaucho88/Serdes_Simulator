# Public roadmap

## 0.1.x — release hardening

- [x] Installable package and <code>serdes-lab</code> CLI
- [x] Reproducible CI and package build
- [x] Public validation, contribution, security, and panel documentation
- [x] Guided DCA/BER/FEC demo
- [ ] Correlated example Touchstone datasets with provenance
- [x] Golden-instrument correlation with the IEEE P802.3bs SMF ad hoc
      waveform library (6/6 within tolerance); FlexDCA CSV import
- [x] SCPI/PyVISA remote control of the bench
- [x] PyPI trusted publishing (`pipx install serdes-optical-lab`)
- [ ] Automated accessibility and browser-performance checks

## 0.2 — comparison and reporting

- Side-by-side A/B configurations with a shared seed
- Exportable HTML/PDF experiment report (JSON/Markdown compliance report shipped)
- Shareable configuration files with schema migration
- Saved experiment recipes and batch execution

## 0.3 — validation depth

- Additional public golden vectors
- Correlation reports against external reference implementations
- Expanded measured-channel and IBIS-AMI examples
- More complete normative procedure coverage where public data permits

## Hosted demo prerequisites

A public hosted service is intentionally deferred until authentication,
per-user state isolation, parser/upload limits, resource quotas, and audit
logging are implemented. See [SECURITY.md](SECURITY.md).
