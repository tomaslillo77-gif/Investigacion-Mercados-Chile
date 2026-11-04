import pandas as pd
import streamlit as st

from ui.components import Raw, badge, show_table

ACCION_KIND = {"Comprar": "ok", "Vender": "bad", "Mantener": "muted"}


def _signed(v: float, fmt) -> str:
    if abs(v) < 0.5:
        return fmt(0)
    return ("+" if v > 0 else "−") + fmt(abs(v))


def show_plan(plan: pd.DataFrame, fmt, destino: str = "modelo") -> None:
    """Tabla de rebalanceo por fondo: hoy vs modelo en % y en pesos, con la acción para el advisor."""
    t = pd.DataFrame({
        "Fondo": plan["fondo"].values,
        "Serie hoy": plan["serie_actual"].fillna("—").values,
        f"Serie {destino}": plan["serie_modelo"].fillna("—").values,
        "Hoy": plan["valor_actual"].map(fmt).values,
        "% hoy": plan["pct_actual"].map(lambda v: f"{v:.1f}%").values,
        f"% {destino}": plan["pct_modelo"].map(lambda v: f"{v:.1f}%").values,
        "Diferencia (pp)": plan["dif_pp"].map(lambda v: f"{v:+.1f}".replace("-", "−")).values,
        "Ajuste sugerido": plan["ajuste_clp"].map(lambda v: _signed(v, fmt)).values,
        "Acción": [badge(a, ACCION_KIND[a]) for a in plan["accion"]],
    })
    show_table(t, num_cols=("Hoy", "% hoy", f"% {destino}", "Diferencia (pp)", "Ajuste sugerido"),
               total_row={"Fondo": "Total", "Hoy": fmt(float(plan["valor_actual"].sum())),
                          "% hoy": f"{plan['pct_actual'].sum():.1f}%", f"% {destino}": f"{plan['pct_modelo'].sum():.1f}%"},
               total_position="bottom")
    comprar = float(plan.loc[plan["ajuste_clp"] > 0, "ajuste_clp"].sum())
    vender = float(-plan.loc[plan["ajuste_clp"] < 0, "ajuste_clp"].sum())
    st.markdown(f"<div class='footnote'>Para alinear la cartera con el {destino}: comprar {fmt(comprar)} y vender {fmt(vender)}. "
                f"Se considera alineado un fondo con diferencia menor a 1 punto porcentual.</div>", unsafe_allow_html=True)
