import os
from pathlib import Path

import pandas as pd
import streamlit as st

from ui.components import card_title, page_title, show_table
from ui.context import Ctx
from wm.export import export_feedback
from wm.loader import ROOT
from wm.store import StoreUnavailable

CATEGORIAS = ["Falta un dato", "Mejora de diseño", "Error", "Otra"]
IMPORTANCIAS = ["baja", "media", "alta"]


def _send(ctx: Ctx) -> None:
    texto = (st.session_state.get("fb_texto") or "").strip()
    if not texto:
        return
    try:
        pagina = ctx.page
        ctx.store.add_feedback(ctx.user, pagina, st.session_state.get("fb_cat", CATEGORIAS[0]), texto,
                               st.session_state.get("fb_imp", "media"))
        st.session_state["fb_texto"] = ""
        st.session_state["fb_ok"] = True
    except StoreUnavailable:
        st.session_state["fb_err"] = True


def sidebar_box(ctx: Ctx) -> None:
    down = not ctx.store_ok
    with st.sidebar.expander("Sugerir mejora"):
        if down:
            st.caption("Base de datos no disponible: lo que escribas se conserva hasta que vuelva.")
            st.session_state.pop("fb_err", None)
        st.selectbox("Tipo", CATEGORIAS, key="fb_cat", disabled=down)
        st.selectbox("Importancia", IMPORTANCIAS, index=1, key="fb_imp", disabled=down)
        st.text_area("¿Qué necesitas ver o mejorar?", key="fb_texto", disabled=down)
        st.button("Enviar", key="fb_send", on_click=_send, args=(ctx,), disabled=down)
        if st.session_state.pop("fb_ok", False):
            st.success("¡Gracias! Quedó registrado.")
        if st.session_state.pop("fb_err", False):
            st.error("No se pudo guardar; el texto sigue aquí, inténtalo de nuevo.")


def render(ctx: Ctx) -> None:
    page_title("Bandeja de feedback")
    if not ctx.store_ok:
        st.warning("Base de datos no disponible: no se puede leer el feedback.")
        return
    try:
        fb = ctx.store.list_feedback()
        cm = ctx.store.list_all_comments()
    except StoreUnavailable:
        st.warning("Base de datos no disponible: no se puede leer el feedback.")
        return
    with st.container(border=True):
        card_title(f"{len(fb)} sugerencias")
        if fb:
            df = pd.DataFrame(fb).sort_values("id", ascending=False)
            show_table(pd.DataFrame({
                "Fecha": df["creado_en"].map(lambda d: f"{d:%d-%m-%Y}").values, "Advisor": df["advisor"].map(ctx.adv_name).values,
                "Página": df["pagina"].values, "Tipo": df["categoria"].values,
                "Importancia": df["importancia"].values, "Sugerencia": df["texto"].values}), link_col="Advisor")
        else:
            st.info("Aún no hay sugerencias.")
        if st.button("Exportar a CSV", key="fb_export"):
            out_dir = Path(os.environ.get("WM_EXPORT_DIR") or ROOT / "exports")
            paths = export_feedback(ctx.store, out_dir, ctx.hoy)
            st.success("Exportado: " + ", ".join(str(p) for p in paths))
    with st.container(border=True):
        card_title("Comentarios recientes de los advisors")
        if cm:
            df = pd.DataFrame(cm).sort_values("id", ascending=False).head(30)
            names = ctx.view.set_index("rut")["cliente_label"]
            show_table(pd.DataFrame({
                "Fecha": df["creado_en"].map(lambda d: f"{d:%d-%m-%Y}").values,
                "Cliente": df["rut"].map(lambda r: names.get(r, r)).values,
                "Advisor": df["advisor"].map(ctx.adv_name).values,
                "Comentario": df["texto"].values}), link_col="Cliente")
        else:
            st.info("Aún no hay comentarios.")
