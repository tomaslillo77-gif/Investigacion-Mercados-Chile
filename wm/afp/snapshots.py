"""Fotos de datos de AFP con fecha de corte: una carpeta AAAA-MM-DD por corte, nunca se sobrescribe otro corte."""
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from wm.afp.fuente import FONDOS

_ARCHIVOS = ("valor_cuota", "patrimonio")


class FechasDesalineadas(Exception):
    pass


@dataclass
class Foto:
    fecha_corte: date
    valor_cuota: pd.DataFrame   # largo: fecha, fondo, afp, valor
    patrimonio: pd.DataFrame


def _afp_en(df: pd.DataFrame, fondo: str, fecha) -> set:
    return set(df[(df["fondo"] == fondo) & (df["fecha"] == fecha)]["afp"])


def armar_foto(valor_cuota: pd.DataFrame, patrimonio: pd.DataFrame) -> Foto:
    """Valida que todos los fondos terminen el mismo día en valor cuota y patrimonio."""
    ult_vc = valor_cuota.groupby("fondo")["fecha"].max()
    ult_pat = patrimonio.groupby("fondo")["fecha"].max()
    fechas = set(ult_vc) | set(ult_pat)
    if set(ult_vc.index) != set(FONDOS) or set(ult_pat.index) != set(FONDOS):
        faltan = sorted((set(FONDOS) - set(ult_vc.index)) | (set(FONDOS) - set(ult_pat.index)))
        raise FechasDesalineadas(f"Faltan datos de los fondos {', '.join(faltan)} (archivo vacío o con fechas ilegibles).")
    if len(fechas) != 1:
        detalle = ", ".join(f"{n} {f}: {d:%Y-%m-%d}" for n, s in (("valor cuota", ult_vc), ("patrimonio", ult_pat))
                            for f, d in s.items())
        raise FechasDesalineadas(f"Los archivos no terminan el mismo día ({detalle}).")
    corte = fechas.pop()
    for f in FONDOS:   # el último día debe traer las mismas AFP en ambos archivos y no perder ninguna del día anterior
        en_corte = {n: _afp_en(df, f, corte) for n, df in (("valor cuota", valor_cuota), ("patrimonio", patrimonio))}
        if en_corte["valor cuota"] != en_corte["patrimonio"]:
            raise FechasDesalineadas(f"Fondo {f}: el último día ({corte:%Y-%m-%d}) trae AFP distintas en valor cuota y patrimonio.")
        for nombre, df in (("valor cuota", valor_cuota), ("patrimonio", patrimonio)):
            previas = df[(df["fondo"] == f) & (df["fecha"] < corte)]
            if previas.empty:
                continue
            perdidas = _afp_en(df, f, previas["fecha"].max()) - en_corte[nombre]
            if perdidas:
                raise FechasDesalineadas(f"Fondo {f}: el último día ({corte:%Y-%m-%d}) no trae {', '.join(sorted(perdidas))} "
                                         f"en {nombre} (fila incompleta o AFP que cerró ese día).")
    return Foto(corte.date(), valor_cuota, patrimonio)


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
            if p.is_dir() and (p / "valor_cuota.csv").exists():
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
    d = {n: pd.read_csv(carpeta / f"{n}.csv", parse_dates=["fecha"]) for n in _ARCHIVOS}
    return Foto(fecha, d["valor_cuota"], d["patrimonio"])
