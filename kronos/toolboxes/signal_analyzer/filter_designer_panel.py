"""Filter Designer dock panel for Signal Analyzer."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from scipy import signal

from .preprocessing_engine import DesignedFilter, PreprocessingEngine
from .signal_store import SignalStore


@dataclass(slots=True)
class FilterRequest:
    """Payload emitted when a filter should be applied."""

    designed_filter: DesignedFilter
    zero_phase: bool


class FilterDesignerPanel(QWidget):
    """Designs and previews filters, then applies to selected signals."""

    apply_to_selected_requested = pyqtSignal(object)
    apply_to_visible_requested = pyqtSignal(object)

    def __init__(self, store: SignalStore, engine: PreprocessingEngine, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._engine = engine

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._render_preview)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        self._type_group = QGroupBox("Filter Type")
        type_form = QFormLayout(self._type_group)
        self.kind_combo = QComboBox()
        self.kind_combo.addItems(["lowpass", "highpass", "bandpass", "bandstop"])
        type_form.addRow("Kind", self.kind_combo)

        self._method_group = QGroupBox("Design Method")
        method_form = QFormLayout(self._method_group)
        self.method_combo = QComboBox()
        self.method_combo.addItems(["butterworth", "cheby1", "cheby2", "ellip", "fir-window"])
        method_form.addRow("Method", self.method_combo)

        self._params_group = QGroupBox("Parameters")
        params_form = QFormLayout(self._params_group)
        self.order_spin = QSpinBox()
        self.order_spin.setRange(1, 500)
        self.order_spin.setValue(4)

        self.fs_spin = QDoubleSpinBox()
        self.fs_spin.setRange(1.0, 1_000_000.0)
        self.fs_spin.setValue(1000.0)
        self.fs_spin.setDecimals(3)

        self.fc1_spin = QDoubleSpinBox()
        self.fc1_spin.setRange(0.01, 500_000.0)
        self.fc1_spin.setValue(100.0)

        self.fc2_spin = QDoubleSpinBox()
        self.fc2_spin.setRange(0.01, 500_000.0)
        self.fc2_spin.setValue(200.0)

        self.ripple_spin = QDoubleSpinBox()
        self.ripple_spin.setRange(0.01, 12.0)
        self.ripple_spin.setValue(1.0)

        self.atten_spin = QDoubleSpinBox()
        self.atten_spin.setRange(1.0, 120.0)
        self.atten_spin.setValue(40.0)

        self.window_combo = QComboBox()
        self.window_combo.addItems(["hann", "hamming", "blackman", "flattop", "kaiser", "rectangular"])

        self.zero_phase_check = QCheckBox("Zero-phase")
        self.zero_phase_check.setChecked(True)

        params_form.addRow("Order", self.order_spin)
        params_form.addRow("Fs", self.fs_spin)
        params_form.addRow("Fc1", self.fc1_spin)
        params_form.addRow("Fc2", self.fc2_spin)
        params_form.addRow("Ripple (dB)", self.ripple_spin)
        params_form.addRow("Attenuation (dB)", self.atten_spin)
        params_form.addRow("Window", self.window_combo)
        params_form.addRow("", self.zero_phase_check)

        self._preview_group = QGroupBox("Response Preview")
        preview_layout = QVBoxLayout(self._preview_group)
        self.figure = Figure(figsize=(3.0, 1.6), dpi=100)
        self.axes_mag = self.figure.add_subplot(211)
        self.axes_phase = self.figure.add_subplot(212)
        self.canvas = FigureCanvas(self.figure)
        preview_layout.addWidget(self.canvas)

        self._actions = QWidget()
        action_layout = QHBoxLayout(self._actions)
        self.design_btn = QPushButton("Design")
        self.apply_selected_btn = QPushButton("Apply Selected")
        self.apply_visible_btn = QPushButton("Apply Visible")
        action_layout.addWidget(self.design_btn)
        action_layout.addWidget(self.apply_selected_btn)
        action_layout.addWidget(self.apply_visible_btn)

        root.addWidget(self._type_group)
        root.addWidget(self._method_group)
        root.addWidget(self._params_group)
        root.addWidget(self._preview_group, 1)
        root.addWidget(self._actions)

        for widget in (
            self.kind_combo,
            self.method_combo,
            self.order_spin,
            self.fs_spin,
            self.fc1_spin,
            self.fc2_spin,
            self.ripple_spin,
            self.atten_spin,
            self.window_combo,
        ):
            if hasattr(widget, "currentIndexChanged"):
                widget.currentIndexChanged.connect(self._schedule_preview)
            if hasattr(widget, "valueChanged"):
                widget.valueChanged.connect(self._schedule_preview)

        self.design_btn.clicked.connect(self._render_preview)
        self.apply_selected_btn.clicked.connect(self._on_apply_selected)
        self.apply_visible_btn.clicked.connect(self._on_apply_visible)

        self._store.selection_changed.connect(self._sync_from_selection)
        self._sync_from_selection("")
        self._render_preview()

    def _schedule_preview(self, *_args) -> None:
        self._debounce.start()

    def _sync_from_selection(self, _signal_id: str) -> None:
        selected = self._store.selected_signal()
        if selected is None:
            return
        self.fs_spin.setValue(max(1.0, float(selected.fs)))

    def design_filter(self) -> DesignedFilter:
        """Design filter using current UI state."""
        return self._engine.design_filter(
            kind=self.kind_combo.currentText(),
            method=self.method_combo.currentText(),
            order=int(self.order_spin.value()),
            fs=float(self.fs_spin.value()),
            fc1=float(self.fc1_spin.value()),
            fc2=float(self.fc2_spin.value()),
            ripple_db=float(self.ripple_spin.value()),
            attenuation_db=float(self.atten_spin.value()),
            fir_window=self.window_combo.currentText(),
        )

    def _render_preview(self) -> None:
        filt = self.design_filter()
        w, h = signal.freqz(filt.b, filt.a, worN=512)

        self.axes_mag.clear()
        self.axes_phase.clear()
        self.axes_mag.plot(w / np.pi, 20.0 * np.log10(np.maximum(np.abs(h), 1e-10)), color="#4cc9f0", lw=1.2)
        self.axes_phase.plot(w / np.pi, np.unwrap(np.angle(h)), color="#f72585", lw=1.0)
        self.axes_mag.set_ylabel("Mag (dB)")
        self.axes_phase.set_ylabel("Phase")
        self.axes_phase.set_xlabel("Normalized Frequency")

        for ax in (self.axes_mag, self.axes_phase):
            ax.set_facecolor("#0d0d1a")
            ax.tick_params(colors="#a0a0b0", labelsize=7)
            for spine in ax.spines.values():
                spine.set_color("#2a2a4a")
            ax.grid(True, color="#1e1e3a", alpha=0.45, linestyle="--")

        self.figure.patch.set_facecolor("#0d0d1a")
        self.canvas.draw_idle()

    def _request(self) -> FilterRequest:
        return FilterRequest(
            designed_filter=self.design_filter(),
            zero_phase=bool(self.zero_phase_check.isChecked()),
        )

    def _on_apply_selected(self) -> None:
        self.apply_to_selected_requested.emit(self._request())

    def _on_apply_visible(self) -> None:
        self.apply_to_visible_requested.emit(self._request())
