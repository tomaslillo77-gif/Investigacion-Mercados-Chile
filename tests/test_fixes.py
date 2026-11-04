"""Pruebas de la pasada de arreglos de la revisión final."""
from datetime import date

import pandas as pd
import pytest

from tests.test_priority import CFG, HOY, clientes
from wm.export import export_feedback
from wm.loader import DatasetCorrupt, DatasetNotFound, load_dataset, parse_number
from wm.metrics import truthy
from wm.priority import score_clients
from wm.quality import validate


# --- #5 prioridad: ceros no inflan el puntaje
def test_all_zero_ingresos_component_is_dropped_and_no_false_motivo():
    out = score_clients(clientes(ingresos_en_juego=[0.0, 0.0]), CFG, HOY)
    assert out["comp_ingresos"].isna().all()
    assert not any("Comisión" in m for ms in out["motivos"] for m in ms)


def test_zero_ingresos_scores_zero_when_others_positive():
    out = score_clients(clientes(ingresos_en_juego=[0.0, 500.0]), CFG, HOY)
    assert out.loc[0, "comp_ingresos"] == 0.0 and out.loc[1, "comp_ingresos"] > 0


# --- #6 archivo corrupto
def test_corrupt_file_raises_datasetcorrupt(tmp_path):
    p = tmp_path / "roto.xlsx"
    p.write_bytes(b"esto no es un excel")
    with pytest.raises(DatasetCorrupt):
        load_dataset(p)


# --- #7 columnas requeridas y tipos
def test_missing_required_column_is_reported_as_error(mini_frames, write_xlsx):
    mini_frames["Dummy Metricas"] = mini_frames["Dummy Metricas"].drop(columns=["IA"])
    ds = load_dataset(write_xlsx(mini_frames))
    assert "advisor" in ds.missing_required
    assert "advisor" in " ".join(i.message for i in validate(ds) if i.level == "error")


@pytest.mark.parametrize("raw,expected", [("35%", 35.0), ("15,1", 15.1), (" 7 ", 7.0), (12, 12.0), ("1,234.5", 1234.5)])
def test_parse_number(raw, expected):
    assert parse_number(raw) == pytest.approx(expected)


def test_dirty_numeric_cell_does_not_crash_and_is_reported(mini_frames, write_xlsx):
    mini_frames["Dummy Metricas"]["share_of_wallet_pct"] = ["35%", "abc"]
    ds = load_dataset(write_xlsx(mini_frames))
    assert ds.clientes["share_of_wallet_pct"].iloc[0] == 35.0 and pd.isna(ds.clientes["share_of_wallet_pct"].iloc[1])
    assert ds.invalid_cells == {"share_of_wallet_pct": 1}
    assert "share_of_wallet_pct" in " ".join(i.message for i in validate(ds) if i.level == "warning")


# --- #8 wealth plan
def test_truthy_handles_text_bool_and_nan():
    s = pd.Series(["No", "Sí", True, False, "FALSE", None, float("nan"), "true"])
    assert list(truthy(s)) == [False, True, True, False, False, False, False, True]


# --- #10 búsqueda con caracteres especiales y filtros
def test_search_with_regex_characters_does_not_raise():
    from ui.pages.clientes import apply_filters
    df = pd.DataFrame({"rut": ["R1", "R2"], "cliente_label": ["R1 · Acme (SA)", "R2 · Otro +56"], "servicio": ["ADC"] * 2,
                       "perfil_norm": ["X"] * 2, "serie_mala": [False, False]})
    assert len(apply_filters(df, {"texto": "("}, date(2026, 10, 17))) == 1
    assert len(apply_filters(df, {"texto": "+56"}, date(2026, 10, 17))) == 1


def test_sin_wealth_plan_filter_uses_truthy_semantics():
    from ui.pages.clientes import apply_filters
    df = pd.DataFrame({"rut": list("ABCD"), "cliente_label": list("abcd"), "servicio": ["ADC"] * 4,
                       "perfil_norm": ["X"] * 4, "serie_mala": [False] * 4,
                       "tiene_wealth_plan": ["No", "Sí", True, None]})
    out = apply_filters(df, {"sin_wealth_plan": True}, date(2026, 10, 17))
    assert list(out["rut"]) == ["A", "D"]


# --- #14 inyección de fórmulas en CSV
def test_export_neutralizes_formula_injection(tmp_path):
    class S:
        def list_feedback(self):
            return [{"id": 1, "advisor": "IA", "pagina": "Home", "categoria": "x",
                     "texto": "=HYPERLINK(\"http://x\")", "importancia": "alta", "creado_en": "2026-10-17"}]

        def list_all_comments(self):
            return [{"id": 1, "rut": "R1", "advisor": "IA", "texto": "+cmd|' /C calc'!A0", "creado_en": "2026-10-17"}]

    fb, cm = export_feedback(S(), tmp_path, date(2026, 10, 17))
    assert "'=HYPERLINK" in fb.read_text(encoding="utf-8-sig")
    assert "'+cmd" in cm.read_text(encoding="utf-8-sig")


# --- #11 archivo faltante
def test_load_data_missing_file_raises_datasetnotfound(monkeypatch, tmp_path):
    from ui.context import load_data
    monkeypatch.setenv("WM_EXCEL", str(tmp_path / "no_existe.xlsx"))
    with pytest.raises(DatasetNotFound):
        load_data(date(2026, 10, 17))


# --- ISIN "n.a." en carteras: cada fondo sin ISIN debe tener su propio identificador
def test_carteras_without_isin_get_unique_ids_per_fund(mini_frames, write_xlsx):
    k = mini_frames["Dummy Carteras"]
    k.loc[0, "isin"], k.loc[1, "isin"] = "n.a.", "n.a."      # Fondo A y Fondo B, ambos sin ISIN
    ds = load_dataset(write_xlsx(mini_frames))
    ids = ds.carteras["isin"].tolist()
    assert ids[0] != ids[1] and ids[0].startswith("SIN_ISIN::") and "Fondo A" in ids[0]
    assert ids[2] == "ISIN_A2"  # los ISIN válidos no se tocan


# --- etiquetas de estado en la tabla de Clientes
def test_estado_cell_keeps_badges_as_html_not_escaped_text():
    from ui.components import Raw, html_table
    from ui.pages.clientes import _estado
    row = pd.Series({"serie_mala": True, "tiene_wealth_plan": False})
    cell = _estado(row, 200)
    assert isinstance(cell, Raw)
    out = html_table(pd.DataFrame({"Estado": [cell]}))
    assert "badge-bad" in out and "&lt;span" not in out
