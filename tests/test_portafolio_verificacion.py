from datetime import date

import pandas as pd
import pytest

from scripts.verificar_portafolios import main
from tests.test_catalogo import _cat, _fila
from wm.catalogo import Catalogo, desde_carteras
from wm.loader import load_dataset
from wm.portafolio_verificacion import a_markdown, analizar, curva_de_cobertura

RV = dict(clase="Renta variable", pct_renta_variable=1.0, pct_rf_local=0.0, pct_alternativos=0.0, pct_moneda_clp=1.0)


def test_curva_de_cobertura_cuenta_los_instrumentos_necesarios_por_nivel():
    v = pd.Series([50.0, 30.0, 10.0, 5.0, 3.0, 2.0])
    assert curva_de_cobertura(v) == {0.80: 2, 0.90: 3, 0.95: 4} and curva_de_cobertura(pd.Series([100.0])) == {0.80: 1, 0.90: 1, 0.95: 1} and curva_de_cobertura(pd.Series(dtype=float)) == {0.80: 0, 0.90: 0, 0.95: 0}


def test_analizar_mide_lo_reconocido_lo_que_falta_y_la_lista():
    cat = Catalogo(_cat(_fila(instrument_id="A", isin="CL0000000001", nemotecnico="NEMOA", **RV), _fila(instrument_id="B", nombre="B", isin="CL0000000002", comision=pd.NA, **RV)))
    pos = pd.DataFrame({"rut": ["R1", "R1", "R2", "R3"], "instrumento": ["a", "b", "x", "y"], "isin": ["CL0000000001", "NEMOA", "ZZ1", "ZZ2"], "valor_clp": [400.0, 300.0, 200.0, 100.0]})
    clientes = pd.DataFrame({"rut": ["R1", "R2", "R3", "R4"]})
    r = analizar(pos, clientes, cat, pd.DataFrame({"rut": ["R1"]}))
    assert r["clientes"] == 4 and r["clientes_con_posiciones"] == 3 and r["posiciones"] == 4 and r["pct_reconocido"] == pytest.approx(70.0)
    assert r["pct_por_via"] == {"isin": pytest.approx(40.0), "nemotecnico": pytest.approx(30.0)} and r["instrumentos_distintos"] == 3      # A (por ISIN y por nemotécnico es el mismo) y los dos sin reconocer
    assert r["instrumentos_sin_reconocer"] == 2 and r["clientes_con_algo_sin_reconocer"] == 2
    assert [x["instrumento"] for x in r["top_sin_reconocer"]] == ["x", "y"] and r["top_sin_reconocer"][0]["pct"] == pytest.approx(20.0)
    assert r["catalogo"]["instrumentos"] == 2 and r["catalogo"]["con_comision"] == 1 and r["portafolios"] == {"definidos": 1, "pct_clientes": 25.0}


def test_el_informe_no_trae_ruts_ni_nombres_de_clientes():
    ds = load_dataset()
    cat = Catalogo(desde_carteras(ds.carteras)[0])
    texto = a_markdown(analizar(ds.posiciones, ds.clientes, cat, pd.DataFrame({"rut": ds.clientes["rut"].head(5)})), date(2026, 10, 27), "el dummy")
    assert "Verificación de supuestos" in texto and "Patrimonio reconocido" in texto and "Portafolios definidos: 5" in texto
    assert not any(str(r) in texto for r in ds.clientes["rut"].head(50)) and "RUT_" not in texto


def test_el_script_escribe_el_informe_y_falla_sin_excel(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("WM_DSN", raising=False)
    assert main(["--out", str(tmp_path)], hoy=date(2026, 10, 27)) == 0
    t = (tmp_path / "verificacion_portafolios_2026-10-27.md").read_text(encoding="utf-8")
    assert "Patrimonio reconocido" in t and "Adopción" not in t and "RUT_" not in t
    assert main(["--excel", str(tmp_path / "no_existe.xlsx"), "--out", str(tmp_path / "x")]) == 1 and "No se generó el informe" in capsys.readouterr().out
