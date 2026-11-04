"""
Column Mapping Configuration
Maps your actual Excel columns to the dashboard fields
Edit the COLUMN_MAPPING dictionary to match your data structure
"""

# ============================================================================
# EDIT THIS SECTION WITH YOUR ACTUAL COLUMN NAMES
# ============================================================================

COLUMN_MAPPING = {
    # Clients Sheet - Map your column names to dashboard fields
    'clients': {
        'RUT': 'RUT',                          # Cliente ID
        'Entidad': 'Name',                     # Client name
        'Household': 'Household',              # Family/Group
        'Servicio': 'Service_Type',            # DAP, Cartera Gestionada, etc.
        'WM': 'Wealth_Manager',                # Wealth Manager name
        'IA': 'Advisor_ID',                    # Investment Advisor ID
        # Optional - add these if you have them:
        # 'Architecture': 'Architecture',       # Conservative, Balanced, etc.
        # 'Risk_Profile': 'Risk_Profile',      # Low, Medium, High, etc.
        # 'Portfolio_Value': 'Portfolio_Value_USD',
        # 'Target_Return': 'Target_Return_%',
    },

    # Holdings Sheet - Map your position columns
    'holdings': {
        'Cliente': 'Client_RUT',               # RUT without formatting
        'Entidad': 'Client_Name',              # Entity name (optional, for reference)
        'Cantidad': 'Units',                   # Number of shares
        'Instrumento': 'Position_Name',        # Instrument name
        'Tipo': 'Asset_Class',                 # Alternatives, Renta Variable, Renta Fija
        'Costo Unitario': 'Cost_Per_Unit',     # Purchase price per share
        'Costo Base': 'Cost_Base',             # Quantity × Purchase price
        'Precio Mercado': 'Unit_Price_USD',    # Current market price per share
        'Valor de Mercado': 'Current_Value_USD',  # Quantity × Market price
        'G/P no Realizada': 'Unrealized_Gains_CLP',  # Unrealized P&L in CLP
        'Rent. no Realizada': 'Unrealized_Return_%',  # Unrealized return %
        'Cuenta': 'Account_Type',              # DAP or account number
        'Fecha': 'Date',                       # Date (optional)
        'ISIN': 'ISIN',                        # International ID (optional)
        'Nemo': 'Nemo',                        # Local ID (optional)
        'CUSIP': 'CUSIP',                      # CUSIP (optional)
        'RIC': 'RIC',                          # RIC (optional)
    },

    # Advisors Sheet (if you have one)
    'advisors': {
        'Advisor_ID': 'Advisor_ID',            # Unique ID
        'Name': 'Name',                         # Advisor name
        'Email': 'Email',                       # Email (optional)
        'Phone': 'Phone',                       # Phone (optional)
    }
}

# ============================================================================
# ASSET CLASS MAPPING - Maps your asset types to dashboard categories
# ============================================================================

ASSET_CLASS_MAPPING = {
    # Spanish to Dashboard Mapping
    'Renta Variable': 'Stocks',           # Variable income (stocks)
    'Renta Fija': 'Bonds',                # Fixed income (bonds)
    'Alternatives': 'Alternatives',       # Alternatives
    'Fondos Mutuos': 'Mutual Funds',      # Mutual funds
    'Depósitos': 'Cash',                  # Deposits/Cash
    'DAP': 'Cash',                        # Term deposits
    'Acciones': 'Stocks',                 # Shares
    'Bonos': 'Bonds',                     # Bonds
    'ETF': 'ETF',                         # Exchange Traded Funds

    # Add any other asset types you have
    # 'Your_Type': 'Dashboard_Category',
}

# ============================================================================
# SERVICE TYPE MAPPING - Maps service types
# ============================================================================

SERVICE_TYPE_MAPPING = {
    'DAP': 'Term_Deposits',
    'Cartera Gestionada': 'Managed_Portfolio',
    'Asesoría': 'Advisory',
    'ADC': 'Discretionary_Mandate',

    # Add any other service types
    # 'Your_Service': 'Category',
}

# ============================================================================
# RISK PROFILE & ARCHITECTURE (Optional)
# If your data doesn't have these, the dashboard will assign defaults
# ============================================================================

# If you want to map service types to risk profiles:
SERVICE_TO_RISK_PROFILE = {
    'Term_Deposits': 'Low',
    'Managed_Portfolio': 'Medium',
    'Advisory': 'Medium',
    'Discretionary_Mandate': 'Medium-High',
}

# If you want to map service types to architectures:
SERVICE_TO_ARCHITECTURE = {
    'Term_Deposits': 'Conservative',
    'Managed_Portfolio': 'Balanced',
    'Advisory': 'Balanced',
    'Discretionary_Mandate': 'Growth',
}

# ============================================================================
# EXCEL FILE CONFIGURATION
# ============================================================================

EXCEL_CONFIG = {
    'file_path': 'data/portfolio_data.xlsx',
    'clients_sheet': 'Clientes',           # Name of your Clients sheet
    'holdings_sheet': 'Posiciones',        # Name of your Holdings sheet
    'advisors_sheet': 'Asesores',          # Name of your Advisors sheet (if exists)
}

# ============================================================================
# CALCULATION SETTINGS
# ============================================================================

CALCULATION_SETTINGS = {
    'rebalance_threshold': 5.0,            # % deviation threshold for rebalancing alerts
    'currency': 'CLP',                     # Default currency
    'date_format': '%Y-%m-%d',             # Date format in your data
}

# ============================================================================
# HELPER FUNCTION - Do not edit
# ============================================================================

def get_mapped_column(category, dashboard_field):
    """Get your actual column name for a dashboard field"""
    mapping = COLUMN_MAPPING.get(category, {})
    for your_col, dash_col in mapping.items():
        if dash_col == dashboard_field:
            return your_col
    return None


def validate_mapping():
    """Check if mapping is configured correctly"""
    errors = []

    if not COLUMN_MAPPING.get('clients'):
        errors.append("⚠️ No clients mapping configured")
    if not COLUMN_MAPPING.get('holdings'):
        errors.append("⚠️ No holdings mapping configured")

    return errors


if __name__ == "__main__":
    errors = validate_mapping()
    if errors:
        print("Configuration Issues:")
        for error in errors:
            print(f"  {error}")
    else:
        print("✅ Mapping configuration is ready!")
