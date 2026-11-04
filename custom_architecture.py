# OBSOLETO (2026-10-27): Sistema antiguo de arquitecturas personalizadas por cliente (JSON suelto). Lo reemplaza `wm/portafolio_cliente.py` (portafolios por cliente con versiones en PostgreSQL, pestaña «Portafolio» de la ficha).
# Solo lo usan `app_v3.py` y los respaldos `app_v4_final_backup_*.py`; se puede borrar cuando esos archivos ya no hagan falta.
"""
Custom Architecture System
Allows advisors to create personalized portfolio allocations per client
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import pandas as pd


class CustomArchitecture:
    """Manage custom architecture allocations per client"""

    def __init__(self, custom_arch_path: str = "data/custom_architectures.json"):
        self.custom_arch_path = Path(custom_arch_path)
        self.custom_archs = self._load_architectures()

    def _load_architectures(self) -> Dict:
        """Load custom architectures from file"""
        if self.custom_arch_path.exists():
            with open(self.custom_arch_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_architectures(self):
        """Save custom architectures to file"""
        self.custom_arch_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.custom_arch_path, 'w', encoding='utf-8') as f:
            json.dump(self.custom_archs, f, indent=2, ensure_ascii=False)

    def create_custom_architecture(self, client_rut: str, architecture_name: str,
                                  instruments_weights: Dict[str, float]) -> tuple[bool, str]:
        """
        Create custom architecture for a client

        Args:
            client_rut: Client RUT
            architecture_name: Name of custom architecture (e.g., "Defensiva Dólares 80% - Pesos 20%")
            instruments_weights: Dict {instrument_name: weight (0-1)}

        Returns:
            Tuple (success: bool, message: str)
        """

        # Validate weights sum to 1.0
        total_weight = sum(instruments_weights.values())
        if abs(total_weight - 1.0) > 0.01:
            return False, f"Pesos deben sumar 100%. Total actual: {total_weight * 100:.1f}%"

        # Validate all weights are positive
        if any(w < 0 for w in instruments_weights.values()):
            return False, "Todos los pesos deben ser no-negativos"

        if client_rut not in self.custom_archs:
            self.custom_archs[client_rut] = {'architectures': []}

        # Add new architecture
        arch_entry = {
            'name': architecture_name,
            'type': 'custom',
            'instruments': instruments_weights,
            'created_date': datetime.now().isoformat(),
            'is_active': True
        }

        self.custom_archs[client_rut]['architectures'].append(arch_entry)
        self._save_architectures()

        return True, f"Arquitectura personalizada creada: {architecture_name}"

    def update_custom_architecture(self, client_rut: str, architecture_name: str,
                                  instruments_weights: Dict[str, float]) -> tuple[bool, str]:
        """
        Update existing custom architecture

        Args:
            client_rut: Client RUT
            architecture_name: Name of architecture to update
            instruments_weights: New weights

        Returns:
            Tuple (success: bool, message: str)
        """

        if client_rut not in self.custom_archs:
            return False, "Cliente no encontrado"

        # Find architecture
        arch_idx = None
        for i, arch in enumerate(self.custom_archs[client_rut]['architectures']):
            if arch['name'] == architecture_name:
                arch_idx = i
                break

        if arch_idx is None:
            return False, f"Arquitectura '{architecture_name}' no encontrada"

        # Validate weights
        total_weight = sum(instruments_weights.values())
        if abs(total_weight - 1.0) > 0.01:
            return False, f"Pesos deben sumar 100%. Total actual: {total_weight * 100:.1f}%"

        # Update
        self.custom_archs[client_rut]['architectures'][arch_idx]['instruments'] = instruments_weights
        self.custom_archs[client_rut]['architectures'][arch_idx]['modified_date'] = datetime.now().isoformat()

        self._save_architectures()

        return True, f"Arquitectura actualizada: {architecture_name}"

    def get_client_custom_architectures(self, client_rut: str) -> List[Dict]:
        """
        Get all custom architectures for a client

        Args:
            client_rut: Client RUT

        Returns:
            List of architecture definitions
        """

        if client_rut not in self.custom_archs:
            return []

        return self.custom_archs[client_rut]['architectures']

    def get_active_custom_architecture(self, client_rut: str) -> Dict:
        """
        Get currently active custom architecture for client

        Args:
            client_rut: Client RUT

        Returns:
            Active architecture dict or empty dict
        """

        archs = self.get_client_custom_architectures(client_rut)

        for arch in archs:
            if arch.get('is_active', False):
                return arch

        return {}

    def set_active_architecture(self, client_rut: str, architecture_name: str) -> tuple[bool, str]:
        """
        Set which architecture is active for client

        Args:
            client_rut: Client RUT
            architecture_name: Name of architecture to activate

        Returns:
            Tuple (success: bool, message: str)
        """

        if client_rut not in self.custom_archs:
            return False, "Cliente no encontrado"

        # Deactivate all, activate one
        found = False
        for arch in self.custom_archs[client_rut]['architectures']:
            if arch['name'] == architecture_name:
                arch['is_active'] = True
                found = True
            else:
                arch['is_active'] = False

        if not found:
            return False, f"Arquitectura '{architecture_name}' no encontrada"

        self._save_architectures()

        return True, f"Arquitectura activada: {architecture_name}"

    def delete_custom_architecture(self, client_rut: str, architecture_name: str) -> tuple[bool, str]:
        """
        Delete custom architecture

        Args:
            client_rut: Client RUT
            architecture_name: Name of architecture to delete

        Returns:
            Tuple (success: bool, message: str)
        """

        if client_rut not in self.custom_archs:
            return False, "Cliente no encontrado"

        initial_count = len(self.custom_archs[client_rut]['architectures'])

        self.custom_archs[client_rut]['architectures'] = [
            arch for arch in self.custom_archs[client_rut]['architectures']
            if arch['name'] != architecture_name
        ]

        if len(self.custom_archs[client_rut]['architectures']) == initial_count:
            return False, f"Arquitectura '{architecture_name}' no encontrada"

        self._save_architectures()

        return True, f"Arquitectura eliminada: {architecture_name}"

    def get_architectures_dataframe(self, client_rut: str) -> pd.DataFrame:
        """
        Get client's architectures as DataFrame

        Args:
            client_rut: Client RUT

        Returns:
            DataFrame with architecture info
        """

        archs = self.get_client_custom_architectures(client_rut)

        if not archs:
            return pd.DataFrame()

        data = []
        for arch in archs:
            data.append({
                'Nombre': arch['name'],
                'Tipo': arch['type'],
                'Activa': '✓' if arch.get('is_active', False) else '',
                'Instrumentos': len(arch['instruments']),
                'Creada': datetime.fromisoformat(arch['created_date']).strftime('%Y-%m-%d %H:%M')
            })

        return pd.DataFrame(data)

    def export_architectures(self, output_path: str = "data/custom_architectures_export.json"):
        """Export all custom architectures"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.custom_archs, f, indent=2, ensure_ascii=False)
        return output_path


if __name__ == "__main__":
    # Test
    ca = CustomArchitecture()

    # Create custom architectures
    defensiva_dolares = {
        'Fondo Scotia Defensivo USD': 0.40,
        'Fondo Balanceado USD': 0.30,
        'Fondo Dinámico USD': 0.20,
        'Cash USD': 0.10
    }

    success, msg = ca.create_custom_architecture(
        'RUT_12345678',
        'Defensiva Dólares 80% - Pesos 20%',
        defensiva_dolares
    )

    print(f"✅ {msg}" if success else f"❌ {msg}")

    # Get architectures
    archs = ca.get_client_custom_architectures('RUT_12345678')
    print(f"\n📋 Arquitecturas guardadas: {len(archs)}")
    for arch in archs:
        print(f"  - {arch['name']}")
