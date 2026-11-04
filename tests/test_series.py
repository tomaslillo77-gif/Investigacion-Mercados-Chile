import pandas as pd

from wm.series import evaluate_series

CARTERAS = pd.DataFrame({
    "arquitectura": ["x", "y", "x", "y"],
    "perfil": ["p"] * 4,
    "diccionario": ["Fondo Z", "Fondo Z", "Fondo W", "Fondo W"],
    "isin": ["Z_WEALTH", "Z_C", "W_I", "W_I2"],
    "serie": ["Wealth", "C", "I", "A"],
    "comision": [0.008, 0.015, 0.010, 0.010],
})


def pos(*isins: str) -> pd.DataFrame:
    return pd.DataFrame({"isin": list(isins), "valor_clp": [100.0] * len(isins)})


def test_series_mala_when_commission_higher_than_model():
    (f,) = evaluate_series(pos("Z_C"), CARTERAS, "x")
    assert f.es_mala and "comisión" in f.motivo
    assert f.comision_actual == 0.015 and f.comision_modelo == 0.008


def test_series_mala_when_serie_differs_for_same_fund():
    (f,) = evaluate_series(pos("W_I2"), CARTERAS, "x")
    assert f.es_mala and f.serie_actual == "A" and f.serie_modelo == "I"


def test_position_already_in_model_series_is_not_mala():
    (f,) = evaluate_series(pos("Z_WEALTH"), CARTERAS, "x")
    assert not f.es_mala


def test_isin_not_in_catalog_yields_no_finding():
    assert evaluate_series(pos("DESCONOCIDO"), CARTERAS, "x") == []


def test_no_architecture_yields_no_findings():
    assert evaluate_series(pos("Z_C"), CARTERAS, None) == []


def test_zero_weight_series_row_is_catalog_not_model():
    """Una serie con peso_objetivo 0 es solo catálogo: si el cliente la tiene, es serie mala."""
    car = CARTERAS.assign(peso_objetivo=[0.5, 0.0, 0.3, 0.2])  # Z_C (retail, más cara) con peso 0
    car = car.assign(arquitectura="x")                          # misma arquitectura que el modelo
    (f,) = evaluate_series(pos("Z_C"), car, "x")
    assert f.es_mala and f.serie_modelo == "Wealth"
