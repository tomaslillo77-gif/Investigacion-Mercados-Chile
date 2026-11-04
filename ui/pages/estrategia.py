from pathlib import Path

import pandas as pd
import streamlit as st

import plotly.graph_objects as go

from ui.components import Raw, card_title, donut, legend_html, page_title, show_table, style_fig
from ui.context import NAV_COMPARADOR, NAV_HISTORIAL, Ctx
from ui.theme import ACCENT, GRIS, NEGRO, PALETTE, SERIE_2, TEXT
from wm.config import load_config
from wm.mercado import equivalencias as eq
from wm.mercado.carteras import cobertura, composicion_cartera, exposicion, ponderado
from wm.mercado.portafolios import ARQUITECTURAS, armar, exposiciones_cartera
from wm.mercado.internacionales import cargar_yahoo
from wm.mercado.historial import cambio_entre_fotos, serie_patrimonio
from wm.mercado.schema import Foto
from wm.mercado.screener import comparar, composicion_fondo, fmt_pct, universo_cmf
from wm.mercado.snapshots import cargar_foto, listar_fotos

RAIZ = Path(__file__).resolve().parent.parent.parent
MAX_FILAS = 200


def _rutas() -> tuple[Path, Path]:
    cfg = load_config("mercado")
    return RAIZ / cfg["snapshots_dir"], RAIZ / cfg["equivalencias"]


def _ruta_yahoo() -> Path:
    return RAIZ / load_config("mercado")["externos_dir"] / "yahoo"


def _num(v, dec: int = 0) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.{dec}f}"


def _sin_foto() -> None:
    with st.container(border=True):
        card_title("Sin datos de mercado cargados", "El screener se alimenta de los 4 Excel del Portal de Fondos Mutuos de la CMF")
        st.markdown(
            "1. Descarga los 4 Excel (rentabilidades, costos, tendencias y carteras) y déjalos en `data/cmf/`.\n"
            "2. Corre `python scripts/actualizar_mercado.py`.\n"
            "3. Recarga esta página.")


def _sello(foto: Foto) -> None:
    st.markdown(f"<div class='footnote'>CMF, datos al {foto.fecha_corte.isoformat()}. Los 4 archivos comparten esa fecha de corte.</div>",
                unsafe_allow_html=True)


def _pct0(v) -> str:
    return "—" if v is None or pd.isna(v) or abs(v) < 0.005 else f"{v * 100:.0f}%"


def _internacionales() -> None:
    cargado = cargar_yahoo(_ruta_yahoo())
    if cargado is None:
        st.info("Todavía no hay datos de Yahoo Finance. Corre `python scripts/actualizar_mercado.py --fuente yahoo` y "
                "recarga esta página.")
        return
    fecha, d = cargado
    st.markdown(f"<div class='footnote'>Yahoo Finance, datos al {fecha.isoformat()}.</div>", unsafe_allow_html=True)
    d = d.sort_values("instrumento")
    show_table(pd.DataFrame({
        "Fondo": d["instrumento"].values, "ISIN": d["isin"].values, "Ticker": d["ticker"].fillna("—").values,
        "Moneda": d["moneda"].fillna("—").values, "Costo (TER)": d["costo"].map(fmt_pct).values,
        "Rent. YTD": d["rent_ytd"].map(fmt_pct).values, "Rent. 1A": d["rent_1a"].map(fmt_pct).values,
        "Rent. 3A anual": d["rent_3a"].map(fmt_pct).values, "Estado": d["estado"].values}),
        num_cols=("ISIN", "Ticker", "Moneda", "Costo (TER)", "Rent. YTD", "Rent. 1A", "Rent. 3A anual", "Estado"))
    n_ok = int((d["estado"] == "Yahoo").sum())
    st.markdown(
        f"<div class='footnote'>{n_ok} de {len(d)} fondos internacionales con datos. Rentabilidades calculadas con el precio de "
        "cierre ajustado por dividendos que entrega Yahoo, en la moneda de cotización del instrumento (no en pesos); la de "
        "3 años es anualizada. El costo (TER) solo viene para ETFs; los fondos mutuos no lo traen. «Sin ticker» y «Sin datos "
        "suficientes» se corrigen escribiendo el ticker en <code>config/equivalencias_fondos.csv</code> (columna "
        "<code>ticker_yahoo</code>). Yahoo es una fuente no oficial: puede cambiar o bloquear sin aviso.</div>",
        unsafe_allow_html=True)


def _universo(foto: Foto) -> None:
    u = universo_cmf(foto)
    c1, c2 = st.columns(2)
    fam = c1.selectbox("Familia", ["Todas"] + sorted(u["familia"].dropna().unique()), key="est_fam")
    agf = c2.selectbox("Administradora", ["Todas"] + sorted(u["nombre_agf"].dropna().unique()), key="est_agf")
    if fam != "Todas":
        u = u[u["familia"] == fam]
    if agf != "Todas":
        u = u[u["nombre_agf"] == agf]
    top = u.head(MAX_FILAS)
    show_table(pd.DataFrame({
        "Fondo": top["nombre_fondo"].values, "Serie": top["fm_serie"].values, "Administradora": top["nombre_agf"].values,
        "Familia": top["familia"].values, "Rent. 1A": top["rent_1a"].map(fmt_pct).values,
        "Rent. 3A": top["rent_3a"].map(fmt_pct).values, "TAC": top["tac"].map(fmt_pct).values,
        "Patrimonio": top["patrimonio"].map(_num).values}),
        num_cols=("Serie", "Rent. 1A", "Rent. 3A", "TAC", "Patrimonio"))
    st.caption(f"Mostrando {len(top)} de {len(u)} series, ordenadas por patrimonio.")


def _stat(label: str, value: str) -> None:
    st.markdown(f"<div class='stat-label'>{label}</div><div class='stat-value'>{value}</div>", unsafe_allow_html=True)


def _espacio() -> None:
    st.markdown("<div class='espacio'></div>", unsafe_allow_html=True)


def _rentabilidades(c: pd.DataFrame, fuente: str) -> None:
    """Indicadores y tabla de rentabilidades y costos por clase de activo y subactivo, con las filas de clase en rojo."""
    usd = fuente == "Yahoo"
    serie = "Ticker" if usd else "Serie"
    costo = "Costo (TER)" if usd else ("Costo" if fuente == "Catálogo" else "TAC")
    rv = c.loc[c["clase"] == "Renta variable", "peso"].sum()
    alt = c.loc[c["clase"] == "Activos alternativos", "peso"].sum()
    k = st.columns(4)
    with k[0]:
        _stat("Renta variable / renta fija" + (" / alternativos" if alt else ""),
              f"{rv * 100:.0f}% / {(1 - rv - alt) * 100:.0f}%" + (f" / {alt * 100:.0f}%" if alt else ""))
    with k[1]:
        _stat("Rentabilidad 1A ponderada", fmt_pct(ponderado(c, "rent_1a")))
    with k[2]:
        _stat("Rentabilidad 3A ponderada", fmt_pct(ponderado(c, "rent_3a")))
    with k[3]:
        _stat(f"{costo} ponderado", fmt_pct(ponderado(c, "tac")))
    _espacio()   # aire entre los indicadores y la tabla

    def valores(d: pd.DataFrame) -> list[str]:
        return [fmt_pct(ponderado(d, k)) for k in ("rent_ytd", "rent_1a", "rent_3a")]

    filas, clases = [], []
    for clase, g in c.groupby("clase", sort=False):
        filas.append([Raw(clase), "", "", fmt_pct(g["peso"].sum() * 100), *valores(g), fmt_pct(ponderado(g, "tac"))])
        clases.append("clase")
        for sub, gs in g.groupby("subactivo", sort=False):
            for i, (_, r) in enumerate(gs.iterrows()):
                filas.append([Raw(f"<span style='padding-left:16px'>{sub}</span>") if i == 0 else "",
                              r["fondo"] if r["estado"] != "Sin datos" else f"{r['fondo']} (sin datos)",
                              r["serie"] if r["serie"] else "—", fmt_pct(r["peso"] * 100), fmt_pct(r["rent_ytd"]),
                              fmt_pct(r["rent_1a"]), fmt_pct(r["rent_3a"]), fmt_pct(r["tac"])])
                clases.append(None)
    tabla = pd.DataFrame(filas, columns=["Activo", "Fondo", serie, "Peso", "Rent. YTD", "Rent. 1A", "Rent. 3A", costo])
    show_table(tabla, num_cols=(serie, "Peso", "Rent. YTD", "Rent. 1A", "Rent. 3A", costo), total_position="bottom",
               row_classes=clases,
               total_row={"Activo": "Total del portafolio", "Peso": fmt_pct(c["peso"].sum() * 100),
                          "Rent. YTD": valores(c)[0], "Rent. 1A": valores(c)[1], "Rent. 3A": valores(c)[2],
                          costo: fmt_pct(ponderado(c, "tac"))})
    con_datos = int((c["estado"] != "Sin datos").sum())
    if fuente == "CMF":
        nota = ("Portafolio armado solo con fondos mutuos Scotia (CMF), un fondo en una sola categoría, serie WEALTH. "
                "Rentabilidad y TAC son el promedio ponderado por peso de los fondos, no la rentabilidad real de una cartera "
                "(sin rebalanceo ni costos de transacción). Los porcentajes por perfil son un punto de partida y se editan "
                "en <code>config/carteras_fondos_mutuos_scotia.yaml</code>.")
    elif fuente == "Yahoo":
        nota = ("Portafolio de la arquitectura Abierta USD armado con los fondos internacionales del catálogo, un fondo en "
                "una sola categoría. Rentabilidades con el precio de cierre ajustado por dividendos de Yahoo, en la moneda de "
                "cotización (dólares; el 3A es anualizado). Rentabilidad y costo son el promedio ponderado por peso de los "
                "fondos con dato, no la rentabilidad real de una cartera. El costo (TER) solo existe para ETFs: cubre el "
                f"{cobertura(c, 'tac') * 100:.0f}% del peso, y la rentabilidad a 3 años el {cobertura(c, 'rent_3a') * 100:.0f}% "
                "(fondos con menos de 3 años de historia no la tienen). Yahoo es una fuente no oficial. Los porcentajes por "
                "perfil son un punto de partida y se editan en <code>config/carteras_usd.yaml</code>.")
    else:
        nota = (f"Modelo del catálogo (pesos del Excel): {con_datos} de {len(c)} fondos con datos. Cada fondo toma sus "
                "rentabilidades y costo de la CMF si tiene equivalencia, o de Yahoo (por ISIN) si es internacional; el resto "
                "se completa en <code>config/equivalencias_fondos.csv</code>. Rentabilidad y costo son el promedio ponderado "
                "de los fondos con dato; las de Yahoo están en su moneda de cotización.")
    st.markdown(f"<div class='footnote'>{nota}</div>", unsafe_allow_html=True)


def _exposiciones(c: pd.DataFrame, carteras: pd.DataFrame, foto: Foto | None, fuente: str) -> None:
    """Beneficio tributario y exposición subyacente por activo y por moneda, con las mismas filas de clase en rojo."""
    e = exposiciones_cartera(c, carteras)
    d = pd.concat([c.reset_index(drop=True), e.drop(columns="fondo")], axis=1)
    cols_valor = ("act_rv", "act_rf", "act_alt", "mon_usd", "mon_clp", "mon_uf", "mon_otras")
    nombres = ["Renta variable", "Renta fija", "Alternativos", "USD", "CLP", "UF", "Otras"]
    filas, clases = [], []
    for clase, g in d.groupby("clase", sort=False):
        filas.append([Raw(clase), "", "", "", *[_pct0(ponderado(g, k)) for k in cols_valor]])
        clases.append("clase")
        for sub, gs in g.groupby("subactivo", sort=False):
            for i, (_, r) in enumerate(gs.iterrows()):
                filas.append([Raw(f"<span style='padding-left:16px'>{sub}</span>") if i == 0 else "", r["fondo"],
                              r["serie"] if r["serie"] else "—", r["beneficio"], *[_pct0(r[k]) for k in cols_valor]])
                clases.append(None)
    tabla = pd.DataFrame(filas, columns=["Activo", "Fondo", "Serie", "Beneficio tributario", *nombres])
    show_table(tabla, num_cols=tuple(tabla.columns[2:]), row_classes=clases)
    if fuente == "CMF":
        nota = ("Los fondos Scotia no están en el catálogo: su exposición está a nivel de valor cuota (cada fondo 100 % en su "
                "categoría y en la moneda de su cotización) y no tienen beneficio tributario hasta conseguir esa fuente "
                "(107 o 108 LIR).")
    else:
        nota = ("Beneficio tributario (107 o 108 LIR) y exposición subyacente de cada fondo por activo y por moneda, según el "
                "catálogo. Las filas de clase son el promedio ponderado por el peso del portafolio.")
    st.markdown(f"<div class='footnote'>{nota}</div>", unsafe_allow_html=True)
    _exposicion(c)
    if fuente == "CMF" and foto is not None:
        _subyacente(c, foto)


def _exposicion(c: pd.DataFrame) -> None:
    ex = exposicion(c)
    st.markdown("<div class='chart-title' style='margin-top:18px'>Exposición</div>", unsafe_allow_html=True)
    cols = st.columns(3)
    for col, (clave, titulo) in zip(cols, (("clase", "Clase de activo"), ("subactivo", "Subactivo"),
                                           ("moneda", "Moneda del valor cuota"))):
        g = ex[clave]
        colores = (PALETTE + [GRIS, SERIE_2])[:len(g)]
        with col:
            st.markdown(f"<div class='chart-title'>{titulo}</div>", unsafe_allow_html=True)
            st.plotly_chart(donut(g["grupo"], g["peso"] * 100, "Cartera", "100%", 220, colores),
                            use_container_width=True, config={"displayModeBar": False}, key=f"est_exp_{clave}")
            st.markdown(legend_html(g["grupo"], [f"{p * 100:.1f}%" for p in g["peso"]], colores), unsafe_allow_html=True)
    st.markdown("<div class='footnote'>Exposición a nivel de fondo: cada fondo cuenta 100 % en su clase y subactivo, y en la "
                "moneda de su valor cuota o cotización, aunque su cartera subyacente sea distinta (por ejemplo, el fondo "
                "Acciones USA cotiza en pesos pero invierte en dólares).</div>", unsafe_allow_html=True)


def _subyacente(c: pd.DataFrame, foto: Foto) -> None:
    st.markdown("<div class='chart-title' style='margin-top:18px'>Composición subyacente (CMF)</div>", unsafe_allow_html=True)
    cols = st.columns(2)
    for col, (por, titulo) in zip(cols, (("clasificacion", "Tipo de instrumento"), ("pais", "País del emisor"))):
        g = composicion_cartera(c, foto, por)
        if len(g) > 7:  # los 6 mayores y el resto agrupado
            g = pd.concat([g.head(6), pd.DataFrame({"grupo": ["Otros"], "peso": [g["peso"].iloc[6:].sum()]})], ignore_index=True)
        colores = (PALETTE + [GRIS, SERIE_2])[:len(g)]
        with col:
            st.markdown(f"<div class='chart-title'>{titulo}</div>", unsafe_allow_html=True)
            st.plotly_chart(donut(g["grupo"], g["peso"] * 100, "Cartera", "100%", 220, colores),
                            use_container_width=True, config={"displayModeBar": False}, key=f"est_sub_{por}")
            st.markdown(legend_html(g["grupo"], [f"{p * 100:.1f}%" for p in g["peso"]], colores), unsafe_allow_html=True)
    st.markdown("<div class='footnote'>Cartera de cada fondo según la CMF, ponderada por su peso en el portafolio. Los datos "
                "de la CMF son incompletos: «Sin composición» son fondos sin cartera en la foto. El país del emisor no "
                "equivale a la exposición real en los fondos que invierten en ETFs: el ETF se registra donde cotiza, no "
                "donde invierte (por ejemplo, el fondo Latam aparece con Estados Unidos).</div>", unsafe_allow_html=True)


def _etiqueta(fila) -> str:
    return f"{fila['nombre_fondo']} · {fila['fm_serie']}"


def _comparador(foto: Foto) -> None:
    u = universo_cmf(foto)
    etiquetas = {(int(r.fo_run), str(r.fm_serie)): _etiqueta(r) for _, r in u.iterrows()}
    inv = {v: k for k, v in etiquetas.items()}
    elegidas = st.multiselect("Series a comparar (de 2 a 4)", list(etiquetas.values()), max_selections=4, key="est_cmp")
    if len(elegidas) < 2:
        st.info("Elige al menos 2 series para compararlas.")
        return
    c = comparar(u, [inv[e] for e in elegidas])
    cols = {_etiqueta(r): r for _, r in c.iterrows()}
    filas = [("Rent. YTD", "rent_ytd", fmt_pct), ("Rent. 1A", "rent_1a", fmt_pct), ("Rent. 3A", "rent_3a", fmt_pct),
             ("Rent. 5A", "rent_5a", fmt_pct), ("Rent. 10A", "rent_10a", fmt_pct), ("TAC", "tac", fmt_pct),
             ("Patrimonio", "patrimonio", _num), ("Partícipes", "participes", _num)]
    tabla = pd.DataFrame({"Indicador": [f[0] for f in filas],
                          **{n: [f[2](r[f[1]]) for f in filas] for n, r in cols.items()}})
    show_table(tabla, num_cols=tuple(cols))
    r1 = c.assign(nombre=[_etiqueta(r) for _, r in c.iterrows()])[["nombre", "rent_1a"]].dropna()
    if not r1.empty:
        st.markdown("<div class='chart-title'>Rentabilidad a 1 año</div>", unsafe_allow_html=True)
        fig = go.Figure(go.Bar(
            x=r1["rent_1a"], y=r1["nombre"], orientation="h", marker_color=[ACCENT if v >= 0 else NEGRO for v in r1["rent_1a"]],
            text=[f"{v:.2f}%" for v in r1["rent_1a"]], textposition="outside", cliponaxis=False,
            textfont=dict(color=TEXT, size=12), hovertemplate="%{y}<br>%{x:.2f}%<extra></extra>"))
        style_fig(fig, 70 + 34 * len(r1))
        fig.update_layout(bargap=0.4, margin=dict(l=10, r=60, t=10, b=10))
        fig.update_yaxes(autorange="reversed", showgrid=False, showline=False, ticksuffix="  ")
        fig.update_xaxes(ticksuffix="%", showgrid=False, showline=False, zeroline=bool((r1["rent_1a"] < 0).any()))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _composicion(foto: Foto) -> None:
    fondos = (foto.series.drop_duplicates("fo_run").set_index("fo_run")["nombre_fondo"].sort_values())
    c1, c2 = st.columns(2)
    fo = c1.selectbox("Fondo", list(fondos.index), key="est_comp_fondo", format_func=lambda f: f"{fondos[f]} ({f})")
    por = c2.selectbox("Corte", ["Clasificación", "País", "Emisor"], key="est_comp_por")
    g = composicion_fondo(foto, int(fo), {"Clasificación": "clasificacion", "País": "pais", "Emisor": "emisor"}[por])
    if g.empty:
        st.info("Sin composición en la foto: la CMF no trae cartera de este fondo.")
        return
    if len(g) > 8:  # los 7 mayores y el resto agrupado
        g = pd.concat([g.head(7), pd.DataFrame({"grupo": ["Otros"], "peso": [g["peso"].iloc[7:].sum()]})], ignore_index=True)
    colores = (PALETTE + [GRIS, SERIE_2])[:len(g)]
    d, leg = st.columns([1, 1])
    with d:
        st.plotly_chart(donut(g["grupo"], g["peso"] * 100, "Fondo", "100%", 260, colores),
                        use_container_width=True, config={"displayModeBar": False})
    with leg:
        st.markdown(legend_html(g["grupo"], [f"{p * 100:.1f}%" for p in g["peso"]], colores), unsafe_allow_html=True)


def _linea(x, y, titulo: str, color: str) -> None:
    st.markdown(f"<div class='chart-title'>{titulo}</div>", unsafe_allow_html=True)
    fig = go.Figure(go.Scatter(x=x, y=y, mode="lines", line=dict(color=color, width=2.5),
                               hovertemplate="%{x}<br>%{y:,.0f}<extra></extra>"))
    style_fig(fig, 240)
    fig.update_xaxes(type="category", showgrid=False, showline=False)
    fig.update_yaxes(showgrid=False, showline=False, rangemode="tozero")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _historial(foto: Foto, snapshots: Path) -> None:
    u = universo_cmf(foto)
    etiquetas = {_etiqueta(r): (int(r.fo_run), str(r.fm_serie)) for _, r in u.iterrows()}
    elegida = st.selectbox("Serie", list(etiquetas), key="est_hist")
    fo, serie = etiquetas[elegida]
    t = serie_patrimonio(foto, fo, serie)
    if t.empty:
        st.info("La CMF no trae historial mensual de esta serie.")
    else:
        meses = [f"{int(m) // 100}-{int(m) % 100:02d}" for m in t["fecha_mes"]]
        c1, c2 = st.columns(2)
        with c1:
            _linea(meses, t["patrimonio"], "Patrimonio", SERIE_2)
        with c2:
            _linea(meses, t["participes"], "Partículas", ACCENT)
    c = cambio_entre_fotos(snapshots, fo, serie)
    if not c.empty:
        st.markdown("<div class='chart-title'>Cambio entre cargas</div>", unsafe_allow_html=True)
        show_table(pd.DataFrame({
            "Corte": [f.isoformat() for f in c["fecha_corte"]], "Rent. 1A": c["rent_1a"].map(fmt_pct).values,
            "Rent. YTD": c["rent_ytd"].map(fmt_pct).values, "TAC": c["tac"].map(fmt_pct).values,
            "Cambio Rent. 1A": c["delta_rent_1a"].map(lambda v: "—" if pd.isna(v) else f"{v:+.2f} pp").values}),
            num_cols=("Rent. 1A", "Rent. YTD", "TAC", "Cambio Rent. 1A"))
    if len(listar_fotos(snapshots)) < 2:
        st.markdown("<div class='footnote'>Hace falta una segunda carga para ver cambios entre cortes.</div>",
                    unsafe_allow_html=True)


def _pagina_screener(foto: Foto | None, ctx: Ctx) -> None:
    """Arquitectura en la primera fila, perfil debajo, y por perfil las vistas Rentabilidades y Exposiciones."""
    carteras = ctx.ds.carteras
    cfg = load_config("arquitecturas")
    nombres, perfiles = cfg["nombres"], cfg["perfiles_nombres"]
    arq = st.radio("Arquitectura", ARQUITECTURAS, horizontal=True, key="est_arq", format_func=lambda a: nombres.get(a, a))
    perfil = st.radio("Perfil", list(perfiles), horizontal=True, key="est_perfil", format_func=lambda p: perfiles[p])
    yahoo = cargar_yahoo(_ruta_yahoo())
    if arq == "cerrada_pesos" and foto is None:       # las carteras Scotia necesitan los 4 Excel de la CMF
        _sin_foto()
        return
    if arq == "abierta_dolares" and yahoo is None:    # y las Abierta USD los datos de Yahoo
        st.info("Todavía no hay datos de Yahoo Finance. Corre `python scripts/actualizar_mercado.py --fuente yahoo` y "
                "recarga esta página.")
        return
    c, fuente = armar(arq, perfil, carteras, _equiv(), foto,
                      None if yahoo is None else yahoo[1])
    if c.empty:
        st.info("Esta arquitectura no tiene fondos para este perfil en el catálogo.")
        return
    if fuente == "CMF":
        _sello(foto)
    elif fuente == "Yahoo":
        st.markdown(f"<div class='footnote'>Yahoo Finance, datos al {yahoo[0].isoformat()}.</div>", unsafe_allow_html=True)
    else:
        partes = ([f"CMF, datos al {foto.fecha_corte.isoformat()}"] if foto is not None else []) + \
                 ([f"Yahoo Finance, datos al {yahoo[0].isoformat()}"] if yahoo is not None else [])
        st.markdown(f"<div class='footnote'>Modelo del catálogo. {'; '.join(partes) or 'Sin datos de mercado cargados'}.</div>",
                    unsafe_allow_html=True)
    t_rent, t_expo = st.tabs(["Rentabilidades", "Exposiciones"])
    with t_rent:
        _rentabilidades(c, fuente)
    with t_expo:
        _exposiciones(c, carteras, foto, fuente)


def _equiv() -> pd.DataFrame:
    return eq.cargar(_rutas()[1])


def _pagina_comparador(foto: Foto | None) -> None:
    if foto is None:
        _sin_foto()
    else:
        _sello(foto)
        with st.container(border=True):
            card_title("Comparador", "De 2 a 4 series de la CMF lado a lado")
            _comparador(foto)
        with st.container(border=True):
            card_title("Composición", "Qué tiene cada fondo mutuo: clasificación, país y emisor (cartera de la CMF)")
            _composicion(foto)
    with st.container(border=True):
        card_title("Universo de fondos", "Todas las series de la CMF o los fondos internacionales del catálogo (Yahoo)")
        vista = st.radio("Universo", ["CMF", "Internacionales"], horizontal=True, key="est_universo",
                         label_visibility="collapsed")
        if vista == "Internacionales":
            _internacionales()
        elif foto is not None:
            _universo(foto)


def _pagina_historial(foto: Foto | None, snapshots: Path) -> None:
    if foto is None:
        _sin_foto()
        return
    _sello(foto)
    with st.container(border=True):
        card_title("Historial", "Patrimonio y partícipes por mes, y cambio de rentabilidad entre cargas")
        _historial(foto, snapshots)


def render(ctx: Ctx) -> None:
    """Portafolios: el subtema (Screener, Comparador o Historial) lo elige la barra lateral y llega en ctx.page."""
    page_title("Portafolios")
    snapshots, _ = _rutas()
    foto = cargar_foto(snapshots)
    if ctx.page == NAV_COMPARADOR:
        _pagina_comparador(foto)
    elif ctx.page == NAV_HISTORIAL:
        _pagina_historial(foto, snapshots)
    else:
        _pagina_screener(foto, ctx)
