import pandas as pd

from wm.mercado import equivalencias as eq

SERIES = pd.DataFrame({"fo_run": [8011, 8011, 5555], "fm_serie": ["I2", "H", "A"],
                       "nombre_fondo": ["VISION MONEY MARKET", "VISION MONEY MARKET", "SECURITY EMERGING M."]})


def _cat(*filas):
    return pd.DataFrame(filas, columns=["instrumento", "isin", "serie"])


def test_coincidencia_exacta_se_cruza():
    p = eq.proponer(_cat(("Visión Money Market", "CL0000000001", "I2")), SERIES)
    assert p.loc[0, "fo_run"] == 8011 and p.loc[0, "fm_serie"] == "I2"
    assert p.loc[0, "confianza"] >= 0.9


def test_nombre_parecido_pero_distinto_no_se_cruza():
    p = eq.proponer(_cat(("Fidelity Emerging Asia", "LU0390711777", "Y")), SERIES)
    assert pd.isna(p.loc[0, "fo_run"]) and pd.isna(p.loc[0, "confianza"])


def test_serie_inexistente_no_se_cruza():
    p = eq.proponer(_cat(("Vision Money Market", "CL0000000001", "Z")), SERIES)
    assert pd.isna(p.loc[0, "fo_run"])


def test_completar_conserva_correcciones_manuales():
    existente = eq.proponer(_cat(("Fidelity Emerging Asia", "LU0390711777", "Y")), SERIES)
    existente.loc[0, ["fo_run", "fm_serie"]] = [5555, "A"]  # corrección manual
    nueva = eq.proponer(_cat(("Fidelity Emerging Asia", "LU0390711777", "Y"),
                             ("Vision Money Market", "CL0000000001", "H")), SERIES)
    r = eq.completar(existente, nueva)
    assert len(r) == 2
    assert r.loc[r.instrumento_catalogo == "Fidelity Emerging Asia", "fo_run"].iloc[0] == 5555
    assert r.loc[r.instrumento_catalogo == "Vision Money Market", "fo_run"].iloc[0] == 8011


def test_ida_y_vuelta_csv(tmp_path):
    p = eq.proponer(_cat(("Visión Money Market", "CL0000000001", "I2"), ("Otro", "LU1", "C")), SERIES)
    eq.guardar(p, tmp_path / "e.csv")
    r = eq.cargar(tmp_path / "e.csv")
    assert list(r.columns) == eq.EQUIV_COLS and len(r) == 2
    assert r.loc[0, "fo_run"] == 8011 and pd.isna(r.loc[1, "fo_run"])
    assert list(eq.cargar(tmp_path / "no.csv").columns) == eq.EQUIV_COLS
