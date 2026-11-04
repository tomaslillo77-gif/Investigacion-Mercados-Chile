"""Índice de AFP por fondo, ponderado por patrimonio, y sus métricas de rentabilidad (nominal, en pesos)."""
import numpy as np
import pandas as pd

from wm.afp.fuente import FONDOS
from wm.afp.snapshots import Foto

_PLAZOS = {"rent_1m": (1, "months"), "rent_3m": (3, "months"), "rent_1a": (1, "years"),
           "rent_3a": (3, "years"), "rent_5a": (5, "years")}


def indice_fondo(vc: pd.DataFrame, pat: pd.DataFrame) -> pd.Series:
    """Índice base 100 de un fondo. `vc` y `pat` son anchos (fecha x AFP).

    Retorno del día = promedio de los retornos de cada AFP ponderado por su patrimonio del día previo con dato.
    Un hueco de días en una AFP se cobra el día que reaparece; una AFP sin retorno o sin patrimonio válido ese
    día no entra al peso; un día sin retornos deja el índice igual.
    """
    vc = vc.where(vc > 0)   # un valor cuota 0 o negativo es un dato malo: se trata como día sin dato
    pat = pat.reindex(index=vc.index, columns=vc.columns)
    retornos, pesos = {}, {}
    for afp in vc.columns:
        propia = vc[afp].dropna()
        retornos[afp] = propia.pct_change(fill_method=None)
        pesos[afp] = pat[afp].reindex(propia.index).shift(1)
    r = pd.DataFrame(retornos).reindex(vc.index)
    w = pd.DataFrame(pesos).reindex(vc.index)
    valido = np.isfinite(r) & w.notna() & (w > 0)
    w = w.where(valido)
    ponderado = (w * r.where(valido)).sum(axis=1) / w.sum(axis=1)
    return 100 * (1 + ponderado.fillna(0.0)).cumprod()


def _ancho(largo: pd.DataFrame, fondo: str) -> pd.DataFrame:
    return largo[largo["fondo"] == fondo].pivot_table(index="fecha", columns="afp", values="valor").sort_index()


def indice_de_foto(foto: Foto, fondo: str) -> pd.Series:
    vc = _ancho(foto.valor_cuota, fondo)
    return indice_fondo(vc, _ancho(foto.patrimonio, fondo))


def _antes_de(indice: pd.Series, limite: pd.Timestamp):
    previo = indice[indice.index <= limite]
    return None if previo.empty else float(previo.iloc[-1])


def metricas(indice: pd.Series) -> dict:
    """Rentabilidad a 1M, 3M, YTD, 1A, 3A y 5A (anualizada desde 3A); None si no hay historia suficiente."""
    ref, ultimo = indice.index[-1], float(indice.iloc[-1])
    out = {}
    for clave, (n, unidad) in _PLAZOS.items():
        base = _antes_de(indice, ref - pd.DateOffset(**{unidad: n}))
        if base is None or base <= 0:
            out[clave] = None
        else:
            r = ultimo / base
            out[clave] = r - 1 if unidad == "months" or n == 1 else r ** (1 / n) - 1
    base = _antes_de(indice, pd.Timestamp(year=ref.year - 1, month=12, day=31))
    out["rent_ytd"] = None if base is None or base <= 0 else ultimo / base - 1
    return {k: out[k] for k in ("rent_1m", "rent_3m", "rent_ytd", "rent_1a", "rent_3a", "rent_5a")}


def rent_anual(indice: pd.Series) -> pd.Series:
    """Rentabilidad por año calendario (el año en curso llega hasta la última fecha; el primer año parcial se omite)."""
    cierre = indice.groupby(indice.index.year).last()
    return (cierre / cierre.shift(1) - 1).dropna()


def patrimonio_total(foto: Foto, fondo: str) -> pd.Series:
    p = foto.patrimonio
    return p[p["fondo"] == fondo].groupby("fecha")["valor"].sum().sort_index()


def resumen(foto: Foto) -> pd.DataFrame:
    corte = pd.Timestamp(foto.fecha_corte)
    filas = []
    for f in FONDOS:
        pat = foto.patrimonio[(foto.patrimonio["fondo"] == f) & (foto.patrimonio["fecha"] == corte)]
        vc = foto.valor_cuota[(foto.valor_cuota["fondo"] == f) & (foto.valor_cuota["fecha"] == corte)]
        filas.append({"fondo": f, **metricas(indice_de_foto(foto, f)),
                      "patrimonio": float(pat["valor"].sum()), "n_afp": int(vc["afp"].nunique())})
    df = pd.DataFrame(filas)
    total = df["patrimonio"].sum()
    df["peso_sistema"] = df["patrimonio"] / total if total else float("nan")
    return df[["fondo", "rent_1m", "rent_3m", "rent_ytd", "rent_1a", "rent_3a", "rent_5a",
               "patrimonio", "peso_sistema", "n_afp"]]
