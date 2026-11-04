"""CMF vía mcp-cmf-chile (MIT, gratis) para valor cuota diario de fondos nacionales. Por evaluar: parte de sus datos sale
de scraping de endpoints web de la CMF, que pueden cambiar. Requiere la clave CMF_API_KEY (gratuita, la entrega la CMF)."""
from datetime import date
from typing import Sequence

import pandas as pd

from wm.mercado.fuentes.base import FuenteNoDisponible

_MSG = "La API de la CMF no está conectada: falta la clave CMF_API_KEY y evaluar el adaptador (mcp-cmf-chile)."


class CmfApiFuente:
    nombre = "cmf_api"

    def rentabilidades(self, ids: Sequence[str]) -> pd.DataFrame | None:
        raise FuenteNoDisponible(_MSG)

    def precios(self, ids: Sequence[str], desde: date) -> pd.DataFrame | None:
        raise FuenteNoDisponible(_MSG)

    def composicion(self, ids: Sequence[str]) -> pd.DataFrame | None:
        raise FuenteNoDisponible(_MSG)
