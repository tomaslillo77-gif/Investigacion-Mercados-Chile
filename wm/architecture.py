from dataclasses import dataclass

import pandas as pd

from wm.exposure import PREFIJO_PERSONALIZADA


@dataclass
class ArchInference:
    arquitectura: str | None
    cobertura: float
    inferida: bool


def infer_architecture(pos_cliente: pd.DataFrame, carteras: pd.DataFrame,
                       min_cobertura: float = 0.60, declarada: str | None = None) -> ArchInference:
    total = float(pos_cliente["valor_clp"].sum()) if len(pos_cliente) else 0.0
    coberturas: dict[str, float] = {}
    if total > 0 and "arquitectura" in carteras.columns:
        # con arquitectura declarada solo se mide esa; sin declarar, se infiere entre los modelos de la casa (no entre los portafolios de otros clientes)
        grupos = carteras[carteras["arquitectura"] == declarada] if declarada else carteras[~carteras["arquitectura"].astype(str).str.startswith(PREFIJO_PERSONALIZADA)]
        for arq, grp in grupos.groupby("arquitectura"):
            held = pos_cliente[pos_cliente["isin"].isin(set(grp["isin"]))]["valor_clp"].sum()
            coberturas[arq] = float(held) / total
    if declarada:
        return ArchInference(declarada, coberturas.get(declarada, 0.0), False)
    if not coberturas:
        return ArchInference(None, 0.0, True)
    best = max(coberturas, key=coberturas.get)
    cob = coberturas[best]
    return ArchInference(best if cob >= min_cobertura else None, cob, True)
