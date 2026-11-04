"""Genera la plantilla vacía del Excel con todas las hojas y columnas del contrato de datos."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wm.columns import OPTIONAL_CLIENT, breakdown_columns  # noqa: E402
from wm.config import load_config  # noqa: E402

CLIENTES = ["RUT", "Entidad", "Household", "Servicio", "WM", "IA", "Perfil de Riesgo", "Última Reunión",
            "Valor de Mercado (CLP)", "CAD (USD MM)", "RUT Normalizado", "Perfil Normalizado",
            *OPTIONAL_CLIENT, "fecha_wealth_plan", "periodo",
            "nombre_cliente", "tipo_persona", "nombre_advisor"]  # OPTIONAL_CLIENT ya incluye las métricas de negocio
POSICIONES = ["Cliente (ID)", "Instrumento", "Tipo", "Isin", "VM Numérico", "G/P no Realizada",
              "Rent. no Realizada", "RUT Normalizado"]
CARTERAS = ["arquitectura", "perfil", "instrumento", "diccionario", "isin", "bloomberg", "nemotecnico", "serie",
            "peso_objetivo", "comision", "yield", "duracion", "liquidez", "pct_uf", "moneda",
            "Perfil Normalizado", *breakdown_columns()]


def build_template(out: Path) -> Path:
    hojas = load_config("excel")["hojas"]
    cols = {hojas["clientes"]: CLIENTES, hojas["posiciones"]: POSICIONES, hojas["carteras"]: CARTERAS}
    with pd.ExcelWriter(out) as xw:
        for sheet, columns in cols.items():
            pd.DataFrame([[f"PLANTILLA — {sheet}"]]).to_excel(xw, sheet_name=sheet, index=False, header=False)
            pd.DataFrame(columns=columns).to_excel(xw, sheet_name=sheet, index=False, startrow=2)
    return out


if __name__ == "__main__":
    print(build_template(ROOT / "data" / "Plantilla Engine WM.xlsx"))
