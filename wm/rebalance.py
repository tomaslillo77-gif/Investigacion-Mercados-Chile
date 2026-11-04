"""Plan de rebalanceo por fondo: lo que tiene el cliente vs lo que debería tener según su cartera modelo."""
import pandas as pd

COLUMNAS = ["fondo", "serie_actual", "serie_modelo", "valor_actual", "pct_actual", "pct_modelo",
            "dif_pp", "ajuste_clp", "accion"]


def _modelo(carteras: pd.DataFrame, arquitectura: str | None, perfil: str | None) -> pd.DataFrame | None:
    if not arquitectura or not perfil or "peso_objetivo" not in carteras.columns:
        return None
    m = carteras[(carteras["arquitectura"] == arquitectura) & (carteras["perfil"] == perfil)]
    m = m[m["peso_objetivo"].fillna(0) > 0]
    if m.empty:
        return None
    g = m.groupby("diccionario").agg(peso=("peso_objetivo", "sum"), serie_modelo=("serie", "first"))
    g["peso"] = g["peso"] / g["peso"].sum() * 100
    return g


def plan_rebalanceo(pos_cliente: pd.DataFrame, carteras: pd.DataFrame, arquitectura: str | None,
                    perfil: str | None, base_clp: float | None = None, tolerancia_pp: float = 1.0) -> pd.DataFrame | None:
    """None si no hay cartera modelo comparable. Dif/ajuste positivos = comprar, negativos = vender.
    Los porcentajes son sobre el valor de las posiciones (o sobre `base_clp` si el cliente no tiene posiciones)."""
    modelo = _modelo(carteras, arquitectura, perfil)
    if modelo is None:
        return None
    catalogo = carteras.drop_duplicates("isin").set_index("isin")
    pos = pos_cliente.copy()
    fondo = pos["isin"].map(catalogo["diccionario"]) if "diccionario" in catalogo.columns else pd.Series(index=pos.index, dtype=object)
    pos["fondo"] = fondo.where(fondo.notna(), pos["instrumento"]).fillna("Sin nombre")
    pos["serie"] = pos["isin"].map(catalogo["serie"]) if "serie" in catalogo.columns else None
    actual = pos.groupby("fondo").agg(valor=("valor_clp", "sum"),
                                      serie=("serie", lambda s: ", ".join(sorted({str(x) for x in s.dropna()})) or None))
    total = float(actual["valor"].sum())
    base = total if total > 0 else float(base_clp or 0.0)
    fondos = list(dict.fromkeys([*modelo.index, *actual.index]))
    rows = []
    for f in fondos:
        valor = float(actual["valor"].get(f, 0.0))
        pct_a = valor / base * 100 if base > 0 else 0.0
        pct_m = float(modelo["peso"].get(f, 0.0))
        dif = pct_m - pct_a
        accion = "Comprar" if dif >= tolerancia_pp else "Vender" if dif <= -tolerancia_pp else "Mantener"
        rows.append({"fondo": f, "serie_actual": actual["serie"].get(f), "serie_modelo": modelo["serie_modelo"].get(f),
                     "valor_actual": valor, "pct_actual": pct_a, "pct_modelo": pct_m, "dif_pp": dif,
                     "ajuste_clp": dif / 100 * base, "accion": accion})
    out = pd.DataFrame(rows, columns=COLUMNAS)
    return out.reindex(out["ajuste_clp"].abs().sort_values(ascending=False).index).reset_index(drop=True)
