import streamlit as st
import pandas as pd
from datetime import datetime
from data_reader import PortfolioDataReader
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(
    page_title="Portfolio Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={}
)

# Custom CSS for professional styling
st.markdown("""
<style>
    * {
        margin: 0;
        padding: 0;
    }

    .main {
        padding: 2rem;
    }

    .header-title {
        font-size: 32px;
        font-weight: 700;
        color: #1F4E78;
        margin-bottom: 0.5rem;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }

    .header-subtitle {
        font-size: 14px;
        color: #666;
        margin-bottom: 2rem;
    }

    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 8px;
        padding: 1.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }

    .metric-value {
        font-size: 28px;
        font-weight: 700;
        color: #1F4E78;
        margin-bottom: 0.5rem;
    }

    .metric-label {
        font-size: 13px;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .status-ok {
        color: #27AE60;
        font-weight: 600;
    }

    .status-warning {
        color: #E74C3C;
        font-weight: 600;
    }

    .dataframe {
        border-radius: 8px;
        overflow: hidden;
    }

    .stTabs [data-baseweb="tab-list"] button {
        background-color: #f0f2f6;
        color: #1F4E78;
        font-weight: 600;
        border-radius: 4px 4px 0 0;
    }

    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        background-color: #1F4E78;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Initialize data reader
@st.cache_resource
def get_data_reader():
    return PortfolioDataReader()

reader = get_data_reader()

# Sidebar configuration
with st.sidebar:
    st.markdown("## 👤 User Access")
    user_role = st.radio(
        "Select your role:",
        ["Investment Advisor", "Managing Director"],
        label_visibility="collapsed"
    )

    if user_role == "Investment Advisor":
        advisors = reader.read_advisors()
        advisor_list = advisors['Advisor_ID'].tolist()
        advisor_id = st.selectbox(
            "Select Advisor:",
            advisor_list,
            label_visibility="collapsed"
        )
    else:
        advisor_id = None

    st.divider()
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Main title
col1, col2 = st.columns([0.8, 0.2])
with col1:
    st.markdown("""
    <div class="header-title">📊 Client Portfolio Dashboard</div>
    <div class="header-subtitle">Centralized wealth management and portfolio analysis</div>
    """, unsafe_allow_html=True)

if user_role == "Investment Advisor":
    # ==================== INVESTMENT ADVISOR VIEW ====================
    advisor_summary = reader.get_advisor_summary(advisor_id)
    clients = reader.get_clients_by_advisor(advisor_id)

    tab1, tab2, tab3 = st.tabs(["Overview", "Client Analysis", "Performance"])

    with tab1:
        st.markdown("### Your Clients Overview")

        # KPI Cards
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Clients</div>
                <div class="metric-value">{advisor_summary['num_clients']}</div>
                <div class="metric-label" style="margin-top: 0.5rem;">
                    {advisor_summary['managed_clients']} Managed
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Assets Under Management</div>
                <div class="metric-value">${advisor_summary['total_aum'] / 1e6:.2f}M</div>
                <div class="metric-label" style="margin-top: 0.5rem;">
                    Avg: ${advisor_summary['avg_portfolio_value'] / 1000:.1f}K
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Avg Diversification</div>
                <div class="metric-value">{advisor_summary['avg_diversification']:.1f}%</div>
                <div class="metric-label" style="margin-top: 0.5rem;">
                    Out of 100
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            status_color = "warning" if advisor_summary['clients_needing_rebalance'] > 0 else "ok"
            status_text = "⚠️ Action Needed" if advisor_summary['clients_needing_rebalance'] > 0 else "✅ All Balanced"
            color_style = "color: #E74C3C;" if advisor_summary['clients_needing_rebalance'] > 0 else ""
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Rebalancing Status</div>
                <div class="metric-value" style="{color_style}">
                    {advisor_summary['clients_needing_rebalance']}
                </div>
                <div class="metric-label status-{status_color}" style="margin-top: 0.5rem;">
                    {status_text}
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # Clients Table
        st.markdown("### Client List")
        clients_display = []

        for _, client in clients.iterrows():
            rut = client['RUT']
            needs_rebalance, reason, deviation = reader.check_rebalance_needed(rut)

            clients_display.append({
                'Client Name': client['Name'],
                'RUT': rut,
                'Portfolio Value': f"${client['Portfolio_Value_USD']:,.0f}",
                'Architecture': client['Architecture'],
                'Risk Profile': client['Risk_Profile'],
                'Type': client['Portfolio_Type'],
                'Rebalance': '⚠️ Yes' if needs_rebalance else '✅ No'
            })

        df_clients = pd.DataFrame(clients_display)
        st.dataframe(df_clients, use_container_width=True, hide_index=True)

    with tab2:
        st.markdown("### Detailed Client Analysis")

        if not clients.empty:
            selected_client = st.selectbox(
                "Select a client:",
                clients['Name'].tolist(),
                key="client_select"
            )

            client_data = clients[clients['Name'] == selected_client].iloc[0]
            client_rut = client_data['RUT']

            # Client Header
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"**Client:** {selected_client}")
                st.markdown(f"**RUT:** {client_rut}")
            with col2:
                st.markdown(f"**Risk Profile:** {client_data['Risk_Profile']}")
                st.markdown(f"**Architecture:** {client_data['Architecture']}")
            with col3:
                portfolio_value = client_data['Portfolio_Value_USD']
                st.markdown(f"**Portfolio Value:** ${portfolio_value:,.0f}")
                st.markdown(f"**Type:** {client_data['Portfolio_Type']}")

            st.divider()

            # Holdings and Allocation
            holdings = reader.get_client_holdings(client_rut)

            if not holdings.empty:
                st.markdown("### Asset Allocation")

                col1, col2 = st.columns([1, 1])

                with col1:
                    # Current vs Target
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
                        height=400,
                        hovermode='x unified',
                        showlegend=True
                    )
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    # Pie chart of current allocation
                    fig = go.Figure(data=[go.Pie(
                        labels=holdings['Asset_Class'],
                        values=holdings['Current_Value_USD'],
                        marker=dict(colors=['#1F4E78', '#27AE60', '#E67E22', '#9B59B6', '#34495E'])
                    )])
                    fig.update_layout(
                        title="Current Portfolio Composition",
                        height=400
                    )
                    st.plotly_chart(fig, use_container_width=True)

                st.divider()

                # Holdings Table
                st.markdown("### Position Details")
                holdings_display = holdings[[
                    'Asset_Class', 'Position_Name', 'Ticker', 'Units', 'Unit_Price_USD',
                    'Current_Value_USD', 'Target_Allocation_%', 'Current_Allocation_%'
                ]].copy()

                holdings_display['Unit_Price_USD'] = holdings_display['Unit_Price_USD'].apply(lambda x: f"${x:,.2f}")
                holdings_display['Current_Value_USD'] = holdings_display['Current_Value_USD'].apply(lambda x: f"${x:,.0f}")
                holdings_display.columns = [
                    'Asset Class', 'Position Name', 'Ticker', 'Units', 'Unit Price',
                    'Current Value', 'Target %', 'Current %'
                ]

                st.dataframe(holdings_display, use_container_width=True, hide_index=True)

                # Rebalancing Recommendation
                needs_rebalance, reason, max_deviation = reader.check_rebalance_needed(client_rut)

                if needs_rebalance:
                    st.warning(f"🔄 Rebalancing Recommended\n\n{reason}")
                else:
                    st.success("✅ Portfolio is well balanced")

        else:
            st.info("No clients assigned to this advisor")

    with tab3:
        st.markdown("### Performance & KPIs")

        if not clients.empty:
            performance_data = []

            for _, client in clients.iterrows():
                rut = client['RUT']
                needs_rebalance, _, _ = reader.check_rebalance_needed(rut)
                kpis = reader.calculate_portfolio_kpis(rut)

                performance_data.append({
                    'Client': client['Name'],
                    'Portfolio Value': client['Portfolio_Value_USD'],
                    'Diversification': kpis.get('diversification_score', 0),
                    'Target Return %': client['Target_Return_%'],
                    'Rebalance': '⚠️ Yes' if needs_rebalance else '✅ No'
                })

            df_performance = pd.DataFrame(performance_data)

            col1, col2 = st.columns(2)

            with col1:
                fig = px.bar(
                    df_performance,
                    x='Client',
                    y='Portfolio Value',
                    title='Portfolio Values by Client',
                    color='Portfolio Value',
                    color_continuous_scale='Blues'
                )
                fig.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig = px.scatter(
                    df_performance,
                    x='Diversification',
                    y='Target Return %',
                    size='Portfolio Value',
                    title='Diversification vs Target Return',
                    hover_name='Client'
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

else:
    # ==================== MANAGING DIRECTOR VIEW ====================
    business_summary = reader.get_business_summary()

    tab1, tab2, tab3 = st.tabs(["Business Overview", "Advisor Performance", "Risk Distribution"])

    with tab1:
        st.markdown("### Business Summary")

        # KPI Cards
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total AUM</div>
                <div class="metric-value">${business_summary['total_aum'] / 1e6:.2f}M</div>
                <div class="metric-label" style="margin-top: 0.5rem;">
                    {business_summary['num_clients']} Clients
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Active Advisors</div>
                <div class="metric-value">{business_summary['num_advisors']}</div>
                <div class="metric-label" style="margin-top: 0.5rem;">
                    Avg AUM: ${business_summary['avg_portfolio_value'] / 1000:.1f}K
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Managed vs Self-Directed</div>
                <div class="metric-value">{business_summary['managed_clients']}:{business_summary['self_directed_clients']}</div>
                <div class="metric-label" style="margin-top: 0.5rem;">
                    Total Clients
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            status_color = "warning" if business_summary['clients_needing_rebalance'] > 0 else "ok"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Portfolios Needing Action</div>
                <div class="metric-value" style="color: #E74C3C;">
                    {business_summary['clients_needing_rebalance']}
                </div>
                <div class="metric-label" style="margin-top: 0.5rem;">
                    Out of {business_summary['num_clients']} Clients
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # All Clients Overview
        st.markdown("### All Client Portfolios")
        all_clients_df = reader.get_all_clients_data()

        if not all_clients_df.empty:
            # Format columns for display
            all_clients_df['Portfolio Value'] = all_clients_df['Portfolio Value'].apply(lambda x: f"${x:,.0f}")

            st.dataframe(all_clients_df, use_container_width=True, hide_index=True)

            # Visualization
            col1, col2 = st.columns(2)

            with col1:
                clients_raw = reader.read_clients()
                fig = px.bar(
                    clients_raw.groupby('Advisor_ID')['Portfolio_Value_USD'].sum().reset_index(),
                    x='Advisor_ID',
                    y='Portfolio_Value_USD',
                    title='AUM by Advisor',
                    labels={'Portfolio_Value_USD': 'AUM ($)', 'Advisor_ID': 'Advisor'},
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
                    title='Client Distribution by Risk Profile',
                    color_discrete_sequence=['#1F4E78', '#27AE60', '#E67E22', '#9B59B6', '#34495E']
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.markdown("### Advisor Performance Metrics")

        advisors = reader.read_advisors()
        advisor_performance = []

        for _, advisor in advisors.iterrows():
            advisor_id = advisor['Advisor_ID']
            summary = reader.get_advisor_summary(advisor_id)
            advisor_performance.append({
                'Advisor': advisor['Name'],
                'ID': advisor_id,
                'Clients': summary['num_clients'],
                'AUM': f"${summary['total_aum'] / 1e6:.2f}M",
                'Avg Portfolio': f"${summary['avg_portfolio_value'] / 1000:.1f}K",
                'Managed': summary['managed_clients'],
                'Rebalance': summary['clients_needing_rebalance'],
                'Avg Diversification': f"{summary['avg_diversification']:.1f}%"
            })

        df_advisors = pd.DataFrame(advisor_performance)
        st.dataframe(df_advisors, use_container_width=True, hide_index=True)

        # Performance chart
        col1, col2 = st.columns(2)

        with col1:
            clients_raw = reader.read_clients()
            advisor_clients = clients_raw.groupby('Advisor_ID').size().reset_index(name='Client Count')
            advisor_names = advisors.set_index('Advisor_ID')['Name'].to_dict()
            advisor_clients['Advisor Name'] = advisor_clients['Advisor_ID'].map(advisor_names)

            fig = px.bar(
                advisor_clients,
                x='Advisor Name',
                y='Client Count',
                title='Client Count by Advisor',
                color='Client Count',
                color_continuous_scale='Greens'
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            advisor_aum = clients_raw.groupby('Advisor_ID')['Portfolio_Value_USD'].mean().reset_index(name='Avg Portfolio Value')
            advisor_aum['Advisor Name'] = advisor_aum['Advisor_ID'].map(advisor_names)

            fig = px.bar(
                advisor_aum,
                x='Advisor Name',
                y='Avg Portfolio Value',
                title='Average Portfolio Value by Advisor',
                color='Avg Portfolio Value',
                color_continuous_scale='Oranges'
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.markdown("### Risk Profile & Portfolio Distribution")

        clients_raw = reader.read_clients()

        col1, col2 = st.columns(2)

        with col1:
            risk_dist = clients_raw.groupby('Risk_Profile')['Portfolio_Value_USD'].agg(['sum', 'count']).reset_index()
            risk_dist.columns = ['Risk Profile', 'Total AUM', 'Client Count']

            fig = px.bar(
                risk_dist,
                x='Risk Profile',
                y='Total AUM',
                title='AUM by Risk Profile',
                color='Total AUM',
                color_continuous_scale='Viridis'
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            arch_dist = clients_raw.groupby('Architecture')['Portfolio_Value_USD'].agg(['sum', 'count']).reset_index()
            arch_dist.columns = ['Architecture', 'Total AUM', 'Client Count']

            fig = px.bar(
                arch_dist,
                x='Architecture',
                y='Total AUM',
                title='AUM by Portfolio Architecture',
                color='Total AUM',
                color_continuous_scale='Plasma'
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        # Detailed distribution table
        st.markdown("### Distribution Summary")
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

st.divider()
st.caption(f"© 2026 Portfolio Management | Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
