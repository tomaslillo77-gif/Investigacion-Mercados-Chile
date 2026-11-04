from datetime import date

import pandas as pd
import streamlit as st

from ui.components import badge, card_title, page_title, show_table
from ui.context import Ctx
from ui.pages.ficha import _send_comment
from wm.store import StoreUnavailable


def _quick_comment(ctx: Ctx, mine: pd.DataFrame, down: bool) -> None:
    if ctx.role == "Managing Director" or mine.empty:
        return
    with st.container(border=True):
        card_title("Comentario rápido")
        rut = st.selectbox("Cliente", list(mine.index), key="seg_pick", disabled=down,
                           format_func=lambda r: mine.loc[r, "cliente_label"])
        st.text_area("Comentario", key=f"coment_{rut}", label_visibility="collapsed", disabled=down)
        st.button("Agregar comentario", key="coment_send", on_click=_send_comment, args=(ctx, rut), disabled=down)


def render(ctx: Ctx) -> None:
    page_title("Seguimiento")
    mine = ctx.mine().set_index("rut")
    acciones, fechas, down = {}, {}, not ctx.store_ok
    if not down:
        try:
            acciones = ctx.store.latest_by_campo("proxima_accion")
            fechas = ctx.store.latest_by_campo("proxima_accion_fecha")
        except StoreUnavailable:
            down = True
    if down:
        st.warning("Base de datos no disponible: el seguimiento está deshabilitado. "
                   "Lo que escribas se conserva en pantalla hasta que vuelva.")
        _quick_comment(ctx, mine, True)
        return

    rows = []
    for rut, a in acciones.items():
        if rut not in mine.index or not a["valor"].strip():
            continue
        f = fechas.get(rut)
        fecha = date.fromisoformat(f["valor"]) if f and f["valor"] else None
        rows.append({"rut": rut, "cliente": mine.loc[rut, "cliente_label"], "accion": a["valor"], "fecha": fecha,
                     "vencida": fecha is not None and fecha < ctx.hoy, "autor": ctx.adv_name(a["advisor"])})

    with st.container(border=True):
        card_title("Próximas acciones", "Las vencidas aparecen primero")
        if not rows:
            st.info("No hay acciones pendientes. Regístralas desde la Ficha del cliente (campo «Próxima acción»).")
        else:
            df = pd.DataFrame(rows).sort_values(["vencida", "fecha"], ascending=[False, True], na_position="last")
            show_table(pd.DataFrame({
                "Cliente": df["cliente"].values, "Próxima acción": df["accion"].values,
                "Fecha": df["fecha"].map(lambda d: "sin fecha" if d is None or pd.isna(d) else f"{d:%d-%m-%Y}").values,
                "Estado": [badge("Vencida", "bad") if v else badge("Pendiente", "muted") for v in df["vencida"]],
                "Registrada por": df["autor"].values}), link_col="Cliente")
    _quick_comment(ctx, mine, False)
