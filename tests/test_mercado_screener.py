import pandas as pd
import pytest

from wm.mercado import screener as sc
from wm.mercado.cmf import leer_cmf


@pytest.fixture
def foto(cmf_dir):
    return leer_cmf(cmf_dir)


@pytest.fixture
def carteras():
    return pd.DataFrame({
        "arquitectura": ["abierta_pesos"] * 4, "perfil": ["Defensivo"] * 4,
        "instrumento": ["Vision Money Market", "Acciones Global", "JP Morgan US", "Fondo Chileno Raro"],
        "serie": ["I2", "I", "C", "A"], "isin": ["CL1", "CL2", "LU0087133087", "CL9"],
        "peso_objetivo": [0.4, 0.3, 0.2, 0.1]})


@pytest.fixture
def equiv():
    return pd.DataFrame({
        "instrumento_catalogo": ["Vision Money Market", "Acciones Global"], "isin": ["CL1", "CL2"],
        "serie_catalogo": ["I2", "I"], "fo_run": [8011, 8915], "fm_serie": ["I2", "I"],
        "ticker_yahoo": [None, None], "ticker_bloomberg": [None, None], "id_riskamerica": [None, None],
        "confianza": [1.0, 1.0]})


def test_modelo_fondos_cruzado_trae_datos(carteras, equiv, foto):
    m = sc.modelo_fondos(carteras, equiv, foto).set_index("instrumento")
    assert m.loc["Vision Money Market", "tac"] == 0.72
    assert m.loc["Vision Money Market", "estado"] == "CMF"
    assert m.loc["Acciones Global", "rent_1a"] == 17.4856


def test_serie_sin_rentabilidad_muestra_nan_no_falla(carteras, equiv, foto):
    m = sc.modelo_fondos(carteras, equiv, foto).set_index("instrumento")
    assert pd.isna(m.loc["Vision Money Market", "rent_1a"])
    assert sc.fmt_pct(m.loc["Vision Money Market", "rent_1a"]) == "—"
    assert sc.fmt_pct(12.3456) == "12.35%" and sc.fmt_pct(None) == "—"


def test_sin_cruce_no_rompe_y_clasifica(carteras, equiv, foto):
    m = sc.modelo_fondos(carteras, equiv, foto).set_index("instrumento")
    assert m.loc["JP Morgan US", "estado"] == "Pendiente Yahoo/Bloomberg"
    assert m.loc["Fondo Chileno Raro", "estado"] == "Sin cruce"


def test_cruce_sin_datos(carteras, equiv, foto):
    equiv.loc[0, "fm_serie"] = "ZZ"
    m = sc.modelo_fondos(carteras, equiv, foto).set_index("instrumento")
    assert m.loc["Vision Money Market", "estado"] == "Cruce sin datos"


def test_foto_none_devuelve_filas_sin_datos(carteras, equiv):
    m = sc.modelo_fondos(carteras, equiv, None)
    assert len(m) == 4 and m["tac"].isna().all()
    assert set(m["estado"]) <= {"Cruce sin datos", "Pendiente Yahoo/Bloomberg", "Sin cruce"}


def test_equivalencias_vacias(carteras, foto):
    m = sc.modelo_fondos(carteras, pd.DataFrame(columns=["instrumento_catalogo", "serie_catalogo"]), foto)
    assert len(m) == 4 and (m["estado"] != "CMF").all()


def test_composicion_suma_uno_y_agrupa(foto):
    c = sc.composicion_fondo(foto, 8011)
    assert round(c["peso"].sum(), 6) == 1.0 and list(c.columns) == ["grupo", "peso"]
    assert len(sc.composicion_fondo(foto, 8011, por="emisor")) == 2


def test_composicion_fondo_inexistente_vacia(foto):
    c = sc.composicion_fondo(foto, 123456)
    assert c.empty and list(c.columns) == ["grupo", "peso"]


def test_comparar_respeta_orden(foto):
    u = sc.universo_cmf(foto)
    c = sc.comparar(u, [(8915, "I"), (8011, "H")])
    assert list(zip(c.fo_run, c.fm_serie)) == [(8915, "I"), (8011, "H")]


def test_universo_ordenado_por_patrimonio(foto):
    u = sc.universo_cmf(foto)
    assert u["patrimonio"].dropna().is_monotonic_decreasing


def test_equivalencia_repetida_no_duplica_filas(carteras, equiv, foto):
    m = sc.modelo_fondos(carteras, pd.concat([equiv, equiv.iloc[[0]]], ignore_index=True), foto)
    assert len(m) == len(carteras)


def test_fondo_sin_isin_es_local_no_pendiente_de_yahoo(equiv, foto):
    cat = pd.DataFrame({"arquitectura": ["a"], "perfil": ["Defensivo"], "instrumento": ["Moneda Deuda Chile"],
                        "serie": ["I"], "isin": ["SIN_ISIN::Moneda deuda Chile"], "peso_objetivo": [1.0]})
    assert sc.modelo_fondos(cat, equiv, foto).loc[0, "estado"] == "Sin cruce"
