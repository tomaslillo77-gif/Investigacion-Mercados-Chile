from datetime import date

import pandas as pd
import pytest

from wm.mercado import internacionales as it
from wm.mercado.equivalencias import EQUIV_COLS

HOY = date(2026, 10, 18)
CAT = pd.DataFrame({
    "instrumento": ["Core S&P 500 UCIT", "Core S&P 500 UCIT", "JP Morgan US Select Equity", "Fidelity Emerging Asia",
                    "Schroder Global Corporate", "Moneda Deuda Chile", "Fondo Chileno"],
    "isin": ["IE00B5BMR087", "IE00B5BMR087_RET", "LU0087133087", "LU0390711777", "LU0106258741",
             "SIN_ISIN::Moneda deuda Chile", "CL0000000001"],
    "serie": ["ETF", "A", "C", "Y", "C", "I", "A"]})


class FakeYahoo:
    def __init__(self):
        self.busquedas = []

    def buscar_isin(self, isin):
        self.busquedas.append(isin)
        return {"IE00B5BMR087": {"symbol": "CSSPX.MI", "nombre": "ISHARES CORE S&P 500", "tipo": "ETF"},
                "LU0087133087": {"symbol": "0P00000DU1", "nombre": "JPM US SELECT", "tipo": "MUTUALFUND"},
                "LU0106258741": {"symbol": "SRVR.F", "nombre": "SCHRODER", "tipo": "ETF"}}.get(isin)

    def info(self, t):
        return {"CSSPX.MI": {"nombre": "iShares Core S&P 500", "tipo": "ETF", "moneda": "EUR", "costo": 0.07, "patrimonio": 1e9}
                }.get(t, {"nombre": None, "tipo": "MUTUALFUND", "moneda": "USD", "costo": None, "patrimonio": None})

    def precios(self, ids, desde):
        n = 1 if ids[0] == "SRVR.F" else 300                      # SRVR.F cotiza un solo día: no sirve
        return pd.DataFrame({"id": ids[0], "fecha": [date(2026, 10, 17)] * n, "valor": [123.4] * n})

    def rentabilidades(self, ids):
        return pd.DataFrame([{"id": ids[0], "fecha": date(2026, 10, 17), "rent_1m": 1.0, "rent_3m": 2.0, "rent_ytd": 3.0,
                              "rent_1a": 4.0, "rent_3a": 5.0}])


@pytest.mark.parametrize("isin,esperado", [("IE00B5BMR087", "IE00B5BMR087"), ("IE00B5BMR087_RET", "IE00B5BMR087"),
                                           ("LU0087133087_B", "LU0087133087"), ("SIN_ISIN::Moneda deuda Chile", None),
                                           ("CL0000000001", None), (None, None), ("", None)])
def test_isin_base(isin, esperado):
    assert it.isin_base(isin) == esperado


def test_universo_une_series_y_deja_fuera_locales():
    u = it.universo(CAT)
    assert sorted(u["isin"]) == ["IE00B5BMR087", "LU0087133087", "LU0106258741", "LU0390711777"]


def test_construir_llena_costo_precio_y_rentabilidades():
    d = it.construir(CAT, FakeYahoo(), hoy=HOY).set_index("isin")
    sp = d.loc["IE00B5BMR087"]
    assert sp["ticker"] == "CSSPX.MI" and sp["estado"] == "Yahoo" and sp["moneda"] == "EUR" and sp["costo"] == 0.07
    assert sp["precio"] == 123.4 and sp["rent_1a"] == 4.0 and sp["rent_3a"] == 5.0
    jp = d.loc["LU0087133087"]
    assert jp["estado"] == "Yahoo" and pd.isna(jp["costo"])      # los fondos mutuos no traen costo en Yahoo


def test_sin_ticker_y_sin_datos_suficientes_no_rompen():
    d = it.construir(CAT, FakeYahoo(), hoy=HOY).set_index("isin")
    assert d.loc["LU0390711777", "estado"] == "Sin ticker" and pd.isna(d.loc["LU0390711777", "rent_1a"])
    sch = d.loc["LU0106258741"]
    assert sch["estado"] == "Sin datos suficientes" and sch["ticker"] == "SRVR.F" and pd.isna(sch["rent_1a"])


def test_ticker_de_las_equivalencias_manda_y_evita_buscar():
    y = FakeYahoo()
    d = it.construir(CAT, y, tickers={"LU0390711777": "0P00FIDELITY"}, hoy=HOY).set_index("isin")
    assert d.loc["LU0390711777", "ticker"] == "0P00FIDELITY" and "LU0390711777" not in y.busquedas


def test_foto_ida_y_vuelta_y_sin_foto(tmp_path):
    d = it.construir(CAT, FakeYahoo(), hoy=HOY)
    it.guardar_yahoo(d, tmp_path / "y", HOY)
    fecha, otra = it.cargar_yahoo(tmp_path / "y")
    assert fecha == HOY and list(otra.columns) == list(d.columns) and len(otra) == len(d)
    assert it.cargar_yahoo(tmp_path / "nada") is None


def test_completar_tickers_solo_llena_vacios_de_ese_isin():
    eq = pd.DataFrame([
        {"instrumento_catalogo": "Core S&P 500 UCIT", "isin": "IE00B5BMR087", "serie_catalogo": "ETF", "ticker_yahoo": None},
        {"instrumento_catalogo": "Core S&P 500 UCIT", "isin": "IE00B5BMR087_RET", "serie_catalogo": "A", "ticker_yahoo": None},
        {"instrumento_catalogo": "JP Morgan US Select Equity", "isin": "LU0087133087", "serie_catalogo": "C",
         "ticker_yahoo": "CORREGIDO"},
        {"instrumento_catalogo": "Otro", "isin": "LU0000000000", "serie_catalogo": "A", "ticker_yahoo": None}])
    eq = eq.reindex(columns=EQUIV_COLS)
    r = it.completar_tickers(eq, it.construir(CAT, FakeYahoo(), hoy=HOY))
    assert r.loc[:1, "ticker_yahoo"].tolist() == ["CSSPX.MI", "CSSPX.MI"]
    assert r.loc[2, "ticker_yahoo"] == "CORREGIDO" and pd.isna(r.loc[3, "ticker_yahoo"])
