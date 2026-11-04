"""Catálogo de instrumentos elegibles para armar portafolios de clientes.

Una fila por instrumento (`instrument_id` único). Es la lista desde la que el advisor elige y de donde salen las comisiones, series y el desglose
(look-through) para calcular exposiciones. Se mantiene en un Excel (hoja `Instrumentos`, y opcionalmente `Alias` con los nombres alternativos con
que un instrumento puede aparecer en las posiciones). Si no hay Excel, se deriva de la hoja de carteras actual con `desde_carteras`, sin perder nada
de lo que el resto del dashboard usa (`a_carteras` devuelve el mismo formato).
"""
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from wm.columns import ALT_COL, RF_COLS, RV_TOTAL, breakdown_columns, rv_columns
from wm.config import load_config
from wm.loader import parse_number
from wm.quality import Issue

IDENTIDAD = ["instrument_id", "nombre", "diccionario", "isin", "bloomberg", "nemotecnico", "run_fondo", "serie", "tipo", "moneda", "clase", "region", "activo"]
NUMEROS = ["comision", "yield", "duracion", "liquidez", "pct_uf"]
TRAZA = ["beneficio_tributario", "fecha_dato", "fuente_dato", "notas"]
NUMERICAS = NUMEROS + breakdown_columns()
SIN_DATO = {"", "n.a.", "n.a", "na", "n/a", "nan", "none", "-"}
MODELO_COLS = ["arquitectura", "perfil", "perfil_norm", "instrument_id", "peso_objetivo"]
# orden y nombres de la hoja de carteras actual, para que `a_carteras` devuelva lo mismo que lee el dashboard hoy
CARTERAS_COLS = ["arquitectura", "perfil", "instrumento", "diccionario", "isin", "bloomberg", "nemotecnico", "serie", "peso_objetivo", "comision", "yield",
                 "duracion", "liquidez", "pct_uf", "moneda", "perfil_norm"] + breakdown_columns() + ["beneficio_tributario"]


@dataclass
class Catalogo:
    instrumentos: pd.DataFrame
    alias: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=["tipo_id", "valor", "instrument_id"]))
    issues: list[Issue] = field(default_factory=list)


def columnas() -> list[str]:
    return IDENTIDAD + NUMEROS + [c for c in breakdown_columns() if c not in NUMEROS] + TRAZA


def _fold(texto: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", str(texto)) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", sin_tildes.strip().lower()).strip("_")


def _vacio(v) -> bool:
    if v is None or v is pd.NA or v is pd.NaT or (isinstance(v, float) and v != v):
        return True
    return str(v).strip().lower() in SIN_DATO


def clave(valor) -> str:
    """Forma comparable de un identificador: mayúsculas, sin espacios repetidos."""
    return re.sub(r"\s+", " ", str(valor).strip().upper())


# ── Derivación desde la hoja de carteras actual ───────────────────────────────────────────────────────────────────────────────────────────
def _clase_y_region(fila: pd.Series) -> tuple[str, str]:
    rf = float(sum(0.0 if pd.isna(fila.get(c)) else fila[c] for c in RF_COLS))
    rv = 0.0 if pd.isna(fila.get(RV_TOTAL)) else float(fila[RV_TOTAL])
    alt = 0.0 if pd.isna(fila.get(ALT_COL)) else float(fila[ALT_COL])
    if max(rf, rv, alt) <= 0:
        return "Otro", ""
    if rv >= rf and rv >= alt:
        regiones = {cat: (0.0 if pd.isna(fila.get(col)) else float(fila[col])) for cat, col in rv_columns().items()}
        return "Renta variable", max(regiones, key=regiones.get) if any(regiones.values()) else ""
    if rf >= alt:
        local = 0.0 if pd.isna(fila.get("pct_rf_local")) else float(fila["pct_rf_local"])
        return "Renta fija", "Local" if local >= rf / 2 else "Internacional"
    return "Alternativos", ""


def _tipo(isin: str, serie) -> str:
    if str(serie).strip().upper() == "ETF":
        return "ETF"
    if str(isin).startswith("SIN_ISIN"):
        return "Fondo mutuo local"
    base = str(isin).split("_")[0]
    if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", base):
        return "Fondo mutuo local" if base.startswith("CL") else "Fondo internacional"
    return "Otro"


def desde_carteras(carteras: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(catálogo, conflictos). Una fila por `isin` (la primera aparición manda). `conflictos` lista los instrumentos cuyos datos difieren entre filas
    de la hoja de carteras (comisión, serie, nombre…): el catálogo se queda con la primera y el resto se informa para que alguien lo revise."""
    c = carteras.copy()
    primero = c.drop_duplicates("isin").reset_index(drop=True)
    cat = pd.DataFrame({"instrument_id": primero["isin"], "isin": primero["isin"]})
    cat["nombre"] = primero["instrumento"] if "instrumento" in primero.columns else primero["isin"]
    cat["diccionario"] = primero["diccionario"] if "diccionario" in primero.columns else cat["nombre"]
    for col in ("bloomberg", "nemotecnico", "serie", "moneda", "comision", "yield", "duracion", "liquidez", "pct_uf", "beneficio_tributario"):
        cat[col] = primero[col] if col in primero.columns else pd.NA
    cat["run_fondo"] = pd.NA
    for col in breakdown_columns():
        if col not in cat.columns:
            cat[col] = primero[col] if col in primero.columns else pd.NA
    for col in NUMERICAS:   # la hoja trae «n.a.» en lo que no aplica: en el catálogo es un número o vacío
        cat[col] = _numerica(cat[col])
    cat["tipo"] = [_tipo(i, s) for i, s in zip(cat["isin"], cat["serie"])]
    clase_region = [_clase_y_region(f) for _, f in primero.iterrows()]
    cat["clase"], cat["region"] = [x[0] for x in clase_region], [x[1] for x in clase_region]
    cat["activo"] = True
    cat["fecha_dato"] = pd.NaT
    cat["fuente_dato"] = "Hoja de carteras del Excel"
    cat["notas"] = ""
    filas = []
    for col in ("instrumento", "bloomberg", "serie", "comision", "liquidez", "pct_uf"):
        if col not in c.columns:
            continue
        n = c.groupby("isin")[col].nunique(dropna=False)
        for isin in n[n > 1].index:
            valores = sorted({str(v) for v in c.loc[c["isin"] == isin, col]})
            filas.append({"instrument_id": isin, "campo": col, "valores": " | ".join(valores)})
    return cat[columnas()], pd.DataFrame(filas, columns=["instrument_id", "campo", "valores"])


def modelos_desde_carteras(carteras: pd.DataFrame) -> pd.DataFrame:
    """Los modelos (arquitectura × perfil × instrumento × peso) de la hoja de carteras."""
    m = carteras[[c for c in ("arquitectura", "perfil", "perfil_norm", "isin", "peso_objetivo") if c in carteras.columns]].copy()
    m = m.rename(columns={"isin": "instrument_id"})
    for col in MODELO_COLS:
        if col not in m.columns:
            m[col] = pd.NA
    return m[MODELO_COLS].reset_index(drop=True)


def a_carteras(catalogo: pd.DataFrame, modelos: pd.DataFrame) -> pd.DataFrame:
    """Modelos + catálogo en el formato de la hoja de carteras que leen `rebalance`, `series`, `exposure` y `alignment`.
    Un instrumento del modelo que no está en el catálogo sale con datos vacíos (no se descarta)."""
    cat = catalogo.drop_duplicates("instrument_id").set_index("instrument_id")
    m = modelos.copy()
    out = m.merge(cat, left_on="instrument_id", right_index=True, how="left", suffixes=("", "_cat"))
    out["isin"] = out["isin"].where(out["isin"].notna(), out["instrument_id"])
    out["instrumento"] = out["nombre"]
    for col in CARTERAS_COLS:
        if col not in out.columns:
            out[col] = pd.NA
    return out[CARTERAS_COLS].reset_index(drop=True)


# ── Lectura y validación ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={c: _fold(c) for c in df.columns})


def _numerica(serie: pd.Series) -> pd.Series:
    return serie.map(lambda v: float("nan") if _vacio(v) else parse_number(v))


def leer_catalogo(ruta, cfg: dict | None = None) -> Catalogo:
    """Lee el Excel del catálogo (ruta o archivo en memoria; hoja de instrumentos y, si existe, de alias). Los problemas de formato van en `issues`; un archivo ilegible lanza ValueError."""
    cfg = cfg or load_config("catalogo")
    ruta = ruta if hasattr(ruta, "read") else Path(ruta)
    archivo = getattr(ruta, "name", "catálogo")
    try:
        xl = pd.ExcelFile(ruta)
    except Exception as e:
        raise ValueError(f"No se pudo abrir el catálogo {archivo}: {type(e).__name__}") from e
    if cfg["hoja_instrumentos"] not in xl.sheet_names:
        raise ValueError(f"El catálogo {archivo} no tiene la hoja «{cfg['hoja_instrumentos']}».")
    df = _normalizar_columnas(pd.read_excel(xl, cfg["hoja_instrumentos"], header=cfg["header_row"]))
    df = df.dropna(how="all")
    for col in columnas():
        if col not in df.columns:
            df[col] = pd.NA
    for col in NUMERICAS:
        df[col] = _numerica(df[col])
    df["activo"] = df["activo"].map(lambda v: True if _vacio(v) else str(v).strip().lower() in {"true", "1", "si", "sí", "s", "x", "yes"})
    df["fecha_dato"] = pd.to_datetime(df["fecha_dato"], errors="coerce")
    for col in ("instrument_id", "isin"):
        df[col] = df[col].map(lambda v: pd.NA if _vacio(v) else str(v).strip())
    df["instrument_id"] = df["instrument_id"].where(df["instrument_id"].notna(), df["isin"])
    df["diccionario"] = df["diccionario"].where(df["diccionario"].notna(), df["nombre"])
    alias = pd.DataFrame(columns=["tipo_id", "valor", "instrument_id"])
    if cfg["hoja_alias"] in xl.sheet_names:
        alias = _normalizar_columnas(pd.read_excel(xl, cfg["hoja_alias"], header=cfg["header_row"])).dropna(how="all")
        for col in ("tipo_id", "valor", "instrument_id"):
            if col not in alias.columns:
                alias[col] = pd.NA
        alias = alias[["tipo_id", "valor", "instrument_id"]].reset_index(drop=True)
    inst = df[columnas()].reset_index(drop=True)
    return Catalogo(inst, alias, validar(inst, alias, cfg))


def validar(cat: pd.DataFrame, alias: pd.DataFrame | None = None, cfg: dict | None = None, hoy: date | None = None) -> list[Issue]:
    """Revisa el catálogo y dice dónde está cada problema (fila de Excel = posición + 2, por el encabezado)."""
    cfg = cfg or load_config("catalogo")
    hoy = hoy or date.today()
    tol = cfg["tolerancia_desglose"]
    out: list[Issue] = []

    def fila(i) -> str:
        return f"fila {i + 2}"

    def nombre(i) -> str:
        r = cat.loc[i]
        return f"{r['nombre'] if not _vacio(r['nombre']) else r['instrument_id']} ({fila(i)})"

    sin_id = cat.index[cat["instrument_id"].isna()]
    for i in sin_id:
        out.append(Issue("error", "catalogo", f"{fila(i)}: falta el identificador (instrument_id o ISIN)."))
    ids = cat["instrument_id"].dropna()
    for v in sorted(set(ids[ids.duplicated(keep=False)])):
        filas = ", ".join(str(i + 2) for i in ids.index[ids == v])
        out.append(Issue("error", "catalogo", f"El identificador «{v}» está repetido (filas {filas})."))
    for i, r in cat.iterrows():
        if pd.isna(r["instrument_id"]):
            continue
        if _vacio(r["nombre"]):
            out.append(Issue("warning", "catalogo", f"{fila(i)}: el instrumento «{r['instrument_id']}» no tiene nombre."))
        if r["activo"] and r["clase"] not in cfg["clases"]:
            out.append(Issue("error", "catalogo", f"{nombre(i)}: la clase «{r['clase']}» no es válida; las posibles son {', '.join(cfg['clases'])}."))
        if not _vacio(r["tipo"]) and r["tipo"] not in cfg["tipos"]:
            out.append(Issue("warning", "catalogo", f"{nombre(i)}: el tipo «{r['tipo']}» no está entre los conocidos."))
        if not _vacio(r["comision"]) and not 0 <= r["comision"] <= 0.2:
            out.append(Issue("warning", "catalogo", f"{nombre(i)}: la comisión {r['comision']} parece fuera de rango (va como fracción: 0,01 = 1%)."))
        pct = [c for c in breakdown_columns() if c in cat.columns and pd.notna(r[c])]
        if any(r[c] > 1 + tol for c in pct):
            out.append(Issue("warning", "catalogo", f"{nombre(i)}: hay porcentajes del desglose mayores que 1; deben ir como fracción (0,35 = 35%)."))
        clases_cols = RF_COLS + [RV_TOTAL, ALT_COL]
        if all(pd.notna(r[c]) for c in clases_cols) and abs(sum(r[c] for c in clases_cols) - 1) > tol:
            out.append(Issue("error", "catalogo", f"{nombre(i)}: renta fija + renta variable + alternativos no suman 100%."))
        rv = [c for c in rv_columns().values() if pd.notna(r[c])]
        if rv and pd.notna(r[RV_TOTAL]) and abs(sum(r[c] for c in rv) - r[RV_TOTAL]) > tol:
            out.append(Issue("error", "catalogo", f"{nombre(i)}: las categorías de renta variable no suman el total de renta variable."))
        moneda = [c for c in ("pct_moneda_usd", "pct_moneda_clp", "pct_moneda_uf", "pct_moneda_otras") if pd.notna(r[c])]
        if len(moneda) == 4 and abs(sum(r[c] for c in moneda) - 1) > tol:
            out.append(Issue("error", "catalogo", f"{nombre(i)}: la exposición de moneda no suma 100%."))
        if pd.notna(r["pct_uf"]) and pd.notna(r["pct_rf_local"]) and r["pct_uf"] > r["pct_rf_local"] + tol:
            out.append(Issue("error", "catalogo", f"{nombre(i)}: UF mayor que la renta fija local."))
        if pd.notna(r["fecha_dato"]) and (pd.Timestamp(hoy) - r["fecha_dato"]).days > cfg["obsoleto_dias"]:
            out.append(Issue("warning", "catalogo", f"{nombre(i)}: el desglose es del {r['fecha_dato']:%d-%m-%Y} (más de {cfg['obsoleto_dias']} días)."))
    isins = cat["isin"].dropna()
    isins = isins[~isins.astype(str).str.startswith("SIN_ISIN")]
    for v in sorted(set(isins[isins.duplicated(keep=False)])):
        out.append(Issue("warning", "catalogo", f"El ISIN «{v}» aparece en más de un instrumento."))
    if alias is not None and len(alias):
        conocidos = set(cat["instrument_id"].dropna())
        for i, r in alias.iterrows():
            if pd.isna(r["instrument_id"]) or str(r["instrument_id"]).strip() not in conocidos:
                out.append(Issue("error", "alias", f"fila {i + 2}: el alias «{r['valor']}» apunta a un instrumento que no está en el catálogo."))
            if _vacio(r["valor"]):
                out.append(Issue("error", "alias", f"fila {i + 2}: el alias no tiene valor."))
        dup = alias.assign(k=alias["valor"].map(clave)).groupby("k")["instrument_id"].nunique()
        for k in dup[dup > 1].index:
            out.append(Issue("error", "alias", f"El alias «{k}» apunta a más de un instrumento: no se puede resolver."))
    return out


# ── Reconocer identificadores (posiciones del cliente) ────────────────────────────────────────────────────────────────────────────────────
def resolver_ids(ids: pd.Series, cat: pd.DataFrame, alias: pd.DataFrame | None = None) -> pd.DataFrame:
    """Reconoce cada identificador (ISIN, nemotécnico, Bloomberg, instrument_id o alias) y devuelve `instrument_id` y `via`. Solo coincidencia **exacta**
    (sin distinguir mayúsculas ni espacios repetidos): nunca se adivina por parecido. Una clave que apunta a dos instrumentos no se usa."""
    fuentes = [("instrument_id", cat["instrument_id"], cat["instrument_id"]), ("isin", cat["isin"], cat["instrument_id"]),
               ("nemotecnico", cat["nemotecnico"], cat["instrument_id"]), ("bloomberg", cat["bloomberg"], cat["instrument_id"])]
    if alias is not None and len(alias):
        fuentes.append(("alias", alias["valor"], alias["instrument_id"]))
    tabla: dict[str, tuple[str, str]] = {}
    for via, claves, destinos in fuentes:
        locales: dict[str, set[str]] = {}
        for k, d in zip(claves, destinos):
            if _vacio(k) or _vacio(d):
                continue
            locales.setdefault(clave(k), set()).add(str(d).strip())
        for k, ds in locales.items():
            if len(ds) == 1 and k not in tabla:
                tabla[k] = (next(iter(ds)), via)
    hallado = [tabla.get(clave(v)) if not _vacio(v) else None for v in ids]
    return pd.DataFrame({"instrument_id": [h[0] if h else pd.NA for h in hallado], "via": [h[1] if h else pd.NA for h in hallado]}, index=ids.index)


def cargar_catalogo(carteras: pd.DataFrame, cfg: dict | None = None, raiz: Path | None = None) -> tuple[Catalogo, str]:
    """(catálogo, fuente). Si existe el Excel del catálogo (`ruta` de config/catalogo.yaml) se usa ese; si no, se deriva de la hoja de carteras.
    Un Excel dañado no deja al dashboard sin lista: se cae a la derivada y la fuente lo dice."""
    cfg = cfg or load_config("catalogo")
    ruta = (raiz or Path(__file__).resolve().parent.parent) / cfg["ruta"]
    if ruta.exists():
        try:
            return leer_catalogo(ruta, cfg), f"Excel del catálogo ({ruta.name})"
        except ValueError as e:
            cat, _ = desde_carteras(carteras)
            return Catalogo(cat, issues=[Issue("error", "catalogo", f"{e} Se usa la lista derivada de la hoja de carteras.")]), "Derivada de la hoja de carteras (el Excel del catálogo no se pudo leer)"
    cat, _ = desde_carteras(carteras)
    return Catalogo(cat, issues=validar(cat, None, cfg)), "Derivada de la hoja de carteras"


# ── Plantilla ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def plantilla() -> bytes:
    """Excel de ejemplo con datos ficticios: hojas `Instrumentos`, `Alias` e `Instrucciones`."""
    base = {c: pd.NA for c in columnas()}
    filas = [
        {**base, "instrument_id": "FICT-ACC-USA", "nombre": "Fondo Ficticio Acciones EE.UU.", "diccionario": "Ficticio acciones USA", "isin": "XX0000000011",
         "nemotecnico": "FICTUSA", "bloomberg": "FICTUSA CI Equity", "serie": "A", "tipo": "Fondo internacional", "moneda": "USD", "clase": "Renta variable",
         "region": "USA", "activo": True, "comision": 0.0075, "liquidez": 2, "pct_renta_variable": 1.0, "pct_rv_usa": 1.0, "pct_rf_local": 0.0,
         "pct_rf_high_yield_internacional": 0.0, "pct_rf_investment_grade": 0.0, "pct_alternativos": 0.0, "pct_moneda_usd": 1.0, "pct_moneda_clp": 0.0,
         "pct_moneda_uf": 0.0, "pct_moneda_otras": 0.0, "beneficio_tributario": "107", "fecha_dato": date(2026, 9, 30), "fuente_dato": "Ficha ficticia"},
        {**base, "instrument_id": "FICT-RF-UF", "nombre": "Fondo Ficticio Deuda UF", "diccionario": "Ficticio deuda UF", "isin": "CLFICT000012",
         "nemotecnico": "FICTUF", "serie": "B", "tipo": "Fondo mutuo local", "moneda": "CLP", "clase": "Renta fija", "region": "Local", "activo": True,
         "comision": 0.0055, "duracion": 3.2, "liquidez": 1, "pct_uf": 0.8, "pct_renta_variable": 0.0, "pct_rf_local": 1.0, "pct_rf_high_yield_internacional": 0.0,
         "pct_rf_investment_grade": 0.0, "pct_alternativos": 0.0, "pct_moneda_usd": 0.0, "pct_moneda_clp": 0.2, "pct_moneda_uf": 0.8, "pct_moneda_otras": 0.0,
         "beneficio_tributario": "-", "fecha_dato": date(2026, 9, 30), "fuente_dato": "Ficha ficticia"},
        {**base, "instrument_id": "FICT-ALT", "nombre": "Fondo Ficticio Real Estate Global", "diccionario": "Ficticio real estate", "isin": "XX0000000029",
         "serie": "I", "tipo": "Fondo internacional", "moneda": "USD", "clase": "Alternativos", "activo": True, "comision": 0.009, "liquidez": 3,
         "pct_renta_variable": 0.0, "pct_rf_local": 0.0, "pct_rf_high_yield_internacional": 0.0, "pct_rf_investment_grade": 0.0, "pct_alternativos": 1.0,
         "pct_moneda_usd": 1.0, "pct_moneda_clp": 0.0, "pct_moneda_uf": 0.0, "pct_moneda_otras": 0.0, "beneficio_tributario": "-",
         "fecha_dato": date(2026, 9, 30), "fuente_dato": "Ficha ficticia"},
    ]
    instrucciones = pd.DataFrame({"Cómo llenar el catálogo": [
        "DATOS FICTICIOS: bórralos y escribe los reales. Una fila por instrumento (y por serie, si la comisión cambia).",
        "instrument_id: clave estable y única. Si el instrumento tiene ISIN, usa el ISIN; si no, un código propio (por ejemplo LOC-RUN-SERIE).",
        "clase: Renta variable, Renta fija, Alternativos, Caja u Otro. region: texto libre (USA, Chile, Local…).",
        "activo: si es VERDADERO, el advisor lo puede elegir al armar un portafolio. Para retirar un instrumento, ponlo en FALSO (no borres la fila).",
        "comision y los porcentajes del desglose (pct_*) van como FRACCIÓN: 0,0075 = 0,75% y 0,35 = 35%.",
        "El desglose es opcional. Sin él, el instrumento se puede elegir, pero no entra en la exposición por región y moneda.",
        "Si lo completas: renta fija + renta variable + alternativos = 100%; las regiones de renta variable suman pct_renta_variable; la moneda suma 100%.",
        "fecha_dato y fuente_dato: de cuándo y de dónde es el desglose. Si pasan más de 120 días, se avisa que está obsoleto.",
        "Hoja Alias: otros nombres con que el instrumento aparece en las posiciones de los clientes (nemotécnico, RUN+serie, variantes). Un alias solo puede apuntar a un instrumento.",
        "Guarda el archivo como data/catalogo_instrumentos.xlsx."]})
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame(filas)[columnas()].to_excel(w, sheet_name="Instrumentos", index=False)
        pd.DataFrame([{"tipo_id": "nemo", "valor": "FICTUSA.SN", "instrument_id": "FICT-ACC-USA"}]).to_excel(w, sheet_name="Alias", index=False)
        instrucciones.to_excel(w, sheet_name="Instrucciones", index=False)
        w.sheets["Instrucciones"].column_dimensions["A"].width = 130
    return buf.getvalue()
