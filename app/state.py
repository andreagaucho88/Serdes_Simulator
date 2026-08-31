"""Stato condiviso della GUI: config corrente, cache della simulazione,
widget helper che modificano la LinkConfig in modo controllato."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from serdes_sim import LinkConfig, PRESETS, DEFAULT_PRESET, simulate  # noqa: E402

# La config sopravvive anche a un full reload del browser (i blocchi cliccabili
# dello schema navigano via URL): viene specchiata su disco a ogni modifica.
_PERSIST_PATH = Path(__file__).resolve().parent.parent / ".last_session.json"


def _load_persisted():
    try:
        payload = json.loads(_PERSIST_PATH.read_text())
        cfg_dict = payload["cfg"]
        cfg_dict["tx_ffe_taps"] = tuple(cfg_dict["tx_ffe_taps"])
        return LinkConfig(**cfg_dict), payload.get("preset_name", DEFAULT_PRESET)
    except Exception:
        return None, None


def _persist(cfg: LinkConfig):
    """Scrittura atomica (tmp + rename): un reload a metà scrittura non può
    leggere un file corrotto. Nota: il file è condiviso fra le sessioni di
    questo utente — è pensato per un uso locale mono-utente."""
    try:
        tmp = _PERSIST_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps({
            "cfg": cfg.to_dict(),
            "preset_name": st.session_state.get("preset_name", DEFAULT_PRESET),
        }))
        tmp.replace(_PERSIST_PATH)
    except Exception:
        pass  # la persistenza è best-effort


def reload_cfg_from_disk() -> bool:
    """Ricarica la config persistita se diversa da quella in sessione.

    Usata dallo scope live per riflettere modifiche fatte da un'altra tab
    (ogni tab Streamlit è una sessione separata). Ritorna True se aggiornata."""
    cfg, preset_name = _load_persisted()
    if cfg is None:
        return False
    if "cfg" not in st.session_state or st.session_state.cfg != cfg:
        st.session_state.cfg = cfg
        if preset_name:
            st.session_state.preset_name = preset_name
        return True
    return False


def get_cfg() -> LinkConfig:
    if "cfg" not in st.session_state:
        cfg, preset_name = _load_persisted()
        if cfg is None:
            cfg, preset_name = PRESETS[DEFAULT_PRESET][0], DEFAULT_PRESET
        st.session_state.cfg = cfg
        st.session_state.preset_name = preset_name
    return st.session_state.cfg


def set_cfg(cfg: LinkConfig):
    st.session_state.cfg = cfg
    _persist(cfg)


def apply_preset(name: str):
    st.session_state.preset_name = name
    set_cfg(PRESETS[name][0])
    # i widget parametro vanno resettati, altrimenti mostrano il valore vecchio
    for key in [k for k in st.session_state if str(k).startswith("w_")]:
        del st.session_state[key]


@st.cache_resource(show_spinner=False, max_entries=24)
def _cached_sim(cfg_json: str, seed: int, depth: str):
    payload = json.loads(cfg_json)
    payload["tx_ffe_taps"] = tuple(payload["tx_ffe_taps"])
    return simulate(LinkConfig(**payload), seed=seed, depth=depth)


def run_sim(cfg: LinkConfig = None, depth: str = "full"):
    cfg = cfg or get_cfg()
    seed = int(st.session_state.get("seed", 20240731))
    with st.spinner("Simulazione della catena in corso…"):
        return _cached_sim(json.dumps(cfg.to_dict()), seed, depth)


# ---------------------------------------------------------------------------
# Widget parametro: unica fonte di verità = st.session_state.cfg
# ---------------------------------------------------------------------------

def param_slider(label, field, min_value, max_value, step=None, scale=1.0,
                 fmt=None, help=None):
    """Slider legato a un campo di LinkConfig (visualizzato in unità scalate)."""
    cfg = get_cfg()
    current = getattr(cfg, field) / scale
    kwargs = dict(help=help, key=f"w_{field}")
    if fmt:
        kwargs["format"] = fmt
    new = st.slider(label, float(min_value), float(max_value), float(current),
                    step=float(step) if step else None, **kwargs)
    if abs(new - current) > 1e-15:
        set_cfg(cfg.with_updates(**{field: new * scale}))
    return new * scale


def param_int_slider(label, field, min_value, max_value, help=None, step=1):
    cfg = get_cfg()
    current = int(getattr(cfg, field))
    # aggancia il valore alla griglia dello slider (config esterne/persistite)
    current = int(min_value) + round((current - int(min_value)) / step) * int(step)
    current = max(int(min_value), min(int(max_value), current))
    new = st.slider(label, int(min_value), int(max_value), current,
                    step=int(step), help=help, key=f"w_{field}")
    if new != current:
        set_cfg(cfg.with_updates(**{field: int(new)}))
    return new


def param_select(label, field, options, format_func=str, help=None):
    cfg = get_cfg()
    current = getattr(cfg, field)
    idx = options.index(current) if current in options else 0
    new = st.selectbox(label, options, index=idx, format_func=format_func,
                       help=help, key=f"w_{field}")
    if new != current:
        set_cfg(cfg.with_updates(**{field: new}))
    return new


def ffe_taps_widget():
    """Tre slider per i tap del TX FFE (pre, main, post)."""
    cfg = get_cfg()
    pre, main, post = cfg.tx_ffe_taps
    c1, c2, c3 = st.columns(3)
    with c1:
        new_pre = st.slider("Tap pre-cursor", -0.35, 0.0, float(pre), 0.01,
                            key="w_ffe_pre")
    with c2:
        new_main = st.slider("Tap main", 0.5, 1.2, float(main), 0.01,
                             key="w_ffe_main")
    with c3:
        new_post = st.slider("Tap post-cursor", -0.35, 0.0, float(post), 0.01,
                             key="w_ffe_post")
    new_taps = (new_pre, new_main, new_post)
    if new_taps != cfg.tx_ffe_taps:
        set_cfg(cfg.with_updates(tx_ffe_taps=new_taps))
    return new_taps
