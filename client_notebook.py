"""
Client Notebook System
Shared notes and comments for client management
Allows advisors to document client situations, changes, and decisions
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import pandas as pd


class ClientNotebook:
    """Manage client notes and documentation"""

    def __init__(self, notebook_path: str = "data/client_notebook.json"):
        self.notebook_path = Path(notebook_path)
        self.notebook = self._load_notebook()

    def _load_notebook(self) -> Dict:
        """Load notebook from file"""
        if self.notebook_path.exists():
            with open(self.notebook_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_notebook(self):
        """Save notebook to file"""
        self.notebook_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.notebook_path, 'w', encoding='utf-8') as f:
            json.dump(self.notebook, f, indent=2, ensure_ascii=False)

    def add_note(self, client_rut: str, client_name: str, note_text: str,
                 advisor_name: str = "System") -> tuple[bool, str]:
        """
        Add a note to client notebook

        Args:
            client_rut: Client RUT
            client_name: Client name
            note_text: Note content
            advisor_name: Name of advisor adding note (optional, for reference)

        Returns:
            Tuple (success: bool, message: str)
        """

        if not note_text.strip():
            return False, "Note cannot be empty"

        if client_rut not in self.notebook:
            self.notebook[client_rut] = {
                'client_name': client_name,
                'notes': []
            }

        note_entry = {
            'timestamp': datetime.now().isoformat(),
            'advisor': advisor_name,
            'text': note_text.strip()
        }

        self.notebook[client_rut]['notes'].append(note_entry)
        self._save_notebook()

        return True, f"Note added for {client_name}"

    def get_client_notes(self, client_rut: str) -> List[Dict]:
        """
        Get all notes for a client

        Args:
            client_rut: Client RUT

        Returns:
            List of note entries (most recent first)
        """

        if client_rut not in self.notebook:
            return []

        notes = self.notebook[client_rut]['notes']
        return sorted(notes, key=lambda x: x['timestamp'], reverse=True)

    def get_client_notebook_df(self, client_rut: str) -> pd.DataFrame:
        """
        Get client notes as DataFrame for display

        Args:
            client_rut: Client RUT

        Returns:
            DataFrame with columns: Fecha, Asesor, Nota
        """

        notes = self.get_client_notes(client_rut)
        if not notes:
            return pd.DataFrame()

        data = []
        for note in notes:
            data.append({
                'Fecha': datetime.fromisoformat(note['timestamp']).strftime('%Y-%m-%d %H:%M'),
                'Asesor': note['advisor'],
                'Nota': note['text']
            })

        return pd.DataFrame(data)

    def edit_note(self, client_rut: str, note_index: int, new_text: str) -> tuple[bool, str]:
        """
        Edit an existing note

        Args:
            client_rut: Client RUT
            note_index: Index of note to edit (0 = most recent)
            new_text: New note text

        Returns:
            Tuple (success: bool, message: str)
        """

        if client_rut not in self.notebook:
            return False, "Client not found"

        notes = self.notebook[client_rut]['notes']
        if note_index >= len(notes):
            return False, "Note index out of range"

        # Notes are stored in order added, but displayed reversed
        # So we need to adjust the index
        actual_index = len(notes) - 1 - note_index

        if actual_index < 0:
            return False, "Invalid note index"

        notes[actual_index]['text'] = new_text.strip()
        notes[actual_index]['edited'] = datetime.now().isoformat()

        self._save_notebook()
        return True, "Note updated"

    def delete_note(self, client_rut: str, note_index: int) -> tuple[bool, str]:
        """
        Delete a note

        Args:
            client_rut: Client RUT
            note_index: Index of note to delete (0 = most recent)

        Returns:
            Tuple (success: bool, message: str)
        """

        if client_rut not in self.notebook:
            return False, "Client not found"

        notes = self.notebook[client_rut]['notes']
        if note_index >= len(notes):
            return False, "Note index out of range"

        actual_index = len(notes) - 1 - note_index

        if actual_index < 0:
            return False, "Invalid note index"

        removed_note = notes.pop(actual_index)
        self._save_notebook()

        return True, f"Note deleted"

    def get_all_clients_with_notes(self) -> List[str]:
        """Get list of all clients with notes"""
        return list(self.notebook.keys())

    def export_notebook(self, output_path: str = "data/client_notebook_export.json"):
        """Export entire notebook to file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.notebook, f, indent=2, ensure_ascii=False)
        return output_path

    def get_notebook_summary(self) -> Dict:
        """Get summary statistics of notebook"""
        total_clients = len(self.notebook)
        total_notes = sum(len(client['notes']) for client in self.notebook.values())

        return {
            'total_clients': total_clients,
            'total_notes': total_notes,
            'avg_notes_per_client': total_notes / total_clients if total_clients > 0 else 0
        }


if __name__ == "__main__":
    # Test
    notebook = ClientNotebook()

    # Add test notes
    notebook.add_note(
        "RUT_12345678",
        "Cliente Prueba",
        "Cliente quiere cambiar a arquitectura defensiva en dólares",
        "Advisor Test"
    )

    notebook.add_note(
        "RUT_12345678",
        "Cliente Prueba",
        "Confirmó cambio. Ahora 80% defensiva dólares, 20% manual pesos",
        "Advisor Test"
    )

    # Get notes
    notes = notebook.get_client_notes("RUT_12345678")
    print(f"\n✅ Notas guardadas: {len(notes)}")
    for note in notes:
        print(f"  - {note['timestamp']}: {note['text']}")

    # Summary
    summary = notebook.get_notebook_summary()
    print(f"\n📊 Resumen: {summary}")
