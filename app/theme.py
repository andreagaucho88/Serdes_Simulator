"""Tema visivo del simulatore: palette a dominio fisico, tipografia, CSS.

Palette (codifica informazione, non decorazione):
- elettrico  = ciano   #56C8E8
- ottico     = ambra IR #FF7A59  (la 1550 nm è invisibile: nei lab si rende in rosso)
- digitale   = violetto #B49CFF
"""

BG = "#0B0F14"
PANEL = "#111922"
PANEL_2 = "#16212C"
GRID = "#1C2833"
INK = "#D7E1E8"
MUTED = "#8CA1AF"

ELECTRICAL = "#56C8E8"
OPTICAL = "#FF7A59"
DIGITAL = "#B49CFF"
AMBER = "#E8C55A"
GREEN_OK = "#3ECF8E"
RED_FAIL = "#FF5470"
TEAL = "#6BD3A8"

DOMAIN_COLORS = {
    "electrical": ELECTRICAL,
    "optical": OPTICAL,
    "digital": DIGITAL,
}

DOMAIN_LABELS = {
    "electrical": "dominio elettrico",
    "optical": "dominio ottico",
    "digital": "dominio digitale / DSP",
}

FONT_BODY = "'IBM Plex Sans', 'Helvetica Neue', sans-serif"
FONT_MONO = "'IBM Plex Mono', 'SF Mono', Menlo, monospace"
FONT_DISPLAY = "'Space Grotesk', 'IBM Plex Sans', sans-serif"

GLOBAL_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap');

html, body, [class*="css"] {{
    font-family: {FONT_BODY};
}}

h1, h2, h3 {{
    font-family: {FONT_DISPLAY} !important;
    letter-spacing: -0.01em;
}}

/* KPI "strumento": numeri in mono */
[data-testid="stMetricValue"] {{
    font-family: {FONT_MONO};
    font-size: 1.55rem;
}}
[data-testid="stMetricLabel"] {{
    color: {MUTED};
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.72rem;
}}

/* tabelle in mono compatto */
[data-testid="stDataFrame"] {{
    font-family: {FONT_MONO};
    font-size: 0.8rem;
}}

/* eyebrow di pagina */
.eyebrow {{
    font-family: {FONT_MONO};
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: {MUTED};
    margin-bottom: -0.4rem;
}}
.eyebrow .dom-electrical {{ color: {ELECTRICAL}; }}
.eyebrow .dom-optical {{ color: {OPTICAL}; }}
.eyebrow .dom-digital {{ color: {DIGITAL}; }}

/* callout didattici */
.note-box {{
    border-left: 3px solid {DIGITAL};
    background: {PANEL};
    padding: 0.7rem 1rem;
    border-radius: 0 8px 8px 0;
    margin: 0.6rem 0;
    color: {INK};
    font-size: 0.92rem;
}}
.warn-box {{
    border-left: 3px solid {AMBER};
    background: {PANEL};
    padding: 0.7rem 1rem;
    border-radius: 0 8px 8px 0;
    margin: 0.6rem 0;
    color: {INK};
    font-size: 0.92rem;
}}
.warn-box b, .note-box b {{ color: {AMBER}; }}
.note-box b {{ color: {DIGITAL}; }}

/* badge PASS/FAIL */
.badge-pass, .badge-fail {{
    font-family: {FONT_MONO};
    font-size: 0.72rem;
    padding: 0.1rem 0.5rem;
    border-radius: 99px;
}}
.badge-pass {{ background: rgba(62,207,142,.12); color: {GREEN_OK}; }}
.badge-fail {{ background: rgba(255,84,112,.12); color: {RED_FAIL}; }}

/* glow del blocco attivo nello schema (disattivato se reduced motion) */
@keyframes pulse-glow {{
    0%, 100% {{ opacity: 0.85; }}
    50% {{ opacity: 1.0; }}
}}
.chain-active {{ animation: pulse-glow 2.6s ease-in-out infinite; }}
@media (prefers-reduced-motion: reduce) {{
    .chain-active {{ animation: none; }}
}}

/* sidebar più da rack */
[data-testid="stSidebar"] {{
    background: {PANEL};
    border-right: 1px solid {GRID};
}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
    font-size: 0.88rem;
}}
</style>
"""


def eyebrow(section: str, domain: str | None = None) -> str:
    """Etichetta sopra il titolo di pagina, con dominio colorato."""
    dom = ""
    if domain:
        dom = f' · <span class="dom-{domain}">{DOMAIN_LABELS[domain]}</span>'
    return f'<div class="eyebrow">{section}{dom}</div>'


def note(text: str) -> str:
    return f'<div class="note-box">{text}</div>'


def warn(text: str) -> str:
    return f'<div class="warn-box">{text}</div>'
