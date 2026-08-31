"""serdes_sim — motore didattico della catena SerDes + link ottico IM/DD.

Fisica estratta dal notebook v7 del corso (codice/build_serdes_course_framework_v7.py).
"""

from .config import LinkConfig, PRESETS, DEFAULT_PRESET
from .engine import simulate, sweep, SimResult, SWEEPABLE_FIELDS

__all__ = ["LinkConfig", "PRESETS", "DEFAULT_PRESET", "simulate", "sweep",
           "SimResult", "SWEEPABLE_FIELDS"]
__version__ = "1.0.0"
