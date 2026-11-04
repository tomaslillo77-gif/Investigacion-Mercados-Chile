"""Revisa el Excel de datos antes de abrir el portal y dice qué corregir y dónde (se corre en el computador del trabajo).

  python scripts/verificar_excel.py                 # usa el Excel de config/excel.yaml (o WM_EXCEL)
  python scripts/verificar_excel.py --excel ruta.xlsx

Termina con código 1 si hay errores. El informe lleva solo nombres de hojas y columnas, conteos y porcentajes: nunca RUT, nombres ni montos."""
import argparse
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from wm.verificar_excel import informe, verificar  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verifica el Excel de datos contra lo que espera el portal.")
    ap.add_argument("--excel", help="Excel de datos (por defecto WM_EXCEL, o el de config/excel.yaml)")
    args = ap.parse_args(argv)
    destino = args.excel or os.environ.get("WM_EXCEL")
    hallazgos = verificar(destino)
    print(informe(hallazgos))
    return 1 if any(h.nivel == "error" for h in hallazgos) else 0


if __name__ == "__main__":
    sys.exit(main())
