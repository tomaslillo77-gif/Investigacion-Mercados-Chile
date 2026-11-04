"""Contrato común de las fuentes de mercado. Las pantallas nunca leen una fuente directamente."""
from datetime import date
from typing import Protocol, Sequence

import pandas as pd


class FuenteNoDisponible(RuntimeError):
    """La fuente no está conectada o instalada en este computador."""


class FuenteMercado(Protocol):
    """Cada método devuelve un DataFrame con las columnas de wm.mercado.schema (RENTAB_COLS, PRECIOS_COLS,
    COMPOSICION_COLS), o None si la fuente no ofrece ese dato. `id` es el identificador propio de la fuente:
    ticker (Yahoo, Bloomberg), id_riskamerica, o 'fo_run|fm_serie' (CMF)."""
    nombre: str

    def rentabilidades(self, ids: Sequence[str]) -> pd.DataFrame | None: ...

    def precios(self, ids: Sequence[str], desde: date) -> pd.DataFrame | None: ...

    def composicion(self, ids: Sequence[str]) -> pd.DataFrame | None: ...
