"""Helper Plotly con il tema del simulatore (dark, mono, colori per dominio)."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from . import theme as T


def base_layout(**kwargs):
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=T.PANEL,
        font=dict(family=T.FONT_MONO, size=11.5, color=T.INK),
        margin=dict(l=54, r=18, t=44, b=46),
        xaxis=dict(gridcolor=T.GRID, zerolinecolor=T.GRID, linecolor=T.GRID),
        yaxis=dict(gridcolor=T.GRID, zerolinecolor=T.GRID, linecolor=T.GRID),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10.5)),
        hoverlabel=dict(font_family=T.FONT_MONO),
    )
    for key, value in kwargs.items():
        if key in ("xaxis", "yaxis") and isinstance(value, dict):
            layout[key] = {**layout[key], **value}
        else:
            layout[key] = value
    return layout


def line_fig(traces, title=None, xtitle=None, ytitle=None, height=340,
             ylog=False, xlog=False, **layout_kwargs):
    """traces: iterable di dict(x=…, y=…, name=…, color=…, dash=…, mode=…, width=…, opacity=…)."""
    fig = go.Figure()
    for tr in traces:
        fig.add_trace(go.Scatter(
            x=np.asarray(tr["x"]), y=np.asarray(tr["y"]),
            name=tr.get("name", ""),
            mode=tr.get("mode", "lines"),
            opacity=tr.get("opacity", 1.0),
            line=dict(color=tr.get("color", T.ELECTRICAL),
                      dash=tr.get("dash", "solid"),
                      width=tr.get("width", 2),
                      shape=tr.get("shape", "linear")),
            marker=dict(size=tr.get("marker_size", 5)),
            showlegend=bool(tr.get("name")),
        ))
    xaxis = dict(title=xtitle, type="log" if xlog else "linear")
    yaxis = dict(title=ytitle, type="log" if ylog else "linear")
    xaxis.update(layout_kwargs.pop("xaxis", {}))
    yaxis.update(layout_kwargs.pop("yaxis", {}))
    fig.update_layout(base_layout(
        title=dict(text=title, font=dict(family=T.FONT_DISPLAY, size=15)) if title else None,
        xaxis=xaxis, yaxis=yaxis,
        height=height, **layout_kwargs))
    return fig


def vline(fig, x, color=T.MUTED, dash="dash", label=None):
    fig.add_vline(x=x, line_color=color, line_dash=dash, line_width=1.2,
                  annotation_text=label, annotation_font=dict(size=10, color=color))
    return fig


def hline(fig, y, color=T.MUTED, dash="dot", label=None):
    fig.add_hline(y=y, line_color=color, line_dash=dash, line_width=1.2,
                  annotation_text=label, annotation_font=dict(size=10, color=color))
    return fig


def stem_fig(x, y, title=None, xtitle=None, ytitle=None, color=T.DIGITAL, height=320):
    fig = go.Figure()
    for xi, yi in zip(np.asarray(x), np.asarray(y)):
        fig.add_trace(go.Scatter(x=[xi, xi], y=[0, yi], mode="lines",
                                 line=dict(color=color, width=1.4),
                                 showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=np.asarray(x), y=np.asarray(y), mode="markers",
                             marker=dict(color=color, size=7), showlegend=False,
                             hovertemplate="%{x}: %{y:.4f}<extra></extra>"))
    fig.update_layout(base_layout(
        title=dict(text=title, font=dict(family=T.FONT_DISPLAY, size=15)) if title else None,
        xaxis=dict(title=xtitle), yaxis=dict(title=ytitle), height=height))
    hline(fig, 0, color=T.GRID, dash="solid")
    return fig


def _eye_colorscale(domain_color):
    return [
        [0.0, "rgba(17,25,34,0)"],
        [0.08, domain_color.replace(")", ", 0.25)").replace("rgb", "rgba")
         if domain_color.startswith("rgb") else _hex_to_rgba(domain_color, 0.28)],
        [0.45, _hex_to_rgba(domain_color, 0.75)],
        [1.0, "#FFFFFF"],
    ]


def _hex_to_rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def eye_heatmap(H, t_edges, v_edges, title=None, domain_color=T.ELECTRICAL,
                height=380, vtitle="Ampiezza [V]"):
    """Eye a densità (istogramma 2D log-compresso), stile scope."""
    z = np.log1p(H)
    fig = go.Figure(go.Heatmap(
        z=z,
        x=0.5 * (np.asarray(t_edges)[:-1] + np.asarray(t_edges)[1:]),
        y=0.5 * (np.asarray(v_edges)[:-1] + np.asarray(v_edges)[1:]),
        colorscale=_eye_colorscale(domain_color),
        showscale=False,
        hovertemplate="t=%{x:.2f} UI<br>V=%{y:.3f}<extra></extra>",
    ))
    fig.update_layout(base_layout(
        title=dict(text=title, font=dict(family=T.FONT_DISPLAY, size=15)) if title else None,
        xaxis=dict(title="Tempo [UI]"), yaxis=dict(title=vtitle),
        height=height, plot_bgcolor="#0D131A"))
    return fig


def bar_fig(x, y, title=None, xtitle=None, ytitle=None, color=T.ELECTRICAL,
            height=320, text=None):
    fig = go.Figure(go.Bar(x=list(x), y=list(y), marker_color=color,
                           text=text, textfont=dict(family=T.FONT_MONO)))
    fig.update_layout(base_layout(
        title=dict(text=title, font=dict(family=T.FONT_DISPLAY, size=15)) if title else None,
        xaxis=dict(title=xtitle), yaxis=dict(title=ytitle), height=height))
    return fig


def heat_fig(z, x, y, title=None, xtitle=None, ytitle=None, height=380,
             colorscale="Viridis", colorbar_title=None):
    fig = go.Figure(go.Heatmap(
        z=z, x=x, y=y, colorscale=colorscale,
        colorbar=dict(title=colorbar_title, tickfont=dict(family=T.FONT_MONO, size=10))))
    fig.update_layout(base_layout(
        title=dict(text=title, font=dict(family=T.FONT_DISPLAY, size=15)) if title else None,
        xaxis=dict(title=xtitle), yaxis=dict(title=ytitle), height=height))
    return fig


def conditional_histograms(y, truth, levels, colors=None, title=None,
                           xtitle="Ampiezza", height=340):
    colors = colors or [T.ELECTRICAL, T.TEAL, T.AMBER, T.OPTICAL]
    fig = go.Figure()
    for level, color in zip(levels, colors):
        selected = np.isclose(truth, level)
        fig.add_trace(go.Histogram(
            x=np.asarray(y)[selected], nbinsx=80, name=f"Tx {level:+.3f}",
            marker_color=_hex_to_rgba(color, 0.55), histnorm="probability density"))
    fig.update_layout(base_layout(
        title=dict(text=title, font=dict(family=T.FONT_DISPLAY, size=15)) if title else None,
        xaxis=dict(title=xtitle), yaxis=dict(title="Densità"),
        barmode="overlay", height=height))
    return fig
