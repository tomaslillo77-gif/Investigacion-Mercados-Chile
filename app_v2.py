import streamlit as st
import pandas as pd
from datetime import datetime
from data_reader import PortfolioDataReader
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

st.set_page_config(
    page_title="Portfolio Dashboard V2",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={}
)

# Custom CSS for professional styling
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

reader = get_data_reader()

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
<div class="header-title">📊 Portfolio Management Dashboard V2</div>
<div class="header-subtitle">Advanced wealth management analytics & portfolio intelligence</div>
""", unsafe_allow_html=True)

if user_role == "Investment Advisor":
    # ==================== INVESTMENT ADVISOR VIEW ====================
    advisor_summary = reader.get_advisor_summary(advisor_id)
    clients = reader.get_clients_by_advisor(advisor_id)

    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Dashboard", "Clients", "Analysis", "Alerts", "Reports"])

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
            status_color = "warning" if advisor_summary['clients_needing_rebalance'] > 0 else "ok"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Rebalancing Needed</div>
                <div class="metric-value">{advisor_summary['clients_needing_rebalance']}</div>
                <div class="metric-label" style="margin-top: 0.5rem;">Action Items</div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # Charts row 1
        col1, col2 = st.columns(2)

        with col1:
            # Portfolio value distribution
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
            # Portfolio type distribution
            portfolio_types = clients['Portfolio_Type'].value_counts()
            fig = go.Figure(data=[go.Pie(
                labels=portfolio_types.index,
                values=portfolio_types.values,
                marker=dict(colors=['#1F4E78', '#27AE60'])
            )])
            fig.update_layout(title="Portfolio Type Distribution", height=400)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # Charts row 2
        col1, col2 = st.columns(2)

        with col1:
            # Risk profile distribution
            risk_dist = clients['Risk_Profile'].value_counts().reset_index()
            risk_dist.columns = ['Risk_Profile', 'Count']
            fig = px.bar(
                risk_dist,
                x='Risk_Profile', y='Count',
                title='Client Distribution by Risk Profile',
                color='Count',
                color_continuous_scale='Viridis'
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Architecture distribution
            arch_dist = clients['Architecture'].value_counts().reset_index()
            arch_dist.columns = ['Architecture', 'Count']
            fig = px.bar(
                arch_dist,
                x='Architecture', y='Count',
                title='Client Distribution by Architecture',
                color='Count',
                color_continuous_scale='Plasma'
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.markdown("### Client Portfolio Management")

        # Clients table with detailed metrics
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
                'Architecture': client['Architecture'],
                'Service': client['Service_Type'],
                'Type': client['Portfolio_Type'],
                'Positions': len(holdings),
                'Diversification': f"{kpis.get('diversification_score', 0):.1f}%",
                'Rebalance': '⚠️ Yes' if needs_rebalance else '✅ No',
                'Deviation': f"{deviation:.1f}%"
            })

        df_clients = pd.DataFrame(clients_data)
        st.dataframe(df_clients, use_container_width=True, hide_index=True)

        # Export option
        csv = df_clients.to_csv(index=False)
        st.download_button(
            label="📥 Download Client List (CSV)",
            data=csv,
            file_name="clients_list.csv",
            mime="text/csv"
        )

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

        # Client header
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Portfolio Value", f"${client_data['Portfolio_Value_USD']:,.0f}")
        with col2:
            st.metric("Risk Profile", client_data['Risk_Profile'])
        with col3:
            st.metric("Architecture", client_data['Architecture'])
        with col4:
            st.metric("Diversification", f"{kpis['diversification_score']:.1f}%")

        st.divider()

        # Allocation charts
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

        # Holdings table
        st.markdown("### Position Details")
        if not holdings.empty:
            holdings_display = holdings[[
                'Asset_Class', 'Position_Name', 'Units', 'Unit_Price_USD',
                'Current_Value_USD', 'Target_Allocation_%', 'Current_Allocation_%',
                'Unrealized_Gains_CLP', 'Unrealized_Return_%'
            ]].copy()

            holdings_display['Unit_Price_USD'] = holdings_display['Unit_Price_USD'].apply(lambda x: f"${x:,.2f}")
            holdings_display['Current_Value_USD'] = holdings_display['Current_Value_USD'].apply(lambda x: f"${x:,.0f}")
            holdings_display['Unrealized_Gains_CLP'] = holdings_display['Unrealized_Gains_CLP'].apply(lambda x: f"${x:,.0f}")
            holdings_display.columns = [
                'Asset Class', 'Position', 'Units', 'Price', 'Value',
                'Target %', 'Current %', 'Unrealized P&L', 'Return %'
            ]

            st.dataframe(holdings_display, use_container_width=True, hide_index=True)

        st.divider()

        # Rebalancing recommendation
        if needs_rebalance:
            st.markdown("""<div class="alert-box">
            <strong>⚠️ Rebalancing Recommended</strong><br>
            """ + reason + """<br>
            Maximum deviation: """ + f"{max_deviation:.1f}%" + """
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""<div class="success-box">
            <strong>✅ Portfolio is Well Balanced</strong><br>
            No immediate rebalancing needed. All allocations within target ranges.
            </div>""", unsafe_allow_html=True)

    with tab4:
        st.markdown("### Portfolio Alerts & Recommendations")

        alerts = []

        # Scan all clients for alerts
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
                    'Action': 'Review and rebalance'
                })

            if kpis['diversification_score'] < 50:
                alerts.append({
                    'Client': client['Name'],
                    'Type': '⚠️ Low Diversification',
                    'Issue': f"Score: {kpis['diversification_score']:.1f}%",
                    'Deviation': 'Low',
                    'Action': 'Add more asset classes'
                })

        if alerts:
            df_alerts = pd.DataFrame(alerts)
            st.dataframe(df_alerts, use_container_width=True, hide_index=True)
        else:
            st.markdown("""<div class="success-box">
            <strong>✅ No Active Alerts</strong><br>
            All client portfolios are performing well.
            </div>""", unsafe_allow_html=True)

    with tab5:
        st.markdown("### Performance Reports")

        col1, col2 = st.columns(2)

        with col1:
            # AUM growth
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
            # Risk vs Return
            perf_data = []
            for _, client in clients.iterrows():
                kpis = reader.calculate_portfolio_kpis(client['RUT'])
                perf_data.append({
                    'Client': client['Name'],
                    'Diversification': kpis['diversification_score'],
                    'Target Return': client['Target_Return_%'],
                    'Portfolio Value': client['Portfolio_Value_USD']
                })

            df_perf = pd.DataFrame(perf_data)
            fig = px.scatter(
                df_perf,
                x='Diversification',
                y='Target Return',
                size='Portfolio Value',
                hover_name='Client',
                title='Risk Profile vs Target Return',
                color='Portfolio Value',
                color_continuous_scale='Viridis'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # Summary statistics
        st.markdown("### Summary Statistics")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Clients", len(clients))
        with col2:
            st.metric("Total AUM", f"${advisor_summary['total_aum'] / 1e6:.2f}M")
        with col3:
            st.metric("Avg Diversification", f"{advisor_summary['avg_diversification']:.1f}%")
        with col4:
            st.metric("Rebalance Actions", advisor_summary['clients_needing_rebalance'])

else:
    # ==================== MANAGING DIRECTOR VIEW ====================
    business_summary = reader.get_business_summary()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Executive Dashboard", "Advisors", "Clients", "Risk Analysis", "Reports"])

    with tab1:
        st.markdown("### Business Performance Overview")

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total AUM</div>
                <div class="metric-value">${business_summary['total_aum'] / 1e6:.2f}M</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Clients</div>
                <div class="metric-value">{business_summary['num_clients']}</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Active Advisors</div>
                <div class="metric-value">{business_summary['num_advisors']}</div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Avg Portfolio</div>
                <div class="metric-value">${business_summary['avg_portfolio_value'] / 1000:.1f}K</div>
            </div>
            """, unsafe_allow_html=True)

        with col5:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Action Items</div>
                <div class="metric-value">{business_summary['clients_needing_rebalance']}</div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # Key charts
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

    with tab2:
        st.markdown("### Advisor Performance Metrics")

        advisors = reader.read_advisors()
        advisor_perf = []

        for _, advisor in advisors.iterrows():
            advisor_id = advisor['Advisor_ID']
            summary = reader.get_advisor_summary(advisor_id)
            advisor_perf.append({
                'Advisor': advisor['Name'],
                'ID': advisor_id,
                'Clients': summary['num_clients'],
                'AUM': f"${summary['total_aum'] / 1e6:.2f}M",
                'Avg Portfolio': f"${summary['avg_portfolio_value'] / 1000:.1f}K",
                'Managed': summary['managed_clients'],
                'Self-Directed': summary['self_directed_clients'],
                'Rebalance': summary['clients_needing_rebalance'],
                'Avg Div.': f"{summary['avg_diversification']:.1f}%"
            })

        df_advisors = pd.DataFrame(advisor_perf)
        st.dataframe(df_advisors, use_container_width=True, hide_index=True)

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            clients_raw = reader.read_clients()
            advisor_clients = clients_raw.groupby('Advisor_ID').size().reset_index(name='Clients')
            fig = px.bar(
                advisor_clients,
                x='Advisor_ID',
                y='Clients',
                title='Clients per Advisor',
                color='Clients',
                color_continuous_scale='Greens'
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            advisor_aum = clients_raw.groupby('Advisor_ID')['Portfolio_Value_USD'].agg(['sum', 'mean']).reset_index()
            fig = px.scatter(
                advisor_aum,
                x='Advisor_ID',
                y='sum',
                size='mean',
                title='AUM and Avg Portfolio by Advisor',
                labels={'sum': 'Total AUM', 'mean': 'Avg Portfolio'}
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.markdown("### All Client Portfolios")

        all_clients_df = reader.get_all_clients_data()

        if not all_clients_df.empty:
            st.dataframe(all_clients_df, use_container_width=True, hide_index=True)

            # Export
            csv = all_clients_df.to_csv(index=False)
            st.download_button(
                label="📥 Download All Clients (CSV)",
                data=csv,
                file_name="all_clients.csv",
                mime="text/csv"
            )

    with tab4:
        st.markdown("### Risk Distribution & Analysis")

        col1, col2 = st.columns(2)

        with col1:
            clients_raw = reader.read_clients()
            risk_aum = clients_raw.groupby('Risk_Profile')['Portfolio_Value_USD'].agg(['sum', 'count']).reset_index()
            fig = px.bar(
                risk_aum,
                x='Risk_Profile',
                y='sum',
                title='AUM by Risk Profile',
                color='sum',
                color_continuous_scale='Viridis'
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            arch_aum = clients_raw.groupby('Architecture')['Portfolio_Value_USD'].agg(['sum', 'count']).reset_index()
            fig = px.bar(
                arch_aum,
                x='Architecture',
                y='sum',
                title='AUM by Architecture',
                color='sum',
                color_continuous_scale='Plasma'
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        st.markdown("### Risk Profile Distribution Matrix")
        dist_data = []

        for risk in clients_raw['Risk_Profile'].unique():
            for arch in clients_raw['Architecture'].unique():
                mask = (clients_raw['Risk_Profile'] == risk) & (clients_raw['Architecture'] == arch)
                count = len(clients_raw[mask])
                aum = clients_raw[mask]['Portfolio_Value_USD'].sum()

                if count > 0:
                    dist_data.append({
                        'Risk Profile': risk,
                        'Architecture': arch,
                        'Clients': count,
                        'Total AUM': f"${aum:,.0f}",
                        'Avg Portfolio': f"${aum / count:,.0f}"
                    })

        if dist_data:
            df_dist = pd.DataFrame(dist_data)
            st.dataframe(df_dist, use_container_width=True, hide_index=True)

    with tab5:
        st.markdown("### Executive Reports")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Managed Portfolios", business_summary['managed_clients'])
        with col2:
            st.metric("Self-Directed", business_summary['self_directed_clients'])
        with col3:
            st.metric("Avg Diversification", f"{business_summary['avg_diversification']:.1f}%")

        st.divider()

        # Performance heatmap
        st.markdown("### Advisor Performance Heatmap")
        clients_raw = reader.read_clients()
        advisors = reader.read_advisors()

        heatmap_data = []
        for _, advisor in advisors.iterrows():
            advisor_id = advisor['Advisor_ID']
            advisor_clients = clients_raw[clients_raw['Advisor_ID'] == advisor_id]

            heatmap_data.append({
                'Advisor': advisor['Name'],
                'Total Clients': len(advisor_clients),
                'AUM (M)': advisor_clients['Portfolio_Value_USD'].sum() / 1e6,
                'Avg Portfolio (K)': advisor_clients['Portfolio_Value_USD'].mean() / 1000,
                'Avg Return Target': advisor_clients['Target_Return_%'].mean()
            })

        df_heatmap = pd.DataFrame(heatmap_data)

        fig = go.Figure(data=go.Heatmap(
            z=[df_heatmap['Total Clients'], df_heatmap['AUM (M)'], df_heatmap['Avg Portfolio (K)']],
            x=df_heatmap['Advisor'],
            y=['Clients', 'AUM (M)', 'Avg Portfolio (K)'],
            colorscale='Viridis'
        ))
        fig.update_layout(height=400, title="Advisor Performance Heatmap")
        st.plotly_chart(fig, use_container_width=True)

st.divider()
st.caption(f"Portfolio Dashboard V2 | Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
