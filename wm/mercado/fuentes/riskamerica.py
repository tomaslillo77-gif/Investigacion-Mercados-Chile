"""RiskAmerica: valor cuota al día de fondos nacionales. Pendiente confirmar acceso y formato (API o descarga).

Al conectarlo: `id_riskamerica` de config/equivalencias_fondos.csv es el `id`; `precios` devuelve el valor cuota diario
y `rentabilidades` las rentabilidades al día por serie.
"""
from datetime import date
from typing import Sequence

import pandas as pd

from wm.mercado.fuentes.base import FuenteNoDisponible

_MSG = "RiskAmerica no está conectado: falta confirmar el acceso (API o descarga) y completar id_riskamerica en las equivalencias."


class RiskAmericaFuente:
    nombre = "riskamerica"

    def rentabilidades(self, ids: Sequence[str]) -> pd.DataFrame | None:
        raise FuenteNoDisponible(_MSG)

    def precios(self, ids: Sequence[str], desde: date) -> pd.DataFrame | None:
        raise FuenteNoDisponible(_MSG)

    def composicion(self, ids: Sequence[str]) -> pd.DataFrame | None:
        raise FuenteNoDisponible(_MSG)
