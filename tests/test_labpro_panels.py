"""Ogni builder di pannello deve produrre JSON serializzabile.

Prima di questo file 15 builder su 24 non venivano mai istanziati da un test:
un KeyError in un pannello si scopriva solo aprendolo nel browser. Qui ogni
builder gira su una sim di riferimento reale (stessa strada di ApiPanel) e il
risultato deve sopravvivere a paneldata.J + json.dumps.
"""

import inspect
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from serdes_sim import LinkConfig                 # noqa: E402
from labpro import paneldata                      # noqa: E402

pytestmark = pytest.mark.slow                     # una sim full-depth condivisa

CFG = LinkConfig()


@pytest.fixture(scope="module")
def ref():
    return paneldata.ref_sim(CFG)


def _kwargs_for(builder):
    params = inspect.signature(builder).parameters
    kw = {}
    if "node" in params:
        kw["node"] = "vctle"
    if "n_traces" in params:
        kw["n_traces"] = 40
    if "nperseg" in params:
        kw["nperseg"] = 1024
    return kw


@pytest.mark.parametrize("name", sorted(paneldata.PANEL_BUILDERS))
def test_panel_builder_produces_json(name, ref):
    builder = paneldata.PANEL_BUILDERS[name]
    payload = builder(ref, CFG, **_kwargs_for(builder))
    assert isinstance(payload, dict), f"{name}: il pannello deve produrre un dict"
    encoded = json.dumps(paneldata.J(payload))
    assert encoded  # nessun NaN/ndarray sopravvissuto alla conversione


@pytest.mark.parametrize("name", ["education", "com"])
def test_config_only_panels_accept_no_sim(name):
    # il server passa sim=None per i pannelli che non richiedono datapath
    builder = paneldata.PANEL_BUILDERS[name]
    payload = builder(None, CFG, **_kwargs_for(builder))
    json.dumps(paneldata.J(payload))


@pytest.mark.parametrize("node", sorted(paneldata.NODES))
def test_eye_panel_every_node(node, ref):
    payload = paneldata.eye_panel(ref, CFG, node=node, n_traces=24)
    json.dumps(paneldata.J(payload))
    assert payload["traces"], f"nodo {node}: nessuna traccia"
