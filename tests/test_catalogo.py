from datetime import date

import pandas as pd
import pytest

from wm.catalogo import (
    CARTERAS_COLS, NUMERICAS, a_carteras, clave, columnas, desde_carteras, leer_catalogo, modelos_desde_carteras, plantilla, resolver_ids, validar,
)
from wm.config import load_config
from wm.loader import load_dataset

CFG = load_config("catalogo")


def _fila(**kw):
    base = {c: pd.NA for c in columnas()}
    base.update({"instrument_id": "A1", "nombre": "Fondo A1", "diccionario": "Fondo A1", "isin": "CL0000000001", "clase": "Renta variable", "tipo": "Fondo mutuo local",
                 "activo": True, "comision": 0.01, "pct_rf_local": 0.0, "pct_rf_high_yield_internacional": 0.0, "pct_rf_investment_grade": 0.0,
                 "pct_renta_variable": 1.0, "pct_alternativos": 0.0, "pct_moneda_usd": 0.0, "pct_moneda_clp": 1.0, "pct_moneda_uf": 0.0, "pct_moneda_otras": 0.0})
    base.update(kw)
    return base


def _cat(*filas):
    return pd.DataFrame(list(filas) or [_fila()])[columnas()]


def _msgs(issues, nivel=None):
    return [i.message for i in issues if nivel is None or i.level == nivel]


@pytest.fixture(scope="module")
def carteras() -> pd.DataFrame:
    return load_dataset().carteras


def test_el_catalogo_derivado_tiene_un_instrumento_por_isin_con_clase_valida(carteras):
    cat, _ = desde_carteras(carteras)
    assert len(cat) == carteras["isin"].nunique() and cat["instrument_id"].is_unique and (cat["instrument_id"] == cat["isin"]).all()
    assert set(cat["clase"]) <= set(CFG["clases"]) and set(cat["tipo"]) <= set(CFG["tipos"]) and cat["activo"].all()
    assert list(cat.columns) == columnas()
    acciones = cat[cat["nombre"].str.contains("S&P 500", na=False)].iloc[0]
    assert acciones["clase"] == "Renta variable" and acciones["region"] == "USA" and acciones["tipo"] == "ETF"


def test_ida_y_vuelta_sobre_la_hoja_de_carteras_no_pierde_nada_salvo_los_conflictos_informados(carteras):
    cat, conflictos = desde_carteras(carteras)
    vuelta = a_carteras(cat, modelos_desde_carteras(carteras))
    assert list(vuelta.columns) == CARTERAS_COLS and len(vuelta) == len(carteras)
    clave_modelo = ["arquitectura", "perfil", "perfil_norm", "isin", "peso_objetivo"]
    pd.testing.assert_frame_equal(vuelta[clave_modelo].reset_index(drop=True), carteras[clave_modelo].reset_index(drop=True), check_dtype=False)
    limpios = ~carteras["isin"].isin(set(conflictos["instrument_id"]))
    antes = carteras.loc[limpios, CARTERAS_COLS].reset_index(drop=True)
    despues = vuelta.loc[limpios.values, CARTERAS_COLS].reset_index(drop=True)
    for col in NUMERICAS:   # «n.a.» de la hoja pasa a vacío en el catálogo
        antes[col], despues[col] = pd.to_numeric(antes[col], errors="coerce"), pd.to_numeric(despues[col], errors="coerce")
    texto = [c for c in CARTERAS_COLS if c not in NUMERICAS]
    pd.testing.assert_frame_equal(antes[NUMERICAS + ["peso_objetivo"]], despues[NUMERICAS + ["peso_objetivo"]], check_dtype=False)
    assert (antes[texto].astype(object).fillna("∅").astype(str) == despues[texto].astype(object).fillna("∅").astype(str)).all().all()   # vacío es vacío, sea NaN o NA
    assert len(conflictos) > 0 and set(conflictos.columns) == {"instrument_id", "campo", "valores"}   # el dummy trae variantes de comisión y serie bajo un mismo ISIN


def test_un_instrumento_del_modelo_que_no_esta_en_el_catalogo_sale_vacio_pero_no_se_pierde():
    modelos = pd.DataFrame({"arquitectura": ["x"], "perfil": ["p"], "perfil_norm": ["P"], "instrument_id": ["NOESTA"], "peso_objetivo": [1.0]})
    out = a_carteras(_cat(), modelos)
    assert len(out) == 1 and out.loc[0, "isin"] == "NOESTA" and pd.isna(out.loc[0, "comision"])


def test_la_plantilla_se_lee_sin_errores_y_trae_instrumentos_y_alias():
    import io
    ruta = io.BytesIO(plantilla())
    cat = leer_catalogo(ruta)
    assert len(cat.instrumentos) == 3 and list(cat.alias["valor"]) == ["FICTUSA.SN"]
    assert not _msgs(cat.issues, "error"), cat.issues
    assert cat.instrumentos.set_index("instrument_id").loc["FICT-RF-UF", "pct_uf"] == pytest.approx(0.8)


@pytest.mark.parametrize("cambio,texto", [
    ({"clase": "Cripto"}, "la clase «Cripto» no es válida"),
    ({"pct_renta_variable": 0.7}, "no suman 100%"),
    ({"pct_rv_usa": 0.5, "pct_rv_chile": 0.1}, "categorías de renta variable no suman"),
    ({"pct_moneda_clp": 0.5}, "la exposición de moneda no suma 100%"),
    ({"pct_uf": 0.5, "pct_rf_local": 0.0}, "UF mayor que la renta fija local"),
])
def test_validar_detecta_los_errores_del_desglose_con_la_fila(cambio, texto):
    mensajes = _msgs(validar(_cat(_fila(**cambio)), None, CFG), "error")
    assert any(texto in m for m in mensajes) and any("fila 2" in m for m in mensajes)


def test_validar_avisa_sin_bloquear_lo_dudoso():
    cat = _cat(_fila(comision=1.5, pct_rv_usa=1.2, tipo="Raro", fecha_dato=pd.Timestamp("2026-01-01")))
    avisos = _msgs(validar(cat, None, CFG, hoy=date(2026, 10, 27)), "warning")
    assert any("comisión" in m for m in avisos) and any("mayores que 1" in m for m in avisos) and any("tipo «Raro»" in m for m in avisos) and any("más de 120 días" in m for m in avisos)


def test_validar_exige_ids_unicos_y_alias_sin_ambiguedad():
    cat = _cat(_fila(), _fila(nombre="Otro", isin="CL0000000002"))
    assert any("«A1» está repetido (filas 2, 3)" in m for m in _msgs(validar(cat, None, CFG), "error"))
    cat = _cat(_fila(), _fila(instrument_id="B2", nombre="B", isin="CL0000000002"))
    alias = pd.DataFrame({"tipo_id": ["nemo", "nemo", "nemo"], "valor": ["xx", "XX ", "zz"], "instrument_id": ["A1", "B2", "NOEXISTE"]})
    m = _msgs(validar(cat, alias, CFG), "error")
    assert any("«XX» apunta a más de un instrumento" in x for x in m) and any("«zz» apunta a un instrumento que no está" in x for x in m)


def test_el_mismo_isin_en_dos_instrumentos_se_avisa_pero_sin_isin_propio_no():
    cat = _cat(_fila(instrument_id="A", isin="CL0000000001"), _fila(instrument_id="B", isin="CL0000000001"),
               _fila(instrument_id="C", isin="SIN_ISIN::x"), _fila(instrument_id="D", isin="SIN_ISIN::x"))
    avisos = _msgs(validar(cat, None, CFG), "warning")
    assert len([m for m in avisos if "más de un instrumento" in m]) == 1


def test_resolver_ids_reconoce_isin_nemo_bloomberg_y_alias_sin_distinguir_mayusculas_ni_espacios():
    cat = _cat(_fila(instrument_id="A1", isin="CL0000000001", nemotecnico="CFIMRVCHA", bloomberg="ABC CI Equity"),
               _fila(instrument_id="B2", nombre="B", isin="CL0000000002", nemotecnico="n.a.", bloomberg=pd.NA))
    alias = pd.DataFrame({"tipo_id": ["run_serie"], "valor": ["9999-1 A"], "instrument_id": ["B2"]})
    ids = pd.Series(["cl0000000001", " CFIMRVCHA", "abc  ci equity", "9999-1  a", "B2", "n.a.", "NO EXISTE", None, "Fondo A1 parecido"])
    r = resolver_ids(ids, cat, alias)
    assert list(r["instrument_id"].fillna("-")) == ["A1", "A1", "A1", "B2", "B2", "-", "-", "-", "-"]
    assert list(r["via"].fillna("-")) == ["isin", "nemotecnico", "bloomberg", "alias", "instrument_id", "-", "-", "-", "-"]


def test_una_clave_ambigua_no_se_usa_y_nunca_se_adivina_por_parecido():
    cat = _cat(_fila(instrument_id="A1", isin="CL0000000001", nemotecnico="DUP"), _fila(instrument_id="B2", nombre="B", isin="CL0000000002", nemotecnico="dup"))
    r = resolver_ids(pd.Series(["DUP", "CL000000000"]), cat)
    assert r["instrument_id"].isna().all()


def test_leer_catalogo_rechaza_archivos_malos(tmp_path):
    (tmp_path / "x.xlsx").write_bytes(b"no soy un excel")
    with pytest.raises(ValueError, match="No se pudo abrir"):
        leer_catalogo(tmp_path / "x.xlsx")
    pd.DataFrame({"a": [1]}).to_excel(tmp_path / "y.xlsx", sheet_name="Otra", index=False)
    with pytest.raises(ValueError, match="no tiene la hoja «Instrumentos»"):
        leer_catalogo(tmp_path / "y.xlsx")


def test_leer_catalogo_acepta_encabezados_con_tildes_y_numeros_con_coma(tmp_path):
    pd.DataFrame({"Instrument ID": ["Z1"], "Nombre": ["Fondo Z"], "Clase": ["Renta fija"], "Comisión": ["0,95%"], "Duración": ["2,5"], "Activo": ["sí"]}).to_excel(
        tmp_path / "c.xlsx", sheet_name="Instrumentos", index=False)
    c = leer_catalogo(tmp_path / "c.xlsx").instrumentos.iloc[0]
    assert c["instrument_id"] == "Z1" and c["comision"] == pytest.approx(0.95) and c["duracion"] == 2.5 and bool(c["activo"]) is True


def test_clave_ignora_mayusculas_y_espacios():
    assert clave("  abc   def ") == "ABC DEF"


def test_el_script_escribe_la_plantilla_y_el_catalogo_derivado(tmp_path, capsys):
    from scripts.crear_plantilla_catalogo import main
    assert main([str(tmp_path / "P.xlsx")]) == 0 and "ficticios" in capsys.readouterr().out
    assert len(leer_catalogo(tmp_path / "P.xlsx").instrumentos) == 3
    assert main(["--desde-excel", str(tmp_path / "D.xlsx")]) == 0 and "con datos distintos" in capsys.readouterr().out
    hojas = pd.read_excel(tmp_path / "D.xlsx", sheet_name=None)
    assert set(hojas) == {"Instrumentos", "Alias", "Conflictos"} 
    errores = _msgs(leer_catalogo(tmp_path / "D.xlsx").issues, "error")
    assert all("UF mayor que la renta fija local" in m for m in errores)    # hallazgo ya conocido del dummy (wm/quality.py lo informa igual)
