import re
from pathlib import Path

from wm import version


def _archivo(tmp_path: Path, texto: str) -> Path:
    p = tmp_path / "VERSION"
    p.write_text(texto, encoding="utf-8")
    return p


def test_version_de_un_zip_viene_del_archivo(tmp_path):
    # `git archive` y «Download ZIP» reemplazan $Format:...$ por el commit y su fecha
    assert version.texto_version(_archivo(tmp_path, "4ca23c2 2026-11-03\n")) == "4ca23c2 · 2026-11-03"


def test_sin_sustituir_se_pregunta_a_git(tmp_path, monkeypatch):
    monkeypatch.setattr(version, "_desde_git", lambda: "abc1234 2026-11-04")
    assert version.texto_version(_archivo(tmp_path, "$Format:%h %cs$\n")) == "abc1234 · 2026-11-04"


def test_sin_archivo_ni_git_dice_desarrollo(tmp_path, monkeypatch):
    monkeypatch.setattr(version, "_desde_git", lambda: None)
    assert version.texto_version(tmp_path / "no_existe") == "desarrollo"
    assert version.texto_version(_archivo(tmp_path, "$Format:%h %cs$")) == "desarrollo"


def test_el_archivo_version_es_el_texto_a_sustituir_o_ya_trae_el_commit():
    # en el repositorio de desarrollo guarda el texto que Git sustituye al exportar; en un ZIP ya trae «commit fecha»
    raiz = Path(__file__).resolve().parent.parent
    contenido = (raiz / "VERSION").read_text(encoding="utf-8").strip()
    assert contenido == "$Format:%h %cs$" or re.fullmatch(r"[0-9a-f]{7,} \d{4}-\d{2}-\d{2}", contenido)
    assert "VERSION export-subst" in (raiz / ".gitattributes").read_text(encoding="utf-8")


def test_la_barra_lateral_muestra_la_version():
    from streamlit.testing.v1 import AppTest
    app = Path(__file__).resolve().parent.parent / "app_v4_final.py"
    at = AppTest.from_file(str(app), default_timeout=90).run()
    assert not at.exception
    assert any(str(c.value).startswith("Versión ") for c in at.sidebar.caption)
