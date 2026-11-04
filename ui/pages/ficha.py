from datetime import date
from itertools import zip_longest

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.components import (badge, card_title, data_as_of, donut, legend_html, page_title, pct, pending_data,
                           safe, show_table)
from ui.pages import portafolio_cliente
from ui.rebalance_view import show_plan
from ui.context import Ctx
from ui.theme import EXPO_PALETTE, SERIE_2, SERIE_1
from wm.auth import can_edit_dato, can_reassign
from wm.config import load_config
from wm.costos import costo_comision
from wm.display import format_rut, nombres_arquitecturas
from wm.metrics import is_true
from wm.exposure import client_exposure, has_breakdown, perfil_de
from wm.priority import dias_sin_contacto
from wm.rebalance import plan_rebalanceo
from wm.series import evaluate_series
from wm.store import StoreUnavailable

# campo capturado por el advisor -> columna equivalente en el Excel
# campos del advisor: los dos primeros junto a los comentarios; el resto en filas de a dos, debajo de ellos
COLUMNA_IZQ = ("patrimonio_externo", "share_of_wallet")
PARES_IZQ = ("wealth_plan", "proxima_accion", "proxima_accion_fecha")
PARES_DER = ("global_complementario", "deep_discovery")
EXCEL_EQUIV = {"share_of_wallet": "share_of_wallet_pct", "wealth_plan": "tiene_wealth_plan"}


def _missing(v) -> bool:
    return v is None or (not isinstance(v, (bool, str)) and pd.isna(v))


def _fmt_excel(campo: str, v) -> str:
    if _missing(v):
        return "no disponible"
    if campo == "wealth_plan":
        return "Sí" if is_true(v) else "No"
    return f"{v:.0f}%" if isinstance(v, (int, float)) else str(v)


def _differs(campo: str, excel_v, captured: str) -> bool:
    if _missing(excel_v):
        return False
    if campo == "wealth_plan":
        return is_true(excel_v) != (captured == "si")
    try:
        return abs(float(excel_v) - float(captured)) >= 10
    except (TypeError, ValueError):
        return False


def _num_str(v: float) -> str:
    return f"{v:.10f}".rstrip("0").rstrip(".")


def _stat(label: str, value: str) -> None:
    st.markdown(f"<div class='stat-label'>{label}</div><div class='stat-value'>{value}</div>", unsafe_allow_html=True)


def _comision(ctx: Ctx, row: pd.Series, pos: pd.DataFrame) -> None:
    """Costo de comisión del cliente: porcentaje total sobre el AUM y, debajo, el porcentaje de cada componente."""
    costo = costo_comision(row, pos, ctx.ds.carteras)
    if costo is None or costo.tasa_pct is None:
        _stat("Comisión", "—")
        st.markdown("<div class='footnote'>Desglose disponible para ADC, ASE y TRA con datos cargados.</div>",
                    unsafe_allow_html=True)
        return
    _stat("Comisión", f"{costo.tasa_pct:.2f}%")
    st.markdown("".join(f"<div class='footnote'>{safe(n)} {v / costo.base * 100:.2f}%</div>" for n, v in costo.items),
                unsafe_allow_html=True)
    if costo.nota:
        st.markdown(f"<div class='footnote'>{safe(costo.nota)}</div>", unsafe_allow_html=True)


def _arch_label(row: pd.Series) -> str:
    nombres = nombres_arquitecturas()
    cob = f"cobertura {row['cobertura_arq']:.0%}"
    if pd.isna(row["arquitectura"]):
        return f"Arquitectura inferida: sin determinar ({cob})"
    nombre = nombres.get(row["arquitectura"], row["arquitectura"])
    return f"Arquitectura {'inferida' if row['arquitectura_inferida'] else 'declarada'}: {nombre} ({cob})"


def _pie(titulo: str, cli: dict, cov: float, subs: dict | None = None, extra_rows: dict | None = None) -> None:
    labels = [k for k, v in cli.items() if v > 0]
    if not labels:
        pending_data(f"sin exposición calculable ({titulo.lower()}).")
        return
    values = [cli[k] / cov * 100 for k in labels]
    st.markdown(f"**{titulo}**")
    top = max(range(len(values)), key=values.__getitem__)
    st.plotly_chart(donut(labels, values, labels[top], f"{values[top]:.0f}%", 260, colors=EXPO_PALETTE),
                    use_container_width=True, config={"displayModeBar": False})
    texts = [f"{v:.1f}%" for v in values]
    rows = _sub_rows(subs, cov)
    for label, extra in (extra_rows or {}).items():
        rows.setdefault(label, []).extend(extra)
    st.markdown(legend_html(labels, texts, colors=EXPO_PALETTE, subs=rows), unsafe_allow_html=True)


def _sub_rows(subs: dict | None, cov: float) -> dict:
    """Ponderación de cada subactivo (% de la cartera) bajo su activo."""
    return {label: [(name, f"{v / cov * 100:.1f}%") for name, v in cats.items() if v > 0]
            for label, cats in (subs or {}).items()}


def _exposiciones(ctx: Ctx, row: pd.Series, pos: pd.DataFrame) -> None:
    with st.container(border=True):
        card_title("Exposiciones", "Exposición de los activos financieros del cliente y moneda subyacente")
        if not has_breakdown(ctx.ds.carteras):
            pending_data("el desglose por fondo (renta fija, variable, alternativos y moneda) aún no está en la hoja de carteras.")
            return
        if pos.empty:
            st.info("Este cliente no tiene posiciones para calcular la exposición.")
            return
        cli = client_exposure(pos, ctx.ds.carteras)
        if cli.cobertura <= 0:
            pending_data("las posiciones del cliente no coinciden con fondos que tengan desglose.")
            return
        clase = {k: cli.clase[k] for k in ("Renta Variable", "Renta Fija", "Alternativos") if k in cli.clase}
        c1, c2 = st.columns(2)
        with c1:
            _pie("Clase de Activos", clase, cli.cobertura,
                 subs={"Renta Variable": cli.rv_categorias, "Renta Fija": cli.rf_categorias})
        with c2:
            if cli.moneda:
                _pie("Moneda", cli.moneda, cli.cobertura,
                     extra_rows=({"UF": [("* % de su renta fija local", f"{cli.uf_sobre_rf_local * 100:.0f}%")]}
                                 if cli.uf_sobre_rf_local is not None else None))
            else:
                st.markdown("**Moneda**")
                pending_data("exposición por moneda (columnas pct_moneda_*).")
        notas = [f"Calculado sobre el {cli.cobertura:.0%} de la cartera con desglose disponible."]
        st.markdown(f"<div class='footnote'>{' '.join(notas)}</div>", unsafe_allow_html=True)


def _costo_pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.2f}%"


def _beneficio(carteras: pd.DataFrame, f) -> str:
    """Beneficio tributario (107 / 108 / -) de la serie actual y, si cambia, de la serie del modelo: 'actual → modelo'."""
    if "beneficio_tributario" not in carteras.columns:
        return "—"
    ben = carteras.drop_duplicates("isin").set_index("isin")["beneficio_tributario"]
    actual, modelo = ben.get(f.isin), ben.get(f.isin_modelo)
    if actual is None or pd.isna(actual):
        return "—"
    return actual if modelo is None or pd.isna(modelo) or modelo == actual else f"{actual} → {modelo}"


def _series(ctx: Ctx, row: pd.Series, pos: pd.DataFrame) -> None:
    with st.container(border=True):
        card_title("Series", "Serie del cliente vs serie del modelo para el mismo fondo")
        findings = evaluate_series(pos, ctx.ds.carteras, row["arquitectura"] if pd.notna(row["arquitectura"]) else None)
        if not findings:
            st.info("Sin información de series para las posiciones de este cliente.")
            return
        valor = pos.groupby("isin")["valor_clp"].sum()
        rows = []
        for f in sorted(findings, key=lambda f: not f.es_mala):
            ahorro = (valor.get(f.isin, 0.0) * (f.comision_actual - f.comision_modelo)
                      if f.es_mala and f.comision_actual is not None and f.comision_modelo is not None
                      and f.comision_actual > f.comision_modelo else 0.0)
            rows.append({"Fondo": f.fondo, "Serie actual": f.serie_actual, "Costo serie actual": _costo_pct(f.comision_actual),
                         "Serie modelo": f.serie_modelo, "Costo serie modelo": _costo_pct(f.comision_modelo),
                         "Beneficio tributario": _beneficio(ctx.ds.carteras, f),
                         "Estado": badge("Serie mala", "bad") if f.es_mala else badge("OK", "ok"),
                         "Detalle": f.motivo, "Ahorro anual estimado": ctx.fmt(ahorro) if ahorro else "—"})
        show_table(pd.DataFrame(rows), num_cols=("Costo serie actual", "Costo serie modelo", "Beneficio tributario", "Ahorro anual estimado"))
        st.markdown("<div class='footnote'>Beneficio tributario de la serie (actual → modelo si cambia): 107 LIR, 10% sobre la utilidad "
                    "realizada; 108 LIR, permite traspasar entre fondos con 108 sin gatillar utilidad tributable, y la ganancia "
                    "acumulada se difiere hasta el rescate; \"-\", sin beneficio.</div>", unsafe_allow_html=True)


def _detalle_posiciones(ctx: Ctx, pos: pd.DataFrame) -> None:
    pos = pos if "costo_tributario_clp" in pos.columns else pos.assign(costo_tributario_clp=float("nan"))
    cols = [c for c in ("instrumento", "tipo", "valor_clp", "gp_no_realizada", "costo_tributario_clp", "rent_no_realizada")
            if c in pos.columns]
    t = pos[cols].sort_values("valor_clp", ascending=False).copy()
    t["valor_clp"] = t["valor_clp"].map(ctx.fmt)
    if "gp_no_realizada" in t:
        t["gp_no_realizada"] = pos.loc[t.index, "gp_no_realizada"].map(lambda v: ctx.fmt(v) if pd.notna(v) else "—")
    if "rent_no_realizada" in t:
        t["rent_no_realizada"] = pos.loc[t.index, "rent_no_realizada"].map(lambda v: pct(v * 100, 1) if pd.notna(v) else "—")
    t["costo_tributario_clp"] = pos.loc[t.index, "costo_tributario_clp"].map(lambda v: ctx.fmt(v) if pd.notna(v) else "—")
    t = t.rename(columns={"instrumento": "Instrumento", "tipo": "Tipo", "valor_clp": "Valor",
                          "gp_no_realizada": "G/P no realizada", "rent_no_realizada": "Rentabilidad",
                          "costo_tributario_clp": "Costo tributario"})
    show_table(t, num_cols=("Valor", "G/P no realizada", "Rentabilidad", "Costo tributario"))


def _gap(rem: float) -> None:
    st.markdown(f"<div style='height:{rem}rem'></div>", unsafe_allow_html=True)


def _nombre_fondo(pos: pd.DataFrame, carteras: pd.DataFrame) -> pd.Series:
    """Nombre del fondo (catálogo por ISIN); si no está, el instrumento sin el prefijo interno SIN_ISIN::."""
    base = (pos["instrumento"] if "instrumento" in pos.columns else pos["isin"]).astype(str).str.replace("SIN_ISIN::", "", regex=False)
    if "diccionario" not in carteras.columns:
        return base
    catalogo = carteras.drop_duplicates("isin").set_index("isin")["diccionario"]
    nombre = pos["isin"].map(catalogo)
    return nombre.where(nombre.notna(), base)


def _rentabilidad(ctx: Ctx, pos: pd.DataFrame) -> None:
    with st.container(border=True):
        card_title("Rentabilidad", "Ganancia o pérdida no realizada por fondo y total de la cartera, sobre el costo de cada posición")
        if pos.empty or not {"valor_clp", "gp_no_realizada"} <= set(pos.columns):
            pending_data("la ganancia/pérdida de las posiciones aún no está en la hoja de posiciones.")
            return
        p = pos.copy()
        p["fondo"] = _nombre_fondo(p, ctx.ds.carteras)
        p = p[p["gp_no_realizada"].notna()]
        if p.empty:
            pending_data("las posiciones de este cliente no traen ganancia/pérdida.")
            return
        g = p.groupby("fondo", as_index=False).agg(valor=("valor_clp", "sum"), gp=("gp_no_realizada", "sum"))
        g["costo"] = g["valor"] - g["gp"]
        g = g.sort_values("valor", ascending=False)

        def rent(gp: float, costo: float) -> float | None:
            return gp / costo * 100 if costo > 0 else None

        def fmt_rent(v) -> str:
            return "—" if v is None else pct(v, 1).replace("-", "−")

        def fmt_gp(v: float) -> str:
            return ("+" if v > 0 else "−" if v < 0 else "") + ctx.fmt(abs(v))

        tot_valor, tot_gp = float(g["valor"].sum()), float(g["gp"].sum())
        tot_rent = rent(tot_gp, tot_valor - tot_gp)
        _gap(0.4)
        c = st.columns([1, 1.3, 1.6])  # el valor actual es la cifra más larga: más ancho, sin pegarse a la vecina
        with c[0]:
            _stat("Rentabilidad total", fmt_rent(tot_rent))
        with c[1]:
            _stat("Ganancia/pérdida total", fmt_gp(tot_gp))
        with c[2]:
            _stat("Valor actual", ctx.fmt(tot_valor))
        _gap(1.2)  # aire entre las cifras y la tabla
        t = pd.DataFrame({
            "Fondo": g["fondo"].values,
            "Valor actual": g["valor"].map(ctx.fmt).values,
            "Costo": g["costo"].map(ctx.fmt).values,
            "Ganancia/pérdida": g["gp"].map(fmt_gp).values,
            "Rentabilidad": [fmt_rent(rent(gp, co)) for gp, co in zip(g["gp"], g["costo"])],
        })
        show_table(t, num_cols=("Valor actual", "Costo", "Ganancia/pérdida", "Rentabilidad"),
                   total_row={"Fondo": "Total cartera", "Valor actual": ctx.fmt(tot_valor),
                              "Costo": ctx.fmt(tot_valor - tot_gp), "Ganancia/pérdida": fmt_gp(tot_gp),
                              "Rentabilidad": fmt_rent(tot_rent)},
                   total_position="bottom")
        n_sin = len(pos) - len(p)
        if n_sin:
            st.markdown(f"<div class='footnote'>{n_sin} posición(es) sin dato de ganancia/pérdida quedan fuera de este cálculo.</div>",
                        unsafe_allow_html=True)


def _positions(ctx: Ctx, row: pd.Series, pos: pd.DataFrame) -> None:
    with st.container(border=True):
        arq = row["arquitectura"] if pd.notna(row["arquitectura"]) else None
        perfil = perfil_de(ctx.ds.carteras, row.get("perfil_norm"), arq)
        plan = plan_rebalanceo(pos, ctx.ds.carteras, arq, perfil, base_clp=float(row["aum_clp"]))
        nombres = nombres_arquitecturas()
        card_title("Posiciones", f"Lo que tiene hoy vs la cartera modelo ({nombres.get(arq, arq)}, {perfil})"
                   if plan is not None else "Lo que tiene hoy el cliente")
        if pos.empty:
            st.info("Este cliente no tiene posiciones registradas.")
        if plan is not None:
            show_plan(plan, ctx.fmt)
        elif not pos.empty:
            st.markdown("<div class='footnote'>Sin cartera modelo comparable: la arquitectura o el perfil del cliente no están determinados.</div>",
                        unsafe_allow_html=True)
        if not pos.empty:
            with st.expander("Detalle de posiciones: valor, ganancia/pérdida y rentabilidad"):
                _detalle_posiciones(ctx, pos)


# ------------------------------------------------------------------ comentarios y datos
def _send_comment(ctx: Ctx, rut: str) -> None:
    key = f"coment_{rut}"
    texto = (st.session_state.get(key) or "").strip()
    if not texto:
        return
    try:
        ctx.store.add_comment(rut, ctx.user, texto)
        st.session_state[key] = ""
    except StoreUnavailable:
        st.session_state["store_error"] = True


def _save_datos(ctx: Ctx, rut: str, campos: dict) -> None:
    try:
        actuales = ctx.store.get_datos(rut)  # se relee al guardar: otro advisor pudo escribir mientras tanto
    except StoreUnavailable:
        st.session_state["store_error"] = True
        return
    for campo, cfg in campos.items():
        v = st.session_state.get(f"dato_{rut}_{campo}")
        if v is None or v == "":
            continue
        if cfg["tipo"] == "si_no":
            v = {"Sí": "si", "No": "no"}.get(v, v)
        elif isinstance(v, date):
            v = v.isoformat()
        elif isinstance(v, (int, float)):
            v = _num_str(float(v))
        actual = actuales.get(campo)
        if actual and not can_edit_dato(actual["advisor"], ctx.user, ctx.role):
            continue
        if actual and actual["valor"] == str(v):
            continue
        try:
            ctx.store.set_dato(rut, campo, str(v), ctx.user)
        except StoreUnavailable:
            st.session_state["store_error"] = True
            return


def _widget(cfg: dict, key: str, actual: dict | None, disabled: bool):
    tipo, label = cfg["tipo"], cfg["etiqueta"]
    val = actual["valor"] if actual else None
    if tipo in ("numero", "porcentaje"):
        return st.number_input(label, value=float(val) if val else None, min_value=0.0,
                               max_value=100.0 if tipo == "porcentaje" else None, key=key, disabled=disabled)
    if tipo == "si_no":
        opts = ["", "Sí", "No"]
        idx = {"si": 1, "no": 2}.get(val, 0)
        return st.selectbox(label, opts, index=idx, key=key, disabled=disabled)
    if tipo == "fecha":
        return st.date_input(label, value=date.fromisoformat(val) if val else None, key=key, disabled=disabled)
    return st.text_input(label, value=val or "", key=key, disabled=disabled)


def _campo(ctx: Ctx, row: pd.Series, rut: str, campo: str, cfg: dict, actual: dict | None, down: bool) -> None:
    editable = can_edit_dato(actual["advisor"] if actual else None, ctx.user, ctx.role)
    _widget(cfg, f"dato_{rut}_{campo}", actual, down or not editable)
    notas = []
    excel_col = EXCEL_EQUIV.get(campo)
    if excel_col and excel_col in row.index:
        notas.append(f"Excel: {safe(_fmt_excel(campo, row[excel_col]))}")
    if actual:
        notas.append(f"ingresado por {safe(ctx.adv_name(actual['advisor']))}, {actual['actualizado_en']:%d-%m-%Y}")
        if excel_col and excel_col in row.index and _differs(campo, row[excel_col], actual["valor"]):
            notas.append("Difiere del Excel")
    if notas:
        st.markdown(f"<div class='footnote field-note'>{' · '.join(notas)}</div>", unsafe_allow_html=True)


def _comments_and_data(ctx: Ctx, row: pd.Series, rut: str) -> None:
    with st.container(border=True):
        card_title("Comentarios y datos del advisor")
        campos = load_config("campos_cliente")["campos"]
        actuales, comentarios, down = {}, [], not ctx.store_ok
        if not down:
            try:
                actuales = ctx.store.get_datos(rut)
                comentarios = ctx.store.list_comments(rut)
            except StoreUnavailable:
                down = True
        if down:
            st.warning("Base de datos no disponible: comentarios y datos capturados deshabilitados. "
                       "Lo que escribas se conserva en pantalla hasta que vuelva.")
            st.session_state.pop("store_error", None)
        elif st.session_state.pop("store_error", False):
            st.error("No se pudo guardar; el texto sigue en pantalla, inténtalo de nuevo.")
        readonly = ctx.role == "Managing Director"

        # Fila 1: datos (izquierda) y comentarios (derecha). Fila 2: los campos restantes en pares, para que queden alineados
        # con los de la izquierda y por debajo de los comentarios. Cada fila es un st.columns propio: alinea por construcción.
        left, right = st.columns(2)
        with left:
            st.markdown("**Datos del cliente**")
            for campo in campos:
                if campo in COLUMNA_IZQ:
                    _campo(ctx, row, rut, campo, campos[campo], actuales.get(campo), down)
        with right:
            st.markdown("**Comentarios**")
            if not readonly:
                st.text_area("Nuevo comentario", key=f"coment_{rut}", label_visibility="collapsed",
                             placeholder="Escribe un comentario sobre este cliente…", disabled=down)
                st.button("Agregar comentario", key="coment_send", on_click=_send_comment, args=(ctx, rut), disabled=down)
            if not comentarios and not down:
                st.caption("Aún no hay comentarios.")
            for c in reversed(comentarios):
                st.markdown(f"<div class='comment'><div class='meta'>{safe(ctx.adv_name(c['advisor']))} · {c['creado_en']:%d-%m-%Y %H:%M}</div>"
                            f"{safe(c['texto'])}</div>", unsafe_allow_html=True)
        for izq, der in zip_longest(PARES_IZQ, PARES_DER):
            a, b = st.columns(2)
            for col, campo in ((a, izq), (b, der)):
                if campo in campos:  # campo None: la celda queda vacía
                    with col:
                        _campo(ctx, row, rut, campo, campos[campo], actuales.get(campo), down)
        if not readonly:
            st.button("Guardar datos", key="datos_save", on_click=_save_datos, args=(ctx, rut, campos), disabled=down)


def _asignacion(ctx: Ctx, row: pd.Series, rut: str) -> None:
    """Quién atiende al cliente. Si fue reasignado desde el portal, lo dice; el Managing Director puede reasignarlo."""
    if bool(row.get("asignacion_pendiente")):
        st.markdown(f"<div class='footnote'>Reasignado desde el portal a {safe(ctx.adv_name(row['advisor']))}; el Excel todavía dice {safe(ctx.adv_name(row['advisor_excel']))}.</div>",
                    unsafe_allow_html=True)
    if not can_reassign(ctx.role):
        return
    k = f"asig_{rut}"
    if ok := st.session_state.pop(k + "_ok", None):
        st.success(f"Cliente reasignado a {ok}.")
    with st.expander("Reasignar cliente a otro advisor"):
        if not ctx.store_ok:
            st.warning("Base de datos no disponible: no se puede reasignar.")
            return
        codigos = [a for a in sorted(ctx.view["advisor"].dropna().unique()) if a != row["advisor"]]
        c1, c2, c3 = st.columns([2, 3, 1])
        nuevo = c1.selectbox("Nuevo advisor", codigos, format_func=ctx.adv_name, key=k + "_nuevo")
        motivo = c2.text_input("Motivo (opcional)", key=k + "_motivo")
        c3.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
        if c3.button("Reasignar", key=k + "_btn", type="primary", disabled=nuevo is None):
            try:
                excel = row.get("advisor_excel") if "advisor_excel" in row.index and pd.notna(row.get("advisor_excel")) else row["advisor"]
                ctx.store.reasignar(rut, nuevo, ctx.user, motivo.strip(), excel)
                st.session_state[k + "_ok"] = ctx.adv_name(nuevo)
                st.rerun()
            except StoreUnavailable:
                st.error("No se pudo guardar la reasignación: la base de datos no responde.")
        h = ctx.store.historial_asignaciones(rut)
        if len(h):
            st.markdown("**Historial de asignaciones**")
            show_table(pd.DataFrame({"Fecha": pd.to_datetime(h["creado_en"]).dt.strftime("%d-%m-%Y %H:%M"), "Advisor": h["advisor"].map(ctx.adv_name),
                                     "Cambiado por": h["cambiado_por"], "Motivo": h["motivo"]}))


def render(ctx: Ctx) -> None:
    page_title("Ficha del cliente")
    mine = ctx.mine().sort_values(["aum_clp", "rut"], ascending=[False, True])   # orden estable: por AUM, no por prioridad (que cambia al guardar un portafolio)
    if mine.empty:
        st.info("No hay clientes para mostrar.")
        return
    ruts = list(mine["rut"])
    elegido = st.session_state.get("cliente_sel")
    if elegido not in ruts:
        st.session_state.pop("cliente_sel", None)
    else:
        st.session_state["cliente_sel"] = elegido   # si cambia el orden de la lista (p. ej. al actualizar el AUM), el selector conserva al cliente en vez de volver al primero
    by_rut = mine.set_index("rut")
    rut = st.selectbox("Cliente", ruts, key="cliente_sel", format_func=lambda r: by_rut.loc[r, "cliente_label"])
    row = by_rut.loc[rut]
    pos = ctx.ds.posiciones[ctx.ds.posiciones["rut"] == rut]

    with st.container(border=True):
        top = st.columns([3, 2])
        with top[0]:
            st.markdown(f"<div class='hello-name'>{safe(row['nombre'])}</div>", unsafe_allow_html=True)
            st.markdown(" ".join([badge(row["tipo_persona"], "muted"), badge(row["servicio"], "muted"),
                                  badge(str(row["perfil_norm"]), "muted")]) +
                        f"<div class='footnote'>{_arch_label(row)} · {safe(format_rut(rut))}</div>", unsafe_allow_html=True)
        with top[1]:
            k1, k2 = st.columns(2)
            with k1:
                _stat("AUM", ctx.fmt_mm(row["aum_clp"]))
            with k2:
                _comision(ctx, row, pos)
        dias = dias_sin_contacto(row.to_frame().T, ctx.hoy).iloc[0]
        cols = st.columns(5)
        with cols[0]:
            _stat("Share of wallet", pct(row.get("share_of_wallet_pct"), 0) if "share_of_wallet_pct" in row.index else "—")
        with cols[1]:
            wp = row.get("tiene_wealth_plan") if "tiene_wealth_plan" in row.index else None
            _stat("Wealth plan", "—" if _missing(wp) else ("Sí" if is_true(wp) else "No"))
        with cols[2]:
            _stat("Último contacto", "sin registro" if pd.isna(dias) else f"{int(dias)} días")
        with cols[3]:
            _stat("Series malas", "Sí" if row["serie_mala"] else "No")
        with cols[4]:
            _stat("Desvío vs modelo", pct(row.get("desvio_modelo_pct"), 1) if "desvio_modelo_pct" in row.index else "—")
        st.markdown(" ".join(chips_ for chips_ in [badge(m, "warn") for m in row["motivos"]]), unsafe_allow_html=True)
    data_as_of(ctx.ds.as_of)
    _asignacion(ctx, row, rut)

    tab_ficha, tab_portafolio = st.tabs(["Resumen", "Portafolio"])
    with tab_ficha:
        _rentabilidad(ctx, pos)
        _exposiciones(ctx, row, pos)
        _positions(ctx, row, pos)
        _series(ctx, row, pos)
        _comments_and_data(ctx, row, rut)
    with tab_portafolio:
        portafolio_cliente.render_tab(ctx, row, rut, pos)
