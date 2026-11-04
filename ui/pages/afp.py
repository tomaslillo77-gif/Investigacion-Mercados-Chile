from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.components import Raw, card_title, page_title, show_table, style_fig
from ui.context import NAV_EVOLUCION, Ctx
from ui.theme import ACCENT, GRIS, PALETTE
from wm.afp.fuente import FONDOS
from wm.afp.indice import indice_de_foto, patrimonio_total, rent_anual, resumen
from wm.afp.snapshots import Foto, cargar_foto
from wm.config import load_config

RAIZ = Path(__file__).resolve().parent.parent.parent
RANGOS = {"1A": 1, "3A": 3, "5A": 5, "10A": None}
RENTAB = {"rent_1m": "1M", "rent_3m": "3M", "rent_ytd": "YTD", "rent_1a": "1A", "rent_3a": "3A (anual)", "rent_5a": "5A (anual)"}


def _ruta() -> Path:
    return RAIZ / load_config("afp")["snapshots_dir"]


def _pct(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v * 100:.2f}%"


def _sin_foto() -> None:
    with st.container(border=True):
        card_title("Sin datos de AFP cargados", "El módulo se alimenta del repositorio collabmarket/data_afp (Superintendencia de Pensiones)")
        st.markdown("1. Corre `python scripts/actualizar_afp.py`.\n2. Recarga esta página.")


def _sello(foto: Foto) -> None:
    st.markdown(f"<div class='footnote'>Datos al {foto.fecha_corte.isoformat()}. Fuente: repositorio collabmarket/data_afp "
                "(Superintendencia de Pensiones). Rentabilidad nominal en pesos.</div>", unsafe_allow_html=True)


def _mejor(df: pd.DataFrame, col: str) -> str | None:
    s = df[col].dropna()
    return None if s.empty else df.loc[s.idxmax(), "fondo"]


def _tabla(foto: Foto) -> None:
    r = resumen(foto)
    mejores = {c: _mejor(r, c) for c in RENTAB}
    filas = []
    for _, x in r.iterrows():
        fila = {"Fondo": f"Fondo {x['fondo']}"}
        for c, nombre in RENTAB.items():
            txt = _pct(x[c])
            fila[nombre] = Raw(f"<b>{txt}</b>") if mejores[c] == x["fondo"] else txt
        fila["Patrimonio (MM$)"] = f"{x['patrimonio'] / 1e6:,.0f}"
        fila["Peso en el sistema"] = _pct(x["peso_sistema"])
        fila["AFP"] = int(x["n_afp"])
        filas.append(fila)
    df = pd.DataFrame(filas)
    show_table(df, num_cols=[c for c in df.columns if c != "Fondo"])


def _grafico_indices(foto: Foto) -> None:
    rango = st.radio("Rango", list(RANGOS), horizontal=True, key="afp_rango", index=1)
    fig = go.Figure()
    for i, f in enumerate(FONDOS):
        idx = indice_de_foto(foto, f)
        if RANGOS[rango]:
            idx = idx[idx.index >= idx.index[-1] - pd.DateOffset(years=RANGOS[rango])]
        idx = idx / idx.iloc[0] * 100
        fig.add_trace(go.Scatter(x=idx.index, y=idx.values, name=f"Fondo {f}", mode="lines",
                                 line=dict(color=PALETTE[i], width=2), hovertemplate="%{y:.1f}<extra>Fondo " + f + "</extra>"))
    style_fig(fig, 340, legend=True)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key="afp_graf_indices")


def _indices(foto: Foto) -> None:
    with st.container(border=True):
        card_title("Rentabilidad por fondo", "Índice de todas las AFP del fondo, ponderado por su patrimonio. Desde 3 años, anualizada. En negrita, la mejor de cada plazo")
        _tabla(foto)
    with st.container(border=True):
        card_title("Índices de AFP por fondo", "Base 100 al inicio del rango elegido")
        _grafico_indices(foto)


def _rango_con_holgura(vals, holgura: float = 0.18) -> list[float]:
    """Eje Y que deja espacio sobre la barra más alta (y bajo la más negativa) para que su etiqueta no se corte."""
    bajo, alto = min(0.0, float(min(vals))), max(0.0, float(max(vals)))
    margen = ((alto - bajo) or 1.0) * holgura
    return [bajo - margen if bajo < 0 else 0.0, alto + margen]


def _evolucion(foto: Foto) -> None:
    fondo = st.radio("Fondo", FONDOS, horizontal=True, key="afp_fondo", format_func=lambda f: f"Fondo {f}")
    pat = patrimonio_total(foto, fondo)
    with st.container(border=True):
        card_title(f"Patrimonio total del Fondo {fondo}", "Suma de todas las AFP, en miles de millones de pesos")
        fig = go.Figure(go.Scatter(x=pat.index, y=pat.values / 1e9, mode="lines", line=dict(color=ACCENT, width=2),
                                   fill="tozeroy", fillcolor="rgba(236,17,26,0.08)",
                                   hovertemplate="$%{y:,.0f} mil MM<extra></extra>"))
        style_fig(fig, 300)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key="afp_graf_patrimonio")
    anual = rent_anual(indice_de_foto(foto, fondo))
    with st.container(border=True):
        card_title(f"Rentabilidad por año calendario del Fondo {fondo}", "Índice ponderado, nominal en pesos. El año en curso llega hasta la fecha de los datos")
        actual = foto.fecha_corte.year
        etiquetas = [f"{a} (a la fecha)" if a == actual else str(a) for a in anual.index]
        vals = anual.values * 100
        fig = go.Figure(go.Bar(x=etiquetas, y=vals, marker_color=[ACCENT if v >= 0 else GRIS for v in vals], text=[_pct(v) for v in anual.values],
                               textposition="outside", cliponaxis=False, hovertemplate="%{y:.2f}%<extra></extra>"))
        style_fig(fig, 300)
        fig.update_yaxes(ticksuffix="%", range=_rango_con_holgura(vals))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key="afp_graf_anual")


def render(ctx: Ctx) -> None:
    page_title("AFP")
    foto = cargar_foto(_ruta())
    if foto is None:
        _sin_foto()
        return
    _sello(foto)
    (_evolucion if ctx.page == NAV_EVOLUCION else _indices)(foto)
