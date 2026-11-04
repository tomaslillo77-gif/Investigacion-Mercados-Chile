import pandas as pd
import pytest

from wm.config import load_config
from wm.mercado.carteras import armar_cartera, composicion_cartera, exposicion, ponderado
from wm.mercado.schema import Foto

CFG = load_config("carteras_fondos_mutuos_scotia")
BASE = ["ACCIONES USA", "RV EUROPA", "LATAM", "ACCIONES CHILE", "DEUDA M. PLAZO UF", "DEUDA MEDIANO PLAZO",
        "DEUDA LARGO PLAZO UF", "CORTO PLAZO UF", "SCOTIA REAL ESTATE GLOBAL"]


def _foto(omitir=()):
    filas = []
    for i, n in enumerate(BASE):
        if n in omitir:
            continue
        for serie, pat in (("A", 10.0), ("WEALTH", 50.0), ("CLASICA", 500.0)):  # la de mayor patrimonio no es WEALTH
            filas.append({"fo_run": 100 + i, "fm_serie": serie, "nombre_fondo": n, "nombre_agf": "SCOTIA CHILE",
                          "patrimonio": pat, "tac": 1.0 + i / 10 + (0.5 if serie == "WEALTH" else 0), "rent_ytd": 5.0,
                          "rent_1a": 10.0 + i, "rent_3a": 8.0, "rent_5a": None, "rent_10a": None, "participes": 1})
    s = pd.DataFrame(filas)
    return Foto(__import__("datetime").date(2026, 6, 30), s, pd.DataFrame(), pd.DataFrame())


def _peso(df, fondo):
    return df.loc[df["fondo"] == fondo, "peso"].sum()


def test_preservacion_reparte_20_80():
    c = armar_cartera("PRESERVACION", CFG, _foto())
    assert round(_peso(c, "ACCIONES USA"), 6) == 0.08 and round(_peso(c, "RV EUROPA"), 6) == 0.05
    assert round(_peso(c, "LATAM"), 6) == 0.03 and round(_peso(c, "ACCIONES CHILE"), 6) == 0.04
    rf = c[c["clase"] == "Renta fija"]
    assert round(rf["peso"].sum(), 6) == 0.8 and len(rf) == 3
    assert all(round(p, 6) == round(0.8 / 3, 6) for p in rf["peso"])


@pytest.mark.parametrize("perfil", list(CFG["perfiles"]))
def test_todos_los_perfiles_suman_uno(perfil):
    c = armar_cartera(perfil, CFG, _foto())
    assert round(c["peso"].sum(), 6) == 1.0
    assert round(c.loc[c["clase"] == "Renta variable", "peso"].sum(), 6) == CFG["perfiles"][perfil]["rv"] / 100


def test_usa_la_serie_wealth_aunque_otra_tenga_mas_patrimonio():
    c = armar_cartera("PRESERVACION", CFG, _foto())
    assert set(c["serie"]) == {"WEALTH"}


def test_sin_wealth_usa_la_de_mayor_patrimonio():
    f = _foto()
    f.series = f.series[f.series["fm_serie"] != "WEALTH"]
    assert set(armar_cartera("PRESERVACION", CFG, f)["serie"]) == {"CLASICA"}


def test_serie_fijada_en_config_manda():
    cfg = {**CFG, "fondos": {**CFG["fondos"], "ACCIONES USA": {**CFG["fondos"]["ACCIONES USA"], "serie": "A"}}}
    c = armar_cartera("PRESERVACION", cfg, _foto())
    assert c.loc[c["fondo"] == "ACCIONES USA", "serie"].iloc[0] == "A"


def test_fondo_ausente_en_cmf_queda_sin_datos_y_mantiene_peso():
    c = armar_cartera("PRESERVACION", CFG, _foto(omitir=["LATAM"]))
    f = c[c["fondo"] == "LATAM"].iloc[0]
    assert f["estado"] == "Sin datos" and round(f["peso"], 6) == 0.03 and pd.isna(f["rent_1a"])
    assert round(c["peso"].sum(), 6) == 1.0


def test_orden_de_visualizacion_sigue_client_portal():
    c = armar_cartera("PRESERVACION", CFG, _foto())
    assert list(c["subactivo"].drop_duplicates()) == ["Estados Unidos", "Europa", "Latinoamérica", "Chile", "Local"]
    assert list(c["clase"].drop_duplicates()) == ["Renta variable", "Renta fija"]


def test_ponderado_renormaliza_y_tolera_nan():
    d = pd.DataFrame({"peso": [0.5, 0.3, 0.2], "rent_1a": [10.0, 20.0, None]})
    assert round(ponderado(d, "rent_1a"), 6) == round((5 + 6) / 0.8, 6)
    assert pd.isna(ponderado(d.assign(rent_1a=None), "rent_1a"))


def test_config_real_es_consistente():
    assert set(CFG["perfiles"]) == set(load_config("arquitecturas")["perfiles_nombres"])
    for nombre, p in CFG["perfiles"].items():
        for clave, clase in (("renta_variable", "Renta variable"), ("renta_fija", "Renta fija")):
            for fondo in p[clave]:
                assert CFG["fondos"][fondo]["clase"] == clase, (nombre, fondo)
                assert CFG["fondos"][fondo]["sub"] in CFG["orden"][clase], (nombre, fondo)


def test_perfiles_diversificados_y_de_riesgo_creciente():
    rvs = [CFG["perfiles"][p]["rv"] for p in load_config("arquitecturas")["perfiles_nombres"]]
    assert rvs == sorted(rvs) and len(set(rvs)) == 5          # más riesgo, más renta variable
    for nombre, p in CFG["perfiles"].items():
        assert len(p["renta_variable"]) >= 4 and len(p["renta_fija"]) >= 3, nombre
        for clave in ("renta_variable", "renta_fija"):
            w = p[clave]
            assert max(w.values()) / sum(w.values()) <= 0.5, (nombre, clave)   # ningún fondo domina su clase
    assert not {"Japón", "Emergentes"} & {CFG["fondos"][f]["sub"] for p in CFG["perfiles"].values()
                                         for f in p["renta_variable"]}  # no hay fondo Scotia para esos subactivos


def test_moneda_del_valor_cuota_y_exposicion_suma_uno():
    f = _foto()
    f.series["moneda_funcional"] = "$$"
    c = armar_cartera("PRESERVACION", CFG, f)
    assert set(c["moneda"]) == {"CLP"}
    for e in exposicion(c).values():
        assert round(e["peso"].sum(), 6) == 1.0
    ex = exposicion(c)
    assert ex["clase"].set_index("grupo")["peso"].round(6).to_dict() == {"Renta variable": 0.2, "Renta fija": 0.8}
    assert ex["moneda"]["grupo"].tolist() == ["CLP"]


def test_moneda_dolar_y_sin_dato():
    f = _foto()
    f.series["moneda_funcional"] = "PROM"
    assert set(armar_cartera("PRESERVACION", CFG, f)["moneda"]) == {"USD"}
    assert set(armar_cartera("PRESERVACION", CFG, _foto(omitir=["LATAM"])).query("fondo == 'LATAM'")["moneda"]) == {"Sin dato"}


def test_alternativos_salen_del_presupuesto_de_renta_variable():
    for nombre, p in CFG["perfiles"].items():
        assert p["rv"] + p["alt"] == {"PRESERVACION": 20, "DEFENSIVO": 40, "EQUILIBRADO": 50, "CLASICO_60_40": 60,
                                      "CRECIMIENTO": 80}[nombre], nombre
    assert CFG["perfiles"]["PRESERVACION"]["alt"] == 0
    alts = [p["alt"] for p in CFG["perfiles"].values()]
    assert alts == sorted(alts)                                       # más riesgo, más alternativos


def test_cartera_con_alternativos_suma_uno_y_orden_rv_rf_alt():
    c = armar_cartera("EQUILIBRADO", CFG, _foto())
    assert round(c["peso"].sum(), 6) == 1.0
    assert list(c["clase"].drop_duplicates()) == ["Renta variable", "Renta fija", "Activos alternativos"]
    alt = c[c["clase"] == "Activos alternativos"]
    assert alt["fondo"].tolist() == ["SCOTIA REAL ESTATE GLOBAL"] and round(alt["peso"].sum(), 6) == 0.05
    assert round(c.loc[c["clase"] == "Renta fija", "peso"].sum(), 6) == 0.5


def test_preservacion_no_tiene_alternativos():
    assert "Activos alternativos" not in set(armar_cartera("PRESERVACION", CFG, _foto())["clase"])


def test_composicion_cartera_pondera_por_peso_y_marca_lo_que_falta():
    f = _foto()
    f.cartera = pd.DataFrame({"fo_run": [100, 100], "nombre_fondo": ["ACCIONES USA"] * 2, "emisor": ["A", "B"],
                              "clasificacion": ["Acciones extranjeras", "ETF – Acciones"], "pais": ["ESTADOS UNIDOS"] * 2,
                              "peso": [0.75, 0.25]})
    c = armar_cartera("PRESERVACION", CFG, f)
    g = composicion_cartera(c, f, "clasificacion").set_index("grupo")["peso"]
    assert round(g["Acciones extranjeras"], 6) == round(0.08 * 0.75, 6)
    assert round(g["ETF – Acciones"], 6) == round(0.08 * 0.25, 6)
    assert round(g["Sin composición"], 6) == 0.92 and round(g.sum(), 6) == 1.0
    assert composicion_cartera(c, None, "pais")["grupo"].tolist() == ["Sin composición"]
