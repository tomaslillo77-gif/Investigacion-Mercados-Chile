from datetime import date

import pandas as pd

from wm.architecture import infer_architecture
from wm.config import load_config
from wm.display import add_display_columns
from wm.loader import Dataset
from wm.series import evaluate_series


def enrich_clientes(ds: Dataset, hoy: date) -> pd.DataFrame:
    """Agrega a cada cliente arquitectura (declarada o inferida), cobertura, serie_mala e ingresos_en_juego."""
    min_cob = load_config("arquitecturas").get("min_cobertura", 0.60)
    out = ds.clientes.copy()
    declared = out["arquitectura"] if "arquitectura" in out.columns else pd.Series(None, index=out.index)
    pos_by_rut = {r: g for r, g in ds.posiciones.groupby("rut")} if len(ds.posiciones) else {}
    empty = ds.posiciones.iloc[0:0]
    arqs, cobs, infer, malas, ingresos = [], [], [], [], []
    for rut, dec in zip(out["rut"], declared):
        pos = pos_by_rut.get(rut, empty)
        res = infer_architecture(pos, ds.carteras, min_cob, declarada=dec if pd.notna(dec) else None)
        findings = evaluate_series(pos, ds.carteras, res.arquitectura)
        valor = pos.groupby("isin")["valor_clp"].sum() if len(pos) else pd.Series(dtype=float)
        en_juego = sum(
            float(valor.get(f.isin, 0.0)) * (f.comision_actual - f.comision_modelo)
            for f in findings
            if f.es_mala and f.comision_actual is not None and f.comision_modelo is not None
            and f.comision_actual > f.comision_modelo)
        arqs.append(res.arquitectura)
        cobs.append(res.cobertura)
        infer.append(res.inferida)
        malas.append(any(f.es_mala for f in findings))
        ingresos.append(en_juego)
    out["arquitectura"] = arqs
    out["cobertura_arq"] = cobs
    out["arquitectura_inferida"] = infer
    out["serie_mala"] = malas
    out["ingresos_en_juego"] = ingresos
    return add_display_columns(out)
