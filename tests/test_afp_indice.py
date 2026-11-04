import numpy as np
import pandas as pd
import pytest

from wm.afp.fuente import FONDOS
from wm.afp.indice import indice_de_foto, indice_fondo, metricas, patrimonio_total, rent_anual, resumen
from wm.afp.snapshots import armar_foto


def _w(**cols):
    """DataFrame ancho con índice de fechas diarias desde 2026-01-01; None = sin dato."""
    n = len(next(iter(cols.values())))
    return pd.DataFrame({k: np.array(v, dtype=float) for k, v in cols.items()},
                        index=pd.date_range("2026-01-01", periods=n, freq="D"))


def test_una_sola_afp_el_indice_es_su_valor_cuota_rebasado():
    vc = _w(X=[50.0, 51.0, 49.0, 52.0])
    pat = _w(X=[10.0, 11.0, 12.0, 13.0])
    esperado = vc["X"] / vc["X"].iloc[0] * 100
    np.testing.assert_allclose(indice_fondo(vc, pat).values, esperado.values)


def test_dos_afp_retorno_ponderado_a_mano():
    vc = _w(X=[100.0, 110.0], Y=[100.0, 120.0])
    pat = _w(X=[300.0, 999.0], Y=[100.0, 999.0])   # pesos del día previo: 75 % y 25 %
    idx = indice_fondo(vc, pat)
    assert idx.iloc[0] == 100
    assert idx.iloc[1] == pytest.approx(100 * (1 + 0.75 * 0.10 + 0.25 * 0.20))


def test_afp_que_entra_a_mitad_no_mueve_el_indice_el_dia_que_aparece():
    vc = _w(X=[100.0, 101.0, 102.01, 103.0301], Y=[None, None, 1e9, 1.02e9])
    pat = _w(X=[100.0] * 4, Y=[None, None, 100.0, 100.0])
    idx = indice_fondo(vc, pat)
    assert idx.iloc[2] == pytest.approx(101.0 * 1.01 / 100 * 100)          # solo X el día 2
    assert idx.iloc[3] / idx.iloc[2] - 1 == pytest.approx(0.5 * 0.01 + 0.5 * 0.02)  # Y pesa desde el día 3


def test_afp_que_cierra_sigue_pesando_mientras_existio():
    vc = _w(X=[100.0, 100.0, 100.0, 110.0], Y=[100.0, 100.0, 120.0, None])
    pat = _w(X=[100.0] * 4, Y=[100.0, 100.0, 100.0, None])
    idx = indice_fondo(vc, pat)
    assert idx.iloc[2] / idx.iloc[1] - 1 == pytest.approx(0.5 * 0.0 + 0.5 * 0.20)  # Y pesa el día 2
    assert idx.iloc[3] / idx.iloc[2] - 1 == pytest.approx(0.10)                   # después solo X


def test_hueco_a_mitad_de_vida_no_distorsiona():
    vc = _w(X=[100.0, 100.0, None, None, None, 110.0], Y=[100.0] * 6)
    pat = _w(X=[100.0] * 6, Y=[100.0] * 6)
    idx = indice_fondo(vc, pat)
    assert idx.iloc[2] == idx.iloc[3] == idx.iloc[4] == idx.iloc[1]            # el hueco no mueve nada
    assert idx.iloc[5] / idx.iloc[4] - 1 == pytest.approx(0.5 * 0.10)          # el retorno entra una sola vez


def test_patrimonio_cero_o_faltante_no_entra_al_peso():
    vc = _w(X=[100.0, 110.0], Y=[100.0, 150.0], Z=[100.0, 130.0])
    pat = _w(X=[100.0, 1.0], Y=[0.0, 1.0], Z=[None, 1.0])
    idx = indice_fondo(vc, pat)
    assert np.isfinite(idx).all()
    assert idx.iloc[1] == pytest.approx(110.0)                                  # solo X tiene peso válido


def test_dia_sin_dato_arrastra_el_indice():
    vc = _w(X=[100.0, 110.0, None, 121.0])
    pat = _w(X=[100.0] * 4)
    idx = indice_fondo(vc, pat)
    assert idx.iloc[2] == idx.iloc[1] and np.isfinite(idx).all()


def _mensual(n=73):
    fechas = pd.date_range("2020-10-15", periods=n, freq=pd.DateOffset(months=1))
    return pd.Series(100 * 1.01 ** np.arange(n), index=fechas)


def test_metricas_con_serie_conocida():
    m = metricas(_mensual())
    anual = 1.01 ** 12 - 1
    assert m["rent_1m"] == pytest.approx(0.01)
    assert m["rent_3m"] == pytest.approx(1.01 ** 3 - 1)
    assert m["rent_1a"] == pytest.approx(anual)
    assert m["rent_3a"] == pytest.approx(anual)       # anualizada
    assert m["rent_5a"] == pytest.approx(anual)
    corta = metricas(_mensual(9))
    assert corta["rent_3m"] is not None and corta["rent_1a"] is None
    assert corta["rent_3a"] is None and corta["rent_5a"] is None


def test_metricas_ytd_usa_el_cierre_del_anio_anterior():
    assert metricas(_mensual())["rent_ytd"] == pytest.approx(1.01 ** 10 - 1)   # 2025-12-15 -> 2026-10-15
    mismo_anio = pd.Series([100.0, 101.0, 102.0], index=pd.to_datetime(["2026-01-15", "2026-02-15", "2026-03-15"]))
    assert metricas(mismo_anio)["rent_ytd"] is None                            # sin cierre del año anterior


def test_rent_anual_omite_el_primer_anio_parcial_e_incluye_el_actual():
    r = rent_anual(_mensual())
    assert list(r.index) == [2021, 2022, 2023, 2024, 2025, 2026]
    assert r.loc[2022] == pytest.approx(1.01 ** 12 - 1)
    assert r.loc[2026] == pytest.approx(1.01 ** 10 - 1)


def _foto():
    fechas = pd.bdate_range("2025-01-01", periods=400)
    filas_vc, filas_pat = [], []
    for fi, f in enumerate(FONDOS):
        for afp, pat0, vive in (("X", 300.0, 400), ("Y", 100.0, 400), ("Z", 50.0, 200)):
            for i, d in enumerate(fechas[:vive]):
                filas_vc.append({"fecha": d, "fondo": f, "afp": afp, "valor": 100 * (1 + 0.0004 * (fi + 1)) ** i})
                filas_pat.append({"fecha": d, "fondo": f, "afp": afp, "valor": pat0 * (1 + fi)})
    return armar_foto(pd.DataFrame(filas_vc), pd.DataFrame(filas_pat))


def test_resumen_cinco_fondos_pesos_suman_uno():
    foto = _foto()
    r = resumen(foto)
    assert list(r["fondo"]) == FONDOS
    assert r["peso_sistema"].sum() == pytest.approx(1.0)
    assert (r["n_afp"] == 2).all()                        # Z cerró
    assert r.loc[0, "patrimonio"] == pytest.approx(400.0)
    assert r["rent_1a"].notna().all()


def test_indice_de_foto_y_patrimonio_total():
    foto = _foto()
    idx = indice_de_foto(foto, "C")
    assert idx.iloc[0] == 100 and idx.is_monotonic_increasing
    pt = patrimonio_total(foto, "C")
    assert pt.iloc[0] == pytest.approx(450.0 * 3) and pt.iloc[-1] == pytest.approx(400.0 * 3)


@pytest.mark.parametrize("malo", [0.0, -1.0])
def test_valor_cuota_cero_o_negativo_no_corrompe_el_indice(malo):
    vc = _w(X=[10.0, malo, 10.0, 11.0], Y=[100.0, 101.0, 102.0, 103.0])
    pat = _w(X=[100.0] * 4, Y=[100.0] * 4)
    idx = indice_fondo(vc, pat)
    assert np.isfinite(idx).all() and (idx > 0).all()
