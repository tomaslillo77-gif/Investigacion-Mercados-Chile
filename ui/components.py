import html
import math
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.theme import BG, BORDER, CARD, MUTED, PALETTE, TEXT

# pandas 3 infiere dtype str y pierde la subclase Raw de las celdas; con object se mantiene el HTML sin escapar.
pd.options.future.infer_string = False


class Raw(str):
    """Fragmento HTML ya confiable; html_table lo deja sin escapar."""


def safe(text) -> str:
    """Texto de usuario/Excel seguro para st.markdown(unsafe_allow_html=True): escapa HTML y '$' (LaTeX)."""
    return html.escape(str(text)).replace("$", "&#36;").replace("\n", "<br>")


MONEDAS_MM = {"USD": "US$", "CAD": "CA$"}  # monedas extranjeras: se muestran en millones


def money(v, moneda: str = "CLP") -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    if v < 0:  # el signo va antes del símbolo: -$2,462,394, no $-2,462,394
        return "-" + money(-v, moneda)
    if moneda in MONEDAS_MM:
        return f"{MONEDAS_MM[moneda]}{v / 1e6:,.2f} MM"
    return f"${v:,.0f}"


def money_mm(v) -> str:
    """Monto en millones de pesos (lectura de gerencia): $1,617 MM."""
    return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else f"${v / 1e6:,.0f} MM"


def pct(v, decimals: int = 1) -> str:
    return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.{decimals}f}%"


def badge(text: str, kind: str = "muted") -> Raw:
    return Raw(f"<span class='badge badge-{kind}'>{html.escape(str(text))}</span>")


def chips(texts: list[str]) -> Raw:
    return Raw("".join(f"<span class='chip'>{html.escape(t)}</span>" for t in texts))


def style_fig(fig: go.Figure, height: int = 300, legend: bool = False) -> go.Figure:
    fig.update_layout(
        height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=MUTED, size=12), margin=dict(l=10, r=10, t=10, b=10),
        showlegend=legend, legend=dict(font=dict(color=TEXT), orientation="h", y=-0.15),
        hoverlabel=dict(bgcolor=BG, font_color=TEXT),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=BORDER)
    fig.update_yaxes(gridcolor=BORDER, gridwidth=1, zeroline=False)
    return fig


def donut(labels, values, center_title: str, center_value: str, height: int = 300, colors=None,
          hover=None) -> go.Figure:
    """`hover`: textos ya formateados (monto en la moneda elegida) para el tooltip; sin él se muestra el valor tal cual."""
    shown = "%{customdata}" if hover is not None else "%{value:,.1f}"
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.72, sort=False, customdata=list(hover) if hover is not None else None,
        marker=dict(colors=(colors or PALETTE)[:len(labels)], line=dict(color=CARD, width=3)),
        textinfo="none", hovertemplate=f"%{{label}}<br>{shown} (%{{percent}})<extra></extra>"))
    fig.add_annotation(text=f"<span style='font-size:11px;color:{MUTED}'>{html.escape(center_title)}</span><br>"
                            f"<b style='font-size:18px;color:{TEXT}'>{html.escape(center_value)}</b>",
                       showarrow=False, x=0.5, y=0.5)
    return style_fig(fig, height)


def legend_html(labels, texts, colors=None, subs: dict | None = None) -> str:
    """Filas de leyenda con punto de color. `subs` mapea una etiqueta a [(subactivo, texto)]: filas sin color, sangradas."""
    colors = colors or PALETTE
    out = []
    for i, (l, t) in enumerate(zip(labels, texts)):
        out.append(f"<div class='legend-row'><span><span class='dot' style='background:{colors[i % len(colors)]}'></span>"
                   f"{html.escape(str(l))}</span><span>{html.escape(str(t))}</span></div>")
        for name, text in (subs or {}).get(l, []):
            out.append(f"<div class='legend-row legend-sub'><span>{html.escape(str(name))}</span>"
                       f"<span>{html.escape(str(text))}</span></div>")
    return "".join(out)


def card_title(text: str, subtitle: str | None = None) -> None:
    st.markdown(f"<div class='card-title'>{html.escape(text)}</div>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f"<div class='footnote'>{html.escape(subtitle)}</div>", unsafe_allow_html=True)


def page_header(left_html: str) -> None:
    """Fila de encabezado de cada página: el título a la izquierda y el inicio de sesión arriba a la derecha."""
    left, right = st.columns([5, 2], vertical_alignment="center")
    with left:
        st.markdown(left_html, unsafe_allow_html=True)
    with right:
        slot = st.session_state.get("_login_slot")
        if slot:
            slot()


def page_title(text: str) -> None:
    page_header(f"<div class='page-title'>{html.escape(text)}</div><div class='page-rule'></div>")


def callout(kind: str, text: str) -> None:
    st.markdown(f"<div class='callout {kind}'>{html.escape(text)}</div>", unsafe_allow_html=True)


def pending_data(msg: str) -> None:
    st.markdown(f"<div class='pending'>Pendiente de datos · {html.escape(msg)}</div>", unsafe_allow_html=True)


def data_as_of(ts: datetime) -> None:
    st.markdown(f"<div class='footnote'>Datos al {ts:%d-%m-%Y %H:%M}</div>", unsafe_allow_html=True)


def _cell(v) -> str:
    if isinstance(v, Raw):
        return str(v)
    return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else html.escape(str(v))


def html_table(df: pd.DataFrame, num_cols=(), link_col: str | None = None, total_row: dict | None = None,
               total_position: str = "top", row_classes: list | None = None) -> str:
    head = "".join(f"<th class='{'num' if c in num_cols else ''}'>{html.escape(str(c))}</th>" for c in df.columns)
    body = ""
    total_html = ""
    if total_row:
        cells = "".join(f"<td class='{'num' if c in num_cols else ''}'>{_cell(total_row.get(c, ''))}</td>"
                        for c in df.columns)
        total_html = f"<tr class='total'>{cells}</tr>"
    if total_position != "bottom":
        body += total_html
    for i, (_, row) in enumerate(df.iterrows()):
        cells = "".join(
            f"<td class='{'num' if c in num_cols else ('link' if c == link_col else '')}'>{_cell(row[c])}</td>"
            for c in df.columns)
        clase = row_classes[i] if row_classes and row_classes[i] else None  # p. ej. 'clase': fila de encabezado de grupo
        body += f"<tr class='{clase}'>{cells}</tr>" if clase else f"<tr>{cells}</tr>"
    if total_position == "bottom":
        body += total_html
    return f"<table class='dtable'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def show_table(df: pd.DataFrame, **kw) -> None:
    st.markdown(html_table(df, **kw), unsafe_allow_html=True)
