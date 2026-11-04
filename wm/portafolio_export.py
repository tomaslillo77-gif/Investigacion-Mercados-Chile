"""Excel del portafolio objetivo para llevar a la reunión con el cliente: portafolio, exposición hoy contra objetivo, ajuste y datos de la versión."""
import io
from datetime import date

import pandas as pd

from wm.portafolio_cliente import Resumen

CLASES = [("Renta Variable", "Renta variable"), ("Renta Fija", "Renta fija"), ("Alternativos", "Alternativos")]


def excel_reunion(cliente: dict, items: pd.DataFrame, objetivo: Resumen, hoy: Resumen, plan: pd.DataFrame | None, estado: str, nota: str = "", fecha: date | None = None) -> bytes:
    """`cliente`: nombre, rut, perfil, advisor. `estado`: «Vigente v3» o «Borrador sin guardar». Los números van como números (no texto) para poder trabajarlos en Excel."""
    port = pd.DataFrame({"Instrumento": items["nombre"].values, "Serie": items["serie"].fillna("").values, "Peso %": pd.to_numeric(items["peso"]).values,
                         "Comisión %": (pd.to_numeric(items["comision"]) * 100).values})
    if len(port):
        total = pd.DataFrame([{"Instrumento": "Total", "Serie": "", "Peso %": port["Peso %"].sum(), "Comisión %": (objetivo.comision or 0) * 100 if objetivo.comision is not None else None}])
        port = pd.concat([port, total], ignore_index=True)
    expo = pd.DataFrame({"Clase": [n for _, n in CLASES], "Hoy %": [hoy.clase.get(k) for k, _ in CLASES], "Objetivo %": [objetivo.clase.get(k) for k, _ in CLASES]})
    detalle = pd.DataFrame({"Dato": ["Cliente", "RUT", "Perfil", "Advisor", "Estado", "Fecha", "Comisión ponderada %", "Renta variable + alternativos % (objetivo)", "Nota"],
                            "Valor": [cliente.get("nombre", ""), cliente.get("rut", ""), cliente.get("perfil", ""), cliente.get("advisor", ""), estado, (fecha or date.today()).isoformat(),
                                      None if objetivo.comision is None else round(objetivo.comision * 100, 3), None if objetivo.riesgo is None else round(objetivo.riesgo, 2), nota or ""]})
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        port.to_excel(w, sheet_name="Portafolio", index=False)
        expo.to_excel(w, sheet_name="Exposición", index=False)
        if plan is not None:
            plan.rename(columns={"fondo": "Fondo", "serie_actual": "Serie hoy", "serie_modelo": "Serie objetivo", "valor_actual": "Valor hoy (CLP)", "pct_actual": "% hoy",
                                 "pct_modelo": "% objetivo", "dif_pp": "Diferencia (pp)", "ajuste_clp": "Ajuste (CLP)", "accion": "Acción"}).to_excel(w, sheet_name="Ajuste", index=False)
        detalle.to_excel(w, sheet_name="Datos", index=False)
        for hoja, anchos in (("Portafolio", (44, 12, 10, 12)), ("Exposición", (18, 10, 12)), ("Datos", (40, 60)), ("Ajuste", (44, 12, 14, 16, 8, 10, 14, 14, 10))):
            if hoja in w.sheets:
                for col, ancho in zip("ABCDEFGHI", anchos):
                    w.sheets[hoja].column_dimensions[col].width = ancho
    return buf.getvalue()
