"""
Data Transformer
Converts your actual Excel data format to dashboard-compatible format
using the column mapping configuration
"""

import pandas as pd
from column_mapping import (
    COLUMN_MAPPING,
    ASSET_CLASS_MAPPING,
    SERVICE_TYPE_MAPPING,
    SERVICE_TO_RISK_PROFILE,
    SERVICE_TO_ARCHITECTURE,
    EXCEL_CONFIG
)


class DataTransformer:
    """Transform your data format to dashboard format"""

    def __init__(self, excel_path=None):
        self.excel_path = excel_path or EXCEL_CONFIG['file_path']
        self.clients_sheet = EXCEL_CONFIG['clients_sheet']
        self.holdings_sheet = EXCEL_CONFIG['holdings_sheet']

    def read_raw_clients(self):
        """Read clients sheet without transformation"""
        try:
            return pd.read_excel(self.excel_path, sheet_name=self.clients_sheet)
        except Exception as e:
            print(f"Error reading clients: {e}")
            return pd.DataFrame()

    def read_raw_holdings(self):
        """Read holdings sheet without transformation"""
        try:
            return pd.read_excel(self.excel_path, sheet_name=self.holdings_sheet)
        except Exception as e:
            print(f"Error reading holdings: {e}")
            return pd.DataFrame()

    def transform_clients(self):
        """Transform clients data to dashboard format"""
        df = self.read_raw_clients()
        if df.empty:
            return pd.DataFrame()

        # Map columns
        mapping = COLUMN_MAPPING['clients']
        rename_dict = {v: k for k, v in mapping.items() if k in df.columns}

        # Rename columns to dashboard format
        df_transformed = df.rename(columns=rename_dict)

        # Handle Service_Type mapping
        if 'Service_Type' in df_transformed.columns:
            df_transformed['Service_Type'] = df_transformed['Service_Type'].map(
                SERVICE_TYPE_MAPPING
            ).fillna(df_transformed['Service_Type'])

        # Add Risk_Profile and Architecture based on Service_Type
        if 'Risk_Profile' not in df_transformed.columns and 'Service_Type' in df_transformed.columns:
            df_transformed['Risk_Profile'] = df_transformed['Service_Type'].map(
                SERVICE_TO_RISK_PROFILE
            ).fillna('Medium')

        if 'Architecture' not in df_transformed.columns and 'Service_Type' in df_transformed.columns:
            df_transformed['Architecture'] = df_transformed['Service_Type'].map(
                SERVICE_TO_ARCHITECTURE
            ).fillna('Balanced')

        # Add Portfolio_Type based on Service_Type
        if 'Portfolio_Type' not in df_transformed.columns:
            service_to_ptype = {
                'Term_Deposits': 'Self-Directed',
                'Managed_Portfolio': 'Managed',
                'Advisory': 'Managed',
                'Discretionary_Mandate': 'Managed',
            }
            if 'Service_Type' in df_transformed.columns:
                df_transformed['Portfolio_Type'] = df_transformed['Service_Type'].map(
                    service_to_ptype
                ).fillna('Managed')

        # Add placeholder values if missing
        if 'Portfolio_Value_USD' not in df_transformed.columns:
            df_transformed['Portfolio_Value_USD'] = 0

        if 'Target_Return_%' not in df_transformed.columns:
            df_transformed['Target_Return_%'] = 5.0

        if 'Benchmark' not in df_transformed.columns:
            df_transformed['Benchmark'] = 'IPSA'

        # Clean up RUT format (remove special chars for matching with holdings)
        if 'RUT' in df_transformed.columns:
            df_transformed['RUT_Clean'] = df_transformed['RUT'].astype(str).str.replace(
                r'[-.]', '', regex=True
            )

        return df_transformed[['RUT', 'Name', 'Household', 'Service_Type', 'Wealth_Manager',
                               'Advisor_ID', 'Risk_Profile', 'Architecture', 'Portfolio_Type',
                               'Portfolio_Value_USD', 'Target_Return_%', 'Benchmark', 'RUT_Clean']]

    def transform_holdings(self, clients_df=None):
        """Transform holdings data to dashboard format"""
        df = self.read_raw_holdings()
        if df.empty:
            return pd.DataFrame()

        mapping = COLUMN_MAPPING['holdings']

        # Rename columns to dashboard format
        rename_dict = {}
        for your_col, dash_col in mapping.items():
            if your_col in df.columns:
                rename_dict[your_col] = dash_col

        df_transformed = df.rename(columns=rename_dict)

        # Handle Asset_Class mapping
        if 'Asset_Class' in df_transformed.columns:
            df_transformed['Asset_Class'] = df_transformed['Asset_Class'].map(
                ASSET_CLASS_MAPPING
            ).fillna(df_transformed['Asset_Class'])

        # Calculate allocations if we have the data
        if 'Current_Value_USD' in df_transformed.columns and clients_df is not None:
            df_transformed = self._calculate_allocations(df_transformed, clients_df)

        # Clean RUT format for matching
        if 'Client_RUT' in df_transformed.columns:
            df_transformed['Client_RUT'] = df_transformed['Client_RUT'].astype(str).str.replace(
                r'[-.]', '', regex=True
            )

        # Calculate derived fields
        if 'Units' in df_transformed.columns and 'Unit_Price_USD' in df_transformed.columns:
            if 'Current_Value_USD' not in df_transformed.columns:
                df_transformed['Current_Value_USD'] = (
                    df_transformed['Units'] * df_transformed['Unit_Price_USD']
                )

        return df_transformed

    def _calculate_allocations(self, holdings_df, clients_df):
        """Calculate current and target allocations"""
        holdings_df['Current_Allocation_%'] = 0.0
        holdings_df['Target_Allocation_%'] = 0.0

        # Group by client
        for client_rut in holdings_df['Client_RUT'].unique():
            client_holdings = holdings_df[holdings_df['Client_RUT'] == client_rut]
            total_value = client_holdings['Current_Value_USD'].sum()

            if total_value > 0:
                holdings_df.loc[holdings_df['Client_RUT'] == client_rut, 'Current_Allocation_%'] = (
                    (client_holdings['Current_Value_USD'] / total_value * 100).values
                )

            # Get target allocation from architecture if possible
            # For now, set equal weight per asset class
            num_assets = len(client_holdings)
            if num_assets > 0:
                target = 100 / num_assets
                holdings_df.loc[holdings_df['Client_RUT'] == client_rut, 'Target_Allocation_%'] = target

        return holdings_df

    def get_dashboard_clients(self):
        """Get clients data ready for dashboard"""
        return self.transform_clients()

    def get_dashboard_holdings(self):
        """Get holdings data ready for dashboard"""
        clients_df = self.get_dashboard_clients()
        return self.transform_holdings(clients_df)

    def validate_data(self):
        """Check data integrity"""
        issues = []

        clients = self.get_dashboard_clients()
        holdings = self.get_dashboard_holdings()

        if clients.empty:
            issues.append("⚠️ No clients data found")
        if holdings.empty:
            issues.append("⚠️ No holdings data found")

        # Check for RUT mismatches
        if not clients.empty and not holdings.empty:
            client_ruts = set(clients['RUT_Clean'].astype(str))
            holding_ruts = set(holdings['Client_RUT'].astype(str))
            orphaned_holdings = holding_ruts - client_ruts

            if orphaned_holdings:
                issues.append(f"⚠️ {len(orphaned_holdings)} holdings have no matching client")

        return issues


if __name__ == "__main__":
    transformer = DataTransformer()

    print("Validating data...")
    issues = transformer.validate_data()

    if issues:
        print("Issues found:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("✅ Data validation passed!")

    print(f"\nClients: {len(transformer.get_dashboard_clients())} loaded")
    print(f"Holdings: {len(transformer.get_dashboard_holdings())} loaded")
