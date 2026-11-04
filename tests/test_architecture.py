import pandas as pd
import pytest

from wm.architecture import infer_architecture

CARTERAS = pd.DataFrame({
    "arquitectura": ["x", "x", "y", "y"],
    "perfil": ["p"] * 4,
    "isin": ["I1", "I2", "I3", "I4"],
})


def pos(items: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame({"isin": list(items), "valor_clp": list(items.values())})


def test_infer_picks_architecture_with_highest_weighted_coverage():
    r = infer_architecture(pos({"I1": 300.0, "I2": 300.0, "I3": 100.0}), CARTERAS)
    assert r.arquitectura == "x" and r.inferida is True
    assert r.cobertura == pytest.approx(0.857, abs=1e-3)


def test_infer_below_threshold_returns_none():
    r = infer_architecture(pos({"I1": 100.0, "ZZ": 900.0}), CARTERAS)
    assert r.arquitectura is None
    assert r.cobertura == pytest.approx(0.1)


def test_declared_architecture_wins_over_inference():
    r = infer_architecture(pos({"I1": 100.0}), CARTERAS, declarada="y")
    assert r.arquitectura == "y" and r.inferida is False


def test_client_without_positions_returns_none_cobertura_zero():
    r = infer_architecture(pos({}), CARTERAS)
    assert r.arquitectura is None and r.cobertura == 0.0
