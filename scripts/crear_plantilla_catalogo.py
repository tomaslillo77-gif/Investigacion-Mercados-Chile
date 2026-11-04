"""Escribe la plantilla Excel del catálogo de instrumentos (datos ficticios) para llenarla con los reales.

  python scripts/crear_plantilla_catalogo.py                       # exports/Plantilla catalogo.xlsx
  python scripts/crear_plantilla_catalogo.py ruta/archivo.xlsx
  python scripts/crear_plantilla_catalogo.py --desde-excel         # catálogo derivado de la hoja de carteras del Excel actual
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import pandas as pd  # noqa: E402

from wm.catalogo import columnas, desde_carteras, plantilla  # noqa: E402
from wm.loader import load_dataset  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    derivar = "--desde-excel" in argv
    resto = [a for a in argv if a != "--desde-excel"]
    destino = Path(resto[0]) if resto else RAIZ / "exports" / ("Catalogo derivado.xlsx" if derivar else "Plantilla catalogo.xlsx")
    destino.parent.mkdir(parents=True, exist_ok=True)
    if derivar:
        cat, conflictos = desde_carteras(load_dataset().carteras)
        with pd.ExcelWriter(destino, engine="openpyxl") as w:
            cat[columnas()].to_excel(w, sheet_name="Instrumentos", index=False)
            pd.DataFrame(columns=["tipo_id", "valor", "instrument_id"]).to_excel(w, sheet_name="Alias", index=False)
            conflictos.to_excel(w, sheet_name="Conflictos", index=False)
        print(f"Catálogo derivado guardado en {destino} ({len(cat)} instrumentos; {conflictos['instrument_id'].nunique()} con datos distintos entre filas, ver la hoja Conflictos).")
        return 0
    destino.write_bytes(plantilla())
    print(f"Plantilla guardada en {destino}. Los datos son ficticios: reemplázalos y guarda el archivo como data/catalogo_instrumentos.xlsx.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
