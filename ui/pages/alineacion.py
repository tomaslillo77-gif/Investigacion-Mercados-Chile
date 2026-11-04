import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.components import badge, card_title, page_title, pending_data, show_table, style_fig
from ui.context import Ctx
from ui.rebalance_view import show_plan
from ui.theme import ACCENT, GRIS, MUTED, TEXT
from wm.alignment import desvio_detalle, ranking
from wm.portafolio_cliente import cfg
from wm.exposure import client_exposure, has_breakdown, model_exposure, perfil_de
from wm.rebalance import plan_rebalanceo


def _desvio_badge(v: float):
    """Verde dentro del límite de desvío (3 pp, config/perfiles_bandas.yaml), amarillo hasta el doble, rojo más allá."""
    lim = cfg()["desvio_max_pp"]
    kind = "bad" if abs(v) >= 2 * lim else "warn" if abs(v) > lim else "ok"
    return badge(f"{v:+.1f} pp", kind)


SANGRIA = "\u00a0" * 5


def _etiqueta(f: dict) -> str:
    if f["nivel"] in (0, "titulo"):
        return f"<b>{f['label']}</b>"
    return SANGRIA * (1 if f["nivel"] == 1 else 2) + f["label"]


def _desvio_fig(filas: list[dict]) -> go.Figure:
    """Barras horizontales que parten del 0 al centro: sobre el modelo hacia la derecha (rojo), bajo el modelo hacia
    los nombres (gris). Cada clase de activo con sus subactivos debajo; las filas 'titulo' no llevan barra."""
    etiquetas = [_etiqueta(f) for f in filas]
    valores = [f.get("desvio") for f in filas]
    hover = ["" if f["nivel"] == "titulo" else f"{f['label']}<br>Cliente {f['cliente']:.1f}% · Modelo {f['modelo']:.1f}%"
             f"<br>Desvío {f['desvio']:+.1f} pp" for f in filas]
    fig = go.Figure()
    for nombre, color, ok in (("Sobre el modelo", ACCENT, lambda v: v >= 0), ("Bajo el modelo", GRIS, lambda v: v < 0)):
        x = [v if v is not None and ok(v) else None for v in valores]
        fig.add_bar(x=x, y=etiquetas, orientation="h", name=nombre, marker_color=color, customdata=hover,
                    text=[f"{v:+.1f}" if v is not None and ok(v) else "" for v in valores], textposition="outside",
                    cliponaxis=False, textfont=dict(color=TEXT, size=12), hovertemplate="%{customdata}<extra></extra>")
    tope = max([abs(v) for v in valores if v is not None] + [2.0]) * 1.3
    style_fig(fig, 90 + 30 * len(filas), True)
    fig.update_layout(barmode="overlay", bargap=0.35, margin=dict(l=10, r=20, t=10, b=50),
                      legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.04, yanchor="top"))
    fig.update_yaxes(autorange="reversed", showgrid=False, showline=False, ticksuffix="  ")
    fig.update_xaxes(range=[-tope, tope], showgrid=False, showline=False, zeroline=True, zerolinecolor=MUTED,
                     ticksuffix=" pp", tickformat="+.0f")
    return fig


def render(ctx: Ctx) -> None:
    page_title("Alineación al modelo")
    mine = ctx.mine()
    r = ranking(mine, ctx.ds)
    if r is None or r.empty:
        pending_data("hace falta la columna desvio_modelo_pct en el Excel o el desglose por fondo en la hoja de carteras.")
        return

    with st.container(border=True):
        card_title("Desvío vs modelo", "Ordenado por el mayor desvío absoluto (puntos porcentuales)")
        t = pd.DataFrame({
            "Cliente": r["rut"].map(mine.set_index("rut")["cliente_label"]).values,
            "Advisor": r["advisor"].map(ctx.adv_name).values,
            "AUM": r["aum_clp"].map(ctx.fmt).values, "Desvío": [_desvio_badge(v) for v in r["desvio_pp"]],
            "Clase": r["clase"].values, "Fuente": r["fuente"].values})
        show_table(t.head(25), num_cols=("AUM", "Desvío"), link_col="Cliente")
        if len(t) > 25:
            st.caption(f"Mostrando 25 de {len(t)} clientes.")

    with st.container(border=True):
        card_title("Detalle por fondo", "Qué comprar y vender para llevar la cartera del cliente a su modelo")
        by = mine.set_index("rut")
        rut = st.selectbox("Cliente", r["rut"].head(100), key="alin_pick",
                           format_func=lambda x: by.loc[x, "cliente_label"])
        row = by.loc[rut]
        pos = ctx.ds.posiciones[ctx.ds.posiciones["rut"] == rut]
        arq = row["arquitectura"] if pd.notna(row["arquitectura"]) else None
        perfil = perfil_de(ctx.ds.carteras, row.get("perfil_norm"), arq)
        plan = plan_rebalanceo(pos, ctx.ds.carteras, arq, perfil, base_clp=float(row["aum_clp"]))
        if plan is None:
            pending_data("para este cliente la arquitectura o el perfil no están determinados, así que no hay cartera modelo contra la cual comparar.")
            return
        show_plan(plan, ctx.fmt)
        if has_breakdown(ctx.ds.carteras) and not pos.empty:
            filas = desvio_detalle(client_exposure(pos, ctx.ds.carteras), model_exposure(ctx.ds.carteras, arq, perfil))
            if filas:
                st.markdown("<div class='chart-title'>Desvío por clase de activo</div>", unsafe_allow_html=True)
                st.plotly_chart(_desvio_fig(filas), use_container_width=True, config={"displayModeBar": False})
                st.markdown("<div class='footnote'>Cliente menos modelo, en puntos porcentuales de la cartera. Moneda y % UF de la "
                            "renta fija local se comparan a nivel consolidado con el objetivo del perfil.</div>",
                            unsafe_allow_html=True)
