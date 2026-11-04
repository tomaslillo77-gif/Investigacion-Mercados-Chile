import streamlit as st
import pandas as pd
from datetime import datetime
from data_reader import PortfolioDataReader
from client_notebook import ClientNotebook
from portfolio_partitioner import PortfolioPartitioner
from custom_architecture import CustomArchitecture
import plotly.graph_objects as go

st.set_page_config(
    page_title="Portfolio Control Center",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------- theme
BG = "#0f1b2b"
SIDEBAR = "#111e30"
CARD = "#172336"
BORDER = "#22314a"
TEXT = "#e6edf5"
MUTED = "#8fa0b8"
TEAL = "#7fd1d9"
BLUE = "#6cb4f5"
INDIGO = "#5560d8"
RED = "#e8735a"
PALETTE = ["#e8735a", "#e8b44f", "#9be37a", "#6cb4f5", "#c47ee8", "#7fd1d9"]

st.markdown(f"""
<style>
    .stApp {{ background: {BG}; color: {TEXT}; }}
    header[data-testid="stHeader"] {{ background: transparent; }}
    .block-container {{ padding-top: 2rem; max-width: 1500px; }}

    /* sidebar */
    section[data-testid="stSidebar"] {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
    .brand {{ font-size: 17px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase;
              color: {TEXT}; padding: 4px 0 2px 0; }}
    .brand-sub {{ font-size: 9px; letter-spacing: 7px; color: {MUTED}; text-transform: uppercase; margin-bottom: 18px; }}
    section[data-testid="stSidebar"] [role="radiogroup"] {{ gap: 2px; }}
    section[data-testid="stSidebar"] [role="radiogroup"] label {{
        padding: 9px 12px; border-radius: 6px; border-left: 3px solid transparent; width: 100%; cursor: pointer; }}
    section[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child {{ display: none; }}
    section[data-testid="stSidebar"] [role="radiogroup"] label:hover {{ background: {CARD}; }}
    section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{
        background: {CARD}; border-left-color: {BLUE}; }}
    section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {{ color: {BLUE}; }}
    section[data-testid="stSidebar"] [role="radiogroup"] label p {{ font-size: 15px; font-weight: 500; }}

    /* cards */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div[data-testid="stVerticalBlock"]) {{
        border-radius: 10px; }}
    div[data-testid="stVerticalBlockBorderWrapper"] {{ background: {CARD}; border-color: {BORDER} !important;
        border-radius: 10px; }}
    .card-title {{ font-size: 19px; font-weight: 600; color: {TEXT}; margin-bottom: 6px; }}
    .section-title {{ font-size: 19px; font-weight: 600; margin: 14px 0 8px 0; }}
    .page-title {{ font-size: 28px; font-weight: 600; margin-bottom: 4px; }}
    .page-rule {{ border-bottom: 1px solid {BORDER}; margin: 6px 0 18px 0; }}
    .hello {{ font-size: 15px; color: {TEXT}; margin-bottom: -4px; }}
    .hello-name {{ font-size: 30px; font-weight: 600; margin-bottom: 14px; }}
    .big-value {{ font-size: 34px; font-weight: 600; color: {TEXT}; line-height: 1.15; margin-bottom: 6px; }}
    .stat-label {{ font-size: 13px; color: {MUTED}; }}
    .stat-value {{ font-size: 21px; font-weight: 600; color: {TEXT}; }}
    .footnote {{ font-size: 11px; color: {MUTED}; margin-top: 6px; }}
    .dot {{ display:inline-block; width:11px; height:11px; border-radius:50%; margin-right:9px; }}
    .legend-row {{ display:flex; justify-content:space-between; font-size:13px; padding:5px 0; }}
    .legend-row span:last-child {{ color:{TEXT}; }}
    .badge {{ display:inline-block; padding:3px 10px; border-radius:12px; font-size:12px; font-weight:600; }}
    .badge-warn {{ background: rgba(232,180,79,.15); color:#e8b44f; }}
    .badge-ok {{ background: rgba(155,227,122,.15); color:#9be37a; }}
    .callout {{ border-left: 3px solid {TEXT}; background:{CARD}; border-radius:6px; padding:12px 16px; margin:8px 0; }}
    .callout.warn {{ border-left-color:#e8b44f; }}
    .callout.ok {{ border-left-color:#9be37a; }}
    .callout.info {{ border-left-color:{BLUE}; }}

    /* dark html tables */
    table.dtable {{ width:100%; border-collapse:collapse; font-size:13px; }}
    table.dtable th {{ background:#1d2c44; color:{TEXT}; font-weight:600; text-align:left; padding:10px 12px; }}
    table.dtable td {{ padding:10px 12px; border-bottom:1px solid {BORDER}; color:{TEXT}; }}
    table.dtable tr.total td {{ font-weight:700; background:#1a2840; }}
    table.dtable td.num, table.dtable th.num {{ text-align:right; }}
    table.dtable td a, table.dtable td.link {{ color:{BLUE}; }}

    /* widgets */
    .stSelectbox div[data-baseweb="select"] > div, .stTextInput input, .stTextArea textarea {{
        background:{BG}; border-color:{BORDER}; }}
    .stButton > button {{ background: transparent; color:{BLUE}; border:1px solid {BORDER}; border-radius:6px; }}
    .stButton > button:hover {{ border-color:{BLUE}; color:{BLUE}; }}
    div[data-testid="stDataFrame"] {{ border:1px solid {BORDER}; border-radius:8px; }}
    hr {{ border-color:{BORDER}; }}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- helpers
def money(v, decimals=0):
    return f"${v:,.{decimals}f}"


def style_fig(fig, height=300, legend=False):
    fig.update_layout(
        height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=MUTED, size=12), margin=dict(l=10, r=10, t=10, b=10),
        showlegend=legend, legend=dict(font=dict(color=TEXT), orientation="h", y=-0.15),
        hoverlabel=dict(bgcolor=BG, font_color=TEXT),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=BORDER)
    fig.update_yaxes(gridcolor=BORDER, griddash="dash", zeroline=False)
    return fig


def donut(labels, values, center_title, center_value, height=300, colors=None):
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.72, sort=False,
        marker=dict(colors=(colors or PALETTE)[:len(labels)], line=dict(color=CARD, width=3)),
        textinfo="none", hovertemplate="%{label}<br>%{value:,.0f} (%{percent})<extra></extra>",
    ))
    fig.add_annotation(text=f"<span style='font-size:11px;color:{MUTED}'>{center_title}</span><br>"
                            f"<b style='font-size:18px;color:{TEXT}'>{center_value}</b>",
                       showarrow=False, x=0.5, y=0.5)
    return style_fig(fig, height)


def legend_html(labels, values, colors=None):
    colors = colors or PALETTE
    rows = "".join(
        f"<div class='legend-row'><span><span class='dot' style='background:{colors[i % len(colors)]}'></span>{l}</span>"
        f"<span>{money(v)}</span></div>" for i, (l, v) in enumerate(zip(labels, values)))
    return rows


def card_title(text):
    st.markdown(f"<div class='card-title'>{text}</div>", unsafe_allow_html=True)


def html_table(df, num_cols=(), link_col=None, dot_col=None, total_row=None):
    head = "".join(f"<th class='{'num' if c in num_cols else ''}'>{c}</th>" for c in df.columns)
    body = ""
    if total_row:
        cells = "".join(f"<td class='{'num' if c in num_cols else ''}'>{total_row.get(c, '')}</td>" for c in df.columns)
        body += f"<tr class='total'>{cells}</tr>"
    for i, row in df.iterrows():
        cells = ""
        for c in df.columns:
            val = row[c]
            cls = "num" if c in num_cols else ("link" if c == link_col else "")
            if c == dot_col:
                color = PALETTE[hash(str(val)) % len(PALETTE)]
                val = f"<span class='dot' style='background:{color}'></span>{val}"
            cells += f"<td class='{cls}'>{val}</td>"
        body += f"<tr>{cells}</tr>"
    st.markdown(f"<table class='dtable'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>",
                unsafe_allow_html=True)


def page_title(text):
    st.markdown(f"<div class='page-title'>{text}</div><div class='page-rule'></div>", unsafe_allow_html=True)


def callout(kind, html):
    st.markdown(f"<div class='callout {kind}'>{html}</div>", unsafe_allow_html=True)


def service_of(df):
    col = "Service_Type" if "Service_Type" in df.columns else "Servicio"
    return col if col in df.columns else None


# ---------------------------------------------------------------- resources
@st.cache_resource
def get_reader():
    return PortfolioDataReader()


@st.cache_resource
def get_notebook():
    return ClientNotebook()


@st.cache_resource
def get_custom_arch():
    return CustomArchitecture()


reader = get_reader()
notebook = get_notebook()
custom_arch = get_custom_arch()

try:
    portfolio_archs = reader.read_portfolio_architectures()
    if isinstance(portfolio_archs, pd.DataFrame) and not portfolio_archs.empty:
        partitioner = PortfolioPartitioner(portfolio_archs)
    else:
        partitioner = PortfolioPartitioner(None)
except Exception:
    partitioner = PortfolioPartitioner(None)

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("<div class='brand'>◍ Portfolio</div><div class='brand-sub'>Control Center</div>",
                unsafe_allow_html=True)
    user_role = st.selectbox("Rol", ["Investment Advisor", "Managing Director"], label_visibility="collapsed")

    if user_role == "Investment Advisor":
        advisors = reader.read_advisors()
        advisor_id = st.selectbox("Asesor", advisors["Advisor_ID"].tolist(), label_visibility="collapsed")
        pages = ["🏠  Home", "👥  Clientes", "⚖️  Net Worth", "🔄  Rebalancing", "📝  Notas"]
    else:
        advisor_id = None
        pages = ["🏠  Home"]

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    page = st.radio("Navegación", pages, label_visibility="collapsed")
    st.markdown("<hr>", unsafe_allow_html=True)
    st.caption(f"Actualizado: {datetime.now().strftime('%H:%M:%S')}")

greeting_name = advisor_id if advisor_id else "Managing Director"

# ================================================================ ADVISOR
if user_role == "Investment Advisor":
    advisor_summary = reader.get_advisor_summary(advisor_id)
    clients = reader.get_clients_by_advisor(advisor_id)

    # ---------------------------------------------------------- HOME
    if page.endswith("Home"):
        st.markdown(f"<div class='hello'>Hello,</div><div class='hello-name'>{greeting_name}</div>",
                    unsafe_allow_html=True)

        ranked = clients.sort_values("Portfolio_Value_USD", ascending=False).reset_index(drop=True)
        total_aum = float(clients["Portfolio_Value_USD"].sum())

        c1, c2, c3 = st.columns([1, 1, 1.25])
        with c1, st.container(border=True):
            card_title("AUM Total")
            st.markdown(f"<div class='big-value'>{money(total_aum)}</div>", unsafe_allow_html=True)
            cum = ranked["Portfolio_Value_USD"].cumsum()
            fig = go.Figure(go.Scatter(x=list(range(1, len(cum) + 1)), y=cum, mode="lines", fill="tozeroy",
                                       line=dict(color=TEAL, width=2), fillcolor="rgba(127,209,217,.18)",
                                       hovertemplate="Top %{x} clientes<br>$%{y:,.0f}<extra></extra>"))
            style_fig(fig, 150)
            fig.update_yaxes(showticklabels=False)
            fig.update_xaxes(showticklabels=False)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            s1, s2 = st.columns(2)
            s1.markdown(f"<div class='stat-label'>Clientes</div><div class='stat-value'>{advisor_summary['num_clients']}</div>",
                        unsafe_allow_html=True)
            s2.markdown(f"<div class='stat-label'>Acción requerida</div><div class='stat-value'>{advisor_summary['clients_needing_rebalance']}</div>",
                        unsafe_allow_html=True)
            st.markdown("<div class='footnote'>AUM acumulado por clientes ordenados de mayor a menor</div>",
                        unsafe_allow_html=True)

        with c2, st.container(border=True):
            card_title("Top Clientes")
            top = ranked.head(7).copy()
            top["Cliente"] = top["Name"]
            top["% del total"] = (top["Portfolio_Value_USD"] / total_aum * 100).map("{:.0f}%".format)
            top["Valor"] = top["Portfolio_Value_USD"].map(money)
            html_table(top[["Cliente", "% del total", "Valor"]], num_cols=("% del total", "Valor"))
            st.markdown(f"<div class='footnote'>Asesor {advisor_id}</div>", unsafe_allow_html=True)

        with c3, st.container(border=True):
            card_title("Distribución por Servicio")
            scol = service_of(clients)
            if scol:
                dist = clients.groupby(scol)["Portfolio_Value_USD"].sum().sort_values(ascending=False)
                a, b = st.columns([1.1, 1])
                with a:
                    st.plotly_chart(donut(dist.index.tolist(), dist.values, "TOTAL AUM", money(total_aum), 280),
                                    use_container_width=True, config={"displayModeBar": False})
                with b:
                    st.markdown("<div style='height:50px'></div>" + legend_html(dist.index, dist.values),
                                unsafe_allow_html=True)
            else:
                st.info("No hay datos de Servicio disponibles")

        d1, d2 = st.columns([1.35, 1])
        with d1, st.container(border=True):
            card_title("AUM por Perfil de Riesgo")
            prof = clients.groupby("Risk_Profile")["Portfolio_Value_USD"].sum().sort_values(ascending=False)
            fig = go.Figure(go.Bar(x=prof.index, y=prof.values, marker_color="#7fc8d0",
                                   hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>"))
            style_fig(fig, 300)
            fig.update_yaxes(tickprefix="$", tickformat=".2s")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown(f"<div class='footnote'>Asesor {advisor_id}</div>", unsafe_allow_html=True)

        with d2, st.container(border=True):
            card_title("Resumen")
            for label, val, color in [
                ("Portafolios gestionados", advisor_summary["managed_clients"], BLUE),
                ("Autogestionados", advisor_summary["self_directed_clients"], INDIGO),
                ("Requieren rebalanceo", advisor_summary["clients_needing_rebalance"], RED),
                ("AUM promedio", money(advisor_summary["avg_portfolio_value"]), TEAL),
            ]:
                st.markdown(f"<div class='legend-row' style='padding:14px 0;border-bottom:1px solid {BORDER}'>"
                            f"<span><span class='dot' style='background:{color}'></span>{label}</span>"
                            f"<span class='stat-value' style='font-size:17px'>{val}</span></div>",
                            unsafe_allow_html=True)

    # ---------------------------------------------------------- CLIENTES
    elif page.endswith("Clientes"):
        page_title("Clientes")
        rows = []
        for _, client in clients.iterrows():
            rut = client["RUT"]
            needs_rebal, _, dev = reader.check_rebalance_needed(rut)
            holdings = reader.get_client_holdings(rut)
            rows.append({
                "Cliente": client["Name"],
                "RUT": rut,
                "Valor": money(client["Portfolio_Value_USD"]),
                "Servicio": str(client.get("Service_Type", client.get("Servicio", ""))).strip(),
                "Perfil": client["Risk_Profile"],
                "Posiciones": len(holdings),
                "Rebalance": "<span class='badge badge-warn'>Sí</span>" if needs_rebal
                             else "<span class='badge badge-ok'>No</span>",
            })
        with st.container(border=True):
            html_table(pd.DataFrame(rows), num_cols=("Valor", "Posiciones"), link_col="Cliente")

    # ---------------------------------------------------------- NET WORTH (client detail)
    elif page.endswith("Net Worth"):
        page_title("Net Worth")
        selected_name = st.selectbox("Cliente", clients["Name"].tolist())
        client_data = clients[clients["Name"] == selected_name].iloc[0]
        client_rut = client_data["RUT"]
        holdings = reader.get_client_holdings(client_rut)
        partition = partitioner.partition_portfolio(holdings, client_data["Architecture"], client_data["Risk_Profile"])
        kpis = reader.calculate_portfolio_kpis(client_rut)

        left, right = st.columns([1, 2.1])
        with left, st.container(border=True):
            st.markdown(f"<div class='stat-label' style='font-size:15px'>Valor actual</div>"
                        f"<div class='big-value'>{money(client_data['Portfolio_Value_USD'])}</div>",
                        unsafe_allow_html=True)
            st.markdown(f"<div class='legend-row'><span><span class='dot' style='background:{BLUE}'></span>En cartera modelo</span></div>"
                        f"<div class='stat-value'>{money(partition['in_model_value'])}</div>"
                        f"<div class='legend-row' style='margin-top:10px'><span><span class='dot' style='background:{INDIGO}'></span>Fuera de cartera</span></div>"
                        f"<div class='stat-value'>{money(partition['outside_model_value'])}</div>",
                        unsafe_allow_html=True)
        with right, st.container(border=True):
            m = st.columns(4)
            for col, (label, val) in zip(m, [
                ("Servicio", str(client_data.get("Service_Type", client_data.get("Servicio", "N/A")))),
                ("Perfil", client_data["Risk_Profile"]),
                ("Arquitectura", client_data["Architecture"]),
                ("Diversif.", f"{kpis['diversification_score']:.0f}%"),
            ]):
                col.markdown(f"<div class='stat-label'>{label}</div><div class='stat-value' style='font-size:17px'>{val}</div>",
                             unsafe_allow_html=True)
            fig = go.Figure(go.Bar(
                x=["En cartera modelo", "Fuera de cartera"],
                y=[partition["in_model_value"], partition["outside_model_value"]],
                marker_color=[BLUE, INDIGO], width=0.35,
                hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>"))
            style_fig(fig, 200)
            fig.update_yaxes(tickprefix="$", tickformat=".2s")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        l2, r2 = st.columns([1, 2.1])
        with l2:
            st.markdown("<div class='section-title'>Asset Breakdown: Clase de Activo</div>", unsafe_allow_html=True)
            if not holdings.empty:
                by_class = holdings.groupby("Asset_Class")["Current_Value_USD"].sum().sort_values(ascending=False)
                st.plotly_chart(donut(by_class.index.tolist(), by_class.values, "Total Assets",
                                      money(by_class.sum()), 330),
                                use_container_width=True, config={"displayModeBar": False})
                st.markdown(legend_html(by_class.index, by_class.values), unsafe_allow_html=True)
            else:
                st.info("Este cliente no tiene posiciones registradas")

        with r2:
            st.markdown("<div class='section-title'>Instrumentos en Cartera Modelo</div>", unsafe_allow_html=True)
            if not partition["in_model_instruments"].empty:
                df = partition["in_model_instruments"][["Instrumento", "Valor", "Target_%", "Actual_%"]].copy()
                total = df["Valor"].sum()
                df["Valor"] = df["Valor"].map(money)
                html_table(df, num_cols=("Valor", "Target_%", "Actual_%"), link_col="Instrumento",
                           dot_col="Instrumento", total_row={"Instrumento": "Total", "Valor": money(total)})
            else:
                st.info("No hay instrumentos en cartera modelo")

            st.markdown("<div class='section-title'>Instrumentos Fuera de Cartera</div>", unsafe_allow_html=True)
            if not partition["outside_model_instruments"].empty:
                df = partition["outside_model_instruments"][["Instrumento", "Valor", "Pct_del_Total"]].copy()
                total = df["Valor"].sum()
                df["Valor"] = df["Valor"].map(money)
                html_table(df, num_cols=("Valor", "Pct_del_Total"), link_col="Instrumento",
                           dot_col="Instrumento", total_row={"Instrumento": "Total", "Valor": money(total)})
            else:
                st.info("No hay instrumentos fuera de cartera")

    # ---------------------------------------------------------- REBALANCING
    elif page.endswith("Rebalancing"):
        page_title("Rebalancing")
        selected_name = st.selectbox("Cliente", clients["Name"].tolist(), key="rebal")
        client_data = clients[clients["Name"] == selected_name].iloc[0]
        client_rut = client_data["RUT"]
        holdings = reader.get_client_holdings(client_rut)
        needs_rebal, reason, dev = reader.check_rebalance_needed(client_rut)

        if needs_rebal:
            callout("warn", f"<strong>⚠️ Rebalancing requerido</strong><br>{reason}")
            actions = partitioner.get_rebalancing_needs(holdings, client_data["Architecture"],
                                                        client_data["Risk_Profile"])
            if actions:
                with st.container(border=True):
                    card_title("Acciones Recomendadas")
                    html_table(pd.DataFrame(actions))
        else:
            callout("ok", "<strong>✅ Portafolio balanceado</strong><br>No se requiere rebalancing en este momento.")

    # ---------------------------------------------------------- NOTAS
    elif page.endswith("Notas"):
        page_title("Notebook de Cliente")
        selected_name = st.selectbox("Cliente", clients["Name"].tolist(), key="notes")
        client_data = clients[clients["Name"] == selected_name].iloc[0]
        client_rut = client_data["RUT"]
        st.markdown(f"<div class='stat-label'>RUT</div><div class='stat-value' style='font-size:16px'>{client_rut}</div>",
                    unsafe_allow_html=True)

        with st.container(border=True):
            card_title("Agregar Nota")
            new_note = st.text_area("Nota", placeholder="Explica la situación del cliente, cambios, decisiones...")
            advisor_name = st.text_input("Nombre del Asesor", placeholder="Tu nombre")
            if st.button("📝 Guardar Nota"):
                if new_note and advisor_name:
                    success, msg = notebook.add_note(client_rut, selected_name, new_note, advisor_name)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("Por favor completa todos los campos")

        with st.container(border=True):
            card_title("Historial de Notas")
            notes_df = notebook.get_client_notebook_df(client_rut)
            if not notes_df.empty:
                st.dataframe(notes_df, use_container_width=True, hide_index=True)
            else:
                st.info("No hay notas para este cliente")

# ================================================================ MANAGING DIRECTOR
else:
    st.markdown(f"<div class='hello'>Hello,</div><div class='hello-name'>{greeting_name}</div>",
                unsafe_allow_html=True)
    business_summary = reader.get_business_summary()
    clients_raw = reader.read_clients()

    c1, c2, c3 = st.columns([1, 1, 1.25])
    with c1, st.container(border=True):
        card_title("AUM Total")
        st.markdown(f"<div class='big-value'>{money(business_summary['total_aum'])}</div>", unsafe_allow_html=True)
        s1, s2 = st.columns(2)
        s1.markdown(f"<div class='stat-label'>Clientes</div><div class='stat-value'>{business_summary['num_clients']}</div>",
                    unsafe_allow_html=True)
        s2.markdown(f"<div class='stat-label'>Asesores</div><div class='stat-value'>{business_summary['num_advisors']}</div>",
                    unsafe_allow_html=True)
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        s3, s4 = st.columns(2)
        s3.markdown(f"<div class='stat-label'>Portafolio promedio</div><div class='stat-value'>{money(business_summary['avg_portfolio_value'])}</div>",
                    unsafe_allow_html=True)
        s4.markdown(f"<div class='stat-label'>Acción requerida</div><div class='stat-value'>{business_summary['clients_needing_rebalance']}</div>",
                    unsafe_allow_html=True)

    with c2, st.container(border=True):
        card_title("Top Asesores")
        by_adv = (clients_raw.groupby("Advisor_ID")["Portfolio_Value_USD"].sum()
                  .sort_values(ascending=False).reset_index())
        total = by_adv["Portfolio_Value_USD"].sum()
        top = pd.DataFrame({
            "Asesor": by_adv["Advisor_ID"],
            "% del total": (by_adv["Portfolio_Value_USD"] / total * 100).map("{:.0f}%".format),
            "Valor": by_adv["Portfolio_Value_USD"].map(money),
        }).head(7)
        html_table(top, num_cols=("% del total", "Valor"))

    with c3, st.container(border=True):
        card_title("Distribución por Servicio")
        scol = service_of(clients_raw)
        if scol:
            dist = clients_raw.groupby(scol)["Portfolio_Value_USD"].sum().sort_values(ascending=False)
            a, b = st.columns([1.1, 1])
            with a:
                st.plotly_chart(donut(dist.index.tolist(), dist.values, "TOTAL AUM",
                                      money(business_summary["total_aum"]), 280),
                                use_container_width=True, config={"displayModeBar": False})
            with b:
                st.markdown("<div style='height:50px'></div>" + legend_html(dist.index, dist.values),
                            unsafe_allow_html=True)

    with st.container(border=True):
        card_title("AUM por Asesor")
        fig = go.Figure(go.Bar(x=by_adv["Advisor_ID"], y=by_adv["Portfolio_Value_USD"], marker_color="#7fc8d0",
                               hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>"))
        style_fig(fig, 320)
        fig.update_yaxes(tickprefix="$", tickformat=".2s")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

st.markdown(f"<div class='footnote' style='margin-top:24px'>Portfolio Control Center | "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>", unsafe_allow_html=True)
