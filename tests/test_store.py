import threading

import psycopg
import pytest

from wm.store import Store, StoreUnavailable


@pytest.fixture
def store(test_dsn) -> Store:
    s = Store(test_dsn)
    s.migrate()
    with psycopg.connect(test_dsn) as c:
        c.execute("TRUNCATE comentarios_cliente, datos_cliente, feedback RESTART IDENTITY")
    return s


def test_migrate_is_idempotent(store):
    store.migrate()
    store.migrate()
    assert store.available() is True


def test_comment_roundtrip_preserves_author_and_order(store):
    store.add_comment("R1", "IA_1", "primero")
    store.add_comment("R1", "IA_2", "segundo")
    store.add_comment("R2", "IA_1", "otro cliente")
    got = store.list_comments("R1")
    assert [(c["advisor"], c["texto"]) for c in got] == [("IA_1", "primero"), ("IA_2", "segundo")]
    assert got[0]["creado_en"] is not None


def test_set_dato_keeps_history_and_get_returns_latest(store):
    store.set_dato("R1", "share_of_wallet", "30", "IA_1")
    store.set_dato("R1", "share_of_wallet", "45", "IA_1")
    store.set_dato("R1", "wealth_plan", "si", "IA_2")
    datos = store.get_datos("R1")
    assert datos["share_of_wallet"]["valor"] == "45"
    assert datos["wealth_plan"]["advisor"] == "IA_2"
    assert [h["valor"] for h in store.dato_history("R1", "share_of_wallet")] == ["30", "45"]


def test_feedback_roundtrip(store):
    store.add_feedback("IA_1", "Home", "Falta un dato", "Quiero ver el segundo apellido", "alta")
    (fb,) = store.list_feedback()
    assert fb["pagina"] == "Home" and fb["importancia"] == "alta" and fb["advisor"] == "IA_1"


def test_concurrent_comments_from_two_threads_all_persisted(store):
    def worker(name: str):
        for i in range(20):
            store.add_comment("R1", name, f"{name}-{i}")

    threads = [threading.Thread(target=worker, args=(n,)) for n in ("IA_1", "IA_2")]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(store.list_comments("R1")) == 40


def test_store_unavailable_with_bad_dsn_returns_false_and_methods_raise():
    s = Store("postgresql://localhost:1/none?connect_timeout=1")
    assert s.available() is False
    with pytest.raises(StoreUnavailable):
        s.add_comment("R1", "IA_1", "x")
    with pytest.raises(StoreUnavailable):
        s.list_comments("R1")


def test_latest_by_campo_returns_latest_per_client(store):
    store.set_dato("R1", "proxima_accion", "llamar", "IA_1")
    store.set_dato("R1", "proxima_accion", "reunión", "IA_1")
    store.set_dato("R2", "proxima_accion", "enviar plan", "IA_2")
    store.set_dato("R2", "otro", "x", "IA_2")
    got = store.latest_by_campo("proxima_accion")
    assert {k: v["valor"] for k, v in got.items()} == {"R1": "reunión", "R2": "enviar plan"}
