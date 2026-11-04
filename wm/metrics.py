from datetime import date

import pandas as pd


def truthy(s: pd.Series) -> pd.Series:
    return s.map(lambda v: str(v).strip().lower() in ("1", "true", "si", "sí", "yes"))


def _contactados_90d(df: pd.DataFrame, hoy: date) -> pd.Series:
    cols = [c for c in ("ultimo_contacto", "ultima_reunion") if c in df.columns]
    last = pd.concat([pd.to_datetime(df[c]) for c in cols], axis=1).max(axis=1)
    return (pd.Timestamp(hoy) - last).dt.days <= 90


def kpis_advisor(clientes: pd.DataFrame, hoy: date) -> dict:
    n = len(clientes)
    return {
        "aum": float(clientes["aum_clp"].sum()),
        "n_clientes": n,
        "sow_promedio": (float(clientes["share_of_wallet_pct"].mean())
                         if "share_of_wallet_pct" in clientes.columns else None),
        "pct_wealth_plan": (float(truthy(clientes["tiene_wealth_plan"]).mean() * 100)
                            if "tiene_wealth_plan" in clientes.columns and n else None),
        "pct_contactados_90d": float(_contactados_90d(clientes, hoy).mean() * 100) if n else None,
    }


def mix_servicio(clientes: pd.DataFrame) -> pd.DataFrame:
    g = clientes.groupby("servicio").agg(aum=("aum_clp", "sum"), n_clientes=("rut", "count")).reset_index()
    total = g["aum"].sum()
    g["pct"] = g["aum"] / total * 100 if total else 0.0
    return g.sort_values("aum", ascending=False).reset_index(drop=True)


def mix_por(clientes: pd.DataFrame, columna: str, nombres: dict[str, str] | None = None,
            orden: list[str] | None = None, sin: str = "Sin determinar") -> pd.DataFrame:
    """AUM y número de clientes por categoría de `columna` (grupo, aum, n_clientes, pct). Los valores vacíos van a `sin`;
    `nombres` traduce el valor del Excel al nombre visible; con `orden` se respeta ese orden y si no, por AUM."""
    nombre = clientes[columna].map(lambda v: sin if pd.isna(v) else (nombres or {}).get(v, v))
    g = clientes.assign(grupo=nombre).groupby("grupo").agg(aum=("aum_clp", "sum"), n_clientes=("rut", "count")).reset_index()
    total = g["aum"].sum()
    g["pct"] = g["aum"] / total * 100 if total else 0.0
    if orden:
        pos = {n: i for i, n in enumerate(orden)}
        return g.sort_values("grupo", key=lambda s: s.map(lambda n: pos.get(n, len(pos)))).reset_index(drop=True)
    return g.sort_values("aum", ascending=False).reset_index(drop=True)


def flujos_netos(clientes: pd.DataFrame, flujos: pd.DataFrame | None = None) -> pd.DataFrame | None:
    """Aportes, retiros y neto por período. Con la hoja de flujos (por quincena) se suman los de los clientes dados;
    si no existe, se usan aportes_periodo / retiros_periodo de la hoja de clientes."""
    if flujos is not None and len(flujos):
        f = flujos[flujos["rut"].isin(clientes["rut"])]
        g = f.groupby("periodo").agg(aportes=("aportes_clp", "sum"), retiros=("retiros_clp", "sum")).reset_index()
        g["neto"] = g["aportes"] - g["retiros"]
        return g.sort_values("periodo").reset_index(drop=True)
    if not {"aportes_periodo", "retiros_periodo"} <= set(clientes.columns):
        return None
    df = clientes.copy()
    if "periodo" not in df.columns:
        df["periodo"] = "Período actual"
    g = df.groupby("periodo").agg(aportes=("aportes_periodo", "sum"),
                                  retiros=("retiros_periodo", "sum")).reset_index()
    g["neto"] = g["aportes"] - g["retiros"]
    return g.sort_values("periodo").reset_index(drop=True)


def comparar_advisors(clientes: pd.DataFrame, hoy: date) -> pd.DataFrame:
    rows = []
    for advisor, grp in clientes.groupby("advisor"):
        k = kpis_advisor(grp, hoy)
        rows.append({
            "advisor": advisor, "aum": k["aum"], "n_clientes": k["n_clientes"],
            "pct_wealth_plan": k["pct_wealth_plan"], "pct_contactados_90d": k["pct_contactados_90d"],
            "pct_series_malas": (float(grp["serie_mala"].astype(bool).mean() * 100)
                                 if "serie_mala" in grp.columns else None),
        })
    return pd.DataFrame(rows, columns=["advisor", "aum", "n_clientes", "pct_wealth_plan",
                                       "pct_contactados_90d", "pct_series_malas"])


def is_true(v) -> bool:
    return bool(truthy(pd.Series([v])).iloc[0])
