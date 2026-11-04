"""Evolución de un fondo: patrimonio y partícipes (Tendencias) y cambio de rentabilidad entre fotos."""
from datetime import date
from pathlib import Path

import pandas as pd

from wm.mercado.schema import Foto
from wm.mercado.snapshots import cargar_foto, listar_fotos


def serie_patrimonio(foto: Foto, fo_run: int, fm_serie: str) -> pd.DataFrame:
    t = foto.tendencias
    t = t[(t["fo_run"] == fo_run) & (t["fm_serie"].astype(str) == str(fm_serie))]
    return t.sort_values("fecha_mes")[["fecha_mes", "patrimonio", "participes"]].reset_index(drop=True)


def cambio_entre_fotos(base: Path, fo_run: int, fm_serie: str) -> pd.DataFrame:
    filas = []
    for f in listar_fotos(base):
        s = cargar_foto(base, f).series
        s = s[(s["fo_run"] == fo_run) & (s["fm_serie"].astype(str) == str(fm_serie))]
        if s.empty:
            continue
        r = s.iloc[0]
        filas.append({"fecha_corte": f, "rent_1a": r["rent_1a"], "rent_ytd": r["rent_ytd"], "tac": r["tac"]})
    cols = ["fecha_corte", "rent_1a", "rent_ytd", "tac", "delta_rent_1a"]
    if not filas:
        return pd.DataFrame(columns=cols)
    d = pd.DataFrame(filas)
    d["delta_rent_1a"] = d["rent_1a"].astype(float).diff()
    return d[cols]
