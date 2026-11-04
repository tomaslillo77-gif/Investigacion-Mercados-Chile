from datetime import date

import pandas as pd
import pytest

from wm.config import load_config
from wm.priority import score_clients

HOY = date(2026, 10, 17)
CFG = load_config("prioridad")


def clientes(**cols) -> pd.DataFrame:
    n = len(next(iter(cols.values())))
    base = {"rut": [f"R{i}" for i in range(n)], "aum_clp": [1000.0] * n,
            "ultima_reunion": [pd.Timestamp(HOY)] * n}
    base.update(cols)
    return pd.DataFrame(base)


def test_larger_aum_scores_higher_tamano():
    out = score_clients(clientes(aum_clp=[100.0, 10000.0]), CFG, HOY)
    assert out.loc[1, "comp_tamano"] > out.loc[0, "comp_tamano"]


def test_days_without_contact_raises_riesgo_fuga():
    f = [pd.Timestamp(HOY), pd.Timestamp(date(2026, 4, 1))]  # 0 y 199 días
    out = score_clients(clientes(ultima_reunion=f), CFG, HOY)
    assert out.loc[0, "comp_riesgo_fuga"] == pytest.approx(0.0)
    assert out.loc[1, "comp_riesgo_fuga"] == pytest.approx(1.0)


def test_missing_ultima_reunion_is_max_risk_and_motivo_sin_contacto():
    out = score_clients(clientes(ultima_reunion=[pd.NaT, pd.Timestamp(HOY)]), CFG, HOY)
    assert out.loc[0, "comp_riesgo_fuga"] == pytest.approx(1.0)
    assert any("Sin contacto registrado" in m for m in out.loc[0, "motivos"])


def test_missing_component_columns_reweight_remaining():
    out = score_clients(clientes(aum_clp=[100.0, 10000.0]), CFG, HOY)
    assert out["comp_oportunidad"].isna().all() and out["comp_ingresos"].isna().all()
    assert out.loc[1, "prioridad"] <= 100.0
    # sin las columnas opcionales, el máximo posible igual alcanza 100 (pesos renormalizados)
    maxed = score_clients(clientes(aum_clp=[100.0, 10000.0],
                                   ultima_reunion=[pd.Timestamp(HOY), pd.NaT]), CFG, HOY)
    assert maxed["prioridad"].max() == pytest.approx(100.0)


def test_oportunidad_uses_share_of_wallet():
    out = score_clients(clientes(share_of_wallet_pct=[90.0, 10.0]), CFG, HOY)
    assert out.loc[1, "comp_oportunidad"] > out.loc[0, "comp_oportunidad"]
    assert any("SoW 10%" in m for m in out.loc[1, "motivos"])


def test_motivos_cite_top_two_components():
    d = pd.Timestamp(date(2026, 6, 19))  # 120 días antes de HOY
    out = score_clients(clientes(ultima_reunion=[d]), CFG, HOY)
    assert "Sin contacto 120 días" in out.loc[0, "motivos"]
    assert len(out.loc[0, "motivos"]) <= 2


def test_score_within_0_100():
    out = score_clients(clientes(aum_clp=[1.0, 5.0, 9.0], share_of_wallet_pct=[0.0, 50.0, 100.0],
                                 desvio_modelo_pct=[30.0, -5.0, 0.0]), CFG, HOY)
    assert out["prioridad"].between(0, 100).all()
