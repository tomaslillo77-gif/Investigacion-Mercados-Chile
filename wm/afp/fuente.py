"""Descarga y parseo de los CSV de collabmarket/data_afp (valor cuota y patrimonio por AFP y fondo)."""
import io
import urllib.request
from collections.abc import Callable

import pandas as pd

FONDOS = ["A", "B", "C", "D", "E"]


class FuenteAfpNoDisponible(Exception):
    pass


def parsear(texto: str) -> pd.DataFrame:
    """CSV con `;` y coma decimal -> ancho: índice Fecha, una columna float por AFP."""
    try:
        df = pd.read_csv(io.StringIO(texto), sep=";", decimal=",")
    except Exception as e:
        raise FuenteAfpNoDisponible(f"Respuesta no es un CSV de AFP: {e}") from e
    df.columns = [str(c).strip() if i == 0 else str(c).strip().upper() for i, c in enumerate(df.columns)]
    if df.columns[0].lower() != "fecha":
        raise FuenteAfpNoDisponible("La respuesta no trae la columna Fecha (¿el repositorio cambió de formato?).")
    df = df.rename(columns={df.columns[0]: "Fecha"})
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df = df.dropna(subset=["Fecha"]).set_index("Fecha").sort_index()
    df = df[~df.index.duplicated(keep="last")]   # una fecha repetida no debe duplicar el patrimonio al sumar
    return df.apply(pd.to_numeric, errors="coerce")


def a_largo(ancho: pd.DataFrame, fondo: str) -> pd.DataFrame:
    largo = ancho.rename_axis("fecha").reset_index().melt(id_vars="fecha", var_name="afp", value_name="valor")
    largo = largo.dropna(subset=["valor"])
    largo.insert(1, "fondo", fondo)
    return largo[["fecha", "fondo", "afp", "valor"]].reset_index(drop=True)


def _leer_url(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8")


def descargar(cfg: dict, leer: Callable[[str], str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(valor_cuota, patrimonio) en formato largo para los 5 fondos, con la ventana de años aplicada."""
    leer = leer or _leer_url
    base = cfg["url_base"].rstrip("/")
    salida = {}
    for prefijo, nombre in (("vcf", "valor_cuota"), ("patf", "patrimonio")):
        partes = []
        for f in FONDOS:
            url = f"{base}/{prefijo}{f}.csv"
            try:
                texto = leer(url)
            except Exception as e:
                raise FuenteAfpNoDisponible(f"No se pudo leer {url}: {e}") from e
            partes.append(a_largo(parsear(texto), f))
        salida[nombre] = pd.concat(partes, ignore_index=True)
    ultima = salida["valor_cuota"]["fecha"].max()
    desde = ultima - pd.DateOffset(years=int(cfg["ventana_anios"]))
    return tuple(df[df["fecha"] >= desde].reset_index(drop=True) for df in salida.values())
