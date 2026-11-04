import pandas as pd
import pytest

from tests.test_mercado_internacionales import CAT as CAT_INTL
from tests.test_mercado_internacionales import FakeYahoo, HOY
from wm.mercado import internacionales as it
from wm.mercado.cmf import leer_cmf
from wm.mercado.portafolios import ARQUITECTURAS, armar, exposiciones_cartera


def _fila(**kw):
    base = {"arquitectura": "abierta_pesos", "perfil": "Defensivo", "instrumento": "X", "serie": "A", "isin": "SIN_ISIN::x",
            "peso_objetivo": 0.0, "beneficio_tributario": "-", "moneda": "CLP", "pct_renta_variable": 0.0,
            "pct_alternativos": 0.0, "pct_rf_local": 0.0, "pct_rf_high_yield_internacional": 0.0,
            "pct_rf_investment_grade": 0.0, "pct_rv_usa": 0.0, "pct_rv_latam": 0.0, "pct_rv_chile": 0.0,
            "pct_rv_emergentes": 0.0, "pct_rv_japon": 0.0, "pct_rv_europa": 0.0, "pct_moneda_usd": 0.0,
            "pct_moneda_clp": 1.0, "pct_moneda_uf": 0.0, "pct_moneda_otras": 0.0}
    base.update(kw)
    return base


CARTERAS = pd.DataFrame([
    _fila(instrumento="Vision Money Market", serie="I2", isin="CL0000000001", peso_objetivo=0.4, pct_rf_local=1),
    _fila(instrumento="Core S&P 500 UCIT", serie="ETF", isin="IE00B5BMR087", peso_objetivo=0.3, pct_renta_variable=1,
          pct_rv_usa=1, beneficio_tributario="107", pct_moneda_usd=0.9, pct_moneda_clp=0.0, pct_moneda_otras=0.1, moneda="USD"),
    _fila(instrumento="Core S&P 500 UCIT", serie="A", isin="IE00B5BMR087_RET", peso_objetivo=0.0, pct_renta_variable=1,
          pct_rv_usa=1, beneficio_tributario="108", pct_moneda_usd=0.9, pct_moneda_clp=0.0, pct_moneda_otras=0.1, moneda="USD"),
    _fila(instrumento="Core S&P 500 UCIT", serie="B", isin="IE00B5BMR087_B", peso_objetivo=0.0, pct_renta_variable=1,
          pct_rv_usa=1, beneficio_tributario="108", pct_moneda_usd=0.9, pct_moneda_clp=0.0, pct_moneda_otras=0.1, moneda="USD"),
    _fila(instrumento="Fondo Raro", serie="A", peso_objetivo=0.3, pct_rf_local=1),
    _fila(arquitectura="abierta_local", instrumento="Otro", peso_objetivo=1.0, pct_rf_local=1),
])
EQUIV = pd.DataFrame([{"instrumento_catalogo": "Vision Money Market", "isin": "CL0000000001", "serie_catalogo": "I2",
                       "fo_run": 8011, "fm_serie": "I2", "ticker_yahoo": None, "ticker_bloomberg": None,
                       "id_riskamerica": None, "confianza": 1.0}])


@pytest.fixture
def yahoo():
    return it.construir(CAT_INTL, FakeYahoo(), hoy=HOY)


def test_las_cuatro_arquitecturas_en_orden():
    assert ARQUITECTURAS == ["cerrada_pesos", "abierta_dolares", "abierta_pesos", "abierta_local"]


def test_abierta_pesos_arma_el_modelo_del_catalogo_con_cmf_y_yahoo(cmf_dir, yahoo):
    c, fuente = armar("abierta_pesos", "DEFENSIVO", CARTERAS, EQUIV, leer_cmf(cmf_dir), yahoo)
    assert fuente == "Catálogo" and round(c["peso"].sum(), 6) == 1.0
    f = c.set_index("fondo")
    assert f.loc["Vision Money Market", "estado"] == "CMF" and f.loc["Vision Money Market", "tac"] == 0.72
    assert f.loc["Vision Money Market", "serie"] == "I2" and f.loc["Vision Money Market", "fo_run"] == 8011
    assert f.loc["Core S&P 500 UCIT", "estado"] == "Yahoo" and f.loc["Core S&P 500 UCIT", "rent_1a"] == 4.0
    assert f.loc["Core S&P 500 UCIT", "serie"] == "ETF"                # la serie del modelo, no el ticker
    assert f.loc["Fondo Raro", "estado"] == "Sin datos" and pd.isna(f.loc["Fondo Raro", "rent_1a"])
    assert list(c["clase"].drop_duplicates()) == ["Renta variable", "Renta fija"]


def test_las_series_sin_peso_del_catalogo_no_aparecen(cmf_dir, yahoo):
    c, _ = armar("abierta_pesos", "DEFENSIVO", CARTERAS, EQUIV, leer_cmf(cmf_dir), yahoo)
    assert len(c) == 3


def test_sin_cmf_ni_yahoo_todo_queda_sin_datos_pero_con_peso():
    c, _ = armar("abierta_pesos", "DEFENSIVO", CARTERAS, EQUIV, None, None)
    assert (c["estado"] == "Sin datos").all() and round(c["peso"].sum(), 6) == 1.0


def test_cartera_gestionada_usa_scotia_y_abierta_usd_usa_yahoo(cmf_dir, yahoo):
    c, fuente = armar("cerrada_pesos", "PRESERVACION", CARTERAS, EQUIV, leer_cmf(cmf_dir), yahoo)
    assert fuente == "CMF" and round(c["peso"].sum(), 6) == 1.0 and "ACCIONES USA" in set(c["fondo"])
    c, fuente = armar("abierta_dolares", "PRESERVACION", CARTERAS, EQUIV, leer_cmf(cmf_dir), yahoo)
    assert fuente == "Yahoo" and "Core S&P 500 UCIT" in set(c["fondo"]) and round(c["peso"].sum(), 6) == 1.0


def test_perfil_o_arquitectura_sin_filas_devuelve_tabla_vacia(cmf_dir):
    c, _ = armar("abierta_local", "CRECIMIENTO", CARTERAS, EQUIV, leer_cmf(cmf_dir), None)
    assert c.empty


def test_exposiciones_toman_los_atributos_del_catalogo(cmf_dir, yahoo):
    c, _ = armar("abierta_pesos", "DEFENSIVO", CARTERAS, EQUIV, leer_cmf(cmf_dir), yahoo)
    e = exposiciones_cartera(c, CARTERAS).set_index("fondo")
    assert e.loc["Core S&P 500 UCIT", "act_rv"] == 1 and e.loc["Core S&P 500 UCIT", "mon_usd"] == 0.9
    assert e.loc["Core S&P 500 UCIT", "beneficio"] == "107"                  # la serie del modelo, no la de otra serie
    assert e.loc["Vision Money Market", "act_rf"] == 1 and e.loc["Vision Money Market", "beneficio"] == "—"


def test_exposiciones_de_un_fondo_fuera_del_catalogo_son_a_nivel_de_valor_cuota():
    c = pd.DataFrame([
        {"clase": "Renta variable", "subactivo": "Estados Unidos", "fondo": "ACCIONES USA", "serie": "WEALTH", "fo_run": 8480,
         "peso": 0.5, "moneda": "CLP"},
        {"clase": "Renta fija", "subactivo": "Local", "fondo": "DEUDA M. PLAZO UF", "serie": "WEALTH", "fo_run": 8106,
         "peso": 0.3, "moneda": "USD"},
        {"clase": "Activos alternativos", "subactivo": "Real estate", "fondo": "REAL ESTATE", "serie": "WEALTH", "fo_run": 1,
         "peso": 0.2, "moneda": "Sin dato"}])
    e = exposiciones_cartera(c, CARTERAS).set_index("fondo")
    assert (e.loc["ACCIONES USA", ["act_rv", "mon_clp"]] == 1).all() and e.loc["ACCIONES USA", "beneficio"] == "—"
    assert e.loc["DEUDA M. PLAZO UF", "act_rf"] == 1 and e.loc["DEUDA M. PLAZO UF", "mon_usd"] == 1
    assert e.loc["REAL ESTATE", "act_alt"] == 1 and e.loc["REAL ESTATE", ["mon_usd", "mon_clp", "mon_uf", "mon_otras"]].sum() == 0


def test_beneficio_de_un_fondo_sin_serie_en_el_catalogo_es_el_mas_frecuente():
    c = pd.DataFrame([{"clase": "Renta variable", "subactivo": "Estados Unidos", "fondo": "Core S&P 500 UCIT", "serie": "CSPX.L",
                       "fo_run": None, "peso": 1.0, "moneda": "USD"}])
    assert exposiciones_cartera(c, CARTERAS).loc[0, "beneficio"] == "108"   # 108, 108 y 107 en las tres series
