import numpy as np
import pandas as pd
import pytest

from wm.exposure import (client_exposure, has_breakdown, model_exposure,
                         portfolio_exposure, uf_on_local_rf)


def funds(rows: dict[str, dict]) -> pd.DataFrame:
    base = dict(pct_rf_local=0.0, pct_rf_high_yield_internacional=0.0, pct_rf_investment_grade=0.0,
                pct_renta_variable=0.0, pct_rv_usa=0.0, pct_rv_latam=0.0, pct_rv_chile=0.0,
                pct_rv_emergentes=0.0, pct_rv_japon=0.0, pct_rv_europa=0.0, pct_alternativos=0.0,
                pct_moneda_usd=0.0, pct_moneda_clp=1.0, pct_moneda_uf=0.0, pct_moneda_otras=0.0)
    return pd.DataFrame({k: {**base, **v} for k, v in rows.items()}).T.rename_axis("isin")


def test_uf_on_local_rf_example():
    assert uf_on_local_rf(0.20, 0.25) == pytest.approx(0.80)


def test_uf_on_local_rf_zero_local_returns_none():
    assert uf_on_local_rf(0.0, 0.0) is None


def test_uf_on_local_rf_uf_exceeds_local_returns_none():
    assert uf_on_local_rf(0.30, 0.25) is None


def test_sumaproducto_two_funds():
    f = funds({"A": dict(pct_rf_local=1.0), "B": dict(pct_renta_variable=1.0, pct_rv_usa=1.0,
                                                      pct_moneda_clp=0.0, pct_moneda_usd=1.0)})
    e = portfolio_exposure(pd.Series({"A": 0.5, "B": 0.5}), f)
    assert e.clase == pytest.approx({"Renta Fija": 0.5, "Renta Variable": 0.5, "Alternativos": 0.0})
    assert e.rv_categorias["USA"] == pytest.approx(0.5)
    assert e.cobertura == pytest.approx(1.0)


def test_moneda_sums_to_one():
    f = funds({"A": dict(pct_moneda_usd=0.5, pct_moneda_clp=0.3, pct_moneda_otras=0.2),
               "B": dict(pct_moneda_clp=1.0)})
    e = portfolio_exposure(pd.Series({"A": 0.4, "B": 0.6}), f)
    assert sum(e.moneda.values()) == pytest.approx(1.0)


def test_uf_exposure_is_weighted_pct_uf():
    f = funds({"A": dict(pct_rf_local=0.25, pct_moneda_uf=0.20, pct_moneda_clp=0.80),
               "B": dict(pct_rf_local=0.10, pct_moneda_uf=0.0)})
    e = portfolio_exposure(pd.Series({"A": 0.6, "B": 0.4}), f)
    assert e.moneda["UF"] == pytest.approx(0.12)
    assert e.uf_sobre_rf_local == pytest.approx(0.12 / (0.6 * 0.25 + 0.4 * 0.10))


def test_fund_with_uf_above_rf_local_is_excluded_from_uf():
    f = funds({"A": dict(pct_rf_local=0.25, pct_moneda_uf=0.30, pct_moneda_clp=0.70)})
    e = portfolio_exposure(pd.Series({"A": 1.0}), f)
    assert e.uf_sobre_rf_local is None  # el fondo incoherente no entra al cálculo de UF sobre RF local


def test_cobertura_partial():
    f = funds({"A": dict(pct_rf_local=1.0), "B": {}})
    f.loc["B", "pct_renta_variable"] = np.nan
    e = portfolio_exposure(pd.Series({"A": 0.7, "B": 0.3}), f)
    assert e.cobertura == pytest.approx(0.7)


def test_no_breakdown_columns(mini_frames):
    carteras = mini_frames["Dummy Carteras"]
    assert has_breakdown(carteras) is False
    e = model_exposure(carteras, "abierta_pesos", "Equilibrado")
    assert e.cobertura == 0.0 and e.clase == {}


def test_client_exposure_maps_positions_by_isin():
    carteras = funds({"ISIN_A": dict(pct_rf_local=1.0), "ISIN_B": dict(pct_renta_variable=1.0)}).reset_index()
    carteras["arquitectura"] = "x"; carteras["perfil"] = "p"; carteras["peso_objetivo"] = 0.5
    pos = pd.DataFrame({"isin": ["ISIN_A", "ISIN_B", "SIN_CATALOGO"], "valor_clp": [600.0, 200.0, 200.0]})
    e = client_exposure(pos, carteras)
    assert e.clase["Renta Fija"] == pytest.approx(0.6)
    assert e.cobertura == pytest.approx(0.8)


def test_model_exposure_normalizes_weights():
    carteras = funds({"A": dict(pct_rf_local=1.0), "B": dict(pct_renta_variable=1.0)}).reset_index()
    carteras["arquitectura"] = "x"; carteras["perfil"] = "p"; carteras["peso_objetivo"] = [0.2, 0.2]
    e = model_exposure(carteras, "x", "p")
    assert e.clase["Renta Fija"] == pytest.approx(0.5)


def test_perfil_of_maps_normalized_profile_to_model_name():
    from wm.exposure import perfil_of
    k = pd.DataFrame({"perfil": ["Equilibrado", "Clasico_60_40"], "perfil_norm": ["EQUILIBRADO", "CLASICO_60_40"]})
    assert perfil_of(k, "EQUILIBRADO") == "Equilibrado"
    assert perfil_of(k, "OTRO") is None


def test_fund_with_bad_uf_keeps_currency_sum_but_skips_uf_ratio():
    f = funds({"A": dict(pct_rf_local=0.0, pct_moneda_uf=0.1, pct_moneda_usd=0.9, pct_moneda_clp=0.0),
               "B": dict(pct_rf_local=0.5, pct_moneda_clp=1.0)})
    e = portfolio_exposure(pd.Series({"A": 0.5, "B": 0.5}), f)
    assert sum(e.moneda.values()) == pytest.approx(1.0)
    assert e.uf_sobre_rf_local is None or e.uf_sobre_rf_local == pytest.approx(0.0)
