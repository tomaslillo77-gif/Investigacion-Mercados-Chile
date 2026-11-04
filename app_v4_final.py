"""Enrutador del dashboard de Advisory and Brokerage. La lógica vive en wm/ y las páginas en ui/pages/."""
from datetime import date

import streamlit as st

st.set_page_config(page_title="Advisory and Brokerage",
                   layout="wide", initial_sidebar_state="expanded")

from ui.theme import inject_css, inject_extra_css  # noqa: E402
from ui.context import (MODULO_AFP, MODULO_CLIENT_PORTAL, MODULO_ESTRATEGIA, NAV_ALINEACION, NAV_CLIENTES, NAV_COMPARADOR, NAV_FEEDBACK,  # noqa: E402
                        NAV_EVOLUCION, NAV_FICHA, NAV_HISTORIAL, NAV_HOME, NAV_INDICES, NAV_MD, NAV_NEGOCIO, NAV_SCREENER, NAV_SEGUIMIENTO, ROLE_IA, ROLE_MD,
                        SECCION_AFP, SECCION_ESTRATEGIA, Ctx, derive_fx,
                        excel_path, get_store, load_data)
from ui.pages import afp, alineacion, clientes, estrategia, feedback, ficha, home, md, negocio, seguimiento  # noqa: E402
from wm.auth import advisors_from, check_pin, modules_for  # noqa: E402
from wm.config import load_config  # noqa: E402
from wm.loader import DatasetCorrupt, DatasetNotFound  # noqa: E402
from wm.version import version_actual  # noqa: E402

inject_css()
inject_extra_css()

PAGES_IA = {NAV_HOME: home, NAV_CLIENTES: clientes, NAV_FICHA: ficha,
            NAV_ALINEACION: alineacion, NAV_SEGUIMIENTO: seguimiento}
PAGES_MD = {NAV_MD: md, NAV_NEGOCIO: negocio, NAV_FICHA: ficha, NAV_FEEDBACK: feedback}   # el MD ve todo el negocio; la ficha le queda en solo lectura
PAGES_ESTRATEGIA = {NAV_SCREENER: estrategia, NAV_COMPARADOR: estrategia, NAV_HISTORIAL: estrategia}  # estrategia.render lee ctx.page
PAGES_AFP = {NAV_INDICES: afp, NAV_EVOLUCION: afp}  # afp.render lee ctx.page

hoy = date.today()
try:
    ds, view, issues = load_data(hoy)
except DatasetNotFound as e:
    st.error(f"No se encontró el archivo de datos. {e}\n\nRevisa la ruta en config/excel.yaml o la variable WM_EXCEL.")
    st.stop()
except DatasetCorrupt as e:
    st.error(f"{e}\n\nReemplázalo por una copia válida del Excel y recarga la página.")
    st.stop()
except Exception as e:  # hoja con formato inesperado
    st.error(f"No se pudo leer el Excel: {e}")
    st.stop()

store, store_ok = get_store()
auth_cfg = load_config("advisors")
users_cfg = load_config("usuarios")
is_dummy = any(k in excel_path().name.lower() for k in ("dummy", "sample"))
# Mientras se desarrolla, el rol se elige en la barra lateral. El inicio de sesión (ui/login.py, wm/auth.resolve_user)
# queda sin conectar: para volver a usarlo, guardar en st.session_state["_login_slot"] y ["auth"] como antes.

with st.sidebar:
    st.markdown("<div class='brand'>Advisory and</div><div class='brand-sub'>Brokerage</div>", unsafe_allow_html=True)
    role = st.selectbox("Rol", list(users_cfg["roles"]), key="role")
    advisor = None
    if role == ROLE_IA:
        options = advisors_from(view)
        if not options:
            st.error("No hay advisors en los datos (revisa la columna IA del Excel; ver «Calidad de datos»).")
        _names = view.drop_duplicates("advisor").set_index("advisor")["advisor_nombre"]
        advisor = (st.selectbox("Advisor", options, key="advisor", format_func=lambda a: str(_names.get(a, a)))
                   if options else None)
    user = advisor or (auth_cfg.get("md_usuario", ROLE_MD) if role == ROLE_MD else role)
    needs_pin = auth_cfg.get("pin_obligatorio", False) or user in (auth_cfg.get("pines") or {})
    pin = st.text_input("PIN", type="password", key="pin") if needs_pin else None
    if not check_pin(user, pin, auth_cfg):
        st.warning("Ingresa tu PIN para continuar.")
        st.stop()

modulos = modules_for(role, users_cfg)
with st.sidebar:
    if st.session_state.get("modulo") not in modulos:
        st.session_state.pop("modulo", None)
    modulo = (st.radio("Módulo", modulos, key="modulo", label_visibility="collapsed") if len(modulos) > 1
              else modulos[0])
    seccion = {MODULO_ESTRATEGIA: SECCION_ESTRATEGIA, MODULO_AFP: SECCION_AFP}.get(modulo, modulo)
    st.markdown(f"<div class='nav-section'>{seccion}</div>", unsafe_allow_html=True)
    if modulo == MODULO_CLIENT_PORTAL:
        moneda = st.radio("Moneda", ["CLP", "USD", "CAD"], horizontal=True, key="moneda")
        pages = PAGES_IA if role == ROLE_IA else PAGES_MD
    else:
        moneda = st.session_state.get("moneda", "CLP")
        pages = PAGES_AFP if modulo == MODULO_AFP else PAGES_ESTRATEGIA
    labels = list(pages)
    if st.session_state.get("nav") not in labels:
        st.session_state.pop("nav", None)
    nav = st.radio("Navegación", labels, key="nav", label_visibility="collapsed")

    if is_dummy:
        st.markdown("<div class='tag'>Datos dummy (sintéticos), no son datos reales</div>", unsafe_allow_html=True)
    if not store_ok:
        st.caption("Base de datos no disponible: comentarios y feedback deshabilitados.")
    st.caption(f"Versión {version_actual()}")
    with st.expander("Calidad de datos"):
        shown = [i for i in issues if i.level != "info"] or issues
        for i in sorted(shown, key=lambda i: ["error", "warning", "info"].index(i.level))[:30]:
            st.caption(f"{ {'error': 'Error', 'warning': 'Aviso', 'info': 'Info'}[i.level] }: {i.message}")

ctx = Ctx(ds=ds, view=view, issues=issues, store=store, store_ok=store_ok, role=role, advisor=advisor,
          user=user, hoy=hoy, moneda=moneda, fx=derive_fx(view), page=nav)
feedback.sidebar_box(ctx)
pages[nav].render(ctx)
