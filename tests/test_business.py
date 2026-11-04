import pandas as pd
import pytest

from wm.business import (aum_por_arquitectura, aum_por_fondo, comisiones_area, comisiones_por,
                         rentabilidad_area, rentabilidad_por)

CARTERAS = pd.DataFrame({"isin": ["I1", "I2"], "diccionario": ["Fondo Uno", "Fondo Dos"],
                         "arquitectura": ["x", "x"], "perfil": ["p", "p"]})
POS = pd.DataFrame({"rut": ["A", "B", "B", "C"], "isin": ["I1", "I1", "I2", "ZZ"],
                    "instrumento": ["a", "a", "b", "Fondo Sin Catalogo"],
                    "valor_clp": [100.0, 300.0, 100.0, 500.0],
                    "rent_no_realizada": [0.10, 0.05, 0.02, 0.00]})


def view(**extra) -> pd.DataFrame:
    base = {"rut": ["A", "B", "C"], "advisor": ["IA1", "IA1", "IA2"], "servicio": ["ADC", "ASE", "ADC"],
            "aum_clp": [100.0, 400.0, 500.0], "arquitectura": ["x", None, "y"],
            "perfil_norm": ["P1", "P1", "P2"], "cliente_label": ["A", "B", "C"]}
    base.update(extra)
    return pd.DataFrame(base)


def test_aum_por_fondo_groups_by_catalog_name_and_falls_back_to_instrumento():
    t = aum_por_fondo(POS, CARTERAS).set_index("fondo")
    assert t.loc["Fondo Uno", "aum"] == 400.0 and t.loc["Fondo Uno", "n_clientes"] == 2
    assert "Fondo Sin Catalogo" in t.index
    assert t["pct"].sum() == pytest.approx(100.0)
    assert list(aum_por_fondo(POS, CARTERAS)["fondo"])[0] == "Fondo Sin Catalogo"  # ordenado por AUM desc


def test_aum_por_arquitectura_has_sin_determinar_bucket_and_sums_100():
    t = aum_por_arquitectura(view(), {"x": "Abierta X"}).set_index("arquitectura")
    assert t.loc["Abierta X", "aum"] == 100.0
    assert t.loc["Sin determinar", "aum"] == 400.0
    assert t.loc["y", "aum"] == 500.0  # sin nombre visible: se muestra el código
    assert t["pct"].sum() == pytest.approx(100.0)


def test_rentabilidad_prefers_excel_column_weighted_by_aum():
    v = view(rentabilidad_12m_pct=[10.0, 5.0, 2.0])
    r = rentabilidad_por(v, "advisor", POS).set_index("grupo")
    assert r.loc["IA1", "rentabilidad_pct"] == pytest.approx((10 * 100 + 5 * 400) / 500)
    assert r["fuente"].iloc[0].startswith("Excel")
    pct, fuente = rentabilidad_area(v, POS)
    assert pct == pytest.approx((10 * 100 + 5 * 400 + 2 * 500) / 1000)


def test_rentabilidad_falls_back_to_positions_no_realizada():
    r = rentabilidad_por(view(), "advisor", POS).set_index("grupo")
    # IA1: A (10%) pesa 100; B ((0.05*300+0.02*100)/400=4.25%) pesa 400
    assert r.loc["IA1", "rentabilidad_pct"] == pytest.approx((10 * 100 + 4.25 * 400) / 500)
    assert "no realizada" in r["fuente"].iloc[0]


def test_rentabilidad_none_without_any_source():
    assert rentabilidad_por(view(), "advisor", POS.drop(columns=["rent_no_realizada"])) is None
    assert rentabilidad_area(view(), None) is None


def test_comisiones_none_without_columns():
    assert comisiones_por(view(), "advisor") is None
    assert comisiones_area(view()) is None


def test_comisiones_by_group_and_area_totals():
    v = view(comision_anual_clp=[10.0, 40.0, 30.0], comision_cobrada_clp=[5.0, 20.0, 30.0])
    c = comisiones_por(v, "advisor").set_index("grupo")
    assert c.loc["IA1", "comision_anual"] == 50.0 and c.loc["IA1", "comision_cobrada"] == 25.0
    assert c.loc["IA1", "pct_cobrado"] == pytest.approx(50.0)
    assert c.loc["IA1", "tasa_pct"] == pytest.approx(10.0)  # 50 / 500 AUM
    a = comisiones_area(v)
    assert a["anual"] == 80.0 and a["cobrada"] == 55.0 and a["tasa_pct"] == pytest.approx(8.0)
