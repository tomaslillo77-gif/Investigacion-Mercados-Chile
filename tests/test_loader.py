from pathlib import Path

import pytest

from wm.loader import (
    DatasetNotFound,
    load_dataset,
    normalize_rut,
    normalize_servicio,
    parse_money,
)

REAL = Path(__file__).resolve().parent.parent / "data" / "Engine WM Dummy.xlsx"


def test_servicio_variants_normalize_to_same_label():
    assert normalize_servicio("Cartera gestionada") == "Cartera Gestionada"
    assert normalize_servicio("Cartera Gestionada") == "Cartera Gestionada"
    assert normalize_servicio("Asesoría") == "ASE"


def test_unknown_servicio_is_sin_clasificar():
    assert normalize_servicio("Foo") == "Sin clasificar"
    assert normalize_servicio(None) == "Sin clasificar"


def test_parse_money_handles_thousands_and_currency_suffix():
    assert parse_money("31,980,049,938.00  $") == 31980049938.0
    assert parse_money(12.5) == 12.5
    assert parse_money("abc") != parse_money("abc")  # NaN


def test_normalize_rut_strips_and_uppercases():
    assert normalize_rut(" rut_1 ") == "RUT_1"


def test_mini_dataset_loads_and_normalizes(mini_xlsx):
    ds = load_dataset(mini_xlsx)
    assert list(ds.clientes["rut"]) == ["RUT_1", "RUT_2"]
    assert list(ds.clientes["servicio"]) == ["Cartera Gestionada", "ADC"]
    assert ds.missing_sheets == []
    assert ds.posiciones["valor_clp"].sum() == 1750
    assert set(ds.posiciones["rut"]) == {"RUT_1", "RUT_2"}


@pytest.mark.skipif(not REAL.exists(), reason="real dummy excel missing")
def test_load_dataset_real_file_has_expected_sheets():
    ds = load_dataset(REAL)
    assert len(ds.clientes) == 99  # 100 filas, 1 RUT duplicado
    assert len(ds.duplicate_ruts) == 1
    assert ds.missing_sheets == []
    assert ds.clientes["servicio"].notna().all()


def test_missing_sheet_is_reported_not_raised(mini_frames, write_xlsx):
    mini_frames.pop("Dummy Posiciones")
    ds = load_dataset(write_xlsx(mini_frames))
    assert ds.missing_sheets == ["Dummy Posiciones"]
    assert len(ds.posiciones) == 0


def test_missing_file_raises_datasetnotfound(tmp_path):
    with pytest.raises(DatasetNotFound):
        load_dataset(tmp_path / "nope.xlsx")


def test_posiciones_gp_and_rent_text_values_are_parsed_to_numbers(mini_frames, write_xlsx):
    pos = mini_frames["Dummy Posiciones"]
    pos["G/P no Realizada"] = ["1,200.50  $", "-300 $", "N/A"]
    pos["Rent. no Realizada"] = ["1.5%", "-0,5%", None]
    ds = load_dataset(write_xlsx(mini_frames))
    assert ds.posiciones["gp_no_realizada"].iloc[:2].tolist() == [1200.5, -300.0]
    assert ds.posiciones["gp_no_realizada"].isna().iloc[2]
    assert ds.posiciones["rent_no_realizada"].iloc[:2].tolist() == [1.5, -0.5]


def test_normalize_beneficio_keeps_107_108_and_defaults_to_dash():
    from wm.loader import normalize_beneficio
    assert [normalize_beneficio(v) for v in (107, "108", "Art. 107 LIR", "108 LIR", "-", None, float("nan"), "")] == \
        ["107", "108", "107", "108", "-", "-", "-", "-"]


def test_flow_sheet_is_loaded_with_biweekly_periods():
    import pandas as pd
    ds = load_dataset(Path(__file__).resolve().parent.parent / "data" / "Engine WM Dummy Completo.xlsx")
    assert ds.flujos is not None and ds.flujos["periodo"].nunique() == 26
    p = sorted(ds.flujos["periodo"].unique())
    assert (pd.to_datetime(p[1]) - pd.to_datetime(p[0])).days == 14


@pytest.mark.parametrize("crudo, esperado", [
    ("12.345.678-9", "123456789"),
    ("12345678-9", "123456789"),
    ("12.345.678-k", "12345678K"),
    (" 12 345 678-9 ", "123456789"),
    (12345678.0, "12345678"),          # Excel guarda el RUT numérico como decimal
    (12345678, "12345678"),
    ("12345678.0", "12345678"),
    ("RUT_84941022", "RUT_84941022"),   # los códigos del Excel sintético no cambian
])
def test_normalize_rut_unifica_formatos(crudo, esperado):
    assert normalize_rut(crudo) == esperado


def test_rut_con_distinto_formato_entre_hojas_calza(mini_frames, write_xlsx):
    mini_frames["Dummy Metricas"]["RUT Normalizado"] = ["12.345.678-9", "9.876.543-K"]
    mini_frames["Dummy Posiciones"]["RUT Normalizado"] = ["123456789", "123456789", "9876543K"]
    ds = load_dataset(write_xlsx(mini_frames))
    assert set(ds.posiciones["rut"]) <= set(ds.clientes["rut"])
    assert len(ds.posiciones) == 3


def test_encabezados_con_espacios_y_tildes_distintas_se_reconocen(mini_frames, write_xlsx):
    m = mini_frames["Dummy Metricas"]
    m.columns = [c.replace("Última Reunión", "Ultima  Reunion ").replace("Valor de Mercado (CLP)", " valor de mercado (clp)") for c in m.columns]
    ds = load_dataset(write_xlsx(mini_frames))
    assert ds.missing_required == []
    assert list(ds.clientes["aum_clp"]) == [1000, 5000]
    assert ds.clientes["ultima_reunion"].notna().sum() == 1


def test_rut_duplicado_se_detecta_aunque_la_columna_tenga_otro_nombre(mini_frames, write_xlsx, tmp_path, monkeypatch):
    mini_frames["Dummy Metricas"] = mini_frames["Dummy Metricas"].rename(columns={"RUT Normalizado": "RUT del cliente"})
    mini_frames["Dummy Metricas"]["RUT del cliente"] = ["RUT_1", "RUT_1"]
    local = tmp_path / "local"
    local.mkdir()
    (local / "excel.yaml").write_text("columnas_clientes:\n  RUT del cliente: rut\n", encoding="utf-8")
    monkeypatch.setenv("WM_CONFIG_DIR", str(local))
    ds = load_dataset(write_xlsx(mini_frames))
    assert ds.duplicate_ruts == ["RUT_1"]
