from dataclasses import dataclass

import pandas as pd


@dataclass
class SerieFinding:
    isin: str
    fondo: str
    serie_actual: str | None
    serie_modelo: str | None
    comision_actual: float | None
    comision_modelo: float | None
    es_mala: bool
    motivo: str
    isin_modelo: str | None = None


def _num(v) -> float | None:
    return None if pd.isna(v) else float(v)


def evaluate_series(pos_cliente: pd.DataFrame, carteras: pd.DataFrame,
                    arquitectura: str | None) -> list[SerieFinding]:
    """Compara la serie del cliente con la del modelo para el mismo fondo (columna diccionario)."""
    if arquitectura is None or not {"diccionario", "serie", "comision"} <= set(carteras.columns):
        return []
    catalogo = carteras.drop_duplicates("isin").set_index("isin")
    modelo = carteras[carteras["arquitectura"] == arquitectura]
    if "peso_objetivo" in modelo.columns:  # peso 0 = serie de catálogo, no parte del modelo
        modelo = modelo[modelo["peso_objetivo"].fillna(0) > 0]
    out: list[SerieFinding] = []
    for isin in pos_cliente["isin"].dropna().unique():
        if isin not in catalogo.index:
            continue  # sin información: no se marca
        act = catalogo.loc[isin]
        fondo = act["diccionario"]
        candidatos = modelo[modelo["diccionario"] == fondo].drop_duplicates("isin")
        if candidatos.empty:
            continue
        if isin in set(candidatos["isin"]):
            m = candidatos[candidatos["isin"] == isin].iloc[0]
            out.append(SerieFinding(isin, fondo, act["serie"], m["serie"], _num(act["comision"]),
                                    _num(m["comision"]), False, "Serie del modelo", isin))
            continue
        m = candidatos.sort_values("comision").iloc[0]
        ca, cm = _num(act["comision"]), _num(m["comision"])
        motivos = []
        if ca is not None and cm is not None and ca > cm:
            motivos.append(f"comisión {ca:.2%} > {cm:.2%} del modelo")
        if act["serie"] != m["serie"]:
            motivos.append(f"serie {act['serie']} distinta a {m['serie']} del modelo")
        out.append(SerieFinding(isin, fondo, act["serie"], m["serie"], ca, cm,
                                bool(motivos), "; ".join(motivos) or "Equivalente al modelo", m["isin"]))
    return out
