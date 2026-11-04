"""Métricas de negocio para el Managing Director: AUM por fondo/arquitectura, rentabilidades, comisiones."""
import pandas as pd

SIN_DET = "Sin determinar"


def _fondo_series(posiciones: pd.DataFrame, carteras: pd.DataFrame) -> pd.Series:
    catalogo = carteras.drop_duplicates("isin").set_index("isin")["diccionario"] if "diccionario" in carteras.columns else pd.Series(dtype=object)
    nombre = posiciones["isin"].map(catalogo)
    return nombre.where(nombre.notna(), posiciones["instrumento"]).fillna("Sin nombre")


def aum_por_fondo(posiciones: pd.DataFrame, carteras: pd.DataFrame) -> pd.DataFrame:
    if posiciones.empty:
        return pd.DataFrame(columns=["fondo", "aum", "pct", "n_clientes"])
    df = posiciones.assign(fondo=_fondo_series(posiciones, carteras))
    g = df.groupby("fondo").agg(aum=("valor_clp", "sum"), n_clientes=("rut", "nunique")).reset_index()
    g["pct"] = g["aum"] / g["aum"].sum() * 100
    return g.sort_values("aum", ascending=False).reset_index(drop=True)[["fondo", "aum", "pct", "n_clientes"]]


def aum_por_arquitectura(view: pd.DataFrame, nombres: dict[str, str]) -> pd.DataFrame:
    arq = view["arquitectura"].map(lambda a: SIN_DET if pd.isna(a) else nombres.get(a, a))
    g = view.assign(arquitectura=arq).groupby("arquitectura")["aum_clp"].sum().reset_index(name="aum")
    g["pct"] = g["aum"] / g["aum"].sum() * 100
    return g.sort_values("aum", ascending=False).reset_index(drop=True)


def _client_rent(view: pd.DataFrame, posiciones: pd.DataFrame | None):
    """(rentabilidad % por cliente, peso por cliente, fuente) o None."""
    if "rentabilidad_12m_pct" in view.columns and view["rentabilidad_12m_pct"].notna().any():
        return view["rentabilidad_12m_pct"], view["aum_clp"], "Excel (rentabilidad 12 meses)"
    if posiciones is not None and "rent_no_realizada" in posiciones.columns and not posiciones.empty:
        p = posiciones.dropna(subset=["rent_no_realizada"])
        if p.empty:
            return None
        num = (p["rent_no_realizada"] * p["valor_clp"]).groupby(p["rut"]).sum()
        den = p["valor_clp"].groupby(p["rut"]).sum()
        rent = (num / den * 100).reindex(view["rut"])
        peso = den.reindex(view["rut"])
        return pd.Series(rent.values, index=view.index), pd.Series(peso.values, index=view.index), "Posiciones (rentabilidad no realizada)"
    return None


def _wavg(values: pd.Series, weights: pd.Series) -> float | None:
    ok = values.notna() & weights.notna() & (weights > 0)
    return float((values[ok] * weights[ok]).sum() / weights[ok].sum()) if ok.any() else None


def rentabilidad_por(view: pd.DataFrame, group: str, posiciones: pd.DataFrame | None) -> pd.DataFrame | None:
    src = _client_rent(view, posiciones)
    if src is None:
        return None
    rent, peso, fuente = src
    rows = []
    for key, idx in view.groupby(group).groups.items():
        r = _wavg(rent.loc[idx], peso.loc[idx])
        if r is not None:
            rows.append({"grupo": key, "rentabilidad_pct": r, "aum": float(view.loc[idx, "aum_clp"].sum()), "fuente": fuente})
    return pd.DataFrame(rows, columns=["grupo", "rentabilidad_pct", "aum", "fuente"]).sort_values(
        "rentabilidad_pct", ascending=False).reset_index(drop=True)


def rentabilidad_area(view: pd.DataFrame, posiciones: pd.DataFrame | None) -> tuple[float, str] | None:
    src = _client_rent(view, posiciones)
    if src is None:
        return None
    r = _wavg(src[0], src[1])
    return None if r is None else (r, src[2])


def _has_comisiones(view: pd.DataFrame) -> bool:
    return any(c in view.columns and view[c].notna().any() for c in ("comision_anual_clp", "comision_cobrada_clp"))


def comisiones_por(view: pd.DataFrame, group: str) -> pd.DataFrame | None:
    if not _has_comisiones(view):
        return None
    df = view.assign(_a=view.get("comision_anual_clp", 0.0), _c=view.get("comision_cobrada_clp", 0.0))
    g = df.groupby(group).agg(comision_anual=("_a", "sum"), comision_cobrada=("_c", "sum"), aum=("aum_clp", "sum")).reset_index()
    g = g.rename(columns={group: "grupo"})
    g["pct_cobrado"] = (g["comision_cobrada"] / g["comision_anual"] * 100).where(g["comision_anual"] > 0)
    g["tasa_pct"] = (g["comision_anual"] / g["aum"] * 100).where(g["aum"] > 0)
    return g.sort_values("comision_anual", ascending=False).reset_index(drop=True)


def comisiones_area(view: pd.DataFrame) -> dict | None:
    if not _has_comisiones(view):
        return None
    anual = float(view.get("comision_anual_clp", pd.Series(dtype=float)).sum())
    cobrada = float(view.get("comision_cobrada_clp", pd.Series(dtype=float)).sum())
    aum = float(view["aum_clp"].sum())
    return {"anual": anual, "cobrada": cobrada, "aum": aum,
            "tasa_pct": anual / aum * 100 if aum else None,
            "pct_cobrado": cobrada / anual * 100 if anual else None}
