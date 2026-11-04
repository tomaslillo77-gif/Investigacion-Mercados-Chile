"""Fotos de la CMF con fecha de corte: una carpeta AAAA-MM-DD por corte, nunca se sobrescribe otro corte."""
import shutil
from datetime import date
from pathlib import Path

import pandas as pd

from wm.mercado.schema import Foto

_ARCHIVOS = ("series", "cartera", "tendencias")


def _carpeta(base: Path, fecha: date) -> Path:
    return Path(base) / fecha.isoformat()


def guardar_foto(foto: Foto, base: Path) -> Path:
    destino = _carpeta(base, foto.fecha_corte)
    if destino.exists():  # recargar el mismo corte reemplaza solo esa carpeta
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    for nombre in _ARCHIVOS:
        getattr(foto, nombre).to_csv(destino / f"{nombre}.csv", index=False, encoding="utf-8")
    return destino


def listar_fotos(base: Path) -> list[date]:
    base = Path(base)
    if not base.exists():
        return []
    fechas = []
    for p in base.iterdir():
        try:
            if p.is_dir() and (p / "series.csv").exists():
                fechas.append(date.fromisoformat(p.name))
        except ValueError:
            continue
    return sorted(fechas)


def cargar_foto(base: Path, fecha: date | None = None) -> Foto | None:
    fechas = listar_fotos(base)
    if not fechas:
        return None
    fecha = fecha or fechas[-1]
    if fecha not in fechas:
        return None
    carpeta = _carpeta(base, fecha)
    d = {n: pd.read_csv(carpeta / f"{n}.csv", dtype={"fm_serie": str}) for n in _ARCHIVOS}
    return Foto(fecha, d["series"], d["cartera"], d["tendencias"])
