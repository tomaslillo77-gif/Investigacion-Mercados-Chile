"""Costo de comisión de un cliente: ADC/ASE = costo ponderado de sus fondos + asesoría; TRA = comisión transaccional."""
from dataclasses import dataclass, field

import pandas as pd

from wm.config import load_config

FONDOS = "Fondos"


@dataclass
class Costo:
    total: float
    items: list[tuple[str, float]] = field(default_factory=list)
    base: float = 0.0               # AUM sobre el que se calculan los porcentajes
    nota: str | None = None

    @property
    def tasa_pct(self) -> float | None:
        return self.total / self.base * 100 if self.base else None


def costo_fondos(pos: pd.DataFrame, carteras: pd.DataFrame) -> tuple[float, float, float]:
    """(costo anual CLP, costo ponderado %, cobertura 0-1): suma de valor x comisión de la serie de cada fondo."""
    if pos.empty or not {"isin", "comision"} <= set(carteras.columns):
        return 0.0, 0.0, 0.0
    com = carteras.drop_duplicates("isin").set_index("isin")["comision"]
    valor = pos.groupby("isin")["valor_clp"].sum()
    rate = valor.index.map(com)
    ok = pd.Series(rate, index=valor.index).notna()
    cubierto = float(valor[ok].sum())
    total = float(valor.sum())
    if cubierto <= 0:
        return 0.0, 0.0, 0.0
    costo = float((valor[ok] * pd.Series(rate, index=valor.index)[ok]).sum())
    return costo, costo / cubierto * 100, cubierto / total


def costo_comision(row: pd.Series, pos: pd.DataFrame, carteras: pd.DataFrame) -> Costo | None:
    """None si el servicio no tiene desglose definido (solo ADC, ASE y TRA) o faltan los datos."""
    tarifas = load_config("tarifas")
    servicio, aum = row.get("servicio"), row.get("aum_clp")
    if servicio in tarifas["asesoria"]:
        fondos, ponderado, cob = costo_fondos(pos, carteras)
        base = float(aum) if pd.notna(aum) else float(pos["valor_clp"].sum())
        asesoria = base * float(tarifas["asesoria"][servicio])
        total = fondos + asesoria
        nota = None
        if pos.empty or cob <= 0:
            nota = "Sin posiciones con costo de serie: el total incluye solo la asesoría."
        elif cob < 0.995:
            nota = f"El costo de fondos se calculó sobre el {cob:.0%} de la cartera con costo de serie disponible."
        return Costo(total, [(FONDOS, fondos), (servicio, asesoria)], base, nota)
    if servicio == "TRA":
        cols = tarifas["transaccional"]
        vals = {p: row.get(c) for p, c in cols.items()}
        if all(pd.isna(v) for v in vals.values()):
            return None
        items = [(p, 0.0 if pd.isna(v) else float(v)) for p, v in vals.items()]
        total = sum(v for _, v in items)
        return Costo(total, items, float(aum) if pd.notna(aum) else 0.0)
    return None
