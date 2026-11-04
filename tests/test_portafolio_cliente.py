from datetime import date, datetime

import pandas as pd
import pytest

from tests.test_catalogo import _cat, _fila
from wm.catalogo import CARTERAS_COLS, desde_carteras
from wm.loader import load_dataset
from wm.portafolio_cliente import (
    EXTERNO, ITEM_COLS, a_filas_carteras, avisos_consolidar, avisos_desvio, desvio_absoluto, ajuste, comision_ponderada, comparar_versiones, desactualizado, desde_modelo, desde_posiciones, es_externo,
    fuera_de_banda, hay_errores, item_desde_catalogo, normalizar, reconocer_posiciones, resumir, validar, vacio,
)

RV = dict(clase="Renta variable", pct_renta_variable=1.0, pct_rf_local=0.0, pct_alternativos=0.0, pct_rv_usa=1.0, pct_moneda_usd=1.0, pct_moneda_clp=0.0)
RF = dict(clase="Renta fija", pct_renta_variable=0.0, pct_rf_local=1.0, pct_alternativos=0.0, pct_moneda_clp=0.2, pct_moneda_uf=0.8, pct_moneda_usd=0.0)


@pytest.fixture
def cat() -> pd.DataFrame:
    return _cat(_fila(instrument_id="RV1", nombre="Acciones USA", diccionario="Acciones USA", isin="CL0000000001", serie="B", comision=0.012, **RV),
                _fila(instrument_id="RF1", nombre="Deuda UF", diccionario="Deuda UF", isin="CL0000000002", serie="A", comision=0.006, **RF),
                _fila(instrument_id="SD1", nombre="Sin desglose", diccionario="Sin desglose", isin="CL0000000003", clase="Otro", comision=0.01,
                      **{c: pd.NA for c in RV if c != "clase"}),
                _fila(instrument_id="OFF", nombre="Retirado", diccionario="Retirado", isin="CL0000000004", activo=False, **RV))


def _items(cat, **pesos):
    return pd.DataFrame([item_desde_catalogo(cat, k, v) for k, v in pesos.items()])


def _msgs(issues, nivel):
    return [i.message for i in issues if i.level == nivel]


def test_normalizar_suma_exactamente_100_y_manda_el_redondeo_al_mayor(cat):
    n = normalizar(_items(cat, RV1=1, RF1=1, SD1=1))
    assert list(n["peso"]) == [33.34, 33.33, 33.33] and round(n["peso"].sum(), 6) == 100.0
    assert normalizar(_items(cat, RV1=0, RF1=0))["peso"].sum() == 0 and normalizar(vacio()).empty


def test_validar_bloquea_solo_los_errores_de_integridad(cat):
    assert _msgs(validar(vacio(), cat), "error") == ["El portafolio no tiene instrumentos."]
    assert any("suman 90.00%" in m for m in _msgs(validar(_items(cat, RV1=50, RF1=40), cat), "error"))
    dup = pd.concat([_items(cat, RV1=50), _items(cat, RV1=50)])
    assert any("aparece más de una vez" in m for m in _msgs(validar(dup, cat), "error"))
    assert any("no puede ser vacío ni negativo" in m for m in _msgs(validar(_items(cat, RV1=-5, RF1=105), cat), "error"))
    fuera = pd.concat([_items(cat, RV1=50), pd.DataFrame([{"instrument_id": "NOEXISTE", "isin": "X", "nombre": "Fantasma", "serie": None, "peso": 50.0, "comision": None}])])
    assert any("Fantasma: no está en la lista" in m for m in _msgs(validar(fuera, cat), "error"))
    ok = _items(cat, RV1=60, RF1=40)
    assert not hay_errores(validar(ok, cat))


def test_validar_avisa_sin_bloquear_externos_inactivos_residuales_y_exceso_de_lineas(cat):
    ext = pd.DataFrame([{"instrument_id": EXTERNO + "ZZ", "isin": "ZZ", "nombre": "Fondo ajeno", "serie": None, "peso": 5.0, "comision": None}])
    it = pd.concat([_items(cat, RV1=60, RF1=34.7, OFF=0.3), ext], ignore_index=True)
    issues = validar(it, cat)
    assert not hay_errores(issues)
    avisos = _msgs(issues, "warning")
    assert any("Fondo ajeno: no está en la lista" in m for m in avisos) and any("Retirado: el instrumento está inactivo" in m for m in avisos)
    assert any("Retirado: posición residual (0.30%)" in m for m in avisos)
    muchos = pd.DataFrame([{"instrument_id": f"I{k}", "isin": f"I{k}", "nombre": f"I{k}", "serie": None, "peso": 4.0, "comision": None} for k in range(26)])
    cat2 = _cat(*[_fila(instrument_id=f"I{k}", nombre=f"I{k}", isin=f"CL{k:010d}") for k in range(26)])
    assert any("26 instrumentos" in m for m in _msgs(validar(muchos, cat2, {**__import__("wm.portafolio_cliente", fromlist=["cfg"]).cfg(), "tolerancia_suma_pp": 5}), "warning"))


def test_desde_posiciones_reconoce_y_deja_lo_externo_a_la_vista(cat):
    pos = pd.DataFrame({"rut": ["R"] * 4, "instrumento": ["a", "b", "c", "d"], "isin": ["cl0000000001", "CL0000000002", "CL0000000001", "ZZ0000000009"],
                        "valor_clp": [300.0, 400.0, 100.0, 200.0]})
    h = desde_posiciones(pos, cat)
    por = h.set_index("instrument_id")["peso"]
    assert por["RV1"] == 40.0 and por["RF1"] == 40.0 and por[EXTERNO + "ZZ0000000009"] == 20.0 and round(h["peso"].sum(), 6) == 100.0
    assert h.set_index("instrument_id").loc[EXTERNO + "ZZ0000000009", "nombre"] == "d" and list(h.columns) == ITEM_COLS
    assert desde_posiciones(pos.iloc[0:0], cat).empty
    r = reconocer_posiciones(pos, cat)
    assert list(r["instrument_id"].fillna("-")) == ["RV1", "RF1", "RV1", "-"] and list(r["via"].fillna("-")) == ["isin", "isin", "isin", "-"]


def test_desde_modelo_toma_los_pesos_del_modelo_de_la_casa():
    ds = load_dataset()
    cat, _ = desde_carteras(ds.carteras)
    arq, perfil = ds.carteras.iloc[0][["arquitectura", "perfil"]]
    it = desde_modelo(ds.carteras, arq, perfil, cat)
    assert not it.empty and round(it["peso"].sum(), 6) == 100.0 and not hay_errores(validar(it, cat)) and it["instrument_id"].is_unique
    assert desde_modelo(ds.carteras, "no_existe", "x", cat).empty


def test_resumir_mide_la_exposicion_el_riesgo_la_comision_y_lo_que_no_tiene_desglose(cat):
    r = resumir(_items(cat, RV1=50, RF1=30, SD1=20), cat)
    assert r.n == 3 and r.cobertura == pytest.approx(0.80) and r.clase["Renta Variable"] == pytest.approx(62.5) and r.clase["Renta Fija"] == pytest.approx(37.5)
    assert r.riesgo == pytest.approx(62.5) and r.sin_desglose == ["Sin desglose"] and r.moneda["UF"] == pytest.approx(30.0)
    assert r.comision == pytest.approx((50 * 0.012 + 30 * 0.006 + 20 * 0.01) / 100) and r.comision_cobertura == pytest.approx(1.0)
    assert resumir(vacio(), cat).n == 0


def test_comision_ponderada_solo_sobre_lo_que_tiene_comision():
    it = pd.DataFrame({"instrument_id": ["a", "b"], "peso": [60.0, 40.0], "comision": [0.01, pd.NA]})
    c, cob = comision_ponderada(it)
    assert c == pytest.approx(0.01) and cob == pytest.approx(0.6) and comision_ponderada(vacio()) == (None, 0.0)


def test_fuera_de_banda_avisa_sobre_y_bajo_la_banda_y_calla_en_la_banda(cat):
    r = resumir(_items(cat, RV1=65, RF1=35), cat)         # riesgo 65%
    assert any("5.0 pp sobre la banda" in m for m in _msgs(fuera_de_banda(r, "EQUILIBRADO"), "warning"))
    assert any("bajo la banda" in m for m in _msgs(fuera_de_banda(r, "CRECIMIENTO"), "warning"))
    assert fuera_de_banda(r, "CLASICO_60_40") == [] and fuera_de_banda(r, "OTRO") == [] and fuera_de_banda(resumir(vacio(), cat), "EQUILIBRADO") == []


def test_desactualizado_por_meses_o_por_cambio_de_perfil():
    assert desactualizado(datetime(2026, 1, 10), date(2026, 5, 9), "EQUILIBRADO", "EQUILIBRADO") is None
    assert "hace 6 meses" in desactualizado(datetime(2026, 1, 10), date(2026, 7, 10), "EQUILIBRADO", "EQUILIBRADO")
    assert "cambió de EQUILIBRADO a CRECIMIENTO" in desactualizado(datetime(2026, 7, 1), date(2026, 7, 2), "EQUILIBRADO", "CRECIMIENTO")
    assert desactualizado(date(2026, 7, 1), date(2026, 7, 2), None, "CRECIMIENTO") is None


def test_comparar_versiones_marca_nuevos_quitados_y_cambios(cat):
    a, b = _items(cat, RV1=60, RF1=40), _items(cat, RV1=50, SD1=50)
    c = comparar_versiones(a, b).set_index("instrument_id")
    assert c.loc["RV1", "estado"] == "cambió" and c.loc["RV1", "dif"] == -10 and c.loc["RF1", "estado"] == "quitado" and c.loc["SD1", "estado"] == "nuevo"
    assert comparar_versiones(a, a)["estado"].eq("igual").all()


def test_a_filas_carteras_tiene_el_formato_de_la_hoja_y_conserva_la_serie_y_los_externos(cat):
    ext = pd.DataFrame([{"instrument_id": EXTERNO + "ZZ", "isin": "ZZ", "nombre": "Fondo ajeno", "serie": "Z", "peso": 10.0, "comision": 0.02}])
    it = pd.concat([_items(cat, RV1=60, RF1=30), ext], ignore_index=True)
    f = a_filas_carteras(it, "personalizada:R1", "Equilibrado", "EQUILIBRADO", cat)
    assert list(f.columns) == CARTERAS_COLS and len(f) == 3 and f["peso_objetivo"].sum() == pytest.approx(1.0)
    assert set(f["arquitectura"]) == {"personalizada:R1"} and set(f["perfil_norm"]) == {"EQUILIBRADO"}
    x = f.set_index("isin")
    assert x.loc["ZZ", "diccionario"] == "Fondo ajeno" and x.loc["ZZ", "serie"] == "Z" and x.loc["ZZ", "comision"] == 0.02 and x.loc["CL0000000001", "serie"] == "B"
    cambiado = it.copy()
    cambiado.loc[0, ["serie", "comision"]] = ["Wealth", 0.003]
    y = a_filas_carteras(cambiado, "p", "x", None, cat).set_index("isin")
    assert y.loc["CL0000000001", "serie"] == "Wealth" and y.loc["CL0000000001", "comision"] == 0.003    # lo elegido por el advisor manda sobre el catálogo


def test_ajuste_dice_que_vender_y_que_comprar_con_el_rebalanceo_del_dashboard(cat):
    pos = pd.DataFrame({"rut": ["R"], "instrumento": ["Acciones USA"], "isin": ["CL0000000001"], "valor_clp": [1000.0]})
    plan = ajuste(pos, _items(cat, RV1=50, RF1=50), cat, None, "Equilibrado", "EQUILIBRADO", base_clp=1000.0).set_index("fondo")
    assert plan.loc["Acciones USA", "dif_pp"] == pytest.approx(-50) and plan.loc["Acciones USA", "ajuste_clp"] == pytest.approx(-500)
    assert plan.loc["Deuda UF", "dif_pp"] == pytest.approx(50) and plan.loc["Deuda UF", "ajuste_clp"] == pytest.approx(500)
    assert ajuste(pos, vacio(), cat, None, "Equilibrado", "EQUILIBRADO") is None


def test_si_el_objetivo_es_lo_que_tiene_hoy_el_ajuste_es_cero_con_datos_del_dummy():
    ds = load_dataset()
    cat, _ = desde_carteras(ds.carteras)
    rut = ds.posiciones["rut"].iloc[0]
    pos = ds.posiciones[ds.posiciones["rut"] == rut]
    objetivo = desde_posiciones(pos, cat)
    plan = ajuste(pos, objetivo, cat, None, "Equilibrado", "EQUILIBRADO", base_clp=float(pos["valor_clp"].sum()))
    assert plan is not None and plan["dif_pp"].abs().max() < 0.05 and es_externo(EXTERNO + "x")


def test_aplicar_edicion_cambia_pesos_y_quita_las_lineas_marcadas(cat):
    from wm.portafolio_cliente import aplicar_edicion
    base = _items(cat, RV1=50, RF1=30, SD1=20)
    out, quito = aplicar_edicion(base, [55, "30,5", 20], [False, False, False])
    assert not quito and out.loc[0, "peso"] == 55.0 and pd.isna(out.loc[1, "peso"])    # «30,5» con coma no es un número: queda vacío y la validación lo señala
    out, quito = aplicar_edicion(base, [60, 40, 0], [False, False, True])
    assert quito and list(out["instrument_id"]) == ["RV1", "RF1"] and list(out["peso"]) == [60.0, 40.0]


def test_agregar_suma_el_instrumento_con_lo_que_falta_y_no_duplica(cat):
    from wm.portafolio_cliente import agregar
    it = agregar(_items(cat, RV1=70), cat, "RF1")
    assert list(it["instrument_id"]) == ["RV1", "RF1"] and it.loc[1, "peso"] == 30.0 and it.loc[1, "serie"] == "A"
    assert agregar(it, cat, "RF1").equals(it) and agregar(_items(cat, RV1=100), cat, "RF1").loc[1, "peso"] == 0.0
    assert list(agregar(vacio(), cat, "SD1")["peso"]) == [100.0]


def test_tabla_hoy_ordena_por_valor_y_marca_lo_que_no_esta_en_la_lista(cat):
    from wm.portafolio_cliente import tabla_hoy
    pos = pd.DataFrame({"rut": ["R"] * 3, "instrumento": ["a", "b", "c"], "isin": ["CL0000000002", "CL0000000001", "ZZ"], "valor_clp": [500.0, 300.0, 200.0]})
    t = tabla_hoy(pos, cat)
    assert list(t["nombre"]) == ["Deuda UF", "Acciones USA", "c"] and list(t["en_lista"]) == [True, True, False] and list(t["peso"]) == [50.0, 30.0, 20.0]
    assert tabla_hoy(pos.iloc[0:0], cat).empty and list(tabla_hoy(pos.iloc[0:0], cat).columns) == ["instrument_id", "nombre", "serie", "valor_clp", "peso", "en_lista", "via"]


def test_avisa_si_el_fondo_tiene_otra_serie_activa_mas_barata(cat):
    from wm.portafolio_cliente import avisos_series
    c = pd.concat([cat, _cat(_fila(instrument_id="RV1-W", nombre="Acciones USA Wealth", diccionario="Acciones USA", isin="CL0000000009", serie="Wealth", comision=0.006, **RV),
                              _fila(instrument_id="RV1-X", nombre="Acciones USA X", diccionario="Acciones USA", isin="CL0000000010", serie="X", comision=0.004, activo=False, **RV))], ignore_index=True)
    a = avisos_series(_items(c, RV1=60, RF1=40), c)
    assert len(a) == 1 and "Acciones USA: la serie B cobra 1.20% y existe la serie Wealth del mismo fondo a 0.60%" in a[0].message    # la X está inactiva: no se sugiere
    assert avisos_series(_items(c, **{"RV1-W": 100}), c) == [] and avisos_series(vacio(), c) == []


def test_impuesto_estimado_de_las_ventas_es_proporcional_a_lo_que_se_vende(cat):
    from wm.portafolio_cliente import impuesto_estimado
    pos = pd.DataFrame({"rut": ["R", "R"], "instrumento": ["Acciones USA", "Deuda UF"], "isin": ["CL0000000001", "CL0000000002"], "valor_clp": [800.0, 200.0],
                        "costo_tributario_clp": [100.0, 0.0]})
    t = impuesto_estimado(pos, _items(cat, RV1=40, RF1=60), cat)       # hoy 80/20, objetivo 40/60: vende la mitad de las acciones
    assert list(t["nombre"]) == ["Acciones USA"] and t.loc[0, "fraccion_vendida"] == pytest.approx(0.5) and t.loc[0, "impuesto_clp"] == pytest.approx(50.0)
    assert impuesto_estimado(pos, _items(cat, RV1=100), cat).empty                  # no vende nada
    assert impuesto_estimado(pos.drop(columns="costo_tributario_clp"), _items(cat, RV1=40), cat).empty and impuesto_estimado(pos.iloc[0:0], _items(cat, RV1=40), cat).empty


def test_el_excel_para_la_reunion_trae_portafolio_exposicion_ajuste_y_datos(cat):
    import io
    from wm.portafolio_export import excel_reunion
    items = _items(cat, RV1=60, RF1=40)
    pos = pd.DataFrame({"rut": ["R"], "instrumento": ["Acciones USA"], "isin": ["CL0000000001"], "valor_clp": [1000.0]})
    plan = ajuste(pos, items, cat, None, "Equilibrado", "EQUILIBRADO", base_clp=1000.0)
    data = excel_reunion({"nombre": "Ana Pérez", "rut": "12.345.678-9", "perfil": "Equilibrado", "advisor": "IA_1"}, items, resumir(items, cat), resumir(items.iloc[:1].assign(peso=100.0), cat), plan,
                         "Vigente v2", "Revisar en marzo", date(2026, 10, 27))
    hojas = pd.read_excel(io.BytesIO(data), sheet_name=None)
    assert list(hojas) == ["Portafolio", "Exposición", "Ajuste", "Datos"]
    p = hojas["Portafolio"]
    assert list(p["Instrumento"]) == ["Acciones USA", "Deuda UF", "Total"] and list(p["Peso %"]) == [60.0, 40.0, 100.0] and p.loc[0, "Comisión %"] == pytest.approx(1.2)
    assert hojas["Exposición"].set_index("Clase").loc["Renta variable", "Objetivo %"] == pytest.approx(60.0) and hojas["Exposición"].set_index("Clase").loc["Renta variable", "Hoy %"] == pytest.approx(100.0)
    d = hojas["Datos"].set_index("Dato")["Valor"]
    assert d["Cliente"] == "Ana Pérez" and d["Estado"] == "Vigente v2" and d["Nota"] == "Revisar en marzo" and d["Fecha"] == "2026-10-27"
    sin_plan = pd.read_excel(io.BytesIO(excel_reunion({}, vacio(), resumir(vacio(), cat), resumir(vacio(), cat), None, "Borrador sin guardar")), sheet_name=None)
    assert list(sin_plan) == ["Portafolio", "Exposición", "Datos"]


def test_desvio_absoluto_es_la_suma_de_diferencias_por_instrumento(cat):
    hoy, obj = _items(cat, RV1=60, RF1=40), _items(cat, RV1=55, RF1=40, SD1=5)
    assert desvio_absoluto(hoy, obj, cat) == pytest.approx(10.0) and desvio_absoluto(obj, obj, cat) == 0
    assert desvio_absoluto(hoy, hoy, cat) == 0


def test_desvio_absoluto_suma_las_series_de_un_mismo_instrumento():
    c = _cat(_fila(instrument_id="A1", nombre="Fondo A", diccionario="Fondo A", isin="CL0000000001", serie="APV", **RV),
             _fila(instrument_id="A2", nombre="Fondo A", diccionario="Fondo A", isin="CL0000000002", serie="B", **RV),
             _fila(instrument_id="B1", nombre="Fondo B", diccionario="Fondo B", isin="CL0000000003", **RF))
    hoy, obj = _items(c, A1=30, A2=30, B1=40), _items(c, A1=60, B1=40)
    assert desvio_absoluto(hoy, obj, c) == pytest.approx(0.0)
    assert [i.message for i in avisos_consolidar(hoy, c)][0].startswith("Fondo A: tiene 2 series")
    assert avisos_consolidar(obj, c) == []


def test_avisa_si_el_desvio_pasa_de_3_pp_y_calla_en_el_limite(cat):
    obj = _items(cat, RV1=50, RF1=50)
    assert avisos_desvio(_items(cat, RV1=51.5, RF1=48.5), obj, cat) == []
    assert "3 pp" in avisos_desvio(_items(cat, RV1=52, RF1=48), obj, cat)[0].message
