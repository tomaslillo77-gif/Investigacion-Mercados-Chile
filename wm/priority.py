from datetime import date

import numpy as np
import pandas as pd

from wm.metrics import truthy

DESVIO_MAX = 20.0  # puntos porcentuales de desvío que equivalen a riesgo máximo


def _pct_rank(s: pd.Series) -> pd.Series:
    return s.rank(pct=True).fillna(0.0)


def dias_sin_contacto(df: pd.DataFrame, hoy: date) -> pd.Series:
    # to_datetime por columna: en una fila suelta (row.to_frame().T) las columnas llegan como object y mezclan Timestamp con NaN
    fechas = [pd.to_datetime(df[c], errors="coerce") for c in ("ultimo_contacto", "ultima_reunion") if c in df.columns]
    last = pd.concat(fechas, axis=1).max(axis=1) if fechas else pd.Series(pd.NaT, index=df.index)
    return (pd.Timestamp(hoy) - pd.to_datetime(last)).dt.days


def score_clients(clientes: pd.DataFrame, config: dict, hoy: date) -> pd.DataFrame:
    df = clientes.reset_index(drop=True)
    pesos = config["pesos"]
    max_dias = config.get("dias_sin_contacto_max", 180)

    dias = dias_sin_contacto(df, hoy)
    contacto = (dias / max_dias).clip(0, 1).fillna(1.0)
    parts = [contacto]
    if "tiene_wealth_plan" in df.columns:
        parts.append((~truthy(df["tiene_wealth_plan"])).astype(float))
    if "desvio_modelo_pct" in df.columns:
        parts.append((df["desvio_modelo_pct"].abs() / DESVIO_MAX).clip(0, 1).fillna(0.0))

    comp = pd.DataFrame({
        "comp_tamano": _pct_rank(df["aum_clp"]),
        "comp_riesgo_fuga": pd.concat(parts, axis=1).mean(axis=1),
        "comp_ingresos": np.nan,
        "comp_oportunidad": np.nan,
    })
    if "ingresos_en_juego" in df.columns:
        ing = df["ingresos_en_juego"].fillna(0.0).clip(lower=0.0)
        if (ing > 0).any():  # si nadie tiene comisión en juego, el componente no aplica
            comp["comp_ingresos"] = ing.where(ing > 0).rank(pct=True).fillna(0.0)
    if "share_of_wallet_pct" in df.columns:
        sow = (df["share_of_wallet_pct"] / 100).clip(lower=0.01)
        comp["comp_oportunidad"] = _pct_rank(df["aum_clp"] / sow - df["aum_clp"])

    keys = {"tamano": "comp_tamano", "riesgo_fuga": "comp_riesgo_fuga",
            "ingresos": "comp_ingresos", "oportunidad": "comp_oportunidad"}
    w = pd.DataFrame({keys[k]: comp[keys[k]].notna() * pesos[k] for k in keys})
    contrib = (comp.fillna(0.0) * w).div(w.sum(axis=1), axis=0)
    prioridad = (contrib.sum(axis=1) * 100).clip(0, 100)

    motivos = []
    for i in df.index:
        top = contrib.loc[i].sort_values(ascending=False).head(2)
        texts = []
        for col, val in top.items():
            if val <= 0:
                continue
            if col == "comp_riesgo_fuga":
                texts.append("Sin contacto registrado" if pd.isna(dias.loc[i]) else f"Sin contacto {int(dias.loc[i])} días")
            elif col == "comp_tamano":
                texts.append("Cliente de gran tamaño")
            elif col == "comp_ingresos":
                texts.append("Comisión en juego por serie")
            elif col == "comp_oportunidad":
                texts.append(f"SoW {df.loc[i, 'share_of_wallet_pct']:.0f}%")
        motivos.append(texts)

    out = pd.concat([df[["rut"]], comp], axis=1)
    out["prioridad"] = prioridad
    out["motivos"] = motivos
    return out
