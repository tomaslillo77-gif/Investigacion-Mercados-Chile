"""Versión del código que está corriendo: «commit · fecha».

El archivo VERSION guarda `$Format:%h %cs$`; `git archive` y el «Download ZIP» de GitHub lo reemplazan por el commit y su fecha
(ver .gitattributes). En un clon de Git, que conserva el texto sin reemplazar, se le pregunta a Git."""
import subprocess
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _desde_git() -> str | None:
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%h %cs"], cwd=ROOT, capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def texto_version(path: Path | None = None) -> str:
    path = path or ROOT / "VERSION"
    try:
        crudo = path.read_text(encoding="utf-8").strip()
    except OSError:
        crudo = ""
    if not crudo or crudo.startswith("$Format"):
        crudo = _desde_git() or ""
    return crudo.replace(" ", " · ", 1) if crudo else "desarrollo"


@lru_cache(maxsize=1)
def version_actual() -> str:
    return texto_version()
