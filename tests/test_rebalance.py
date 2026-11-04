import pandas as pd
import pytest

from wm.rebalance import plan_rebalanceo

CARTERAS = pd.DataFrame({
    "arquitectura": ["x", "x", "x", "x", "y"],
    "perfil": ["p", "p", "p", "p", "p"],
    "diccionario": ["Fondo A", "Fondo B", "Fondo C", "Fondo Z", "Fondo A"],
    "isin": ["A1", "B1", "C1", "Z_W", "A_OTRO"],
    "serie": ["I", "I", "I", "Wealth", "I"],
    "peso_objetivo": [0.5, 0.3, 0.2, 0.0, 1.0],
})
CARTERAS = CARTERAS[CARTERAS["isin"] != "Z_W"].reset_index(drop=True)


def pos(**valores) -> pd.DataFrame:
    return pd.DataFrame({"isin": list(valores), "instrumento": list(valores), "valor_clp": list(valores.values())})


def row(plan: pd.DataFrame, fondo: str) -> pd.Series:
    return plan.set_index("fondo").loc[fondo]


def test_gap_to_model_in_pp_and_clp_with_buy_sell_actions():
    plan = plan_rebalanceo(pos(A1=600.0, B1=400.0), CARTERAS, "x", "p")
    a, b, c = row(plan, "Fondo A"), row(plan, "Fondo B"), row(plan, "Fondo C")
    assert (a.pct_actual, a.pct_modelo, a.dif_pp, a.ajuste_clp, a.accion) == (60.0, 50.0, -10.0, -100.0, "Vender")
    assert (b.pct_actual, b.pct_modelo, b.dif_pp, b.ajuste_clp, b.accion) == (40.0, 30.0, -10.0, -100.0, "Vender")
    assert (c.pct_actual, c.pct_modelo, c.dif_pp, c.ajuste_clp, c.accion) == (0.0, 20.0, 20.0, 200.0, "Comprar")
    assert plan["ajuste_clp"].sum() == pytest.approx(0.0)


def test_fund_held_but_not_in_model_is_a_full_sell():
    plan = plan_rebalanceo(pos(A1=500.0, D1=500.0), CARTERAS, "x", "p")
    d = row(plan, "D1")  # sin catálogo: se identifica por el nombre del instrumento
    assert d.pct_modelo == 0.0 and d.accion == "Vender" and d.ajuste_clp == pytest.approx(-500.0)


def test_other_series_of_a_model_fund_is_compared_at_fund_level_with_both_series_shown():
    z_model = pd.DataFrame({
        "arquitectura": ["x", "x"], "perfil": ["p", "p"], "diccionario": ["Fondo Z", "Fondo Z"],
        "isin": ["Z_W", "Z_RET"], "serie": ["Wealth", "A"], "peso_objetivo": [1.0, 0.0]})
    plan = plan_rebalanceo(pos(Z_RET=1000.0), z_model, "x", "p")
    z = row(plan, "Fondo Z")
    assert z.serie_actual == "A" and z.serie_modelo == "Wealth"
    # la serie distinta no cambia el peso del fondo: la diferencia de serie se avisa aparte
    assert z.pct_actual == 100.0 and z.pct_modelo == 100.0 and z.accion == "Mantener"


def test_within_tolerance_is_mantener():
    plan = plan_rebalanceo(pos(A1=505.0, B1=300.0, C1=195.0), CARTERAS, "x", "p")
    assert row(plan, "Fondo A").accion == "Mantener"  # 50.5% vs 50%: 0.5 pp < 1 pp


def test_model_weights_are_normalized_to_100():
    c = CARTERAS.copy()
    c.loc[c["arquitectura"] == "x", "peso_objetivo"] *= 0.5  # suma 0.5 -> debe normalizarse
    plan = plan_rebalanceo(pos(A1=500.0, B1=300.0, C1=200.0), c, "x", "p")
    assert plan["pct_modelo"].sum() == pytest.approx(100.0)
    assert plan["dif_pp"].abs().max() == pytest.approx(0.0)


def test_no_model_returns_none():
    assert plan_rebalanceo(pos(A1=1.0), CARTERAS, None, "p") is None
    assert plan_rebalanceo(pos(A1=1.0), CARTERAS, "x", None) is None
    assert plan_rebalanceo(pos(A1=1.0), CARTERAS, "inexistente", "p") is None


def test_client_without_positions_uses_base_clp_and_buys_the_whole_model():
    plan = plan_rebalanceo(pos().iloc[0:0], CARTERAS, "x", "p", base_clp=1000.0)
    assert plan["accion"].eq("Comprar").all()
    assert row(plan, "Fondo A").ajuste_clp == pytest.approx(500.0)


def test_rows_sorted_by_largest_adjustment_first():
    plan = plan_rebalanceo(pos(A1=600.0, B1=400.0), CARTERAS, "x", "p")
    assert plan["ajuste_clp"].abs().is_monotonic_decreasing
