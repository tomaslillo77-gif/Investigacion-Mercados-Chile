from dataclasses import dataclass, field

import pandas as pd

from wm.columns import ALT_COL, MONEDA_COLS, RF_COLS, RV_TOTAL, breakdown_columns, rv_columns

TOL = 0.005
PREFIJO_PERSONALIZADA = "personalizada:"   # arquitectura de un cliente con portafolio definido por su advisor: «personalizada:<rut>»
PERFIL_PERSONALIZADO = "Personalizado"
CLASS_REQUIRED = RF_COLS + [RV_TOTAL, ALT_COL]
RF_NOMBRES = dict(zip(["Renta Fija Local", "High Yield", "Investment Grade"], RF_COLS))


@dataclass
class Exposure:
    clase: dict[str, float] = field(default_factory=dict)
    rv_categorias: dict[str, float] = field(default_factory=dict)
    rf_categorias: dict[str, float] = field(default_factory=dict)
    moneda: dict[str, float] = field(default_factory=dict)
    uf_sobre_rf_local: float | None = None
    cobertura: float = 0.0


def uf_on_local_rf(pct_uf: float, pct_rf_local: float) -> float | None:
    """UF como fracción de la renta fija local; None si es indefinido o incoherente."""
    if pct_rf_local <= 0 or pct_uf > pct_rf_local + TOL:
        return None
    return min(pct_uf / pct_rf_local, 1.0)


def has_breakdown(carteras: pd.DataFrame) -> bool:
    return all(c in carteras.columns for c in CLASS_REQUIRED)


def fund_table(carteras: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in breakdown_columns() if c in carteras.columns]
    return carteras.drop_duplicates("isin").set_index("isin")[cols]


def portfolio_exposure(weights: pd.Series, funds: pd.DataFrame) -> Exposure:
    if not has_breakdown(funds):
        return Exposure()
    w = weights[weights.index.isin(funds.index)]
    f = funds.loc[w.index]
    covered = f[CLASS_REQUIRED].notna().all(axis=1)
    w, f = w[covered], f[covered].fillna(0.0)
    exp = Exposure(cobertura=float(w.sum()))
    if w.empty:
        return exp
    exp.clase = {
        "Renta Fija": float((w * f[RF_COLS].sum(axis=1)).sum()),
        "Renta Variable": float((w * f[RV_TOTAL]).sum()),
        "Alternativos": float((w * f[ALT_COL]).sum()),
    }
    exp.rf_categorias = {name: float((w * f[col]).sum()) for name, col in RF_NOMBRES.items()}
    for cat, col in rv_columns().items():
        if col in f.columns:
            exp.rv_categorias[cat] = float((w * f[col]).sum())
    if all(c in f.columns for c in MONEDA_COLS.values()):
        uf = MONEDA_COLS["UF"]
        valid = ~(f[uf] > f["pct_rf_local"] + TOL)
        exp.moneda = {m: float((w * f[col]).sum()) for m, col in MONEDA_COLS.items()}
        wv, fv = w[valid], f[valid]  # los fondos con UF incoherente no entran al cálculo UF/RF local
        local = float((wv * fv["pct_rf_local"]).sum())
        if local > 0:
            exp.uf_sobre_rf_local = float((wv * fv[uf]).sum()) / local
    return exp


def model_exposure(carteras: pd.DataFrame, arquitectura: str, perfil: str) -> Exposure:
    if not has_breakdown(carteras):
        return Exposure()
    sel = carteras[(carteras["arquitectura"] == arquitectura) & (carteras["perfil"] == perfil)]
    if sel.empty or sel["peso_objetivo"].sum() <= 0:
        return Exposure()
    weights = sel.groupby("isin")["peso_objetivo"].sum()
    return portfolio_exposure(weights / weights.sum(), fund_table(carteras))


def client_exposure(posiciones_cliente: pd.DataFrame, carteras: pd.DataFrame) -> Exposure:
    total = posiciones_cliente["valor_clp"].sum()
    if not has_breakdown(carteras) or total <= 0:
        return Exposure()
    weights = posiciones_cliente.groupby("isin")["valor_clp"].sum() / total
    return portfolio_exposure(weights, fund_table(carteras))


def perfil_of(carteras: pd.DataFrame, perfil_norm: str) -> str | None:
    if "perfil_norm" not in carteras.columns:
        return None
    match = carteras.loc[carteras["perfil_norm"] == perfil_norm, "perfil"].dropna().unique()
    return str(match[0]) if len(match) else None


def es_personalizada(arquitectura) -> bool:
    return isinstance(arquitectura, str) and arquitectura.startswith(PREFIJO_PERSONALIZADA)


def perfil_de(carteras: pd.DataFrame, perfil_norm: str, arquitectura) -> str | None:
    """Perfil con el que buscar el modelo del cliente en la hoja de carteras: el de su perfil normalizado, o «Personalizado» si su portafolio lo definió el advisor."""
    return PERFIL_PERSONALIZADO if es_personalizada(arquitectura) else perfil_of(carteras, perfil_norm)
