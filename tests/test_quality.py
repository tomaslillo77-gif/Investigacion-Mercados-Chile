from datetime import datetime

import pandas as pd

from wm.loader import Dataset
from wm.quality import Issue, validate


def make_ds(clientes=None, carteras=None, **kw) -> Dataset:
    c = clientes if clientes is not None else pd.DataFrame({
        "rut": ["R1"], "servicio": ["ADC"], "perfil_norm": ["EQUILIBRADO"], "advisor": ["IA_1"]})
    k = carteras if carteras is not None else pd.DataFrame({
        "arquitectura": ["a", "a"], "perfil": ["Equilibrado"] * 2, "peso_objetivo": [0.5, 0.5]})
    return Dataset(c, pd.DataFrame(), k, datetime(2026, 1, 1), kw.get("missing", []),
                   kw.get("dups", []))


def msgs(issues: list[Issue], level: str) -> str:
    return " | ".join(i.message for i in issues if i.level == level)


def test_missing_optional_columns_reported_as_info():
    out = validate(make_ds())
    assert "share_of_wallet_pct" in msgs(out, "info")


def test_model_weights_not_100_is_warning():
    k = pd.DataFrame({"arquitectura": ["a", "a"], "perfil": ["X", "X"], "peso_objetivo": [0.3, 0.2]})
    out = validate(make_ds(carteras=k))
    assert "0.50" in msgs(out, "warning") or "50" in msgs(out, "warning")


def test_model_weights_100_has_no_weight_warning():
    out = validate(make_ds())
    assert "peso" not in msgs(out, "warning").lower()


def test_rv_categories_not_summing_to_total_is_error():
    k = pd.DataFrame({"arquitectura": ["a"], "perfil": ["X"], "peso_objetivo": [1.0],
                      "pct_renta_variable": [0.6], "pct_rv_usa": [0.2], "pct_rv_europa": [0.2]})
    assert "pct_renta_variable" in msgs(validate(make_ds(carteras=k)), "error")


def test_currency_not_summing_100_is_error():
    k = pd.DataFrame({"arquitectura": ["a"], "perfil": ["X"], "peso_objetivo": [1.0],
                      "pct_moneda_usd": [0.5], "pct_moneda_clp": [0.2],
                      "pct_moneda_uf": [0.0], "pct_moneda_otras": [0.0]})
    assert "moneda" in msgs(validate(make_ds(carteras=k)), "error").lower()


def test_uf_greater_than_rf_local_is_error():
    k = pd.DataFrame({"arquitectura": ["a"], "perfil": ["X"], "peso_objetivo": [1.0],
                      "diccionario": ["Fondo Z"], "pct_rf_local": [0.25], "pct_moneda_uf": [0.30]})
    assert "Fondo Z" in msgs(validate(make_ds(carteras=k)), "error")


def test_servicio_sin_clasificar_listed():
    c = pd.DataFrame({"rut": ["R1", "R2"], "servicio": ["Sin clasificar", "ADC"],
                      "perfil_norm": ["EQUILIBRADO"] * 2, "advisor": ["a", "b"]})
    assert "Sin clasificar" in msgs(validate(make_ds(clientes=c)), "warning")


def test_perfil_fuera_de_los_cinco_is_warning():
    c = pd.DataFrame({"rut": ["R1"], "servicio": ["ADC"], "perfil_norm": ["OTRO"], "advisor": ["a"]})
    assert "OTRO" in msgs(validate(make_ds(clientes=c)), "warning")


def test_missing_sheet_is_error_and_duplicates_warn():
    out = validate(make_ds(missing=["Dummy Posiciones"], dups=["R9"]))
    assert "Dummy Posiciones" in msgs(out, "error")
    assert "R9" in msgs(out, "warning")
