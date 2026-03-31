"""Central signal state store for Signal Analyzer."""

from __future__ import annotations

from collections import OrderedDict

from PyQt6.QtCore import QObject, pyqtSignal

from .signal_model import SignalRecord


class SignalStore(QObject):
    """Single source of truth for all signal and ROI state."""

    signal_added = pyqtSignal(object)
    signal_removed = pyqtSignal(str)
    signal_updated = pyqtSignal(object)
    selection_changed = pyqtSignal(str)
    roi_changed = pyqtSignal(float, float)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._records: "OrderedDict[str, SignalRecord]" = OrderedDict()
        self._selected_id: str | None = None
        self._roi: tuple[float, float] | None = None

    def clear(self) -> None:
        """Remove all signals and reset store state."""
        for record_id in list(self._records.keys()):
            self.remove_signal(record_id)
        self._roi = None

    def add_signal(self, record: SignalRecord) -> None:
        """Add a new signal record and emit updates."""
        self._records[record.id] = record
        self.signal_added.emit(record)
        if self._selected_id is None:
            self.set_selected(record.id)

    def remove_signal(self, record_id: str) -> None:
        """Remove signal by id and emit updates."""
        if record_id not in self._records:
            return
        del self._records[record_id]
        self.signal_removed.emit(record_id)

        if self._selected_id == record_id:
            self._selected_id = next(iter(self._records.keys()), None)
            self.selection_changed.emit(self._selected_id or "")

    def update_signal(self, record: SignalRecord) -> None:
        """Replace an existing signal by id and emit updated signal."""
        if record.id not in self._records:
            self.add_signal(record)
            return
        self._records[record.id] = record
        self.signal_updated.emit(record)

    def set_selected(self, record_id: str | None) -> None:
        """Update selected signal id and emit change."""
        if record_id is not None and record_id not in self._records:
            return
        self._selected_id = record_id
        self.selection_changed.emit(record_id or "")

    def selected_id(self) -> str | None:
        """Return currently selected signal id."""
        return self._selected_id

    def selected_signal(self) -> SignalRecord | None:
        """Return selected signal record, if any."""
        if self._selected_id is None:
            return None
        return self._records.get(self._selected_id)

    def get_signal(self, record_id: str) -> SignalRecord | None:
        """Return a signal by id."""
        return self._records.get(record_id)

    def list_signals(self) -> list[SignalRecord]:
        """Return all records in insertion order."""
        return list(self._records.values())

    def visible_signals(self) -> list[SignalRecord]:
        """Return only visible records."""
        return [record for record in self._records.values() if record.visible]

    def set_roi(self, t_min: float, t_max: float) -> None:
        """Set global ROI and notify subscribers."""
        left = float(min(t_min, t_max))
        right = float(max(t_min, t_max))
        self._roi = (left, right)
        self.roi_changed.emit(left, right)

    def roi(self) -> tuple[float, float] | None:
        """Return current global ROI bounds in seconds."""
        return self._roi
