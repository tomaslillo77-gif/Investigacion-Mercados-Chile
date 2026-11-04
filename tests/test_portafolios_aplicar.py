from datetime import date, datetime

import pandas as pd
import pytest

from wm.architecture import infer_architecture
from wm.catalogo import desde_carteras
from wm.config import load_config
from wm.display import nombres_arquitecturas
from wm.enrich import enrich_clientes
from wm.exposure import PERFIL_PERSONALIZADO, es_personalizada, perfil_de, perfil_of
from wm.loader import load_dataset
from wm.metrics import mix_por
from wm.portafolio_cliente import (
    DEFINIDO, DESACTUALIZADO, SIN_DEFINIR, aplicar_portafolios, desde_posiciones, desvio_vs_objetivo, estado_portafolios, normalizar,
)

HOY = date(2026, 10, 27)


@pytest.fixture(scope="module")
def ds():
    return load_dataset()


@pytest.fixture(scope="module")
def cat(ds):
    return desde_carteras(ds.carteras)[0]


def _vigentes(rut, items, version=1, creado=datetime(2026, 10, 1), perfil="EQUILIBRADO"):
    return items.assign(rut=rut, version=version, advisor="IA_X", creado_en=creado, perfil_al_guardar=perfil)


def _cliente_con_posiciones(ds):
    rut = ds.posiciones["rut"].iloc[0]
    return rut, ds.posiciones[ds.posiciones["rut"] == rut]


def test_los_portafolios_vigentes_pasan_a_ser_la_arquitectura_del_cliente_y_sus_filas_de_cartera(ds, cat):
    rut, pos = _cliente_con_posiciones(ds)
    nuevo = aplicar_portafolios(ds, _vigentes(rut, desde_posiciones(pos, cat)), cat)
    c = nuevo.clientes.set_index("rut")
    assert c.loc[rut, "arquitectura"] == f"personalizada:{rut}" and es_personalizada(c.loc[rut, "arquitectura"])
    otros = c.drop(index=rut)
    assert (otros["arquitectura"].fillna("x") == ds.clientes.set_index("rut").drop(index=rut)["arquitectura"].fillna("x")).all()
    filas = nuevo.carteras[nuevo.carteras["arquitectura"] == f"personalizada:{rut}"]
    assert len(filas) > 0 and set(filas["perfil"]) == {PERFIL_PERSONALIZADO} and filas["peso_objetivo"].sum() == pytest.approx(1.0)
    assert len(nuevo.carteras) == len(ds.carteras) + len(filas) and nuevo.casa() is nuevo.carteras_casa and len(nuevo.casa()) == len(ds.carteras)


def test_sin_portafolios_o_con_ruts_desconocidos_el_dataset_no_cambia(ds, cat):
    assert aplicar_portafolios(ds, pd.DataFrame(), cat) is ds
    rut, pos = _cliente_con_posiciones(ds)
    assert aplicar_portafolios(ds, _vigentes("RUT_NO_EXISTE", desde_posiciones(pos, cat)), cat) is ds
    assert ds.casa() is ds.carteras


def test_el_perfil_se_busca_como_personalizado_y_la_arquitectura_se_muestra_personalizada(ds):
    assert perfil_de(ds.carteras, "EQUILIBRADO", "personalizada:R1") == PERFIL_PERSONALIZADO
    assert perfil_de(ds.carteras, "EQUILIBRADO", "abierta_local") == perfil_of(ds.carteras, "EQUILIBRADO")
    n = nombres_arquitecturas()
    assert n.get("personalizada:RUT_1") == "Personalizada" and n["personalizada:RUT_1"] == "Personalizada" and n.get("abierta_local") == load_config("arquitecturas")["nombres"]["abierta_local"]
    mix = mix_por(pd.DataFrame({"rut": ["a", "b", "c"], "aum_clp": [10.0, 20.0, 30.0], "arquitectura": ["personalizada:a", "personalizada:b", "abierta_local"]}), "arquitectura", n)
    assert set(mix["grupo"]) == {"Personalizada", n.get("abierta_local")} and mix.set_index("grupo").loc["Personalizada", "n_clientes"] == 2


def test_la_inferencia_ignora_los_portafolios_de_otros_clientes_y_la_declarada_solo_mide_la_suya(ds, cat):
    rut, pos = _cliente_con_posiciones(ds)
    nuevo = aplicar_portafolios(ds, _vigentes(rut, desde_posiciones(pos, cat)), cat)
    sin = infer_architecture(pos, ds.carteras, 0.0)
    con = infer_architecture(pos, nuevo.carteras, 0.0)
    assert con.arquitectura == sin.arquitectura and con.cobertura == pytest.approx(sin.cobertura) and not es_personalizada(con.arquitectura)
    declarada = infer_architecture(pos, nuevo.carteras, 0.6, declarada=f"personalizada:{rut}")
    assert declarada.arquitectura == f"personalizada:{rut}" and not declarada.inferida and declarada.cobertura == pytest.approx(1.0)


def test_enrich_usa_el_portafolio_como_arquitectura_declarada(ds, cat):
    rut, pos = _cliente_con_posiciones(ds)
    view = enrich_clientes(aplicar_portafolios(ds, _vigentes(rut, desde_posiciones(pos, cat)), cat), HOY).set_index("rut")
    assert view.loc[rut, "arquitectura"] == f"personalizada:{rut}" and not view.loc[rut, "arquitectura_inferida"] and view.loc[rut, "cobertura_arq"] == pytest.approx(1.0)


def test_el_desvio_contra_el_objetivo_es_cero_si_el_objetivo_es_lo_que_tiene_y_crece_si_se_aleja(ds, cat):
    rut, pos = _cliente_con_posiciones(ds)
    objetivo = desde_posiciones(pos, cat)
    igual = aplicar_portafolios(ds, _vigentes(rut, objetivo), cat)
    assert desvio_vs_objetivo(igual, [rut], _vigentes(rut, objetivo), cat)[rut] == pytest.approx(0.0, abs=0.1)
    assert igual.clientes.set_index("rut").loc[rut, "desvio_modelo_pct"] == pytest.approx(0.0, abs=0.1)
    distinto = objetivo.copy()
    distinto["peso"] = [100.0] + [0.0] * (len(distinto) - 1)
    lejos = aplicar_portafolios(ds, _vigentes(rut, normalizar(distinto)), cat)
    assert abs(desvio_vs_objetivo(lejos, [rut], _vigentes(rut, normalizar(distinto)), cat)[rut]) > 1.0
    assert desvio_vs_objetivo(igual, ["RUT_SIN_POSICIONES"], _vigentes(rut, objetivo), cat) == {}


def test_estado_de_los_portafolios_sin_definir_definido_y_desactualizado():
    view = pd.DataFrame({"rut": ["A", "B", "C", "D"], "perfil_norm": ["EQUILIBRADO", "EQUILIBRADO", "CRECIMIENTO", None]})
    resumen = pd.DataFrame({"rut": ["B", "C", "D"], "version": [3, 1, 2], "creado_en": [datetime(2026, 10, 1), datetime(2026, 10, 1), datetime(2026, 1, 5)],
                            "perfil_al_guardar": ["EQUILIBRADO", "EQUILIBRADO", None], "n_items": [5, 4, 3]})
    e = estado_portafolios(view, resumen, HOY).set_index("rut")
    assert list(e["portafolio_estado"]) == [SIN_DEFINIR, DEFINIDO, DESACTUALIZADO, DESACTUALIZADO]
    assert pd.isna(e.loc["A", "portafolio_version"]) and e.loc["B", "portafolio_version"] == 3
    assert "cambió de EQUILIBRADO a CRECIMIENTO" in e.loc["C", "portafolio_motivo"] and "hace 9 meses" in e.loc["D", "portafolio_motivo"] and e.loc["B", "portafolio_motivo"] == ""
    assert (estado_portafolios(view, None, HOY)["portafolio_estado"] == SIN_DEFINIR).all()


def test_contar_estados_resume_la_cartera_de_clientes():
    from wm.portafolio_cliente import contar_estados
    v = pd.DataFrame({"portafolio_estado": [DEFINIDO, DEFINIDO, DESACTUALIZADO, SIN_DEFINIR]})
    assert contar_estados(v) == {"n": 4, "definidos": 2, "desactualizados": 1, "sin_definir": 1, "pct_con_portafolio": 75.0}
    assert contar_estados(pd.DataFrame({"rut": ["a"]}))["sin_definir"] == 1 and contar_estados(pd.DataFrame({"portafolio_estado": []}))["pct_con_portafolio"] is None
