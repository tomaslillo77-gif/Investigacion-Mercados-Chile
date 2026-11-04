import sys
from datetime import date

import pandas as pd
import pytest

from wm.mercado.fuentes import yahoo as ymod
from wm.mercado.fuentes.base import FuenteNoDisponible
from wm.mercado.fuentes.bloomberg import BloombergFuente
from wm.mercado.fuentes.cmf_api import CmfApiFuente
from wm.mercado.fuentes.riskamerica import RiskAmericaFuente
from wm.mercado.fuentes.yahoo import YahooFuente
from wm.mercado.schema import COMPOSICION_COLS, PRECIOS_COLS, RENTAB_COLS

HOY = date(2026, 10, 18)


class FuenteFalsa:
    nombre = "falsa"

    def rentabilidades(self, ids):
        return pd.DataFrame({"id": list(ids), "fecha": [HOY] * len(ids), "rent_1m": 1.0, "rent_3m": 2.0,
                             "rent_ytd": 3.0, "rent_1a": 4.0, "rent_3a": 5.0})[RENTAB_COLS]

    def precios(self, ids, desde):
        return pd.DataFrame({"id": list(ids), "fecha": [desde] * len(ids), "valor": 1.0})[PRECIOS_COLS]

    def composicion(self, ids):
        return None


def test_contrato_fuente_falsa():
    f = FuenteFalsa()
    assert list(f.rentabilidades(["A"]).columns) == RENTAB_COLS
    assert list(f.precios(["A"], HOY).columns) == PRECIOS_COLS
    assert f.composicion(["A"]) is None


@pytest.mark.parametrize("fuente,palabra", [(BloombergFuente(), "blpapi"), (RiskAmericaFuente(), "RiskAmerica"),
                                            (CmfApiFuente(), "CMF_API_KEY")])
def test_fuentes_no_conectadas_lanzan_error_claro(fuente, palabra):
    for llamada in (lambda: fuente.precios(["X"], HOY), lambda: fuente.rentabilidades(["X"]),
                    lambda: fuente.composicion(["X"])):
        with pytest.raises(FuenteNoDisponible) as e:
            llamada()
        assert palabra in str(e.value)


def _precios_falsos(llamadas):
    def descargar(id_, desde):
        llamadas.append(id_)
        return pd.DataFrame({"fecha": [date(2026, 10, 1), date(2026, 10, 17)], "valor": [100.0, 110.0]})
    return descargar


def _yahoo(tmp_path, descargar, monkeypatch):
    monkeypatch.setattr(ymod.time, "sleep", lambda s: None)
    return YahooFuente(tmp_path / "cache", descargar=descargar, hoy=lambda: HOY)


def test_yahoo_usa_cache_el_mismo_dia(tmp_path, monkeypatch):
    llamadas = []
    y = _yahoo(tmp_path, _precios_falsos(llamadas), monkeypatch)
    a = y.precios(["SPY"], date(2026, 10, 1))
    b = y.precios(["SPY"], date(2026, 10, 1))
    assert llamadas == ["SPY"] and list(a.columns) == PRECIOS_COLS and len(b) == 2


def test_yahoo_ante_falla_devuelve_cache(tmp_path, monkeypatch):
    y = _yahoo(tmp_path, _precios_falsos([]), monkeypatch)
    y.precios(["SPY"], date(2026, 10, 1))

    def falla(id_, desde):
        raise ConnectionError("bloqueado")
    y2 = YahooFuente(tmp_path / "cache", descargar=falla, hoy=lambda: date(2026, 10, 19), reintentos=2)
    r = y2.precios(["SPY"], date(2026, 10, 1))
    assert r is not None and len(r) == 2  # dato guardado del día anterior


def test_yahoo_falla_sin_cache_devuelve_none(tmp_path, monkeypatch):
    def falla(id_, desde):
        raise ConnectionError("bloqueado")
    assert _yahoo(tmp_path, falla, monkeypatch).precios(["SPY"], date(2026, 10, 1)) is None


def test_yahoo_sin_yfinance_lanza_no_disponible(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "yfinance", None)
    y = YahooFuente(tmp_path / "cache", hoy=lambda: HOY)
    with pytest.raises(FuenteNoDisponible) as e:
        y.precios(["SPY"], date(2026, 10, 1))
    assert "yfinance" in str(e.value)


def test_yahoo_rentabilidades_desde_precios(tmp_path, monkeypatch):
    def descargar(id_, desde):
        return pd.DataFrame({"fecha": [date(2025, 10, 18), date(2025, 12, 31), date(2026, 9, 18), date(2026, 10, 18)],
                             "valor": [100.0, 105.0, 120.0, 130.0]})
    r = _yahoo(tmp_path, descargar, monkeypatch).rentabilidades(["SPY"])
    assert list(r.columns) == RENTAB_COLS
    assert round(r.loc[0, "rent_1a"], 2) == 30.0 and round(r.loc[0, "rent_ytd"], 2) == round((130 / 105 - 1) * 100, 2)
    assert round(r.loc[0, "rent_1m"], 2) == round((130 / 120 - 1) * 100, 2)


def test_yahoo_composicion_no_ofrecida(tmp_path, monkeypatch):
    assert _yahoo(tmp_path, _precios_falsos([]), monkeypatch).composicion(["SPY"]) is None


def test_yahoo_rentabilidad_a_3_anios_anualizada(tmp_path, monkeypatch):
    def descargar(id_, desde):
        return pd.DataFrame({"fecha": [date(2023, 10, 17), date(2026, 10, 17)], "valor": [100.0, 172.8]})  # 1.2^3 = 1.728
    r = _yahoo(tmp_path, descargar, monkeypatch).rentabilidades(["X"])
    assert "rent_3a" in RENTAB_COLS and round(r.loc[0, "rent_3a"], 2) == 20.0


def test_yahoo_busca_isin_y_guarda_el_resultado_para_siempre(tmp_path, monkeypatch):
    llamadas = []

    def buscar(isin):
        llamadas.append(isin)
        return {"symbol": "CSSPX.MI", "nombre": "ISHARES CORE S&P 500", "tipo": "ETF"}
    monkeypatch.setattr(ymod.time, "sleep", lambda s: None)
    y = YahooFuente(tmp_path / "cache", buscar=buscar, hoy=lambda: HOY)
    assert y.buscar_isin("IE00B5BMR087")["symbol"] == "CSSPX.MI"
    y2 = YahooFuente(tmp_path / "cache", buscar=buscar, hoy=lambda: date(2026, 12, 1))   # otra sesión, otro día
    assert y2.buscar_isin("IE00B5BMR087")["symbol"] == "CSSPX.MI" and llamadas == ["IE00B5BMR087"]


def test_yahoo_isin_no_encontrado_o_con_falla_devuelve_none(tmp_path, monkeypatch):
    monkeypatch.setattr(ymod.time, "sleep", lambda s: None)
    assert YahooFuente(tmp_path / "a", buscar=lambda i: None, hoy=lambda: HOY).buscar_isin("XX") is None

    def falla(isin):
        raise ConnectionError("bloqueado")
    assert YahooFuente(tmp_path / "b", buscar=falla, hoy=lambda: HOY, reintentos=2).buscar_isin("XX") is None


def test_yahoo_info_usa_cache_el_mismo_dia_y_tolera_fallas(tmp_path, monkeypatch):
    llamadas = []

    def info(id_):
        llamadas.append(id_)
        return {"nombre": "X", "tipo": "ETF", "moneda": "USD", "costo": 0.07, "patrimonio": 1e9}
    monkeypatch.setattr(ymod.time, "sleep", lambda s: None)
    y = YahooFuente(tmp_path / "cache", info=info, hoy=lambda: HOY)
    assert y.info("CSPX.L")["costo"] == 0.07 and y.info("CSPX.L")["moneda"] == "USD" and llamadas == ["CSPX.L"]

    def falla(id_):
        raise ConnectionError("x")
    assert YahooFuente(tmp_path / "c2", info=falla, hoy=lambda: HOY, reintentos=1).info("Z") == {}
