"""Nombres canónicos de columnas opcionales y helpers compartidos."""
import unicodedata

from wm.config import load_config

OPTIONAL_CLIENT = ["ultimo_contacto", "tiene_wealth_plan", "share_of_wallet_pct",
                   "desvio_modelo_pct", "aportes_periodo", "retiros_periodo", "arquitectura",
                   "rentabilidad_12m_pct", "comision_anual_clp", "comision_cobrada_clp",
                   "com_tra_renta_variable_clp", "com_tra_renta_fija_clp", "com_tra_intermediacion_clp",
                   "com_tra_allfunds_clp"]
RF_COLS = ["pct_rf_local", "pct_rf_high_yield_internacional", "pct_rf_investment_grade"]
RV_TOTAL = "pct_renta_variable"
ALT_COL = "pct_alternativos"
MONEDA_COLS = {"USD": "pct_moneda_usd", "CLP": "pct_moneda_clp",
               "UF": "pct_moneda_uf", "Otras": "pct_moneda_otras"}
PERFILES_NORM = {"PRESERVACION", "DEFENSIVO", "EQUILIBRADO", "CLASICO_60_40", "CRECIMIENTO"}


def rv_column(categoria: str) -> str:
    folded = "".join(c for c in unicodedata.normalize("NFD", categoria)
                     if unicodedata.category(c) != "Mn")
    return "pct_rv_" + folded.strip().lower().replace(" ", "_")


def rv_columns() -> dict[str, str]:
    return {c: rv_column(c) for c in load_config("categorias_rv")["categorias"]}


def breakdown_columns() -> list[str]:
    return RF_COLS + [RV_TOTAL, ALT_COL] + list(MONEDA_COLS.values()) + list(rv_columns().values())
