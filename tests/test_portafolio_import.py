import io

import pandas as pd
import pytest

from tests.test_catalogo import _cat, _fila
from wm.portafolio_import import leer_portafolios, plantilla_portafolios

RV = dict(clase="Renta variable", pct_renta_variable=1.0, pct_rf_local=0.0, pct_alternativos=0.0, pct_moneda_clp=1.0)


@pytest.fixture
def cat():
    return _cat(_fila(instrument_id="A", nombre="Fondo A", isin="CL0000000001", nemotecnico="NEMOA", serie="B", comision=0.01, **RV),
                _fila(instrument_id="B", nombre="Fondo B", isin="CL0000000002", serie="A", comision=0.02, **RV))


def _excel(filas, cols=("rut", "instrumento", "peso")):
    buf = io.BytesIO()
    pd.DataFrame(filas, columns=list(cols)).to_excel(buf, index=False)
    buf.seek(0)
    return buf


def test_acepta_a_cada_cliente_completo_con_instrumentos_reconocidos_por_isin_o_nemo(cat):
    r = leer_portafolios(_excel([("RUT_1", "cl0000000001", 60), ("RUT_1", "CL0000000002", "40"), ("RUT_2", "NEMOA", 100)]), cat, None, {"RUT_1", "RUT_2"})
    assert r.ok and set(r.portafolios) == {"RUT_1", "RUT_2"}
    p = r.portafolios["RUT_1"].set_index("instrument_id")
    assert p.loc["A", "peso"] == 60 and p.loc["B", "peso"] == 40 and p.loc["A", "nombre"] == "Fondo A" and p.loc["B", "comision"] == 0.02
    assert list(r.portafolios["RUT_2"]["instrument_id"]) == ["A"]


def test_un_cliente_con_error_se_rechaza_completo_y_no_frena_a_los_demas(cat):
    r = leer_portafolios(_excel([("RUT_1", "CL0000000001", 60), ("RUT_1", "CL0000000002", 30), ("RUT_2", "CL0000000001", 100), ("RUT_3", "NOEXISTE", 100),
                                 ("RUT_9", "CL0000000001", 100), (None, "CL0000000001", 100), ("RUT_4", "CL0000000001", None)]), cat, None, {"RUT_1", "RUT_2", "RUT_3", "RUT_4"})
    assert set(r.portafolios) == {"RUT_2"}
    msgs = {(e["rut"], e["fila"]): e["mensaje"] for e in r.errores}
    assert any("suman 90.00%" in m for (rut, _), m in msgs.items() if rut == "RUT_1")
    assert "«NOEXISTE» no se reconoce" in msgs[("RUT_3", 5)] and "no existe o no es tuyo" in msgs[("RUT_9", 6)] and msgs[(None, 7)] == "La fila no tiene RUT." and "peso falta" in msgs[("RUT_4", 8)]


def test_los_repetidos_y_las_columnas_faltantes_se_informan(cat):
    r = leer_portafolios(_excel([("RUT_1", "CL0000000001", 50), ("RUT_1", "NEMOA", 50)]), cat, None, {"RUT_1"})
    assert not r.portafolios and any("aparece más de una vez" in e["mensaje"] for e in r.errores)
    r = leer_portafolios(_excel([("RUT_1", 100)], cols=("rut", "peso")), cat, None, {"RUT_1"})
    assert r.errores[0]["mensaje"].startswith("Faltan las columnas instrumento") and not r.ok
    assert "No se pudo leer el Excel" in leer_portafolios(io.BytesIO(b"no soy un excel"), cat, None, set()).errores[0]["mensaje"]


def test_acepta_encabezados_alternativos_y_pesos_con_coma(cat):
    r = leer_portafolios(_excel([("RUT_1", "CL0000000001", "33,5"), ("RUT_1", "CL0000000002", "66,5")], cols=("Cliente", "ISIN", "Peso")), cat, None, {"RUT_1"})
    assert r.ok and list(r.portafolios["RUT_1"]["peso"]) == [33.5, 66.5]


def test_la_plantilla_se_lee_con_los_ejemplos_ficticios_como_errores_de_cliente_desconocido(cat):
    r = leer_portafolios(io.BytesIO(plantilla_portafolios()), cat, None, {"RUT_X"})
    assert not r.portafolios and all("no existe o no es tuyo" in e["mensaje"] for e in r.errores)
    ok = leer_portafolios(io.BytesIO(plantilla_portafolios([("RUT_X", "CL0000000001", 100)])), cat, None, {"RUT_X"})
    assert ok.ok and list(ok.portafolios) == ["RUT_X"]


def test_guardar_masivo_crea_una_version_por_cliente_y_un_fallo_no_detiene_a_los_demas(cat, test_dsn):
    import psycopg
    from wm.portafolio_import import Resultado, guardar_masivo
    from wm.store import Store
    s = Store(test_dsn)
    s.migrate()
    with psycopg.connect(test_dsn) as c:
        c.execute("TRUNCATE portafolio_cliente, portafolio_cliente_item RESTART IDENTITY CASCADE")
    r = leer_portafolios(_excel([("RUT_1", "CL0000000001", 100), ("RUT_2", "CL0000000002", 100)]), cat, None, {"RUT_1", "RUT_2"})
    s.guardar_portafolio("RUT_1", r.portafolios["RUT_1"], "IA_0", version_base=0)             # ya tiene la versión 1
    guardados, fallidos = guardar_masivo(s, r, "IA_1", {"RUT_1": "EQUILIBRADO", "RUT_2": None})
    assert guardados == ["RUT_1", "RUT_2"] and fallidos == []
    p = s.portafolio_vigente("RUT_1")
    assert p["version"] == 2 and p["origen"] == "excel" and p["advisor"] == "IA_1" and p["perfil_al_guardar"] == "EQUILIBRADO" and s.portafolio_vigente("RUT_2")["version"] == 1
    malo = Resultado(portafolios={"RUT_3": r.portafolios["RUT_2"].assign(peso=150.0), "RUT_4": r.portafolios["RUT_2"]})   # el primero viola el CHECK de la base
    g, f = guardar_masivo(s, malo, "IA_1", {})
    assert f == ["RUT_3"] and g == ["RUT_4"] and s.portafolio_vigente("RUT_3") is None
