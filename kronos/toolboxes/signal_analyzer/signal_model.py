"""Signal data model types for Signal Analyzer."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

import numpy as np
from PyQt6.QtGui import QColor


DEFAULT_SIGNAL_COLORS: tuple[str, ...] = (
    "#89b4fa",
    "#cba6f7",
    "#f5c2e7",
    "#74c7ec",
    "#a6e3a1",
    "#fab387",
    "#f9e2af",
    "#b4befe",
)


@dataclass(slots=True)
class SignalRecord:
    """Represents one signal in the analyzer session."""

    id: str
    name: str
    data: np.ndarray
    fs: float
    unit: str = ""
    start_time: float = 0.0
    source: str = "derived"
    parent_id: str | None = None
    color: QColor = field(default_factory=lambda: QColor(DEFAULT_SIGNAL_COLORS[0]))
    visible: bool = True
    preprocessing_log: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        name: str,
        data: np.ndarray,
        fs: float,
        *,
        unit: str = "",
        start_time: float = 0.0,
        source: str = "derived",
        parent_id: str | None = None,
        color: QColor | None = None,
    ) -> "SignalRecord":
        """Build a normalized signal record with generated UUID."""
        array = np.asarray(data, dtype=np.float64).reshape(-1)
        return cls(
            id=str(uuid4()),
            name=name,
            data=array,
            fs=float(fs),
            unit=unit,
            start_time=float(start_time),
            source=source,
            parent_id=parent_id,
            color=color if color is not None else QColor(DEFAULT_SIGNAL_COLORS[0]),
        )

    @property
    def duration(self) -> float:
        """Return duration in seconds for this record."""
        if self.fs <= 0.0:
            return 0.0
        return float(self.data.size) / self.fs

    @property
    def end_time(self) -> float:
        """Return absolute end time in seconds."""
        return self.start_time + self.duration

    def copy_with(
        self,
        *,
        name: str | None = None,
        data: np.ndarray | None = None,
        parent_id: str | None = None,
        source: str | None = None,
        append_log: str | None = None,
    ) -> "SignalRecord":
        """Return a derived signal with updated metadata and new UUID."""
        next_record = SignalRecord.create(
            name=name or self.name,
            data=self.data if data is None else np.asarray(data, dtype=np.float64),
            fs=self.fs,
            unit=self.unit,
            start_time=self.start_time,
            source=source or "derived",
            parent_id=parent_id if parent_id is not None else self.id,
            color=QColor(self.color),
        )
        next_record.visible = self.visible
        next_record.preprocessing_log = list(self.preprocessing_log)
        if append_log:
            next_record.preprocessing_log.append(append_log)
        return next_record
