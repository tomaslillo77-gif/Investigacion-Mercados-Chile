import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from wm.config import load_config
from wm.asignacion import aplicar_asignaciones
from wm.catalogo import cargar_catalogo
from wm.enrich import enrich_clientes
from wm.loader import ROOT, Dataset, DatasetNotFound, load_dataset
from wm.portafolio_cliente import aplicar_portafolios, estado_portafolios
from wm.priority import score_clients
from wm.quality import Issue, validate
from wm.store import Store, StoreUnavailable
from ui.components import money, money_mm

load_dotenv(ROOT / ".env")

NAV_HOME = "Home"
NAV_CLIENTES = "Clientes"
NAV_FICHA = "Ficha del cliente"
NAV_ALINEACION = "Alineación al modelo"
NAV_SEGUIMIENTO = "Seguimiento"
NAV_MD = "Resumen del equipo"
NAV_NEGOCIO = "Manejo de negocio"
NAV_FEEDBACK = "Bandeja de feedback"
NAV_SCREENER = "Screener"
NAV_COMPARADOR = "Comparador"
NAV_HISTORIAL = "Historial"
SECCION_ESTRATEGIA = "Portafolios"   # sección de la barra lateral bajo el módulo Estrategia
SECCION_AFP = "AFP"                  # sección de la barra lateral bajo el módulo Mercados
MODULO_CLIENT_PORTAL = "Client Portal"
NAV_INDICES = "Índices"
NAV_EVOLUCION = "Evolución"
MODULO_ESTRATEGIA = "Estrategia"
MODULO_AFP = "Mercados"   # módulo con los índices de AFP (la sección crecerá con otros mercados)
ROLE_ESTRATEGIA = "Estrategia"
ROLE_IA = "Investment Advisor"
ROLE_MD = "Managing Director"


@dataclass
class Ctx:
    ds: Dataset
    view: pd.DataFrame          # todos los clientes enriquecidos + puntaje de prioridad
    issues: list[Issue]
    store: Store | None
    store_ok: bool
    role: str
    advisor: str | None
    user: str                   # quien firma comentarios y feedback
    hoy: date
    moneda: str
    fx: float | None            # CLP por USD (derivado de AUM / CAD en USD MM)
    page: str = ""

    def mine(self) -> pd.DataFrame:
        if self.role == ROLE_MD or self.advisor is None:
            return self.view
        return self.view[self.view["advisor"] == self.advisor]

    def adv_name(self, code) -> str:
        m = self.view.drop_duplicates("advisor").set_index("advisor")["advisor_nombre"]
        return str(m.get(code, code))

    def rate(self) -> float | None:
        """CLP por unidad de la moneda elegida (None si es CLP o no se puede derivar)."""
        if not self.fx:
            return None
        if self.moneda == "USD":
            return self.fx
        if self.moneda == "CAD":
            return self.fx / float(load_config("tipo_cambio")["cad_por_usd"])
        return None

    def mm(self, v_clp):
        """Monto en millones de la moneda elegida (número o serie), para ejes y barras de los gráficos."""
        r = self.rate() or 1.0
        return v_clp / r / 1e6

    def axis_mm(self) -> dict:
        """Formato de un eje de montos en millones de la moneda elegida."""
        prefix = {"USD": "US$", "CAD": "CA$"}.get(self.moneda if self.rate() else "CLP", "$")
        return dict(tickprefix=prefix, ticksuffix=" MM", tickformat=",.0f")

    def fmt_mm(self, v_clp) -> str:
        r = self.rate()
        return money(v_clp / r, self.moneda) if r else money_mm(v_clp)

    def fmt(self, v_clp) -> str:
        r = self.rate()
        return money(v_clp / r, self.moneda) if r else money(v_clp, "CLP")


def excel_path() -> Path:
    env = os.environ.get("WM_EXCEL")
    return Path(env) if env else ROOT / load_config("excel")["ruta"]


@st.cache_data(show_spinner="Cargando datos…")
def _load(path: str, mtime: float, hoy: date, dsn: str | None = None, huella_portafolios: str = ""):
    ds = load_dataset(Path(path))
    issues = validate(ds)                       # se valida lo que trae el Excel, antes de sumarle los portafolios de los advisors
    estado = None
    if dsn:
        try:
            store = Store(dsn)
            ds = aplicar_asignaciones(ds, store.asignaciones_vigentes())   # el advisor que fija el MD manda sobre el del Excel
            vigentes, resumen = store.portafolios_vigentes(), store.resumen_portafolios_vigentes()
            catalogo, _ = cargar_catalogo(ds.carteras)
            ds = aplicar_portafolios(ds, vigentes, catalogo.instrumentos)
            estado = resumen
        except StoreUnavailable:
            estado = None
    enriched = enrich_clientes(ds, hoy)
    scored = score_clients(enriched, load_config("prioridad"), hoy)
    view = enriched.merge(scored.drop(columns=[], errors="ignore"), on="rut", how="left")
    return ds, estado_portafolios(view, estado, hoy), issues


def load_data(hoy: date):
    p = excel_path()
    if not p.exists():
        raise DatasetNotFound(f"No se encontró el archivo de datos: {p}")
    dsn, huella = None, ""
    store, ok = get_store()
    if ok:
        try:   # qué portafolios hay y en qué versión: si alguien guarda uno, la caché se renueva
            huella = ";".join(f"{r.rut}:{r.version}" for r in store.resumen_portafolios_vigentes().itertuples())
            huella += "|" + ";".join(str(i) for i in store.asignaciones_vigentes()["id"])
            dsn = os.environ.get("WM_DSN")
        except StoreUnavailable:
            dsn = None
    return _load(str(p), p.stat().st_mtime, hoy, dsn, huella)


@st.cache_resource
def _migrated(dsn: str) -> bool:
    Store(dsn).migrate()  # si falla no se cachea y se reintenta en el próximo rerun
    return True


def get_store() -> tuple[Store | None, bool]:
    dsn = os.environ.get("WM_DSN")
    if not dsn:
        return None, False
    s = Store(dsn)
    try:
        _migrated(dsn)
        return s, s.available()
    except StoreUnavailable:
        return s, False


def derive_fx(view: pd.DataFrame) -> float | None:
    if "cad_usd_mm" not in view.columns:
        return None
    usd = pd.to_numeric(view["cad_usd_mm"], errors="coerce").sum() * 1e6
    return float(view["aum_clp"].sum() / usd) if usd > 0 else None


def now() -> datetime:
    return datetime.now()
