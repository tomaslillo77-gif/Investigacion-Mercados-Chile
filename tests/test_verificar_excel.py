import importlib.util
from pathlib import Path

from wm.verificar_excel import informe, verificar

ROOT = Path(__file__).resolve().parent.parent


def _niveles(hallazgos, nivel):
    return [h for h in hallazgos if h.nivel == nivel]


def _textos(hallazgos, nivel=None):
    return " | ".join(f"{h.mensaje} {h.ayuda}" for h in hallazgos if nivel is None or h.nivel == nivel)


def test_excel_limpio_no_tiene_errores(mini_xlsx):
    assert _niveles(verificar(mini_xlsx), "error") == []


def test_archivo_que_no_existe_es_un_error(tmp_path):
    h = verificar(tmp_path / "no_existe.xlsx")
    assert [x.nivel for x in h] == ["error"]
    assert "no_existe.xlsx" in h[0].mensaje


def test_hoja_que_falta_es_error_y_lista_las_que_hay(mini_frames, write_xlsx):
    mini_frames.pop("Dummy Posiciones")
    h = verificar(write_xlsx(mini_frames))
    errores = _textos(h, "error")
    assert "Dummy Posiciones" in errores
    assert "Dummy Metricas" in errores          # la ayuda enumera las hojas que sí tiene el archivo
    assert "hojas" in errores                   # y dice dónde corregirlo


def test_columna_critica_renombrada_propone_la_parecida(mini_frames, write_xlsx):
    m = mini_frames["Dummy Metricas"]
    mini_frames["Dummy Metricas"] = m.rename(columns={"Valor de Mercado (CLP)": "Valor de mercado (CLP) total"})
    h = verificar(write_xlsx(mini_frames))
    errores = _textos(h, "error")
    assert "aum_clp" in errores
    assert "Valor de mercado (CLP) total" in errores   # la sugerencia
    assert "columnas_clientes" in errores


def test_rut_de_posiciones_que_no_estan_en_clientes_se_avisa_con_conteo_sin_mostrar_el_rut(mini_frames, write_xlsx):
    mini_frames["Dummy Posiciones"]["RUT Normalizado"] = ["RUT_1", "RUT_1", "RUT_999"]
    h = verificar(write_xlsx(mini_frames))
    texto = _textos(h, "aviso")
    assert "1 de 3" in texto
    assert "RUT_999" not in informe(h)


def test_encabezados_en_la_fila_equivocada_se_detectan(mini_frames, write_xlsx, tmp_path, monkeypatch):
    local = tmp_path / "local"
    local.mkdir()
    (local / "excel.yaml").write_text("header_row: 0\n", encoding="utf-8")
    monkeypatch.setenv("WM_CONFIG_DIR", str(local))
    h = verificar(write_xlsx(mini_frames))
    assert "header_row" in _textos(h)


def test_el_informe_resume_y_no_lleva_valores_de_clientes(mini_xlsx):
    texto = informe(verificar(mini_xlsx))
    assert "errores" in texto.lower()
    assert "RUT_1" not in texto and "Fondo A" not in texto


def test_el_script_devuelve_1_con_errores_y_0_sin_ellos(mini_xlsx, tmp_path, capsys):
    spec = importlib.util.spec_from_file_location("verificar_excel_script", ROOT / "scripts" / "verificar_excel.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main(["--excel", str(mini_xlsx)]) == 0
    assert mod.main(["--excel", str(tmp_path / "x.xlsx")]) == 1
    assert "Verificación del Excel" in capsys.readouterr().out
