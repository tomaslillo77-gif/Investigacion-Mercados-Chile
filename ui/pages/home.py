import streamlit as st

from ui.components import card_title, chips, page_header, safe, data_as_of, donut, legend_html, money, pct, show_table
from ui.context import NAV_FICHA, Ctx
from wm.config import load_config
from wm.display import nombres_arquitecturas
from wm.metrics import kpis_advisor, mix_por, mix_servicio
from wm.portafolio_cliente import contar_estados


def _open(rut: str) -> None:
    st.session_state["cliente_sel"] = rut
    st.session_state["nav"] = NAV_FICHA


def _stat(label: str, value: str) -> None:
    st.markdown(f"<div class='stat-label'>{label}</div><div class='stat-value'>{value}</div>",
                unsafe_allow_html=True)


def render(ctx: Ctx) -> None:
    mine = ctx.mine()
    page_header(f"<div class='hello'>Hola,</div><div class='hello-name'>{safe(ctx.adv_name(ctx.advisor) if ctx.advisor else 'equipo')}</div>")
    data_as_of(ctx.ds.as_of)
    if mine.empty:
        st.info("Este advisor no tiene clientes en los datos cargados.")
        return

    k = kpis_advisor(mine, ctx.hoy)
    with st.container(border=True):
        card_title("Mi cartera")
        cols = st.columns([1.9, 1, 1.5, 1.3, 1.5, 1.5])
        with cols[0]:
            _stat("AUM total", ctx.fmt_mm(k["aum"]))
        with cols[1]:
            _stat("Clientes", f"{k['n_clientes']:,}")
        with cols[2]:
            _stat("Share of wallet promedio", pct(k["sow_promedio"], 0) if k["sow_promedio"] is not None else "—")
        with cols[3]:
            _stat("Con wealth plan", pct(k["pct_wealth_plan"], 0) if k["pct_wealth_plan"] is not None else "—")
        with cols[4]:
            _stat("Contactados en 90 días", pct(k["pct_contactados_90d"], 0))
        with cols[5]:
            e = contar_estados(mine)
            _stat("Con portafolio definido", pct(e["pct_con_portafolio"], 0) if ctx.store_ok else "—")
        if k["sow_promedio"] is None or k["pct_wealth_plan"] is None:
            st.markdown("<div class='footnote'>— = dato no disponible en el Excel cargado.</div>", unsafe_allow_html=True)

    cfg = load_config("arquitecturas")
    perfiles = list(cfg["perfiles_nombres"].values())
    distribuciones = (
        ("Servicio", mix_servicio(mine).rename(columns={"servicio": "grupo"})),
        ("Perfil", mix_por(mine, "perfil_norm", cfg["perfiles_nombres"], perfiles)),
        ("Arquitectura", mix_por(mine, "arquitectura", nombres_arquitecturas())),
    )
    with st.container(border=True):
        card_title("Distribución")
        for col, (titulo, mix) in zip(st.columns(3), distribuciones):
            with col:
                st.markdown(f"**{titulo}**")
                st.plotly_chart(donut(mix["grupo"], mix["aum"], "AUM", ctx.fmt_mm(k["aum"]), 260,
                                      hover=[ctx.fmt(a) for a in mix["aum"]]),
                                use_container_width=True, config={"displayModeBar": False})
                st.markdown(legend_html(mix["grupo"], [f"{ctx.fmt(a)} · {n}" for a, n in zip(mix["aum"], mix["n_clientes"])]),
                            unsafe_allow_html=True)

    with st.container(border=True):
        card_title("Cola de atención", "Clientes con mayor prioridad: tamaño, riesgo de fuga, ingresos en juego y oportunidad")
        top = mine.sort_values("prioridad", ascending=False).head(10)
        table = top.assign(
            Cliente=top["cliente_label"],
            Servicio=top["servicio"],
            AUM=top["aum_clp"].map(ctx.fmt),
            Prioridad=top["prioridad"].map(lambda v: f"{v:.0f}"),
            Motivos=top["motivos"].map(chips),
        )[["Cliente", "Servicio", "AUM", "Prioridad", "Motivos"]]
        show_table(table, num_cols=("AUM", "Prioridad"), link_col="Cliente")
        pick = st.selectbox("Abrir ficha de", top["rut"], key="home_pick",
                            format_func=lambda r: top.set_index("rut").loc[r, "cliente_label"])
        st.button("Abrir ficha", key="home_open", on_click=_open, args=(pick,))
