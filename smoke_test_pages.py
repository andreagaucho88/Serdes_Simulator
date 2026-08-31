"""Smoke test: esegue ogni pagina della GUI in bare mode e riporta le eccezioni.

Uso: python smoke_test_pages.py
"""

import logging
import sys
import traceback

logging.getLogger("streamlit").setLevel(logging.ERROR)

from app.ui.overview import page_overview
from app.ui.chain import page_chain
from app.ui.stages_tx import page_stimulus, page_tx, page_channel
from app.ui.stages_optics import page_mzm, page_fiber
from app.ui.stages_rx import page_receiver, page_adc
from app.ui.stages_dsp import page_timing, page_eq, page_ber
from app.ui.experiments import page_experiments
from app.ui.realism import page_realism
from app.ui.notes import page_notes
from app.ui.fec_page import page_fec
from app.ui.eyes import page_eyes
from app.ui.measures import page_measures
from app.ui.scope import page_scope
from app.ui.spectrum import page_spectrum
from app.ui.standards import page_standards

PAGES = [
    ("overview", page_overview),
    ("chain", page_chain),
    ("stimulus", page_stimulus),
    ("tx", page_tx),
    ("channel", page_channel),
    ("mzm", page_mzm),
    ("fiber", page_fiber),
    ("receiver", page_receiver),
    ("adc", page_adc),
    ("timing", page_timing),
    ("eq", page_eq),
    ("ber", page_ber),
    ("experiments", page_experiments),
    ("realism", page_realism),
    ("notes", page_notes),
    ("fec", page_fec),
    ("eyes", page_eyes),
    ("measures", page_measures),
    ("scope", page_scope),
    ("spectrum", page_spectrum),
    ("standards", page_standards),
]


def main():
    failures = 0
    for name, fn in PAGES:
        try:
            fn()
            print(f"  OK   {name}")
        except Exception:
            failures += 1
            print(f"  FAIL {name}")
            traceback.print_exc()
    print(f"{len(PAGES) - failures}/{len(PAGES)} pagine OK")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
