import pandas as pd
import pytest

from wm.afp.fuente import FONDOS, FuenteAfpNoDisponible, a_largo, descargar, parsear


def test_parsear_coma_decimal_y_celdas_vacias():
    df = parsear("Fecha;A;B\n2026-10-14;100,5;\n2026-10-15;101,0;7,25")
    assert len(df) == 2
    assert df.loc["2026-10-15", "B"] == 7.25
    assert pd.isna(df.loc["2026-10-14", "B"])
    assert df.index.is_monotonic_increasing and str(df.index.dtype).startswith("datetime64")


def test_parsear_normaliza_nombres_de_afp():
    assert list(parsear("Fecha; Habitat ;PROVIDA\n2026-10-15;1;2").columns) == ["HABITAT", "PROVIDA"]


def test_parsear_rechaza_html():
    with pytest.raises(FuenteAfpNoDisponible):
        parsear("<html>404</html>")


def test_a_largo_descarta_nan():
    largo = a_largo(parsear("Fecha;A;B\n2026-10-14;100,5;\n2026-10-15;101,0;7,25"), "C")
    assert list(largo.columns) == ["fecha", "fondo", "afp", "valor"]
    assert len(largo) == 3 and set(largo["fondo"]) == {"C"}


def _csv(inicio="2012-01-01", fin="2026-10-15"):
    fechas = pd.date_range(inicio, fin, freq="30D")
    return "Fecha;X;Y\n" + "\n".join(f"{d:%Y-%m-%d};100,5;200,25" for d in fechas) + f"\n{fin};101,0;201,0\n"


def test_descargar_aplica_ventana_y_une_los_cinco_fondos():
    urls = []

    def leer(url):
        urls.append(url)
        return _csv()
    cfg = {"url_base": "https://x/data", "ventana_anios": 10}
    vc, pat = descargar(cfg, leer=leer)
    assert vc["fecha"].min() >= pd.Timestamp("2016-10-15")
    assert set(vc["fondo"]) == set(FONDOS) == set(pat["fondo"])
    assert "https://x/data/vcfA.csv" in urls and "https://x/data/patfE.csv" in urls


def test_descargar_traduce_errores_de_red():
    def leer(url):
        raise OSError("sin red")
    with pytest.raises(FuenteAfpNoDisponible):
        descargar({"url_base": "https://x", "ventana_anios": 10}, leer=leer)


def test_parsear_descarta_fechas_duplicadas_y_deja_la_ultima():
    df = parsear("Fecha;A\n2026-10-14;1,0\n2026-10-15;2,0\n2026-10-15;3,0")
    assert len(df) == 2 and df.loc["2026-10-15", "A"] == 3.0
