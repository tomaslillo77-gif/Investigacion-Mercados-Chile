import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from wm.config import load_config

ROOT = Path(__file__).resolve().parent.parent
CLIENT_REQUIRED = ["rut", "entidad", "household", "servicio", "wm", "advisor", "perfil",
                   "perfil_norm", "ultima_reunion", "aum_clp", "cad_usd_mm"]
POSICION_REQUIRED = ["rut", "instrumento", "tipo", "isin", "valor_clp"]


class DatasetNotFound(Exception):
    pass


class DatasetCorrupt(Exception):
    pass


CLIENT_CRITICAL = ["rut", "servicio", "advisor", "aum_clp"]
CLIENT_NUMERIC = ["share_of_wallet_pct", "desvio_modelo_pct", "aportes_periodo", "retiros_periodo",
                  "rentabilidad_12m_pct", "comision_anual_clp", "comision_cobrada_clp",
                  "com_tra_renta_variable_clp", "com_tra_renta_fija_clp", "com_tra_intermediacion_clp",
                  "com_tra_allfunds_clp"]


@dataclass
class Dataset:
    clientes: pd.DataFrame
    posiciones: pd.DataFrame
    carteras: pd.DataFrame
    as_of: datetime
    missing_sheets: list[str]
    duplicate_ruts: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    invalid_cells: dict[str, int] = field(default_factory=dict)
    flujos: pd.DataFrame | None = None   # rut, periodo, aportes_clp, retiros_clp (opcional)
    carteras_casa: pd.DataFrame | None = None   # solo los modelos de la casa, cuando `carteras` incluye además los portafolios definidos por los advisors

    def casa(self) -> pd.DataFrame:
        """La hoja de carteras sin los portafolios personalizados: de aquí salen la lista de instrumentos y los modelos de la casa."""
        return self.carteras_casa if self.carteras_casa is not None else self.carteras


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", str(text))
    return "".join(c for c in text if unicodedata.category(c) != "Mn").strip().lower()


def normalize_servicio(raw) -> str:
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return "Sin clasificar"
    equiv = load_config("servicios")["equivalencias"]
    return equiv.get(_fold(raw), "Sin clasificar")


def parse_money(raw) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    if raw is None:
        return float("nan")
    cleaned = re.sub(r"[^0-9.\-]", "", str(raw).replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return float("nan")


def parse_number(raw) -> float:
    """Número tolerante: '35%', '15,1' (coma decimal), '1,234.5', ' 7 '."""
    if isinstance(raw, (int, float)):
        return float(raw)
    if raw is None:
        return float("nan")
    t = re.sub(r"[%\s]", "", str(raw))
    if "," in t and "." not in t:
        t = t.replace(",", ".")
    else:
        t = t.replace(",", "")
    try:
        return float(t)
    except ValueError:
        return float("nan")


def normalize_rut(raw) -> str:
    """Misma forma del RUT en todas las hojas: sin puntos, guion ni espacios, en mayúsculas ('12.345.678-k' -> '12345678K').
    Un RUT numérico que Excel guardó como decimal (12345678.0) pierde el '.0'. Los códigos como 'RUT_1' no cambian."""
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)
    t = str(raw).strip()
    if re.fullmatch(r"\d+\.0", t):
        t = t[:-2]
    return re.sub(r"[.\-\s]", "", t).upper()


def _fold_col(text) -> str:
    return re.sub(r"\s+", " ", _fold(text))


def _alinear_encabezados(raw: pd.DataFrame, claves) -> pd.DataFrame:
    """Reconoce un encabezado aunque difiera en tildes, mayúsculas o espacios de más: lo renombra al que espera config/excel.yaml."""
    por_forma = {_fold_col(k): k for k in claves}
    nuevos = {c: por_forma[_fold_col(c)] for c in raw.columns if _fold_col(c) in por_forma and c != por_forma[_fold_col(c)]}
    return raw.rename(columns=nuevos) if nuevos else raw


def _read_sheet(xl: pd.ExcelFile, sheet: str, header: int) -> pd.DataFrame | None:
    return pd.read_excel(xl, sheet_name=sheet, header=header) if sheet in xl.sheet_names else None


def _empty(cols: list[str]) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in cols})


def _build_clientes(raw: pd.DataFrame, mapping: dict) -> tuple[pd.DataFrame, list[str], dict[str, int]]:
    df = raw.rename(columns={k: v for k, v in mapping.items() if k in raw.columns})
    df = df.loc[:, ~df.columns.duplicated()]
    missing_required = [c for c in CLIENT_CRITICAL if c not in df.columns]
    invalid: dict[str, int] = {}
    for col in CLIENT_NUMERIC:
        if col in df.columns:
            parsed = df[col].map(parse_number)
            bad = int((df[col].notna() & parsed.isna()).sum())
            if bad:
                invalid[col] = bad
            df[col] = parsed
    for col in CLIENT_REQUIRED:
        if col not in df.columns:
            df[col] = pd.NA
    df["rut"] = df["rut"].map(lambda v: normalize_rut(v) if pd.notna(v) else None)
    df = df[df["rut"].notna()].drop_duplicates("rut").copy()
    df["servicio"] = df["servicio"].map(normalize_servicio)
    df["aum_clp"] = df["aum_clp"].map(parse_money)
    df["cad_usd_mm"] = pd.to_numeric(df["cad_usd_mm"], errors="coerce")
    for col in ("ultima_reunion", "ultimo_contacto", "fecha_wealth_plan"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    keep = [c for c in df.columns if c in set(mapping.values())]
    return df[keep].reset_index(drop=True), missing_required, invalid


def _build_posiciones(raw: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    df = raw.rename(columns={k: v for k, v in mapping.items() if k in raw.columns})
    df = df.loc[:, ~df.columns.duplicated()]
    if "valor_clp" not in df.columns and "Valor de Mercado" in raw.columns:
        df["valor_clp"] = raw["Valor de Mercado"].map(parse_money)
    for col in POSICION_REQUIRED:
        if col not in df.columns:
            df[col] = pd.NA
    df["rut"] = df["rut"].map(lambda v: normalize_rut(v) if pd.notna(v) else None)
    df = df[df["rut"].notna()].copy()
    df["valor_clp"] = df["valor_clp"].map(parse_money)
    if "gp_no_realizada" in df.columns:
        df["gp_no_realizada"] = df["gp_no_realizada"].map(parse_money)
    if "rent_no_realizada" in df.columns:
        df["rent_no_realizada"] = df["rent_no_realizada"].map(parse_number)
    if "costo_tributario_clp" in df.columns:  # impuesto estimado si se vende; lo entrega el cálculo tributario externo
        df["costo_tributario_clp"] = df["costo_tributario_clp"].map(parse_money)
    keep = [c for c in df.columns if c in set(mapping.values())]
    return df[keep].reset_index(drop=True)


def normalize_beneficio(raw) -> str:
    """Beneficio tributario de la serie: '107' o '108' (LIR); cualquier otra cosa, sin beneficio ('-')."""
    m = re.search(r"\b(107|108)\b", str(raw))
    return m.group(1) if m else "-"


def _build_flujos(raw: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    df = raw.rename(columns={k: v for k, v in mapping.items() if k in raw.columns})
    df = df.loc[:, ~df.columns.duplicated()]
    for col in mapping.values():
        if col not in df.columns:
            df[col] = pd.NA
    df["rut"] = df["rut"].map(lambda v: normalize_rut(v) if pd.notna(v) else None)
    df = df[df["rut"].notna() & df["periodo"].notna()].copy()
    df["periodo"] = pd.to_datetime(df["periodo"], errors="coerce").dt.strftime("%Y-%m-%d")
    for col in ("aportes_clp", "retiros_clp"):
        df[col] = df[col].map(parse_money).fillna(0.0)
    return df[list(mapping.values())].dropna(subset=["periodo"]).reset_index(drop=True)


def _build_carteras(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns=lambda c: re.sub(r"\s+", "_", str(c).strip().lower()))
    df = df.rename(columns={"perfil_normalizado": "perfil_norm"})
    if "beneficio_tributario" in df.columns:
        df["beneficio_tributario"] = df["beneficio_tributario"].map(normalize_beneficio)
    if "isin" in df.columns:  # fondos locales sin ISIN ("n.a."): un identificador propio por fondo, sin colisiones
        sin = df["isin"].isna() | df["isin"].astype(str).str.strip().str.lower().isin(["n.a.", "n.a", "na", "n/a", "", "nan", "none"])
        nombre = df["diccionario"] if "diccionario" in df.columns else df.get("instrumento", df["isin"])
        df.loc[sin, "isin"] = "SIN_ISIN::" + nombre.astype(str)[sin]
    return df


def load_dataset(path: Path | None = None) -> Dataset:
    cfg = load_config("excel")
    path = Path(path) if path else ROOT / cfg["ruta"]
    if not path.exists():
        raise DatasetNotFound(f"No se encontró el archivo de datos: {path}")
    header = cfg["header_row"]
    missing: list[str] = []
    frames: dict[str, pd.DataFrame | None] = {}
    try:
        xl = pd.ExcelFile(path)
        for key, sheet in cfg["hojas"].items():
            frames[key] = _read_sheet(xl, sheet, header)
            if frames[key] is None:
                missing.append(sheet)
            elif f"columnas_{key}" in cfg:   # tolera tildes, mayúsculas y espacios de más en los encabezados
                extra = ["Valor de Mercado"] if key == "posiciones" else []
                frames[key] = _alinear_encabezados(frames[key], list(cfg[f"columnas_{key}"]) + extra)
    except Exception as e:  # archivo dañado, truncado o que no es un Excel
        raise DatasetCorrupt(f"El archivo {path.name} está dañado o no es un Excel válido ({type(e).__name__}).") from e
    missing_required: list[str] = []
    invalid: dict[str, int] = {}
    if frames["clientes"] is not None:
        clientes, missing_required, invalid = _build_clientes(frames["clientes"], cfg["columnas_clientes"])
    else:
        clientes = _empty(CLIENT_REQUIRED)
    posiciones = (_build_posiciones(frames["posiciones"], cfg["columnas_posiciones"])
                  if frames["posiciones"] is not None else _empty(POSICION_REQUIRED))
    carteras = (_build_carteras(frames["carteras"])
                if frames["carteras"] is not None else _empty(["arquitectura", "perfil", "isin"]))
    flujos = None
    if cfg.get("hoja_flujos") and "hoja_flujos" in cfg and cfg["hoja_flujos"] in xl.sheet_names:
        crudo = pd.read_excel(xl, sheet_name=cfg["hoja_flujos"], header=header)
        flujos = _build_flujos(_alinear_encabezados(crudo, list(cfg["columnas_flujos"])), cfg["columnas_flujos"])
    dups: list[str] = []
    col_rut = None
    if frames["clientes"] is not None:   # la columna del RUT tal como se llama en este Excel (puede haber varias candidatas en la config)
        col_rut = next((k for k, v in cfg["columnas_clientes"].items() if v == "rut" and k in frames["clientes"].columns), None)
    if col_rut is not None:
        ruts = frames["clientes"][col_rut].dropna().map(normalize_rut)
        dups = sorted(ruts[ruts.duplicated()].unique())
    return Dataset(clientes, posiciones, carteras,
                   datetime.fromtimestamp(path.stat().st_mtime), missing, dups,
                   missing_required, invalid, flujos)
