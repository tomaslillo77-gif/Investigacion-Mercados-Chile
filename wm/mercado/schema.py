"""Tablas normalizadas del módulo Estrategia. Las pantallas leen solo estas columnas, venga el dato de la fuente que venga."""
from dataclasses import dataclass
from datetime import date

import pandas as pd

SERIES_COLS = ["fo_run", "fm_serie", "nombre_fondo", "nombre_agf", "familia", "clase_inversionista", "moneda_funcional",
               "tac", "patrimonio", "participes", "rent_ytd", "rent_1a", "rent_3a", "rent_5a", "rent_10a"]
CARTERA_COLS = ["fo_run", "nombre_fondo", "emisor", "clasificacion", "pais", "peso"]  # peso en 0-1 por fondo
TENDENCIAS_COLS = ["fo_run", "fm_serie", "fecha_mes", "patrimonio", "participes", "tac"]

RENTAB_COLS = ["id", "fecha", "rent_1m", "rent_3m", "rent_ytd", "rent_1a", "rent_3a"]  # rent_3a anualizada
PRECIOS_COLS = ["id", "fecha", "valor"]
COMPOSICION_COLS = ["id", "emisor", "clasificacion", "pais", "peso"]


@dataclass
class Foto:
    """Una carga de la CMF a una fecha de corte (fin de mes)."""
    fecha_corte: date
    series: pd.DataFrame
    cartera: pd.DataFrame
    tendencias: pd.DataFrame
