"""Tabla que une cada fondo del catálogo con su identificador en cada fuente (CMF, Yahoo, Bloomberg, RiskAmerica)."""
import difflib
import re
import unicodedata
from pathlib import Path

import pandas as pd

EQUIV_COLS = ["instrumento_catalogo", "isin", "serie_catalogo", "fo_run", "fm_serie", "ticker_yahoo",
              "ticker_bloomberg", "id_riskamerica", "confianza"]
_LLAVE = ["instrumento_catalogo", "serie_catalogo"]


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", s).strip()


def proponer(carteras: pd.DataFrame, series: pd.DataFrame, corte: float = 0.9) -> pd.DataFrame:
    """Una fila por (instrumento, serie) del catálogo. Solo cruza coincidencias muy altas cuyo fondo tenga esa serie."""
    por_nombre = {}
    for (n, fo), g in series.assign(_n=series["nombre_fondo"].map(_norm)).groupby(["_n", "fo_run"]):
        por_nombre.setdefault(n, []).append((int(fo), set(g["fm_serie"].astype(str))))
    cat = carteras[["instrumento", "isin", "serie"]].drop_duplicates(["instrumento", "serie"])
    filas = []
    for _, r in cat.iterrows():
        n = _norm(r["instrumento"])
        cands = sorted(((difflib.SequenceMatcher(None, n, c).ratio(), c) for c in por_nombre), reverse=True)
        fo = serie = conf = None
        for ratio, c in cands:
            if ratio < corte:
                break
            hit = next((f for f, ss in por_nombre[c] if str(r["serie"]) in ss), None)
            if hit is not None:
                fo, serie, conf = hit, str(r["serie"]), round(ratio, 2)
                break
        filas.append({"instrumento_catalogo": r["instrumento"], "isin": r["isin"], "serie_catalogo": r["serie"],
                      "fo_run": fo, "fm_serie": serie, "ticker_yahoo": None, "ticker_bloomberg": None,
                      "id_riskamerica": None, "confianza": conf})
    return pd.DataFrame(filas, columns=EQUIV_COLS)


def cargar(path: Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=EQUIV_COLS)
    df = pd.read_csv(path, dtype={"fm_serie": str, "serie_catalogo": str, "ticker_yahoo": str,
                                  "ticker_bloomberg": str, "id_riskamerica": str})
    for c in EQUIV_COLS:
        if c not in df:
            df[c] = None
    return df[EQUIV_COLS]


def guardar(df: pd.DataFrame, path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df[EQUIV_COLS].to_csv(path, index=False, encoding="utf-8")


def completar(existente: pd.DataFrame, propuesta: pd.DataFrame) -> pd.DataFrame:
    """Agrega los instrumentos nuevos del catálogo sin tocar las filas existentes (las correcciones manuales se conservan)."""
    if existente.empty:
        return propuesta[EQUIV_COLS].reset_index(drop=True)
    claves = set(zip(existente["instrumento_catalogo"], existente["serie_catalogo"].astype(str)))
    nuevas = propuesta[[(i, str(s)) not in claves for i, s in zip(propuesta["instrumento_catalogo"],
                                                                  propuesta["serie_catalogo"])]]
    if nuevas.empty:
        return existente[EQUIV_COLS].reset_index(drop=True)
    return pd.concat([existente.astype(object), nuevas.astype(object)], ignore_index=True)[EQUIV_COLS]
