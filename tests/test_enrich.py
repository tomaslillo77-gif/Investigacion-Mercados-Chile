from datetime import date

import pandas as pd

from wm.enrich import enrich_clientes
from wm.loader import load_dataset

HOY = date(2026, 10, 17)


def test_client_with_positions_gets_architecture_and_flags(mini_xlsx):
    ds = load_dataset(mini_xlsx)
    out = enrich_clientes(ds, HOY).set_index("rut")
    assert out.loc["RUT_1", "arquitectura"] == "abierta_pesos"
    assert out.loc["RUT_1", "cobertura_arq"] == 1.0
    assert bool(out.loc["RUT_1", "arquitectura_inferida"]) is True
    assert out.loc["RUT_1", "serie_mala"] in (True, False)


def test_client_without_positions_has_no_architecture(mini_frames, write_xlsx):
    mini_frames["Dummy Posiciones"] = mini_frames["Dummy Posiciones"].iloc[0:0]
    out = enrich_clientes(load_dataset(write_xlsx(mini_frames)), HOY)
    assert out["arquitectura"].isna().all()
    assert (out["cobertura_arq"] == 0.0).all()
    assert not out["serie_mala"].any()


def test_declared_architecture_column_wins(mini_frames, write_xlsx):
    mini_frames["Dummy Metricas"]["arquitectura"] = ["abierta_dolares", None]
    out = enrich_clientes(load_dataset(write_xlsx(mini_frames)), HOY).set_index("rut")
    assert out.loc["RUT_1", "arquitectura"] == "abierta_dolares"
    assert bool(out.loc["RUT_1", "arquitectura_inferida"]) is False


def test_serie_mala_adds_ingresos_en_juego(mini_frames, write_xlsx):
    # RUT_2 posee ISIN de otra arquitectura con mayor comisión que el modelo de la suya
    k = mini_frames["Dummy Carteras"]
    extra = pd.DataFrame({"arquitectura": ["otra"], "perfil": ["Equilibrado"], "instrumento": ["Fondo C"],
                          "diccionario": ["Fondo C"], "isin": ["ISIN_C_CARA"], "serie": ["C"],
                          "peso_objetivo": [0.2], "comision": [0.03], "pct_uf": [0], "moneda": ["USD"],
                          "Perfil Normalizado": ["EQUILIBRADO"]})
    mini_frames["Dummy Carteras"] = pd.concat([k, extra], ignore_index=True)
    pos = mini_frames["Dummy Posiciones"]
    nueva = pos.iloc[[2]].copy()
    nueva["Isin"], nueva["VM Numérico"] = "ISIN_C_CARA", 100
    pos.loc[2, "VM Numérico"] = 750
    mini_frames["Dummy Posiciones"] = pd.concat([pos, nueva], ignore_index=True)
    out = enrich_clientes(load_dataset(write_xlsx(mini_frames)), HOY).set_index("rut")
    assert bool(out.loc["RUT_2", "serie_mala"]) is True
    assert out.loc["RUT_2", "ingresos_en_juego"] > 0
