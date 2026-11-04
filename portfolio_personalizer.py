# OBSOLETO (2026-10-27): Sistema antiguo de asignaciones personalizadas por cliente (JSON suelto). Lo reemplaza `wm/portafolio_cliente.py` (portafolios por cliente con versiones en PostgreSQL, pestaña «Portafolio» de la ficha).
# Solo lo usan `app_v3.py` y los respaldos `app_v4_final_backup_*.py`; se puede borrar cuando esos archivos ya no hagan falta.
"""
Portfolio Personalizer
Allows customization of portfolio allocations per client
Handles model portfolios and custom allocations
"""

import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Tuple

class PortfolioPersonalizer:
    """Manage and personalize portfolio allocations for clients"""

    def __init__(self, data_path: str = "data/"):
        self.data_path = Path(data_path)
        self.custom_allocations_file = self.data_path / "custom_allocations.json"
        self.load_custom_allocations()

    def load_custom_allocations(self):
        """Load custom allocations from file"""
        if self.custom_allocations_file.exists():
            with open(self.custom_allocations_file, 'r') as f:
                self.custom_allocations = json.load(f)
        else:
            self.custom_allocations = {}

    def save_custom_allocations(self):
        """Save custom allocations to file"""
        self.data_path.mkdir(exist_ok=True)
        with open(self.custom_allocations_file, 'w') as f:
            json.dump(self.custom_allocations, f, indent=2)

    def get_assigned_portfolio(self, client_rut: str, client_service_type: str,
                              default_portfolio_df: pd.DataFrame) -> Dict:
        """
        Get assigned portfolio for a client

        Args:
            client_rut: Client RUT
            client_service_type: Service type (Cartera gestionada, ADC, Asesoría, etc.)
            default_portfolio_df: Default portfolio model dataframe

        Returns:
            Dictionary with portfolio allocation
        """

        # If client has custom allocation, return it
        if client_rut in self.custom_allocations:
            return self.custom_allocations[client_rut]

        # If service type is Self-Directed or Depósito, no model portfolio
        if client_service_type in ['Self-Directed', 'Depósito a Plazo', 'DAP']:
            return {
                'type': 'none',
                'name': 'No model portfolio',
                'allocations': {}
            }

        # Otherwise return default based on service type
        return {
            'type': 'default',
            'name': f'Default - {client_service_type}',
            'allocations': self._get_default_allocations(client_service_type)
        }

    def _get_default_allocations(self, service_type: str) -> Dict[str, float]:
        """Get default allocations based on service type"""

        defaults = {
            'Cartera gestionada': {
                'Renta Variable': 0.50,
                'Renta Fija': 0.30,
                'Alternatives': 0.15,
                'Cash': 0.05
            },
            'ADC': {
                'Renta Variable': 0.55,
                'Renta Fija': 0.25,
                'Alternatives': 0.15,
                'Cash': 0.05
            },
            'Asesoría': {
                'Renta Variable': 0.60,
                'Renta Fija': 0.20,
                'Alternatives': 0.15,
                'Cash': 0.05
            },
            'TRA': {  # Discretionary Mandate
                'Renta Variable': 0.55,
                'Renta Fija': 0.25,
                'Alternatives': 0.15,
                'Cash': 0.05
            }
        }

        return defaults.get(service_type, {})

    def create_custom_allocation(self, client_rut: str, allocation_name: str,
                                allocations: Dict[str, float]) -> Tuple[bool, str]:
        """
        Create a custom allocation for a client

        Args:
            client_rut: Client RUT
            allocation_name: Name for this custom allocation
            allocations: Dict of {asset_class: allocation_percentage}

        Returns:
            Tuple (success: bool, message: str)
        """

        # Validate allocations sum to 1.0
        total = sum(allocations.values())
        if abs(total - 1.0) > 0.01:  # Allow 1% tolerance
            return False, f"Allocations must sum to 100%. Current total: {total * 100:.1f}%"

        # Validate all percentages are positive
        if any(v < 0 for v in allocations.values()):
            return False, "All allocations must be non-negative"

        # Save custom allocation
        self.custom_allocations[client_rut] = {
            'type': 'custom',
            'name': allocation_name,
            'allocations': allocations,
            'created_date': pd.Timestamp.now().isoformat()
        }

        self.save_custom_allocations()
        return True, f"Custom allocation saved for {client_rut}"

    def modify_allocation_parameter(self, client_rut: str, parameter: str,
                                   value: float) -> Tuple[bool, str]:
        """
        Quickly modify a specific parameter (e.g., USD percentage)

        Args:
            client_rut: Client RUT
            parameter: Parameter to modify (e.g., 'USD_percentage')
            value: New value (0-1)

        Returns:
            Tuple (success: bool, message: str)
        """

        if value < 0 or value > 1:
            return False, "Value must be between 0 and 1"

        if client_rut not in self.custom_allocations:
            # Create custom allocation from existing
            if client_rut in self.custom_allocations:
                self.custom_allocations[client_rut]['type'] = 'custom'
            else:
                self.custom_allocations[client_rut] = {
                    'type': 'custom',
                    'name': f'Modified - {client_rut}',
                    'allocations': {},
                    'parameters': {}
                }

        # Store parameter modification
        if 'parameters' not in self.custom_allocations[client_rut]:
            self.custom_allocations[client_rut]['parameters'] = {}

        self.custom_allocations[client_rut]['parameters'][parameter] = value
        self.save_custom_allocations()

        return True, f"Parameter '{parameter}' updated to {value * 100:.1f}%"

    def reset_to_default(self, client_rut: str) -> Tuple[bool, str]:
        """Reset client to default portfolio"""

        if client_rut in self.custom_allocations:
            del self.custom_allocations[client_rut]
            self.save_custom_allocations()
            return True, f"Reset {client_rut} to default portfolio"

        return False, f"No custom allocation found for {client_rut}"

    def get_all_custom_allocations(self) -> pd.DataFrame:
        """Get DataFrame of all custom allocations"""

        data = []
        for rut, allocation in self.custom_allocations.items():
            data.append({
                'Client RUT': rut,
                'Allocation Name': allocation.get('name', ''),
                'Type': allocation.get('type', ''),
                'Created': allocation.get('created_date', '')
            })

        if not data:
            return pd.DataFrame()

        return pd.DataFrame(data)

    def export_allocations(self, output_path: str = "data/custom_allocations_export.json"):
        """Export all custom allocations"""
        with open(output_path, 'w') as f:
            json.dump(self.custom_allocations, f, indent=2)
        return output_path


class PortfolioModelManager:
    """Manage portfolio models and their compositions"""

    def __init__(self, portfolio_models_df: pd.DataFrame = None):
        """
        Initialize with portfolio models

        Args:
            portfolio_models_df: DataFrame with columns:
                - Architecture
                - Risk_Profile
                - Asset_Class
                - Target_Allocation_%
        """
        self.models = portfolio_models_df or pd.DataFrame()
        self.architectures = []
        self.risk_profiles = []
        self.asset_classes = []

        if not self.models.empty:
            self.architectures = self.models['Architecture'].unique().tolist()
            self.risk_profiles = self.models['Risk_Profile'].unique().tolist()
            self.asset_classes = self.models['Asset_Class'].unique().tolist()

    def get_model_allocation(self, architecture: str, risk_profile: str) -> Dict[str, float]:
        """
        Get allocation for specific model

        Args:
            architecture: Architecture name (Conservative, Balanced, etc.)
            risk_profile: Risk profile name (Low, Medium, High, etc.)

        Returns:
            Dictionary of {asset_class: allocation}
        """

        filtered = self.models[
            (self.models['Architecture'] == architecture) &
            (self.models['Risk_Profile'] == risk_profile)
        ]

        if filtered.empty:
            return {}

        return dict(zip(filtered['Asset_Class'], filtered['Target_Allocation_%']))

    def get_available_models(self, service_type: str = None) -> List[Tuple[str, str]]:
        """
        Get available models

        Returns:
            List of (Architecture, Risk_Profile) tuples
        """

        models = []
        for arch in self.architectures:
            for risk in self.risk_profiles:
                models.append((arch, risk))

        return models

    def create_custom_model(self, name: str, allocations: Dict[str, float]) -> Dict:
        """
        Create a custom portfolio model

        Args:
            name: Name of custom model
            allocations: Dict of {asset_class: allocation}

        Returns:
            Custom model dictionary
        """

        # Validate
        total = sum(allocations.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Allocations must sum to 100%. Current: {total * 100:.1f}%")

        return {
            'name': name,
            'type': 'custom',
            'allocations': allocations,
            'created_date': pd.Timestamp.now().isoformat()
        }


if __name__ == "__main__":
    # Test PersonalPortfolioPersonalizer
    personalizer = PortfolioPersonalizer()

    # Test creating custom allocation
    custom_alloc = {
        'Renta Variable': 0.40,  # 40% stocks (no USD preference)
        'Renta Fija': 0.35,       # 35% bonds
        'Alternatives': 0.20,     # 20% alternatives
        'Cash': 0.05              # 5% cash
    }

    success, msg = personalizer.create_custom_allocation(
        'RUT_12345678',
        'Modified - Sin Dólares',
        custom_alloc
    )
    print(f"✅ {msg}" if success else f"❌ {msg}")

    # Test modifying parameter
    success, msg = personalizer.modify_allocation_parameter(
        'RUT_12345678',
        'USD_percentage',
        0.30
    )
    print(f"✅ {msg}" if success else f"❌ {msg}")

    print("\n📊 Custom Allocations Saved")
