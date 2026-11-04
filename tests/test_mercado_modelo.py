import pandas as pd
import pytest

from wm.mercado.carteras import ponderado
from wm.mercado.modelo import agrupar_modelo, clasificar


def _cat(**kw):
    base = {"arquitectura": "abierta_pesos", "perfil": "Defensivo", "instrumento": "X", "serie": "A", "peso_objetivo": 0.0,
            "beneficio_tributario": "-", "pct_renta_variable": 0.0, "pct_alternativos": 0.0, "pct_rf_local": 0.0,
            "pct_rf_high_yield_internacional": 0.0, "pct_rf_investment_grade": 0.0, "pct_rv_usa": 0.0, "pct_rv_latam": 0.0,
            "pct_rv_chile": 0.0, "pct_rv_emergentes": 0.0, "pct_rv_japon": 0.0, "pct_rv_europa": 0.0,
            "pct_moneda_usd": 0.0, "pct_moneda_clp": 1.0, "pct_moneda_uf": 0.0, "pct_moneda_otras": 0.0}
    base.update(kw)
    return base


CAT = pd.DataFrame([
    _cat(instrumento="Core S&P 500", serie="ETF", peso_objetivo=0.3, beneficio_tributario="107", pct_renta_variable=1,
         pct_rv_usa=1, pct_moneda_usd=0.9, pct_moneda_clp=0.0, pct_moneda_otras=0.1),
    _cat(instrumento="Latam UCITS", peso_objetivo=0.1, pct_renta_variable=1, pct_rv_latam=1, beneficio_tributario="108"),
    _cat(instrumento="Deuda Local", peso_objetivo=0.4, pct_rf_local=1, pct_moneda_uf=1.0, pct_moneda_clp=0.0),
    _cat(instrumento="US High Yield", peso_objetivo=0.1, pct_rf_high_yield_internacional=1, pct_moneda_usd=1.0,
         pct_moneda_clp=0.0),
    _cat(instrumento="Private Assets", peso_objetivo=0.1, pct_alternativos=1, pct_moneda_usd=1.0, pct_moneda_clp=0.0),
    _cat(instrumento="Otro perfil", perfil="Crecimiento", peso_objetivo=1.0, pct_renta_variable=1, pct_rv_chile=1),
])


@pytest.mark.parametrize("instrumento,esperado", [
    ("Core S&P 500", ("Renta variable", "Estados Unidos")), ("Latam UCITS", ("Renta variable", "Latinoamérica")),
    ("Deuda Local", ("Renta fija", "Local")), ("US High Yield", ("Renta fija", "Internacional")),
    ("Private Assets", ("Activos alternativos", "Alternativos"))])
def test_clasificar_asigna_una_categoria_por_fondo(instrumento, esperado):
    assert clasificar(CAT[CAT["instrumento"] == instrumento].iloc[0]) == esperado


def test_fondo_mixto_va_a_su_clase_dominante():
    r = pd.Series(_cat(pct_renta_variable=0.6, pct_rv_usa=0.6, pct_rf_local=0.4))
    assert clasificar(r) == ("Renta variable", "Estados Unidos")


def test_agrupar_modelo_filtra_ordena_y_trae_exposiciones():
    m = agrupar_modelo(CAT, "abierta_pesos", "Defensivo")
    assert list(m["clase"].drop_duplicates()) == ["Renta variable", "Renta fija", "Activos alternativos"]
    assert list(m["subactivo"].drop_duplicates()) == ["Estados Unidos", "Latinoamérica", "Local", "Internacional", "Alternativos"]
    assert "Otro perfil" not in set(m["instrumento"])
    sp = m[m["instrumento"] == "Core S&P 500"].iloc[0]
    assert sp["beneficio"] == "107" and sp["act_rv"] == 1 and sp["mon_usd"] == 0.9
    assert m[m["instrumento"] == "Deuda Local"].iloc[0]["act_rf"] == 1


def test_exposicion_de_clase_se_pondera_por_el_peso_del_modelo():
    m = agrupar_modelo(CAT, "abierta_pesos", "Defensivo")
    rf = m[m["clase"] == "Renta fija"]
    assert round(ponderado(rf, "mon_uf"), 6) == round(0.4 / 0.5, 6)       # Deuda Local pesa 0.4 de 0.5
    assert round(ponderado(rf, "mon_usd"), 6) == round(0.1 / 0.5, 6)


def test_perfil_sin_filas_devuelve_vacio_con_columnas():
    m = agrupar_modelo(CAT, "abierta_pesos", "Inexistente")
    assert m.empty and "clase" in m.columns


def test_series_sin_peso_en_el_modelo_no_se_muestran():
    cat = pd.concat([CAT, pd.DataFrame([_cat(instrumento="Core S&P 500", serie="B", peso_objetivo=0.0, pct_renta_variable=1,
                                             pct_rv_usa=1)])], ignore_index=True)
    m = agrupar_modelo(cat, "abierta_pesos", "Defensivo")
    assert ("Core S&P 500", "B") not in set(zip(m["instrumento"], m["serie"])) and len(m) == 5
