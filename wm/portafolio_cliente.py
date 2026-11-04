"""Portafolio objetivo de un cliente, definido por el advisor: lógica pura (sin Streamlit ni base de datos).

Un portafolio es una tabla de `items`: instrumento, serie, peso (en puntos porcentuales, suman 100) y comisión. El advisor lo arma eligiendo de la lista
de instrumentos (`wm/catalogo.py`); aquí se valida, se normaliza, se mide (exposición y costo) y se convierte al formato de la hoja de carteras para que el
rebalanceo, la evaluación de series y las exposiciones del resto del dashboard lo usen sin cambios.

Reglas: lo que rompe la integridad (suma distinta de 100%, repetidos, pesos negativos, instrumentos desconocidos) es un **error** y no se guarda; el resto
(banda del perfil, series más caras, posiciones residuales, instrumentos inactivos) son **avisos**: el criterio es del advisor.
"""
from dataclasses import dataclass, field, replace
from datetime import date, datetime

import pandas as pd

from wm.catalogo import CARTERAS_COLS, a_carteras, resolver_ids
from wm.columns import breakdown_columns
from wm.config import load_config
from wm.exposure import PERFIL_PERSONALIZADO, PREFIJO_PERSONALIZADA, client_exposure, es_personalizada, has_breakdown, model_exposure, portfolio_exposure
from wm.loader import Dataset
from wm.quality import Issue
from wm.rebalance import plan_rebalanceo

ITEM_COLS = ["instrument_id", "isin", "nombre", "serie", "peso", "comision"]
EXTERNO = "EXT::"          # prefijo de lo que el cliente tiene y no está en la lista: se muestra y se puede mantener, pero sin desglose
SHEET = "portafolio"


def cfg() -> dict:
    return load_config("perfiles_bandas")


def vacio() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=object if c != "peso" and c != "comision" else float) for c in ITEM_COLS})


def es_externo(instrument_id) -> bool:
    return str(instrument_id).startswith(EXTERNO)


def _items(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in ITEM_COLS:
        if c not in out.columns:
            out[c] = pd.NA
    return out[ITEM_COLS].reset_index(drop=True)


# ── Armar ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def item_desde_catalogo(catalogo: pd.DataFrame, instrument_id: str, peso: float = 0.0) -> dict:
    """La fila de un portafolio para un instrumento del catálogo: copia nombre, serie e comisión del momento."""
    r = catalogo.drop_duplicates("instrument_id").set_index("instrument_id").loc[instrument_id]
    return {"instrument_id": instrument_id, "isin": r["isin"], "nombre": r["nombre"] if pd.notna(r["nombre"]) else instrument_id,
            "serie": r["serie"], "peso": float(peso), "comision": r["comision"]}


def reconocer_posiciones(pos: pd.DataFrame, catalogo: pd.DataFrame, alias: pd.DataFrame | None = None) -> pd.DataFrame:
    """Posiciones del cliente con `instrument_id` y `via` (cómo se reconoció). Lo no reconocido queda con `instrument_id` vacío."""
    if pos.empty:
        return pos.assign(instrument_id=pd.Series(dtype=object), via=pd.Series(dtype=object))
    r = resolver_ids(pos["isin"], catalogo, alias)
    return pos.assign(instrument_id=r["instrument_id"].values, via=r["via"].values)


def desde_posiciones(pos: pd.DataFrame, catalogo: pd.DataFrame, alias: pd.DataFrame | None = None) -> pd.DataFrame:
    """Lo que el cliente tiene hoy, como portafolio: un ítem por instrumento con su peso (suman 100). Lo que no está en la lista entra como externo
    (`EXT::`), con su nombre tal cual viene, para que se vea y se pueda mantener."""
    if pos.empty or pos["valor_clp"].sum() <= 0:
        return vacio()
    p = reconocer_posiciones(pos, catalogo, alias)
    total = float(p["valor_clp"].sum())
    filas = []
    conocidos = p[p["instrument_id"].notna()].groupby("instrument_id")["valor_clp"].sum()
    for iid, valor in conocidos.items():
        filas.append(item_desde_catalogo(catalogo, iid, valor / total * 100))
    desconocidos = p[p["instrument_id"].isna()]
    for clave, g in desconocidos.groupby(desconocidos["isin"].astype(str)):
        nombre = str(g["instrumento"].iloc[0]) if "instrumento" in g.columns and pd.notna(g["instrumento"].iloc[0]) else clave
        filas.append({"instrument_id": EXTERNO + clave, "isin": clave, "nombre": nombre, "serie": pd.NA, "peso": float(g["valor_clp"].sum()) / total * 100, "comision": pd.NA})
    return normalizar(_items(pd.DataFrame(filas)).sort_values("peso", ascending=False))


def desde_modelo(carteras: pd.DataFrame, arquitectura: str, perfil: str, catalogo: pd.DataFrame) -> pd.DataFrame:
    """Un modelo de la casa (arquitectura × perfil) como punto de partida."""
    m = carteras[(carteras["arquitectura"] == arquitectura) & (carteras["perfil"] == perfil) & (carteras["peso_objetivo"].fillna(0) > 0)]
    if m.empty:
        return vacio()
    pesos = m.groupby("isin")["peso_objetivo"].sum()
    filas = []
    for iid, w in pesos.items():
        if iid in set(catalogo["instrument_id"]):
            filas.append(item_desde_catalogo(catalogo, iid, w))
        else:
            r = m[m["isin"] == iid].iloc[0]
            filas.append({"instrument_id": EXTERNO + iid, "isin": iid, "nombre": r.get("diccionario", iid), "serie": r.get("serie"), "peso": float(w), "comision": r.get("comision")})
    out = _items(pd.DataFrame(filas))
    out["peso"] = out["peso"] / out["peso"].sum() * 100
    return normalizar(out.sort_values("peso", ascending=False))


def desde_version(items: pd.DataFrame) -> pd.DataFrame:
    """Copia de una versión anterior como punto de partida."""
    return _items(items)


def normalizar(items: pd.DataFrame, decimales: int = 2) -> pd.DataFrame:
    """Escala los pesos para que sumen exactamente 100, con `decimales`; la diferencia de redondeo va al ítem de mayor peso. Sin pesos positivos, no cambia nada."""
    out = _items(items)
    total = float(out["peso"].fillna(0).clip(lower=0).sum())
    if out.empty or total <= 0:
        return out
    out["peso"] = (out["peso"].fillna(0).clip(lower=0) / total * 100).round(decimales)
    resto = round(100 - float(out["peso"].sum()), decimales)
    if resto:
        out.loc[out["peso"].idxmax(), "peso"] = round(out["peso"].max() + resto, decimales)
    return out


# ── Validar ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def validar(items: pd.DataFrame, catalogo: pd.DataFrame, config: dict | None = None) -> list[Issue]:
    """Errores (impiden guardar) y avisos (no bloquean). Cada mensaje nombra el instrumento."""
    c = config or cfg()
    it = _items(items)
    out: list[Issue] = []
    if it.empty:
        return [Issue("error", SHEET, "El portafolio no tiene instrumentos.")]
    conocidos = catalogo.drop_duplicates("instrument_id").set_index("instrument_id")
    for i, r in it.iterrows():
        nombre = r["nombre"] if pd.notna(r["nombre"]) else r["instrument_id"]
        if pd.isna(r["instrument_id"]):
            out.append(Issue("error", SHEET, f"La línea {i + 1} no tiene instrumento."))
            continue
        if pd.isna(r["peso"]) or r["peso"] < 0:
            out.append(Issue("error", SHEET, f"{nombre}: el peso no puede ser vacío ni negativo."))
        elif r["peso"] > 100:
            out.append(Issue("error", SHEET, f"{nombre}: el peso no puede superar 100%."))
        if es_externo(r["instrument_id"]):
            out.append(Issue("warning", SHEET, f"{nombre}: no está en la lista de instrumentos; se mantiene sin desglose (no entra en la exposición)."))
        elif r["instrument_id"] not in conocidos.index:
            out.append(Issue("error", SHEET, f"{nombre}: no está en la lista de instrumentos."))
        elif not bool(conocidos.loc[r["instrument_id"], "activo"]):
            out.append(Issue("warning", SHEET, f"{nombre}: el instrumento está inactivo en la lista; conviene reemplazarlo."))
        if pd.notna(r["peso"]) and 0 < r["peso"] < c["peso_minimo_pp"]:
            out.append(Issue("warning", SHEET, f"{nombre}: posición residual ({r['peso']:.2f}%)."))
    repetidos = it["instrument_id"].dropna()
    for v in sorted(set(repetidos[repetidos.duplicated(keep=False)])):
        nombre = it.loc[it["instrument_id"] == v, "nombre"].iloc[0]
        out.append(Issue("error", SHEET, f"{nombre if pd.notna(nombre) else v} aparece más de una vez."))
    suma = float(it["peso"].fillna(0).sum())
    if abs(suma - 100) > c["tolerancia_suma_pp"]:
        out.append(Issue("error", SHEET, f"Los pesos suman {suma:.2f}%, deben sumar 100%."))
    if len(it) > c["max_instrumentos"]:
        out.append(Issue("warning", SHEET, f"El portafolio tiene {len(it)} instrumentos (más de {c['max_instrumentos']})."))
    return out


def hay_errores(issues: list[Issue]) -> bool:
    return any(i.level == "error" for i in issues)


# ── Medir ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
@dataclass
class Resumen:
    clase: dict[str, float] = field(default_factory=dict)        # % de lo que tiene desglose (suma 100)
    rv_categorias: dict[str, float] = field(default_factory=dict)
    rf_categorias: dict[str, float] = field(default_factory=dict)
    moneda: dict[str, float] = field(default_factory=dict)
    cobertura: float = 0.0                                       # fracción del portafolio con desglose
    riesgo: float | None = None                                  # renta variable + alternativos, en % de lo que tiene desglose
    comision: float | None = None                                # fracción ponderada (0,01 = 1%)
    comision_cobertura: float = 0.0
    n: int = 0
    sin_desglose: list[str] = field(default_factory=list)


def resumir(items: pd.DataFrame, catalogo: pd.DataFrame) -> Resumen:
    it = _items(items)
    it = it[it["peso"].fillna(0) > 0]
    res = Resumen(n=len(it))
    if it.empty:
        return res
    w = it.set_index("instrument_id")["peso"] / it["peso"].sum()
    cols = [c for c in breakdown_columns() if c in catalogo.columns]
    funds = catalogo.drop_duplicates("instrument_id").set_index("instrument_id")[cols]
    exp = portfolio_exposure(w[~w.index.duplicated()], funds)
    res.cobertura = exp.cobertura
    if exp.cobertura > 0:
        res.clase = {k: v / exp.cobertura * 100 for k, v in exp.clase.items()}
        res.rv_categorias = {k: v / exp.cobertura * 100 for k, v in exp.rv_categorias.items()}
        res.rf_categorias = {k: v / exp.cobertura * 100 for k, v in exp.rf_categorias.items()}
        res.moneda = {k: v / exp.cobertura * 100 for k, v in exp.moneda.items()}
        res.riesgo = res.clase.get("Renta Variable", 0.0) + res.clase.get("Alternativos", 0.0)
    cubiertos = set(funds.index[funds[[c for c in ("pct_renta_variable", "pct_alternativos", "pct_rf_local", "pct_rf_high_yield_internacional", "pct_rf_investment_grade") if c in funds.columns]].notna().all(axis=1)]) if len(funds) else set()
    res.sin_desglose = [str(n) for iid, n in zip(it["instrument_id"], it["nombre"]) if iid not in cubiertos]
    res.comision, res.comision_cobertura = comision_ponderada(it)
    return res


def comision_ponderada(items: pd.DataFrame) -> tuple[float | None, float]:
    """(comisión ponderada por peso sobre las líneas que tienen comisión, fracción del portafolio con ese dato)."""
    it = _items(items)
    con = it[it["peso"].fillna(0).gt(0) & it["comision"].notna()]
    total = float(it["peso"].fillna(0).sum())
    if con.empty or total <= 0:
        return None, 0.0
    peso = float(con["peso"].sum())
    return float((con["peso"] * con["comision"].astype(float)).sum() / peso), peso / total


# ── Avisos que no bloquean ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def fuera_de_banda(resumen: Resumen, perfil_norm: str | None, config: dict | None = None) -> list[Issue]:
    """Aviso si el riesgo (renta variable + alternativos) cae fuera de la banda del perfil del cliente."""
    c = config or cfg()
    banda = c["bandas"].get(str(perfil_norm or "").upper())
    if banda is None or resumen.riesgo is None:
        return []
    if resumen.riesgo > banda["riesgo_max"] + 1e-9:
        return [Issue("warning", SHEET, f"Renta variable + alternativos en {resumen.riesgo:.1f}%: {resumen.riesgo - banda['riesgo_max']:.1f} pp sobre la banda del perfil ({banda['riesgo_min']}% a {banda['riesgo_max']}%).")]
    if resumen.riesgo < banda["riesgo_min"] - 1e-9:
        return [Issue("warning", SHEET, f"Renta variable + alternativos en {resumen.riesgo:.1f}%: {banda['riesgo_min'] - resumen.riesgo:.1f} pp bajo la banda del perfil ({banda['riesgo_min']}% a {banda['riesgo_max']}%).")]
    return []


def desactualizado(creado_en, hoy: date, perfil_al_guardar: str | None, perfil_actual: str | None, config: dict | None = None) -> str | None:
    """Motivo por el que un portafolio vigente se considera desactualizado, o None. Pasados N meses o si el perfil del cliente cambió desde que se guardó."""
    c = config or cfg()
    if perfil_al_guardar and perfil_actual and str(perfil_al_guardar).upper() != str(perfil_actual).upper():
        return f"el perfil del cliente cambió de {perfil_al_guardar} a {perfil_actual} desde que se guardó"
    f = creado_en.date() if isinstance(creado_en, datetime) else creado_en
    meses = (hoy.year - f.year) * 12 + hoy.month - f.month - (1 if hoy.day < f.day else 0)
    if meses >= c["desactualizado_meses"]:
        return f"se guardó hace {meses} meses (más de {c['desactualizado_meses']})"
    return None


def comparar_versiones(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """Diferencias entre dos versiones: instrumento, peso en cada una y diferencia (b − a), con el estado (nuevo, quitado, cambió, igual)."""
    a, b = _items(a), _items(b)
    m = a[["instrument_id", "nombre", "peso"]].merge(b[["instrument_id", "nombre", "peso"]], on="instrument_id", how="outer", suffixes=("_a", "_b"))
    m["nombre"] = m["nombre_b"].where(m["nombre_b"].notna(), m["nombre_a"])
    m["peso_a"], m["peso_b"] = m["peso_a"].fillna(0.0).astype(float), m["peso_b"].fillna(0.0).astype(float)
    m["dif"] = m["peso_b"] - m["peso_a"]
    m["estado"] = ["nuevo" if x == 0 and y > 0 else "quitado" if y == 0 and x > 0 else "cambió" if abs(d) > 0.005 else "igual" for x, y, d in zip(m["peso_a"], m["peso_b"], m["dif"])]
    return m[["instrument_id", "nombre", "peso_a", "peso_b", "dif", "estado"]].sort_values("dif", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)


# ── Conectar con el resto del dashboard ─────────────────────────────────────────────────────────────────────────────────────────────────────
def a_filas_carteras(items: pd.DataFrame, arquitectura: str, perfil: str, perfil_norm: str | None, catalogo: pd.DataFrame) -> pd.DataFrame:
    """El portafolio como filas del formato de la hoja de carteras (arquitectura × perfil × instrumento × peso), para `rebalance`, `series`, `exposure` y `alignment`."""
    it = _items(items)
    it = it[it["peso"].fillna(0) > 0]
    modelos = pd.DataFrame({"arquitectura": arquitectura, "perfil": perfil, "perfil_norm": perfil_norm, "instrument_id": it["instrument_id"].map(lambda v: str(v)[len(EXTERNO):] if es_externo(v) else v),
                            "peso_objetivo": it["peso"] / 100})
    out = a_carteras(catalogo, modelos)
    ext = it["instrument_id"].map(es_externo).values
    for col_out, col_item in (("instrumento", "nombre"), ("diccionario", "nombre"), ("serie", "serie"), ("comision", "comision")):
        valores = it[col_item].values
        out[col_out] = [v if e and pd.notna(v) else o for o, v, e in zip(out[col_out], valores, ext)]
    # la serie y la comisión elegidas por el advisor mandan (el catálogo puede haber cambiado desde que guardó)
    out["serie"] = [s if pd.notna(s) else o for o, s in zip(out["serie"], it["serie"].values)]
    out["comision"] = [c if pd.notna(c) else o for o, c in zip(out["comision"], it["comision"].values)]
    return out[CARTERAS_COLS].reset_index(drop=True)


def ajuste(pos: pd.DataFrame, items: pd.DataFrame, catalogo: pd.DataFrame, alias: pd.DataFrame | None, perfil: str, perfil_norm: str | None,
           base_clp: float | None = None, tolerancia_pp: float = 1.0) -> pd.DataFrame | None:
    """Qué comprar y vender para pasar de lo que tiene hoy al objetivo (el mismo cálculo del rebalanceo del dashboard). None si el portafolio está vacío."""
    objetivo = a_filas_carteras(items, "objetivo", perfil, perfil_norm, catalogo)
    if objetivo.empty:
        return None
    resto_filas = a_carteras(catalogo, pd.DataFrame({"arquitectura": "catalogo", "perfil": "-", "perfil_norm": pd.NA, "instrument_id": catalogo["instrument_id"], "peso_objetivo": 0.0}))
    carteras = pd.concat([objetivo, resto_filas], ignore_index=True)
    reconocidas = reconocer_posiciones(pos, catalogo, alias)
    p = reconocidas.assign(isin=reconocidas["instrument_id"].where(reconocidas["instrument_id"].notna(), reconocidas["isin"]))
    return plan_rebalanceo(p, carteras, "objetivo", perfil, base_clp=base_clp, tolerancia_pp=tolerancia_pp)


# ── Edición en pantalla ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def aplicar_edicion(base: pd.DataFrame, pesos, quitar) -> tuple[pd.DataFrame, bool]:
    """Aplica lo que el advisor editó en la tabla (pesos nuevos y líneas marcadas para quitar) sobre `base`, en el mismo orden de filas.
    Devuelve (portafolio resultante sin las líneas quitadas, si se quitó alguna)."""
    out = _items(base)
    out["peso"] = pd.to_numeric(pd.Series(list(pesos)), errors="coerce").values
    marcadas = [bool(q) for q in quitar]
    return out[[not q for q in marcadas]].reset_index(drop=True), any(marcadas)


def agregar(items: pd.DataFrame, catalogo: pd.DataFrame, instrument_id: str) -> pd.DataFrame:
    """Suma un instrumento de la lista con lo que falta para llegar a 100% (0 si ya se pasó). Si ya está, no cambia nada."""
    it = _items(items)
    if instrument_id in set(it["instrument_id"]):
        return it
    faltante = max(0.0, round(100 - float(it["peso"].fillna(0).sum()), 2))
    fila = pd.DataFrame([item_desde_catalogo(catalogo, instrument_id, faltante)])
    return pd.concat([it, fila], ignore_index=True) if not it.empty else _items(fila)


def tabla_hoy(pos: pd.DataFrame, catalogo: pd.DataFrame, alias: pd.DataFrame | None = None) -> pd.DataFrame:
    """Lo que el cliente tiene hoy, para mostrar: instrumento, serie, valor, peso (%) y si está en la lista de instrumentos (`en_lista`) y cómo se reconoció (`via`).
    Ordenado de mayor a menor valor."""
    cols = ["instrument_id", "nombre", "serie", "valor_clp", "peso", "en_lista", "via"]
    if pos.empty or pos["valor_clp"].sum() <= 0:
        return pd.DataFrame(columns=cols)
    p = reconocer_posiciones(pos, catalogo, alias)
    total = float(p["valor_clp"].sum())
    cat = catalogo.drop_duplicates("instrument_id").set_index("instrument_id")
    filas = []
    for iid, g in p[p["instrument_id"].notna()].groupby("instrument_id"):
        filas.append({"instrument_id": iid, "nombre": cat.loc[iid, "nombre"], "serie": cat.loc[iid, "serie"], "valor_clp": float(g["valor_clp"].sum()),
                      "en_lista": True, "via": g["via"].iloc[0]})
    sin = p[p["instrument_id"].isna()]
    for clave, g in sin.groupby(sin["isin"].astype(str)):
        nombre = g["instrumento"].iloc[0] if "instrumento" in g.columns and pd.notna(g["instrumento"].iloc[0]) else clave
        filas.append({"instrument_id": EXTERNO + clave, "nombre": nombre, "serie": pd.NA, "valor_clp": float(g["valor_clp"].sum()), "en_lista": False, "via": pd.NA})
    out = pd.DataFrame(filas)
    out["peso"] = out["valor_clp"] / total * 100
    return out[cols].sort_values("valor_clp", ascending=False).reset_index(drop=True)


# ── Aplicar los portafolios guardados al conjunto de datos ────────────────────────────────────────────────────────────────────────────────
def aplicar_portafolios(ds: Dataset, vigentes: pd.DataFrame, catalogo: pd.DataFrame) -> Dataset:
    """Dataset donde cada cliente con portafolio vigente tiene como arquitectura «personalizada:<rut>» y su portafolio como filas de `carteras`, de modo que
    el rebalanceo, la evaluación de series, la exposición y el alineamiento funcionan sin cambios. Los modelos de la casa quedan en `carteras_casa`.
    `vigentes`: la tabla de `Store.portafolios_vigentes()`. Un portafolio de un RUT que ya no está en los datos se ignora."""
    if vigentes is None or vigentes.empty:
        return ds
    clientes = ds.clientes.copy()
    perfiles = clientes.set_index("rut")["perfil_norm"].to_dict() if "perfil_norm" in clientes.columns else {}
    filas, con_portafolio = [], []
    for rut, g in vigentes.groupby("rut"):
        if rut not in perfiles:
            continue
        filas.append(a_filas_carteras(g[ITEM_COLS], PREFIJO_PERSONALIZADA + rut, PERFIL_PERSONALIZADO, perfiles[rut], catalogo))
        con_portafolio.append(rut)
    if not filas:
        return ds
    clientes["arquitectura_casa"] = clientes["arquitectura"] if "arquitectura" in clientes.columns else pd.NA
    clientes["arquitectura"] = [PREFIJO_PERSONALIZADA + r if r in set(con_portafolio) else a for r, a in zip(clientes["rut"], clientes["arquitectura_casa"])]
    carteras = pd.concat([ds.carteras, *filas], ignore_index=True)
    nuevo = replace(ds, clientes=clientes, carteras=carteras, carteras_casa=ds.carteras)
    desvios = desvio_vs_objetivo(nuevo, con_portafolio, vigentes, catalogo)
    if len(desvios):
        col = nuevo.clientes["desvio_modelo_pct"] if "desvio_modelo_pct" in nuevo.clientes.columns else pd.Series(float("nan"), index=nuevo.clientes.index)
        nuevo.clientes["desvio_modelo_pct"] = [desvios.get(r, v) for r, v in zip(nuevo.clientes["rut"], col)]
    return nuevo


def _clave_fondo(items: pd.DataFrame, catalogo: pd.DataFrame) -> pd.Series:
    """Fondo al que pertenece cada instrumento: sus series distintas comparten clave (el «diccionario» del catálogo). Un externo o un instrumento sin
    diccionario es su propio fondo."""
    cat = catalogo.drop_duplicates("instrument_id").set_index("instrument_id")["diccionario"].to_dict()
    claves = []
    for iid in items["instrument_id"]:
        d = cat.get(iid)
        claves.append(str(d) if d is not None and pd.notna(d) and str(d).strip() else str(iid))
    return pd.Series(claves, index=items.index)


def desvio_absoluto(hoy: pd.DataFrame, objetivo: pd.DataFrame, catalogo: pd.DataFrame) -> float:
    """Desvío del portafolio del cliente contra su objetivo: suma, sobre los instrumentos, de la diferencia absoluta de peso (en puntos porcentuales).
    Las series distintas de un mismo instrumento se suman antes de comparar."""
    def por_fondo(df: pd.DataFrame) -> pd.Series:
        it = _items(df)
        it = it[it["peso"].fillna(0) > 0]
        return it["peso"].astype(float).groupby(_clave_fondo(it, catalogo)).sum()
    a, b = por_fondo(hoy), por_fondo(objetivo)
    return float(a.sub(b, fill_value=0.0).abs().sum())


def avisos_desvio(hoy: pd.DataFrame, objetivo: pd.DataFrame, catalogo: pd.DataFrame, config: dict | None = None) -> list[Issue]:
    """Aviso si el desvío absoluto total pasa del límite (`desvio_max_pp`). No bloquea nada: el criterio es del advisor."""
    c = config or cfg()
    d = desvio_absoluto(hoy, objetivo, catalogo)
    if d > c["desvio_max_pp"] + 1e-9:
        return [Issue("warning", SHEET, f"El portafolio del cliente se desvía {d:.1f} pp del objetivo (suma de diferencias absolutas por instrumento); el límite es {c['desvio_max_pp']:g} pp.")]
    return []


def avisos_consolidar(items: pd.DataFrame, catalogo: pd.DataFrame) -> list[Issue]:
    """Aviso por cada instrumento con más de una serie con peso: conviene consolidar las series en una."""
    it = _items(items)
    it = it[it["peso"].fillna(0) > 0]
    claves = _clave_fondo(it, catalogo)
    out = []
    for _, g in it.groupby(claves):
        if g["instrument_id"].nunique() > 1:
            series = ", ".join(str(s) if pd.notna(s) else "—" for s in g["serie"])
            out.append(Issue("warning", SHEET, f"{g['nombre'].iloc[0]}: tiene {len(g)} series ({series}). Conviene consolidarlas en una; para el desvío se suman."))
    return out


def desvio_vs_objetivo(ds: Dataset, ruts: list[str], vigentes: pd.DataFrame, catalogo: pd.DataFrame) -> dict[str, float]:
    """Desvío absoluto total (pp) de cada cliente contra su portafolio guardado por el advisor, para los clientes con posiciones."""
    por_rut = {r: g for r, g in ds.posiciones.groupby("rut")} if len(ds.posiciones) else {}
    out = {}
    for rut in ruts:
        pos = por_rut.get(rut)
        obj = vigentes[vigentes["rut"] == rut]
        if pos is None or obj.empty or pos["valor_clp"].sum() <= 0:
            continue
        out[rut] = desvio_absoluto(desde_posiciones(pos, catalogo), obj[ITEM_COLS], catalogo)
    return out


SIN_DEFINIR, DEFINIDO, DESACTUALIZADO = "Sin definir", "Definido", "Desactualizado"


def estado_portafolios(view: pd.DataFrame, resumen: pd.DataFrame | None, hoy: date, config: dict | None = None) -> pd.DataFrame:
    """Agrega a los clientes `portafolio_version` y `portafolio_estado` (sin definir, definido o desactualizado) y `portafolio_motivo`. `resumen` es la tabla de
    `Store.resumen_portafolios_vigentes()`; sin ella (sin base de datos) todos quedan sin definir."""
    out = view.copy()
    por_rut = {} if resumen is None or resumen.empty else resumen.set_index("rut").to_dict("index")
    perfiles = out["perfil_norm"] if "perfil_norm" in out.columns else pd.Series([None] * len(out), index=out.index)
    versiones, estados, motivos = [], [], []
    for rut, perfil in zip(out["rut"], perfiles):
        r = por_rut.get(rut)
        if r is None:
            versiones.append(pd.NA), estados.append(SIN_DEFINIR), motivos.append("")
            continue
        motivo = desactualizado(r["creado_en"], hoy, r["perfil_al_guardar"], None if pd.isna(perfil) else perfil, config)
        versiones.append(int(r["version"])), estados.append(DESACTUALIZADO if motivo else DEFINIDO), motivos.append(motivo or "")
    out["portafolio_version"], out["portafolio_estado"], out["portafolio_motivo"] = versiones, estados, motivos
    return out


def contar_estados(view: pd.DataFrame) -> dict:
    """Cuántos clientes de `view` tienen el portafolio definido, desactualizado o sin definir, y el % con portafolio (definido o desactualizado)."""
    n = len(view)
    e = view["portafolio_estado"] if "portafolio_estado" in view.columns else pd.Series([SIN_DEFINIR] * n)
    definidos, desact = int((e == DEFINIDO).sum()), int((e == DESACTUALIZADO).sum())
    return {"n": n, "definidos": definidos, "desactualizados": desact, "sin_definir": n - definidos - desact,
            "pct_con_portafolio": (definidos + desact) / n * 100 if n else None}


# ── Avisos del cambio: series y tributación ─────────────────────────────────────────────────────────────────────────────────────────────
def avisos_series(items: pd.DataFrame, catalogo: pd.DataFrame) -> list[Issue]:
    """Aviso si el fondo elegido tiene otra serie activa más barata en la lista. No dice cuál conviene: puede haber requisitos de monto o de canal que el sistema no ve."""
    it = _items(items)
    cat = catalogo.drop_duplicates("instrument_id")
    cat = cat[cat["activo"].astype(bool) & cat["comision"].notna() & cat["diccionario"].notna()]
    out = []
    for _, r in it[it["peso"].fillna(0) > 0].iterrows():
        fila = cat[cat["instrument_id"] == r["instrument_id"]]
        if fila.empty or pd.isna(r["comision"]):
            continue
        mismas = cat[(cat["diccionario"] == fila["diccionario"].iloc[0]) & (cat["comision"] < float(r["comision"]) - 1e-9)]
        if mismas.empty:
            continue
        mejor = mismas.sort_values("comision").iloc[0]
        serie = mejor["serie"] if pd.notna(mejor["serie"]) else mejor["instrument_id"]
        out.append(Issue("warning", SHEET, f"{r['nombre']}: la serie {r['serie'] if pd.notna(r['serie']) else '—'} cobra {float(r['comision']) * 100:.2f}% y existe la serie {serie} "
                                           f"del mismo fondo a {float(mejor['comision']) * 100:.2f}% (puede tener requisitos de monto o de canal)."))
    return out


def impuesto_estimado(pos: pd.DataFrame, items: pd.DataFrame, catalogo: pd.DataFrame, alias: pd.DataFrame | None = None) -> pd.DataFrame:
    """Impuesto estimado de las ventas que implica llegar al objetivo: por posición reconocida cuyo peso objetivo es menor que el de hoy, la fracción que se vende
    por el `costo_tributario_clp` de la posición (que entrega el cálculo tributario externo). Columnas: nombre, fraccion_vendida, impuesto_clp, beneficio."""
    cols = ["nombre", "fraccion_vendida", "impuesto_clp", "beneficio"]
    if pos.empty or "costo_tributario_clp" not in pos.columns:
        return pd.DataFrame(columns=cols)
    p = reconocer_posiciones(pos, catalogo, alias)
    total = float(p["valor_clp"].sum())
    if total <= 0:
        return pd.DataFrame(columns=cols)
    objetivo = _items(items).groupby("instrument_id")["peso"].sum()
    cat = catalogo.drop_duplicates("instrument_id").set_index("instrument_id")
    filas = []
    claves = p["instrument_id"].where(p["instrument_id"].notna(), EXTERNO + p["isin"].astype(str))
    for iid, g in p.groupby(claves):
        hoy_pct = float(g["valor_clp"].sum()) / total * 100
        meta = float(objetivo.get(iid, 0.0))
        fraccion = max(0.0, (hoy_pct - meta) / hoy_pct) if hoy_pct > 0 else 0.0
        impuesto = float(g["costo_tributario_clp"].fillna(0).sum()) * fraccion
        if fraccion > 0 and impuesto > 0:
            nombre = cat.loc[iid, "nombre"] if iid in cat.index else (g["instrumento"].iloc[0] if "instrumento" in g.columns else iid)
            ben = cat.loc[iid, "beneficio_tributario"] if iid in cat.index else pd.NA
            filas.append({"nombre": nombre, "fraccion_vendida": fraccion, "impuesto_clp": impuesto, "beneficio": ben if pd.notna(ben) else "-"})
    return pd.DataFrame(filas, columns=cols).sort_values("impuesto_clp", ascending=False).reset_index(drop=True)
