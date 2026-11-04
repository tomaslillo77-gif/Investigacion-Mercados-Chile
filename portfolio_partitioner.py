"""
Portfolio Partitioner
Identifies what % of client portfolio is in assigned model vs outside
"""

import pandas as pd
from typing import Dict, Tuple, List


class PortfolioPartitioner:
    """Partition client portfolio into model vs non-model positions"""

    def __init__(self, portfolio_models_df: pd.DataFrame = None):
        """
        Initialize with portfolio models

        Args:
            portfolio_models_df: DataFrame with model portfolio compositions
        """
        if portfolio_models_df is None or (isinstance(portfolio_models_df, pd.DataFrame) and portfolio_models_df.empty):
            self.models = pd.DataFrame()
        else:
            self.models = portfolio_models_df
        self.model_instruments_cache = {}

    def get_model_instruments(self, architecture: str, risk_profile: str) -> Dict[str, float]:
        """
        Get all instruments in a model portfolio with their target weights

        Args:
            architecture: Architecture name
            risk_profile: Risk profile name

        Returns:
            Dict {instrument_name: target_weight}
        """

        cache_key = f"{architecture}_{risk_profile}"

        if cache_key in self.model_instruments_cache:
            return self.model_instruments_cache[cache_key]

        if self.models.empty:
            return {}

        filtered = self.models[
            (self.models['Architecture'] == architecture) &
            (self.models['Risk_Profile'] == risk_profile)
        ]

        if filtered.empty:
            return {}

        # Get instruments with their weights
        instruments = {}
        for _, row in filtered.iterrows():
            instrument_name = row.get('Instrumento', row.get('Position_Name', ''))
            weight = row.get('Target_Allocation_%', row.get('Ponderacion_%', 0))

            if instrument_name and weight:
                instruments[instrument_name] = weight

        self.model_instruments_cache[cache_key] = instruments
        return instruments

    def partition_portfolio(self, client_holdings: pd.DataFrame,
                           assigned_architecture: str,
                           assigned_risk_profile: str) -> Dict:
        """
        Partition client portfolio into model and non-model positions

        Args:
            client_holdings: DataFrame with client positions
                Columns: Instrumento (or Position_Name), Current_Value_USD
            assigned_architecture: Assigned architecture
            assigned_risk_profile: Assigned risk profile

        Returns:
            Dictionary with partition analysis
        """

        if client_holdings.empty:
            return {
                'total_value': 0,
                'in_model_value': 0,
                'outside_model_value': 0,
                'in_model_pct': 0,
                'outside_model_pct': 0,
                'in_model_instruments': pd.DataFrame(),
                'outside_model_instruments': pd.DataFrame(),
                'model_instruments': {}
            }

        # Get model instruments for this assignment
        model_instruments = self.get_model_instruments(assigned_architecture, assigned_risk_profile)

        total_value = client_holdings['Current_Value_USD'].sum()

        in_model_positions = []
        outside_model_positions = []
        in_model_value = 0
        outside_model_value = 0

        # Process each holding
        for _, holding in client_holdings.iterrows():
            instrument_name = holding.get('Instrumento', holding.get('Position_Name', ''))
            value = holding['Current_Value_USD']

            # Check if instrument is in model
            if instrument_name in model_instruments:
                in_model_value += value
                in_model_positions.append({
                    'Instrumento': instrument_name,
                    'Valor': value,
                    'Target_%': model_instruments[instrument_name] * 100,
                    'Actual_%': (value / total_value * 100) if total_value > 0 else 0,
                    'Tipo': 'En Cartera'
                })
            else:
                outside_model_value += value
                outside_model_positions.append({
                    'Instrumento': instrument_name,
                    'Valor': value,
                    'Pct_del_Total': (value / total_value * 100) if total_value > 0 else 0,
                    'Tipo': 'Fuera de Cartera'
                })

        # Calculate percentages
        in_model_pct = (in_model_value / total_value * 100) if total_value > 0 else 0
        outside_model_pct = (outside_model_value / total_value * 100) if total_value > 0 else 0

        return {
            'total_value': total_value,
            'in_model_value': in_model_value,
            'outside_model_value': outside_model_value,
            'in_model_pct': in_model_pct,
            'outside_model_pct': outside_model_pct,
            'in_model_instruments': pd.DataFrame(in_model_positions) if in_model_positions else pd.DataFrame(),
            'outside_model_instruments': pd.DataFrame(outside_model_positions) if outside_model_positions else pd.DataFrame(),
            'model_instruments': model_instruments
        }

    def get_rebalancing_needs(self, client_holdings: pd.DataFrame,
                             assigned_architecture: str,
                             assigned_risk_profile: str,
                             threshold_pct: float = 5.0) -> List[Dict]:
        """
        Identify rebalancing needs within model portfolio

        Args:
            client_holdings: Client positions
            assigned_architecture: Assigned architecture
            assigned_risk_profile: Assigned risk profile
            threshold_pct: Threshold % for deviation alert

        Returns:
            List of rebalancing actions needed
        """

        partition = self.partition_portfolio(
            client_holdings,
            assigned_architecture,
            assigned_risk_profile
        )

        if partition['in_model_instruments'].empty:
            return []

        rebalancing_actions = []

        for _, instrument in partition['in_model_instruments'].iterrows():
            target = instrument['Target_%']
            actual = instrument['Actual_%']
            deviation = actual - target

            if abs(deviation) > threshold_pct:
                action = "COMPRAR" if deviation < 0 else "VENDER"
                rebalancing_actions.append({
                    'Instrumento': instrument['Instrumento'],
                    'Accion': action,
                    'Target_%': target,
                    'Actual_%': actual,
                    'Desviacion_%': abs(deviation),
                    'Prioridad': 'Alta' if abs(deviation) > threshold_pct * 2 else 'Media'
                })

        return sorted(rebalancing_actions, key=lambda x: x['Desviacion_%'], reverse=True)

    def generate_partition_summary(self, partition: Dict) -> str:
        """
        Generate text summary of partition

        Args:
            partition: Partition dictionary from partition_portfolio()

        Returns:
            Human-readable summary
        """

        total = partition['total_value']
        in_model = partition['in_model_value']
        outside = partition['outside_model_value']
        in_pct = partition['in_model_pct']
        out_pct = partition['outside_model_pct']

        summary = f"""
RESUMEN DE PARTICIÓN DE PORTAFOLIO

Valor Total: ${total:,.0f}

Distribución:
  ✓ En Cartera Modelo: ${in_model:,.0f} ({in_pct:.1f}%)
  ⚠ Fuera de Cartera: ${outside:,.0f} ({out_pct:.1f}%)

Instrumentos:
  - En modelo: {len(partition['in_model_instruments'])}
  - Fuera: {len(partition['outside_model_instruments'])}
"""

        return summary


if __name__ == "__main__":
    # Test
    # Create sample data
    sample_holdings = pd.DataFrame({
        'Instrumento': [
            'Fondo Scotia Defensivo',
            'Fondo Balanceado',
            'Acciones Mineras ABC',
            'QUEDES XYZ'
        ],
        'Current_Value_USD': [300000, 400000, 200000, 100000]
    })

    sample_models = pd.DataFrame({
        'Architecture': ['Scotia', 'Scotia'],
        'Risk_Profile': ['Defensivo', 'Defensivo'],
        'Instrumento': ['Fondo Scotia Defensivo', 'Fondo Balanceado'],
        'Target_Allocation_%': [30, 40]
    })

    partitioner = PortfolioPartitioner(sample_models)
    partition = partitioner.partition_portfolio(
        sample_holdings,
        'Scotia',
        'Defensivo'
    )

    print(partitioner.generate_partition_summary(partition))
    print(f"\n📊 En Cartera:")
    print(partition['in_model_instruments'])
    print(f"\n⚠ Fuera de Cartera:")
    print(partition['outside_model_instruments'])
