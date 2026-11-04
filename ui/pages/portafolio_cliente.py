"""Pestaña «Portafolio» de la ficha del cliente: el advisor ve lo que el cliente tiene hoy y arma el portafolio objetivo desde la lista de instrumentos.

Se guarda como versión inmutable en la base (`wm/store.py`), vigente de inmediato y sin aprobación: el portal refleja lo que el advisor decide.
La lógica vive en `wm/portafolio_cliente.py`; aquí solo está la pantalla y el estado de la sesión.
"""
from datetime import date

import pandas as pd
import streamlit as st

from ui.components import badge, card_title, pct, show_table
from ui.context import Ctx
from ui.rebalance_view import show_plan
from wm.auth import can_edit_portafolio
from wm.catalogo import cargar_catalogo
from wm.config import load_config
from wm.display import format_rut
from wm.exposure import perfil_of
from wm.portafolio_export import excel_reunion
from wm.portafolio_cliente import (
    EXTERNO, ITEM_COLS, agregar, ajuste, aplicar_edicion, cfg, comparar_versiones, desactualizado, desde_modelo, desde_posiciones, desde_version,
    avisos_consolidar, avisos_desvio, avisos_series, hay_errores, impuesto_estimado, normalizar, resumir, tabla_hoy, validar, vacio,
)
from wm.store import ConflictoDeVersion, StoreUnavailable

PUNTOS = ["Lo que tiene hoy", "Un modelo de la casa", "Una versión guardada", "Vacío"]


@st.cache_data(show_spinner=False)
def _catalogo(carteras: pd.DataFrame, huella: float):
    c, fuente = cargar_catalogo(carteras)
    return c.instrumentos, c.alias, [(i.level, i.message) for i in c.issues], fuente


def _huella_catalogo() -> float:
    from wm.loader import ROOT
    ruta = ROOT / load_config("catalogo")["ruta"]
    return ruta.stat().st_mtime if ruta.exists() else 0.0


def _k(rut: str, nombre: str) -> str:
    return f"pf_{nombre}_{rut}"


def _fmt_pct(v) -> str:
    return "—" if pd.isna(v) else f"{v:.1f}%".replace(".", ",")


def _fmt_com(v) -> str:
    return "—" if pd.isna(v) else f"{v * 100:.2f}%".replace(".", ",")


def _perfil(ctx: Ctx, row: pd.Series) -> str:
    return perfil_of(ctx.ds.casa(), row.get("perfil_norm")) or str(row.get("perfil_norm") or "—")


def _set_base(rut: str, items: pd.DataFrame, origen: str | None = None) -> None:
    """Cambia el portafolio que se está editando y reinicia la tabla editable (su estado interno depende de la versión de la clave)."""
    st.session_state[_k(rut, "base")] = items.reset_index(drop=True)
    st.session_state[_k(rut, "ver")] = st.session_state.get(_k(rut, "ver"), 0) + 1
    if origen:
        st.session_state[_k(rut, "origen")] = origen


def _leer_vigente(ctx: Ctx, rut: str):
    """(portafolio vigente o None, historial, base caída). La base caída desactiva la edición pero no la pantalla."""
    if not ctx.store_ok:
        return None, [], True
    try:
        return ctx.store.portafolio_vigente(rut), ctx.store.historial_portafolio(rut), False
    except StoreUnavailable:
        return None, [], True


def _iniciar(rut: str, vigente, hoy: pd.DataFrame) -> None:
    if _k(rut, "base") in st.session_state:
        return
    if vigente:
        st.session_state[_k(rut, "base")] = vigente["items"]
        st.session_state[_k(rut, "leida")] = vigente["version"]
        st.session_state[_k(rut, "origen")] = f"version:{vigente['version']}"
    else:
        st.session_state[_k(rut, "base")] = hoy
        st.session_state[_k(rut, "leida")] = 0
        st.session_state[_k(rut, "origen")] = "hoy"
    st.session_state[_k(rut, "ver")] = 0


def _tabla_items(items: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"Instrumento": items["nombre"], "Serie": items["serie"].fillna("—"), "Peso": items["peso"].map(_fmt_pct), "Comisión": items["comision"].map(_fmt_com)})


# ── Paneles ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _panel_hoy(ctx: Ctx, t: pd.DataFrame) -> None:
    with st.container(border=True):
        card_title("Lo que tiene hoy", "Posiciones del cliente, reconocidas contra la lista de instrumentos")
        if t.empty:
            st.info("Este cliente no tiene posiciones registradas.")
            return
        show_table(pd.DataFrame({"Instrumento": t["nombre"], "Serie": t["serie"].fillna("—"), "Valor": t["valor_clp"].map(ctx.fmt), "%": t["peso"].map(_fmt_pct),
                                 "En la lista": [badge("Sí", "ok") if v else badge("No", "warn") for v in t["en_lista"]]}), num_cols=("Valor", "%"))
        fuera = t[~t["en_lista"]]
        if len(fuera):
            st.markdown(f"<div class='footnote'>{len(fuera)} posición(es) ({_fmt_pct(fuera['peso'].sum())} del valor) no están en la lista de instrumentos: se muestran "
                        "tal como vienen y no entran en las exposiciones.</div>", unsafe_allow_html=True)


def _punto_de_partida(ctx: Ctx, rut: str, row: pd.Series, pos: pd.DataFrame, cat: pd.DataFrame, alias: pd.DataFrame, hist: list[dict]) -> None:
    with st.container(border=True):
        card_title("Punto de partida", "Reemplaza lo que estás editando")
        c1, c2, c3 = st.columns([2, 3, 1])
        punto = c1.selectbox("Partir de", PUNTOS, key=_k(rut, "punto"))
        items = None
        if punto == PUNTOS[1]:
            modelos = ctx.ds.casa()[["arquitectura", "perfil"]].drop_duplicates()
            opciones = [f"{a} · {p}" for a, p in zip(modelos["arquitectura"], modelos["perfil"])]
            actual = f"{row.get('arquitectura_casa', row['arquitectura'])} · {_perfil(ctx, row)}"
            elegido = c2.selectbox("Modelo", opciones, index=opciones.index(actual) if actual in opciones else 0, key=_k(rut, "modelo"))
            arq, perfil = elegido.split(" · ", 1)
            items, origen = desde_modelo(ctx.ds.casa(), arq, perfil, cat), f"modelo:{arq}/{perfil}"
        elif punto == PUNTOS[2]:
            if hist:
                v = c2.selectbox("Versión", [h["version"] for h in hist], key=_k(rut, "vers"),
                                 format_func=lambda n: f"v{n} · {next(h for h in hist if h['version'] == n)['creado_en']:%d-%m-%Y}")
                guardada = ctx.store.portafolio_version(rut, v)
                items, origen = desde_version(guardada["items"]), f"version:{v}"
            else:
                c2.caption("Todavía no hay versiones guardadas.")
        elif punto == PUNTOS[0]:
            items, origen = desde_posiciones(pos, cat, alias), "hoy"
        else:
            items, origen = vacio(), "vacio"
        c3.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
        if c3.button("Cargar", key=_k(rut, "cargar"), disabled=items is None):
            _set_base(rut, items, origen)
            st.rerun()


def _editor(rut: str, cat: pd.DataFrame, disabled: bool) -> tuple[pd.DataFrame, bool]:
    """Tabla editable del portafolio objetivo. Devuelve (portafolio con lo editado, si hubo líneas quitadas)."""
    base = st.session_state[_k(rut, "base")]
    if base.empty:
        st.caption("El portafolio está vacío: agrega instrumentos desde la lista.")
        return base, False
    vista = pd.DataFrame({"Instrumento": base["nombre"].values, "Serie": base["serie"].fillna("—").values, "Peso %": pd.to_numeric(base["peso"]).values,
                          "Comisión %": (pd.to_numeric(base["comision"]) * 100).values, "Quitar": False})
    editada = st.data_editor(vista, key=f"pf_editor_{rut}_{st.session_state[_k(rut, 'ver')]}", hide_index=True, num_rows="fixed", use_container_width=True,
                             disabled=["Instrumento", "Serie", "Comisión %"] if not disabled else True,
                             column_config={"Peso %": st.column_config.NumberColumn("Peso %", min_value=0.0, max_value=100.0, step=0.5, format="%.2f"),
                                            "Comisión %": st.column_config.NumberColumn("Comisión %", format="%.2f"),
                                            "Quitar": st.column_config.CheckboxColumn("Quitar")})
    return aplicar_edicion(base, editada["Peso %"], editada["Quitar"])


def _agregar(rut: str, items: pd.DataFrame, cat: pd.DataFrame) -> None:
    ya = set(items["instrument_id"])
    activos = cat[cat["activo"].astype(bool) & ~cat["instrument_id"].isin(ya)]
    activos = activos.sort_values("nombre", key=lambda c: c.astype(str).str.casefold(), kind="stable")
    nombres = {r["instrument_id"]: f"{r['nombre']} · serie {r['serie'] if pd.notna(r['serie']) else '—'} · {r['clase']}" for _, r in activos.iterrows()}
    c1, c2 = st.columns([5, 1])
    elegido = c1.selectbox("Agregar instrumento", list(nombres), index=None, placeholder="Buscar por nombre, serie o clase", key=_k(rut, f"add{st.session_state[_k(rut, 'ver')]}"),
                           format_func=lambda i: nombres[i])
    c2.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
    if c2.button("Agregar", key=_k(rut, "agregar"), disabled=elegido is None):
        _set_base(rut, agregar(items, cat, elegido))
        st.rerun()


def _metricas(ctx: Ctx, row: pd.Series, items: pd.DataFrame, hoy_items: pd.DataFrame, cat: pd.DataFrame, issues) -> None:
    r = resumir(items, cat)
    h = resumir(hoy_items, cat)
    total = float(items["peso"].fillna(0).sum())
    k = st.columns(4)
    k[0].metric("Total", _fmt_pct(total), help="Debe sumar 100%")
    k[1].metric("Renta variable + alternativos", _fmt_pct(r.riesgo) if r.riesgo is not None else "—", help="Del portafolio con desglose")
    k[2].metric("Comisión ponderada", _fmt_com(r.comision) if r.comision is not None else "—")
    k[3].metric("Instrumentos", str(r.n))
    if r.clase:
        t = pd.DataFrame({"Clase": ["Renta variable", "Renta fija", "Alternativos"],
                          "Hoy": [_fmt_pct(h.clase.get(c)) if h.clase else "—" for c in ("Renta Variable", "Renta Fija", "Alternativos")],
                          "Objetivo": [_fmt_pct(r.clase.get(c)) for c in ("Renta Variable", "Renta Fija", "Alternativos")]})
        show_table(t, num_cols=("Hoy", "Objetivo"))
        st.markdown(f"<div class='footnote'>Exposición calculada sobre el {r.cobertura:.0%} del portafolio que tiene desglose en la lista"
                    + (f"; sin desglose: {', '.join(r.sin_desglose)}" if r.sin_desglose else "") + ".</div>", unsafe_allow_html=True)
    for i in issues:
        (st.error if i.level == "error" else st.warning)(i.message)
    for a in avisos_consolidar(items, cat) + avisos_desvio(hoy_items, items, cat):
        st.warning(a.message)


def _ajuste(ctx: Ctx, row: pd.Series, pos: pd.DataFrame, items: pd.DataFrame, cat: pd.DataFrame, alias: pd.DataFrame) -> pd.DataFrame | None:
    with st.container(border=True):
        card_title("Diferencia entre lo que tiene hoy y el objetivo", "Qué comprar y vender para llegar al portafolio objetivo")
        plan = ajuste(pos, items, cat, alias, _perfil(ctx, row), row.get("perfil_norm"), base_clp=float(row["aum_clp"]))
        if plan is None:
            st.markdown("<div class='footnote'>Agrega instrumentos para ver el ajuste.</div>", unsafe_allow_html=True)
        else:
            show_plan(plan, ctx.fmt, destino="objetivo")
        series = avisos_series(items, cat)
        impuestos = impuesto_estimado(pos, items, cat, alias)
        if series or len(impuestos):
            with st.expander("Avisos del cambio: series y tributación"):
                for a in series:
                    st.warning(a.message)
                if len(impuestos):
                    st.markdown(f"**Impuesto estimado por las ventas: {ctx.fmt(float(impuestos['impuesto_clp'].sum()))}**")
                    show_table(pd.DataFrame({"Posición": impuestos["nombre"], "Se vende": impuestos["fraccion_vendida"].map(lambda v: f"{v:.0%}"),
                                             "Impuesto estimado": impuestos["impuesto_clp"].map(ctx.fmt), "Beneficio (LIR)": impuestos["beneficio"]}),
                               num_cols=("Se vende", "Impuesto estimado"))
                    st.markdown("<div class='footnote'>Proporcional a lo que se vende, sobre el costo tributario de cada posición que entrega el cálculo tributario. "
                                "Es una estimación; un fondo con beneficio 107 o 108 puede diferir o evitar el impuesto según cómo se traspase.</div>", unsafe_allow_html=True)
    return plan


def _guardar(ctx: Ctx, rut: str, row: pd.Series, items: pd.DataFrame, issues, cat: pd.DataFrame, hoy_items: pd.DataFrame) -> None:
    ver = st.session_state[_k(rut, "ver")]
    nota = st.text_area("Nota (opcional)", key=_k(rut, f"nota{ver}"), placeholder="Por qué este portafolio: contexto, objetivos del cliente, decisiones…")
    obligatoria = cfg()["nota_obligatoria_si_desvio"] and bool(avisos_desvio(hoy_items, items, cat))
    bloqueado = hay_errores(issues) or (obligatoria and not nota.strip())
    if st.button("Guardar versión", key=_k(rut, "guardar"), type="primary", disabled=bloqueado):
        try:
            v = ctx.store.guardar_portafolio(rut, items[ITEM_COLS], ctx.user, nota.strip(), st.session_state.get(_k(rut, "origen"), "vacio"),
                                             row.get("perfil_norm"), st.session_state.get(_k(rut, "leida"), 0))
        except ConflictoDeVersion as e:
            st.session_state[_k(rut, "flash")] = ("conflicto", e.version_actual)
        except StoreUnavailable:
            st.session_state[_k(rut, "flash")] = ("error", None)
        else:
            st.session_state[_k(rut, "leida")] = v
            st.session_state[_k(rut, "origen")] = f"version:{v}"
            _set_base(rut, items)
            st.session_state[_k(rut, "flash")] = ("ok", v)
        st.rerun()


def _flash(rut: str) -> None:
    f = st.session_state.pop(_k(rut, "flash"), None)
    if not f:
        return
    tipo, v = f
    if tipo == "ok":
        st.success(f"Guardado como versión {v}; ya es la vigente.")
    elif tipo == "conflicto":
        st.error(f"Otro advisor guardó la versión {v} de este cliente mientras editabas. No se guardó nada. Carga la versión guardada como punto de partida y vuelve a aplicar tus cambios.")
    else:
        st.error("No se pudo guardar: la base de datos no responde. Lo que editaste sigue en pantalla; inténtalo de nuevo.")


def _historial(ctx: Ctx, rut: str, hist: list[dict]) -> None:
    with st.expander(f"Historial de versiones ({len(hist)})"):
        if not hist:
            st.caption("Todavía no hay versiones guardadas.")
            return
        show_table(pd.DataFrame({"Versión": [f"v{h['version']}" + (" (vigente)" if h["vigente"] else "") for h in hist],
                                 "Fecha": [f"{h['creado_en']:%d-%m-%Y %H:%M}" for h in hist], "Advisor": [ctx.adv_name(h["advisor"]) for h in hist],
                                 "Instrumentos": [str(h["n_items"]) for h in hist], "Origen": [h["origen"] for h in hist], "Nota": [h["nota"] or "—" for h in hist]}),
                   num_cols=("Instrumentos",))
        if len(hist) >= 2:
            c1, c2 = st.columns(2)
            nums = [h["version"] for h in hist]
            a = c1.selectbox("Comparar", nums, index=1, key=_k(rut, "cmp_a"), format_func=lambda n: f"v{n}")
            b = c2.selectbox("con", nums, index=0, key=_k(rut, "cmp_b"), format_func=lambda n: f"v{n}")
            d = comparar_versiones(ctx.store.portafolio_version(rut, a)["items"], ctx.store.portafolio_version(rut, b)["items"])
            show_table(pd.DataFrame({"Instrumento": d["nombre"], f"v{a}": d["peso_a"].map(_fmt_pct), f"v{b}": d["peso_b"].map(_fmt_pct),
                                     "Diferencia (pp)": d["dif"].map(lambda v: f"{v:+.1f}".replace("-", "−")), "Estado": d["estado"]}), num_cols=(f"v{a}", f"v{b}", "Diferencia (pp)"))


# ── Entrada ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def render_tab(ctx: Ctx, row: pd.Series, rut: str, pos: pd.DataFrame) -> None:
    cat, alias, avisos_cat, fuente = _catalogo(ctx.ds.casa(), _huella_catalogo())
    vigente, hist, base_caida = _leer_vigente(ctx, rut)
    hoy_items = desde_posiciones(pos, cat, alias)
    _iniciar(rut, vigente, hoy_items)
    puede = can_edit_portafolio(row.get("advisor"), ctx.advisor, ctx.role)
    editable = puede and not base_caida
    _flash(rut)

    with st.container(border=True):
        card_title("Portafolio objetivo", "Lo define el advisor; queda guardado por versiones y refleja lo que se implementa")
        estado = []
        if vigente:
            estado.append(badge(f"Vigente: v{vigente['version']} · {vigente['creado_en']:%d-%m-%Y} · {ctx.adv_name(vigente['advisor'])}", "ok"))
            motivo = desactualizado(vigente["creado_en"], ctx.hoy, vigente["perfil_al_guardar"], row.get("perfil_norm"))
            if motivo:
                estado.append(badge("Desactualizado", "warn"))
        else:
            estado.append(badge("Sin portafolio guardado: esto es un borrador", "warn"))
        st.markdown(" ".join(estado), unsafe_allow_html=True)
        if vigente and motivo:
            st.markdown(f"<div class='footnote'>Conviene revisarlo: {motivo}.</div>", unsafe_allow_html=True)
        if base_caida:
            st.warning("Base de datos no disponible: no se puede guardar ni leer el portafolio vigente. Se muestra lo que tiene hoy el cliente.")
        elif not puede:
            st.info("Solo el advisor asignado al cliente puede editar su portafolio; aquí se muestra en solo lectura." if ctx.role == "Managing Director" or ctx.advisor != row.get("advisor")
                    else "No tienes permiso para editar este portafolio.")
        st.markdown(f"<div class='footnote'>Lista de instrumentos: {fuente}. {len(cat)} instrumentos, {int(cat['activo'].astype(bool).sum())} activos.</div>", unsafe_allow_html=True)
        errores_cat = [m for n, m in avisos_cat if n == "error"]
        if errores_cat:
            with st.expander(f"La lista tiene {len(errores_cat)} problema(s) de datos"):
                st.markdown("\n".join(f"- {m}" for m in errores_cat[:20]))

    izq, der = st.columns([2, 3])
    with izq:
        _panel_hoy(ctx, tabla_hoy(pos, cat, alias))
    with der:
        if editable:
            _punto_de_partida(ctx, rut, row, pos, cat, alias, hist)
        with st.container(border=True):
            card_title("Portafolio objetivo", "Pesos en % del portafolio; deben sumar 100%")
            items, quito = _editor(rut, cat, disabled=not editable)
            if quito:
                _set_base(rut, items)
                st.rerun()
            if editable:
                _agregar(rut, items, cat)
                if st.button("Normalizar a 100%", key=_k(rut, "normalizar"), disabled=items.empty):
                    _set_base(rut, normalizar(items))
                    st.rerun()
            issues = validar(items, cat)
            _metricas(ctx, row, items, hoy_items, cat, issues if not items.empty else [])
    plan = _ajuste(ctx, row, pos, items, cat, alias)
    with st.container(border=True):
        card_title("Guardar y llevar a la reunión" if editable else "Llevar a la reunión")
        if editable:
            _guardar(ctx, rut, row, items, issues, cat, hoy_items)
        estado = f"Vigente v{vigente['version']}" if vigente and st.session_state.get(_k(rut, "leida")) == vigente["version"] and not items.empty else "Borrador sin guardar"
        st.download_button("Descargar Excel para la reunión", excel_reunion({"nombre": row.get("nombre", ""), "rut": format_rut(rut), "perfil": str(row.get("perfil_norm") or ""),
                                                                             "advisor": ctx.adv_name(row.get("advisor"))}, items, resumir(items, cat), resumir(hoy_items, cat), plan, estado,
                                                                            st.session_state.get(_k(rut, f"nota{st.session_state[_k(rut, 'ver')]}"), ""), ctx.hoy),
                           file_name=f"portafolio_{rut}_{ctx.hoy:%Y%m%d}.xlsx", key=_k(rut, "excel"), disabled=items.empty,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if not base_caida:
        _historial(ctx, rut, hist)
