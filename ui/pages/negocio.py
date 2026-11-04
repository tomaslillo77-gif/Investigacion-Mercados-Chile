import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.components import (card_title, data_as_of, page_title, donut, legend_html, pct, pending_data, show_table,
                           style_fig)
from ui.context import Ctx
from ui.theme import ACCENT, MUTED, NEGRO, PALETTE, TEXT
from wm.business import (SIN_DET, aum_por_arquitectura, aum_por_fondo, comisiones_area, comisiones_por,
                         rentabilidad_area, rentabilidad_por)
from wm.config import load_config
from wm.display import nombres_arquitecturas

PENDING_COMISIONES = ("faltan las columnas comision_anual_clp (comisión anual del cliente) y "
                      "comision_cobrada_clp (comisión cobrada) en el Excel.")


def _stat(label: str, value: str) -> None:
    st.markdown(f"<div class='stat-label'>{label}</div><div class='stat-value'>{value}</div>", unsafe_allow_html=True)


def _rent_bar(df: pd.DataFrame, label_fn=lambda g: g, orden: list[str] | None = None) -> None:
    """Rentabilidad por grupo en barras horizontales: etiquetas legibles a la izquierda, valor al final de cada barra.
    Las barras son rojas; una pérdida va en negro."""
    d = df.assign(nombre=[label_fn(g) for g in df["grupo"]])
    if orden:
        d = d.assign(_o=d["nombre"].map({n: i for i, n in enumerate(orden)}).fillna(len(orden))).sort_values("_o")
    else:
        d = d.sort_values("rentabilidad_pct", ascending=False)
    v = d["rentabilidad_pct"]
    fig = go.Figure(go.Bar(
        x=v, y=d["nombre"], orientation="h", marker_color=[ACCENT if x >= 0 else NEGRO for x in v],
        text=[f"{x:.2f}%" for x in v], textposition="outside", cliponaxis=False, textfont=dict(color=TEXT, size=12),
        hovertemplate="%{y}<br>%{x:.2f}%<extra></extra>"))
    style_fig(fig, 70 + 34 * len(d))
    fig.update_layout(bargap=0.4, margin=dict(l=10, r=60, t=10, b=10))
    fig.update_yaxes(autorange="reversed", showgrid=False, showline=False, ticksuffix="  ")
    # sin líneas verticales; solo si hay pérdidas se marca el cero para distinguir los lados
    fig.update_xaxes(ticksuffix="%", showgrid=False, showline=False, zeroline=bool((v < 0).any()), zerolinecolor=MUTED,
                     rangemode="tozero" if (v >= 0).all() else "normal")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render(ctx: Ctx) -> None:
    view, pos, car = ctx.view, ctx.ds.posiciones, ctx.ds.carteras
    page_title("Manejo de negocio")
    data_as_of(ctx.ds.as_of)
    nombres_arq = nombres_arquitecturas()
    area = rentabilidad_area(view, pos)
    com = comisiones_area(view)

    with st.container(border=True):
        card_title("Negocio del área")
        c = st.columns([1.9, 1.3, 1.6, 1.5, 1.2])  # más ancho para el AUM: los montos no quedan pegados
        with c[0]:
            _stat("AUM total", ctx.fmt_mm(float(view["aum_clp"].sum())))
        with c[1]:
            _stat("Rentabilidad del área", pct(area[0], 2) if area else "—")
        with c[2]:
            _stat("Comisión anual (clientes)", ctx.fmt_mm(com["anual"]) if com else "—")
        with c[3]:
            _stat("Comisión cobrada", ctx.fmt_mm(com["cobrada"]) if com else "—")
        with c[4]:
            _stat("Comisión / AUM", pct(com["tasa_pct"], 2) if com and com["tasa_pct"] is not None else "—")
        notas = []
        if area:
            notas.append(f"Rentabilidad: {area[1]}, ponderada por AUM.")
        if not com:
            notas.append("— = dato no disponible en el Excel cargado.")
        if notas:
            st.markdown(f"<div class='footnote'>{' '.join(notas)}</div>", unsafe_allow_html=True)

    left, right = st.columns(2)
    with left, st.container(border=True):
        card_title("AUM por arquitectura", "% del AUM de clientes según la arquitectura de su cartera")
        arq = aum_por_arquitectura(view, nombres_arq)
        colors = [("#8fa0b8" if a == SIN_DET else PALETTE[i % len(PALETTE)]) for i, a in enumerate(arq["arquitectura"])]
        st.plotly_chart(donut(arq["arquitectura"], arq["aum"], "AUM", ctx.fmt_mm(float(arq["aum"].sum())), 260, colors,
                              hover=[ctx.fmt(a) for a in arq["aum"]]),
                        use_container_width=True, config={"displayModeBar": False})
        st.markdown(legend_html(arq["arquitectura"], [f"{ctx.fmt(a)} · {p:.1f}%" for a, p in zip(arq["aum"], arq["pct"])], colors),
                    unsafe_allow_html=True)
    fondos = aum_por_fondo(pos, car)
    with right, st.container(border=True):
        card_title("AUM por fondo", "Los 10 fondos con más AUM")
        if fondos.empty:
            st.info("No hay posiciones cargadas.")
        else:
            top = fondos.head(10).iloc[::-1]
            fig = go.Figure(go.Bar(x=ctx.mm(top["aum"]), y=top["fondo"], orientation="h", marker_color=ACCENT,
                                   customdata=[ctx.fmt(a) for a in top["aum"]],
                                   text=[ctx.fmt_mm(a) for a in top["aum"]], textposition="outside", cliponaxis=False,
                                   textfont=dict(color=TEXT, size=12),
                                   hovertemplate="%{y}<br>%{customdata}<extra></extra>"))
            style_fig(fig, 70 + 32 * len(top))
            fig.update_layout(bargap=0.4, margin=dict(l=10, r=90, t=10, b=10))
            fig.update_yaxes(showgrid=False, showline=False, ticksuffix="  ")
            fig.update_xaxes(showgrid=False, showline=False, zeroline=False, rangemode="tozero", **ctx.axis_mm())
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with st.container(border=True):
        card_title("Cuánto tenemos en cada fondo", "AUM de posiciones por fondo (serie del catálogo agrupada por fondo)")
        if fondos.empty:
            st.info("No hay posiciones cargadas.")
        else:
            show_table(pd.DataFrame({
                "Fondo": fondos["fondo"].values, "AUM": fondos["aum"].map(ctx.fmt).values,
                "% del AUM": fondos["pct"].map(lambda v: f"{v:.1f}%").values,
                "N° clientes": fondos["n_clientes"].values}).head(25),
                num_cols=("AUM", "% del AUM", "N° clientes"), total_row={
                    "Fondo": f"Total ({len(fondos)} fondos)", "AUM": ctx.fmt(float(fondos["aum"].sum())),
                    "% del AUM": "100.0%", "N° clientes": pos["rut"].nunique()})
            if len(fondos) > 25:
                st.caption(f"Mostrando 25 de {len(fondos)} fondos.")

    with st.container(border=True):
        card_title("Rentabilidades", "Rentabilidad ponderada por AUM según distintos cortes de la cartera")
        r_adv = rentabilidad_por(view, "advisor", pos)
        if r_adv is None:
            pending_data("falta rentabilidad_12m_pct en el Excel o rentabilidad no realizada en las posiciones.")
        else:
            v2 = view.assign(arq_vis=view["arquitectura"].map(lambda a: SIN_DET if pd.isna(a) else nombres_arq.get(a, a)))
            perfiles = load_config("arquitecturas")["perfiles_nombres"]
            cortes = (  # (título, rentabilidades, nombre visible, orden)
                ("Advisor", r_adv, ctx.adv_name, None),
                ("Servicio", rentabilidad_por(view[view["servicio"] != "TRA"], "servicio", pos), lambda g: g, None),  # TRA es transaccional
                ("Portafolio", rentabilidad_por(v2, "arq_vis", pos), lambda g: g, None),
                ("Perfil de riesgo", rentabilidad_por(view, "perfil_norm", pos), lambda g: perfiles.get(g, g), list(perfiles.values())),
            )
            for fila in (cortes[:2], cortes[2:]):
                for col, (titulo, r, nombre, orden) in zip(st.columns(2), fila):
                    with col:
                        st.markdown(f"<div class='chart-title'>{titulo}</div>", unsafe_allow_html=True)
                        if r is None:
                            pending_data("sin rentabilidad para este corte.")
                        else:
                            _rent_bar(r, nombre, orden)
            st.markdown(f"<div class='footnote'>{r_adv['fuente'].iloc[0]}, ponderada por AUM. "
                        "Servicio no incluye TRA. Portafolio es la arquitectura de la cartera del cliente.</div>",
                        unsafe_allow_html=True)

    with st.container(border=True):
        card_title("Ingresos por comisión", "Comisión anual esperada vs cobrada, por advisor y por servicio")
        by_adv, by_srv = comisiones_por(view, "advisor"), comisiones_por(view, "servicio")
        if by_adv is None:
            pending_data(PENDING_COMISIONES)
        else:
            c1, c2 = st.columns(2)
            for col, df, titulo, fn in ((c1, by_adv, "Advisor", ctx.adv_name), (c2, by_srv, "Servicio", lambda x: x)):
                with col:
                    show_table(pd.DataFrame({
                        titulo: df["grupo"].map(fn).values,
                        "Comisión anual": df["comision_anual"].map(ctx.fmt).values,
                        "Cobrada": df["comision_cobrada"].map(ctx.fmt).values,
                        "% cobrado": df["pct_cobrado"].map(lambda v: pct(v, 0)).values,
                        "Comisión / AUM": df["tasa_pct"].map(lambda v: pct(v, 2)).values}),
                        num_cols=("Comisión anual", "Cobrada", "% cobrado", "Comisión / AUM"), link_col=titulo)

    with st.container(border=True):
        card_title("Comisiones por cliente", "Los 15 clientes con mayor comisión anual")
        if com is None:
            pending_data(PENDING_COMISIONES)
        else:
            top = view.sort_values("comision_anual_clp", ascending=False).head(15)
            tasa = (top["comision_anual_clp"] / top["aum_clp"] * 100).where(top["aum_clp"] > 0)
            show_table(pd.DataFrame({
                "Cliente": top["cliente_label"].values, "Servicio": top["servicio"].values,
                "AUM": top["aum_clp"].map(ctx.fmt).values,
                "Comisión anual": top["comision_anual_clp"].map(ctx.fmt).values,
                "Cobrada": top["comision_cobrada_clp"].map(ctx.fmt).values,
                "Comisión / AUM": tasa.map(lambda v: pct(v, 2)).values}),
                num_cols=("AUM", "Comisión anual", "Cobrada", "Comisión / AUM"), link_col="Cliente")
