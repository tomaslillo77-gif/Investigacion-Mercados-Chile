import os
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _leer(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _mezclar(base: dict, local: dict) -> dict:
    """Los diccionarios se mezclan clave por clave; cualquier otro valor (texto, número, lista) lo reemplaza el local."""
    out = dict(base)
    for k, v in local.items():
        out[k] = _mezclar(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def local_dir() -> Path:
    """Carpeta con los ajustes de este computador (WM_CONFIG_DIR, o config/local). Git no la versiona."""
    env = os.environ.get("WM_CONFIG_DIR")
    return Path(env) if env else CONFIG_DIR / "local"


def load_config(name: str, base: Path | None = None) -> dict:
    """Lee config/<name>.yaml; si existe <carpeta local>/<name>.yaml, se mezcla encima. Con `base` explícita no hay carpeta local."""
    path = (base or CONFIG_DIR) / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Config '{name}' no encontrada en {path}")
    cfg = _leer(path)
    if base is None:
        extra = local_dir() / f"{name}.yaml"
        if extra.exists():
            cfg = _mezclar(cfg, _leer(extra))
    return cfg
