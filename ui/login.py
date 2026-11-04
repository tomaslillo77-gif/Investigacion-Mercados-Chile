"""Inicio de sesión en la parte superior derecha: el usuario determina el rol y, con él, qué vistas se desbloquean."""
import streamlit as st

from wm.auth import advisors_from, check_login, resolve_user


def _login(view, pin_cfg, user_cfg) -> None:
    user = resolve_user(st.session_state.get("login_user"), view, user_cfg)
    if user is None:
        st.session_state["login_error"] = "Usuario no encontrado."
    elif not check_login(user, st.session_state.get("login_pin"), user_cfg, pin_cfg):
        st.session_state["login_error"] = "Contraseña incorrecta."
    else:
        st.session_state.pop("login_error", None)
        for k in ("nav", "modulo", "login_user", "login_pin"):
            st.session_state.pop(k, None)
        st.session_state["auth"] = user


def _logout() -> None:
    for k in ("auth", "nav", "modulo"):
        st.session_state.pop(k, None)


def render_control(view, pin_cfg, user_cfg, dummy: bool) -> None:
    auth = st.session_state.get("auth")
    if auth:
        with st.popover(f"{auth['nombre']} · {auth['rol']}"):
            st.caption(f"Sesión iniciada como {auth['nombre']} ({auth['rol']}).")
            st.button("Cerrar sesión", key="logout", on_click=_logout)
        return
    with st.popover("Iniciar sesión"):
        st.text_input("Usuario", key="login_user")
        st.text_input("Contraseña", type="password", key="login_pin")
        st.button("Entrar", key="login_go", on_click=_login, args=(view, pin_cfg, user_cfg))
        if st.session_state.get("login_error"):
            st.error(st.session_state["login_error"])
        if dummy:
            names = view.drop_duplicates("advisor").set_index("advisor")["advisor_nombre"]
            demo = [*user_cfg.get("usuarios", {}), *[str(names.get(a, a)) for a in advisors_from(view)]]
            st.caption("Demo: " + ", ".join(demo) + f". Contraseña: {user_cfg.get('pin_por_defecto', '')}")
