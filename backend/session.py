"""
Session management for Quadratic AI.
Stores uploaded DataFrames in memory, keyed by sheet_id.
"""

import pandas as pd
import uuid
from typing import Dict, Optional


class SessionStore:
    """Simple in-memory store for uploaded spreadsheets."""

    def __init__(self):
        self._sheets: Dict[str, pd.DataFrame] = {}
        self._filenames: Dict[str, str] = {}

    def add_sheet(self, df: pd.DataFrame, filename: str) -> str:
        """Store a DataFrame and return its unique sheet_id."""
        sheet_id = str(uuid.uuid4())[:8]
        self._sheets[sheet_id] = df
        self._filenames[sheet_id] = filename
        return sheet_id

    def get_sheet(self, sheet_id: str) -> Optional[pd.DataFrame]:
        """Retrieve a DataFrame by sheet_id."""
        return self._sheets.get(sheet_id)

    def update_sheet(self, sheet_id: str, df: pd.DataFrame):
        """Update an existing DataFrame."""
        if sheet_id in self._sheets:
            self._sheets[sheet_id] = df

    def get_filename(self, sheet_id: str) -> Optional[str]:
        """Get the original filename for a sheet."""
        return self._filenames.get(sheet_id)

    def list_sheets(self) -> Dict[str, str]:
        """Return mapping of sheet_id -> filename."""
        return dict(self._filenames)

    def delete_sheet(self, sheet_id: str):
        """Remove a sheet from the store."""
        self._sheets.pop(sheet_id, None)
        self._filenames.pop(sheet_id, None)


# Global singleton
store = SessionStore()
