"""Fondos internacionales del catálogo (ISIN de Luxemburgo, Irlanda, etc.) con costo, precio y rentabilidad de Yahoo Finance."""
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

MIN_DIAS = 20  # menos precios que esto no permite calcular rentabilidades
COLUMNAS = ["instrumento", "isin", "ticker", "nombre_yahoo", "tipo", "moneda", "costo", "patrimonio", "precio",
            "fecha_precio", "rent_ytd", "rent_1a", "rent_3a", "estado"]
_ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d")


def isin_base(isin) -> str | None:
    """ISIN internacional sin sufijo de serie (IE00B5BMR087_RET -> IE00B5BMR087). None para fondos locales (CL), sin ISIN
    (SIN_ISIN::nombre) o valores vacíos: esos se resuelven con la CMF, no con Yahoo."""
    if not isinstance(isin, str) or not _ISIN.match(isin[:12]) or isin.startswith("CL"):
        return None
    return isin[:12]


def universo(carteras: pd.DataFrame) -> pd.DataFrame:
    u = carteras[["instrumento", "isin"]].copy()
    u["isin"] = u["isin"].map(isin_base)
    return u.dropna(subset=["isin"]).drop_duplicates("isin").reset_index(drop=True)


def construir(carteras: pd.DataFrame, yahoo, tickers: dict[str, str] | None = None, hoy: date | None = None) -> pd.DataFrame:
    """Una fila por fondo internacional del catálogo. `tickers` (ISIN -> ticker de Yahoo) tiene prioridad sobre la búsqueda."""
    hoy = hoy or date.today()
    tickers = {k: v for k, v in (tickers or {}).items() if isinstance(v, str) and v}
    filas = []
    for _, f in universo(carteras).iterrows():
        base = {c: None for c in COLUMNAS}
        base.update(instrumento=f["instrumento"], isin=f["isin"])
        t = tickers.get(f["isin"])
        hallado = None if t else yahoo.buscar_isin(f["isin"])
        t = t or (hallado or {}).get("symbol")
        if not t:
            filas.append({**base, "estado": "Sin ticker"})
            continue
        info = yahoo.info(t) or {}
        base.update(ticker=t, nombre_yahoo=info.get("nombre") or (hallado or {}).get("nombre"),
                    tipo=info.get("tipo") or (hallado or {}).get("tipo"), moneda=info.get("moneda"),
                    costo=info.get("costo"), patrimonio=info.get("patrimonio"))
        p = yahoo.precios([t], hoy - timedelta(days=1100))
        if p is None or len(p) < MIN_DIAS:
            filas.append({**base, "estado": "Sin datos suficientes"})
            continue
        ult = p.sort_values("fecha").iloc[-1]
        r = yahoo.rentabilidades([t])
        r = r.iloc[0] if r is not None and not r.empty else {}
        filas.append({**base, "precio": float(ult["valor"]), "fecha_precio": ult["fecha"], "estado": "Yahoo",
                      **{k: r.get(k) for k in ("rent_ytd", "rent_1a", "rent_3a")}})
    return pd.DataFrame(filas, columns=COLUMNAS)


def guardar_yahoo(df: pd.DataFrame, base: Path, fecha: date) -> Path:
    destino = Path(base) / fecha.isoformat()
    destino.mkdir(parents=True, exist_ok=True)
    df.to_csv(destino / "internacionales.csv", index=False, encoding="utf-8")
    return destino


def cargar_yahoo(base: Path) -> tuple[date, pd.DataFrame] | None:
    base = Path(base)
    if not base.exists():
        return None
    fechas = []
    for p in base.iterdir():
        try:
            if (p / "internacionales.csv").exists():
                fechas.append(date.fromisoformat(p.name))
        except ValueError:
            continue
    if not fechas:
        return None
    f = max(fechas)
    return f, pd.read_csv(base / f.isoformat() / "internacionales.csv")


def completar_tickers(equiv: pd.DataFrame, resultado: pd.DataFrame) -> pd.DataFrame:
    """Llena `ticker_yahoo` vacío en las equivalencias con el ticker hallado por ISIN. No pisa lo ya escrito."""
    encontrados = dict(zip(resultado["isin"], resultado["ticker"]))
    out = equiv.copy()
    out["ticker_yahoo"] = out["ticker_yahoo"].astype(object)
    for i, isin in out["isin"].items():
        b = isin_base(isin)
        if b in encontrados and isinstance(encontrados[b], str) and pd.isna(out.at[i, "ticker_yahoo"]):
            out.at[i, "ticker_yahoo"] = encontrados[b]
    return out
