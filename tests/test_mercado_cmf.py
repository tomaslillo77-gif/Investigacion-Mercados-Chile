from datetime import date

import pandas as pd
import pytest

from tests.conftest import _write_cmf
from wm.mercado.cmf import ArchivoCMFFaltante, FechasDesalineadas, leer_cmf


def test_series_une_costos_y_rentabilidades(cmf_dir):
    s = leer_cmf(cmf_dir).series.set_index(["fo_run", "fm_serie"])
    assert len(s) == 3
    assert s.loc[(8011, "I2"), "tac"] == 0.72
    assert s.loc[(8915, "I"), "rent_1a"] == 17.4856
    assert pd.isna(s.loc[(8915, "I"), "tac"])
    assert pd.isna(s.loc[(8011, "I2"), "rent_1a"])
    assert s.loc[(8011, "I2"), "participes"] == 12  # última fila de Tendencias


def test_peso_cartera_suma_uno_por_fondo(cmf_dir):
    c = leer_cmf(cmf_dir).cartera
    assert c.groupby("fo_run").peso.sum().round(6).to_dict() == {8011: 1.0, 9999: 1.0}
    assert sorted(c[c.fo_run == 8011].peso.round(2)) == [0.3, 0.7]


def test_fecha_corte_es_fin_de_mes(cmf_dir):
    assert leer_cmf(cmf_dir).fecha_corte == date(2026, 6, 30)


def test_fechas_desalineadas_se_rechaza(tmp_path):
    carpeta = _write_cmf(tmp_path / "x", fecha_cartera=202603)
    with pytest.raises(FechasDesalineadas) as e:
        leer_cmf(carpeta)
    assert "carteras" in str(e.value) and "202603" in str(e.value)


def test_archivo_faltante(cmf_dir):
    (cmf_dir / "Comparador de Costos CMF.xlsx").unlink()
    with pytest.raises(ArchivoCMFFaltante) as e:
        leer_cmf(cmf_dir)
    assert "costos" in str(e.value)
