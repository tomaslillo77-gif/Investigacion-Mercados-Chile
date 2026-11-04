"""Bloomberg: solo disponible en el computador del trabajo (Terminal abierta y `blpapi` instalado).

Para conectarlo: instalar blpapi, completar `ticker_bloomberg` en config/equivalencias_fondos.csv e implementar
los tres métodos con BDP (datos actuales) y BDH (histórico). Campos a pedir y su destino:
  PX_LAST           -> precios.valor
  CHG_PCT_YTD       -> rentabilidades.rent_ytd
  CHG_PCT_1M / 3M   -> rentabilidades.rent_1m / rent_3m
  CHG_PCT_1YR       -> rentabilidades.rent_1a
  FUND_EXPENSE_RATIO -> costo anual del fondo (se agrega a la tabla de series cuando exista el adaptador)
"""
from datetime import date
from typing import Sequence

import pandas as pd

from wm.mercado.fuentes.base import FuenteNoDisponible

_MSG = "Bloomberg no está conectado: requiere el paquete blpapi y una Terminal abierta (solo en el computador del trabajo)."


class BloombergFuente:
    nombre = "bloomberg"

    def rentabilidades(self, ids: Sequence[str]) -> pd.DataFrame | None:
        raise FuenteNoDisponible(_MSG)

    def precios(self, ids: Sequence[str], desde: date) -> pd.DataFrame | None:
        raise FuenteNoDisponible(_MSG)

    def composicion(self, ids: Sequence[str]) -> pd.DataFrame | None:
        raise FuenteNoDisponible(_MSG)
