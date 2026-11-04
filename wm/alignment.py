import pandas as pd

from wm.exposure import Exposure, client_exposure, has_breakdown, model_exposure, perfil_de
from wm.loader import Dataset


def desvio_por_clase(cli: Exposure, mod: Exposure) -> dict[str, float]:
    """Cliente menos modelo, en puntos porcentuales, ambos normalizados por su cobertura."""
    if not cli.clase or not mod.clase or cli.cobertura <= 0 or mod.cobertura <= 0:
        return {}
    return {k: (cli.clase[k] / cli.cobertura - mod.clase[k] / mod.cobertura) * 100 for k in cli.clase}


def ranking(view: pd.DataFrame, ds: Dataset | None) -> pd.DataFrame | None:
    base_cols = ["rut", "entidad", "advisor", "aum_clp"]
    if "desvio_modelo_pct" in view.columns:
        out = view[base_cols].copy()
        out["desvio_pp"] = view["desvio_modelo_pct"].values
        out["clase"] = "—"
        out["fuente"] = "Excel"
    elif ds is not None and has_breakdown(ds.carteras):
        pos_by = {r: g for r, g in ds.posiciones.groupby("rut")}
        rows = []
        for _, c in view.iterrows():
            perfil = perfil_de(ds.carteras, c.get("perfil_norm"), c.get("arquitectura"))
            pos = pos_by.get(c["rut"])
            if pos is None or pd.isna(c.get("arquitectura")) or not perfil:
                continue
            d = desvio_por_clase(client_exposure(pos, ds.carteras), model_exposure(ds.carteras, c["arquitectura"], perfil))
            if d:
                clase = max(d, key=lambda k: abs(d[k]))
                rows.append({**{k: c[k] for k in base_cols}, "desvio_pp": d[clase], "clase": clase, "fuente": "Calculado"})
        if not rows:
            return None
        out = pd.DataFrame(rows)
    else:
        return None
    out = out[out["desvio_pp"].notna()]
    return out.reindex(out["desvio_pp"].abs().sort_values(ascending=False).index).reset_index(drop=True)


def desvio_detalle(cli: Exposure, mod: Exposure) -> list[dict]:
    """Desvío del cliente vs su modelo en filas listas para graficar, en puntos porcentuales de la cartera:
    cada clase con sus subactivos (renta variable, renta fija, alternativos), luego la moneda consolidada y el
    % de UF sobre la renta fija local. Cada fila: label, nivel (0 clase, 1 subactivo, 2 sub-subactivo, 'titulo'),
    cliente, modelo, desvio (cliente - modelo). Una fila 'titulo' no tiene valores."""
    if not cli.clase or not mod.clase or cli.cobertura <= 0 or mod.cobertura <= 0:
        return []

    def fila(label: str, nivel, c: float, m: float) -> dict:
        c, m = c / cli.cobertura * 100, m / mod.cobertura * 100
        return {"label": label, "nivel": nivel, "cliente": c, "modelo": m, "desvio": c - m}

    rows: list[dict] = []
    for clase, subs_c, subs_m in (("Renta Variable", cli.rv_categorias, mod.rv_categorias),
                                  ("Renta Fija", cli.rf_categorias, mod.rf_categorias),
                                  ("Alternativos", {}, {})):
        rows.append(fila(clase, 0, cli.clase.get(clase, 0.0), mod.clase.get(clase, 0.0)))
        for nombre, c in subs_c.items():
            m = subs_m.get(nombre, 0.0)
            if c or m:
                rows.append(fila(nombre, 1, c, m))
    if cli.moneda and mod.moneda:
        rows.append({"label": "Moneda", "nivel": "titulo"})
        for moneda, c in cli.moneda.items():
            m = mod.moneda.get(moneda, 0.0)
            if c or m:
                rows.append(fila(moneda, 1, c, m))
            if moneda == "UF" and cli.uf_sobre_rf_local is not None and mod.uf_sobre_rf_local is not None:
                c_uf, m_uf = cli.uf_sobre_rf_local * 100, mod.uf_sobre_rf_local * 100
                rows.append({"label": "% UF de la renta fija local", "nivel": 2, "cliente": c_uf, "modelo": m_uf,
                             "desvio": c_uf - m_uf})
    return rows
