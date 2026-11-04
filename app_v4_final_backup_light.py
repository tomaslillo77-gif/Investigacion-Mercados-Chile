import streamlit as st
import pandas as pd
from datetime import datetime
from data_reader import PortfolioDataReader
from client_notebook import ClientNotebook
from portfolio_partitioner import PortfolioPartitioner
from custom_architecture import CustomArchitecture
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(
    page_title="Portfolio Control Center V4",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main { padding: 2rem; }
    .header-title { font-size: 36px; font-weight: 700; color: #1F4E78; margin-bottom: 0.5rem; }
    .header-subtitle { font-size: 14px; color: #666; margin-bottom: 2rem; }
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 8px; padding: 1.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    .metric-value { font-size: 28px; font-weight: 700; color: #1F4E78; }
    .metric-label { font-size: 12px; color: #666; text-transform: uppercase; }
    .alert-box { background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 1rem; border-radius: 4px; margin: 1rem 0; }
    .success-box { background-color: #d4edda; border-left: 4px solid #28a745; padding: 1rem; border-radius: 4px; }
    .info-box { background-color: #d1ecf1; border-left: 4px solid #17a2b8; padding: 1rem; border-radius: 4px; }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] { background-color: #1F4E78; color: white; }
</style>
""", unsafe_allow_html=True)

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

# Initialize partitioner with actual data
try:
    portfolio_archs = reader.read_portfolio_architectures()
    if isinstance(portfolio_archs, pd.DataFrame) and not portfolio_archs.empty:
        partitioner = PortfolioPartitioner(portfolio_archs)
    else:
        partitioner = PortfolioPartitioner(None)
except:
    partitioner = PortfolioPartitioner(None)

# Sidebar
with st.sidebar:
    st.markdown("## 👤 Control Center")
    user_role = st.radio("Rol:", ["Investment Advisor", "Managing Director"], label_visibility="collapsed")

    if user_role == "Investment Advisor":
        advisors = reader.read_advisors()
        advisor_id = st.selectbox("Asesor:", advisors['Advisor_ID'].tolist(), label_visibility="collapsed")
    else:
        advisor_id = None

    st.divider()
    st.caption(f"Actualizado: {datetime.now().strftime('%H:%M:%S')}")

st.markdown("""
<div class="header-title">📊 Portfolio Control Center</div>
<div class="header-subtitle">Gestión centralizada y control de portafolios de clientes</div>
""", unsafe_allow_html=True)

if user_role == "Investment Advisor":
    # ==================== ADVISOR VIEW ====================
    advisor_summary = reader.get_advisor_summary(advisor_id)
    clients = reader.get_clients_by_advisor(advisor_id)

    tabs = st.tabs(["Dashboard", "Clientes", "Análisis Detallado", "Rebalancing", "Notas Compartidas"])

    with tabs[0]:  # Dashboard
        st.markdown("### Resumen de Portafolios")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">Clientes Totales</div>
                <div class="metric-value">{advisor_summary['num_clients']}</div>
            </div>""", unsafe_allow_html=True)
        with col2:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">AUM</div>
                <div class="metric-value">${advisor_summary['total_aum'] / 1e6:.2f}M</div>
            </div>""", unsafe_allow_html=True)
        with col3:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">Portafolios Gestionados</div>
                <div class="metric-value">{advisor_summary['managed_clients']}</div>
            </div>""", unsafe_allow_html=True)
        with col4:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">Acción Requerida</div>
                <div class="metric-value">{advisor_summary['clients_needing_rebalance']}</div>
            </div>""", unsafe_allow_html=True)

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            top_clients = clients.nlargest(8, 'Portfolio_Value_USD')[['Name', 'Portfolio_Value_USD']]
            fig = px.bar(top_clients, x='Portfolio_Value_USD', y='Name', orientation='h',
                        title='Top 8 Clientes por AUM', color='Portfolio_Value_USD',
                        color_continuous_scale='Blues')
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            service_col = 'Service_Type' if 'Service_Type' in clients.columns else 'Servicio'
            if service_col in clients.columns:
                service_dist = clients[service_col].value_counts()
                fig = px.pie(values=service_dist.values, names=service_dist.index,
                            title='Distribución por Tipo de Servicio')
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos de Servicio disponibles")

    with tabs[1]:  # Clientes
        st.markdown("### Lista de Clientes")

        client_data = []
        for _, client in clients.iterrows():
            rut = client['RUT']
            needs_rebal, _, dev = reader.check_rebalance_needed(rut)
            holdings = reader.get_client_holdings(rut)

            client_data.append({
                'Cliente': client['Name'],
                'RUT': rut,
                'Valor': f"${client['Portfolio_Value_USD']:,.0f}",
                'Servicio': str(client.get('Service_Type', client.get('Servicio', ''))).strip(),
                'Perfil': client['Risk_Profile'],
                'Posiciones': len(holdings),
                'Rebalance': '⚠️ Sí' if needs_rebal else '✅ No',
            })

        st.dataframe(pd.DataFrame(client_data), use_container_width=True, hide_index=True)

    with tabs[2]:  # Análisis Detallado
        st.markdown("### Análisis Detallado de Cliente")

        selected_name = st.selectbox("Selecciona cliente:", clients['Name'].tolist())
        client_data = clients[clients['Name'] == selected_name].iloc[0]
        client_rut = client_data['RUT']

        # Client header
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Valor Portafolio", f"${client_data['Portfolio_Value_USD']:,.0f}")
        with col2:
            service_val = client_data.get('Service_Type', client_data.get('Servicio', 'N/A'))
            st.metric("Servicio", service_val)
        with col3:
            st.metric("Perfil", client_data['Risk_Profile'])
        with col4:
            st.metric("Arquitectura", client_data['Architecture'])
        with col5:
            kpis = reader.calculate_portfolio_kpis(client_rut)
            st.metric("Diversif.", f"{kpis['diversification_score']:.0f}%")

        st.divider()

        # Portfolio Partition
        holdings = reader.get_client_holdings(client_rut)
        partition = partitioner.partition_portfolio(holdings, client_data['Architecture'], client_data['Risk_Profile'])

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""<div class="success-box">
            <strong>En Cartera Modelo</strong><br>
            ${partition['in_model_value']:,.0f} ({partition['in_model_pct']:.1f}%)
            </div>""", unsafe_allow_html=True)
        with col2:
            st.markdown(f"""<div class="alert-box">
            <strong>Fuera de Cartera</strong><br>
            ${partition['outside_model_value']:,.0f} ({partition['outside_model_pct']:.1f}%)
            </div>""", unsafe_allow_html=True)
        with col3:
            st.markdown(f"""<div class="info-box">
            <strong>Total AUM</strong><br>
            ${partition['total_value']:,.0f}
            </div>""", unsafe_allow_html=True)

        # Visualization
        if partition['in_model_value'] > 0 or partition['outside_model_value'] > 0:
            fig = go.Figure(data=[go.Pie(
                labels=['En Cartera Modelo', 'Fuera de Cartera'],
                values=[partition['in_model_pct'], partition['outside_model_pct']],
                marker=dict(colors=['#27AE60', '#E67E22'])
            )])
            fig.update_layout(title="Partición del Portafolio", height=400)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # Instruments comparison
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Instrumentos en Cartera Modelo")
            if not partition['in_model_instruments'].empty:
                display_df = partition['in_model_instruments'][[
                    'Instrumento', 'Valor', 'Target_%', 'Actual_%'
                ]].copy()
                display_df['Valor'] = display_df['Valor'].apply(lambda x: f"${x:,.0f}")
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                st.info("No hay instrumentos en cartera modelo")

        with col2:
            st.markdown("#### Instrumentos Fuera de Cartera")
            if not partition['outside_model_instruments'].empty:
                display_df = partition['outside_model_instruments'][[
                    'Instrumento', 'Valor', 'Pct_del_Total'
                ]].copy()
                display_df['Valor'] = display_df['Valor'].apply(lambda x: f"${x:,.0f}")
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                st.info("No hay instrumentos fuera de cartera")

    with tabs[3]:  # Rebalancing
        st.markdown("### Recomendaciones de Rebalancing")

        selected_name = st.selectbox("Selecciona cliente:", clients['Name'].tolist(), key="rebal")
        client_data = clients[clients['Name'] == selected_name].iloc[0]
        client_rut = client_data['RUT']
        holdings = reader.get_client_holdings(client_rut)

        needs_rebal, reason, dev = reader.check_rebalance_needed(client_rut)

        if needs_rebal:
            st.markdown(f"""<div class="alert-box">
            <strong>⚠️ Rebalancing Requerido</strong><br>
            {reason}
            </div>""", unsafe_allow_html=True)

            # Get rebalancing actions
            partition = partitioner.partition_portfolio(holdings, client_data['Architecture'], client_data['Risk_Profile'])
            actions = partitioner.get_rebalancing_needs(holdings, client_data['Architecture'], client_data['Risk_Profile'])

            if actions:
                st.markdown("#### Acciones Recomendadas")
                actions_df = pd.DataFrame(actions)
                st.dataframe(actions_df, use_container_width=True, hide_index=True)
        else:
            st.markdown("""<div class="success-box">
            <strong>✅ Portafolio Balanceado</strong><br>
            No se requiere rebalancing en este momento.
            </div>""", unsafe_allow_html=True)

    with tabs[4]:  # Notas Compartidas
        st.markdown("### Notebook de Cliente")

        selected_name = st.selectbox("Selecciona cliente:", clients['Name'].tolist(), key="notes")
        client_data = clients[clients['Name'] == selected_name].iloc[0]
        client_rut = client_data['RUT']

        st.markdown(f"**Cliente:** {selected_name}")
        st.markdown(f"**RUT:** {client_rut}")

        st.divider()

        # Add new note
        st.markdown("#### Agregar Nota")
        new_note = st.text_area("Nota:", placeholder="Explica la situación del cliente, cambios, decisiones...")

        advisor_name = st.text_input("Nombre del Asesor:", placeholder="Tu nombre")

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

        st.divider()

        # Display existing notes
        st.markdown("#### Historial de Notas")
        notes_df = notebook.get_client_notebook_df(client_rut)

        if not notes_df.empty:
            st.dataframe(notes_df, use_container_width=True, hide_index=True)
        else:
            st.info("No hay notas para este cliente")

else:
    # ==================== MANAGING DIRECTOR VIEW ====================
    st.markdown("### Visión de Negocio")

    business_summary = reader.get_business_summary()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("AUM Total", f"${business_summary['total_aum'] / 1e6:.2f}M")
    with col2:
        st.metric("Clientes", business_summary['num_clients'])
    with col3:
        st.metric("Asesores", business_summary['num_advisors'])
    with col4:
        st.metric("Portafolio Promedio", f"${business_summary['avg_portfolio_value'] / 1000:.0f}K")
    with col5:
        st.metric("Acción Requerida", business_summary['clients_needing_rebalance'])

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        clients_raw = reader.read_clients()
        aum_by_adv = clients_raw.groupby('Advisor_ID')['Portfolio_Value_USD'].sum().reset_index()
        fig = px.bar(aum_by_adv, x='Advisor_ID', y='Portfolio_Value_USD',
                    title='AUM por Asesor', color='Portfolio_Value_USD', color_continuous_scale='Blues')
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Use Servicio column (renamed from Service_Type by data_reader)
        service_col = 'Service_Type' if 'Service_Type' in clients_raw.columns else 'Servicio'
        service_dist = clients_raw[service_col].value_counts()
        fig = px.pie(values=service_dist.values, names=service_dist.index,
                    title='Distribución por Tipo de Servicio')
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

st.divider()
st.caption(f"Portfolio Control Center V4 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
