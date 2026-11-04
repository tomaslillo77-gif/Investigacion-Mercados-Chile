"""Carga masiva de portafolios objetivo desde un Excel: una fila por cliente e instrumento, con el peso en %.

Columnas: `rut`, `instrumento` (ISIN, nemotécnico, Bloomberg, instrument_id o alias de la lista de instrumentos) y `peso` (en %, 0 a 100). Se valida todo antes de aceptar
un cliente: el cliente existe, cada instrumento se reconoce en la lista (solo coincidencia exacta), no hay repetidos y los pesos suman 100%. Los errores no frenan a los
demás clientes: cada cliente se acepta o se rechaza completo, con su motivo y la fila del Excel.
"""
import io
import re
import unicodedata
from dataclasses import dataclass, field

import pandas as pd

from wm.catalogo import resolver_ids
from wm.loader import normalize_rut, parse_number
from wm.portafolio_cliente import cfg, item_desde_catalogo, validar
from wm.store import ConflictoDeVersion, StoreUnavailable

COLUMNAS = ["rut", "instrumento", "peso"]


@dataclass
class Resultado:
    portafolios: dict[str, pd.DataFrame] = field(default_factory=dict)       # rut -> ítems listos para guardar
    errores: list[dict] = field(default_factory=list)                          # {fila, rut, mensaje}

    @property
    def ok(self) -> bool:
        return not self.errores


def _fold(t) -> str:
    return re.sub(r"[^a-z0-9]+", "_", "".join(c for c in unicodedata.normalize("NFD", str(t).strip().lower()) if unicodedata.category(c) != "Mn")).strip("_")


def leer_portafolios(archivo, catalogo: pd.DataFrame, alias: pd.DataFrame | None, ruts_validos: set[str], config: dict | None = None) -> Resultado:
    """Lee el Excel (ruta o archivo en memoria, primera hoja) y arma los portafolios de los clientes que no tienen errores."""
    c = config or cfg()
    res = Resultado()
    try:
        raw = pd.read_excel(archivo, sheet_name=0)
    except Exception as e:
        res.errores.append({"fila": None, "rut": None, "mensaje": f"No se pudo leer el Excel ({type(e).__name__})."})
        return res
    raw = raw.rename(columns={col: {"id": "rut", "cliente": "rut", "isin": "instrumento", "instrument_id": "instrumento", "peso_": "peso", "peso_pct": "peso"}.get(_fold(col), _fold(col)) for col in raw.columns})
    faltan = [col for col in COLUMNAS if col not in raw.columns]
    if faltan:
        res.errores.append({"fila": None, "rut": None, "mensaje": f"Faltan las columnas {', '.join(faltan)} (se esperan: {', '.join(COLUMNAS)})."})
        return res
    raw = raw.dropna(how="all")
    raw["fila"] = raw.index + 2
    raw["rut"] = raw["rut"].map(lambda v: None if pd.isna(v) else normalize_rut(v))
    raw["peso"] = raw["peso"].map(lambda v: float("nan") if pd.isna(v) else parse_number(v))
    reconocidos = resolver_ids(raw["instrumento"], catalogo, alias)
    raw["instrument_id"] = reconocidos["instrument_id"].values
    for rut, g in raw.groupby(raw["rut"].fillna("(sin RUT)"), sort=False):
        malos: list[dict] = []
        if rut == "(sin RUT)":
            res.errores += [{"fila": int(f), "rut": None, "mensaje": "La fila no tiene RUT."} for f in g["fila"]]
            continue
        if rut not in ruts_validos:
            res.errores.append({"fila": int(g["fila"].iloc[0]), "rut": rut, "mensaje": "El cliente no existe o no es tuyo."})
            continue
        for _, r in g.iterrows():
            if pd.isna(r["instrument_id"]):
                malos.append({"fila": int(r["fila"]), "rut": rut, "mensaje": f"El instrumento «{r['instrumento']}» no se reconoce en la lista (ISIN, nemotécnico, Bloomberg o alias exactos)."})
            elif pd.isna(r["peso"]):
                malos.append({"fila": int(r["fila"]), "rut": rut, "mensaje": "El peso falta o no es un número."})
        if malos:
            res.errores += malos
            continue
        items = pd.DataFrame([item_desde_catalogo(catalogo, r["instrument_id"], r["peso"]) for _, r in g.iterrows()])
        problemas = [i.message for i in validar(items, catalogo, c) if i.level == "error"]
        if problemas:
            res.errores += [{"fila": int(g["fila"].iloc[0]), "rut": rut, "mensaje": m} for m in problemas]
            continue
        res.portafolios[rut] = items
    return res


def plantilla_portafolios(ejemplos: list[tuple[str, str, float]] | None = None) -> bytes:
    """Excel de ejemplo con datos ficticios y una hoja de instrucciones."""
    filas = ejemplos or [("RUT_00000001", "FICT-ACC-USA", 60.0), ("RUT_00000001", "FICT-RF-UF", 40.0), ("RUT_00000002", "FICT-RF-UF", 100.0)]
    instrucciones = pd.DataFrame({"Cómo llenar": [
        "DATOS FICTICIOS: bórralos y escribe los reales. Una fila por cliente e instrumento.",
        "rut: el RUT del cliente tal como está en el Excel de datos (solo clientes tuyos).",
        "instrumento: ISIN, nemotécnico, Bloomberg o código de la lista de instrumentos (tiene que coincidir exacto).",
        "peso: en porcentaje del portafolio, de 0 a 100. Los pesos de cada cliente deben sumar 100.",
        "Un cliente se acepta o se rechaza completo; los errores te dicen fila y motivo, y no frenan a los otros clientes.",
        "Cada cliente queda con una versión nueva (vigente) y origen «excel»."]})
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame(filas, columns=["rut", "instrumento", "peso"]).to_excel(w, sheet_name="Portafolios", index=False)
        instrucciones.to_excel(w, sheet_name="Instrucciones", index=False)
        w.sheets["Instrucciones"].column_dimensions["A"].width = 110
        for col, ancho in zip("ABC", (18, 28, 10)):
            w.sheets["Portafolios"].column_dimensions[col].width = ancho
    return buf.getvalue()


def guardar_masivo(store, res: Resultado, advisor: str, perfiles: dict[str, str | None]) -> tuple[list[str], list[str]]:
    """Guarda cada portafolio aceptado como versión nueva vigente (origen «excel»). Devuelve (ruts guardados, ruts que no se pudieron guardar porque otro advisor
    guardó mientras tanto o la base no respondió). Un fallo no detiene a los demás."""
    guardados, fallidos = [], []
    for rut, items in res.portafolios.items():
        try:
            hist = store.historial_portafolio(rut)
            store.guardar_portafolio(rut, items, advisor, "Carga masiva desde Excel", "excel", perfiles.get(rut), hist[0]["version"] if hist else 0)
            guardados.append(rut)
        except (ConflictoDeVersion, StoreUnavailable):
            fallidos.append(rut)
    return guardados, fallidos
