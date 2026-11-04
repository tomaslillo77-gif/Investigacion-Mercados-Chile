from dataclasses import dataclass
from typing import Literal

import pandas as pd

from wm.columns import (MONEDA_COLS, OPTIONAL_CLIENT, PERFILES_NORM, RV_TOTAL, rv_columns)
from wm.loader import Dataset

TOL = 0.005


@dataclass
class Issue:
    level: Literal["error", "warning", "info"]
    sheet: str
    message: str


def _fund_name(row: pd.Series) -> str:
    return str(row.get("diccionario", row.name))


def validate(ds: Dataset) -> list[Issue]:
    out: list[Issue] = []
    for sheet in ds.missing_sheets:
        out.append(Issue("error", sheet, f"Falta la hoja '{sheet}'; los widgets que dependen de ella no se muestran."))
    if ds.duplicate_ruts:
        out.append(Issue("warning", "clientes", "RUT duplicados (se usa la primera fila): " + ", ".join(ds.duplicate_ruts)))

    for col in ds.missing_required:
        out.append(Issue("error", "clientes", f"Falta la columna requerida '{col}' en la hoja de clientes."))
    for col, n in ds.invalid_cells.items():
        out.append(Issue("warning", "clientes", f"{n} celda(s) no numérica(s) en {col}; se ignoran."))
    c = ds.clientes
    for col in OPTIONAL_CLIENT:
        if col not in c.columns:
            out.append(Issue("info", "clientes", f"Columna opcional ausente: {col}"))
    if "nombre_cliente" not in c.columns:
        out.append(Issue("info", "clientes", "El Excel no trae nombre_cliente / tipo_persona / nombre_advisor: se muestran nombres ficticios."))
    if "servicio" in c.columns and (c["servicio"] == "Sin clasificar").any():
        n = int((c["servicio"] == "Sin clasificar").sum())
        out.append(Issue("warning", "clientes", f"{n} cliente(s) con servicio 'Sin clasificar'"))
    if "perfil_norm" in c.columns:
        bad = sorted({str(v) for v in c["perfil_norm"].dropna() if str(v) not in PERFILES_NORM})
        if bad:
            out.append(Issue("warning", "clientes", "Perfiles fuera de los cinco oficiales: " + ", ".join(bad)))

    k = ds.carteras
    if {"arquitectura", "perfil", "peso_objetivo"} <= set(k.columns):
        sums = k.groupby(["arquitectura", "perfil"])["peso_objetivo"].sum()
        for (arq, perfil), total in sums.items():
            if abs(total - 1) > TOL:
                out.append(Issue("warning", "carteras", f"Pesos del modelo {arq} × {perfil} suman {total:.2f}, no 1.00"))

    rvc = [col for col in rv_columns().values() if col in k.columns]
    if RV_TOTAL in k.columns and rvc:
        diff = (k[rvc].fillna(0).sum(axis=1) - k[RV_TOTAL].fillna(0)).abs()
        for idx in k.index[diff > TOL]:
            out.append(Issue("error", "carteras", f"{_fund_name(k.loc[idx])}: las categorías de RV no suman {RV_TOTAL}"))

    mcols = list(MONEDA_COLS.values())
    if all(col in k.columns for col in mcols):
        diff = (k[mcols].fillna(0).sum(axis=1) - 1).abs()
        for idx in k.index[diff > TOL]:
            out.append(Issue("error", "carteras", f"{_fund_name(k.loc[idx])}: la exposición de moneda no suma 100%"))

    if "pct_rf_local" in k.columns and MONEDA_COLS["UF"] in k.columns:
        bad = k[k[MONEDA_COLS["UF"]].fillna(0) > k["pct_rf_local"].fillna(0) + TOL]
        for idx in bad.index:
            out.append(Issue("error", "carteras", f"{_fund_name(k.loc[idx])}: UF mayor que la renta fija local; se excluye del cálculo de UF"))
    return out
