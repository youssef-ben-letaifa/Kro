"""Measurements table widget for ROI statistics."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .preprocessing_engine import PreprocessingEngine
from .signal_store import SignalStore


class MeasurementsWidget(QWidget):
    """Bottom statistics panel that updates from store/ROI events."""

    def __init__(self, store: SignalStore, engine: PreprocessingEngine, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._engine = engine

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 2)
        header_layout.addWidget(QLabel("Measurements"))
        header_layout.addStretch(1)

        self._export_btn = QPushButton("Export CSV")
        self._export_btn.clicked.connect(self._export_csv)
        header_layout.addWidget(self._export_btn)

        self.table = QTableWidget(0, 12)
        self.table.setHorizontalHeaderLabels(
            [
                "Name",
                "ROI-Min(s)",
                "ROI-Max(s)",
                "Min",
                "Max",
                "Mean",
                "RMS",
                "Peak-to-Peak",
                "THD(%)",
                "SNR(dB)",
                "SINAD(dB)",
                "SFDR(dB)",
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)

        root.addWidget(header)
        root.addWidget(self.table, 1)

        self._store.signal_added.connect(lambda _rec: self.refresh())
        self._store.signal_removed.connect(lambda _sid: self.refresh())
        self._store.signal_updated.connect(lambda _rec: self.refresh())
        self._store.roi_changed.connect(lambda _a, _b: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        """Recompute and display current measurements."""
        roi = self._store.roi()
        visible = self._store.visible_signals()

        self.table.setRowCount(len(visible))
        for row, record in enumerate(visible):
            m = self._engine.compute_measurements(record.data, record.fs, roi=roi)
            roi_min = roi[0] if roi else record.start_time
            roi_max = roi[1] if roi else record.end_time

            values = [
                record.name,
                f"{roi_min:.4g}",
                f"{roi_max:.4g}",
                f"{m.min_value:.6g}",
                f"{m.max_value:.6g}",
                f"{m.mean:.6g}",
                f"{m.rms:.6g}",
                f"{m.peak_to_peak:.6g}",
                f"{m.thd:.4g}",
                f"{m.snr:.4g}",
                f"{m.sinad:.4g}",
                f"{m.sfdr:.4g}",
            ]

            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, col, item)

    def _export_csv(self) -> None:
        """Export current table values to clipboard-friendly CSV text."""
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        lines = [",".join(headers)]
        for row in range(self.table.rowCount()):
            values = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                values.append(item.text() if item is not None else "")
            lines.append(",".join(values))

        text = "\n".join(lines)
        QApplication.clipboard().setText(text)
