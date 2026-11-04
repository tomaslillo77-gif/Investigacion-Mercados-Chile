"""Modelo del catálogo (arquitectura y perfil) agrupado por clase de activo y subactivo, con beneficio tributario y la
exposición subyacente por activo y moneda de cada fondo."""
import pandas as pd

from wm.columns import MONEDA_COLS, RF_COLS, rv_columns
from wm.config import load_config

CLASES = ["Renta variable", "Renta fija", "Activos alternativos"]
_NOMBRE_SUB = {"USA": "Estados Unidos", "Latam": "Latinoamérica"}
COLUMNAS = ["clase", "subactivo", "instrumento", "serie", "isin", "moneda", "peso", "beneficio", "act_rv", "act_rf", "act_alt",
            "mon_usd", "mon_clp", "mon_uf", "mon_otras"]


def _num(r: pd.Series, col: str) -> float:
    v = pd.to_numeric(r.get(col), errors="coerce")
    return 0.0 if pd.isna(v) else float(v)


def clasificar(r: pd.Series) -> tuple[str, str]:
    """Una categoría por fondo, la dominante: clase por mayor exposición y subactivo por la mayor dentro de la clase."""
    rv, alt = _num(r, "pct_renta_variable"), _num(r, "pct_alternativos")
    rf = sum(_num(r, c) for c in RF_COLS)
    if alt >= rv and alt >= rf and alt > 0:
        return "Activos alternativos", "Alternativos"
    if rv >= rf and rv > 0:
        mejor = max(rv_columns().items(), key=lambda kv: _num(r, kv[1]))[0]
        return "Renta variable", _NOMBRE_SUB.get(mejor, mejor)
    internacional = _num(r, "pct_rf_high_yield_internacional") + _num(r, "pct_rf_investment_grade")
    return "Renta fija", "Internacional" if internacional > _num(r, "pct_rf_local") else "Local"


def agrupar_modelo(carteras: pd.DataFrame, arquitectura: str, perfil: str) -> pd.DataFrame:
    d = carteras[(carteras["arquitectura"] == arquitectura) & (carteras["perfil"] == perfil)]
    d = d[pd.to_numeric(d["peso_objetivo"], errors="coerce").fillna(0) > 0]  # series del catálogo que el modelo no usa
    if d.empty:
        return pd.DataFrame(columns=COLUMNAS)
    orden = load_config("carteras_fondos_mutuos_scotia")["orden"]
    filas = []
    for _, r in d.iterrows():
        clase, sub = clasificar(r)
        b = str(r.get("beneficio_tributario") or "-")
        filas.append({"clase": clase, "subactivo": sub, "instrumento": r["instrumento"], "serie": str(r["serie"]),
                      "isin": r.get("isin"), "moneda": r.get("moneda"),
                      "peso": _num(r, "peso_objetivo"), "beneficio": "—" if b in ("-", "nan", "None") else b,
                      "act_rv": _num(r, "pct_renta_variable"), "act_rf": sum(_num(r, c) for c in RF_COLS),
                      "act_alt": _num(r, "pct_alternativos"),
                      **{f"mon_{k.lower()}": _num(r, col) for k, col in MONEDA_COLS.items()}})
    m = pd.DataFrame(filas, columns=COLUMNAS)

    def clave(f):
        subs = orden.get(f["clase"], [])
        return (CLASES.index(f["clase"]), subs.index(f["subactivo"]) if f["subactivo"] in subs else len(subs))
    m["_o"] = [clave(f) for _, f in m.iterrows()]
    return m.sort_values("_o", kind="stable").drop(columns="_o").reset_index(drop=True)
