import pandas as pd
import pytest

from wm.alignment import desvio_por_clase, ranking
from wm.exposure import Exposure


def exp(rf, rv, alt, cob=1.0) -> Exposure:
    return Exposure(clase={"Renta Fija": rf, "Renta Variable": rv, "Alternativos": alt}, cobertura=cob)


def test_desvio_por_clase_in_percentage_points_normalized_by_coverage():
    d = desvio_por_clase(exp(0.3, 0.2, 0.0, cob=0.5), exp(0.5, 0.4, 0.1))
    assert d["Renta Fija"] == pytest.approx(10.0)    # 0.3/0.5=60% vs 50%
    assert d["Renta Variable"] == pytest.approx(0.0)  # 0.2/0.5=40% vs 40%
    assert d["Alternativos"] == pytest.approx(-10.0)


def test_ranking_uses_excel_desvio_and_sorts_by_abs_desc():
    view = pd.DataFrame({"rut": ["A", "B", "C"], "entidad": ["a", "b", "c"], "advisor": ["x"] * 3,
                         "aum_clp": [1.0, 2.0, 3.0], "desvio_modelo_pct": [2.0, -15.0, 8.0]})
    r = ranking(view, None)
    assert list(r["rut"]) == ["B", "C", "A"]
    assert set(r["fuente"]) == {"Excel"}


def test_ranking_none_without_desvio_column_nor_breakdown(mini_xlsx):
    from wm.loader import load_dataset
    ds = load_dataset(mini_xlsx)
    view = ds.clientes.assign(arquitectura="abierta_pesos")
    assert ranking(view, ds) is None


def _exp(clase, rv, rf, moneda, uf_rf, cob=1.0):
    from wm.exposure import Exposure
    return Exposure(clase=clase, rv_categorias=rv, rf_categorias=rf, moneda=moneda, uf_sobre_rf_local=uf_rf, cobertura=cob)


def test_desvio_detalle_lists_each_class_with_its_subassets_then_currency_and_uf_over_local_rf():
    from wm.alignment import desvio_detalle
    cli = _exp({"Renta Variable": 0.6, "Renta Fija": 0.4, "Alternativos": 0.0}, {"USA": 0.4, "Chile": 0.2},
               {"Renta Fija Local": 0.4, "High Yield": 0.0}, {"USD": 0.5, "CLP": 0.2, "UF": 0.3, "Otras": 0.0}, 0.75)
    mod = _exp({"Renta Variable": 0.5, "Renta Fija": 0.5, "Alternativos": 0.0}, {"USA": 0.5},
               {"Renta Fija Local": 0.3, "High Yield": 0.2}, {"USD": 0.6, "CLP": 0.1, "UF": 0.3, "Otras": 0.0}, 0.5)
    rows = desvio_detalle(cli, mod)
    assert [r["label"] for r in rows] == ["Renta Variable", "USA", "Chile", "Renta Fija", "Renta Fija Local", "High Yield",
                                          "Alternativos", "Moneda", "USD", "CLP", "UF", "% UF de la renta fija local"]
    by = {r["label"]: r for r in rows}
    assert by["Renta Variable"]["desvio"] == pytest.approx(10.0) and by["USA"]["desvio"] == pytest.approx(-10.0)
    assert by["Chile"]["desvio"] == pytest.approx(20.0) and by["High Yield"]["desvio"] == pytest.approx(-20.0)
    assert by["USD"]["desvio"] == pytest.approx(-10.0)
    assert by["% UF de la renta fija local"]["desvio"] == pytest.approx(25.0)
    assert by["Moneda"]["nivel"] == "titulo" and "desvio" not in by["Moneda"]


def test_desvio_detalle_is_empty_without_comparable_model():
    from wm.alignment import desvio_detalle
    from wm.exposure import Exposure
    assert desvio_detalle(_exp({"Renta Fija": 1.0}, {}, {}, {}, None), Exposure()) == []
