from datetime import date

import pandas as pd
import pytest

from wm.afp.fuente import FONDOS
from wm.afp.snapshots import FechasDesalineadas, Foto, armar_foto, cargar_foto, guardar_foto, listar_fotos


def _largo(fin="2026-10-15", valor=100.0, sin_ultimo=None):
    filas = []
    for f in FONDOS:
        fechas = pd.date_range(end=fin, periods=3, freq="D")
        if f == sin_ultimo:
            fechas = fechas[:-1]
        for d in fechas:
            filas.append({"fecha": d, "fondo": f, "afp": "X", "valor": valor})
    return pd.DataFrame(filas)


def test_guardar_y_cargar_ida_y_vuelta(tmp_path):
    foto = armar_foto(_largo(), _largo(valor=5.0))
    guardar_foto(foto, tmp_path)
    leida = cargar_foto(tmp_path)
    assert leida.fecha_corte == date(2026, 10, 15) == foto.fecha_corte
    pd.testing.assert_frame_equal(leida.valor_cuota, foto.valor_cuota)
    pd.testing.assert_frame_equal(leida.patrimonio, foto.patrimonio)


def test_mismo_dia_reemplaza_y_otro_dia_no_toca(tmp_path):
    guardar_foto(armar_foto(_largo("2026-10-14"), _largo("2026-10-14")), tmp_path)
    guardar_foto(armar_foto(_largo("2026-10-15"), _largo("2026-10-15")), tmp_path)
    guardar_foto(armar_foto(_largo("2026-10-15", valor=999.0), _largo("2026-10-15")), tmp_path)
    assert listar_fotos(tmp_path) == [date(2026, 10, 14), date(2026, 10, 15)]
    assert (cargar_foto(tmp_path).valor_cuota["valor"] == 999.0).all()
    assert (cargar_foto(tmp_path, date(2026, 10, 14)).valor_cuota["valor"] == 100.0).all()


def test_cargar_sin_fotos_devuelve_none(tmp_path):
    assert cargar_foto(tmp_path / "no_existe") is None


def test_cargar_fecha_inexistente_devuelve_none(tmp_path):
    guardar_foto(armar_foto(_largo(), _largo()), tmp_path)
    assert cargar_foto(tmp_path, date(2020, 1, 1)) is None


def test_desalineada_valor_cuota_vs_patrimonio_se_rechaza():
    with pytest.raises(FechasDesalineadas):
        armar_foto(_largo(), _largo(sin_ultimo="C"))


def test_desalineada_entre_fondos_se_rechaza():
    with pytest.raises(FechasDesalineadas):
        armar_foto(_largo(sin_ultimo="E"), _largo(sin_ultimo="E"))


def test_listar_ignora_carpetas_ajenas(tmp_path):
    guardar_foto(armar_foto(_largo(), _largo()), tmp_path)
    (tmp_path / "basura").mkdir()
    (tmp_path / "suelto.txt").write_text("x")
    assert listar_fotos(tmp_path) == [date(2026, 10, 15)]


def _dos_afp(ult_x=True, ult_y=True, fondos=FONDOS):
    filas = []
    for f in fondos:
        for afp, ultimo in (("X", ult_x), ("Y", ult_y or f != "A")):
            fechas = pd.date_range(end="2026-10-15", periods=3, freq="D")
            for d in (fechas if ultimo else fechas[:-1]):
                filas.append({"fecha": d, "fondo": f, "afp": afp, "valor": 100.0})
    return pd.DataFrame(filas)


def test_ultimo_dia_incompleto_se_rechaza():
    """Falta una AFP en la última fila de un fondo (en ambos archivos): no es un corte válido."""
    with pytest.raises(FechasDesalineadas):
        armar_foto(_dos_afp(ult_y=False), _dos_afp(ult_y=False))


def test_ultimo_dia_con_distintas_afp_entre_valor_cuota_y_patrimonio_se_rechaza():
    with pytest.raises(FechasDesalineadas):
        armar_foto(_dos_afp(), _dos_afp(ult_y=False))


def test_fondo_vacio_en_ambos_archivos_se_rechaza():
    with pytest.raises(FechasDesalineadas):
        armar_foto(_dos_afp(fondos=FONDOS[:-1]), _dos_afp(fondos=FONDOS[:-1]))
