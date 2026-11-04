"""Tablas que muestra el screener de Estrategia: fondos del modelo cruzados con la foto de la CMF."""
import pandas as pd

from wm.mercado.schema import Foto

METRICAS = ["tac", "patrimonio", "participes", "rent_ytd", "rent_1a", "rent_3a", "rent_5a", "rent_10a"]


def fmt_pct(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:.2f}%"


def _estado(isin, tiene_cruce: bool, tiene_datos: bool) -> str:
    if tiene_cruce:
        return "CMF" if tiene_datos else "Cruce sin datos"
    # CL e SIN_ISIN son fondos locales (se cruzan con la CMF); el resto son internacionales (Yahoo o Bloomberg)
    return "Sin cruce" if str(isin).upper().startswith(("CL", "SIN_ISIN")) else "Pendiente Yahoo/Bloomberg"


def modelo_fondos(carteras: pd.DataFrame, equiv: pd.DataFrame, foto: Foto | None) -> pd.DataFrame:
    """Una fila por (arquitectura, perfil, instrumento, serie) del modelo, con los datos CMF si hay cruce."""
    base = carteras[["arquitectura", "perfil", "instrumento", "serie", "isin", "peso_objetivo"]].copy()
    base["serie"] = base["serie"].astype(str)
    eqv = equiv.reindex(columns=["instrumento_catalogo", "serie_catalogo", "fo_run", "fm_serie"]).copy()
    eqv["serie_catalogo"] = eqv["serie_catalogo"].astype(str)
    eqv = eqv.drop_duplicates(["instrumento_catalogo", "serie_catalogo"], keep="first")  # una fila repetida no duplica el fondo
    eqv["fo_run"] = pd.to_numeric(eqv["fo_run"], errors="coerce")
    eqv["fm_serie"] = eqv["fm_serie"].astype(object).where(eqv["fm_serie"].notna(), None)
    m = base.merge(eqv, left_on=["instrumento", "serie"], right_on=["instrumento_catalogo", "serie_catalogo"],
                   how="left").drop(columns=["instrumento_catalogo", "serie_catalogo"])
    if foto is not None and not foto.series.empty:
        s = foto.series[["fo_run", "fm_serie"] + METRICAS].copy()
        s["fm_serie"] = s["fm_serie"].astype(str)
        s["fo_run"] = s["fo_run"].astype(float)
        s["_dato"] = True
        m = m.merge(s, on=["fo_run", "fm_serie"], how="left")
        m["_dato"] = m["_dato"].eq(True)
    else:
        for c in METRICAS:
            m[c] = float("nan")
        m["_dato"] = False
    m["estado"] = [_estado(i, pd.notna(f), d) for i, f, d in zip(m["isin"], m["fo_run"], m["_dato"])]
    return m.drop(columns="_dato").reset_index(drop=True)


def universo_cmf(foto: Foto) -> pd.DataFrame:
    return foto.series.sort_values("patrimonio", ascending=False, na_position="last").reset_index(drop=True)


def composicion_fondo(foto: Foto, fo_run: int, por: str = "clasificacion") -> pd.DataFrame:
    c = foto.cartera[foto.cartera["fo_run"] == fo_run]
    if c.empty:
        return pd.DataFrame(columns=["grupo", "peso"])
    g = c.groupby(por, dropna=False)["peso"].sum().sort_values(ascending=False).reset_index()
    return g.rename(columns={por: "grupo"}).assign(grupo=lambda d: d["grupo"].fillna("Sin dato"))


def comparar(df: pd.DataFrame, claves: list[tuple[int, str]]) -> pd.DataFrame:
    d = df.assign(_k=list(zip(df["fo_run"].astype("Int64"), df["fm_serie"].astype(str))))
    filas = [d[d["_k"] == (int(fo), str(se))] for fo, se in claves]
    filas = [f for f in filas if not f.empty]
    return (pd.concat(filas).drop(columns="_k").reset_index(drop=True) if filas else d.iloc[0:0].drop(columns="_k"))
