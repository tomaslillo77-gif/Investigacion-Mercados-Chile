import threading

import pandas as pd
import psycopg
import pytest

from wm.portafolio_cliente import ITEM_COLS
from wm.store import ConflictoDeVersion, Store, StoreUnavailable


@pytest.fixture
def store(test_dsn) -> Store:
    s = Store(test_dsn)
    s.migrate()
    with psycopg.connect(test_dsn) as c:
        c.execute("TRUNCATE portafolio_cliente, portafolio_cliente_item RESTART IDENTITY CASCADE")
    return s


def _items(**pesos):
    return pd.DataFrame([{"instrument_id": k, "isin": k, "nombre": f"Fondo {k}", "serie": "A", "peso": v, "comision": 0.01} for k, v in pesos.items()], columns=ITEM_COLS)


def test_la_primera_version_queda_vigente_con_sus_items_en_orden(store):
    assert store.portafolio_vigente("R1") is None
    v = store.guardar_portafolio("R1", _items(X=60, Y=40), "IA_1", nota="inicial", origen="hoy", perfil_al_guardar="EQUILIBRADO", version_base=0)
    p = store.portafolio_vigente("R1")
    assert v == 1 and p["version"] == 1 and p["advisor"] == "IA_1" and p["nota"] == "inicial" and p["origen"] == "hoy" and p["perfil_al_guardar"] == "EQUILIBRADO" and p["vigente"]
    assert list(p["items"]["instrument_id"]) == ["X", "Y"] and list(p["items"]["peso"]) == [60.0, 40.0] and p["items"]["comision"].iloc[0] == pytest.approx(0.01)
    assert p["creado_en"] is not None


def test_cada_guardado_crea_una_version_nueva_y_la_anterior_se_conserva(store):
    store.guardar_portafolio("R1", _items(X=100), "IA_1", version_base=0)
    store.guardar_portafolio("R1", _items(X=50, Y=50), "IA_2", nota="cambio", version_base=1)
    h = store.historial_portafolio("R1")
    assert [(x["version"], x["advisor"], x["vigente"], x["n_items"]) for x in h] == [(2, "IA_2", True, 2), (1, "IA_1", False, 1)]
    assert list(store.portafolio_version("R1", 1)["items"]["instrument_id"]) == ["X"] and store.portafolio_vigente("R1")["version"] == 2
    assert store.portafolio_version("R1", 9) is None and store.historial_portafolio("OTRO") == []


def test_guardar_sobre_una_version_vieja_avisa_y_no_escribe(store):
    store.guardar_portafolio("R1", _items(X=100), "IA_1", version_base=0)
    store.guardar_portafolio("R1", _items(Y=100), "IA_2", version_base=1)
    with pytest.raises(ConflictoDeVersion) as e:
        store.guardar_portafolio("R1", _items(Z=100), "IA_1", version_base=1)
    assert e.value.version_actual == 2
    assert [x["version"] for x in store.historial_portafolio("R1")] == [2, 1] and list(store.portafolio_vigente("R1")["items"]["instrument_id"]) == ["Y"]
    with pytest.raises(ConflictoDeVersion):
        store.guardar_portafolio("R1", _items(Z=100), "IA_1", version_base=0)


def test_dos_advisors_guardando_a_la_vez_la_primera_version_uno_gana_y_el_otro_recibe_el_aviso(store):
    resultados, barrera = [], threading.Barrier(2)

    def worker(nombre):
        barrera.wait()
        try:
            resultados.append(("ok", store.guardar_portafolio("R1", _items(**{nombre: 100}), nombre, version_base=0)))
        except ConflictoDeVersion as e:
            resultados.append(("conflicto", e.version_actual))
    hilos = [threading.Thread(target=worker, args=(n,)) for n in ("IA_1", "IA_2")]
    [t.start() for t in hilos]
    [t.join() for t in hilos]
    assert sorted(r[0] for r in resultados) == ["conflicto", "ok"]
    assert len(store.historial_portafolio("R1")) == 1 and store.portafolio_vigente("R1")["vigente"]


def test_un_item_invalido_deja_todo_como_estaba(store):
    store.guardar_portafolio("R1", _items(X=100), "IA_1", version_base=0)
    malo = _items(X=50, Y=150)           # el peso máximo por línea es 100
    with pytest.raises(StoreUnavailable):
        store.guardar_portafolio("R1", malo, "IA_2", version_base=1)
    assert [x["version"] for x in store.historial_portafolio("R1")] == [1] and store.portafolio_vigente("R1")["version"] == 1


def test_la_base_garantiza_una_sola_version_vigente_por_cliente(store, test_dsn):
    store.guardar_portafolio("R1", _items(X=100), "IA_1", version_base=0)
    with psycopg.connect(test_dsn) as c, pytest.raises(psycopg.errors.UniqueViolation):
        c.execute("INSERT INTO portafolio_cliente (rut, version, advisor, vigente) VALUES ('R1', 7, 'IA_1', TRUE)")


def test_los_vigentes_de_todos_los_clientes_en_una_consulta(store):
    store.guardar_portafolio("R1", _items(X=100), "IA_1", version_base=0)
    store.guardar_portafolio("R1", _items(X=60, Y=40), "IA_1", version_base=1)
    store.guardar_portafolio("R2", _items(Z=100), "IA_2", perfil_al_guardar="CRECIMIENTO", version_base=0)
    df = store.portafolios_vigentes()
    assert sorted(df["rut"].unique()) == ["R1", "R2"] and len(df) == 3 and set(df.loc[df["rut"] == "R1", "version"]) == {2}
    r = store.resumen_portafolios_vigentes().set_index("rut")
    assert r.loc["R1", "n_items"] == 2 and r.loc["R2", "perfil_al_guardar"] == "CRECIMIENTO" and r.loc["R1", "version"] == 2
    assert store.portafolios_vigentes()["comision"].notna().all()


def test_sin_base_las_operaciones_de_portafolio_lanzan_store_unavailable():
    s = Store("postgresql://localhost:1/none?connect_timeout=1")
    for f in (lambda: s.portafolio_vigente("R1"), lambda: s.historial_portafolio("R1"), lambda: s.portafolios_vigentes(),
              lambda: s.guardar_portafolio("R1", _items(X=100), "IA_1", version_base=0)):
        with pytest.raises(StoreUnavailable):
            f()
