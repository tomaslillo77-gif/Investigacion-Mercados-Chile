"""Nombres para mostrar. Si el Excel trae nombre_cliente / tipo_persona / nombre_advisor se usan;
si no, se generan nombres FICTICIOS y estables, en inglés y con la palabra «Dummy» (el Excel real solo trae códigos anonimizados)."""
import hashlib
import random
import re

import pandas as pd

from wm.config import load_config
from wm.exposure import es_personalizada

NATURAL, JURIDICA = "Persona natural", "Persona jurídica"
EMPRESA_TIPO = ["Holdings", "Capital", "Ventures", "Trading", "Partners", "Estates"]
EMPRESA_SUFIJO = ["Ltd.", "Inc.", "LLC"]


def _rng(key: str) -> random.Random:
    return random.Random(int(hashlib.sha256(key.encode()).hexdigest(), 16))


def format_rut(rut) -> str:
    """'RUT_01234567' -> '123.456-7': el último dígito es el verificador y el resto el cuerpo, con puntos de miles.
    Si no tiene esa forma (por ejemplo 'RUT_1'), se devuelve tal cual."""
    m = re.fullmatch(r"(?:RUT_?)?(\d{2,})([\dK])", str(rut).strip().upper())
    if not m:
        return str(rut)
    cuerpo = f"{int(m.group(1)):,}".replace(",", ".")
    return f"{cuerpo}-{m.group(2)}"


def synthetic_cliente(rut: str) -> tuple[str, str]:
    """Nombre inventado y obvio (\"Dummy ...\") para que no se confunda con un cliente real."""
    r = _rng(f"cliente:{rut}")
    if r.random() < 0.65:
        return f"Dummy Client {r.randint(1000, 9999)}", NATURAL
    return f"Dummy {r.choice(EMPRESA_TIPO)} {r.randint(100, 999)} {r.choice(EMPRESA_SUFIJO)}", JURIDICA


def advisor_names(codes: list[str]) -> dict[str, str]:
    """Nombre inventado, único y estable para cada código de advisor: Dummy Advisor 01, 02..."""
    return {code: f"Dummy Advisor {i + 1:02d}" for i, code in enumerate(sorted(codes))}


def add_display_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    syn = out["rut"].map(synthetic_cliente)
    nombre = syn.map(lambda t: t[0])
    tipo = syn.map(lambda t: t[1])
    if "nombre_cliente" in out.columns:
        nombre = out["nombre_cliente"].where(out["nombre_cliente"].notna(), nombre)
    if "tipo_persona" in out.columns:
        tipo = out["tipo_persona"].where(out["tipo_persona"].notna(), tipo)
    out["nombre"], out["tipo_persona"] = nombre, tipo
    out["cliente_label"] = out["rut"].map(format_rut) + " " + out["nombre"]
    names = advisor_names([a for a in out["advisor"].dropna().unique()]) if "advisor" in out.columns else {}
    adv = out["advisor"].map(names) if "advisor" in out.columns else pd.Series(index=out.index, dtype=object)
    if "nombre_advisor" in out.columns:
        adv = out["nombre_advisor"].where(out["nombre_advisor"].notna(), adv)
    out["advisor_nombre"] = adv
    return out


class _NombresArquitectura(dict):
    """Nombre visible de cada arquitectura. Los portafolios definidos por el advisor («personalizada:<rut>») se muestran todos como «Personalizada»."""

    def __missing__(self, clave):
        return "Personalizada" if es_personalizada(clave) else clave

    def get(self, clave, defecto=None):
        return "Personalizada" if es_personalizada(clave) else super().get(clave, defecto)


def nombres_arquitecturas() -> dict:
    return _NombresArquitectura(load_config("arquitecturas")["nombres"])
