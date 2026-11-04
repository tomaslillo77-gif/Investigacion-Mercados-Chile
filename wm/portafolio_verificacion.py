"""Informe anónimo para comprobar con los datos reales los supuestos del constructor de portafolios: qué parte del patrimonio de los clientes se reconoce en la lista de
instrumentos, cuántos instrumentos hacen falta para cubrir el 80, 90 y 95%, y qué hay en la lista. Solo agrega: conteos, montos y porcentajes; nunca RUT ni nombres de clientes."""
from datetime import date

import pandas as pd

from wm.catalogo import Catalogo
from wm.portafolio_cliente import reconocer_posiciones

NIVELES = (0.80, 0.90, 0.95)


def curva_de_cobertura(valores: pd.Series) -> dict[float, int]:
    """Cuántos instrumentos (los de mayor monto primero) se necesitan para cubrir el 80, 90 y 95% del monto."""
    v = valores[valores > 0].sort_values(ascending=False)
    if v.empty:
        return {n: 0 for n in NIVELES}
    acumulado = v.cumsum() / v.sum()
    return {n: int((acumulado < n - 1e-12).sum() + 1) for n in NIVELES}


def analizar(posiciones: pd.DataFrame, clientes: pd.DataFrame, catalogo: Catalogo, resumen_portafolios: pd.DataFrame | None = None) -> dict:
    """Números del informe. `resumen_portafolios` es la tabla de `Store.resumen_portafolios_vigentes()` (o None si no hay base)."""
    cat = catalogo.instrumentos
    p = reconocer_posiciones(posiciones, cat, catalogo.alias) if len(posiciones) else posiciones.assign(instrument_id=pd.Series(dtype=object), via=pd.Series(dtype=object))
    total = float(p["valor_clp"].sum()) if len(p) else 0.0
    reconocido = p[p["instrument_id"].notna()]
    por_via = reconocido.groupby("via")["valor_clp"].sum() if len(reconocido) else pd.Series(dtype=float)
    sin = p[p["instrument_id"].isna()]
    sin_agr = sin.assign(clave=sin["isin"].astype(str)).groupby("clave").agg(valor=("valor_clp", "sum"), clientes=("rut", "nunique"), nombre=("instrumento", "first")).sort_values("valor", ascending=False) if len(sin) else pd.DataFrame(columns=["valor", "clientes", "nombre"])
    por_instrumento = p.assign(clave=p["instrument_id"].where(p["instrument_id"].notna(), "EXT::" + p["isin"].astype(str))).groupby("clave")["valor_clp"].sum() if len(p) else pd.Series(dtype=float)
    ruts_con_pos = set(p["rut"]) if len(p) else set()
    sin_ruts = set(sin["rut"]) if len(sin) else set()
    out = {
        "clientes": int(clientes["rut"].nunique()), "clientes_con_posiciones": len(ruts_con_pos), "posiciones": len(p), "valor_total": total,
        "pct_reconocido": float(reconocido["valor_clp"].sum() / total * 100) if total else None,
        "pct_por_via": {k: float(v / total * 100) for k, v in por_via.items()} if total else {},
        "instrumentos_distintos": int(len(por_instrumento)), "instrumentos_sin_reconocer": int(len(sin_agr)),
        "clientes_con_algo_sin_reconocer": len(sin_ruts), "curva": curva_de_cobertura(por_instrumento),
        "top_sin_reconocer": [{"instrumento": str(r["nombre"]) if pd.notna(r["nombre"]) else k, "pct": float(r["valor"] / total * 100) if total else None, "clientes": int(r["clientes"])}
                              for k, r in sin_agr.head(15).iterrows()],
        "catalogo": {"instrumentos": int(len(cat)), "activos": int(cat["activo"].astype(bool).sum()), "con_desglose": int(cat[["pct_renta_variable", "pct_alternativos", "pct_rf_local"]].notna().all(axis=1).sum()),
                     "con_comision": int(cat["comision"].notna().sum()), "alias": int(len(catalogo.alias)), "errores": sum(i.level == "error" for i in catalogo.issues),
                     "avisos": sum(i.level == "warning" for i in catalogo.issues)},
    }
    if resumen_portafolios is not None:
        n = out["clientes"]
        out["portafolios"] = {"definidos": int(len(resumen_portafolios)), "pct_clientes": len(resumen_portafolios) / n * 100 if n else None}
    return out


def a_markdown(r: dict, hoy: date, origen: str) -> str:
    def p(v, d=1):
        return "—" if v is None else f"{v:.{d}f}%".replace(".", ",")
    L = [f"# Verificación de supuestos del constructor de portafolios", "", f"Generado el {hoy:%d-%m-%Y} a partir de {origen}. No contiene RUT ni nombres de clientes: solo conteos y porcentajes.", "",
         "## Los datos", f"- Clientes: {r['clientes']} ({r['clientes_con_posiciones']} con posiciones). Posiciones: {r['posiciones']}. Instrumentos distintos: {r['instrumentos_distintos']}.", "",
         "## ¿Se reconoce lo que tienen los clientes? (supuestos C2 y C5)",
         f"- Patrimonio reconocido en la lista de instrumentos: **{p(r['pct_reconocido'], 2)}**."]
    L += [f"  - por {via}: {p(v)}" for via, v in r["pct_por_via"].items()]
    L += [f"- Instrumentos sin reconocer: {r['instrumentos_sin_reconocer']}, que tocan a {r['clientes_con_algo_sin_reconocer']} clientes.",
          f"- Para cubrir el 80%, 90% y 95% del patrimonio hacen falta {r['curva'][0.80]}, {r['curva'][0.90]} y {r['curva'][0.95]} instrumentos (si la lista cubre esos, el trabajo de mantenerla es acotado).", ""]
    if r["top_sin_reconocer"]:
        L += ["### Los 15 instrumentos sin reconocer de mayor monto (lo primero que habría que agregar a la lista)", "", "| Instrumento | % del patrimonio | Clientes |", "|---|---|---|"]
        L += [f"| {x['instrumento']} | {p(x['pct'], 2)} | {x['clientes']} |" for x in r["top_sin_reconocer"]]
        L.append("")
    c = r["catalogo"]
    L += ["## La lista de instrumentos (supuesto C2)", f"- {c['instrumentos']} instrumentos, {c['activos']} activos; {c['con_desglose']} con desglose, {c['con_comision']} con comisión, {c['alias']} alias.",
          f"- Problemas de datos: {c['errores']} errores y {c['avisos']} avisos (se ven en la pestaña Portafolio de la ficha)."]
    if "portafolios" in r:
        L += ["", "## Adopción (supuesto C1)", f"- Portafolios definidos: {r['portafolios']['definidos']} ({p(r['portafolios']['pct_clientes'])} de los clientes)."]
    return "\n".join(L) + "\n"
