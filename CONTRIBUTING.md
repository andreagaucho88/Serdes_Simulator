# Contributing

Thanks for helping improve SerDes Optical Lab PRO. The project values
physical traceability, reproducible results, and honest claim boundaries over
feature count.

## Development setup

~~~bash
git clone https://github.com/andreagaucho88/Serdes_Simulator.git
cd Serdes_Simulator
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,legacy]"
~~~

Run the fast loop:

~~~bash
python -m pytest -m "not slow" -q
python -m ruff check .
node --check labpro/static/app.js
~~~

Before opening a pull request:

~~~bash
python -m pytest tests -q
python -m serdes_sim.selftest
python -m build
git diff --check
~~~

## Change rules

- Physical models belong in <code>serdes_sim/</code>, not in the UI.
- Panel-data builders transform results; they must not invent physics.
- Every new <code>LinkConfig</code> field needs bilingual control help and a
  paired efficacy test.
- Every new action needs a documented endpoint, state mutation, observable,
  and model boundary.
- Do not change frozen numerical baselines merely to silence a failure.
- Do not claim IEEE/OIF compliance without the complete procedure and
  correlated evidence.
- Keep the active Lab PRO interface bilingual.
- Never commit local paths, sessions, credentials, or private agent notes.

## Pull requests

Keep each pull request focused. Describe:

1. the physical or product problem;
2. reference planes affected;
3. expected before/after behavior;
4. validation performed;
5. model limitations or unsupported conditions.

Screenshots or GIFs are welcome for UI changes, but numerical evidence and
tests remain the source of truth.

## Reporting issues

Use the repository issue templates for reproducible bugs and feature
proposals. Report security-sensitive findings privately as described in
[SECURITY.md](SECURITY.md).
