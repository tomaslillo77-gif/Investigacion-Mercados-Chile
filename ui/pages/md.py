import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.components import (badge, card_title, data_as_of, donut, legend_html, page_title, pct, pending_data, show_table,
                           style_fig)
from ui.context import Ctx
from ui.theme import ACCENT, BORDER, SERIE_1, SERIE_2
from wm.asignacion import PENDIENTE, cambios, excel_reasignaciones
from wm.metrics import comparar_advisors, flujos_netos, kpis_advisor, mix_servicio
from wm.portafolio_cliente import DEFINIDO, contar_estados
from wm.priority import dias_sin_contacto


def _stat(label: str, value: str) -> None:
    st.markdown(f"<div class='stat-label'>{label}</div><div class='stat-value'>{value}</div>", unsafe_allow_html=True)


def _dash(v, decimals: int = 0) -> str:
    return "—" if v is None or pd.isna(v) else pct(v, decimals)


def _flujos_fig(f: pd.DataFrame, ctx: Ctx) -> go.Figure:
    """Aportes y retiros (en negativo) por período, en barras, con el neto en línea."""
    x = pd.to_datetime(f["periodo"], errors="coerce")
    x = x if x.notna().all() else f["periodo"]  # períodos que no son fechas: se dejan como categorías
    fig = go.Figure()
    # los ejes van en millones de la moneda elegida; el tooltip muestra el monto completo en esa moneda
    for name, v in (("Aportes", f["aportes"]), ("Retiros", -f["retiros"]), ("Neto", f["neto"])):
        trace = dict(x=x, y=ctx.mm(v), name=name, customdata=[ctx.fmt(a) for a in v],
                     hovertemplate=f"{name}: %{{customdata}}<extra></extra>")
        if name == "Neto":
            fig.add_scatter(mode="lines+markers", line=dict(color=SERIE_2), **trace)
        else:
            fig.add_bar(marker_color=SERIE_1 if name == "Aportes" else ACCENT, **trace)
    fig.update_yaxes(**ctx.axis_mm())
    fig.update_layout(barmode="relative")
    if x is not f["periodo"]:
        fig.update_xaxes(tickformat="%d %b %y")
    # style_fig fija la leyenda; después se centra y se baja un poco bajo el gráfico
    return style_fig(fig, 320, True).update_layout(legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.3, yanchor="top"))


def _equipo(ctx: Ctx) -> None:
    view = ctx.view
    page_title("Resumen del equipo")
    data_as_of(ctx.ds.as_of)
    k = kpis_advisor(view, ctx.hoy)
    with st.container(border=True):
        card_title("Negocio consolidado")
        cols = st.columns([1.9, 1, 1, 1.5, 1.3, 1.5])
        with cols[0]:
            _stat("AUM total", ctx.fmt_mm(k["aum"]))
        with cols[1]:
            _stat("Clientes", f"{k['n_clientes']:,}")
        with cols[2]:
            _stat("Advisors", f"{view['advisor'].nunique()}")
        with cols[3]:
            _stat("Contactados en 90 días", _dash(k["pct_contactados_90d"]))
        with cols[4]:
            _stat("Con series malas", _dash(view["serie_mala"].mean() * 100))
        with cols[5]:
            _stat("Con portafolio definido", _dash(contar_estados(view)["pct_con_portafolio"]) if ctx.store_ok else "—")

    left, right = st.columns(2)
    with left, st.container(border=True):
        card_title("Aportes y retiros netos por período")
        if flujos_netos(view, ctx.ds.flujos) is None:
            pending_data("faltan las columnas aportes_periodo y retiros_periodo en el Excel.")
        else:
            chart = st.container()
            advisors = sorted(view["advisor"].dropna().unique())
            sel = st.multiselect("Advisors", advisors, key="flujos_advisors", format_func=ctx.adv_name,
                                 placeholder="Todos los advisors", label_visibility="collapsed")
            sub = view[view["advisor"].isin(sel)] if sel else view  # sin selección = todos; varios = su combinación
            f = flujos_netos(sub, ctx.ds.flujos)
            with chart:
                st.plotly_chart(_flujos_fig(f, ctx), use_container_width=True, config={"displayModeBar": False})
    with right, st.container(border=True):
        card_title("Mix de servicios consolidado")
        mix = mix_servicio(view)
        st.plotly_chart(donut(mix["servicio"], mix["aum"], "AUM", ctx.fmt_mm(k["aum"]), 260,
                              hover=[ctx.fmt(a) for a in mix["aum"]]),
                        use_container_width=True, config={"displayModeBar": False})
        st.markdown(legend_html(mix["servicio"], [f"{ctx.fmt(a)} · {n}" for a, n in zip(mix["aum"], mix["n_clientes"])]),
                    unsafe_allow_html=True)

    with st.container(border=True):
        card_title("Comparación de advisors")
        comp = comparar_advisors(view, ctx.hoy).sort_values("aum", ascending=False)
        show_table(pd.DataFrame({
            "Advisor": comp["advisor"].map(ctx.adv_name).values, "AUM": comp["aum"].map(ctx.fmt).values,
            "Clientes": comp["n_clientes"].values, "% con wealth plan": comp["pct_wealth_plan"].map(_dash).values,
            "% contactados 90d": comp["pct_contactados_90d"].map(_dash).values,
            "% series malas": comp["pct_series_malas"].map(_dash).values,
        }), num_cols=("AUM", "Clientes", "% con wealth plan", "% contactados 90d", "% series malas"), link_col="Advisor")

    with st.container(border=True):
        card_title("Alertas del equipo", "Cantidad de clientes por advisor que requieren atención")
        d = dias_sin_contacto(view, ctx.hoy)
        al = view.assign(sin_contacto=d.isna() | (d > 90))
        rows = []
        for adv, g in al.groupby("advisor"):
            sc, sm = int(g["sin_contacto"].sum()), int(g["serie_mala"].sum())
            dv = int((g["desvio_modelo_pct"].abs() >= 10).sum()) if "desvio_modelo_pct" in g.columns else None
            pf = int((g["portafolio_estado"] != DEFINIDO).sum()) if "portafolio_estado" in g.columns and ctx.store_ok else None
            rows.append({"Advisor": ctx.adv_name(adv), "Sin contacto > 90 días": badge(sc, "warn" if sc else "ok"),
                         "Series malas": badge(sm, "bad" if sm else "ok"),
                         "Portafolio por definir o revisar": badge(pf, "warn" if pf else "ok") if pf is not None else "—",
                         "Desvío ≥ 10 pp": badge(dv, "warn" if dv else "ok") if dv is not None else "—"})
        show_table(pd.DataFrame(rows).sort_values("Advisor"), link_col="Advisor")


def reasignaciones(ctx: Ctx) -> None:
    """Cambios de advisor hechos desde el portal y su estado frente al Excel; la hoja «Pendientes» es lo que hay que cambiar en la fuente."""
    with st.container(border=True):
        card_title("Reasignaciones de clientes", "Se hacen desde la Ficha del cliente; el Excel debe reflejarlas")
        if not ctx.store_ok:
            st.markdown("<div class='footnote'>Base de datos no disponible: no hay reasignaciones que mostrar.</div>", unsafe_allow_html=True)
            return
        c = cambios(ctx.view, ctx.store.asignaciones_vigentes(), ctx.adv_name)
        if c.empty:
            st.markdown("<div class='footnote'>Todavía no se ha reasignado ningún cliente.</div>", unsafe_allow_html=True)
            return
        pend = int((c["Estado"] == PENDIENTE).sum())
        st.markdown(badge(f"{pend} pendiente(s) en el Excel", "warn" if pend else "ok") + f" <span class='footnote'>de {len(c)} reasignaciones</span>", unsafe_allow_html=True)
        show_table(c.drop(columns=["RUT"]))
        st.download_button("Descargar para actualizar el Excel", excel_reasignaciones(c, ctx.store.historial_asignaciones().assign(
            advisor=lambda d: d["advisor"].map(ctx.adv_name), advisor_excel=lambda d: d["advisor_excel"].map(ctx.adv_name))),
            "Reasignaciones.xlsx", key="asig_excel", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", disabled=pend == 0)


def render(ctx: Ctx) -> None:
    _equipo(ctx)
    reasignaciones(ctx)
