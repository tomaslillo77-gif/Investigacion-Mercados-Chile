from datetime import datetime

import pandas as pd
import psycopg
import pytest

from tests.test_portafolio_page import _abrir, _html
from wm.asignacion import PENDIENTE, REFLEJADA, aplicar_asignaciones, cambios, excel_reasignaciones
from wm.loader import load_dataset
from wm.store import Store


@pytest.fixture
def store(test_dsn) -> Store:
    s = Store(test_dsn)
    s.migrate()
    with psycopg.connect(test_dsn) as c:
        c.execute("TRUNCATE asignacion_cliente, portafolio_cliente, portafolio_cliente_item RESTART IDENTITY CASCADE")
    return s


def test_reasignar_deja_una_vigente_y_conserva_el_historial(store):
    store.reasignar("R1", "IA_2", "MD", "balance de carga", "IA_1")
    store.reasignar("R1", "IA_3", "MD", "", "IA_1")
    v = store.asignaciones_vigentes()
    assert list(v["advisor"]) == ["IA_3"] and v["advisor_excel"].iloc[0] == "IA_1" and v["cambiado_por"].iloc[0] == "MD"
    h = store.historial_asignaciones("R1")
    assert [(r.advisor, r.vigente) for r in h.itertuples()] == [("IA_3", True), ("IA_2", False)] and h["motivo"].iloc[1] == "balance de carga"
    assert store.historial_asignaciones("OTRO").empty and len(store.historial_asignaciones()) == 2


def test_aplicar_asignaciones_cambia_el_advisor_y_marca_lo_pendiente():
    ds = load_dataset()
    rut = ds.clientes["rut"].iloc[0]
    actual = ds.clientes.loc[ds.clientes["rut"] == rut, "advisor"].iloc[0]
    otro = next(a for a in ds.clientes["advisor"].dropna().unique() if a != actual)
    vig = pd.DataFrame({"rut": [rut, "NO_EXISTE"], "advisor": [otro, "IA_X"], "advisor_excel": [actual, actual]})
    n = aplicar_asignaciones(ds, vig).clientes.set_index("rut")
    fila = n.loc[[rut]].iloc[0]
    assert fila["advisor"] == otro and fila["advisor_excel"] == actual and bool(fila["asignacion_pendiente"]) and "NO_EXISTE" not in n.index
    sin = aplicar_asignaciones(ds, vig.iloc[0:0])
    assert sin is ds
    igual = aplicar_asignaciones(ds, pd.DataFrame({"rut": [rut], "advisor": [actual], "advisor_excel": [actual]})).clientes.set_index("rut").loc[[rut]].iloc[0]
    assert not bool(igual["asignacion_pendiente"])


def test_cambios_distingue_pendiente_de_reflejada_y_el_excel_trae_solo_los_pendientes():
    view = pd.DataFrame({"rut": ["A", "B"], "cliente_label": ["A x", "B y"], "advisor_excel": ["IA_1", "IA_2"], "advisor": ["IA_9", "IA_2"]})
    vig = pd.DataFrame({"rut": ["A", "B"], "advisor": ["IA_9", "IA_2"], "advisor_excel": ["IA_1", "IA_1"], "cambiado_por": ["MD", "MD"],
                        "motivo": ["m", ""], "creado_en": [datetime(2026, 10, 29, 10), datetime(2026, 10, 28, 9)]})
    c = cambios(view, vig, lambda x: f"N-{x}")
    assert dict(zip(c["RUT"], c["Estado"])) == {"A": PENDIENTE, "B": REFLEJADA} and c.iloc[0]["Advisor nuevo"] == "N-IA_9" and c.iloc[0]["Advisor en el Excel"] == "N-IA_1"
    x = pd.read_excel(__import__("io").BytesIO(excel_reasignaciones(c)), sheet_name=None)
    assert list(x["Pendientes"]["RUT"]) == ["A"] and len(x["Historial"]) == 2
    assert cambios(view, vig.iloc[0:0], str).empty


@pytest.fixture(autouse=True)
def _limpio(test_dsn, monkeypatch):
    Store(test_dsn).migrate()
    with psycopg.connect(test_dsn) as c:
        c.execute("TRUNCATE asignacion_cliente, portafolio_cliente, portafolio_cliente_item RESTART IDENTITY CASCADE")


def test_el_md_reasigna_desde_la_ficha_y_el_cliente_cambia_de_advisor():
    at, rut = _abrir("Managing Director")
    antes = at.session_state["cliente_sel"]
    at.selectbox(key=f"asig_{rut}_nuevo").select_index(0)
    at.text_input(key=f"asig_{rut}_motivo").input("prueba")
    next(b for b in at.button if b.key == f"asig_{rut}_btn").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Cliente reasignado a" in _html(at)
    assert at.selectbox(key="cliente_sel").value == antes


def test_un_advisor_no_ve_el_control_de_reasignar():
    at, rut = _abrir()
    assert not [e for e in at.get("expander") if "Reasignar cliente" in str(getattr(e, "label", ""))]


def test_la_pagina_del_md_lista_las_reasignaciones_y_ofrece_el_excel(test_dsn):
    at, rut = _abrir("Managing Director")
    sel = at.selectbox(key=f"asig_{rut}_nuevo")
    sel.select_index(0)
    next(b for b in at.button if b.key == f"asig_{rut}_btn").click().run()
    at.sidebar.radio(key="nav").set_value("Resumen del equipo").run()
    assert not at.exception, [e.value for e in at.exception]
    h = _html(at)
    assert "Reasignaciones de clientes" in h and "1 pendiente(s) en el Excel" in h
    assert [b for b in at.get("download_button") if "Descargar para actualizar el Excel" in str(getattr(b, "proto", ""))]
