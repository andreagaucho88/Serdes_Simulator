"""Pagina note: glossario, confini di validità, esercizi, metodo di studio."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import common, content
from .. import theme as T


def page_notes():
    common.page_header("APPENDICE", "Note, glossario e metodo", None, None,
                       "Il metodo conta più dei numeri: ogni modello deve "
                       "dichiarare cosa è e cosa non è.")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Metodo di studio", "Glossario", "Esercizi guidati", "Confini di validità"])

    with tab1:
        st.markdown(content.SEVEN_QUESTIONS)
        st.markdown("""
**Modalità consigliate**

- **Prima lettura**: preset default, pagina *Catena completa*, leggi i
  checkpoint verdi e il signal ledger.
- **Laboratorio**: cambia un parametro alla volta nella pagina del suo stadio;
  prevedi il segno dell'effetto *prima* di muovere lo slider.
- **Esperimenti**: usa gli sweep per trasformare un'intuizione in una curva.
- **Colloquio**: per ogni pagina, prova a rispondere alle sette domande ad alta
  voce senza guardare le note.
""")
        st.markdown(T.note(
            "Regola di estensione del progetto: ogni nuovo blocco dichiara "
            "input/output, unità, sample rate, reference plane, equazione, "
            "ipotesi, failure mode, osservabile e almeno un checkpoint."),
            unsafe_allow_html=True)

    with tab2:
        rows = [{"termine": k, "definizione": v} for k, v in content.GLOSSARY.items()]
        st.dataframe(pd.DataFrame(rows), use_container_width=True,
                     hide_index=True, height=560)

    with tab3:
        st.markdown(content.EXERCISE_A)
        st.divider()
        st.markdown(content.EXERCISE_B)
        st.divider()
        st.markdown(content.EXERCISE_C)

    with tab4:
        st.markdown(content.VALIDITY)
        st.markdown("""
**Cosa questo simulatore È:**
- una catena end-to-end senza `simulate_link()` opaca, con ogni stadio ispezionabile;
- un framework di sensitivity analysis con checkpoint automatici;
- un compagno eseguibile delle lezioni L01–L28.

**Cosa questo simulatore NON è:**
- un tester TDECQ/SECQ/COM conforme (servono clause, pattern, filtri e
  procedure prescritti);
- un simulatore elettromagnetico o circuitale (i filtri sono magnitudini a
  fase zero: isolano la banda, non la causalità);
- una dichiarazione di conformità Ethernet/OIF (PRBS13Q-style ≠ test vector
  di clause; RLM e opening 3σ sono proxy).

**Semplificazioni dichiarate principali:**
- filtri Butterworth in sola magnitudine (fase zero);
- MZM con chirp parametrico α, non un modello elettro-ottico estratto;
- rumori bianchi gaussiani one-sided (niente 1/f, niente burst);
- CDR: acquisition a griglia + loop first-order, non un NCO quantizzato;
- fibra: solo attenuazione + CD (niente PMD, niente non linearità Kerr);
- il record è un periodo PRBS13Q (8191 simboli): floor statistico ~1e-4.
""")
