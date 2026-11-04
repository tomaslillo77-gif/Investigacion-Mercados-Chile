"""Informe anónimo para confirmar o descartar los supuestos del constructor de portafolios con los datos reales (se corre en el computador del trabajo).

  python scripts/verificar_portafolios.py                  # usa el Excel de config/excel.yaml y escribe exports/verificacion_portafolios_AAAA-MM-DD.md
  python scripts/verificar_portafolios.py --excel ruta.xlsx --out carpeta

El informe lleva solo conteos y porcentajes (nunca RUT ni nombres de clientes). Se lee en el mismo computador; no hace falta sacarlo del banco."""
import argparse
import os
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from wm.catalogo import cargar_catalogo  # noqa: E402
from wm.loader import DatasetCorrupt, DatasetNotFound, load_dataset  # noqa: E402
from wm.portafolio_verificacion import a_markdown, analizar  # noqa: E402
from wm.store import Store, StoreUnavailable  # noqa: E402


def main(argv: list[str] | None = None, hoy: date | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verifica los supuestos del constructor de portafolios con los datos cargados.")
    ap.add_argument("--excel", help="Excel de datos (por defecto, el de config/excel.yaml)")
    ap.add_argument("--out", help="carpeta de salida (por defecto, exports/)")
    args = ap.parse_args(argv)
    hoy = hoy or date.today()
    try:
        ds = load_dataset(Path(args.excel) if args.excel else None)
    except (DatasetNotFound, DatasetCorrupt) as e:
        print(f"No se generó el informe: {e}")
        return 1
    catalogo, fuente = cargar_catalogo(ds.casa())
    resumen = None
    dsn = os.environ.get("WM_DSN")
    if dsn:
        try:
            resumen = Store(dsn).resumen_portafolios_vigentes()
        except StoreUnavailable:
            resumen = None
    texto = a_markdown(analizar(ds.posiciones, ds.clientes, catalogo, resumen), hoy, f"el Excel de datos y la lista de instrumentos ({fuente})")
    carpeta = Path(args.out) if args.out else RAIZ / "exports"
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"verificacion_portafolios_{hoy.isoformat()}.md"
    destino.write_text(texto, encoding="utf-8")
    print(f"Informe guardado en {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
