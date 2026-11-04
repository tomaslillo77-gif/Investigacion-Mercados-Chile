"""
Generate Comprehensive Dummy Data for Portfolio Dashboard
Includes all variations of services, risk profiles, architectures, and asset types
"""

import pandas as pd
import numpy as np
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime, timedelta

def create_dummy_data():
    """Create comprehensive dummy data with all variations"""

    Path("data").mkdir(exist_ok=True)

    # Define styles
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    wb = Workbook()
    if 'Sheet' in wb.sheetnames:
        wb.remove(wb['Sheet'])

    # ============================================================================
    # SHEET 1: ADVISORS (6 advisors + 1 managing director)
    # ============================================================================
    ws_advisors = wb.create_sheet("Asesores", 0)

    advisors_data = {
        'Advisor_ID': ['advisor_1', 'advisor_2', 'advisor_3', 'advisor_4', 'advisor_5', 'advisor_6'],
        'Name': [
            'Pedro García',
            'María López',
            'Juan Martínez',
            'Ana Rodríguez',
            'Carlos Fernández',
            'Laura Sánchez'
        ],
        'Email': [
            'pedro.garcia@bank.com',
            'maria.lopez@bank.com',
            'juan.martinez@bank.com',
            'ana.rodriguez@bank.com',
            'carlos.fernandez@bank.com',
            'laura.sanchez@bank.com'
        ],
        'Phone': [
            '+56-2-1234-5001',
            '+56-2-1234-5002',
            '+56-2-1234-5003',
            '+56-2-1234-5004',
            '+56-2-1234-5005',
            '+56-2-1234-5006'
        ],
    }

    df_advisors = pd.DataFrame(advisors_data)
    _write_sheet(ws_advisors, df_advisors, header_fill, header_font, border)

    # ============================================================================
    # SHEET 2: CLIENTS (30 clients with all service types and variations)
    # ============================================================================
    ws_clients = wb.create_sheet("Clientes", 1)

    services = ['DAP', 'Cartera Gestionada', 'Asesoría', 'ADC']
    architectures = ['Conservative', 'Balanced', 'Growth', 'Aggressive']
    risk_profiles = ['Low', 'Low-Medium', 'Medium', 'Medium-High', 'High']
    portfolio_types = ['Managed', 'Self-Directed']

    clients_data = {
        'RUT': [],
        'Entidad': [],
        'Household': [],
        'Servicio': [],
        'WM': [],
        'IA': [],
        'Architecture': [],
        'Risk_Profile': [],
        'Portfolio_Type': [],
        'Portfolio_Value_USD': [],
        'Target_Return_%': [],
        'Benchmark': []
    }

    # Generate 30 diverse clients
    rut_counter = 10000000
    client_counter = 0
    advisors = advisors_data['Advisor_ID']
    advisor_names = advisors_data['Name']

    for i in range(30):
        rut_counter += 1
        client_counter += 1
        advisor_idx = i % 6
        advisor_id = advisors[advisor_idx]
        advisor_name = advisor_names[advisor_idx]

        # Vary service types
        service_idx = i % 4
        service = services[service_idx]

        # Vary architectures and risk profiles
        arch_idx = i % 4
        risk_idx = i % 5
        architecture = architectures[arch_idx]
        risk_profile = risk_profiles[risk_idx]

        # Determine portfolio type based on service
        if service == 'DAP':
            portfolio_type = 'Self-Directed'
            portfolio_value = np.random.randint(50000, 500000)
            target_return = 1.5
        elif service == 'Cartera Gestionada':
            portfolio_type = 'Managed'
            portfolio_value = np.random.randint(300000, 2000000)
            target_return = np.random.choice([4.5, 5.0, 5.5, 6.0, 6.5, 7.0])
        elif service == 'Asesoría':
            portfolio_type = 'Managed'
            portfolio_value = np.random.randint(500000, 3000000)
            target_return = np.random.choice([5.0, 5.5, 6.0, 6.5, 7.0, 7.5])
        else:  # ADC
            portfolio_type = 'Managed'
            portfolio_value = np.random.randint(1000000, 5000000)
            target_return = np.random.choice([6.0, 6.5, 7.0, 7.5, 8.0, 8.5])

        # Benchmarks
        benchmarks = ['IPSA', 'S&P 500', 'NASDAQ', 'Bloomberg Barclays', 'MSCI World']
        benchmark = np.random.choice(benchmarks)

        clients_data['RUT'].append(f"{rut_counter}-9")
        clients_data['Entidad'].append(f"Cliente {chr(65 + (client_counter % 26))}{client_counter}")
        clients_data['Household'].append(f"Familia {chr(65 + (i % 26))}")
        clients_data['Servicio'].append(service)
        clients_data['WM'].append(advisor_name)
        clients_data['IA'].append(advisor_id)
        clients_data['Architecture'].append(architecture)
        clients_data['Risk_Profile'].append(risk_profile)
        clients_data['Portfolio_Type'].append(portfolio_type)
        clients_data['Portfolio_Value_USD'].append(portfolio_value)
        clients_data['Target_Return_%'].append(target_return)
        clients_data['Benchmark'].append(benchmark)

    df_clients = pd.DataFrame(clients_data)
    _write_sheet(ws_clients, df_clients, header_fill, header_font, border)

    # ============================================================================
    # SHEET 3: HOLDINGS (Multiple positions per client)
    # ============================================================================
    ws_holdings = wb.create_sheet("Posiciones", 2)

    asset_types = ['Renta Variable', 'Renta Fija', 'Alternatives', 'Fondos Mutuos', 'DAP', 'Depósitos']
    instruments = {
        'Renta Variable': ['AAPL', 'MSFT', 'GOOG', 'TSLA', 'SPY', 'QQQ', 'IPSA', 'AFE', 'CENCL'],
        'Renta Fija': ['US Treasury 10Y', 'Corporate Bonds', 'Bloomberg Barclays', 'BTP Italia', 'Bonos del Estado', 'Corporate Bonds CLF'],
        'Alternatives': ['Real Estate Fund', 'Private Equity Fund', 'Hedge Fund', 'Commodities ETF'],
        'Fondos Mutuos': ['Fondo Equilibrado', 'Fondo Conservador', 'Fondo Crecimiento', 'Fondo Global'],
        'DAP': ['Depósito a Plazo', 'DAP 30 días', 'DAP 90 días', 'DAP 180 días'],
        'Depósitos': ['Cuenta Corriente', 'Cuenta de Ahorro', 'Depósito en Moneda Extranjera']
    }

    holdings_data = {
        'Cliente': [],
        'Entidad': [],
        'Cantidad': [],
        'Instrumento': [],
        'Tipo': [],
        'Costo_Unitario': [],
        'Costo_Base': [],
        'Precio_Mercado': [],
        'Valor_de_Mercado': [],
        'G_P_no_Realizada': [],
        'Rent_no_Realizada_%': [],
        'Cuenta': [],
        'ISIN': [],
        'Nemo': [],
        'Movimientos': []
    }

    # Generate holdings for each client
    for idx, client_row in df_clients.iterrows():
        rut_clean = client_row['RUT'].replace('-', '').replace('.', '')
        client_entity = client_row['Entidad']
        portfolio_value = client_row['Portfolio_Value_USD']

        # Each client has 3-6 positions
        num_positions = np.random.randint(3, 7)
        position_values = np.random.dirichlet(np.ones(num_positions)) * portfolio_value

        for pos_idx in range(num_positions):
            # Vary asset types
            asset_type_idx = pos_idx % len(asset_types)
            asset_type = asset_types[asset_type_idx]

            # Select instrument
            instrument = np.random.choice(instruments[asset_type])

            # Generate position data
            quantity = np.random.randint(10, 1000)
            cost_per_unit = np.random.uniform(50, 300)
            cost_base = quantity * cost_per_unit

            # Current price (some variation from cost)
            price_variance = np.random.uniform(0.8, 1.2)
            current_price = cost_per_unit * price_variance
            current_value = quantity * current_price

            # Use pre-calculated position value
            current_value = position_values[pos_idx]
            current_price = current_value / quantity if quantity > 0 else 0

            # Gains/losses
            gains_loss = current_value - cost_base
            return_pct = (gains_loss / cost_base * 100) if cost_base > 0 else 0

            # Account type
            account_type = 'DAP' if asset_type == 'DAP' else str(np.random.randint(1000, 9999))

            # ISINs
            isin = f"US{np.random.randint(100000000, 999999999)}{np.random.choice(['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'])}"
            nemo = f"NEO{np.random.randint(10000000, 99999999)}"

            holdings_data['Cliente'].append(rut_clean)
            holdings_data['Entidad'].append(client_entity)
            holdings_data['Cantidad'].append(quantity)
            holdings_data['Instrumento'].append(instrument)
            holdings_data['Tipo'].append(asset_type)
            holdings_data['Costo_Unitario'].append(round(cost_per_unit, 2))
            holdings_data['Costo_Base'].append(round(cost_base, 2))
            holdings_data['Precio_Mercado'].append(round(current_price, 2))
            holdings_data['Valor_de_Mercado'].append(round(current_value, 2))
            holdings_data['G_P_no_Realizada'].append(round(gains_loss, 2))
            holdings_data['Rent_no_Realizada_%'].append(round(return_pct, 2))
            holdings_data['Cuenta'].append(account_type)
            holdings_data['ISIN'].append(isin)
            holdings_data['Nemo'].append(nemo)
            holdings_data['Movimientos'].append('Compra' if np.random.random() > 0.3 else 'Actualización')

    df_holdings = pd.DataFrame(holdings_data)
    _write_sheet(ws_holdings, df_holdings, header_fill, header_font, border)

    # ============================================================================
    # SHEET 4: PORTFOLIO ARCHITECTURES (4 × 5 = 20 profiles)
    # ============================================================================
    ws_arch = wb.create_sheet("Portfolio_Architectures", 3)

    architectures_data = []
    for arch in ['Conservative', 'Balanced', 'Growth', 'Aggressive']:
        for risk in ['Low', 'Low-Medium', 'Medium', 'Medium-High', 'High']:
            if arch == 'Conservative':
                if risk == 'Low':
                    stocks, bonds, alternatives, cash = 15, 70, 10, 5
                elif risk == 'Low-Medium':
                    stocks, bonds, alternatives, cash = 25, 60, 10, 5
                elif risk == 'Medium':
                    stocks, bonds, alternatives, cash = 35, 50, 10, 5
                elif risk == 'Medium-High':
                    stocks, bonds, alternatives, cash = 45, 40, 10, 5
                else:  # High
                    stocks, bonds, alternatives, cash = 55, 30, 10, 5

            elif arch == 'Balanced':
                if risk == 'Low':
                    stocks, bonds, alternatives, cash = 30, 50, 15, 5
                elif risk == 'Low-Medium':
                    stocks, bonds, alternatives, cash = 40, 40, 15, 5
                elif risk == 'Medium':
                    stocks, bonds, alternatives, cash = 50, 30, 15, 5
                elif risk == 'Medium-High':
                    stocks, bonds, alternatives, cash = 60, 20, 15, 5
                else:  # High
                    stocks, bonds, alternatives, cash = 70, 10, 15, 5

            elif arch == 'Growth':
                if risk == 'Low':
                    stocks, bonds, alternatives, cash = 50, 25, 20, 5
                elif risk == 'Low-Medium':
                    stocks, bonds, alternatives, cash = 60, 15, 20, 5
                elif risk == 'Medium':
                    stocks, bonds, alternatives, cash = 70, 5, 20, 5
                elif risk == 'Medium-High':
                    stocks, bonds, alternatives, cash = 75, 0, 20, 5
                else:  # High
                    stocks, bonds, alternatives, cash = 80, 0, 15, 5

            else:  # Aggressive
                if risk == 'Low':
                    stocks, bonds, alternatives, cash = 70, 10, 15, 5
                elif risk == 'Low-Medium':
                    stocks, bonds, alternatives, cash = 80, 0, 15, 5
                elif risk == 'Medium':
                    stocks, bonds, alternatives, cash = 85, 0, 10, 5
                elif risk == 'Medium-High':
                    stocks, bonds, alternatives, cash = 90, 0, 5, 5
                else:  # High
                    stocks, bonds, alternatives, cash = 95, 0, 0, 5

            architectures_data.append({
                'Architecture': arch,
                'Risk_Profile': risk,
                'Stocks_%': stocks,
                'Bonds_%': bonds,
                'Alternatives_%': alternatives,
                'Cash_%': cash
            })

    df_arch = pd.DataFrame(architectures_data)
    _write_sheet(ws_arch, df_arch, header_fill, header_font, border)

    # ============================================================================
    # SHEET 5: SUMMARY (Documentation)
    # ============================================================================
    ws_summary = wb.create_sheet("README", 4)

    summary_text = [
        ["PORTFOLIO DASHBOARD - DUMMY DATA"],
        [],
        ["OVERVIEW"],
        ["This file contains complete dummy data for testing the Portfolio Dashboard"],
        ["It includes all possible variations of services, risk profiles, and architectures"],
        [],
        ["DATA INCLUDED"],
        ["- 6 Investment Advisors"],
        ["- 30 Clients with different characteristics"],
        ["- 4 Service Types: DAP, Cartera Gestionada, Asesoría, ADC"],
        ["- 5 Risk Profiles: Low, Low-Medium, Medium, Medium-High, High"],
        ["- 4 Portfolio Architectures: Conservative, Balanced, Growth, Aggressive"],
        ["- 100+ Holdings across multiple asset types"],
        ["- 6 Asset Types: Renta Variable, Renta Fija, Alternatives, Fondos Mutuos, DAP, Depósitos"],
        [],
        ["SHEETS"],
        ["1. Asesores - Investment advisors information"],
        ["2. Clientes - Client data with all variations"],
        ["3. Posiciones - Holdings/positions for each client"],
        ["4. Portfolio_Architectures - Target allocations (DO NOT EDIT)"],
        ["5. README - This documentation"],
        [],
        ["HOW TO USE"],
        ["1. Configure column_mapping.py with these column names"],
        ["2. Run: python data_transformer.py"],
        ["3. Run: streamlit run app.py"],
        ["4. Test all features with this comprehensive dummy data"],
        [],
        ["FEATURES TO TEST"],
        ["- Investment Advisor view with all clients"],
        ["- Detailed portfolio analysis"],
        ["- Rebalancing recommendations"],
        ["- Managing Director business overview"],
        ["- Advisor performance comparison"],
        ["- Risk profile distribution"],
        [],
        ["DATA STATISTICS"],
        [f"Total Clients: 30"],
        [f"Total Holdings: {len(df_holdings)}"],
        [f"Total AUM: ${df_clients['Portfolio_Value_USD'].sum():,.0f}"],
        [f"Average Portfolio: ${df_clients['Portfolio_Value_USD'].mean():,.0f}"],
        [],
        ["GENERATING THIS DATA"],
        ["This file was generated by: generate_dummy_data.py"],
        [f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"],
        ["All data is realistic but completely fictional for testing purposes"],
    ]

    for row_idx, row_data in enumerate(summary_text, 1):
        for col_idx, value in enumerate(row_data, 1):
            cell = ws_summary.cell(row=row_idx, column=col_idx, value=value)
            if row_idx == 1:
                cell.font = Font(bold=True, size=14)
            elif 'OVERVIEW' in str(value) or 'DATA' in str(value) or 'SHEETS' in str(value) or 'HOW' in str(value) or 'FEATURES' in str(value) or 'STATISTICS' in str(value) or 'GENERATING' in str(value):
                cell.font = Font(bold=True, size=11)
            cell.border = border

    ws_summary.column_dimensions['A'].width = 80

    # Save workbook
    output_path = 'data/portfolio_data_dummy.xlsx'
    wb.save(output_path)

    print(f"✅ Dummy data created successfully!")
    print(f"\n📊 DATA SUMMARY:")
    print(f"   Advisors: {len(df_advisors)}")
    print(f"   Clients: {len(df_clients)}")
    print(f"   Holdings: {len(df_holdings)}")
    print(f"   Total AUM: ${df_clients['Portfolio_Value_USD'].sum():,.0f}")
    print(f"   Average Portfolio: ${df_clients['Portfolio_Value_USD'].mean():,.0f}")
    print(f"\n📁 File saved to: {output_path}")
    print(f"\n🎯 NEXT STEPS:")
    print(f"   1. Copy this file: cp data/portfolio_data_dummy.xlsx data/portfolio_data.xlsx")
    print(f"   2. Configure column_mapping.py (if needed)")
    print(f"   3. Run: streamlit run app.py")
    print(f"\n✨ Ready to test all dashboard features!")


def _write_sheet(worksheet, dataframe, header_fill, header_font, border):
    """Write dataframe to worksheet with formatting"""

    # Write headers
    for c_idx, column_title in enumerate(dataframe.columns, 1):
        cell = worksheet.cell(row=1, column=c_idx)
        cell.value = column_title
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Write data
    for r_idx, row in enumerate(dataframe.values, 2):
        for c_idx, value in enumerate(row, 1):
            cell = worksheet.cell(row=r_idx, column=c_idx)
            cell.value = value
            cell.border = border

            # Format numbers
            if isinstance(value, (int, float)) and c_idx > 3:
                if isinstance(value, float):
                    cell.number_format = '#,##0.00'
                else:
                    cell.number_format = '#,##0'

    # Adjust column widths
    for c_idx, column_title in enumerate(dataframe.columns, 1):
        max_length = max(
            dataframe.iloc[:, c_idx - 1].astype(str).map(len).max(),
            len(str(column_title))
        )
        worksheet.column_dimensions[get_column_letter(c_idx)].width = min(max_length + 2, 50)


if __name__ == "__main__":
    create_dummy_data()
