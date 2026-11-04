import streamlit as st
import pandas as pd
from datetime import datetime
from data_reader import PortfolioDataReader
from portfolio_personalizer import PortfolioPersonalizer, PortfolioModelManager
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

st.set_page_config(
    page_title="Portfolio Dashboard V3",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={}
)

# Custom CSS
st.markdown("""
<style>
    .main { padding: 2rem; }
    .header-title { font-size: 32px; font-weight: 700; color: #1F4E78; margin-bottom: 0.5rem; }
    .header-subtitle { font-size: 14px; color: #666; margin-bottom: 2rem; }
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 8px; padding: 1.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    .metric-value { font-size: 28px; font-weight: 700; color: #1F4E78; margin-bottom: 0.5rem; }
    .metric-label { font-size: 13px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }
    .alert-box { background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 1rem; border-radius: 4px; margin: 1rem 0; }
    .success-box { background-color: #d4edda; border-left: 4px solid #28a745; padding: 1rem; border-radius: 4px; margin: 1rem 0; }
    .danger-box { background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 1rem; border-radius: 4px; margin: 1rem 0; }
    .stTabs [data-baseweb="tab-list"] button { background-color: #f0f2f6; color: #1F4E78; font-weight: 600; }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] { background-color: #1F4E78; color: white; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_data_reader():
    return PortfolioDataReader()

@st.cache_resource
def get_personalizer():
    return PortfolioPersonalizer()

reader = get_data_reader()
personalizer = get_personalizer()

# Sidebar
with st.sidebar:
    st.markdown("## 👤 User Access")
    user_role = st.radio("Select your role:", ["Investment Advisor", "Managing Director"], label_visibility="collapsed")

    if user_role == "Investment Advisor":
        advisors = reader.read_advisors()
        advisor_list = advisors['Advisor_ID'].tolist()
        advisor_id = st.selectbox("Select Advisor:", advisor_list, label_visibility="collapsed")
    else:
        advisor_id = None

    st.divider()
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Main title
st.markdown("""
<div class="header-title">📊 Portfolio Management Dashboard V3</div>
<div class="header-subtitle">Advanced wealth management with customizable portfolios</div>
""", unsafe_allow_html=True)

if user_role == "Investment Advisor":
    # ==================== INVESTMENT ADVISOR VIEW ====================
    advisor_summary = reader.get_advisor_summary(advisor_id)
    clients = reader.get_clients_by_advisor(advisor_id)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Dashboard", "Clients", "Analysis", "Portfolio Customization", "Alerts", "Reports"])

    with tab1:
        st.markdown("### Portfolio Overview")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Clients</div>
                <div class="metric-value">{advisor_summary['num_clients']}</div>
                <div class="metric-label" style="margin-top: 0.5rem;">{advisor_summary['managed_clients']} Managed</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Assets Under Management</div>
                <div class="metric-value">${advisor_summary['total_aum'] / 1e6:.2f}M</div>
                <div class="metric-label" style="margin-top: 0.5rem;">Avg: ${advisor_summary['avg_portfolio_value'] / 1000:.1f}K</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Avg Diversification</div>
                <div class="metric-value">{advisor_summary['avg_diversification']:.1f}%</div>
                <div class="metric-label" style="margin-top: 0.5rem;">Optimal: 70%+</div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Rebalancing Needed</div>
                <div class="metric-value">{advisor_summary['clients_needing_rebalance']}</div>
                <div class="metric-label" style="margin-top: 0.5rem;">Action Items</div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            client_values = clients[['Name', 'Portfolio_Value_USD']].copy()
            fig = px.bar(
                client_values.sort_values('Portfolio_Value_USD', ascending=False).head(10),
                x='Name', y='Portfolio_Value_USD',
                title='Top 10 Clients by Portfolio Value',
                color='Portfolio_Value_USD',
                color_continuous_scale='Blues'
            )
            fig.update_layout(height=400, showlegend=False, hovermode='x unified')
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            portfolio_types = clients['Portfolio_Type'].value_counts()
            fig = go.Figure(data=[go.Pie(
                labels=portfolio_types.index,
                values=portfolio_types.values,
                marker=dict(colors=['#1F4E78', '#27AE60'])
            )])
            fig.update_layout(title="Portfolio Type Distribution", height=400)
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.markdown("### Client Portfolio Management")

        clients_data = []
        for _, client in clients.iterrows():
            rut = client['RUT']
            needs_rebalance, reason, deviation = reader.check_rebalance_needed(rut)
            kpis = reader.calculate_portfolio_kpis(rut)
            holdings = reader.get_client_holdings(rut)

            clients_data.append({
                'Client': client['Name'],
                'RUT': rut,
                'Value': f"${client['Portfolio_Value_USD']:,.0f}",
                'Risk': client['Risk_Profile'],
                'Service': client['Service_Type'],
                'Type': client['Portfolio_Type'],
                'Positions': len(holdings),
                'Diversification': f"{kpis.get('diversification_score', 0):.1f}%",
                'Rebalance': '⚠️ Yes' if needs_rebalance else '✅ No',
            })

        df_clients = pd.DataFrame(clients_data)
        st.dataframe(df_clients, use_container_width=True, hide_index=True)

    with tab3:
        st.markdown("### Detailed Portfolio Analysis")

        selected_client = st.selectbox(
            "Select a client:",
            clients['Name'].tolist(),
            key="client_select_adv"
        )

        client_data = clients[clients['Name'] == selected_client].iloc[0]
        client_rut = client_data['RUT']
        holdings = reader.get_client_holdings(client_rut)
        kpis = reader.calculate_portfolio_kpis(client_rut)
        needs_rebalance, reason, max_deviation = reader.check_rebalance_needed(client_rut)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Portfolio Value", f"${client_data['Portfolio_Value_USD']:,.0f}")
        with col2:
            st.metric("Risk Profile", client_data['Risk_Profile'])
        with col3:
            st.metric("Service Type", client_data['Service_Type'])
        with col4:
            st.metric("Diversification", f"{kpis['diversification_score']:.1f}%")

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            if not holdings.empty:
                fig = go.Figure(data=[
                    go.Bar(
                        name='Target %',
                        x=holdings['Asset_Class'],
                        y=holdings['Target_Allocation_%'],
                        marker_color='rgba(31, 78, 120, 0.7)'
                    ),
                    go.Bar(
                        name='Current %',
                        x=holdings['Asset_Class'],
                        y=holdings['Current_Allocation_%'],
                        marker_color='rgba(39, 174, 96, 0.7)'
                    )
                ])
                fig.update_layout(
                    title="Target vs Current Allocation",
                    xaxis_title="Asset Class",
                    yaxis_title="Allocation %",
                    barmode='group',
                    height=450,
                    hovermode='x unified'
                )
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            if not holdings.empty:
                fig = go.Figure(data=[go.Pie(
                    labels=holdings['Asset_Class'],
                    values=holdings['Current_Value_USD'],
                    marker=dict(colors=['#1F4E78', '#27AE60', '#E67E22', '#9B59B6', '#34495E', '#16A085'])
                )])
                fig.update_layout(title="Portfolio Composition", height=450)
                st.plotly_chart(fig, use_container_width=True)

        st.divider()

        st.markdown("### Position Details")
        if not holdings.empty:
            holdings_display = holdings[[
                'Asset_Class', 'Position_Name', 'Units', 'Unit_Price_USD',
                'Current_Value_USD', 'Target_Allocation_%', 'Current_Allocation_%'
            ]].copy()

            holdings_display['Unit_Price_USD'] = holdings_display['Unit_Price_USD'].apply(lambda x: f"${x:,.2f}")
            holdings_display['Current_Value_USD'] = holdings_display['Current_Value_USD'].apply(lambda x: f"${x:,.0f}")
            holdings_display.columns = [
                'Asset Class', 'Position', 'Units', 'Price', 'Value',
                'Target %', 'Current %'
            ]

            st.dataframe(holdings_display, use_container_width=True, hide_index=True)

        if needs_rebalance:
            st.markdown(f"""<div class="alert-box">
            <strong>⚠️ Rebalancing Recommended</strong><br>
            {reason}
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""<div class="success-box">
            <strong>✅ Portfolio is Well Balanced</strong>
            </div>""", unsafe_allow_html=True)

    with tab4:
        st.markdown("### 🎯 Portfolio Customization")

        st.markdown("""
        #### Customize Portfolio Models by Client

        Change the target allocation for each client based on their needs:
        - **No USD exposure** → Remove Renta Variable (Stocks)
        - **Fixed USD percentage** → Set specific allocation
        - **Custom allocation** → Design your own mix
        """)

        st.divider()

        # Select client to customize
        selected_client = st.selectbox(
            "Select client to customize:",
            clients['Name'].tolist(),
            key="client_customize"
        )

        client_data = clients[clients['Name'] == selected_client].iloc[0]
        client_rut = client_data['RUT']
        client_service = client_data['Service_Type']

        st.markdown(f"**Selected Client:** {selected_client} ({client_rut})")
        st.markdown(f"**Service Type:** {client_service}")
        st.markdown(f"**Portfolio Value:** ${client_data['Portfolio_Value_USD']:,.0f}")

        # Check if client can have customization
        if client_service in ['Self-Directed', 'Depósito a Plazo', 'DAP']:
            st.warning("⚠️ This client has a Self-Directed service and does not have a portfolio model.")
        else:
            st.divider()

            # Show current allocation
            st.markdown("#### Current Target Allocation")
            holdings = reader.get_client_holdings(client_rut)

            if not holdings.empty:
                current_alloc = dict(zip(holdings['Asset_Class'], holdings['Target_Allocation_%']))
                col_data = []
                for asset, pct in current_alloc.items():
                    col_data.append({'Asset Class': asset, 'Target %': pct})
                df_current = pd.DataFrame(col_data)
                st.dataframe(df_current, use_container_width=True, hide_index=True)

            st.divider()

            # Customization options
            st.markdown("#### Customization Options")

            customization_type = st.radio(
                "Choose customization type:",
                ["Keep Current", "Remove USD Exposure", "Fixed USD %", "Custom Allocation"],
                horizontal=False
            )

            if customization_type == "Keep Current":
                st.info("No changes will be made to this client's portfolio.")

            elif customization_type == "Remove USD Exposure":
                st.markdown("**Remove Renta Variable (Stocks) from allocation**")

                if st.button("Apply - Remove USD Exposure", key=f"remove_usd_{client_rut}"):
                    # Reallocate from stocks to other assets
                    new_alloc = {
                        'Renta Variable': 0.0,
                        'Renta Fija': 0.45,
                        'Alternatives': 0.35,
                        'Cash': 0.20
                    }

                    success, msg = personalizer.create_custom_allocation(
                        client_rut,
                        f"No USD - {datetime.now().strftime('%Y-%m-%d')}",
                        new_alloc
                    )

                    if success:
                        st.success(f"✅ {msg}")
                        st.markdown("**New Allocation:**")
                        for asset, pct in new_alloc.items():
                            st.write(f"- {asset}: {pct * 100:.0f}%")
                    else:
                        st.error(f"❌ {msg}")

            elif customization_type == "Fixed USD %":
                st.markdown("**Set a specific percentage for Renta Variable (Stocks)**")

                usd_pct = st.slider(
                    "USD Percentage (Renta Variable):",
                    min_value=0,
                    max_value=100,
                    value=50,
                    step=5
                )

                # Show what other allocations will be
                remaining = 1.0 - (usd_pct / 100)
                other_pcts = {
                    'Renta Fija': remaining * 0.50,
                    'Alternatives': remaining * 0.35,
                    'Cash': remaining * 0.15
                }

                st.markdown("**Resulting Allocation:**")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Renta Variable", f"{usd_pct}%")
                with col2:
                    st.metric("Renta Fija", f"{other_pcts['Renta Fija'] * 100:.0f}%")
                with col3:
                    st.metric("Alternatives", f"{other_pcts['Alternatives'] * 100:.0f}%")
                with col4:
                    st.metric("Cash", f"{other_pcts['Cash'] * 100:.0f}%")

                if st.button("Apply - Fixed USD %", key=f"fixed_usd_{client_rut}"):
                    new_alloc = {
                        'Renta Variable': usd_pct / 100,
                        'Renta Fija': other_pcts['Renta Fija'],
                        'Alternatives': other_pcts['Alternatives'],
                        'Cash': other_pcts['Cash']
                    }

                    success, msg = personalizer.create_custom_allocation(
                        client_rut,
                        f"Fixed USD {usd_pct}% - {datetime.now().strftime('%Y-%m-%d')}",
                        new_alloc
                    )

                    if success:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")

            elif customization_type == "Custom Allocation":
                st.markdown("**Design your own allocation**")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    rv = st.number_input("Renta Variable %", min_value=0, max_value=100, value=50) / 100
                with col2:
                    rf = st.number_input("Renta Fija %", min_value=0, max_value=100, value=30) / 100
                with col3:
                    alt = st.number_input("Alternatives %", min_value=0, max_value=100, value=15) / 100
                with col4:
                    cash = st.number_input("Cash %", min_value=0, max_value=100, value=5) / 100

                total = rv + rf + alt + cash
                st.markdown(f"**Total: {total * 100:.1f}%**")

                if abs(total - 1.0) > 0.01:
                    st.error(f"❌ Allocations must sum to 100%. Current: {total * 100:.1f}%")
                elif st.button("Apply - Custom Allocation", key=f"custom_{client_rut}"):
                    new_alloc = {
                        'Renta Variable': rv,
                        'Renta Fija': rf,
                        'Alternatives': alt,
                        'Cash': cash
                    }

                    success, msg = personalizer.create_custom_allocation(
                        client_rut,
                        f"Custom - {datetime.now().strftime('%Y-%m-%d')}",
                        new_alloc
                    )

                    if success:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")

            st.divider()

            # Reset option
            if st.button("🔄 Reset to Default Portfolio", key=f"reset_{client_rut}"):
                success, msg = personalizer.reset_to_default(client_rut)
                if success:
                    st.success(f"✅ {msg}")
                else:
                    st.info(msg)

    with tab5:
        st.markdown("### Portfolio Alerts & Recommendations")

        alerts = []
        for _, client in clients.iterrows():
            rut = client['RUT']
            needs_rebalance, reason, deviation = reader.check_rebalance_needed(rut)
            kpis = reader.calculate_portfolio_kpis(rut)

            if needs_rebalance:
                alerts.append({
                    'Client': client['Name'],
                    'Type': '⚠️ Rebalancing',
                    'Issue': reason,
                    'Deviation': f"{deviation:.1f}%",
                })

            if kpis['diversification_score'] < 50:
                alerts.append({
                    'Client': client['Name'],
                    'Type': '⚠️ Low Div',
                    'Issue': f"Score: {kpis['diversification_score']:.1f}%",
                    'Deviation': 'Low',
                })

        if alerts:
            df_alerts = pd.DataFrame(alerts)
            st.dataframe(df_alerts, use_container_width=True, hide_index=True)
        else:
            st.success("✅ No active alerts")

    with tab6:
        st.markdown("### Performance Reports")

        col1, col2 = st.columns(2)
        with col1:
            clients_sorted = clients.sort_values('Portfolio_Value_USD', ascending=True).tail(10)
            fig = px.barh(
                clients_sorted,
                x='Portfolio_Value_USD',
                y='Name',
                title='Largest Client Portfolios',
                color='Portfolio_Value_USD',
                color_continuous_scale='Greens'
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            perf_data = []
            for _, client in clients.iterrows():
                kpis = reader.calculate_portfolio_kpis(client['RUT'])
                perf_data.append({
                    'Client': client['Name'],
                    'Diversification': kpis['diversification_score'],
                    'Risk Level': len(client['Risk_Profile']),
                    'Portfolio Value': client['Portfolio_Value_USD']
                })

            df_perf = pd.DataFrame(perf_data)
            fig = px.scatter(
                df_perf,
                x='Diversification',
                y='Risk Level',
                size='Portfolio Value',
                hover_name='Client',
                title='Diversification Analysis',
                color='Portfolio Value',
                color_continuous_scale='Viridis'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

else:
    # ==================== MANAGING DIRECTOR VIEW ====================
    st.markdown("### Business Overview")

    business_summary = reader.get_business_summary()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total AUM", f"${business_summary['total_aum'] / 1e6:.2f}M")
    with col2:
        st.metric("Total Clients", business_summary['num_clients'])
    with col3:
        st.metric("Active Advisors", business_summary['num_advisors'])
    with col4:
        st.metric("Avg Portfolio", f"${business_summary['avg_portfolio_value'] / 1000:.1f}K")
    with col5:
        st.metric("Action Items", business_summary['clients_needing_rebalance'])

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        clients_raw = reader.read_clients()
        aum_by_advisor = clients_raw.groupby('Advisor_ID')['Portfolio_Value_USD'].sum().reset_index()
        fig = px.bar(
            aum_by_advisor,
            x='Advisor_ID',
            y='Portfolio_Value_USD',
            title='AUM by Advisor',
            color='Portfolio_Value_USD',
            color_continuous_scale='Blues'
        )
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        risk_dist = clients_raw['Risk_Profile'].value_counts()
        fig = px.pie(
            values=risk_dist.values,
            names=risk_dist.index,
            title='Client Risk Profile Distribution',
            color_discrete_sequence=['#1F4E78', '#27AE60', '#E67E22', '#9B59B6', '#34495E']
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

st.divider()
st.caption(f"Portfolio Dashboard V3 | Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
