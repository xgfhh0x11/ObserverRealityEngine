"""
History - Measurement Log
Tracks all collapses and MW snapshots.
Time = number of measurements.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class HistoryEntry:
    """Single history entry"""
    timestamp: datetime
    mw_snapshot: Dict
    result: str
    measurement_number: int


class History:
    """
    History log of all measurements.
    
    Time is defined as: number_of_measurements
    Each entry represents one collapse event.
    """
    
    def __init__(self):
        self.entries: List[HistoryEntry] = []
    
    def append(self, mw_snapshot: Dict, result: str):
        """
        Append new measurement to history.
        
        Args:
            mw_snapshot: Snapshot from MW.snapshot()
            result: Collapsed result (SET identifier)
        """
        entry = HistoryEntry(
            timestamp=datetime.now(),
            mw_snapshot=mw_snapshot,
            result=result,
            measurement_number=len(self.entries)
        )
        self.entries.append(entry)
    
    def get_window(self, n: Optional[int] = None) -> 'History':
        """
        Get history window (for history_scope).
        
        Args:
            n: Number of recent entries (None = all)
        
        Returns:
            New History object with windowed entries
        """
        windowed = History()
        if n is None:
            windowed.entries = list(self.entries)
        else:
            windowed.entries = self.entries[-n:]
        return windowed
    
    def get_last_n(self, n: int) -> List[HistoryEntry]:
        """Get last N entries"""
        return self.entries[-n:] if n > 0 else []
    
    def get_all(self) -> List[HistoryEntry]:
        """Get all entries"""
        return list(self.entries)
    
    def get_time(self) -> int:
        """
        Get current time = number of measurements.
        """
        return len(self.entries)
    
    def __len__(self) -> int:
        """Time = number of measurements"""
        return len(self.entries)

