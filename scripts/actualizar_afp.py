"""Actualiza los datos del módulo AFP desde collabmarket/data_afp (valor cuota y patrimonio por AFP y fondo).

  python scripts/actualizar_afp.py                 # baja los CSV y guarda una foto en data/afp/AAAA-MM-DD/
  python scripts/actualizar_afp.py --out otra/carpeta --ventana-anios 5
"""
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from wm.afp.fuente import FuenteAfpNoDisponible, descargar  # noqa: E402
from wm.afp.snapshots import FechasDesalineadas, armar_foto, guardar_foto, listar_fotos  # noqa: E402
from wm.config import load_config  # noqa: E402


def _ultima(carpeta: Path) -> str:
    fotos = listar_fotos(carpeta)
    return f"La última foto disponible es la del {fotos[-1].isoformat()}." if fotos else "Todavía no hay fotos guardadas."


def main(argv: list[str] | None = None, leer=None) -> int:
    ap = argparse.ArgumentParser(description="Actualiza los datos de AFP (valor cuota y patrimonio).")
    ap.add_argument("--out", help="carpeta de fotos (por defecto, snapshots_dir de config/afp.yaml)")
    ap.add_argument("--ventana-anios", type=int, help="años de historia a guardar (por defecto, config/afp.yaml)")
    args = ap.parse_args(argv)

    cfg = load_config("afp")
    if args.ventana_anios:
        cfg["ventana_anios"] = args.ventana_anios
    carpeta = Path(args.out) if args.out else RAIZ / cfg["snapshots_dir"]
    try:
        vc, pat = descargar(cfg, leer=leer)
        foto = armar_foto(vc, pat)
    except (FuenteAfpNoDisponible, FechasDesalineadas) as e:
        print(f"No se actualizó: {e}\n{_ultima(carpeta)}")
        return 1
    destino = guardar_foto(foto, carpeta)
    print(f"Foto guardada en {destino} (datos al {foto.fecha_corte.isoformat()}, "
          f"{vc['afp'].nunique()} AFP, ventana de {cfg['ventana_anios']} años).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
