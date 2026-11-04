from pathlib import Path

import pytest

from wm.config import load_config


def test_load_config_returns_dict():
    cfg = load_config("servicios")
    assert isinstance(cfg, dict)
    assert "equivalencias" in cfg


def test_load_config_missing_raises_filenotfound_with_name(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="no_existe"):
        load_config("no_existe", base=tmp_path)


def _yaml(path: Path, texto: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(texto, encoding="utf-8")
    return path


def test_config_local_se_mezcla_sobre_la_base(tmp_path: Path, monkeypatch):
    base = tmp_path / "config"
    _yaml(base / "excel.yaml", "ruta: data/dummy.xlsx\nhojas:\n  clientes: Dummy\n  posiciones: Pos\n")
    _yaml(tmp_path / "local" / "excel.yaml", "ruta: C:/datos/real.xlsx\nhojas:\n  clientes: Clientes\n")
    monkeypatch.setattr("wm.config.CONFIG_DIR", base)
    monkeypatch.setenv("WM_CONFIG_DIR", str(tmp_path / "local"))
    cfg = load_config("excel")
    assert cfg["ruta"] == "C:/datos/real.xlsx"                      # el valor local manda
    assert cfg["hojas"] == {"clientes": "Clientes", "posiciones": "Pos"}   # lo que el local no toca, queda


def test_config_local_por_defecto_es_config_local(tmp_path: Path, monkeypatch):
    base = tmp_path / "config"
    _yaml(base / "x.yaml", "a: 1\nb: 2\n")
    _yaml(base / "local" / "x.yaml", "b: 3\n")
    monkeypatch.setattr("wm.config.CONFIG_DIR", base)
    monkeypatch.delenv("WM_CONFIG_DIR", raising=False)
    assert load_config("x") == {"a": 1, "b": 3}


def test_sin_config_local_se_usa_la_base(tmp_path: Path, monkeypatch):
    base = tmp_path / "config"
    _yaml(base / "x.yaml", "a: 1\n")
    monkeypatch.setattr("wm.config.CONFIG_DIR", base)
    monkeypatch.delenv("WM_CONFIG_DIR", raising=False)
    assert load_config("x") == {"a": 1}


def test_base_explicita_ignora_la_config_local(tmp_path: Path, monkeypatch):
    _yaml(tmp_path / "x.yaml", "a: 1\n")
    _yaml(tmp_path / "local" / "x.yaml", "a: 9\n")
    monkeypatch.setenv("WM_CONFIG_DIR", str(tmp_path / "local"))
    assert load_config("x", base=tmp_path) == {"a": 1}


def test_las_listas_locales_reemplazan_a_las_de_la_base(tmp_path: Path, monkeypatch):
    base = tmp_path / "config"
    _yaml(base / "x.yaml", "cats: [a, b, c]\n")
    _yaml(base / "local" / "x.yaml", "cats: [z]\n")
    monkeypatch.setattr("wm.config.CONFIG_DIR", base)
    monkeypatch.delenv("WM_CONFIG_DIR", raising=False)
    assert load_config("x") == {"cats": ["z"]}
