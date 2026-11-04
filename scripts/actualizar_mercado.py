"""Actualiza los datos de mercado del módulo Estrategia.

  python scripts/actualizar_mercado.py                  # 4 Excel de la CMF (data/cmf/) -> foto en data/mercado/AAAA-MM-DD/
  python scripts/actualizar_mercado.py --fuente yahoo   # fondos internacionales del catálogo, por ISIN, desde Yahoo Finance
"""
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from datetime import date  # noqa: E402

from wm.config import load_config  # noqa: E402
from wm.mercado import equivalencias as eq  # noqa: E402
from wm.mercado import internacionales as intl  # noqa: E402
from wm.mercado.cmf import ArchivoCMFFaltante, FechasDesalineadas, leer_cmf  # noqa: E402
from wm.mercado.fuentes.base import FuenteNoDisponible  # noqa: E402
from wm.mercado.fuentes.yahoo import YahooFuente  # noqa: E402
from wm.mercado.snapshots import guardar_foto  # noqa: E402


def _cargar_catalogo(excel: str | None):
    from wm.loader import load_dataset
    return load_dataset(Path(excel) if excel else None).carteras


def _yahoo(cache_dir: Path) -> YahooFuente:
    return YahooFuente(cache_dir)


def _actualizar_yahoo(args) -> int:
    externos = Path(args.externos)
    equiv_path = Path(args.equivalencias)
    equiv = eq.cargar(equiv_path)
    tickers = {intl.isin_base(i): t for i, t in zip(equiv["isin"], equiv["ticker_yahoo"]) if intl.isin_base(i) and isinstance(t, str)}
    try:
        df = intl.construir(_cargar_catalogo(args.excel), _yahoo(externos / "yahoo_cache"), tickers)
    except FuenteNoDisponible as e:
        print(f"No se actualizó: {e}")
        return 1
    destino = intl.guardar_yahoo(df, externos / "yahoo", date.today())
    eq.guardar(intl.completar_tickers(equiv, df), equiv_path)
    ok = int((df["estado"] == "Yahoo").sum())
    print(f"Yahoo {date.today().isoformat()}: {ok} de {len(df)} fondos internacionales con datos "
          f"({int((df['estado'] == 'Sin ticker').sum())} sin ticker) -> {destino}")
    return 0


def main(argv=None) -> int:
    cfg = load_config("mercado")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fuente", default="cmf_excel", choices=["cmf_excel", "yahoo"])
    ap.add_argument("--excel", default=None, help="Excel del catálogo (solo --fuente yahoo); por defecto el de config/excel.yaml")
    ap.add_argument("--externos", default=str(RAIZ / cfg["externos_dir"]))
    ap.add_argument("--equivalencias", default=str(RAIZ / cfg["equivalencias"]))
    ap.add_argument("--cmf-dir", default=str(RAIZ / cfg["cmf_dir"]))
    ap.add_argument("--out", default=str(RAIZ / cfg["snapshots_dir"]))
    args = ap.parse_args(argv)
    if args.fuente == "yahoo":
        return _actualizar_yahoo(args)
    try:
        foto = leer_cmf(Path(args.cmf_dir))
    except (ArchivoCMFFaltante, FechasDesalineadas) as e:
        print(f"No se actualizó: {e}")
        return 1
    destino = guardar_foto(foto, Path(args.out))
    print(f"Foto {foto.fecha_corte.isoformat()}: {len(foto.series)} series, "
          f"{foto.series['fo_run'].nunique()} fondos, {foto.cartera['fo_run'].nunique()} con cartera -> {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
