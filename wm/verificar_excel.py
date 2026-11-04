"""Revisa un Excel de datos antes de abrir el portal y explica, en lenguaje claro, qué corregir y dónde.

Solo informa nombres de hojas y de columnas, conteos y porcentajes: nunca RUT, nombres ni montos de clientes."""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path

import pandas as pd

from wm.config import load_config
from wm.loader import (CLIENT_CRITICAL, CLIENT_REQUIRED, POSICION_REQUIRED, DatasetCorrupt, DatasetNotFound,
                       _alinear_encabezados, _fold_col, load_dataset, normalize_rut)
from wm.quality import validate

ORDEN = {"error": 0, "aviso": 1, "info": 2}
LOCAL = "config/local/excel.yaml"


@dataclass
class Hallazgo:
    nivel: str      # error | aviso | info
    hoja: str
    mensaje: str
    ayuda: str = ""


def _canonicas(mapping: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for real, canon in mapping.items():
        out.setdefault(canon, []).append(real)
    return out


def _encabezados(xl: pd.ExcelFile, hoja: str, fila: int) -> list[str]:
    return [str(c) for c in pd.read_excel(xl, sheet_name=hoja, header=fila, nrows=0).columns]


def _formato_rut(v) -> str:
    t = str(v).strip()
    if re.fullmatch(r"\d{1,2}(\.\d{3}){2}-[\dkK]", t):
        return "con puntos y guion"
    if re.fullmatch(r"\d+-[\dkK]", t):
        return "con guion"
    if re.fullmatch(r"\d+(\.0)?", t):
        return "solo números"
    return "otro formato"


def _columnas(xl: pd.ExcelFile, clave: str, hoja: str, fila: int, mapping: dict, criticas: set[str], requeridas: set[str]) -> list[Hallazgo]:
    """Compara los encabezados reales de una hoja con lo que espera config/excel.yaml."""
    out: list[Hallazgo] = []
    reales = _encabezados(xl, hoja, fila)
    esperados = {_fold_col(k) for k in mapping}
    vistas = pd.read_excel(xl, sheet_name=hoja, header=None, nrows=15)
    aciertos = [sum(_fold_col(v) in esperados for v in vistas.iloc[i].dropna()) for i in range(len(vistas))]
    mejor = max(range(len(aciertos)), key=aciertos.__getitem__, default=fila)
    if aciertos and mejor != fila and aciertos[mejor] >= 3 and aciertos[mejor] > (aciertos[fila] if fila < len(aciertos) else 0):
        out.append(Hallazgo("error", hoja, f"Los encabezados esperados están en la fila {mejor + 1} de Excel, no en la que indica la configuración.",
                            f"Pon `header_row: {mejor}` en {LOCAL} (es el número de fila de los encabezados menos 1)."))
        return out
    alineados = {_fold_col(c) for c in reales}
    mapeados = {_fold_col(k) for k in mapping}
    sin_usar = [c for c in reales if _fold_col(c) not in mapeados]
    opcionales: list[str] = []
    for canon, nombres in _canonicas(mapping).items():
        if any(_fold_col(n) in alineados for n in nombres):
            continue
        nivel = "error" if canon in criticas else ("aviso" if canon in requeridas else "info")
        if nivel == "info":
            opcionales.append(canon)
            continue
        cercanos = get_close_matches(_fold_col(nombres[0]), [_fold_col(c) for c in sin_usar], n=1, cutoff=0.6)
        sugerida = next((c for c in sin_usar if cercanos and _fold_col(c) == cercanos[0]), None)
        if sugerida:
            ayuda = f"¿Será «{sugerida}»? Agrégalo en {LOCAL}:\n    columnas_{clave}:\n      {sugerida}: {canon}"
        elif nivel == "info":
            ayuda = "Es opcional: sin ella, esos cuadros dicen «Pendiente de datos»."
        else:
            ayuda = (f"Indica cómo se llama en tu Excel, en {LOCAL}:\n    columnas_{clave}:\n      <nombre en tu Excel>: {canon}"
                     + (f"\n  Columnas del archivo que el portal no usa: {', '.join(sin_usar[:15])}{'…' if len(sin_usar) > 15 else ''}" if sin_usar else ""))
        out.append(Hallazgo(nivel, hoja, f"No se encuentra la columna «{canon}» (se esperaba «{nombres[0]}»).", ayuda))
    if opcionales:
        out.append(Hallazgo("info", hoja, f"Columnas opcionales que no vienen ({len(opcionales)}): {', '.join(opcionales)}.",
                            "Sin ellas, los cuadros que las usan dicen «Pendiente de datos». No es un error."))
    return out


def _ruts(ds, hoja_p: str, hoja_f: str) -> list[Hallazgo]:
    out: list[Hallazgo] = []
    c = ds.clientes
    if c.empty or "rut" not in c.columns:
        return out
    en_clientes = set(c["rut"])
    p = ds.posiciones
    if len(p) and "rut" in p.columns:
        fuera = ~p["rut"].isin(en_clientes)
        if fuera.any():
            out.append(Hallazgo("aviso", hoja_p, f"{int(fuera.sum())} de {len(p)} posiciones tienen un RUT que no está en la hoja de clientes.",
                                "Suele ser un RUT escrito distinto entre hojas (con o sin puntos, guion o dígito verificador). El portal ya ignora puntos, guion y espacios; "
                                "si persiste, revisa que ambas hojas usen el mismo RUT."))
        sin_pos = len(en_clientes - set(p["rut"]))
        if sin_pos:
            out.append(Hallazgo("info", hoja_p, f"{sin_pos} de {len(en_clientes)} clientes no tienen posiciones.", "Aparecerán con la ficha vacía."))
    f = ds.flujos
    if f is not None and len(f) and "rut" in f.columns:
        fuera = ~f["rut"].isin(en_clientes)
        if fuera.any():
            out.append(Hallazgo("aviso", hoja_f, f"{int(fuera.sum())} de {len(f)} filas de flujos tienen un RUT que no está en la hoja de clientes.", ""))
    return out


def _patrimonio(ds, hoja: str) -> list[Hallazgo]:
    c, p = ds.clientes, ds.posiciones
    if c.empty or p.empty or "aum_clp" not in c.columns or "valor_clp" not in p.columns:
        return []
    suma = p.groupby("rut")["valor_clp"].sum()
    comp = c.set_index("rut")["aum_clp"].to_frame().join(suma.rename("pos")).dropna()
    comp = comp[comp["aum_clp"] > 0]
    if comp.empty:
        return []
    calzan = ((comp["pos"] - comp["aum_clp"]).abs() / comp["aum_clp"] <= 0.01).mean()
    nivel = "info" if calzan >= 0.8 else "aviso"
    ayuda = "" if nivel == "info" else "Revisa que `aum_clp` y `valor_clp` estén en la misma moneda y al mismo corte de fecha."
    return [Hallazgo(nivel, hoja, f"En {calzan:.0%} de los clientes, la suma de sus posiciones coincide (±1 %) con su patrimonio.", ayuda)]


def verificar(path: Path | str | None = None) -> list[Hallazgo]:
    cfg = load_config("excel")
    ruta = Path(path) if path else Path(cfg["ruta"])
    try:
        ds = load_dataset(ruta if path else None)
    except (DatasetNotFound, DatasetCorrupt) as e:
        return [Hallazgo("error", "archivo", str(e), "Revisa la ruta (`ruta` en config/excel.yaml o la variable WM_EXCEL) y que sea un .xlsx válido.")]
    out: list[Hallazgo] = []
    hojas = cfg["hojas"]
    for h in ds.missing_sheets:
        clave = next((k for k, v in hojas.items() if v == h), "")
        existentes = pd.ExcelFile(ruta if path else Path(cfg["ruta"])).sheet_names
        out.append(Hallazgo("error", h, f"Falta la hoja «{h}».",
                            f"El archivo tiene las hojas: {', '.join(existentes)}.\n  Indica la correcta en {LOCAL}:\n    hojas:\n      {clave}: <nombre de la hoja>"))
    xl = pd.ExcelFile(ruta if path else Path(cfg["ruta"]))
    fila = cfg["header_row"]
    plan = [("clientes", set(CLIENT_CRITICAL), set(CLIENT_REQUIRED) - set(CLIENT_CRITICAL)),
            ("posiciones", {"rut", "valor_clp"}, set(POSICION_REQUIRED) - {"rut", "valor_clp"})]
    for clave, criticas, requeridas in plan:
        if hojas[clave] in xl.sheet_names:
            out += _columnas(xl, clave, hojas[clave], fila, cfg[f"columnas_{clave}"], criticas, requeridas)
    if cfg.get("hoja_flujos") in xl.sheet_names:
        out += _columnas(xl, "flujos", cfg["hoja_flujos"], fila, cfg["columnas_flujos"], set(), set())
    out += _ruts(ds, hojas["posiciones"], cfg.get("hoja_flujos", "flujos"))
    out += _patrimonio(ds, hojas["clientes"])
    if hojas["clientes"] in xl.sheet_names:
        crudo = _alinear_encabezados(pd.read_excel(xl, sheet_name=hojas["clientes"], header=fila), list(cfg["columnas_clientes"]))
        col_rut = next((k for k, v in cfg["columnas_clientes"].items() if v == "rut" and k in crudo.columns), None)
        formatos = crudo[col_rut].dropna().map(_formato_rut).value_counts() if col_rut else []
        if len(formatos) > 1:
            out.append(Hallazgo("aviso", hojas["clientes"], "Los RUT vienen en formatos mezclados: " + ", ".join(f"{n} {f}" for f, n in formatos.items()) + ".",
                                "El portal los unifica solo; no hay que corregir nada."))
    propios = {"Falta la columna requerida", "Columna opcional ausente"}
    for i in validate(ds):
        if any(i.message.startswith(p) for p in propios):
            continue
        msg = f"{len(ds.duplicate_ruts)} RUT repetidos en la hoja de clientes (se usa la primera fila)." if i.message.startswith("RUT duplicados") else i.message
        out.append(Hallazgo({"error": "error", "warning": "aviso"}.get(i.level, "info"), i.sheet, msg))
    return sorted(out, key=lambda h: ORDEN[h.nivel])


def informe(hallazgos: list[Hallazgo]) -> str:
    e = sum(h.nivel == "error" for h in hallazgos)
    a = sum(h.nivel == "aviso" for h in hallazgos)
    i = sum(h.nivel == "info" for h in hallazgos)
    lineas = ["Verificación del Excel", "=" * 22,
              f"{e} errores · {a} avisos · {i} informaciones", "(Este informe no incluye RUT, nombres ni montos de clientes.)", ""]
    marca = {"error": "ERROR", "aviso": "AVISO", "info": "INFO "}
    for h in hallazgos:
        lineas.append(f"[{marca[h.nivel]}] {h.hoja}: {h.mensaje}")
        if h.ayuda:
            lineas += [f"        {x}" if n == 0 else f"      {x}" for n, x in enumerate(h.ayuda.splitlines())]
    if not e:
        lineas += ["", "Sin errores: ya puedes abrir el portal." if not a else "Sin errores: puedes abrir el portal; revisa los avisos."]
    else:
        lineas += ["", "Corrige los errores y vuelve a correr la verificación."]
    return "\n".join(lineas)
