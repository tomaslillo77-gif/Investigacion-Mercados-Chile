import pandas as pd
import pytest

from wm.costos import FONDOS, costo_comision, costo_fondos

CARTERAS = pd.DataFrame({"isin": ["A", "B", "C"], "comision": [0.010, 0.020, float("nan")]})
POS = pd.DataFrame({"isin": ["A", "B"], "valor_clp": [600.0, 400.0]})


def _row(servicio, aum=1000.0, **extra):
    return pd.Series({"servicio": servicio, "aum_clp": aum, **extra})


def test_costo_fondos_is_value_weighted():
    costo, ponderado, cob = costo_fondos(POS, CARTERAS)
    assert costo == pytest.approx(14.0)          # 600 x 1% + 400 x 2%
    assert ponderado == pytest.approx(1.4)
    assert cob == 1.0


def test_costo_fondos_ignores_positions_without_series_cost():
    pos = pd.DataFrame({"isin": ["A", "C"], "valor_clp": [500.0, 500.0]})
    costo, ponderado, cob = costo_fondos(pos, CARTERAS)
    assert costo == pytest.approx(5.0) and ponderado == pytest.approx(1.0) and cob == 0.5


@pytest.mark.parametrize("servicio,tarifa", [("ADC", 0.0040), ("ASE", 0.0025)])
def test_adc_and_ase_add_advisory_fee_to_fund_cost(servicio, tarifa):
    c = costo_comision(_row(servicio), POS, CARTERAS)
    assert dict(c.items) == {FONDOS: pytest.approx(14.0), servicio: pytest.approx(1000 * tarifa)}
    assert c.total == pytest.approx(14.0 + 1000 * tarifa)
    assert c.tasa_pct == pytest.approx(c.total / 1000 * 100)


def test_tra_breaks_down_into_four_transactional_products():
    row = _row("TRA", com_tra_renta_variable_clp=4.0, com_tra_renta_fija_clp=3.0,
               com_tra_intermediacion_clp=2.0, com_tra_allfunds_clp=1.0)
    c = costo_comision(row, POS, CARTERAS)
    assert [n for n, _ in c.items] == ["Renta Variable", "Renta Fija", "Intermediación", "Allfunds"]
    assert c.total == 10.0


def test_tra_without_data_and_other_services_have_no_breakdown():
    assert costo_comision(_row("TRA"), POS, CARTERAS) is None
    assert costo_comision(_row("Self Directed"), POS, CARTERAS) is None


def test_adc_without_positions_notes_advisory_only():
    c = costo_comision(_row("ADC"), POS.iloc[0:0], CARTERAS)
    assert c.total == pytest.approx(4.0) and c.nota
