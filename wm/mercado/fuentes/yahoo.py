"""Yahoo Finance: prototipo para fondos internacionales y referencias (S&P 500, tipos de cambio).

No hay API oficial: se usa `yfinance`, que puede cambiar o bloquear sin aviso. Por eso cada respuesta se guarda en
caché por día, el ritmo de peticiones se limita, se reintenta con espera creciente y, si Yahoo falla, se devuelve el
último dato guardado. Para producción conviene un proveedor con licencia (Bloomberg, Alpha Vantage, Finnhub).
"""
import json
import re
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Sequence

import pandas as pd

from wm.mercado.fuentes.base import FuenteNoDisponible
from wm.mercado.schema import PRECIOS_COLS, RENTAB_COLS


def _descargar_yfinance(id_: str, desde: date) -> pd.DataFrame:
    try:
        import yfinance
    except ImportError as e:
        raise FuenteNoDisponible("Falta instalar yfinance (pip install yfinance) para usar Yahoo Finance.") from e
    h = yfinance.Ticker(id_).history(start=desde.isoformat())
    return pd.DataFrame({"fecha": [d.date() for d in h.index], "valor": h["Close"].astype(float).values})


def _buscar_yfinance(isin: str) -> dict | None:
    try:
        import yfinance
    except ImportError as e:
        raise FuenteNoDisponible("Falta instalar yfinance (pip install yfinance) para usar Yahoo Finance.") from e
    quotes = yfinance.Search(isin, max_results=3).quotes
    q = next((x for x in quotes if x.get("symbol")), None)
    return None if q is None else {"symbol": q["symbol"], "nombre": q.get("shortname") or q.get("longname") or q["symbol"],
                                   "tipo": q.get("quoteType")}


def _info_yfinance(id_: str) -> dict:
    try:
        import yfinance
    except ImportError as e:
        raise FuenteNoDisponible("Falta instalar yfinance (pip install yfinance) para usar Yahoo Finance.") from e
    i = yfinance.Ticker(id_).info
    return {"nombre": i.get("longName") or i.get("shortName"), "tipo": i.get("quoteType"), "moneda": i.get("currency"),
            "costo": i.get("netExpenseRatio"), "patrimonio": i.get("totalAssets")}  # costo en %, p. ej. 0.07 = 0,07 %


class YahooFuente:
    nombre = "yahoo"

    def __init__(self, cache_dir: Path, pausa_seg: float = 1.0, reintentos: int = 3,
                 descargar: Callable[[str, date], pd.DataFrame] | None = None,
                 hoy: Callable[[], date] = date.today, buscar: Callable[[str], dict | None] | None = None,
                 info: Callable[[str], dict] | None = None):
        self.cache_dir = Path(cache_dir)
        self.pausa, self.reintentos, self.hoy = pausa_seg, reintentos, hoy
        self.descargar = descargar or _descargar_yfinance
        self._buscar, self._info = buscar or _buscar_yfinance, info or _info_yfinance

    def _con_reintentos(self, fn: Callable, *args):
        """Llama a la fuente con espera creciente entre intentos; devuelve el error del último si todos fallan."""
        ultimo = None
        for intento in range(self.reintentos):
            try:
                r = fn(*args)
                time.sleep(self.pausa)  # ritmo limitado entre peticiones
                return r
            except FuenteNoDisponible:
                raise
            except Exception as e:
                ultimo = e
                time.sleep(self.pausa * 2 ** intento)
        raise ultimo if ultimo else RuntimeError("sin intentos")

    def buscar_isin(self, isin: str) -> dict | None:
        """Ticker de Yahoo de un ISIN ({symbol, nombre, tipo}). Lo encontrado se guarda para siempre en isin.json."""
        archivo = self.cache_dir / "isin.json"
        guardado = json.loads(archivo.read_text(encoding="utf-8")) if archivo.exists() else {}
        if isin in guardado:
            return guardado[isin]
        try:
            r = self._con_reintentos(self._buscar, isin)
        except FuenteNoDisponible:
            raise
        except Exception:
            return None
        if r:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            archivo.write_text(json.dumps({**guardado, isin: r}, ensure_ascii=False, indent=1), encoding="utf-8")
        return r

    def info(self, id_: str) -> dict:
        """Nombre, tipo, moneda, costo (%) y patrimonio del instrumento; en caché por día. {} si Yahoo no responde."""
        f = self.cache_dir / self.hoy().isoformat() / (re.sub(r"[^\w.=^-]", "_", id_) + ".info.json")
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        try:
            r = self._con_reintentos(self._info, id_) or {}
        except FuenteNoDisponible:
            raise
        except Exception:
            return {}
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
        return r

    @staticmethod
    def _archivo(id_: str) -> str:
        return re.sub(r"[^\w.=^-]", "_", id_) + ".csv"

    def _cache_mas_reciente(self, id_: str) -> pd.DataFrame | None:
        if not self.cache_dir.exists():
            return None
        for d in sorted((p for p in self.cache_dir.iterdir() if p.is_dir()), reverse=True):
            f = d / self._archivo(id_)
            if f.exists():
                return pd.read_csv(f, parse_dates=["fecha"]).assign(fecha=lambda x: x["fecha"].dt.date)
        return None

    def _precios_de(self, id_: str, desde: date) -> pd.DataFrame | None:
        hoy_dir = self.cache_dir / self.hoy().isoformat()
        f = hoy_dir / self._archivo(id_)
        if f.exists():
            return pd.read_csv(f, parse_dates=["fecha"]).assign(fecha=lambda x: x["fecha"].dt.date)
        for intento in range(self.reintentos):
            try:
                d = self.descargar(id_, desde)
                hoy_dir.mkdir(parents=True, exist_ok=True)
                d.to_csv(f, index=False)
                time.sleep(self.pausa)  # ritmo limitado entre peticiones
                return d
            except FuenteNoDisponible:
                raise
            except Exception:
                time.sleep(self.pausa * 2 ** intento)
        return self._cache_mas_reciente(id_)

    def precios(self, ids: Sequence[str], desde: date) -> pd.DataFrame | None:
        partes = []
        for id_ in ids:
            d = self._precios_de(id_, desde)
            if d is not None and not d.empty:
                partes.append(d.assign(id=id_)[PRECIOS_COLS])
        return pd.concat(partes, ignore_index=True) if partes else None

    def rentabilidades(self, ids: Sequence[str]) -> pd.DataFrame | None:
        hoy = self.hoy()
        p = self.precios(ids, hoy - timedelta(days=1100))
        if p is None:
            return None
        filas = []
        for id_, g in p.groupby("id"):
            g = g.sort_values("fecha")
            ult = g.iloc[-1]

            def desde_(fecha: date, anios: int = 1):
                previo = g[g["fecha"] <= fecha]
                if previo.empty:
                    return None
                total = ult["valor"] / previo.iloc[-1]["valor"]
                return (total - 1) * 100 if anios == 1 else (total ** (1 / anios) - 1) * 100
            filas.append({"id": id_, "fecha": ult["fecha"], "rent_1m": desde_(ult["fecha"] - timedelta(days=30)),
                          "rent_3m": desde_(ult["fecha"] - timedelta(days=91)),
                          "rent_ytd": desde_(date(ult["fecha"].year - 1, 12, 31)),
                          "rent_1a": desde_(ult["fecha"] - timedelta(days=365)),
                          "rent_3a": desde_(ult["fecha"] - timedelta(days=1095), 3)})
        return pd.DataFrame(filas, columns=RENTAB_COLS)

    def composicion(self, ids: Sequence[str]) -> pd.DataFrame | None:
        return None  # la composición no está verificada en Yahoo; se prueba ticker por ticker en la etapa 2
