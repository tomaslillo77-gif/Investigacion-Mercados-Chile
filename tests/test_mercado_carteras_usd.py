import pandas as pd
import pytest

from wm.config import load_config
from wm.loader import load_dataset
from wm.mercado.carteras import armar_cartera_yahoo, cobertura, exposicion
from wm.mercado.internacionales import COLUMNAS

CFG = load_config("carteras_usd")
SIN_DATOS = {"Fidelity Emerging Asia", "Schroder Emerging Asia", "Hamilton Lane Global Private Assets",
             "Schroder Global Corporate"}                      # los que Yahoo no entrega hoy


def _yahoo(omitir=()):
    filas = []
    for i, n in enumerate(CFG["fondos"]):
        if n in omitir or n in SIN_DATOS:
            filas.append({**{c: None for c in COLUMNAS}, "instrumento": n, "estado": "Sin ticker"})
            continue
        etf = i % 3 == 0
        filas.append({"instrumento": n, "isin": "X", "ticker": f"T{i}", "nombre_yahoo": n, "tipo": "ETF" if etf else "MUTUALFUND",
                      "moneda": "USD", "costo": 0.2 if etf else None, "patrimonio": 1e9, "precio": 100.0,
                      "fecha_precio": "2026-10-17", "rent_ytd": 3.0, "rent_1a": 10.0 + i, "rent_3a": 6.0, "estado": "Yahoo"})
    return pd.DataFrame(filas, columns=COLUMNAS)


def _peso(c, fondo):
    return round(c.loc[c["fondo"] == fondo, "peso"].sum(), 6)


def test_config_es_consistente_con_el_catalogo_y_los_perfiles():
    catalogo = set(load_dataset().carteras["instrumento"])
    assert set(CFG["fondos"]) <= catalogo, set(CFG["fondos"]) - catalogo
    assert set(CFG["perfiles"]) == set(load_config("arquitecturas")["perfiles_nombres"])
    for nombre, p in CFG["perfiles"].items():
        for clave, clase in (("renta_variable", "Renta variable"), ("renta_fija", "Renta fija"),
                             ("alternativos", "Activos alternativos")):
            for fondo in p.get(clave, {}):
                assert CFG["fondos"][fondo]["clase"] == clase and CFG["fondos"][fondo]["sub"] in CFG["orden"][clase]
        assert p["rv"] + p["alt"] == {"PRESERVACION": 20, "DEFENSIVO": 40, "EQUILIBRADO": 50, "CLASICO_60_40": 60,
                                      "CRECIMIENTO": 80}[nombre]
        assert (p["alt"] == 0) == ("alternativos" not in p)
        assert len(p["renta_variable"]) >= 4 and len(p["renta_fija"]) >= 5 - (nombre == "CRECIMIENTO")
        for clave in ("renta_variable", "renta_fija"):
            assert max(p[clave].values()) / sum(p[clave].values()) <= 0.4, (nombre, clave)   # ningún fondo domina
    assert not any(f in SIN_DATOS for p in CFG["perfiles"].values() for k in ("renta_variable", "renta_fija", "alternativos")
                   for f in p.get(k, {})), "los fondos sin datos en Yahoo no entran a las carteras"


@pytest.mark.parametrize("perfil", list(CFG["perfiles"]))
def test_cada_perfil_suma_uno_con_el_peso_de_rv_rf_y_alt(perfil):
    c = armar_cartera_yahoo(perfil, CFG, _yahoo())
    p = CFG["perfiles"][perfil]
    assert round(c["peso"].sum(), 6) == 1.0
    por_clase = c.groupby("clase")["peso"].sum().round(6).to_dict()
    assert por_clase.get("Renta variable", 0) == p["rv"] / 100 and por_clase.get("Activos alternativos", 0) == p["alt"] / 100
    assert round(por_clase["Renta fija"], 6) == round(1 - (p["rv"] + p["alt"]) / 100, 6)


def test_preservacion_reparte_el_ejemplo_de_ee_uu():
    c = armar_cartera_yahoo("PRESERVACION", CFG, _yahoo())
    assert _peso(c, "Core S&P 500 UCIT") == 0.08 and _peso(c, "Janus Henderson Pan European") == 0.06
    assert "Activos alternativos" not in set(c["clase"])
    assert list(c["clase"].drop_duplicates()) == ["Renta variable", "Renta fija"]


def test_orden_de_visualizacion_y_ticker_como_serie():
    c = armar_cartera_yahoo("EQUILIBRADO", CFG, _yahoo())
    assert list(c["clase"].drop_duplicates()) == ["Renta variable", "Renta fija", "Activos alternativos"]
    assert list(c["subactivo"].drop_duplicates()) == ["Estados Unidos", "Europa", "Latinoamérica", "Investment Grade",
                                                      "High Yield", "Alternativos"]
    assert c["serie"].str.startswith("T").all() and c["fo_run"].isna().all()


def test_fondo_sin_datos_conserva_el_peso_y_se_marca():
    c = armar_cartera_yahoo("PRESERVACION", CFG, _yahoo(omitir=["Janus Henderson Pan European"]))
    f = c[c["fondo"] == "Janus Henderson Pan European"].iloc[0]
    assert f["estado"] == "Sin datos" and round(f["peso"], 6) == 0.06 and pd.isna(f["rent_1a"]) and f["moneda"] == "Sin dato"
    assert round(c["peso"].sum(), 6) == 1.0


def test_sin_foto_de_yahoo_todo_queda_sin_datos():
    c = armar_cartera_yahoo("DEFENSIVO", CFG, None)
    assert (c["estado"] == "Sin datos").all() and round(c["peso"].sum(), 6) == 1.0


def test_costo_solo_de_etfs_y_cobertura_del_costo():
    c = armar_cartera_yahoo("DEFENSIVO", CFG, _yahoo())
    assert c["tac"].notna().any() and c["tac"].isna().any()          # los fondos mutuos no traen costo en Yahoo
    cob = cobertura(c, "tac")
    assert 0 < cob < 1 and round(cob, 6) == round(c.loc[c["tac"].notna(), "peso"].sum(), 6)
    assert cobertura(c.assign(tac=None), "tac") == 0


def test_exposicion_por_moneda_usa_la_moneda_de_cotizacion():
    c = armar_cartera_yahoo("EQUILIBRADO", CFG, _yahoo())
    assert exposicion(c)["moneda"]["grupo"].tolist() == ["USD"]
