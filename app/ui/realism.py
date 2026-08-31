"""Pagina realismo: banco IBIS-AMI + ecosistema di pacchetti/riferimenti."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import streamlit as st

from serdes_sim import ami

from .. import common, plots
from .. import theme as T
from ..state import get_cfg, run_sim

ECOSYSTEM_MD = """
### Cosa usiamo già in questo simulatore

| Pacchetto / risorsa | Stato | Ruolo qui |
|---|---|---|
| **scikit-rf** | installato | lettura robusta Touchstone; il canale S2P può sostituire il modello analitico (pagina *Canale elettrico*) |
| **serdespy** (R. Barrie, UofT) | installato | libreria di riferimento per cross-validare FFE/DFE/CTLE e import canali; stessi algoritmi in forma indipendente |
| **loader IBIS-AMI** (questo tool) | integrato | esegue vere librerie AMI vendor via ctypes (banco qui sotto) |

### Riferimenti studiati (non dipendenze)

| Risorsa | Cosa insegna |
|---|---|
| **PyBERT / pyibis-ami** (D. Banas) | l'ecosistema AMI open in Python: parsing `.ami`, esecuzione modelli, e `ibisami` per *costruire* modelli propri |
| **JLSD** (K. Zheng, Julia) | simulazione SerDes ad alte prestazioni con oversampling; ottimo per confrontare CDR/jitter |
| **MATLAB SerDes Toolbox** | il riferimento commerciale per authoring IBIS-AMI (esporta DLL AMI da blocchi Simulink) |
| **SerDesSystemCProject** | modellazione SystemC/AMS a livello RTL-ish della stessa catena |
| **serdesbook** (Prasun Hardas) | materiale companion del libro di riferimento su equalization/link budget |

### Che cosa significherebbe "usare un modello IBIS-AMI" qui

Un modello IBIS-AMI **è un binario compilato dal vendor** (`.dll`/`.so`/`.dylib`)
più un file `.ami` di parametri: non esiste un "AMI open" del TX/RX di un chip
reale. Il flusso standard EDA è:

1. la piattaforma calcola la **risposta impulsiva del canale** (dal Touchstone);
2. `AMI_Init` del TX e dell'RX la modificano (equalizzazione LTI);
3. se il modello lo supporta, `AMI_GetWave` processa la waveform a blocchi
   (comportamento non lineare / tempo-variante, CDR inclusa);
4. la piattaforma fa statistica su bit e jitter.

Il banco qui sotto implementa esattamente le chiamate 2–3 su una libreria a tua
scelta. Se non hai binari vendor, il pulsante compila un **modello demo in C**
(FFE 3 tap in Init + saturazione in GetWave) per vedere il meccanismo reale.
"""


def page_realism():
    common.page_header("LABORATORIO · REALISMO", "IBIS-AMI e pacchetti",
                       None, None,
                       "Quanto è 'reale' un simulatore? Dipende da cosa "
                       "dichiara. Qui: modelli vendor eseguibili e pacchetti "
                       "di riferimento.")

    st.markdown(ECOSYSTEM_MD)
    st.markdown(T.warn(
        "Eseguire un binario AMI significa <b>eseguire codice del vendor</b>: "
        "caricare solo librerie di cui ti fidi. Il risultato è realistico "
        "quanto il modello che carichi."), unsafe_allow_html=True)

    st.divider()
    st.subheader("Banco IBIS-AMI")

    cfg = get_cfg()
    sim = run_sim()

    col1, col2 = st.columns([1.2, 1])
    with col1:
        lib_path = st.text_input(
            "Percorso libreria AMI (.dylib / .so / .dll)",
            value=st.session_state.get("ami_lib_path", ""),
            placeholder="/percorso/del/modello_tx.dylib")
        if st.button("Compila e usa il modello demo (richiede cc/clang)"):
            try:
                demo_dir = str(Path.home() / ".serdes_sim_ami_demo")
                built = ami.build_demo_model(demo_dir)
                st.session_state["ami_lib_path"] = built
                st.rerun()
            except Exception as exc:
                st.error(f"Compilazione demo fallita: {exc}")
    with col2:
        ami_text = st.text_area("Parametri AMI_parameters_in (formato .ami)",
                                value="(model)", height=68)

    lib_path = st.session_state.get("ami_lib_path", "") or lib_path
    if not lib_path:
        st.info("Indica una libreria AMI oppure compila il modello demo per "
                "provare il flusso Init/GetWave.")
        return
    if not Path(lib_path).exists():
        st.error(f"File non trovato: {lib_path}")
        return

    try:
        model = ami.AmiModel(lib_path)
    except OSError as exc:
        st.error(f"Libreria non caricabile: {exc}")
        return

    st.caption(f"Caricata: `{lib_path}` · AMI_GetWave "
               f"{'presente' if model.has_getwave else 'assente (Init-only/LTI)'}")

    # --- AMI_Init sulla pulse response del canale corrente ------------------
    st.markdown("**AMI_Init — l'impulso del canale prima e dopo il modello**")
    n_ui = 64
    impulse = np.zeros(n_ui * cfg.analog_sps)
    center = 8 * cfg.analog_sps
    impulse[center] = 1.0
    from serdes_sim.blocks.channel import channel_response
    from serdes_sim.utils import apply_frequency_response
    channel_impulse, _, _ = apply_frequency_response(
        impulse, cfg.fs_analog_hz, lambda f: channel_response(f, cfg))

    res_init = model.init(channel_impulse, 1 / cfg.fs_analog_hz, cfg.ui_s,
                          params_in=ami_text)
    if not res_init.ok:
        st.error(f"AMI_Init ha ritornato {res_init.returned}: "
                 f"{res_init.error or res_init.msg}")
        model.close()
        return

    t_ui = (np.arange(len(channel_impulse)) - center) / cfg.analog_sps
    window = (t_ui > -4) & (t_ui < 12)
    fig = plots.line_fig(
        [dict(x=t_ui[window], y=channel_impulse[window] / np.max(np.abs(channel_impulse)),
              name="impulso canale", color=T.MUTED, width=1.6),
         dict(x=t_ui[window], y=res_init.output[window] / np.max(np.abs(channel_impulse)),
              name="dopo AMI_Init", color=T.DIGITAL, width=2.2)],
        xtitle="Tempo [UI]", ytitle="Ampiezza normalizzata", height=320)
    st.plotly_chart(fig, use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        if res_init.msg:
            st.caption(f"msg del modello: `{res_init.msg}`")
    with c2:
        if res_init.params_out:
            try:
                tree = ami.parse_ami_tree(res_init.params_out)
                st.json(ami.ami_tree_to_dict(tree), expanded=False)
            except Exception:
                st.caption(f"AMI_parameters_out: `{res_init.params_out[:200]}`")

    # --- AMI_GetWave sulla waveform TX corrente -----------------------------
    if model.has_getwave:
        st.markdown("**AMI_GetWave — la waveform del driver prima e dopo**")
        n_show = 12 * cfg.analog_sps
        wave = sim.tx.driver_voltage_v[:4096].copy()
        res_wave = model.getwave(wave)
        if res_wave.ok:
            t_ps = np.arange(n_show) / cfg.fs_analog_hz * 1e12
            fig = plots.line_fig(
                [dict(x=t_ps, y=wave[:n_show], name="ingresso", color=T.MUTED,
                      width=1.6),
                 dict(x=t_ps, y=res_wave.output[:n_show], name="dopo GetWave",
                      color=T.ELECTRICAL, width=2.2)],
                xtitle="Tempo [ps]", ytitle="V", height=320)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error(f"AMI_GetWave: {res_wave.error or res_wave.returned}")
    model.close()

    st.markdown(T.note(
        "Questo è un <b>banco separato</b>: il modello AMI non viene inserito "
        "nel percorso principale della catena. Integrarlo (sostituendo TX FFE + "
        "driver con il modello vendor) è l'estensione naturale — vedi "
        "HANDOFF_CODEX.md."), unsafe_allow_html=True)
