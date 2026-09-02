"""Schemi SVG: catena completa con blocco attivo evidenziato + mini-schemi.

La catena è l'elemento firma della GUI: due file (TX sopra, RX sotto),
colori per dominio fisico, reference plane tratteggiati nei tre attraversamenti
irreversibili (E/O al MZM, O/E al PD, A/D all'ADC).
"""

from __future__ import annotations

from . import theme as T

# (id, etichetta, dominio, riga) — l'ordine è l'ordine del segnale
CHAIN_BLOCKS = [
    ("stimulus", "PRBS\nNRZ/PAM4", "digital", 0),
    ("txffe", "TX FFE", "digital", 0),
    ("dac", "DAC", "electrical", 0),
    ("driver", "Driver", "electrical", 0),
    ("channel", "Canale el.\nS21", "electrical", 0),
    ("mzm", "MZM", "optical", 0),
    ("fiber", "Fibra\nloss + CD", "optical", 0),
    ("pd", "PD", "electrical", 1),
    ("tia", "TIA + AGC", "electrical", 1),
    ("ctle", "CTLE", "electrical", 1),
    ("adc", "ADC 2 sps\ninterleaved", "digital", 1),
    ("cdr", "CDR\nGardner/MM", "digital", 1),
    ("eq", "FSE + DFE", "digital", 1),
    ("ber", "BER · LLR\nGMI", "digital", 1),
    # analisi del pattern d'errore, NON un encoder/decoder nel data path
    ("fec", "Analisi FEC\nRS(544,514)", "digital", 1),
]

# pagina di destinazione (url_path) per ogni blocco cliccabile
BLOCK_LINKS = {
    "stimulus": "stimolo", "txffe": "tx", "dac": "tx", "driver": "tx",
    "channel": "canale", "mzm": "mzm", "fiber": "fibra",
    "pd": "ricevitore", "tia": "ricevitore", "ctle": "ricevitore",
    "adc": "adc", "cdr": "timing", "eq": "eq", "ber": "ber", "fec": "fec",
}

_W, _H = 122, 52
_ROW_Y = (64, 178)


def chain_diagram(active: str | None = None, clickable: bool = True) -> str:
    rows = {0: [], 1: []}
    for bid, label, dom, row in CHAIN_BLOCKS:
        rows[row].append((bid, label, dom))

    max_len = max(len(b) for b in rows.values())
    gap = 22
    total_w = 40 * 2 + max_len * _W + (max_len - 1) * gap
    row_x0 = {r: (total_w - (len(b) * _W + (len(b) - 1) * gap)) / 2
              for r, b in rows.items()}

    def block_xy(index_in_row, row):
        return row_x0[row] + index_in_row * (_W + gap), _ROW_Y[row]

    parts = []
    parts.append(
        f'<svg viewBox="0 0 {total_w} 258" width="100%" '
        f'style="max-width:1200px;display:block;margin:0 auto;" '
        f'xmlns="http://www.w3.org/2000/svg" font-family="{T.FONT_MONO}">')
    parts.append(
        '<defs><filter id="glow" x="-40%" y="-40%" width="180%" height="180%">'
        '<feGaussianBlur stdDeviation="5" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter></defs>')

    positions = {}
    for row_idx, blocks in rows.items():
        for i, (bid, label, dom) in enumerate(blocks):
            x, y = block_xy(i, row_idx)
            positions[bid] = (x, y)
            color = T.DOMAIN_COLORS[dom]
            is_active = bid == active
            fill = "rgba(255,255,255,0.035)"
            stroke_w = 2.4 if is_active else 1.2
            extra = 'filter="url(#glow)" class="chain-active"' if is_active else ""
            opacity = "1" if (is_active or active is None) else "0.55"
            href = BLOCK_LINKS.get(bid) if clickable else None
            if href:
                parts.append(f'<a href="/{href}" target="_self" '
                             f'style="cursor:pointer;">')
            parts.append(f'<g opacity="{opacity}">')
            parts.append(
                f'<rect x="{x}" y="{y}" width="{_W}" height="{_H}" rx="9" '
                f'fill="{fill}" stroke="{color}" stroke-width="{stroke_w}" {extra}/>')
            lines = label.split("\n")
            if len(lines) == 1:
                parts.append(
                    f'<text x="{x + _W / 2}" y="{y + _H / 2 + 4}" text-anchor="middle" '
                    f'fill="{T.INK}" font-size="12.5">{lines[0]}</text>')
            else:
                parts.append(
                    f'<text x="{x + _W / 2}" y="{y + _H / 2 - 3}" text-anchor="middle" '
                    f'fill="{T.INK}" font-size="12">{lines[0]}</text>')
                parts.append(
                    f'<text x="{x + _W / 2}" y="{y + _H / 2 + 13}" text-anchor="middle" '
                    f'fill="{T.MUTED}" font-size="10">{lines[1]}</text>')
            parts.append("</g>")
            if href:
                parts.append("</a>")

    def arrow(x1, y1, x2, y2, color):
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
            f'stroke-width="1.6"/>')
        parts.append(
            f'<polygon points="{x2},{y2} {x2 - 7},{y2 - 3.5} {x2 - 7},{y2 + 3.5}" '
            f'fill="{color}"/>')

    # frecce orizzontali dentro ciascuna fila (colore del blocco di destinazione)
    for row_idx, blocks in rows.items():
        for i in range(len(blocks) - 1):
            x, y = block_xy(i, row_idx)
            color = T.DOMAIN_COLORS[blocks[i + 1][2]]
            arrow(x + _W, y + _H / 2, x + _W + gap, y + _H / 2, color)

    # laser sopra il MZM
    mzm_x, mzm_y = positions["mzm"]
    lx, ly = mzm_x + 14, 8
    parts.append(
        f'<rect x="{lx}" y="{ly}" width="{_W - 28}" height="30" rx="8" '
        f'fill="rgba(255,122,89,0.08)" stroke="{T.OPTICAL}" stroke-width="1.1"/>')
    parts.append(
        f'<text x="{lx + (_W - 28) / 2}" y="{ly + 19}" text-anchor="middle" '
        f'fill="{T.OPTICAL}" font-size="11">LASER CW</text>')
    parts.append(
        f'<line x1="{mzm_x + _W / 2}" y1="{ly + 30}" x2="{mzm_x + _W / 2}" '
        f'y2="{mzm_y}" stroke="{T.OPTICAL}" stroke-width="1.4"/>')
    parts.append(
        f'<polygon points="{mzm_x + _W / 2},{mzm_y} {mzm_x + _W / 2 - 3.5},{mzm_y - 7} '
        f'{mzm_x + _W / 2 + 3.5},{mzm_y - 7}" fill="{T.OPTICAL}"/>')

    # ritorno fibra → PD (fila 2)
    fx, fy = positions["fiber"]
    px, py = positions["pd"]
    mid_y = (_ROW_Y[0] + _H + _ROW_Y[1]) / 2
    parts.append(
        f'<path d="M {fx + _W} {fy + _H / 2} h 16 q 8 0 8 8 V {mid_y} '
        f'H {px - 22} q -8 0 -8 8 V {py + _H / 2 - 8} q 0 8 8 8 h 14" '
        f'fill="none" stroke="{T.OPTICAL}" stroke-width="1.6" stroke-dasharray="1 0"/>')
    parts.append(
        f'<polygon points="{px},{py + _H / 2} {px - 7},{py + _H / 2 - 3.5} '
        f'{px - 7},{py + _H / 2 + 3.5}" fill="{T.OPTICAL}"/>')

    # reference plane tratteggiati: E/O, O/E, A/D
    def ref_plane(x, y, label):
        parts.append(
            f'<line x1="{x}" y1="{y - 8}" x2="{x}" y2="{y + _H + 8}" '
            f'stroke="{T.MUTED}" stroke-width="1" stroke-dasharray="4 4"/>')
        parts.append(
            f'<text x="{x}" y="{y + _H + 21}" text-anchor="middle" '
            f'fill="{T.MUTED}" font-size="9.5">{label}</text>')

    ref_plane(mzm_x - gap / 2, mzm_y, "piano E/O")
    ref_plane(px - gap / 2 - 4, py, "piano O/E")
    ax, ay = positions["adc"]
    ref_plane(ax - gap / 2, ay, "piano A/D")

    parts.append("</svg>")
    return "".join(parts)


def domain_legend() -> str:
    items = [("digital", "digitale / DSP"), ("electrical", "elettrico"),
             ("optical", "ottico")]
    spans = "".join(
        f'<span style="margin-right:1.2rem;font-family:{T.FONT_MONO};'
        f'font-size:0.72rem;color:{T.MUTED};">'
        f'<span style="display:inline-block;width:10px;height:10px;'
        f'border-radius:2px;background:{T.DOMAIN_COLORS[d]};margin-right:6px;"></span>'
        f'{label}</span>'
        for d, label in items)
    return f'<div style="text-align:center;margin-top:-6px;">{spans}</div>'


# ---------------------------------------------------------------------------
# Mini-schemi per le pagine di dettaglio
# ---------------------------------------------------------------------------

def mzm_schematic() -> str:
    """Interferometro Mach-Zehnder: split, due bracci con phase shifter, ricombina."""
    o, e, mut = T.OPTICAL, T.ELECTRICAL, T.MUTED
    return f"""
<svg viewBox="0 0 560 170" width="100%" style="max-width:560px" xmlns="http://www.w3.org/2000/svg" font-family="{T.FONT_MONO}">
  <text x="10" y="90" fill="{o}" font-size="11">E in</text>
  <line x1="45" y1="85" x2="95" y2="85" stroke="{o}" stroke-width="2"/>
  <path d="M 95 85 C 125 85 125 45 155 45" fill="none" stroke="{o}" stroke-width="2"/>
  <path d="M 95 85 C 125 85 125 125 155 125" fill="none" stroke="{o}" stroke-width="2"/>
  <line x1="155" y1="45" x2="330" y2="45" stroke="{o}" stroke-width="2"/>
  <line x1="155" y1="125" x2="330" y2="125" stroke="{o}" stroke-width="2"/>
  <rect x="200" y="28" width="90" height="34" rx="6" fill="rgba(86,200,232,0.08)" stroke="{e}"/>
  <text x="245" y="49" text-anchor="middle" fill="{e}" font-size="10.5">+φ(t)/2</text>
  <rect x="200" y="108" width="90" height="34" rx="6" fill="rgba(86,200,232,0.08)" stroke="{e}"/>
  <text x="245" y="129" text-anchor="middle" fill="{e}" font-size="10.5">−φ(t)/2</text>
  <line x1="245" y1="10" x2="245" y2="28" stroke="{e}" stroke-width="1.6"/>
  <text x="255" y="18" fill="{e}" font-size="10">V(t) push-pull</text>
  <path d="M 330 45 C 360 45 360 85 390 85" fill="none" stroke="{o}" stroke-width="2"/>
  <path d="M 330 125 C 360 125 360 85 390 85" fill="none" stroke="{o}" stroke-width="2"/>
  <line x1="390" y1="85" x2="450" y2="85" stroke="{o}" stroke-width="2"/>
  <text x="458" y="90" fill="{o}" font-size="11">E out</text>
  <text x="280" y="160" text-anchor="middle" fill="{mut}" font-size="10">Δφ = φ_b + πV/Vπ · uscita ∝ cos(Δφ/2) · chirp e^(jαΔφ/2)</text>
</svg>"""


def pd_tia_schematic() -> str:
    o, e, mut = T.OPTICAL, T.ELECTRICAL, T.MUTED
    return f"""
<svg viewBox="0 0 560 150" width="100%" style="max-width:560px" xmlns="http://www.w3.org/2000/svg" font-family="{T.FONT_MONO}">
  <text x="8" y="70" fill="{o}" font-size="11">P(t)</text>
  <line x1="42" y1="65" x2="105" y2="65" stroke="{o}" stroke-width="2" stroke-dasharray="6 4"/>
  <polygon points="105,45 105,85 140,65" fill="none" stroke="{e}" stroke-width="2"/>
  <line x1="140" y1="45" x2="140" y2="85" stroke="{e}" stroke-width="2"/>
  <text x="122" y="105" text-anchor="middle" fill="{mut}" font-size="10">PD: I = R·P + I_d</text>
  <line x1="140" y1="65" x2="215" y2="65" stroke="{e}" stroke-width="2"/>
  <text x="177" y="55" text-anchor="middle" fill="{e}" font-size="10">I(t) + shot/RIN</text>
  <polygon points="215,38 215,92 285,65" fill="rgba(86,200,232,0.08)" stroke="{e}" stroke-width="2"/>
  <text x="238" y="69" fill="{e}" font-size="11">TIA</text>
  <path d="M 215 38 h 35 v -18 h 40 v 18" fill="none" stroke="{e}" stroke-width="1.4"/>
  <rect x="250" y="12" width="40" height="12" fill="none" stroke="{e}" stroke-width="1.4"/>
  <text x="300" y="23" fill="{mut}" font-size="10">Z_T [Ω]</text>
  <line x1="285" y1="65" x2="360" y2="65" stroke="{e}" stroke-width="2"/>
  <rect x="360" y="45" width="80" height="40" rx="6" fill="rgba(86,200,232,0.08)" stroke="{e}"/>
  <text x="400" y="69" text-anchor="middle" fill="{e}" font-size="11">AGC</text>
  <line x1="440" y1="65" x2="500" y2="65" stroke="{e}" stroke-width="2"/>
  <text x="506" y="70" fill="{e}" font-size="11">V(t)</text>
  <text x="280" y="135" text-anchor="middle" fill="{mut}" font-size="10">square-law: la fase ottica non è più osservabile dopo questo piano</text>
</svg>"""


def dfe_schematic() -> str:
    d, ink, mut = T.DIGITAL, T.INK, T.MUTED
    return f"""
<svg viewBox="0 0 560 170" width="100%" style="max-width:560px" xmlns="http://www.w3.org/2000/svg" font-family="{T.FONT_MONO}">
  <text x="8" y="66" fill="{d}" font-size="11">y_k (FSE)</text>
  <line x1="80" y1="61" x2="130" y2="61" stroke="{d}" stroke-width="2"/>
  <circle cx="150" cy="61" r="16" fill="none" stroke="{d}" stroke-width="2"/>
  <text x="150" y="66" text-anchor="middle" fill="{ink}" font-size="14">Σ</text>
  <text x="163" y="88" fill="{mut}" font-size="12">−</text>
  <line x1="166" y1="61" x2="245" y2="61" stroke="{d}" stroke-width="2"/>
  <rect x="245" y="38" width="105" height="46" rx="8" fill="rgba(180,156,255,0.08)" stroke="{d}" stroke-width="1.6"/>
  <text x="297" y="59" text-anchor="middle" fill="{ink}" font-size="11">slicer</text>
  <text x="297" y="75" text-anchor="middle" fill="{mut}" font-size="9.5">4 livelli Gray</text>
  <line x1="350" y1="61" x2="470" y2="61" stroke="{d}" stroke-width="2"/>
  <text x="478" y="66" fill="{d}" font-size="11">â_k</text>
  <line x1="410" y1="61" x2="410" y2="128" stroke="{d}" stroke-width="1.6"/>
  <rect x="220" y="110" width="150" height="36" rx="8" fill="rgba(180,156,255,0.08)" stroke="{d}" stroke-width="1.6"/>
  <text x="295" y="132" text-anchor="middle" fill="{ink}" font-size="10.5">Σ b_m · â_(k−m)</text>
  <line x1="410" y1="128" x2="370" y2="128" stroke="{d}" stroke-width="1.6"/>
  <path d="M 220 128 H 150 V 77" fill="none" stroke="{d}" stroke-width="1.6"/>
  <polygon points="150,77 146.5,84 153.5,84" fill="{d}"/>
  <text x="280" y="164" text-anchor="middle" fill="{mut}" font-size="10">una decisione errata entra nella storia: error propagation causale</text>
</svg>"""


def adc_interleave_schematic() -> str:
    e, d, ink, mut = T.ELECTRICAL, T.DIGITAL, T.INK, T.MUTED
    lanes = ""
    for i in range(4):
        y = 26 + i * 30
        lanes += (
            f'<rect x="180" y="{y}" width="120" height="22" rx="5" '
            f'fill="rgba(180,156,255,0.08)" stroke="{d}" stroke-width="1.3"/>'
            f'<text x="240" y="{y + 15}" text-anchor="middle" fill="{ink}" font-size="9.5">'
            f'sub-ADC {i} · g{i}, o{i}, τ{i}</text>'
            f'<line x1="120" y1="{y + 11}" x2="180" y2="{y + 11}" stroke="{e}" stroke-width="1.4"/>'
            f'<line x1="300" y1="{y + 11}" x2="352" y2="{y + 11}" stroke="{d}" stroke-width="1.4"/>')
    return f"""
<svg viewBox="0 0 560 160" width="100%" style="max-width:560px" xmlns="http://www.w3.org/2000/svg" font-family="{T.FONT_MONO}">
  <text x="8" y="80" fill="{e}" font-size="11">V(t)</text>
  <line x1="45" y1="75" x2="95" y2="75" stroke="{e}" stroke-width="2"/>
  <line x1="95" y1="37" x2="95" y2="113" stroke="{e}" stroke-width="1.6"/>
  <line x1="95" y1="37" x2="120" y2="37" stroke="{e}" stroke-width="1.4"/>
  <line x1="95" y1="67" x2="120" y2="67" stroke="{e}" stroke-width="1.4"/>
  <line x1="95" y1="97" x2="120" y2="97" stroke="{e}" stroke-width="1.4"/>
  <line x1="95" y1="113" x2="120" y2="116" stroke="{e}" stroke-width="1.4"/>
  {lanes}
  <line x1="352" y1="37" x2="352" y2="116" stroke="{d}" stroke-width="1.6"/>
  <rect x="352" y="58" width="66" height="36" rx="6" fill="rgba(180,156,255,0.08)" stroke="{d}" stroke-width="1.6"/>
  <text x="385" y="80" text-anchor="middle" fill="{ink}" font-size="10.5">MUX</text>
  <line x1="418" y1="76" x2="475" y2="76" stroke="{d}" stroke-width="2"/>
  <text x="482" y="81" fill="{d}" font-size="11">x[n]</text>
  <text x="280" y="150" text-anchor="middle" fill="{mut}" font-size="10">lane m = n mod M · gli spur cadono a k·fs/M · il DSP vede solo x[n]</text>
</svg>"""


def ctle_schematic() -> str:
    e, mut, ink = T.ELECTRICAL, T.MUTED, T.INK
    return f"""
<svg viewBox="0 0 560 130" width="100%" style="max-width:560px" xmlns="http://www.w3.org/2000/svg" font-family="{T.FONT_MONO}">
  <line x1="30" y1="95" x2="520" y2="95" stroke="{mut}" stroke-width="1"/>
  <line x1="60" y1="110" x2="60" y2="20" stroke="{mut}" stroke-width="1"/>
  <path d="M 60 70 L 200 70 C 260 70 250 38 320 38 L 400 38 C 450 38 460 80 505 95" fill="none" stroke="{e}" stroke-width="2.4"/>
  <circle cx="215" cy="70" r="5" fill="none" stroke="{ink}" stroke-width="1.6"/>
  <text x="215" y="115" text-anchor="middle" fill="{ink}" font-size="10">zero f_z</text>
  <line x1="330" y1="38" x2="330" y2="30" stroke="{ink}" stroke-width="0"/>
  <text x="330" y="28" text-anchor="middle" fill="{ink}" font-size="10">polo f_p</text>
  <path d="M 325 33 L 330 43 L 335 33" fill="none" stroke="{ink}" stroke-width="1.4"/>
  <text x="452" y="55" text-anchor="middle" fill="{ink}" font-size="10">polo alto f_h</text>
  <text x="90" y="55" fill="{mut}" font-size="10">|H(f)| dB</text>
  <text x="500" y="112" fill="{mut}" font-size="10">f</text>
</svg>"""
