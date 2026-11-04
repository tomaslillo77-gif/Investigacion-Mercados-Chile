import csv
from datetime import date
from pathlib import Path

FEEDBACK_COLS = ["id", "advisor", "pagina", "categoria", "texto", "importancia", "creado_en"]
COMMENT_COLS = ["id", "rut", "advisor", "texto", "creado_en"]


def _safe(v):
    """Neutraliza inyección de fórmulas al abrir el CSV en Excel."""
    return "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


def _write(path: Path, cols: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows([{k: _safe(v) for k, v in r.items()} for r in rows])


def export_feedback(store, out_dir: Path, hoy: date) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fb = out_dir / f"feedback_{hoy.isoformat()}.csv"
    cm = out_dir / f"comentarios_{hoy.isoformat()}.csv"
    _write(fb, FEEDBACK_COLS, store.list_feedback())
    _write(cm, COMMENT_COLS, store.list_all_comments())
    return [fb, cm]
