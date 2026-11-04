import hmac
import unicodedata

import pandas as pd


def check_pin(user: str, pin: str | None, cfg: dict) -> bool:
    expected = (cfg.get("pines") or {}).get(user)
    if expected is None:
        return not cfg.get("pin_obligatorio", False)
    return pin is not None and hmac.compare_digest(str(pin), str(expected))


def advisors_from(clientes: pd.DataFrame) -> list[str]:
    return sorted(clientes["advisor"].dropna().unique().tolist())


def can_edit_dato(existing_advisor: str | None, user: str, role: str) -> bool:
    if role == "Managing Director":
        return False
    return existing_advisor is None or existing_advisor == user


def can_edit_portafolio(advisor_del_cliente: str | None, advisor_usuario: str | None, role: str) -> bool:
    """El portafolio de un cliente lo define su advisor; el Managing Director lo ve, no lo edita (igual que los datos del cliente)."""
    return role == "Investment Advisor" and advisor_del_cliente is not None and advisor_del_cliente == advisor_usuario


def can_reassign(role: str) -> bool:
    """Solo el Managing Director cambia el advisor asignado a un cliente."""
    return role == "Managing Director"


def _fold(text) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(text).strip().casefold()) if unicodedata.category(c) != "Mn")


def resolve_user(text, view: pd.DataFrame, cfg: dict) -> dict | None:
    """Usuario que escribió quien inicia sesión: un usuario de la config, o un advisor (por código o por nombre).
    Devuelve {usuario, nombre, rol, advisor, pin_key} o None si no existe."""
    key = _fold(text)
    if not key:
        return None
    codes = advisors_from(view)
    for usuario, u in (cfg.get("usuarios") or {}).items():
        if key in (_fold(usuario), _fold(u["nombre"])):
            adv = u.get("advisor")
            adv = (codes[0] if codes else None) if adv == "primero" else (adv if adv in codes else None)
            if u["rol"] == "Investment Advisor" and adv is None:
                return None  # usuario de advisor sin advisor en los datos: no hay vista que mostrar
            return {"usuario": usuario, "nombre": u["nombre"], "rol": u["rol"], "advisor": adv, "pin_key": usuario,
                    "pin": u.get("pin")}
    names = view.drop_duplicates("advisor").set_index("advisor")["advisor_nombre"]
    for code in codes:
        if key in (_fold(code), _fold(names.get(code, code))):
            return {"usuario": code, "nombre": str(names.get(code, code)), "rol": "Investment Advisor",
                    "advisor": code, "pin_key": code, "pin": None}
    return None


def check_login(user: dict, pin: str | None, users_cfg: dict, pin_cfg: dict) -> bool:
    """Contraseña del usuario (la suya, o la por defecto); si no hay ninguna, rige el PIN de advisors.yaml."""
    expected = user.get("pin") or users_cfg.get("pin_por_defecto")
    if expected is None:
        return check_pin(user["pin_key"], pin, pin_cfg)
    return pin is not None and hmac.compare_digest(str(pin), str(expected))


def modules_for(rol: str, cfg: dict) -> list[str]:
    return list((cfg.get("roles") or {}).get(rol, []))
