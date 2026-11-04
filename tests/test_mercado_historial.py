from datetime import date

import pandas as pd

from wm.mercado import historial as h
from wm.mercado.cmf import leer_cmf
from wm.mercado.snapshots import guardar_foto


def test_serie_patrimonio_ordenada(cmf_dir):
    s = h.serie_patrimonio(leer_cmf(cmf_dir), 8011, "I2")
    assert list(s.columns) == ["fecha_mes", "patrimonio", "participes"]
    assert list(s["fecha_mes"]) == [202605, 202606] and s["participes"].tolist() == [10, 12]


def test_serie_patrimonio_inexistente_vacia(cmf_dir):
    assert h.serie_patrimonio(leer_cmf(cmf_dir), 1, "Z").empty


def _dos_fotos(cmf_dir, base):
    f1 = leer_cmf(cmf_dir)
    guardar_foto(f1, base)
    f2 = leer_cmf(cmf_dir)
    f2.fecha_corte = date(2026, 9, 30)
    f2.series.loc[f2.series.fo_run == 8915, "rent_1a"] = 20.0
    guardar_foto(f2, base)


def test_cambio_entre_fotos_calcula_delta(cmf_dir, tmp_path):
    _dos_fotos(cmf_dir, tmp_path / "m")
    c = h.cambio_entre_fotos(tmp_path / "m", 8915, "I")
    assert c["fecha_corte"].tolist() == [date(2026, 6, 30), date(2026, 9, 30)]
    assert round(c["delta_rent_1a"].iloc[1], 4) == round(20.0 - 17.4856, 4)
    assert pd.isna(c["delta_rent_1a"].iloc[0])


def test_cambio_con_una_foto_no_falla(cmf_dir, tmp_path):
    guardar_foto(leer_cmf(cmf_dir), tmp_path / "m")
    c = h.cambio_entre_fotos(tmp_path / "m", 8915, "I")
    assert len(c) == 1 and pd.isna(c["delta_rent_1a"].iloc[0])


def test_cambio_sin_fotos_vacio(tmp_path):
    assert h.cambio_entre_fotos(tmp_path / "nada", 8915, "I").empty
