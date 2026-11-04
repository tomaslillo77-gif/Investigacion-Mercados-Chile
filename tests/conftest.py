from pathlib import Path

import pandas as pd
import pytest

SHEETS = {
    "metricas": "Dummy Metricas",
    "posiciones": "Dummy Posiciones",
    "carteras": "Dummy Carteras",
}


@pytest.fixture(autouse=True)
def _sin_config_local(tmp_path_factory, monkeypatch):
    """Las pruebas usan solo config/*.yaml del repositorio; los ajustes de config/local de cada computador no las alteran."""
    monkeypatch.setenv("WM_CONFIG_DIR", str(tmp_path_factory.mktemp("sin_config_local")))


def _write(path: Path, frames: dict[str, pd.DataFrame]) -> None:
    with pd.ExcelWriter(path) as xw:
        for name, df in frames.items():
            pd.DataFrame([["TITULO"]]).to_excel(xw, sheet_name=name, index=False, header=False)
            df.to_excel(xw, sheet_name=name, index=False, startrow=2)


@pytest.fixture
def mini_frames() -> dict[str, pd.DataFrame]:
    metricas = pd.DataFrame({
        "RUT": ["RUT_1", "RUT_2"],
        "Entidad": ["E1", "E2"],
        "Household": ["H1", "H2"],
        "Servicio": ["Cartera gestionada", "ADC"],
        "WM": ["WM_1", "WM_1"],
        "IA": ["IA_1", "IA_2"],
        "Perfil de Riesgo": ["Equilibrado", "OTRO"],
        "Última Reunión": [pd.Timestamp("2026-08-01"), None],
        "Valor de Mercado (CLP)": [1000, 5000],
        "CAD (USD MM)": [1.0, 5.0],
        "RUT Normalizado": [" rut_1", "RUT_2 "],
        "Perfil Normalizado": ["EQUILIBRADO", "OTRO"],
    })
    posiciones = pd.DataFrame({
        "Cliente (ID)": ["RUT_1", "RUT_1", "RUT_2"],
        "Instrumento": ["Fondo A", "Fondo B", "Fondo C"],
        "Tipo": ["Renta Fija Local", "Renta Variable Local", "Renta Fija Local"],
        "Isin": ["ISIN_A", "ISIN_B", "ISIN_C"],
        "Valor de Mercado": ["1,000.00  $", "500.00  $", "250.00  $"],
        "G/P no Realizada": [10, -5, 0],
        "Rent. no Realizada": [0.01, -0.01, 0.0],
        "RUT Normalizado": ["RUT_1", "RUT_1", "RUT_2"],
        "VM Numérico": [1000, 500, 250],
    })
    carteras = pd.DataFrame({
        "arquitectura": ["abierta_pesos"] * 4,
        "perfil": ["Equilibrado"] * 4,
        "instrumento": ["Fondo A", "Fondo B", "Fondo A", "Fondo C"],
        "diccionario": ["Fondo A", "Fondo B", "Fondo A", "Fondo C"],
        "isin": ["ISIN_A", "ISIN_B", "ISIN_A2", "ISIN_C"],
        "serie": ["I", "C", "Wealth", "I"],
        "peso_objetivo": [0.4, 0.3, 0.1, 0.2],
        "comision": [0.01, 0.012, 0.008, 0.01],
        "pct_uf": [0, 0, 0, 0],
        "moneda": ["CLP", "CLP", "CLP", "USD"],
        "Perfil Normalizado": ["EQUILIBRADO"] * 4,
    })
    return {SHEETS["metricas"]: metricas, SHEETS["posiciones"]: posiciones, SHEETS["carteras"]: carteras}


@pytest.fixture
def mini_xlsx(tmp_path: Path, mini_frames) -> Path:
    p = tmp_path / "mini.xlsx"
    _write(p, mini_frames)
    return p


@pytest.fixture
def write_xlsx(tmp_path: Path):
    def _w(frames: dict[str, pd.DataFrame]) -> Path:
        p = tmp_path / "custom.xlsx"
        _write(p, frames)
        return p
    return _w


import os  # noqa: E402

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@pytest.fixture
def test_dsn() -> str:
    dsn = os.environ.get("WM_TEST_DSN")
    if not dsn:
        pytest.skip("WM_TEST_DSN no definido: tests de PostgreSQL omitidos")
    return dsn


def _write_cmf(carpeta: Path, fecha_cartera: int = 202606) -> Path:
    """Recorte sintético de los 4 Excel del Portal de Fondos Mutuos de la CMF, con sus hojas y columnas reales."""
    carpeta.mkdir(parents=True, exist_ok=True)
    rent = pd.DataFrame({
        "fo_run": [8915, 8011], "fm_serie": ["I", "H"],
        "rent_nominal_1a": [17.4856, 4.1], "rent_nominal_3a_ann": [23.4697, 5.0],
        "rent_nominal_5a_ann": [15.0025, 5.5], "rent_nominal_10a_ann": [16.9049, None],
        "rent_nominal_ytd": [8.8237, 2.0], "nombre_fondo": ["ACCIONES GLOBAL", "VISION MONEY MARKET"],
        "nombre_agf": ["AGF UNO", "PRINCIPAL"], "familia_estudios": ["Accionario internacional", "Deuda < 90 dias"],
        "fm_fecha": [20260630, 20260630]})
    costos = pd.DataFrame({
        "fo_run": [8011, 8011], "fm_serie": ["I2", "H"], "pat_total": [5828.28, 11726.87],
        "moneda_funcional": ["$$", "$$"], "familia_estudios": ["Deuda < 90 dias"] * 2,
        "clase_inversionista": ["Alto Patrimonio", "APV"], "nombre_fondo": ["VISION MONEY MARKET"] * 2,
        "nombre_agf": ["PRINCIPAL"] * 2, "tac_sintetica": [0.72, 1.07], "fm_fecha_num": [20260630, 20260630]})
    tend = pd.DataFrame({
        "fo_run": [8011, 8011, 8011, 8915], "fm_serie": ["I2", "I2", "H", "I"],
        "patrimonio_fm": [5000.0, 5828.28, 11726.87, 900.0], "participes_fm": [10, 12, 30, 5],
        "tac_total": [0.7, 0.72, 1.07, 1.5], "fecha_mes": [202605, 202606, 202606, 202606],
        "nombre_fondo": ["VISION MONEY MARKET"] * 3 + ["ACCIONES GLOBAL"], "rut_agf": [1, 1, 1, 2]})
    cart = pd.DataFrame({
        "fo_run": [8011, 8011, 9999], "nemotecnico": ["A", "B", "C"],
        "nombre_emisor": ["BANCO X", "BANCO Y", "EMISOR Z"], "pais_emisor": ["CL", "CL", "US"],
        "val_cierr": [30.0, 70.0, 5.0], "fecha_mes": [fecha_cartera] * 3,
        "clasificacion_instrumentos_txt": ["Depósitos local", "Bancario local", "Acciones extranjeras"],
        "nombre_pais_emisor": ["CHILE", "CHILE", "ESTADOS UNIDOS"],
        "nombre_fondo": ["VISION MONEY MARKET"] * 2 + ["FONDO NUEVE"], "nombre_agf": ["PRINCIPAL"] * 2 + ["AGF UNO"]})
    for nombre, hoja, df in (("Rentabilidades CMF", "rentabilidades_por_serie_fondo", rent),
                             ("Comparador de Costos CMF", "datos_costos", costos),
                             ("Tendencias de Mercado CMF", "datos", tend),
                             ("Carteras Fondos Mutuos CMF", "datos", cart)):
        df.to_excel(carpeta / f"{nombre}.xlsx", sheet_name=hoja, index=False)
    return carpeta


@pytest.fixture
def cmf_dir(tmp_path: Path) -> Path:
    return _write_cmf(tmp_path / "cmf")
