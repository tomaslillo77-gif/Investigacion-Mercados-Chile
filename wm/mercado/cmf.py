"""Lee los 4 Excel del Portal de Fondos Mutuos de la CMF y los deja como una Foto con fecha de corte."""
import calendar
from datetime import date
from pathlib import Path

import pandas as pd

from wm.mercado.schema import CARTERA_COLS, SERIES_COLS, TENDENCIAS_COLS, Foto

# clave en el nombre del archivo -> (hoja, columna con la fecha)
ARCHIVOS = {"rentabilidades": ("rentabilidades_por_serie_fondo", "fm_fecha"),
            "costos": ("datos_costos", "fm_fecha_num"),
            "tendencias": ("datos", "fecha_mes"),
            "carteras": ("datos", "fecha_mes")}


class ArchivoCMFFaltante(FileNotFoundError):
    pass


class FechasDesalineadas(ValueError):
    pass


def _buscar(carpeta: Path, clave: str) -> Path:
    for p in sorted(carpeta.glob("*.xlsx")):
        if clave in p.name.lower() and not p.name.startswith("~$"):
            return p
    raise ArchivoCMFFaltante(f"Falta el Excel de {clave} en {carpeta}. Descárgalo del Portal de Fondos Mutuos de la CMF.")


def _yyyymm(valor) -> int:
    return int(str(int(valor))[:6])


def leer_cmf(carpeta: Path) -> Foto:
    carpeta = Path(carpeta)
    d = {k: pd.read_excel(_buscar(carpeta, k), sheet_name=hoja) for k, (hoja, _) in ARCHIVOS.items()}
    cortes = {k: (_yyyymm(d[k][col].max()) if k == "tendencias" else _yyyymm(d[k][col].dropna().iloc[0]))
              for k, (_, col) in ARCHIVOS.items()}
    if len(set(cortes.values())) > 1:
        det = ", ".join(f"{k} {v}" for k, v in cortes.items())
        raise FechasDesalineadas(f"Los 4 Excel deben tener la misma fecha de corte (AAAAMM): {det}.")
    ym = next(iter(cortes.values()))
    fecha = date(ym // 100, ym % 100, calendar.monthrange(ym // 100, ym % 100)[1])

    rent = d["rentabilidades"].rename(columns={
        "rent_nominal_ytd": "rent_ytd", "rent_nominal_1a": "rent_1a", "rent_nominal_3a_ann": "rent_3a",
        "rent_nominal_5a_ann": "rent_5a", "rent_nominal_10a_ann": "rent_10a", "familia_estudios": "familia"})
    cost = d["costos"].rename(columns={"tac_sintetica": "tac", "pat_total": "patrimonio", "familia_estudios": "familia"})
    llave = ["fo_run", "fm_serie"]
    series = cost.merge(rent[llave + ["rent_ytd", "rent_1a", "rent_3a", "rent_5a", "rent_10a", "familia", "nombre_fondo",
                                      "nombre_agf"]], on=llave, how="outer", suffixes=("", "_r"))
    for c in ("familia", "nombre_fondo", "nombre_agf"):  # si la serie solo está en Rentabilidades
        series[c] = series[c].fillna(series[f"{c}_r"])

    t = d["tendencias"].rename(columns={"patrimonio_fm": "patrimonio", "participes_fm": "participes", "tac_total": "tac"})
    ultima = t.sort_values("fecha_mes").groupby(llave, as_index=False).last()[llave + ["participes"]]
    series = series.merge(ultima, on=llave, how="left")
    for c in SERIES_COLS:
        if c not in series:
            series[c] = pd.NA
    series = series[SERIES_COLS].astype({"fo_run": int})

    c = d["carteras"].rename(columns={"nombre_emisor": "emisor", "clasificacion_instrumentos_txt": "clasificacion",
                                      "nombre_pais_emisor": "pais"})
    c["peso"] = c["val_cierr"] / c.groupby("fo_run")["val_cierr"].transform("sum")
    return Foto(fecha, series.reset_index(drop=True), c[CARTERA_COLS].reset_index(drop=True),
                t[TENDENCIAS_COLS].reset_index(drop=True))
