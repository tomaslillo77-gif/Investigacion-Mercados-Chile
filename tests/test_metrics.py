from datetime import date

import pandas as pd
import pytest

from wm.metrics import comparar_advisors, flujos_netos, kpis_advisor, mix_servicio

HOY = date(2026, 10, 17)


def clientes(**extra) -> pd.DataFrame:
    base = {"rut": ["A", "B", "C"], "advisor": ["IA_1", "IA_1", "IA_2"],
            "servicio": ["ADC", "ASE", "ADC"], "aum_clp": [100.0, 300.0, 600.0],
            "ultima_reunion": [pd.Timestamp("2026-10-01"), pd.Timestamp("2026-01-01"), pd.NaT]}
    base.update(extra)
    return pd.DataFrame(base)


def test_mix_servicio_pct_sums_to_100():
    m = mix_servicio(clientes())
    assert m["pct"].sum() == pytest.approx(100.0)
    assert m.set_index("servicio").loc["ADC", "n_clientes"] == 2


def test_kpi_basics_and_contactados_90d():
    k = kpis_advisor(clientes(), HOY)
    assert k["aum"] == 1000.0 and k["n_clientes"] == 3
    assert k["pct_contactados_90d"] == pytest.approx(100 / 3)


def test_kpi_optional_none_when_column_missing():
    k = kpis_advisor(clientes(), HOY)
    assert k["sow_promedio"] is None and k["pct_wealth_plan"] is None


def test_kpi_optional_present():
    k = kpis_advisor(clientes(share_of_wallet_pct=[10.0, 20.0, 30.0],
                              tiene_wealth_plan=[True, False, False]), HOY)
    assert k["sow_promedio"] == pytest.approx(20.0)
    assert k["pct_wealth_plan"] == pytest.approx(100 / 3)


def test_flujos_none_without_columns():
    assert flujos_netos(clientes()) is None


def test_flujos_neto_is_aportes_minus_retiros():
    f = flujos_netos(clientes(aportes_periodo=[10.0, 5.0, 7.0], retiros_periodo=[1.0, 2.0, 3.0],
                              periodo=["2026-09", "2026-09", "2026-10"]))
    assert list(f["periodo"]) == ["2026-09", "2026-10"]
    assert list(f["neto"]) == [12.0, 4.0]


def test_comparar_advisors_one_row_per_advisor():
    c = comparar_advisors(clientes(), HOY).set_index("advisor")
    assert list(c.index) == ["IA_1", "IA_2"]
    assert c.loc["IA_1", "aum"] == 400.0
    assert pd.isna(c.loc["IA_1", "pct_series_malas"])


def test_comparar_advisors_series_malas_when_flag_present():
    c = comparar_advisors(clientes(serie_mala=[True, False, False]), HOY).set_index("advisor")
    assert c.loc["IA_1", "pct_series_malas"] == pytest.approx(50.0)


def test_flujos_netos_uses_flow_sheet_by_period_and_only_the_given_clients():
    import pandas as pd
    cl = pd.DataFrame({"rut": ["A", "B"], "aportes_periodo": [999.0, 999.0], "retiros_periodo": [999.0, 999.0]})
    fl = pd.DataFrame({"rut": ["A", "A", "B", "C"], "periodo": ["2026-10-05", "2026-10-19", "2026-10-05", "2026-10-05"],
                       "aportes_clp": [10.0, 4.0, 5.0, 100.0], "retiros_clp": [1.0, 2.0, 1.0, 100.0]})
    todos = flujos_netos(cl, fl)
    assert list(todos["periodo"]) == ["2026-10-05", "2026-10-19"]
    assert list(todos["aportes"]) == [15.0, 4.0] and list(todos["neto"]) == [13.0, 2.0]   # C no es cliente dado
    solo_b = flujos_netos(cl[cl["rut"] == "B"], fl)
    assert list(solo_b["aportes"]) == [5.0]


def test_mix_por_groups_by_aum_translates_names_and_sends_blanks_to_sin_determinar():
    import pandas as pd
    from wm.metrics import mix_por
    cl = pd.DataFrame({"rut": ["A", "B", "C"], "aum_clp": [10.0, 30.0, 60.0], "arquitectura": ["x", "x", None]})
    g = mix_por(cl, "arquitectura", {"x": "Abierta USD"})
    assert list(g["grupo"]) == ["Sin determinar", "Abierta USD"]        # por AUM descendente
    assert list(g["aum"]) == [60.0, 40.0] and list(g["n_clientes"]) == [1, 2]
    assert g["pct"].sum() == 100.0


def test_mix_por_respects_given_order_and_puts_unknown_names_last():
    import pandas as pd
    from wm.metrics import mix_por
    cl = pd.DataFrame({"rut": ["A", "B", "C"], "aum_clp": [1.0, 2.0, 3.0], "p": ["B", "A", "Z"]})
    g = mix_por(cl, "p", orden=["A", "B"])
    assert list(g["grupo"]) == ["A", "B", "Z"]
