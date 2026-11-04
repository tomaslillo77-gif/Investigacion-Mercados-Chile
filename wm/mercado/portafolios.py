"""Portafolios por arquitectura y perfil: de dónde sale cada uno y cómo se ven sus exposiciones.

- Cartera Gestionada: fondos mutuos Scotia de la CMF (config/carteras_fondos_mutuos_scotia.yaml).
- Abierta USD: fondos internacionales con datos de Yahoo Finance (config/carteras_usd.yaml).
- Abierta Pesos y Local: el modelo del catálogo, con datos de la CMF o de Yahoo donde hay equivalencia.
"""
import pandas as pd

from wm.columns import MONEDA_COLS, RF_COLS
from wm.config import load_config
from wm.mercado.carteras import COLUMNAS, MONEDAS, _METRICAS, armar_cartera, armar_cartera_yahoo
from wm.mercado.internacionales import isin_base
from wm.mercado.modelo import _num, agrupar_modelo
from wm.mercado.schema import Foto

ARQUITECTURAS = ["cerrada_pesos", "abierta_dolares", "abierta_pesos", "abierta_local"]
EXPO_COLS = ["fondo", "beneficio", "act_rv", "act_rf", "act_alt", "mon_usd", "mon_clp", "mon_uf", "mon_otras"]


def _vacia() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNAS)


def _armar_catalogo(arq: str, perfil: str, carteras: pd.DataFrame, equiv: pd.DataFrame, foto: Foto | None,
                    yahoo: pd.DataFrame | None) -> pd.DataFrame:
    """El modelo del catálogo (pesos del Excel). Cada fondo toma sus datos de la CMF si tiene equivalencia, si no de Yahoo
    por ISIN, y si no queda 'Sin datos'. La serie que se muestra es la del modelo."""
    perfil_cat = next((p for p in carteras["perfil"].dropna().unique() if str(p).upper() == perfil), None)
    if perfil_cat is None:
        return _vacia()
    m = agrupar_modelo(carteras, arq, perfil_cat)
    if m.empty:
        return _vacia()
    cruce = {(r["instrumento_catalogo"], str(r["serie_catalogo"])): (int(r["fo_run"]), str(r["fm_serie"]))
             for _, r in equiv.iterrows() if pd.notna(r.get("fo_run")) and pd.notna(r.get("fm_serie"))}
    cmf = {} if foto is None else {(int(r["fo_run"]), str(r["fm_serie"])): r for _, r in foto.series.iterrows()}
    yh = {} if yahoo is None else {r["isin"]: r for _, r in yahoo.iterrows() if r["estado"] == "Yahoo"}
    filas = []
    for _, r in m.iterrows():
        base = {"clase": r["clase"], "subactivo": r["subactivo"], "fondo": r["instrumento"], "serie": r["serie"],
                "fo_run": None, "peso": r["peso"], "moneda": r["moneda"] if isinstance(r["moneda"], str) else "Sin dato"}
        k = cruce.get((r["instrumento"], r["serie"]))
        if k and k in cmf:
            f = cmf[k]
            filas.append({**base, "fo_run": k[0], "moneda": MONEDAS.get(str(f.get("moneda_funcional")), base["moneda"]),
                          **{c: pd.to_numeric(f[c], errors="coerce") for c in _METRICAS}, "estado": "CMF"})
            continue
        y = yh.get(isin_base(r["isin"]))
        if y is not None:
            filas.append({**base, "moneda": y["moneda"] if isinstance(y["moneda"], str) else base["moneda"],
                          "rent_ytd": y["rent_ytd"], "rent_1a": y["rent_1a"], "rent_3a": y["rent_3a"], "tac": y["costo"],
                          "patrimonio": y["patrimonio"], "estado": "Yahoo"})
            continue
        filas.append({**base, **{c: float("nan") for c in _METRICAS}, "estado": "Sin datos"})
    return pd.DataFrame(filas, columns=COLUMNAS)


def armar(arq: str, perfil: str, carteras: pd.DataFrame, equiv: pd.DataFrame, foto: Foto | None,
          yahoo: pd.DataFrame | None) -> tuple[pd.DataFrame, str]:
    """Cartera del perfil (normalizado, p. ej. 'DEFENSIVO') en la arquitectura, y su fuente: 'CMF', 'Yahoo' o 'Catálogo'."""
    if arq == "cerrada_pesos":
        return armar_cartera(perfil, load_config("carteras_fondos_mutuos_scotia"), foto), "CMF"
    if arq == "abierta_dolares":
        return armar_cartera_yahoo(perfil, load_config("carteras_usd"), yahoo), "Yahoo"
    return _armar_catalogo(arq, perfil, carteras, equiv, foto, yahoo), "Catálogo"


def _fondo_a_nivel_de_valor_cuota(r: pd.Series) -> dict:
    """Fondo que no está en el catálogo: 100 % en su clase y en la moneda de su valor cuota; sin beneficio tributario."""
    mon = {"CLP": "mon_clp", "USD": "mon_usd", "UF": "mon_uf"}.get(str(r["moneda"]))
    return {"beneficio": "—", "act_rv": float(r["clase"] == "Renta variable"), "act_rf": float(r["clase"] == "Renta fija"),
            "act_alt": float(r["clase"] == "Activos alternativos"),
            **{c: float(c == mon) for c in ("mon_usd", "mon_clp", "mon_uf", "mon_otras")}}


def exposiciones_cartera(c: pd.DataFrame, carteras: pd.DataFrame) -> pd.DataFrame:
    """Beneficio tributario y exposición subyacente (por activo y por moneda) de cada fondo de la cartera `c`. Los fondos
    que están en el catálogo traen sus porcentajes; los demás (por ejemplo, los Scotia) quedan a nivel de valor cuota."""
    filas = []
    for _, r in c.iterrows():
        rows = carteras[carteras["instrumento"] == r["fondo"]]
        if rows.empty:
            filas.append({"fondo": r["fondo"], **_fondo_a_nivel_de_valor_cuota(r)})
            continue
        misma = rows[rows["serie"].astype(str) == str(r["serie"])]
        fila = (misma if not misma.empty else rows).iloc[0]
        if not misma.empty:
            b = fila.get("beneficio_tributario")
        else:  # la serie de la cartera no es del catálogo (p. ej. un ticker): el beneficio más frecuente del fondo
            b = rows["beneficio_tributario"].dropna().mode()
            b = b.iloc[0] if not b.empty else None
        filas.append({"fondo": r["fondo"], "beneficio": "—" if b in (None, "-", "nan") or pd.isna(b) else str(b),
                      "act_rv": _num(fila, "pct_renta_variable"), "act_rf": sum(_num(fila, k) for k in RF_COLS),
                      "act_alt": _num(fila, "pct_alternativos"),
                      **{f"mon_{k.lower()}": _num(fila, col) for k, col in MONEDA_COLS.items()}})
    return pd.DataFrame(filas, columns=EXPO_COLS)
