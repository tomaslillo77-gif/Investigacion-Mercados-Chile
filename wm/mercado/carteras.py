"""Carteras gestionadas armadas con fondos mutuos Scotia de la CMF, ordenadas por clase de activo y subactivo."""
import pandas as pd

from wm.mercado.schema import Foto

COLUMNAS = ["clase", "subactivo", "fondo", "serie", "fo_run", "peso", "moneda", "rent_ytd", "rent_1a", "rent_3a", "tac",
            "patrimonio", "estado"]
_METRICAS = ["rent_ytd", "rent_1a", "rent_3a", "tac", "patrimonio"]
# Símbolo de moneda funcional de la CMF -> moneda del valor cuota ($$ = pesos; PROM = fondos en dólares)
MONEDAS = {"$$": "CLP", "PROM": "USD"}


def _serie_de(series: pd.DataFrame, agf: str, fondo: str, fijada: str | None, preferida: str | None) -> pd.Series | None:
    """La serie fijada del fondo; si no hay, la preferida (WEALTH); si tampoco existe, la de mayor patrimonio."""
    s = series[series["nombre_agf"].astype(str).str.upper().str.contains(agf.upper(), regex=False)
               & (series["nombre_fondo"] == fondo)]
    if s.empty:
        return None
    for nombre in (fijada, preferida):
        if nombre is not None:
            m = s[s["fm_serie"].astype(str) == str(nombre)]
            if not m.empty:
                return m.iloc[0]
    pat = pd.to_numeric(s["patrimonio"], errors="coerce")
    return s.loc[pat.idxmax()] if pat.notna().any() else s.iloc[0]


def _armar(perfil: str, cfg: dict, fila_de) -> pd.DataFrame:
    """Reparte la cartera del perfil entre clases (renta variable, renta fija, alternativos) y fondos, en el orden de Client
    Portal. `fila_de(fondo, meta)` devuelve los datos del fondo (serie, fo_run, moneda y métricas) o None si no los hay; esos
    fondos quedan con estado 'Sin datos' y conservan su peso."""
    p = cfg["perfiles"][perfil]
    rv, alt = p["rv"] / 100, p.get("alt", 0) / 100
    filas = []
    for clase, clave, w_clase in (("Renta variable", "renta_variable", rv), ("Renta fija", "renta_fija", 1 - rv - alt),
                                  ("Activos alternativos", "alternativos", alt)):
        reparto = p.get(clave) or {}
        total = sum(reparto.values())
        if w_clase <= 0 or not total:
            continue
        orden = cfg["orden"][clase]
        for fondo in sorted(reparto, key=lambda n: orden.index(cfg["fondos"][n]["sub"])):  # estable: respeta el orden dado
            meta = cfg["fondos"][fondo]
            datos = fila_de(fondo, meta)
            base = {"clase": clase, "subactivo": meta["sub"], "fondo": fondo, "peso": w_clase * reparto[fondo] / total}
            if datos is None:
                filas.append({**base, "serie": None, "fo_run": None, "moneda": "Sin dato",
                              **{m: float("nan") for m in _METRICAS}, "estado": "Sin datos"})
            else:
                filas.append({**base, **datos, "estado": "CMF" if datos.get("fo_run") is not None else "Yahoo"})
    return pd.DataFrame(filas, columns=COLUMNAS)


def armar_cartera(perfil: str, cfg: dict, foto: Foto | None) -> pd.DataFrame:
    """Cartera gestionada Scotia: fondos mutuos de la CMF (perfil normalizado, p. ej. 'PRESERVACION')."""
    def fila_de(fondo, meta):
        fila = None if foto is None else _serie_de(foto.series, cfg["agf"], fondo, meta.get("serie"), cfg.get("serie_preferida"))
        if fila is None:
            return None
        return {"serie": str(fila["fm_serie"]), "fo_run": int(fila["fo_run"]),
                "moneda": MONEDAS.get(str(fila.get("moneda_funcional")), "Sin dato"),
                **{m: pd.to_numeric(fila[m], errors="coerce") for m in _METRICAS}}
    return _armar(perfil, cfg, fila_de)


def armar_cartera_yahoo(perfil: str, cfg: dict, yahoo: pd.DataFrame | None) -> pd.DataFrame:
    """Cartera de fondos internacionales con datos de Yahoo Finance (tabla de wm.mercado.internacionales). La serie es el
    ticker, el costo (TER, solo ETFs) va en `tac` y la moneda es la de cotización del instrumento."""
    por_fondo = {} if yahoo is None else {r["instrumento"]: r for _, r in yahoo.iterrows() if r["estado"] == "Yahoo"}

    def fila_de(fondo, meta):
        r = por_fondo.get(fondo)
        if r is None:
            return None
        return {"serie": str(r["ticker"]), "fo_run": None, "moneda": r["moneda"] if isinstance(r["moneda"], str) else "Sin dato",
                "rent_ytd": pd.to_numeric(r["rent_ytd"], errors="coerce"), "rent_1a": pd.to_numeric(r["rent_1a"], errors="coerce"),
                "rent_3a": pd.to_numeric(r["rent_3a"], errors="coerce"), "tac": pd.to_numeric(r["costo"], errors="coerce"),
                "patrimonio": pd.to_numeric(r["patrimonio"], errors="coerce")}
    return _armar(perfil, cfg, fila_de)


def cobertura(df: pd.DataFrame, col: str) -> float:
    """Fracción del peso de la cartera que tiene el dato `col` (p. ej. cuánto del portafolio trae costo)."""
    ok = pd.to_numeric(df[col], errors="coerce").notna()
    total = df["peso"].sum()
    return float(df.loc[ok, "peso"].sum() / total) if total else 0.0


def ponderado(df: pd.DataFrame, col: str) -> float:
    """Promedio ponderado por peso, renormalizado entre los fondos que tienen el dato."""
    v = pd.to_numeric(df[col], errors="coerce")
    ok = v.notna()
    peso = df.loc[ok, "peso"].sum()
    return float("nan") if not ok.any() or not peso else float((df.loc[ok, "peso"] * v[ok]).sum() / peso)


def exposicion(cartera: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Exposición de la cartera a nivel de fondo, no de la cartera subyacente: cada fondo cuenta 100 % en su clase,
    su subactivo y la moneda de su valor cuota. Devuelve {'clase', 'subactivo', 'moneda'} con columnas grupo y peso."""
    out = {}
    for nombre, col in (("clase", "clase"), ("subactivo", "subactivo"), ("moneda", "moneda")):
        g = cartera.groupby(col, sort=False)["peso"].sum().reset_index().rename(columns={col: "grupo"})
        out[nombre] = g.sort_values("peso", ascending=False, kind="stable").reset_index(drop=True) \
            if nombre == "moneda" else g
    return out


def composicion_cartera(c: pd.DataFrame, foto: Foto | None, por: str = "clasificacion") -> pd.DataFrame:
    """Composición subyacente de la cartera según la CMF: la cartera de cada fondo (normalizada) por el peso del fondo.
    Los fondos sin cartera en la foto suman bajo 'Sin composición'. `por`: clasificacion, pais o emisor."""
    partes = []
    for _, r in c.iterrows():
        g = None
        if foto is not None and pd.notna(r["fo_run"]):
            g = foto.cartera[foto.cartera["fo_run"] == int(r["fo_run"])]
        if g is None or g.empty:
            partes.append(("Sin composición", r["peso"]))
            continue
        for grupo, w in g.groupby(por, dropna=False)["peso"].sum().items():
            partes.append((grupo if pd.notna(grupo) else "Sin dato", r["peso"] * w))
    d = pd.DataFrame(partes, columns=["grupo", "peso"]).groupby("grupo", sort=False)["peso"].sum().reset_index()
    return d.sort_values("peso", ascending=False, kind="stable").reset_index(drop=True)
