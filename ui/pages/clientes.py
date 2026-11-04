from datetime import date

import pandas as pd
import streamlit as st

from ui.components import Raw, badge, card_title, page_title, show_table
from ui.context import NAV_FICHA, Ctx
from wm.exposure import es_personalizada
from wm.metrics import is_true, truthy
from wm.portafolio_cliente import DEFINIDO, DESACTUALIZADO
from wm.priority import dias_sin_contacto

DEFAULT_FILTROS = {"texto": "", "servicios": [], "perfiles": [], "sin_contacto": False,
                   "sin_wealth_plan": False, "serie_mala": False, "sow_bajo": False, "portafolio_pendiente": False}


def apply_filters(df: pd.DataFrame, f: dict, hoy: date) -> pd.DataFrame:
    out = df
    if f.get("texto"):
        t = f["texto"].strip().lower()
        out = out[out["cliente_label"].astype(str).str.lower().str.contains(t, na=False, regex=False)]
    if f.get("servicios"):
        out = out[out["servicio"].isin(f["servicios"])]
    if f.get("perfiles"):
        out = out[out["perfil_norm"].isin(f["perfiles"])]
    if f.get("sin_contacto"):
        d = dias_sin_contacto(out, hoy)
        out = out[d.isna() | (d > 90)]
    if f.get("sin_wealth_plan") and "tiene_wealth_plan" in out.columns:
        out = out[~truthy(out["tiene_wealth_plan"])]
    if f.get("serie_mala"):
        out = out[out["serie_mala"]]
    if f.get("sow_bajo") and "share_of_wallet_pct" in out.columns:
        out = out[out["share_of_wallet_pct"] < 30]
    if f.get("portafolio_pendiente") and "portafolio_estado" in out.columns:
        out = out[out["portafolio_estado"] != DEFINIDO]
    return out


def _estado(row: pd.Series, dias) -> Raw:
    parts = []
    if pd.isna(dias) or dias > 90:
        parts.append(badge("Sin contacto", "warn"))
    if row.get("serie_mala"):
        parts.append(badge("Serie mala", "bad"))
    if "tiene_wealth_plan" in row.index and not is_true(row["tiene_wealth_plan"]):
        parts.append(badge("Sin wealth plan", "muted"))
    return Raw(" ".join(parts)) if parts else badge("Al día", "ok")


def _portafolio(row: pd.Series) -> Raw:
    estado = row.get("portafolio_estado")
    if estado == DEFINIDO:
        return badge(f"Definido v{int(row['portafolio_version'])}", "ok")
    if estado == DESACTUALIZADO:
        return badge("Desactualizado", "warn")
    return badge("Sin definir", "muted")


def _open(rut: str) -> None:
    st.session_state["cliente_sel"] = rut
    st.session_state["nav"] = NAV_FICHA


def render(ctx: Ctx) -> None:
    page_title("Clientes")
    mine = ctx.mine()
    saved = {**DEFAULT_FILTROS, **st.session_state.get("filtros", {})}
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 2, 2])
        texto = c1.text_input("Buscar por RUT o nombre", saved["texto"], key="f_texto")
        servicios = c2.multiselect("Servicio", sorted(mine["servicio"].dropna().unique()), saved["servicios"], key="f_servicios")
        perfiles = c3.multiselect("Perfil", sorted(mine["perfil_norm"].dropna().unique()), saved["perfiles"], key="f_perfiles")
        b = st.columns(5)
        sin_contacto = b[0].checkbox("Sin contacto > 90 días", saved["sin_contacto"], key="f_sin_contacto")
        sin_wp = b[1].checkbox("Sin wealth plan", saved["sin_wealth_plan"], key="f_sin_wp")
        serie_mala = b[2].checkbox("Serie mala", saved["serie_mala"], key="f_serie_mala")
        sow_bajo = b[3].checkbox("Share of wallet < 30%", saved["sow_bajo"], key="f_sow_bajo")
        pf_pendiente = b[4].checkbox("Portafolio por definir o revisar", saved["portafolio_pendiente"], key="f_pf_pendiente")
    filtros = {"texto": texto, "servicios": servicios, "perfiles": perfiles, "sin_contacto": sin_contacto,
               "sin_wealth_plan": sin_wp, "serie_mala": serie_mala, "sow_bajo": sow_bajo, "portafolio_pendiente": pf_pendiente}
    st.session_state["filtros"] = filtros

    res = apply_filters(mine, filtros, ctx.hoy).sort_values("prioridad", ascending=False)
    with st.container(border=True):
        card_title(f"{len(res)} clientes", "Ordenados por prioridad")
        if res.empty:
            st.info("Ningún cliente cumple los filtros.")
            return
        dias = dias_sin_contacto(res, ctx.hoy)
        table = pd.DataFrame({
            "Cliente": res["cliente_label"].values,
            "Tipo": res["tipo_persona"].values,
            "Servicio": res["servicio"].values,
            "Perfil": res["perfil_norm"].values,
            "Arquitectura": res["arquitectura"].map(lambda a: "sin determinar" if pd.isna(a) else "personalizada" if es_personalizada(a) else a).values,
            "Portafolio": [_portafolio(r) for _, r in res.iterrows()],
            "AUM": res["aum_clp"].map(ctx.fmt).values,
            "Días sin contacto": dias.map(lambda d: "—" if pd.isna(d) else f"{int(d)}").values,
            "Estado": [_estado(r, d) for (_, r), d in zip(res.iterrows(), dias)],
            "Prioridad": res["prioridad"].map(lambda v: f"{v:.0f}").values,
        })
        show_table(table.head(200), num_cols=("AUM", "Días sin contacto", "Prioridad"), link_col="Cliente")
        if len(table) > 200:
            st.caption(f"Mostrando 200 de {len(table)}; usa los filtros o exporta el CSV completo.")
        pick = st.selectbox("Abrir ficha de", res["rut"].head(200), key="clientes_pick",
                            format_func=lambda r: res.set_index("rut").loc[r, "cliente_label"])
        st.button("Abrir ficha", key="clientes_open", on_click=_open, args=(pick,))
        estados = [(("Sin contacto; " if (pd.isna(d) or d > 90) else "") + ("Serie mala; " if r["serie_mala"] else "")).rstrip("; ")
                   for (_, r), d in zip(res.iterrows(), dias)]
        st.download_button("Exportar CSV", table.assign(Estado=estados, Portafolio=res["portafolio_estado"].values if "portafolio_estado" in res.columns else "").to_csv(index=False).encode("utf-8-sig"),
                           "clientes.csv", "text/csv", key="clientes_csv")
