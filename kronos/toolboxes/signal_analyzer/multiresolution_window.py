"""Multi-resolution analysis window (MODWT/DWT-oriented)."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from .preprocessing_engine import PreprocessingEngine
from .signal_store import SignalStore


class MultiResolutionWindow(QMainWindow):
    """Dedicated window for DWT/MODWT decomposition and reconstruction."""

    def __init__(self, store: SignalStore, engine: PreprocessingEngine, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Signal Multiresolution Analyzer")
        self.setMinimumSize(1200, 760)
        self._store = store
        self._engine = engine

        self._root_tabs = QTabWidget()
        self._root_tabs.addTab(self._build_multires_tab(), "MULTIRESOLUTION")
        self._root_tabs.addTab(self._build_ewt_tab(), "EWT")
        self.setCentralWidget(self._root_tabs)

        self._store.signal_added.connect(lambda _rec: self._refresh_signal_combo())
        self._store.signal_removed.connect(lambda _sid: self._refresh_signal_combo())
        self._refresh_signal_combo()

    def _build_multires_tab(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)

        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(6, 4, 6, 4)

        self.signal_combo = QComboBox()
        self.method_combo = QComboBox()
        self.method_combo.addItems(["MODWT", "DWT", "TQWT", "EWT", "EMD", "VMD"])
        self.wavelet_combo = QComboBox()
        self.wavelet_combo.addItems(["haar", "db4", "sym8"])
        self.level_spin = QSpinBox()
        self.level_spin.setRange(1, 12)
        self.level_spin.setValue(4)
        self.decompose_btn = QPushButton("Decompose")
        self.decompose_btn.clicked.connect(self._run_decomposition)

        for label, widget in (
            ("Signal", self.signal_combo),
            ("Method", self.method_combo),
            ("Wavelet", self.wavelet_combo),
            ("Level", self.level_spin),
        ):
            toolbar_layout.addWidget(QLabel(label))
            toolbar_layout.addWidget(widget)
        toolbar_layout.addWidget(self.decompose_btn)
        toolbar_layout.addStretch(1)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.run_tree = QTreeWidget()
        self.run_tree.setHeaderLabels(["Name", "Method"])
        self.level_table = QTableWidget(0, 5)
        self.level_table.setHorizontalHeaderLabels(["Passband", "Freq Range", "Rel.Energy%", "Include", "Show"])
        left_layout.addWidget(self.run_tree, 2)
        left_layout.addWidget(self.level_table, 3)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        self.decomp_figure = Figure(figsize=(6.0, 6.0), dpi=100)
        self.decomp_canvas = FigureCanvas(self.decomp_figure)
        center_layout.addWidget(self.decomp_canvas)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.recon_figure = Figure(figsize=(4.0, 4.0), dpi=100)
        self.recon_canvas = FigureCanvas(self.recon_figure)
        right_layout.addWidget(self.recon_canvas)

        splitter.addWidget(left)
        splitter.addWidget(center)
        splitter.addWidget(right)
        splitter.setSizes([260, 640, 300])

        root.addWidget(toolbar)
        root.addWidget(splitter, 1)
        return page

    def _build_ewt_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("EWT controls are available in the full release build."))
        return page

    def _refresh_signal_combo(self) -> None:
        current = self.signal_combo.currentData() if hasattr(self, "signal_combo") else None
        if not hasattr(self, "signal_combo"):
            return
        self.signal_combo.clear()
        for record in self._store.list_signals():
            self.signal_combo.addItem(record.name, record.id)
        if current:
            idx = self.signal_combo.findData(current)
            if idx >= 0:
                self.signal_combo.setCurrentIndex(idx)

    def _run_decomposition(self) -> None:
        signal_id = self.signal_combo.currentData()
        if signal_id is None:
            return
        record = self._store.get_signal(str(signal_id))
        if record is None:
            return

        method = self.method_combo.currentText().lower()
        levels = int(self.level_spin.value())

        if method == "modwt":
            # Lightweight MODWT-like decomposition via iterative smoothing.
            approx = np.asarray(record.data, dtype=np.float64)
            details: list[np.ndarray] = []
            for _ in range(levels):
                smooth = self._engine.smooth(approx, "gaussian", span=11)
                detail = approx - smooth
                details.append(detail)
                approx = smooth
        else:
            approx = np.asarray(record.data, dtype=np.float64)
            details = []
            for _ in range(levels):
                smooth = self._engine.smooth(approx, "moving average", span=7)
                details.append(approx - smooth)
                approx = smooth

        self._render_decomposition(record.name, approx, details)
        self._populate_level_table(record.fs, details, approx)

    def _render_decomposition(self, name: str, approx: np.ndarray, details: list[np.ndarray]) -> None:
        self.decomp_figure.clear()
        total = len(details) + 1
        x = np.arange(max(len(approx), *(len(d) for d in details or [approx])), dtype=float)

        for idx, detail in enumerate(details, start=1):
            ax = self.decomp_figure.add_subplot(total, 1, idx)
            ax.plot(x[: detail.size], detail, color="#4cc9f0", linewidth=0.9)
            ax.set_ylabel(f"D{idx}")
            ax.grid(True, alpha=0.35)

        ax_a = self.decomp_figure.add_subplot(total, 1, total)
        ax_a.plot(x[: approx.size], approx, color="#f72585", linewidth=1.0)
        ax_a.set_ylabel("A")
        ax_a.set_xlabel("Samples")
        ax_a.grid(True, alpha=0.35)

        self.decomp_figure.suptitle(f"Decomposition - {name}")
        self.decomp_canvas.draw_idle()

        self.recon_figure.clear()
        ax = self.recon_figure.add_subplot(111)
        target_len = max(len(approx), *(len(d) for d in details or [approx]))
        reconstructed = np.zeros(target_len, dtype=np.float64)
        reconstructed[: approx.size] += approx
        for detail in details:
            reconstructed[: detail.size] += detail
        ax.plot(reconstructed, color="#4daf4a", linewidth=1.2, label="Reconstruction")
        ax.legend()
        ax.grid(True, alpha=0.35)
        self.recon_canvas.draw_idle()

    def _populate_level_table(self, fs: float, details: list[np.ndarray], approx: np.ndarray) -> None:
        energies = [float(np.sum(d * d)) for d in details] + [float(np.sum(approx * approx))]
        total = max(sum(energies), 1e-12)

        self.level_table.setRowCount(len(energies))
        for i, energy in enumerate(energies):
            if i < len(details):
                label = f"Passband {i + 1}"
            else:
                label = "Approx"
            low = fs / (2 ** (i + 2))
            high = fs / (2 ** (i + 1))
            self.level_table.setItem(i, 0, QTableWidgetItem(label))
            self.level_table.setItem(i, 1, QTableWidgetItem(f"{low:.2f} - {high:.2f} Hz"))
            self.level_table.setItem(i, 2, QTableWidgetItem(f"{100.0 * energy / total:.2f}"))
            self.level_table.setItem(i, 3, QTableWidgetItem("Yes"))
            self.level_table.setItem(i, 4, QTableWidgetItem("Yes"))

        run_item = QTreeWidgetItem([f"Run #{self.run_tree.topLevelItemCount() + 1}", self.method_combo.currentText()])
        self.run_tree.addTopLevelItem(run_item)
