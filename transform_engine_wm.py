"""
Transform Engine WM Dummy.xlsx to dashboard-compatible format
Converts the WM data warehouse structure to our simplified schema
"""

import pandas as pd
from pathlib import Path
import re

def clean_numeric(value):
    """Convert formatted numeric strings to float"""
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    # Convert to string and clean
    s = str(value).strip()
    # Remove currency symbols and text
    s = re.sub(r'[^\d,.-]', '', s)
    # Handle European format (1.234,56) and US format (1,234.56)
    if ',' in s and '.' in s:
        # If both present, determine which is thousands separator
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        # Assume comma is thousands separator
        s = s.replace(',', '')

    try:
        return float(s)
    except:
        return 0.0

def transform_engine_wm():
    """Transform Engine WM Dummy.xlsx to portfolio_data.xlsx format"""

    source_path = "Engine WM Dummy.xlsx"
    output_path = "data/portfolio_data.xlsx"

    print("📖 Reading Engine WM Dummy.xlsx...")

    # Read source sheets
    metricas = pd.read_excel(source_path, sheet_name="Dummy Metricas", header=2)
    posiciones = pd.read_excel(source_path, sheet_name="Dummy Posiciones", header=2)
    carteras = pd.read_excel(source_path, sheet_name="Dummy Carteras", header=2)
    data_filtro = pd.read_excel(source_path, sheet_name="Dummy Data Filtro", header=2)

    print("\n✅ Step 1: Extract Advisors")
    # Get unique advisors from metricas
    advisors_list = []
    for _, row in metricas.iterrows():
        if pd.notna(row.get('WM')):
            advisor_id = str(row['WM']).strip()
            if advisor_id not in [a['Advisor_ID'] for a in advisors_list]:
                advisors_list.append({
                    'Advisor_ID': advisor_id,
                    'Name': f"Advisor {advisor_id}",
                    'Email': f"{advisor_id.lower()}@wealthmgmt.cl",
                    'Phone': "+56 2 1234 5678"
                })

    advisors_df = pd.DataFrame(advisors_list)
    print(f"   Found {len(advisors_df)} advisors")
    print(advisors_df.head())

    print("\n✅ Step 2: Extract Clients")
    # Get unique clients from metricas (one row per client)
    clients_list = []
    seen_clients = set()

    for _, row in metricas.iterrows():
        rut = str(row.get('RUT', '')).strip()
        if rut and rut not in seen_clients:
            seen_clients.add(rut)
            clients_list.append({
                'RUT': rut,
                'Name': str(row.get('Entidad', rut)).strip(),
                'Advisor_ID': str(row.get('IA', 'IA_000001')).strip(),
                'Architecture': 'Scotia',  # Default, will vary by profile
                'Risk_Profile': str(row.get('Perfil de Riesgo', 'Medium')).strip(),
                'Portfolio_Type': 'Managed',
                'Service_Type': str(row.get('Servicio', 'Wealth Management')).strip(),
                'Portfolio_Value_USD': clean_numeric(row.get('CAD (USD MM)', 0)) * 1_000_000,
            })

    clients_df = pd.DataFrame(clients_list)
    print(f"   Found {len(clients_df)} clients")
    print(clients_df.head())

    print("\n✅ Step 3: Extract Holdings")
    # Get holdings from posiciones (one row per position)
    holdings_list = []

    for _, row in posiciones.iterrows():
        rut = str(row.get('Cliente (ID)', '')).strip()
        instrumento = str(row.get('Instrumento', '')).strip()

        if rut and instrumento:
            holdings_list.append({
                'Client_RUT': rut,
                'Position_Name': instrumento,
                'Asset_Class': str(row.get('Tipo', 'Mixed')).strip(),
                'Units': clean_numeric(row.get('Cantidad', 0)),
                'Unit_Price_USD': clean_numeric(row.get('Precio Mercado', 0)),
                'Current_Value_USD': clean_numeric(row.get('Valor de Mercado', 0)),
                'Ticker': str(row.get('Isin', '')).strip(),
            })

    holdings_df = pd.DataFrame(holdings_list)
    print(f"   Found {len(holdings_df)} holdings")
    print(holdings_df.head())

    print("\n✅ Step 4: Extract Portfolio Architectures")
    # Get portfolio models from carteras
    archs_list = []
    seen_archs = set()

    for _, row in carteras.iterrows():
        arch_key = (str(row.get('arquitectura', '')).strip(), str(row.get('perfil', '')).strip())
        if arch_key[0] and arch_key not in seen_archs:
            seen_archs.add(arch_key)
            archs_list.append({
                'Architecture': arch_key[0],
                'Risk_Profile': arch_key[1],
                'Stocks_%': 0.40,  # Default allocation
                'Bonds_%': 0.40,
                'Alternatives_%': 0.20,
                'Real_Estate_%': 0.0,
                'Instruments': str(row.get('instrumento', '')).strip(),
            })

    # If no architectures found, create defaults
    if not archs_list:
        for arch in ['Scotia', 'Abierta Pesos', 'Abierta Dólares', 'Abierta Local']:
            for profile in ['Conservador', 'Moderado', 'Balanceado', 'Agresivo', 'Muy Agresivo']:
                archs_list.append({
                    'Architecture': arch,
                    'Risk_Profile': profile,
                    'Stocks_%': 0.30 if 'Conservador' in profile else 0.60,
                    'Bonds_%': 0.50 if 'Conservador' in profile else 0.30,
                    'Alternatives_%': 0.20,
                    'Real_Estate_%': 0.0,
                })

    archs_df = pd.DataFrame(archs_list).drop_duplicates(subset=['Architecture', 'Risk_Profile'])
    print(f"   Found {len(archs_df)} architecture profiles")
    print(archs_df.head())

    print("\n✅ Step 5: Save to Excel")
    # Create output directory
    Path("data").mkdir(exist_ok=True)

    # Write to Excel
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        advisors_df.to_excel(writer, sheet_name='Advisors', index=False)
        clients_df.to_excel(writer, sheet_name='Clients', index=False)
        holdings_df.to_excel(writer, sheet_name='Holdings', index=False)
        archs_df.to_excel(writer, sheet_name='Portfolio_Architectures', index=False)

        # Add README
        readme_text = pd.DataFrame({
            'INFO': [
                'PORTFOLIO DASHBOARD - DATA FROM ENGINE WM',
                '',
                'This file is auto-generated from Engine WM Dummy.xlsx',
                'Source: Engine WM Dummy.xlsx',
                'Format: Dashboard-compatible structure',
                '',
                'Sheets:',
                '  - Advisors: Wealth managers and investment advisors',
                '  - Clients: Client data with risk profiles and services',
                '  - Holdings: Current portfolio positions',
                '  - Portfolio_Architectures: Model portfolio definitions',
            ]
        })
        readme_text.to_excel(writer, sheet_name='README', index=False)

    print(f"\n✅ Successfully transformed!")
    print(f"   Output: {output_path}")
    print(f"\n   📊 Summary:")
    print(f"      - {len(advisors_df)} Advisors")
    print(f"      - {len(clients_df)} Clients")
    print(f"      - {len(holdings_df)} Holdings")
    print(f"      - {len(archs_df)} Architecture Profiles")

if __name__ == "__main__":
    transform_engine_wm()
