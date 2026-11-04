from pathlib import Path

import pandas as pd
import psycopg
import pytest
from streamlit.testing.v1 import AppTest

from wm.catalogo import desde_carteras
from wm.loader import load_dataset
from wm.portafolio_cliente import item_desde_catalogo

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app_v4_final.py")
DS = load_dataset(ROOT / "data" / "Engine WM Dummy Completo.xlsx")
CAT, _ = desde_carteras(DS.carteras)
RV = CAT[CAT["clase"] == "Renta variable"]["instrument_id"].iloc[0]
RF = CAT[CAT["clase"] == "Renta fija"]["instrument_id"].iloc[0]


@pytest.fixture(autouse=True)
def env(monkeypatch, test_dsn):
    monkeypatch.setenv("WM_EXCEL", str(ROOT / "data" / "Engine WM Dummy Completo.xlsx"))
    monkeypatch.setenv("WM_DSN", test_dsn)
    with psycopg.connect(test_dsn) as c:
        c.execute("TRUNCATE portafolio_cliente, portafolio_cliente_item RESTART IDENTITY CASCADE")


def _abrir(role="Investment Advisor") -> tuple[AppTest, str]:
    at = AppTest.from_file(APP, default_timeout=120).run()
    if role != "Investment Advisor":
        at.sidebar.selectbox(key="role").set_value(role).run()
    at.sidebar.radio(key="nav").set_value("Ficha del cliente").run()
    assert not at.exception, [e.value for e in at.exception]
    return at, at.selectbox(key="cliente_sel").value


def _html(at):
    """Todo el texto de la página: markdown y también los mensajes (éxito, error, aviso, info)."""
    return " ".join(e.value for e in [*at.markdown, *at.success, *at.error, *at.warning, *at.info])


def _poner(at, rut, **pesos):
    items = pd.DataFrame([item_desde_catalogo(CAT, k, v) for k, v in pesos.items()])
    at.session_state[f"pf_base_{rut}"] = items
    at.session_state[f"pf_ver_{rut}"] = at.session_state[f"pf_ver_{rut}"] + 1
    return at.run()


def _boton(at, etiqueta):
    return next(b for b in at.button if b.label == etiqueta)


def test_la_ficha_trae_la_pestana_portafolio_con_lo_que_tiene_hoy_y_un_borrador(monkeypatch):
    at, rut = _abrir()
    assert [t.label for t in at.tabs][:2] == ["Resumen", "Portafolio"]
    h = _html(at)
    assert "Portafolio objetivo" in h and "Lo que tiene hoy" in h and "Sin portafolio guardado: esto es un borrador" in h and "Punto de partida" in h
    assert "Diferencia entre lo que tiene hoy y el objetivo" in h and not at.exception


def test_guardar_crea_la_version_1_vigente_y_queda_en_memoria_al_volver(monkeypatch):
    at, rut = _abrir()
    at = _poner(at, rut, **{RV: 60.0, RF: 40.0})
    assert not _boton(at, "Guardar versión").disabled
    at.text_area(key=f"pf_nota{at.session_state[f'pf_ver_{rut}']}_{rut}").set_value("Cliente quiere más renta variable").run()
    _boton(at, "Guardar versión").click().run()
    assert "Guardado como versión 1; ya es la vigente." in _html(at) and not at.exception
    from wm.store import Store
    import os
    p = Store(os.environ["WM_DSN"]).portafolio_vigente(rut)
    assert p["version"] == 1 and p["nota"] == "Cliente quiere más renta variable" and p["origen"] == "hoy" and list(p["items"]["instrument_id"]) == [RV, RF]
    otra, _ = _abrir()
    otra.session_state["cliente_sel"] = rut          # otra sesión, el mismo cliente
    otra.run()
    assert "Vigente: v1" in _html(otra) and "borrador" not in _html(otra)


def test_el_portafolio_guardado_pasa_a_ser_la_arquitectura_del_cliente_en_toda_la_app(monkeypatch):
    at, rut = _abrir()
    at = _poner(at, rut, **{RV: 60.0, RF: 40.0})
    _boton(at, "Guardar versión").click().run()
    h = _html(at)
    assert "Arquitectura declarada: Personalizada" in h and "(Personalizada, Personalizado)" in h and not at.exception
    at.sidebar.radio(key="nav").set_value("Alineación al modelo").run()
    assert not at.exception, [e.value for e in at.exception]
    otro = AppTest.from_file(APP, default_timeout=120).run()
    otro.sidebar.radio(key="nav").set_value("Home").run()
    assert not otro.exception and "Personalizada" in " ".join(m.value for m in otro.markdown)


def test_clientes_home_y_resumen_del_equipo_muestran_quien_tiene_portafolio(monkeypatch):
    at, rut = _abrir()
    at = _poner(at, rut, **{RV: 60.0, RF: 40.0})
    _boton(at, "Guardar versión").click().run()
    at.sidebar.radio(key="nav").set_value("Clientes").run()
    assert not at.exception and "Definido v1" in _html(at) and "Sin definir" in _html(at)
    antes = next(m.value for m in at.markdown if "<th" in m.value).count("<tr>")
    at.checkbox(key="f_pf_pendiente").set_value(True).run()
    despues = next(m.value for m in at.markdown if "<th" in m.value).count("<tr>")
    assert despues == antes - 1 and "Definido v1" not in _html(at)
    at.sidebar.radio(key="nav").set_value("Home").run()
    assert "Con portafolio definido" in _html(at)
    md = AppTest.from_file(APP, default_timeout=120).run()
    md.sidebar.selectbox(key="role").set_value("Managing Director").run()
    assert not md.exception and "Con portafolio definido" in _html(md) and "Portafolio por definir o revisar" in _html(md)


def test_los_errores_de_integridad_bloquean_el_guardado_y_los_avisos_no(monkeypatch):
    at, rut = _abrir()
    at = _poner(at, rut, **{RV: 60.0, RF: 30.0})
    assert _boton(at, "Guardar versión").disabled
    assert "Los pesos suman 90.00%, deben sumar 100%." in " ".join(e.value for e in at.error)
    at = _poner(at, rut, **{RV: 100.0})            # todo en renta variable: fuera de banda para casi cualquier perfil, pero solo es un aviso
    assert not _boton(at, "Guardar versión").disabled


def test_normalizar_lleva_los_pesos_a_100(monkeypatch):
    at, rut = _abrir()
    at = _poner(at, rut, **{RV: 60.0, RF: 30.0})
    _boton(at, "Normalizar a 100%").click().run()
    assert list(at.session_state[f"pf_base_{rut}"]["peso"]) == [66.67, 33.33] and not _boton(at, "Guardar versión").disabled


def test_agregar_un_instrumento_de_la_lista_le_da_lo_que_falta_para_100(monkeypatch):
    at, rut = _abrir()
    at = _poner(at, rut, **{RV: 70.0})
    sel = next(s for s in at.selectbox if s.label == "Agregar instrumento")
    sel.set_value(RF).run()
    _boton(at, "Agregar").click().run()
    base = at.session_state[f"pf_base_{rut}"].set_index("instrument_id")
    assert list(base.index) == [RV, RF] and base.loc[RF, "peso"] == 30.0


def test_partir_de_un_modelo_de_la_casa_carga_sus_instrumentos(monkeypatch):
    at, rut = _abrir()
    next(s for s in at.selectbox if s.label == "Partir de").set_value("Un modelo de la casa").run()
    _boton(at, "Cargar").click().run()
    base = at.session_state[f"pf_base_{rut}"]
    assert len(base) > 0 and round(base["peso"].sum(), 6) == 100.0 and at.session_state[f"pf_origen_{rut}"].startswith("modelo:")


def test_si_otro_advisor_guardo_mientras_editabas_se_avisa_y_no_se_escribe(monkeypatch):
    import os
    from wm.store import Store
    at, rut = _abrir()
    at = _poner(at, rut, **{RV: 60.0, RF: 40.0})
    Store(os.environ["WM_DSN"]).guardar_portafolio(rut, pd.DataFrame([item_desde_catalogo(CAT, RV, 100.0)]), "OTRO", "mientras tanto", version_base=0)
    _boton(at, "Guardar versión").click().run()
    assert "Otro advisor guardó la versión 1" in " ".join(e.value for e in at.error)
    assert [h["version"] for h in Store(os.environ["WM_DSN"]).historial_portafolio(rut)] == [1]


def test_el_historial_lista_las_versiones_y_las_compara(monkeypatch):
    at, rut = _abrir()
    for pesos in ({RV: 60.0, RF: 40.0}, {RV: 50.0, RF: 50.0}):
        at = _poner(at, rut, **pesos)
        _boton(at, "Guardar versión").click().run()
    h = _html(at)
    assert "v2 (vigente)" in h and "v1" in h and "Diferencia (pp)" in h and "cambió" in h


def test_solo_el_advisor_asignado_puede_editar_y_el_md_solo_la_ve():
    from wm.auth import can_edit_portafolio
    assert can_edit_portafolio("IA_1", "IA_1", "Investment Advisor") and not can_edit_portafolio("IA_1", "IA_2", "Investment Advisor")
    assert not can_edit_portafolio("IA_1", "IA_1", "Managing Director") and not can_edit_portafolio(None, None, "Investment Advisor")
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.sidebar.selectbox(key="role").set_value("Managing Director").run()
    assert "Ficha del cliente" in at.sidebar.radio(key="nav").options         # el MD ve todo el negocio


def test_sin_base_de_datos_la_pestana_avisa_y_no_deja_editar(monkeypatch):
    monkeypatch.setenv("WM_DSN", "postgresql://localhost:1/none?connect_timeout=1")
    at, rut = _abrir()
    assert "Base de datos no disponible: no se puede guardar ni leer el portafolio vigente" in " ".join(w.value for w in at.warning)
    assert not [b for b in at.button if b.label == "Guardar versión"]


def test_ofrece_el_excel_para_la_reunion_y_los_avisos_del_cambio(monkeypatch):
    at, rut = _abrir()
    at = _poner(at, rut, **{RV: 60.0, RF: 40.0})
    descargas = [b for b in at.get("download_button") if "Excel para la reunión" in str(getattr(b, "proto", ""))]
    assert descargas and not _boton(at, "Guardar versión").disabled
    assert not at.exception


def test_clientes_ya_no_ofrece_la_carga_masiva():
    at, _ = _abrir()
    at.sidebar.radio(key="nav").set_value("Clientes").run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Cargar portafolios desde Excel" not in str(at.get("expander"))


def test_el_selector_de_instrumentos_va_en_orden_alfabetico():
    at, rut = _abrir()
    sel = next(x for x in at.selectbox if x.label == "Agregar instrumento")
    nombres = [o.split(" · ")[0].casefold() for o in sel.options]
    assert nombres == sorted(nombres) and len(nombres) > 5


def test_el_md_abre_la_ficha_en_solo_lectura():
    at, rut = _abrir("Managing Director")
    assert "Solo el advisor asignado" in _html(at) and not [b for b in at.button if b.label == "Guardar versión" and not b.disabled] and not at.exception
