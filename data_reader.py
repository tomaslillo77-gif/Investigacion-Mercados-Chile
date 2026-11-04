import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import re

class PortfolioDataReader:
    """Read and process portfolio data from Excel files"""

    @staticmethod
    def _clean_numeric(value):
        """Convert formatted numeric strings to float"""
        if pd.isna(value):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)

        s = str(value).strip()
        s = re.sub(r'[^\d,.-]', '', s)
        if ',' in s and '.' in s:
            if s.rfind(',') > s.rfind('.'):
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '')
        elif ',' in s:
            s = s.replace(',', '')

        try:
            return float(s)
        except:
            return 0.0

    def __init__(self, excel_path: str = "data/Engine WM Dummy.xlsx"):
        self.excel_path = excel_path
        self._clients_cache = None
        self._holdings_cache = None
        self._advisors_cache = None
        self._architectures_cache = None
        self._is_engine_wm = "Engine WM" in excel_path

    def read_advisors(self) -> pd.DataFrame:
        """Read advisor data from Excel"""
        if self._advisors_cache is not None:
            return self._advisors_cache
        try:
            if self._is_engine_wm:
                # Extract advisors from Dummy Metricas
                df = pd.read_excel(self.excel_path, sheet_name="Dummy Metricas", header=2)
                advisors_list = []
                for _, row in df.iterrows():
                    advisor_id = str(row.get('IA', '')).strip()
                    if advisor_id and advisor_id not in [a['Advisor_ID'] for a in advisors_list]:
                        advisors_list.append({
                            'Advisor_ID': advisor_id,
                            'Name': f"Advisor {advisor_id}",
                            'Email': f"{advisor_id.lower()}@wealthmgmt.cl",
                            'Phone': "+56 2 1234 5678"
                        })
                df = pd.DataFrame(advisors_list)
            else:
                df = pd.read_excel(self.excel_path, sheet_name="Advisors")
            self._advisors_cache = df
            return df
        except FileNotFoundError:
            print(f"Excel file not found at {self.excel_path}")
            return pd.DataFrame()

    def read_clients(self) -> pd.DataFrame:
        """Read client data from Excel"""
        if self._clients_cache is not None:
            return self._clients_cache
        try:
            if self._is_engine_wm:
                # Extract clients from Dummy Metricas (one per unique RUT)
                df_raw = pd.read_excel(self.excel_path, sheet_name="Dummy Metricas", header=2)
                clients_list = []
                seen = set()

                for _, row in df_raw.iterrows():
                    rut = str(row.get('RUT', '')).strip()
                    if rut and rut not in seen:
                        seen.add(rut)
                        clients_list.append({
                            'RUT': rut,
                            'Name': str(row.get('Entidad', rut)).strip(),
                            'Advisor_ID': str(row.get('IA', 'IA_000001')).strip(),
                            'Architecture': 'Scotia',
                            'Risk_Profile': str(row.get('Perfil de Riesgo', 'Medium')).strip(),
                            'Portfolio_Type': 'Managed',
                            'Service_Type': str(row.get('Servicio', 'Wealth Management')).strip(),
                            'Portfolio_Value_USD': self._clean_numeric(row.get('CAD (USD MM)', 0)) * 1_000_000,
                        })
                df = pd.DataFrame(clients_list)
            else:
                # Try different sheet names
                sheet_name = "Clients"
                try:
                    df = pd.read_excel(self.excel_path, sheet_name=sheet_name)
                except:
                    df = pd.read_excel(self.excel_path, sheet_name="Clientes")

                # Rename columns to standard names if needed
                column_mapping = {
                    'Entidad': 'Name',
                    'Servicio': 'Service_Type',
                    'WM': 'Wealth_Manager',
                    'IA': 'Advisor_ID',
                }
                for old_col, new_col in column_mapping.items():
                    if old_col in df.columns and new_col not in df.columns:
                        df.rename(columns={old_col: new_col}, inplace=True)

            self._clients_cache = df
            return df
        except FileNotFoundError:
            print(f"Excel file not found at {self.excel_path}")
            return pd.DataFrame()

    def read_holdings(self) -> pd.DataFrame:
        """Read client holdings from Excel"""
        if self._holdings_cache is not None:
            return self._holdings_cache
        try:
            if self._is_engine_wm:
                # Extract holdings from Dummy Posiciones
                df_raw = pd.read_excel(self.excel_path, sheet_name="Dummy Posiciones", header=2)
                holdings_list = []

                for _, row in df_raw.iterrows():
                    rut = str(row.get('Cliente (ID)', '')).strip()
                    instrumento = str(row.get('Instrumento', '')).strip()

                    if rut and instrumento:
                        holdings_list.append({
                            'Client_RUT': rut,
                            'Position_Name': instrumento,
                            'Asset_Class': str(row.get('Tipo', 'Mixed')).strip(),
                            'Units': self._clean_numeric(row.get('Cantidad', 0)),
                            'Unit_Price_USD': self._clean_numeric(row.get('Precio Mercado', 0)),
                            'Current_Value_USD': self._clean_numeric(row.get('Valor de Mercado', 0)),
                            'Ticker': str(row.get('Isin', '')).strip(),
                        })

                df = pd.DataFrame(holdings_list)
            else:
                # Try different sheet names
                sheet_name = "Holdings"
                try:
                    df = pd.read_excel(self.excel_path, sheet_name=sheet_name)
                except:
                    df = pd.read_excel(self.excel_path, sheet_name="Posiciones")

                # Rename columns to standard names if needed
                column_mapping = {
                    'Cliente': 'Client_RUT',
                    'Cantidad': 'Units',
                    'Instrumento': 'Position_Name',
                    'Tipo': 'Asset_Class',
                    'Precio_Mercado': 'Unit_Price_USD',
                    'Valor_de_Mercado': 'Current_Value_USD',
                    'G_P_no_Realizada': 'Unrealized_Gains_CLP',
                    'Rent_no_Realizada_%': 'Unrealized_Return_%',
                }
                for old_col, new_col in column_mapping.items():
                    if old_col in df.columns and new_col not in df.columns:
                        df.rename(columns={old_col: new_col}, inplace=True)

            self._holdings_cache = df
            return df
        except FileNotFoundError:
            print(f"Excel file not found at {self.excel_path}")
            return pd.DataFrame()

    def read_portfolio_architectures(self) -> pd.DataFrame:
        """Read portfolio architecture definitions"""
        if self._architectures_cache is not None:
            return self._architectures_cache
        try:
            if self._is_engine_wm:
                # Extract architectures from Dummy Carteras
                df_raw = pd.read_excel(self.excel_path, sheet_name="Dummy Carteras", header=2)
                archs_list = []
                seen = set()

                for _, row in df_raw.iterrows():
                    arch = str(row.get('arquitectura', '')).strip()
                    profile = str(row.get('perfil', '')).strip()
                    key = (arch, profile)

                    if arch and key not in seen:
                        seen.add(key)
                        archs_list.append({
                            'Architecture': arch,
                            'Risk_Profile': profile,
                            'Stocks_%': self._clean_numeric(row.get('peso_objetivo', 0.40)),
                            'Bonds_%': 0.40,
                            'Alternatives_%': 0.20,
                            'Real_Estate_%': 0.0,
                        })

                # If empty, create defaults
                if not archs_list:
                    for arch in ['Scotia', 'Abierta_Pesos', 'Abierta_Dolares']:
                        for profile in ['Conservador', 'Moderado', 'Balanceado']:
                            archs_list.append({
                                'Architecture': arch,
                                'Risk_Profile': profile,
                                'Stocks_%': 0.30,
                                'Bonds_%': 0.50,
                                'Alternatives_%': 0.20,
                                'Real_Estate_%': 0.0,
                            })

                df = pd.DataFrame(archs_list)
            else:
                df = pd.read_excel(self.excel_path, sheet_name="Portfolio_Architectures")

            self._architectures_cache = df
            return df
        except FileNotFoundError:
            print(f"Excel file not found at {self.excel_path}")
            return pd.DataFrame()

    def get_clients_by_advisor(self, advisor_id: str) -> pd.DataFrame:
        """Get all clients for a specific advisor"""
        clients = self.read_clients()
        return clients[clients['Advisor_ID'] == advisor_id].reset_index(drop=True)

    def get_client_holdings(self, client_rut: str) -> pd.DataFrame:
        """Get all holdings for a specific client"""
        holdings = self.read_holdings()
        return holdings[holdings['Client_RUT'] == client_rut].reset_index(drop=True)

    def get_client_info(self, client_rut: str) -> Dict:
        """Get complete client information"""
        clients = self.read_clients()
        client = clients[clients['RUT'] == client_rut]
        if client.empty:
            return {}
        return client.iloc[0].to_dict()

    def calculate_portfolio_kpis(self, client_rut: str) -> Dict:
        """Calculate key performance indicators for a client portfolio"""
        client = self.get_client_info(client_rut)
        holdings = self.get_client_holdings(client_rut)

        total_value = 0
        num_positions = 0
        diversification = 0

        if client and not holdings.empty:
            total_value = holdings['Current_Value_USD'].sum()
            num_positions = len(holdings)
            diversification = self._calculate_diversification(holdings)

        kpis = {
            'client_rut': client_rut,
            'client_name': client.get('Name', '') if client else '',
            'portfolio_value': total_value,
            'num_positions': num_positions,
            'architecture': client.get('Architecture', '') if client else '',
            'risk_profile': client.get('Risk_Profile', '') if client else '',
            'portfolio_type': client.get('Portfolio_Type', '') if client else '',
            'target_return': client.get('Target_Return_%', 0) if client else 0,
            'benchmark': client.get('Benchmark', '') if client else '',
            'diversification_score': diversification
        }
        return kpis

    def _calculate_diversification(self, holdings: pd.DataFrame) -> float:
        """Calculate Herfindahl diversification index (0-100)"""
        if holdings.empty:
            return 0

        # If we have Current_Allocation_%, use it; otherwise calculate from values
        if 'Current_Allocation_%' in holdings.columns:
            allocations = holdings['Current_Allocation_%'].values / 100
        elif 'Current_Value_USD' in holdings.columns:
            total = holdings['Current_Value_USD'].sum()
            if total > 0:
                allocations = (holdings['Current_Value_USD'].values / total)
            else:
                return 0
        else:
            return 0

        # Filter out zero allocations
        allocations = allocations[allocations > 0]
        if len(allocations) == 0:
            return 0

        herfindahl = np.sum(allocations ** 2)
        # Convert to 0-100 scale where 100 is perfectly diversified
        diversification = 100 * (1 - herfindahl)
        return round(diversification, 2)

    def check_rebalance_needed(self, client_rut: str, threshold: float = 5.0) -> Tuple[bool, str, float]:
        """
        Check if client portfolio needs rebalancing
        threshold: allowed deviation in percentage points
        Returns: (needs_rebalance, reason, max_deviation)
        """
        holdings = self.get_client_holdings(client_rut)
        if holdings.empty:
            return False, "No holdings found", 0

        # Simplified check: if portfolio has any positions, assume it's balanced
        # Full rebalancing logic would require Target_Allocation_% data
        max_deviation = 0
        problem_asset = ""

        # Check if we have the target allocation columns
        if 'Target_Allocation_%' in holdings.columns and 'Current_Allocation_%' in holdings.columns:
            for _, holding in holdings.iterrows():
                target = holding.get('Target_Allocation_%', 0)
                actual = holding.get('Current_Allocation_%', 0)
                if pd.notna(target) and pd.notna(actual):
                    deviation = abs(actual - target)
                    if deviation > max_deviation:
                        max_deviation = deviation
                        problem_asset = str(holding.get('Asset_Class', 'Unknown'))

        needs_rebalance = max_deviation > threshold

        if needs_rebalance:
            reason = f"⚠️ {problem_asset} is {max_deviation:.1f}% away from target (threshold: {threshold}%)"
        else:
            reason = "✅ Portfolio is balanced"

        return needs_rebalance, reason, max_deviation

    def get_advisor_summary(self, advisor_id: str) -> Dict:
        """Get summary KPIs for an advisor's book of business"""
        clients = self.get_clients_by_advisor(advisor_id)

        if clients.empty:
            return {
                'advisor_id': advisor_id,
                'num_clients': 0,
                'total_aum': 0,
                'avg_portfolio_value': 0,
                'managed_clients': 0,
                'self_directed_clients': 0,
                'clients_needing_rebalance': 0,
                'avg_diversification': 0
            }

        total_aum = clients['Portfolio_Value_USD'].sum()
        num_clients = len(clients)
        managed_clients = len(clients[clients['Portfolio_Type'] == 'Managed'])
        self_directed = len(clients[clients['Portfolio_Type'] == 'Self-Directed'])

        clients_needing_rebalance = 0
        diversifications = []

        for _, client in clients.iterrows():
            needs_rebalance, _, _ = self.check_rebalance_needed(client['RUT'])
            if needs_rebalance:
                clients_needing_rebalance += 1

            kpis = self.calculate_portfolio_kpis(client['RUT'])
            diversifications.append(kpis.get('diversification_score', 0))

        avg_diversification = np.mean(diversifications) if diversifications else 0

        return {
            'advisor_id': advisor_id,
            'num_clients': num_clients,
            'total_aum': total_aum,
            'avg_portfolio_value': total_aum / num_clients if num_clients > 0 else 0,
            'managed_clients': managed_clients,
            'self_directed_clients': self_directed,
            'clients_needing_rebalance': clients_needing_rebalance,
            'avg_diversification': round(avg_diversification, 2)
        }

    def get_business_summary(self) -> Dict:
        """Get summary KPIs for the entire business"""
        clients = self.read_clients()
        advisors = self.read_advisors()

        if clients.empty:
            return {
                'total_aum': 0,
                'num_clients': 0,
                'num_advisors': 0,
                'avg_portfolio_value': 0,
                'managed_clients': 0,
                'self_directed_clients': 0,
                'clients_needing_rebalance': 0,
                'avg_diversification': 0
            }

        total_aum = clients['Portfolio_Value_USD'].sum()
        num_clients = len(clients)
        num_advisors = len(advisors)
        managed_clients = len(clients[clients['Portfolio_Type'] == 'Managed'])
        self_directed = len(clients[clients['Portfolio_Type'] == 'Self-Directed'])

        clients_needing_rebalance = 0
        diversifications = []

        for _, client in clients.iterrows():
            needs_rebalance, _, _ = self.check_rebalance_needed(client['RUT'])
            if needs_rebalance:
                clients_needing_rebalance += 1

            kpis = self.calculate_portfolio_kpis(client['RUT'])
            diversifications.append(kpis.get('diversification_score', 0))

        avg_diversification = np.mean(diversifications) if diversifications else 0

        return {
            'total_aum': total_aum,
            'num_clients': num_clients,
            'num_advisors': num_advisors,
            'avg_portfolio_value': total_aum / num_clients if num_clients > 0 else 0,
            'managed_clients': managed_clients,
            'self_directed_clients': self_directed,
            'clients_needing_rebalance': clients_needing_rebalance,
            'avg_diversification': round(avg_diversification, 2)
        }

    def get_all_clients_data(self) -> pd.DataFrame:
        """Get all clients with summary data for director overview"""
        clients = self.read_clients()
        data = []

        for _, client in clients.iterrows():
            rut = client['RUT']
            needs_rebalance, reason, deviation = self.check_rebalance_needed(rut)

            data.append({
                'RUT': rut,
                'Name': client['Name'],
                'Advisor': client['Advisor_ID'],
                'Portfolio Value': client['Portfolio_Value_USD'],
                'Architecture': client['Architecture'],
                'Risk Profile': client['Risk_Profile'],
                'Type': client['Portfolio_Type'],
                'Rebalance Needed': '⚠️ Yes' if needs_rebalance else '✅ No',
                'Deviation': f"{deviation:.1f}%"
            })

        return pd.DataFrame(data)


if __name__ == "__main__":
    # Test the reader with sample data
    from create_template import create_professional_template
    create_professional_template()

    reader = PortfolioDataReader()

    print("\n=== BUSINESS SUMMARY ===")
    summary = reader.get_business_summary()
    for key, value in summary.items():
        if 'aum' in key.lower() or 'value' in key.lower():
            print(f"{key}: ${value:,.2f}")
        else:
            print(f"{key}: {value}")
