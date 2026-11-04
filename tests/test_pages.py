import re
import os
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data" / "Engine WM Dummy Completo.xlsx"
APP = str(ROOT / "app_v4_final.py")


@pytest.fixture(autouse=True)
def env(monkeypatch, test_dsn):
    monkeypatch.setenv("WM_EXCEL", str(SAMPLE))
    monkeypatch.setenv("WM_DSN", test_dsn)


def run(nav: str | None = None, role: str = "Investment Advisor", advisor: str | None = None,
        cliente: str | None = None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=90).run()
    assert not at.exception, at.exception
    if role != "Investment Advisor":
        at.sidebar.selectbox(key="role").set_value(role).run()
    if advisor:
        at.sidebar.selectbox(key="advisor").set_value(advisor).run()
    if cliente:
        at.session_state["cliente_sel"] = cliente
    if nav:
        at.sidebar.radio(key="nav").set_value(nav).run()
    assert not at.exception, at.exception
    return at


def test_home_renders_kpis_and_attention_queue_without_exception():
    at = run()
    html = " ".join(m.value for m in at.markdown)
    assert "Mi cartera" in html and "Cola de atención" in html


def test_home_queue_has_at_most_10_rows():
    at = run()
    queue = next(m.value for m in at.markdown if "Motivos" in m.value)
    assert queue.count("<tr>") - 1 <= 10  # sin contar la fila de encabezado


def test_clientes_filter_sin_contacto_reduces_rows():
    at = run("Clientes")
    before = next(m.value for m in at.markdown if "<th" in m.value).count("<tr>")
    at.checkbox(key="f_sin_contacto").set_value(True).run()
    assert not at.exception
    after = next((m.value for m in at.markdown if "<th" in m.value), "").count("<tr>")
    assert after < before


def test_clientes_export_csv_button_present():
    at = run("Clientes")
    assert any("Exportar CSV" in str(getattr(b, "label", "")) for b in at.get("download_button"))


def test_home_with_missing_optional_columns_shows_dash_not_error(tmp_path, monkeypatch):
    import pandas as pd
    from tests.conftest import _write
    frames = pd.read_excel(SAMPLE, sheet_name=None, header=2)
    frames["Dummy Metricas"] = frames["Dummy Metricas"].drop(
        columns=["share_of_wallet_pct", "tiene_wealth_plan", "desvio_modelo_pct"])
    p = tmp_path / "lean.xlsx"
    _write(p, frames)
    monkeypatch.setenv("WM_EXCEL", str(p))
    at = run()
    assert "dato no disponible" in " ".join(m.value for m in at.markdown)


# ------------------------------------------------------------------ ficha
NAV_FICHA = "Ficha del cliente"


@pytest.fixture(autouse=True)
def clean_db(test_dsn):
    import psycopg
    from wm.store import Store
    Store(test_dsn).migrate()
    with psycopg.connect(test_dsn) as c:
        c.execute("TRUNCATE comentarios_cliente, datos_cliente, feedback RESTART IDENTITY")


def _pick(with_positions: bool) -> tuple[str, str]:
    from datetime import date
    from wm.enrich import enrich_clientes
    from wm.loader import load_dataset
    ds = load_dataset(SAMPLE)
    view = enrich_clientes(ds, date.today()).set_index("rut")
    held = set(ds.posiciones["rut"])
    rut = next(r for r in view.index if (r in held) == with_positions)
    return rut, view.loc[rut, "advisor"]


def test_ficha_without_positions_shows_empty_state():
    rut, adv = _pick(False)
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    assert any("no tiene posiciones" in i.value for i in at.info)


def _pick_by_arch(declarada: bool) -> tuple[str, str]:
    from datetime import date
    from wm.enrich import enrich_clientes
    from wm.loader import load_dataset
    ds = load_dataset(SAMPLE)
    view = enrich_clientes(ds, date.today()).set_index("rut")
    held = set(ds.posiciones["rut"])
    rut = next(r for r in view.index if r in held and view.loc[r, "arquitectura"] is not None
               and bool(view.loc[r, "arquitectura_inferida"]) is (not declarada))
    return rut, view.loc[rut, "advisor"]


def test_ficha_shows_architecture_as_inferida_with_coverage():
    rut, adv = _pick_by_arch(declarada=False)
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    html = " ".join(m.value for m in at.markdown)
    assert "Arquitectura inferida" in html and "cobertura" in html


def test_ficha_shows_architecture_as_declarada_when_excel_has_it():
    rut, adv = _pick_by_arch(declarada=True)
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    assert "Arquitectura declarada" in " ".join(m.value for m in at.markdown)


def test_ficha_exposure_pending_without_breakdown_columns(tmp_path, monkeypatch):
    import pandas as pd
    from tests.conftest import _write
    frames = pd.read_excel(SAMPLE, sheet_name=None, header=2)
    keep = [c for c in frames["Dummy Carteras"].columns if not c.startswith(("pct_rv", "pct_rf", "pct_moneda", "pct_renta", "pct_alt"))]
    frames["Dummy Carteras"] = frames["Dummy Carteras"][keep]
    p = tmp_path / "nobreak.xlsx"
    _write(p, frames)
    monkeypatch.setenv("WM_EXCEL", str(p))
    rut, adv = _pick(True)
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    assert "Pendiente de datos" in " ".join(m.value for m in at.markdown)


def test_ficha_comment_submit_persists_to_store(test_dsn):
    from wm.store import Store
    rut, adv = _pick(True)
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    at.text_area(key=f"coment_{rut}").set_value("Llamar la próxima semana").run()
    at.button(key="coment_send").click().run()
    assert not at.exception
    (c,) = Store(test_dsn).list_comments(rut)
    assert c["advisor"] == adv and c["texto"] == "Llamar la próxima semana"


def test_ficha_dato_shows_excel_value_and_advisor_value_with_author(test_dsn):
    from wm.store import Store
    rut, adv = _pick(True)
    Store(test_dsn).set_dato(rut, "share_of_wallet", "42", adv)
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    html = " ".join(m.value for m in at.markdown)
    from datetime import date
    from wm.enrich import enrich_clientes
    from wm.loader import load_dataset
    nombre = enrich_clientes(load_dataset(SAMPLE), date.today()).set_index("advisor").loc[adv, "advisor_nombre"].iloc[0]
    assert "Excel" in html and f"ingresado por {nombre}" in html


def test_ficha_comments_disabled_with_warning_when_store_unavailable(monkeypatch):
    monkeypatch.setenv("WM_DSN", "postgresql://localhost:1/none?connect_timeout=1")
    rut, adv = _pick(True)
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    assert any("no disponible" in w.value for w in at.warning)
    assert len(at.text_area) > 0 and all(t.disabled for t in at.text_area)


def test_advisor_cannot_edit_dato_written_by_other_advisor(test_dsn):
    from wm.store import Store
    rut, adv = _pick(True)
    Store(test_dsn).set_dato(rut, "share_of_wallet", "42", "OTRO_ADVISOR")
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    assert at.number_input(key=f"dato_{rut}_share_of_wallet").disabled is True


# ------------------------------------------------------------------ alineación y seguimiento
NAV_ALINEACION = "Alineación al modelo"
NAV_SEGUIMIENTO = "Seguimiento"


def test_alineacion_renders_ranking_from_excel_desvio():
    at = run(NAV_ALINEACION)
    html = " ".join(m.value for m in at.markdown)
    assert "Desvío" in html and "Pendiente de datos" not in html


def test_alineacion_pending_without_breakdown_and_desvio(tmp_path, monkeypatch):
    import pandas as pd
    from tests.conftest import _write
    frames = pd.read_excel(SAMPLE, sheet_name=None, header=2)
    frames["Dummy Metricas"] = frames["Dummy Metricas"].drop(columns=["desvio_modelo_pct"])
    k = frames["Dummy Carteras"]
    frames["Dummy Carteras"] = k[[c for c in k.columns if not c.startswith("pct_rv") and c not in
                                  ("pct_rf_local", "pct_renta_variable", "pct_alternativos")]]
    p = tmp_path / "nodesv.xlsx"
    _write(p, frames)
    monkeypatch.setenv("WM_EXCEL", str(p))
    at = run(NAV_ALINEACION)
    assert "Pendiente de datos" in " ".join(m.value for m in at.markdown)


def _two_clients_same_advisor():
    from datetime import date
    from wm.enrich import enrich_clientes
    from wm.loader import load_dataset
    view = enrich_clientes(load_dataset(SAMPLE), date.today())
    adv = view["advisor"].value_counts().index[0]
    sub = view[view["advisor"] == adv]
    return adv, sub.iloc[0], sub.iloc[1]


def test_seguimiento_overdue_actions_listed_first(test_dsn):
    from wm.store import Store
    adv, a, b = _two_clients_same_advisor()
    s = Store(test_dsn)
    s.set_dato(b["rut"], "proxima_accion", "Enviar propuesta", adv)       # futura (se inserta primero)
    s.set_dato(b["rut"], "proxima_accion_fecha", "2099-01-01", adv)
    s.set_dato(a["rut"], "proxima_accion", "Llamar al cliente", adv)       # vencida
    s.set_dato(a["rut"], "proxima_accion_fecha", "2020-01-01", adv)
    at = run(NAV_SEGUIMIENTO, advisor=adv)
    table = next(m.value for m in at.markdown if "Próxima acción" in m.value and "<table" in m.value)
    assert table.index("Llamar al cliente") < table.index("Enviar propuesta")
    assert "Vencida" in table


def test_seguimiento_empty_state_when_no_actions():
    at = run(NAV_SEGUIMIENTO)
    assert any("No hay acciones" in i.value for i in at.info)


# ------------------------------------------------------------------ MD y feedback
MD = "Managing Director"
NAV_MD = "Resumen del equipo"
NAV_FEEDBACK = "Bandeja de feedback"


def test_md_view_renders_consolidated_kpis():
    at = run(role=MD)
    html = " ".join(m.value for m in at.markdown)
    assert "Resumen del equipo" in html and "Comparación de advisors" in html


def test_md_flujos_pending_without_columns(tmp_path, monkeypatch):
    import pandas as pd
    from tests.conftest import _write
    frames = pd.read_excel(SAMPLE, sheet_name=None, header=2)
    frames["Dummy Metricas"] = frames["Dummy Metricas"].drop(columns=["aportes_periodo", "retiros_periodo", "periodo"])
    frames.pop("Dummy Flujos", None)
    p = tmp_path / "noflujos.xlsx"
    _write(p, frames)
    monkeypatch.setenv("WM_EXCEL", str(p))
    at = run(role=MD)
    assert "Pendiente de datos" in " ".join(m.value for m in at.markdown)


def test_md_advisor_comparison_has_one_row_per_advisor():
    from wm.loader import load_dataset
    n = load_dataset(SAMPLE).clientes["advisor"].nunique()
    at = run(role=MD)
    table = next(m.value for m in at.markdown if "% series malas" in m.value)
    assert table.count("<tr>") == n + 1  # encabezado + una fila por advisor


def test_md_feedback_inbox_lists_store_items(test_dsn):
    from wm.store import Store
    Store(test_dsn).add_feedback("IA_X", "Home", "Falta un dato", "Quiero ver la fecha de ingreso", "alta")
    at = run(NAV_FEEDBACK, role=MD)
    assert "Quiero ver la fecha de ingreso" in " ".join(m.value for m in at.markdown)


def test_md_can_trigger_csv_export(tmp_path, monkeypatch, test_dsn):
    from wm.store import Store
    Store(test_dsn).add_feedback("IA_X", "Home", "Falta un dato", "x", "baja")
    monkeypatch.setenv("WM_EXPORT_DIR", str(tmp_path))
    at = run(NAV_FEEDBACK, role=MD)
    at.button(key="fb_export").click().run()
    assert not at.exception
    assert len(list(tmp_path.glob("feedback_*.csv"))) == 1


def test_sidebar_feedback_button_saves_page_of_origin_automatically(test_dsn):
    from wm.store import Store
    at = run("Clientes")
    at.sidebar.text_area(key="fb_texto").set_value("Agregar columna de fecha de nacimiento").run()
    at.sidebar.button(key="fb_send").click().run()
    assert not at.exception
    (fb,) = Store(test_dsn).list_feedback()
    assert "Clientes" in fb["pagina"] and fb["texto"].startswith("Agregar columna")


# ------------------------------------------------------------------ pasada de arreglos (revisión final)
BAD_DSN = "postgresql://localhost:1/none?connect_timeout=1"


def test_comment_html_is_escaped_not_rendered(test_dsn):
    from wm.store import Store
    rut, adv = _pick(True)
    Store(test_dsn).add_comment(rut, adv, "<style>.stApp{display:none}</style> rentabilidad <5% y $100 y $200")
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    html = " ".join(m.value for m in at.markdown)
    assert "<style>.stApp{display:none}" not in html
    assert "&lt;style&gt;" in html


def test_typed_comment_survives_store_outage(monkeypatch):
    rut, adv = _pick(True)
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    at.text_area(key=f"coment_{rut}").set_value("borrador importante").run()
    monkeypatch.setenv("WM_DSN", BAD_DSN)
    at.run()
    assert not at.exception
    ta = at.text_area(key=f"coment_{rut}")
    assert ta.value == "borrador importante" and ta.disabled is True


def test_sidebar_feedback_text_survives_store_outage(monkeypatch):
    at = run("Clientes")
    at.sidebar.text_area(key="fb_texto").set_value("idea a medias").run()
    monkeypatch.setenv("WM_DSN", BAD_DSN)
    at.run()
    ta = at.sidebar.text_area(key="fb_texto")
    assert ta.value == "idea a medias" and ta.disabled is True


def test_save_does_not_overwrite_value_written_by_another_advisor_meanwhile(test_dsn):
    from wm.store import Store
    rut, adv = _pick(True)
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    at.number_input(key=f"dato_{rut}_patrimonio_externo").set_value(200.0)
    Store(test_dsn).set_dato(rut, "patrimonio_externo", "100", "OTRO_ADVISOR")  # llega después de dibujar la página
    at.button(key="datos_save").click().run()
    got = Store(test_dsn).get_datos(rut)["patrimonio_externo"]
    assert got["valor"] == "100" and got["advisor"] == "OTRO_ADVISOR"


def test_large_numbers_are_stored_without_scientific_notation(test_dsn):
    from wm.store import Store
    rut, adv = _pick(True)
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    at.number_input(key=f"dato_{rut}_patrimonio_externo").set_value(1234567890.0)
    at.button(key="datos_save").click().run()
    assert Store(test_dsn).get_datos(rut)["patrimonio_externo"]["valor"] == "1234567890"


def test_ficha_flags_when_excel_and_advisor_values_differ(test_dsn):
    from datetime import date
    from wm.enrich import enrich_clientes
    from wm.loader import load_dataset
    from wm.store import Store
    rut, adv = _pick(True)
    view = enrich_clientes(load_dataset(SAMPLE), date.today()).set_index("rut")
    excel = int(view.loc[rut, "share_of_wallet_pct"])
    Store(test_dsn).set_dato(rut, "share_of_wallet", str(excel + 50 if excel < 50 else excel - 50), adv)
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    assert "Difiere del Excel" in " ".join(m.value for m in at.markdown)


def test_ficha_shows_wealth_plan_no_when_excel_says_no(tmp_path, monkeypatch):
    import pandas as pd
    from tests.conftest import _write
    rut, adv = _pick(True)
    frames = pd.read_excel(SAMPLE, sheet_name=None, header=2)
    m = frames["Dummy Metricas"]
    m["tiene_wealth_plan"] = m["tiene_wealth_plan"].astype(object)
    m.loc[m["RUT Normalizado"] == rut, "tiene_wealth_plan"] = "No"
    p = tmp_path / "wp.xlsx"
    _write(p, frames)
    monkeypatch.setenv("WM_EXCEL", str(p))
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    html = " ".join(m_.value for m_ in at.markdown)
    assert "Wealth plan</div><div class='stat-value'>No<" in html


# ------------------------------------------------------------------ nombres y datos reales
REAL = ROOT / "data" / "Engine WM Dummy.xlsx"


def test_home_shows_advisor_full_name_and_clients_as_rut_and_name():
    at = run()
    html = " ".join(m.value for m in at.markdown)
    assert "IA_" not in next(m.value for m in at.markdown if "hello-name" in m.value)
    assert "ENTITY_" not in html
    queue = next(m.value for m in at.markdown if "Motivos" in m.value)
    assert "RUT_" not in queue and re.search(r"\d\.\d{3}-[\dK] ", queue)  # 848.711-4 Nombre


def test_advisor_selector_lists_names_not_codes():
    at = run()
    assert all(not str(o).startswith("IA_") for o in at.sidebar.selectbox(key="advisor").options)


def test_clientes_table_shows_tipo_persona():
    at = run("Clientes")
    table = next(m.value for m in at.markdown if "<th" in m.value)
    assert "Tipo" in table and ("Persona natural" in table or "Persona jurídica" in table)


def test_ficha_with_real_excel_in_usd_does_not_crash(monkeypatch):
    """Regresión: G/P no Realizada llega como texto en el Excel real y rompía la Ficha en USD."""
    monkeypatch.setenv("WM_EXCEL", str(REAL))
    from datetime import date
    from wm.enrich import enrich_clientes
    from wm.loader import load_dataset
    ds = load_dataset(REAL)
    view = enrich_clientes(ds, date.today()).set_index("rut")
    import pandas as pd
    raw = pd.read_excel(REAL, sheet_name="Dummy Posiciones", header=2)
    con_gp = set(raw.loc[raw["G/P no Realizada"].notna(), "RUT Normalizado"].str.strip().str.upper())
    rut = next(r for r in ds.posiciones["rut"].unique() if r in view.index and r in con_gp)
    at = AppTest.from_file(APP, default_timeout=90).run()
    at.sidebar.selectbox(key="advisor").set_value(view.loc[rut, "advisor"]).run()
    at.sidebar.radio(key="moneda").set_value("USD").run()
    at.session_state["cliente_sel"] = rut
    at.sidebar.radio(key="nav").set_value(NAV_FICHA).run()
    assert not at.exception, at.exception


# ------------------------------------------------------------------ manejo de negocio
NAV_NEGOCIO = "Manejo de negocio"


def _html(at) -> str:
    return " ".join(m.value for m in at.markdown)


def test_negocio_page_renders_all_sections_for_md():
    at = run(NAV_NEGOCIO, role=MD)
    html = _html(at)
    for section in ("AUM por arquitectura", "Cuánto tenemos en cada fondo", "Rentabilidades",
                    "Ingresos por comisión", "Comisiones por cliente"):
        assert section in html, section
    assert "Pendiente de datos" not in html


def test_negocio_fondo_table_lists_funds_with_aum_and_clients():
    at = run(NAV_NEGOCIO, role=MD)
    table = next(m.value for m in at.markdown if "<th" in m.value and "N° clientes" in m.value)
    assert "AUM" in table and "% del AUM" in table


def test_negocio_comisiones_pending_without_columns(tmp_path, monkeypatch):
    import pandas as pd
    from tests.conftest import _write
    frames = pd.read_excel(SAMPLE, sheet_name=None, header=2)
    frames["Dummy Metricas"] = frames["Dummy Metricas"].drop(columns=["comision_anual_clp", "comision_cobrada_clp"])
    p = tmp_path / "nocom.xlsx"
    _write(p, frames)
    monkeypatch.setenv("WM_EXCEL", str(p))
    html = _html(run(NAV_NEGOCIO, role=MD))
    assert "Pendiente de datos" in html and "comision_anual_clp" in html


def test_negocio_rentabilidad_falls_back_to_positions_when_no_excel_column(tmp_path, monkeypatch):
    import pandas as pd
    from tests.conftest import _write
    frames = pd.read_excel(SAMPLE, sheet_name=None, header=2)
    frames["Dummy Metricas"] = frames["Dummy Metricas"].drop(columns=["rentabilidad_12m_pct"])
    p = tmp_path / "norent.xlsx"
    _write(p, frames)
    monkeypatch.setenv("WM_EXCEL", str(p))
    assert "rentabilidad no realizada" in _html(run(NAV_NEGOCIO, role=MD))


def test_negocio_with_original_dummy_degrades_without_crashing(monkeypatch):
    monkeypatch.setenv("WM_EXCEL", str(REAL))
    at = run(NAV_NEGOCIO, role=MD)
    assert not at.exception
    assert "Pendiente de datos" in _html(at)  # comisiones aún no existen en el dummy original


# ------------------------------------------------------------------ exposiciones y rebalanceo en la ficha
def test_ficha_has_exposiciones_section_above_posiciones_with_class_and_currency():
    rut, adv = _pick_by_arch(declarada=False)
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    html = _html(at)
    assert html.index("Exposiciones") < html.index("Posiciones")
    assert "Clase de Activos" in html and "**Moneda**" in html
    assert "· modelo" not in html  # la comparación con el modelo vive en Posiciones
    if "Renta Variable" in html and "Renta Fija" in html:
        assert html.index("Renta Variable") < html.index("Renta Fija")
    assert any(c in html for c in ("Renta Fija", "Renta Variable", "Alternativos"))
    assert any(m in html for m in ("USD", "CLP", "UF"))
    assert len(at.get("plotly_chart")) >= 2


def test_ficha_positions_compare_with_model_in_percent_and_clp():
    rut, adv = _pick_by_arch(declarada=False)
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    table = next(m.value for m in at.markdown if "<th" in m.value and "% modelo" in m.value)
    for header in ("Fondo", "% hoy", "% modelo", "Diferencia (pp)", "Ajuste sugerido", "Acción"):
        assert header in table, header
    assert "Comprar" in table or "Vender" in table or "Mantener" in table


def test_alineacion_detail_shows_fund_level_rebalance_table():
    at = run(NAV_ALINEACION)
    assert any("% modelo" in m.value and "<th" in m.value for m in at.markdown)


def test_no_emojis_anywhere_in_the_rendered_app():
    import re
    emoji = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\uFE0F]")
    at = run()
    texts = [m.value for m in at.markdown] + [e.value for e in at.caption] + [str(o) for r in at.sidebar.radio for o in r.options]
    assert not [t for t in texts if emoji.search(t)]


# ------------------------------------------------------------------ costo de comisión en la ficha
def _pick_by_servicio(servicio: str) -> tuple[str, str]:
    from wm.loader import load_dataset
    ds = load_dataset(SAMPLE)
    held = set(ds.posiciones["rut"])
    c = ds.clientes[(ds.clientes["servicio"] == servicio) & ds.clientes["rut"].isin(held)].iloc[0]
    return c["rut"], c["advisor"]


@pytest.mark.parametrize("servicio,items", [
    ("ADC", ("Fondos", "ADC")),
    ("ASE", ("Fondos", "ASE")),
    ("TRA", ("Renta Variable", "Renta Fija", "Intermediación", "Allfunds")),
])
def test_ficha_shows_commission_total_with_breakdown_by_service(servicio, items):
    rut, adv = _pick_by_servicio(servicio)
    html = _html(run(NAV_FICHA, advisor=adv, cliente=rut))
    assert "Comisión" in html
    head = html[html.index(">Comisión<"):]
    assert all(i in head for i in items)


def test_ficha_series_table_shows_cost_of_each_series():
    rut, adv = _pick_by_arch(declarada=False)
    html = _html(run(NAV_FICHA, advisor=adv, cliente=rut))
    assert "Costo serie actual" in html and "Costo serie modelo" in html


def test_ficha_client_label_uses_formatted_rut_without_prefix():
    rut, adv = _pick_by_servicio("ADC")
    html = _html(run(NAV_FICHA, advisor=adv, cliente=rut))
    assert "RUT_" not in html.split("Ficha del cliente", 1)[-1].split("Comisión", 1)[0].replace(rut, "")


def test_ficha_position_detail_shows_tax_cost_column():
    rut, adv = _pick_by_servicio("ADC")
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    table = next(m.value for m in at.markdown if "<th" in m.value and "G/P no realizada" in m.value)
    assert "Costo tributario" in table
    assert "—" not in table.split("Costo tributario", 1)[1].split("</tr>", 1)[1]  # el dummy trae el monto de cada posición


def test_ficha_tax_cost_sits_left_of_rentabilidad_and_series_shows_tax_benefit():
    rut, adv = _pick_by_arch(declarada=False)
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    detalle = next(m.value for m in at.markdown if "<th" in m.value and "G/P no realizada" in m.value)
    assert detalle.index("Costo tributario") < detalle.index("Rentabilidad")
    series = next(m.value for m in at.markdown if "<th" in m.value and "Costo serie modelo" in m.value)
    assert series.index("Serie modelo") < series.index("Beneficio tributario") < series.index("Estado")


def test_tables_keep_first_column_left_and_center_the_rest():
    from ui.theme import CSS
    assert "table.dtable th:first-child, table.dtable td:first-child { text-align:left; }" in CSS
    assert "table.dtable td, table.dtable th.num { text-align:center; }" in CSS


def test_ficha_series_tax_benefit_is_107_108_or_dash_per_series():
    import re
    rut, adv = _pick_by_arch(declarada=False)
    series = next(m.value for m in _pick_run(rut, adv).markdown if "<th" in m.value and "Costo serie modelo" in m.value)
    col = re.findall(r"<th[ >][^<]*", series).index(next(h for h in re.findall(r"<th[ >][^<]*", series) if "Beneficio tributario" in h))
    cells = [re.findall(r"<td[^>]*>(.*?)</td>", row)[col] for row in series.split("<tr>")[2:]]
    assert cells and all(re.fullmatch(r"(-|107|108)( → (-|107|108))?", c) for c in cells), cells


def _pick_run(rut, adv):
    return run(NAV_FICHA, advisor=adv, cliente=rut)


def test_advisor_form_has_global_complementario_and_deep_discovery_right_after_wealth_plan(test_dsn):
    from wm.store import Store
    rut, adv = _pick(True)
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    from wm.config import load_config
    campos = list(load_config("campos_cliente")["campos"])
    assert campos[campos.index("wealth_plan") + 1:campos.index("wealth_plan") + 3] == ["global_complementario", "deep_discovery"]
    at.number_input(key=f"dato_{rut}_global_complementario").set_value(35.0)
    at.selectbox(key=f"dato_{rut}_deep_discovery").set_value("Sí")
    at.button(key="datos_save").click().run()
    got = Store(test_dsn).get_datos(rut)
    assert got["global_complementario"]["valor"] == "35" and got["deep_discovery"]["valor"] == "si"


def _keys_in_page_order(node, out=None):
    out = [] if out is None else out
    if getattr(node, "key", None):
        out.append(node.key)
    for child in getattr(node, "children", {}).values():
        _keys_in_page_order(child, out)
    return out


def test_global_complementario_and_deep_discovery_render_below_comments_column():
    rut, adv = _pick(True)
    keys = _keys_in_page_order(run(NAV_FICHA, advisor=adv, cliente=rut).main)
    order = [keys.index(k) for k in (f"coment_{rut}", f"dato_{rut}_wealth_plan", f"dato_{rut}_global_complementario",
                                     f"dato_{rut}_proxima_accion", f"dato_{rut}_deep_discovery",
                                     f"dato_{rut}_proxima_accion_fecha")]
    assert order == sorted(order)  # filas de a dos: izquierda y derecha alineadas, debajo de los comentarios


def test_sidebar_currency_offers_cad_and_converts_aum_with_the_cad_rate():
    from ui.context import derive_fx
    at = run()
    assert list(at.sidebar.radio(key="moneda").options) == ["CLP", "USD", "CAD"]
    at.sidebar.radio(key="moneda").set_value("CAD").run()
    assert not at.exception, at.exception
    assert any("CA$" in m.value for m in at.markdown)
    at.sidebar.radio(key="moneda").set_value("USD").run()
    assert any("US$" in m.value for m in at.markdown) and not any("CA$" in m.value for m in at.markdown)


def test_md_flows_chart_is_bars_only_with_centered_legend_below():
    import json
    at = run("Resumen del equipo", role="Managing Director")
    assert not at.radio  or all(r.key != "flujos_vista" for r in at.radio)   # sin selector de tipo de gráfico
    spec = json.loads(at.get("plotly_chart")[0].proto.spec)
    assert [t["type"] for t in spec["data"]] == ["bar", "bar", "scatter"]
    leg = spec["layout"]["legend"]
    assert leg["x"] == 0.5 and leg["xanchor"] == "center" and leg["y"] <= -0.25


def test_md_flows_chart_can_be_filtered_by_advisor_or_a_combination_of_them():
    import json
    at = run("Resumen del equipo", role="Managing Director")
    box = at.multiselect(key="flujos_advisors")
    assert len(box.options) >= 2

    def serie():
        spec = _chart_specs(at)[0]
        return next(t for t in spec["data"] if t["name"] == "Aportes")["y"]
    todos = serie()
    assert len(todos) == 26                       # una quincena por punto
    at.multiselect(key="flujos_advisors").select(box.options[0]).run()
    uno = serie()
    at.multiselect(key="flujos_advisors").select(box.options[1]).run()
    dos = serie()
    assert sum(uno) < sum(dos) < sum(todos) or sum(uno) < sum(todos)
    assert not at.exception


# ------------------------------------------------------------------ rol y módulos (el rol se elige en la barra lateral)
def test_sidebar_offers_the_three_roles_and_brand_is_advisory_and_brokerage():
    at = AppTest.from_file(APP, default_timeout=90).run()
    assert not at.exception
    assert list(at.sidebar.selectbox(key="role").options) == ["Investment Advisor", "Managing Director", "Estrategia"]
    html = _html(at)
    assert "Advisory and" in html and "Brokerage" in html and "Wealth" not in html


def test_roles_unlock_different_modules():
    ia = run()
    assert list(ia.sidebar.radio(key="modulo").options) == ["Client Portal", "Estrategia", "Mercados"]
    assert list(ia.sidebar.radio(key="nav").options) == ["Home", "Clientes", "Ficha del cliente", "Alineación al modelo", "Seguimiento"]
    ia.sidebar.radio(key="modulo").set_value("Estrategia").run()   # el advisor también ve Estrategia
    h = " ".join(m.value for m in ia.markdown)
    assert not ia.exception and "Portafolios" in h              # con o sin foto de la CMF
    md_ = run(role="Managing Director")
    assert list(md_.sidebar.radio(key="modulo").options) == ["Client Portal", "Estrategia", "Mercados"]
    assert list(md_.sidebar.radio(key="nav").options) == ["Resumen del equipo", "Manejo de negocio", "Ficha del cliente", "Bandeja de feedback"]
    md_.sidebar.radio(key="modulo").set_value("Estrategia").run()
    assert not md_.exception and list(md_.sidebar.radio(key="nav").options) == ["Screener", "Comparador", "Historial"]
    assert "Portafolios" in " ".join(m.value for m in md_.sidebar.markdown)      # sección bajo el módulo Estrategia
    otro = run(role="Estrategia")
    assert list(otro.sidebar.radio(key="modulo").options) == ["Estrategia", "Mercados"]
    assert list(otro.sidebar.radio(key="nav").options) == ["Screener", "Comparador", "Historial"]


def _decode(o):
    """plotly >= 6 serializa los arreglos numéricos como {'dtype','bdata'}; los devuelve a lista."""
    import base64
    import numpy as np
    if isinstance(o, dict):
        if "bdata" in o and "dtype" in o:
            return np.frombuffer(base64.b64decode(o["bdata"]), dtype=np.dtype(o["dtype"])).tolist()
        return {k: _decode(v) for k, v in o.items()}
    return [_decode(v) for v in o] if isinstance(o, list) else o


def _chart_specs(at):
    import json
    return [_decode(json.loads(c.proto.spec)) for c in at.get("plotly_chart")]


@pytest.mark.parametrize("moneda,prefix", [("CLP", "$"), ("USD", "US$"), ("CAD", "CA$")])
def test_chart_tooltips_and_axes_follow_the_selected_currency(moneda, prefix):
    home = run()
    home.sidebar.radio(key="moneda").set_value(moneda).run()
    pie = next(s for s in _chart_specs(home) if s["data"][0]["type"] == "pie")["data"][0]
    assert all(str(t).startswith(prefix) for t in pie["customdata"]) and "customdata" in pie["hovertemplate"]
    negocio = run(NAV_NEGOCIO, role=MD)
    negocio.sidebar.radio(key="moneda").set_value(moneda).run()
    bar = next(s for s in _chart_specs(negocio) if s["data"][0]["type"] == "bar" and s["data"][0].get("orientation") == "h")
    assert bar["layout"]["xaxis"]["tickprefix"] == prefix and bar["layout"]["xaxis"]["ticksuffix"] == " MM"
    assert all(str(t).startswith(prefix) for t in bar["data"][0]["customdata"])
    md_ = run("Resumen del equipo", role=MD)
    md_.sidebar.radio(key="moneda").set_value(moneda).run()
    flujos = next(s for s in _chart_specs(md_) if s["data"][0]["type"] == "bar")
    assert flujos["layout"]["yaxis"]["tickprefix"] == prefix
    assert all(str(t).lstrip("−-").startswith(prefix) for t in flujos["data"][0]["customdata"])


def test_negocio_kpi_row_gives_the_aum_more_room_than_the_other_figures():
    import re
    src = (ROOT / "ui" / "pages" / "negocio.py").read_text()
    widths = [float(w) for w in re.search(r"st\.columns\(\[([\d., ]+)\]\)", src).group(1).split(",")]
    assert widths[0] == max(widths) and len(widths) == 5


def test_negocio_bar_charts_are_red_horizontal_with_value_labels_and_readable_profile_names():
    at = run(NAV_NEGOCIO, role=MD)
    bars = [s for s in _chart_specs(at) if s["data"][0]["type"] == "bar"]
    assert len(bars) == 5                                  # AUM por fondo, advisor, servicio, portafolio y perfil
    for spec in bars:
        t = spec["data"][0]
        assert t["orientation"] == "h" and t["textposition"] == "outside" and t["text"]
        colors = t["marker"]["color"]
        colors = [colors] if isinstance(colors, str) else colors
        assert set(colors) <= {"#EC111A", "#3B3B3F"} and "#EC111A" in colors
    servicio = bars[2]["data"][0]["y"]
    assert servicio and "TRA" not in servicio
    perfil = bars[-1]["data"][0]["y"]
    assert perfil == [n for n in ["Preservación", "Defensivo", "Equilibrado", "Clásico 60-40", "Crecimiento"] if n in perfil]
    assert not any("_" in n or n.isupper() for n in perfil)  # sin CLASICO_60_40 ni PRESERVACION en bruto


def test_negocio_return_charts_have_no_dashed_area_reference_line():
    spec = [s for s in _chart_specs(run(NAV_NEGOCIO, role=MD)) if s["data"][0]["type"] == "bar"]
    assert all(not s["layout"].get("shapes") for s in spec)


def test_negocio_returns_section_has_four_chart_titles_in_a_professional_font():
    from ui.theme import CSS
    html = _html(run(NAV_NEGOCIO, role=MD))
    titulos = [html.index(f"<div class='chart-title'>{t}</div>") for t in ("Advisor", "Servicio", "Portafolio", "Perfil de riesgo")]
    assert html.index("Rentabilidades") < min(titulos) and titulos == sorted(titulos)
    assert "Rentabilidad por" not in html
    assert "font-family: Charter" in CSS.split(".chart-title")[1].split("}")[0]  # misma tipografía serif de los títulos


def test_negocio_bar_charts_have_no_vertical_lines():
    for spec in [s for s in _chart_specs(run(NAV_NEGOCIO, role=MD)) if s["data"][0]["type"] == "bar"]:
        x = spec["layout"]["xaxis"]
        assert x["showgrid"] is False and x["showline"] is False
        assert spec["layout"]["yaxis"]["showline"] is False and spec["layout"]["yaxis"]["showgrid"] is False


def test_ficha_rentabilidad_table_shows_fund_names_not_internal_ids():
    rut, adv = _pick_by_servicio("ADC")
    at = run(NAV_FICHA, advisor=adv, cliente=rut)
    table = next(m.value for m in at.markdown if "<th" in m.value and "Total cartera" in m.value)
    assert "SIN_ISIN" not in table


def test_alineacion_detail_chart_is_a_diverging_bar_chart_with_class_subassets_and_currency():
    at = run(NAV_ALINEACION)
    specs = [s for s in _chart_specs(at) if s["data"][0]["type"] == "bar" and s["data"][0].get("orientation") == "h"]
    assert specs, "no se dibujó el gráfico de desvío"
    spec = specs[0]
    y = [t.replace("<b>", "").replace("</b>", "").replace(" ", "") for t in spec["data"][0]["y"]]
    assert y.index("Renta Variable") < y.index("Renta Fija") < y.index("Moneda")
    x = spec["layout"]["xaxis"]["range"]
    assert x[0] == -x[1] and x[1] > 0                       # el cero queda en el centro
    assert spec["layout"]["xaxis"]["zeroline"] is True and spec["layout"]["yaxis"]["autorange"] == "reversed"
    assert [t["name"] for t in spec["data"]] == ["Sobre el modelo", "Bajo el modelo"]


def test_alineacion_detail_chart_uses_red_for_positive_and_gray_for_negative():
    at = run(NAV_ALINEACION)
    spec = next(s for s in _chart_specs(at) if s["data"][0]["type"] == "bar" and s["data"][0].get("orientation") == "h")
    assert {t["name"]: t["marker"]["color"] for t in spec["data"]} == {"Sobre el modelo": "#EC111A", "Bajo el modelo": "#8A8A90"}


# ------------------------------------------------------------------ robustez con volumen y datos sucios (dummy de 500 clientes)
@pytest.fixture(scope="module")
def sucios():
    """Clientes con casos límite del dummy: los encuentra por sus propiedades, no por su posición."""
    from datetime import date
    from wm.enrich import enrich_clientes
    from wm.loader import load_dataset
    ds = load_dataset(SAMPLE)
    view = enrich_clientes(ds, date.today())
    pos = ds.posiciones
    por = lambda ruts: sorted(set(ruts) & set(view["rut"]))  # noqa: E731
    return {
        "ds": ds, "view": view,
        "aum_cero": por(view.loc[view["aum_clp"] == 0, "rut"]),
        "servicio_desconocido": por(view.loc[view["servicio"] == "Sin clasificar", "rut"]),
        "sin_advisor": por(view.loc[view["advisor"].isna(), "rut"]),
        "nombre_html": por(view.loc[view["nombre"].str.contains("<b>", regex=False), "rut"]),
        "nombre_largo": por(view.loc[view["nombre"].str.len() > 100, "rut"]),
        "isin_fuera_catalogo": por(pos.loc[pos["isin"] == "XX0000000000", "rut"]),
        "posicion_valor_cero": por(pos.loc[pos["valor_clp"] == 0, "rut"]),
        "gp_vacio": por(pos.loc[pos["gp_no_realizada"].isna(), "rut"]),
    }


def test_dummy_has_volume_and_every_edge_case_is_present(sucios):
    ds, view = sucios["ds"], sucios["view"]
    assert len(view) >= 450 and view["advisor"].nunique() >= 10 and view["household"].nunique() < len(view)
    for caso in ("aum_cero", "servicio_desconocido", "sin_advisor", "nombre_html", "nombre_largo", "isin_fuera_catalogo",
                 "posicion_valor_cero", "gp_vacio"):
        assert sucios[caso], f"falta el caso límite {caso}"
    assert ds.duplicate_ruts, "el dummy debe traer un RUT repetido para probar Calidad de datos"


def test_every_client_goes_through_the_calculations_without_errors(sucios):
    """Las cuentas que alimentan la ficha, para los 500 clientes: nada se cae y no aparecen NaN/inf donde hay un monto."""
    import math
    from wm.alignment import desvio_detalle
    from wm.costos import costo_comision
    from wm.exposure import client_exposure, model_exposure, perfil_of
    from wm.rebalance import plan_rebalanceo
    from wm.series import evaluate_series
    ds, view = sucios["ds"], sucios["view"]
    pos_by = {r: g for r, g in ds.posiciones.groupby("rut")}
    vacio = ds.posiciones.iloc[0:0]
    for _, c in view.iterrows():
        pos = pos_by.get(c["rut"], vacio)
        arq = c["arquitectura"] if c["arquitectura"] == c["arquitectura"] else None
        perfil = perfil_of(ds.carteras, c.get("perfil_norm"))
        evaluate_series(pos, ds.carteras, arq)
        cli = client_exposure(pos, ds.carteras)
        if arq and perfil:
            desvio_detalle(cli, model_exposure(ds.carteras, arq, perfil))
            plan = plan_rebalanceo(pos, ds.carteras, arq, perfil, base_clp=float(c["aum_clp"]))
            if plan is not None:
                assert all(math.isfinite(v) for v in plan["ajuste_clp"])
        costo = costo_comision(c, pos, ds.carteras)
        if costo is not None:
            assert math.isfinite(costo.total)


@pytest.mark.parametrize("caso", ["aum_cero", "servicio_desconocido", "nombre_html", "nombre_largo", "isin_fuera_catalogo",
                                  "posicion_valor_cero", "gp_vacio"])
def test_ficha_of_dirty_clients_renders_without_exception(sucios, caso):
    view = sucios["view"].set_index("rut")
    for rut in sucios[caso][:3]:
        adv = view.loc[rut, "advisor"]
        if adv != adv:
            continue  # sin advisor: ninguna ficha de advisor la alcanza
        for moneda in ("CLP", "USD"):
            at = AppTest.from_file(APP, default_timeout=90).run()
            at.sidebar.selectbox(key="advisor").set_value(adv).run()
            at.sidebar.radio(key="moneda").set_value(moneda).run()
            at.session_state["cliente_sel"] = rut
            at.sidebar.radio(key="nav").set_value(NAV_FICHA).run()
            assert not at.exception, (caso, rut, moneda, at.exception)


def test_html_in_client_names_is_escaped_everywhere(sucios):
    rut = sucios["nombre_html"][0]
    view = sucios["view"].set_index("rut")
    adv = view.loc[rut, "advisor"]
    for nav in (NAV_FICHA, "Clientes", "Home", "Alineación al modelo"):
        at = run(nav, advisor=adv, cliente=rut)
        assert "<b>Hijos</b>" not in _html(at), nav          # nunca como HTML vivo
    assert "&lt;b&gt;Hijos" in _html(run(NAV_FICHA, advisor=adv, cliente=rut))


def test_all_pages_render_for_every_advisor_and_for_the_md_with_500_clients(sucios):
    advisors = sorted(sucios["view"]["advisor"].dropna().unique())
    assert len(advisors) >= 10
    for adv in advisors[:4] + advisors[-2:]:                                  # una muestra, incluidos advisors nuevos
        for nav in ("Home", "Clientes", "Alineación al modelo", "Seguimiento"):
            at = run(nav, advisor=adv)
            assert not at.exception, (adv, nav, at.exception)
    for nav in ("Resumen del equipo", "Manejo de negocio", "Bandeja de feedback"):
        at = run(nav, role=MD)
        assert not at.exception, (nav, at.exception)
    at = run(NAV_NEGOCIO, role=MD)
    for moneda in ("USD", "CAD"):
        at.sidebar.radio(key="moneda").set_value(moneda).run()
        assert not at.exception, (moneda, at.exception)


def test_quality_panel_flags_the_duplicated_rut_of_the_dummy(sucios):
    at = run()
    avisos = " ".join(c.value for c in at.sidebar.expander[-1].caption) if at.sidebar.expander else ""
    assert "RUT" in avisos or any("repetid" in c.value.lower() or "duplic" in c.value.lower() for c in at.caption)


def test_loading_and_enriching_500_clients_is_fast_enough():
    import time
    from datetime import date
    from wm.enrich import enrich_clientes
    from wm.loader import load_dataset
    t0 = time.perf_counter()
    enrich_clientes(load_dataset(SAMPLE), date.today())
    assert time.perf_counter() - t0 < 30


# ---------------------------------------------------------------- Estrategia (portafolios)
def _estrategia(monkeypatch, tmp_path, con_foto=True, con_equiv=True, con_yahoo=False, nav="Screener"):
    import ui.pages.estrategia as est
    from tests.conftest import _write_cmf
    from wm.loader import load_dataset
    from wm.mercado import equivalencias as eq
    from wm.mercado.cmf import leer_cmf
    from wm.mercado.snapshots import guardar_foto
    snaps, equiv = tmp_path / "m", tmp_path / "e.csv"
    if con_foto:
        guardar_foto(leer_cmf(_write_cmf(tmp_path / "cmf")), snaps)
    if con_equiv:
        c = load_dataset().carteras.iloc[0]
        e = pd.DataFrame([{"instrumento_catalogo": c["instrumento"], "isin": c["isin"], "serie_catalogo": c["serie"],
                           "fo_run": 8011, "fm_serie": "I2", "confianza": 1.0}])
        eq.guardar(e.reindex(columns=eq.EQUIV_COLS), equiv)
    monkeypatch.setattr(est, "_rutas", lambda: (snaps, equiv))
    monkeypatch.setattr(est, "_ruta_yahoo", lambda: tmp_path / "ext" / "yahoo")
    if con_yahoo:
        from datetime import date as _d
        from tests.test_mercado_internacionales import CAT, FakeYahoo
        from wm.mercado import internacionales as _it
        _it.guardar_yahoo(_it.construir(CAT, FakeYahoo(), hoy=_d(2026, 10, 18)), tmp_path / "ext" / "yahoo", _d(2026, 10, 18))
    if con_yahoo == "completo":      # todos los fondos de las carteras Abierta USD con datos
        from tests.test_mercado_carteras_usd import _yahoo as _yahoo_usd
        _it.guardar_yahoo(_yahoo_usd(), tmp_path / "ext" / "yahoo", _d(2026, 10, 18))
    return run(nav, role="Estrategia")


def _html(at) -> str:
    return " ".join(m.value for m in at.markdown)


def _portafolio(at, arq, perfil=None):
    at.radio(key="est_arq").set_value(arq).run()
    if perfil:
        at.radio(key="est_perfil").set_value(perfil).run()
    assert not at.exception, at.exception
    return _html(at)


def _tabla_con(h, texto):
    return next(t for t in h.split("<table class='dtable'>") if texto in t)


def test_portafolios_es_el_titulo_y_los_subtemas_estan_en_la_barra_lateral(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path)
    assert list(at.sidebar.radio(key="nav").options) == ["Screener", "Comparador", "Historial"]
    assert "page-title'>Portafolios" in _html(at)


def test_la_primera_fila_son_las_arquitecturas_y_debajo_el_perfil(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path)
    assert list(at.radio(key="est_arq").options) == ["Cartera Gestionada", "Abierta USD", "Abierta Pesos", "Local"]
    assert at.radio(key="est_arq").value == "cerrada_pesos"
    assert list(at.radio(key="est_perfil").options) == ["Preservación", "Defensivo", "Equilibrado", "Clásico 60-40", "Crecimiento"]
    ordenados = [r.key for r in at.radio]
    assert ordenados.index("est_arq") < ordenados.index("est_perfil")


def test_cada_perfil_tiene_las_vistas_rentabilidades_y_exposiciones(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path)
    assert [t.label for t in at.tabs] == ["Rentabilidades", "Exposiciones"]
    h = _html(at)
    assert "Rent. 1A" in _tabla_con(h, "Rent. 1A") and "Beneficio tributario" in _tabla_con(h, "Beneficio tributario")


def test_estrategia_sin_foto_explica_como_cargar(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path, con_foto=False)
    h = _html(at)
    assert not at.exception and "data/cmf" in h and "actualizar_mercado" in h


def test_estrategia_muestra_sello_de_la_cmf(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path)
    assert not at.exception and "CMF, datos al 2026-06-30" in _html(at)


def test_cartera_gestionada_ordena_por_clase_y_subactivo(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path)
    assert not at.exception
    h = _html(at)
    assert "Renta variable" in h and "Renta fija" in h and "Total del portafolio" in h
    orden = [h.index(x) for x in ("Estados Unidos", "Europa", "Latinoamérica", "Chile", "Local")]
    assert orden == sorted(orden)
    assert "20.00%" in h and "80.00%" in h        # Preservación: 20% RV, 80% RF
    assert "(sin datos)" in h                       # la foto de prueba no trae fondos Scotia: no se rompe


def test_cartera_gestionada_cambia_con_el_perfil(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path)
    at.radio(key="est_perfil").set_value("CRECIMIENTO").run()
    assert not at.exception
    h = _html(at)
    assert "72.00%" in h and "8.00%" in h and "20.00%" in h   # Crecimiento: 72 RV + 8 alternativos + 20 RF


def test_filas_de_clase_van_en_rojo(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path)
    t = _tabla_con(_html(at), "Rent. 1A")
    assert t.count("<tr class='clase'>") == 2          # Preservación: renta variable y renta fija, sin alternativos
    at.radio(key="est_perfil").set_value("EQUILIBRADO").run()
    t = _tabla_con(_html(at), "Rent. 1A")
    assert t.count("<tr class='clase'>") == 3 and "Activos alternativos" in t and "Real estate" in t


def test_exposiciones_usa_la_estructura_de_clases_con_otras_columnas(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path)
    t = _tabla_con(_html(at), "Beneficio tributario")
    assert "<tr class='clase'>" in t
    cabecera = t[:t.index("</thead>")]
    for col in ("Beneficio tributario", "Renta variable", "Renta fija", "Alternativos", "USD", "CLP", "UF", "Otras"):
        assert f">{col}<" in cabecera, col
    for col in ("Peso", "Rent. YTD", "Rent. 1A", "Rent. 3A", "TAC", "Patrimonio"):   # no repite las de rentabilidades
        assert f">{col}<" not in cabecera, col


def test_exposiciones_muestra_graficos_y_composicion_subyacente(monkeypatch, tmp_path):
    h = _html(_estrategia(monkeypatch, tmp_path))
    for titulo in ("Clase de activo", "Subactivo", "Moneda del valor cuota", "Composición subyacente", "Tipo de instrumento",
                   "País del emisor"):
        assert titulo in h, titulo
    assert "donde cotiza" in h and "valor cuota" in h and "subyacente" in h


def test_abierta_usd_sin_datos_de_yahoo_explica_como_cargarlos(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path)
    _portafolio(at, "abierta_dolares")
    assert any("--fuente yahoo" in i.value for i in at.info)


def test_abierta_usd_ordena_por_clase_con_filas_rojas_y_alternativos(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path, con_yahoo="completo")
    h = _portafolio(at, "abierta_dolares", "EQUILIBRADO")
    t = _tabla_con(h, "Rent. 1A")
    assert t.count("<tr class='clase'>") == 3 and "Activos alternativos" in t
    orden = [t.index(x) for x in ("Estados Unidos", "Europa", "Latinoamérica", "Investment Grade", "High Yield")]
    assert orden == sorted(orden)
    assert "Total del portafolio" in t and "T0" in t and ">Ticker<" in t         # el ticker va como identificador
    assert "Yahoo Finance, datos al 2026-10-18" in h


def test_abierta_usd_advierte_la_cobertura_del_costo_y_la_fuente(monkeypatch, tmp_path):
    h = _portafolio(_estrategia(monkeypatch, tmp_path, con_yahoo="completo"), "abierta_dolares", "DEFENSIVO")
    assert "Costo (TER)" in h and "% del peso" in h and "no oficial" in h and "ajustado por dividendos" in h


def test_abierta_usd_cambia_con_el_perfil(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path, con_yahoo="completo")
    assert _tabla_con(_portafolio(at, "abierta_dolares", "PRESERVACION"), "Rent. 1A").count("<tr class='clase'>") == 2
    assert _tabla_con(_portafolio(at, "abierta_dolares", "CRECIMIENTO"), "Rent. 1A").count("<tr class='clase'>") == 3


def test_abierta_pesos_y_local_muestran_el_modelo_del_catalogo(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path, con_yahoo=True)
    for arq in ("abierta_pesos", "abierta_local"):
        h = _portafolio(at, arq, "DEFENSIVO")
        t = _tabla_con(h, "Rent. 1A")
        assert "<tr class='clase'>" in t and "Total del portafolio" in t, arq
        assert "modelo del catálogo" in h.lower() or "Modelo del catálogo" in h, arq


def test_abierta_pesos_toma_datos_de_yahoo_donde_hay_equivalencia(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path, con_yahoo=True)
    h = _portafolio(at, "abierta_pesos", "PRESERVACION")
    assert not at.exception and "fondos con datos" in h


def test_los_listados_de_fondos_viven_en_el_comparador(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path, nav="Comparador", con_yahoo=True)
    assert not at.exception and list(at.radio(key="est_universo").options) == ["CMF", "Internacionales"]
    at.radio(key="est_universo").set_value("Internacionales").run()
    h = _html(at)
    assert "Yahoo Finance, datos al 2026-10-18" in h and "CSSPX.MI" in h and "0.07%" in h and "Sin ticker" in h
    assert "ajustado por dividendos" in h and "no oficial" in h


def test_universo_cmf_limita_filas(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path, nav="Comparador")
    assert not at.exception
    t = _tabla_con(_html(at), "Administradora")
    assert t.count("<tr>") <= 200 + 1
    assert any("Mostrando 3 de 3 series" in c.value for c in at.caption)


def test_internacionales_sin_datos_de_yahoo_explica_como_cargarlos(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path, nav="Comparador")
    at.radio(key="est_universo").set_value("Internacionales").run()
    assert not at.exception and any("--fuente yahoo" in i.value for i in at.info)


def test_el_sello_de_la_cmf_solo_aparece_en_las_vistas_que_la_usan(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path, con_yahoo="completo")
    h = _portafolio(at, "abierta_dolares")
    assert "Yahoo Finance, datos al" in h and "CMF, datos al" not in h


def test_las_vistas_que_no_usan_la_cmf_funcionan_sin_sus_excel(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path, con_foto=False, con_yahoo="completo")
    assert any("data/cmf" in m.value for m in at.markdown)             # Cartera Gestionada sí necesita la CMF
    h = _portafolio(at, "abierta_dolares", "EQUILIBRADO")
    assert "Total del portafolio" in h
    h = _portafolio(at, "abierta_pesos")
    assert "Total del portafolio" in h


def test_comparador_pide_dos_series(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path, nav="Comparador")
    at.multiselect(key="est_cmp").set_value(["ACCIONES GLOBAL · I"]).run()
    assert not at.exception
    assert any("al menos 2" in i.value for i in at.info)
    assert "Rentabilidad a 1 año" not in _html(at)


def test_comparador_muestra_columnas_por_fondo(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path, nav="Comparador")
    at.multiselect(key="est_cmp").set_value(["ACCIONES GLOBAL · I", "VISION MONEY MARKET · I2"]).run()
    assert not at.exception
    h = _html(at)
    assert "ACCIONES GLOBAL · I" in h and "VISION MONEY MARKET · I2" in h
    assert "17.49%" in h and "—" in h
    assert "Rentabilidad a 1 año" in h


def test_composicion_vive_en_el_comparador_y_suma_100(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path, nav="Comparador")
    at.selectbox(key="est_comp_fondo").set_value(8011).run()
    assert not at.exception
    leyenda = next(m.value for m in at.markdown if "legend-row" in m.value and "Bancario local" in m.value)
    pesos = [float(x) for x in re.findall(r"(\d+\.\d)%", leyenda)]
    assert abs(sum(pesos) - 100) <= 0.1


def test_composicion_fondo_sin_cartera(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path, nav="Comparador")
    at.selectbox(key="est_comp_fondo").set_value(8915).run()
    assert not at.exception and any("Sin composición en la foto" in i.value for i in at.info)


def test_historial_pagina_nota_una_foto(monkeypatch, tmp_path):
    at = _estrategia(monkeypatch, tmp_path, nav="Historial")
    at.selectbox(key="est_hist").set_value("VISION MONEY MARKET · I2").run()
    assert not at.exception
    assert "Hace falta una segunda carga" in _html(at)
    assert len(at.get("plotly_chart")) >= 2     # patrimonio y partícipes


# ---------------------------------------------------------------- AFP (índice ponderado por fondo)
def _foto_afp(tmp_path):
    import numpy as np
    from wm.afp.fuente import FONDOS
    from wm.afp.snapshots import armar_foto, guardar_foto
    fechas = pd.bdate_range("2021-01-04", periods=1500)
    vc, pat = [], []
    for fi, f in enumerate(FONDOS):
        for afp, p0, vive in (("X", 300.0, 1500), ("Y", 100.0, 1500), ("Z", 50.0, 700)):
            for i, d in enumerate(fechas[:vive]):
                vc.append({"fecha": d, "fondo": f, "afp": afp, "valor": 100 * (1 + 0.0002 * (fi + 1)) ** i})
                pat.append({"fecha": d, "fondo": f, "afp": afp, "valor": p0 * (1 + fi) * 1e9})
    guardar_foto(armar_foto(pd.DataFrame(vc), pd.DataFrame(pat)), tmp_path / "afp")
    return armar_foto(pd.DataFrame(vc), pd.DataFrame(pat)).fecha_corte


def _afp(monkeypatch, tmp_path, con_foto=True, nav="Índices", role="Managing Director"):
    import ui.pages.afp as afp
    if con_foto:
        _foto_afp(tmp_path)
    monkeypatch.setattr(afp, "_ruta", lambda: tmp_path / "afp")
    at = run(role=role)
    at.sidebar.radio(key="modulo").set_value("Mercados").run()
    assert not at.exception, at.exception
    if nav != "Índices":
        at.sidebar.radio(key="nav").set_value(nav).run()
    assert not at.exception, at.exception
    return at


@pytest.mark.parametrize("role", ["Investment Advisor", "Managing Director", "Estrategia"])
def test_mercados_aparece_como_modulo_para_advisor_md_y_estrategia(role):
    assert "Mercados" in list(run(role=role).sidebar.radio(key="modulo").options)


def test_afp_la_seccion_y_los_subtemas_estan_en_la_barra_lateral(monkeypatch, tmp_path):
    at = _afp(monkeypatch, tmp_path)
    assert list(at.sidebar.radio(key="nav").options) == ["Índices", "Evolución"]
    assert "nav-section'>AFP<" in " ".join(m.value for m in at.sidebar.markdown)


def test_indices_muestra_cinco_fondos_y_el_sello_de_fecha(monkeypatch, tmp_path):
    at = _afp(monkeypatch, tmp_path)
    h = _html(at)
    assert all(f"Fondo {f}" in h for f in "ABCDE")
    assert "Datos al 2026-" in h and "Índices de AFP por fondo" in h
    assert len(at.get("plotly_chart")) == 1


def test_indices_el_selector_de_rango_cambia_el_grafico_sin_romper(monkeypatch, tmp_path):
    at = _afp(monkeypatch, tmp_path)
    for rango in ("10A", "1A", "3A"):
        at.radio(key="afp_rango").set_value(rango).run()
        assert not at.exception, at.exception


def test_evolucion_cambia_de_fondo(monkeypatch, tmp_path):
    at = _afp(monkeypatch, tmp_path, nav="Evolución")
    at.radio(key="afp_fondo").set_value("C").run()
    assert not at.exception, at.exception
    assert "Fondo C" in _html(at)
    assert len(at.get("plotly_chart")) == 2


def test_sin_foto_muestra_los_pasos_de_actualizacion(monkeypatch, tmp_path):
    for nav in ("Índices", "Evolución"):
        at = _afp(monkeypatch, tmp_path, con_foto=False, nav=nav)
        assert "scripts/actualizar_afp.py" in _html(at)


def test_afp_no_usa_la_red(monkeypatch, tmp_path):
    import urllib.request

    def sin_red(*a, **k):
        raise AssertionError("la página AFP no debe usar la red")
    monkeypatch.setattr(urllib.request, "urlopen", sin_red)
    for nav in ("Índices", "Evolución"):
        assert not _afp(monkeypatch, tmp_path, nav=nav).exception


def test_evolucion_barras_en_rojo_y_eje_con_holgura_para_la_etiqueta_mas_alta(monkeypatch, tmp_path):
    at = _afp(monkeypatch, tmp_path, nav="Evolución")
    barras = next(s for s in _chart_specs(at) if s["data"][0]["type"] == "bar")
    d = barras["data"][0]
    assert set(d["marker"]["color"]) == {"#EC111A"}                      # sin retornos negativos: todas rojas
    assert d["cliponaxis"] is False
    assert barras["layout"]["yaxis"]["range"][1] > max(d["y"]) * 1.1        # la etiqueta «18.07%» cabe arriba
    assert barras["layout"]["yaxis"]["range"][0] <= min(0, min(d["y"]))


def test_evolucion_con_retornos_negativos_deja_holgura_abajo(monkeypatch, tmp_path):
    import ui.pages.afp as afp
    monkeypatch.setattr(afp, "rent_anual", lambda idx: pd.Series({2024: -0.12, 2025: 0.18}))
    at = _afp(monkeypatch, tmp_path, nav="Evolución")
    barras = next(s for s in _chart_specs(at) if s["data"][0]["type"] == "bar")
    assert barras["layout"]["yaxis"]["range"][0] < -12 * 1.1
    assert barras["data"][0]["marker"]["color"] == ["#8A8A90", "#EC111A"]   # negativo en gris, positivo en rojo


def test_mercados_titula_la_pagina_afp_como_estrategia_titula_portafolios(monkeypatch, tmp_path):
    at = _afp(monkeypatch, tmp_path)
    assert "page-title'>AFP" in _html(at)


def test_screener_deja_espacio_entre_los_indicadores_y_la_tabla(monkeypatch, tmp_path):
    h = _html(_estrategia(monkeypatch, tmp_path))
    desde = h.index("ponderado</div><div class='stat-value'>")
    ultimo_indicador = h.rindex("stat-value", 0, h.index("<table class='dtable'>"))
    entre = h[ultimo_indicador:h.index("<table class='dtable'>", ultimo_indicador)]
    assert "<div class='espacio'></div>" in entre and desde < ultimo_indicador
