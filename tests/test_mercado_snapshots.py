import shutil
from datetime import date

import pandas as pd
import pandas.testing as pdt

from scripts.actualizar_mercado import main
from tests.conftest import _write_cmf
from wm.mercado.cmf import leer_cmf
from wm.mercado.snapshots import cargar_foto, guardar_foto, listar_fotos


def test_guardar_y_cargar_ida_y_vuelta(cmf_dir, tmp_path):
    foto = leer_cmf(cmf_dir)
    guardar_foto(foto, tmp_path / "m")
    otra = cargar_foto(tmp_path / "m")
    assert otra.fecha_corte == date(2026, 6, 30)
    pdt.assert_frame_equal(otra.series, foto.series, check_dtype=False)
    pdt.assert_frame_equal(otra.cartera, foto.cartera, check_dtype=False)


def test_no_sobrescribe_otras_fotos(cmf_dir, tmp_path):
    base = tmp_path / "m"
    foto = leer_cmf(cmf_dir)
    guardar_foto(foto, base)
    sept = leer_cmf(cmf_dir)
    sept.fecha_corte = date(2026, 9, 30)
    guardar_foto(sept, base)
    assert listar_fotos(base) == [date(2026, 6, 30), date(2026, 9, 30)]
    assert cargar_foto(base, date(2026, 6, 30)).fecha_corte == date(2026, 6, 30)
    assert cargar_foto(base).fecha_corte == date(2026, 9, 30)


def test_recargar_mismo_corte_reemplaza(cmf_dir, tmp_path):
    base = tmp_path / "m"
    guardar_foto(leer_cmf(cmf_dir), base)
    guardar_foto(leer_cmf(cmf_dir), base)
    assert listar_fotos(base) == [date(2026, 6, 30)]


def test_cargar_sin_fotos_devuelve_none(tmp_path):
    assert cargar_foto(tmp_path / "no_existe") is None
    (tmp_path / "vacia").mkdir()
    assert cargar_foto(tmp_path / "vacia") is None
    assert listar_fotos(tmp_path / "vacia") == []


def test_script_ok_y_rechaza_desalineadas(cmf_dir, tmp_path, capsys):
    out = tmp_path / "out"
    assert main(["--cmf-dir", str(cmf_dir), "--out", str(out)]) == 0
    assert (out / "2026-06-30" / "series.csv").exists()
    assert "2026-06-30" in capsys.readouterr().out
    malo = _write_cmf(tmp_path / "malo", fecha_cartera=202603)
    out2 = tmp_path / "out2"
    assert main(["--cmf-dir", str(malo), "--out", str(out2)]) == 1
    assert not out2.exists() or not list(out2.iterdir())


def test_script_yahoo_guarda_foto_y_completa_tickers(tmp_path, monkeypatch, capsys):
    import scripts.actualizar_mercado as sc
    from tests.test_mercado_internacionales import CAT, FakeYahoo
    from wm.mercado import equivalencias as eq
    from wm.mercado.internacionales import cargar_yahoo
    monkeypatch.setattr(sc, "_cargar_catalogo", lambda excel: CAT)
    monkeypatch.setattr(sc, "_yahoo", lambda cache_dir: FakeYahoo())
    equiv = tmp_path / "e.csv"
    eq.guardar(pd.DataFrame([{"instrumento_catalogo": "Core S&P 500 UCIT", "isin": "IE00B5BMR087",
                              "serie_catalogo": "ETF"}]).reindex(columns=eq.EQUIV_COLS), equiv)
    args = ["--fuente", "yahoo", "--externos", str(tmp_path / "ext"), "--equivalencias", str(equiv)]
    assert sc.main(args) == 0
    fecha, df = cargar_yahoo(tmp_path / "ext" / "yahoo")
    assert len(df) == 4 and "Yahoo" in set(df["estado"])
    assert eq.cargar(equiv).loc[0, "ticker_yahoo"] == "CSSPX.MI"
    assert "Yahoo" in capsys.readouterr().out


def test_script_yahoo_sin_yfinance_falla_con_mensaje(tmp_path, monkeypatch, capsys):
    import scripts.actualizar_mercado as sc
    from tests.test_mercado_internacionales import CAT
    from wm.mercado.fuentes.base import FuenteNoDisponible

    class Roto:
        def buscar_isin(self, isin):
            raise FuenteNoDisponible("Falta instalar yfinance")
    monkeypatch.setattr(sc, "_cargar_catalogo", lambda excel: CAT)
    monkeypatch.setattr(sc, "_yahoo", lambda cache_dir: Roto())
    assert sc.main(["--fuente", "yahoo", "--externos", str(tmp_path / "e"), "--equivalencias", str(tmp_path / "q.csv")]) == 1
    assert "yfinance" in capsys.readouterr().out
