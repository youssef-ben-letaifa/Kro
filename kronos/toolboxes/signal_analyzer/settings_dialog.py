"""Preferences dialog for Signal Analyzer."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
)


@dataclass(slots=True)
class AnalyzerSettings:
    """In-memory settings for Signal Analyzer behavior."""

    significant_digits: int = 6
    workspace_auto_refresh: bool = True
    workspace_refresh_interval_ms: int = 2000


class SettingsDialog(QDialog):
    """Modal dialog to update analyzer preferences."""

    def __init__(self, settings: AnalyzerSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Signal Analyzer Preferences")
        self.setMinimumWidth(420)
        self._settings = settings

        root = QVBoxLayout(self)
        form = QFormLayout()

        self.digits_spin = QSpinBox()
        self.digits_spin.setRange(2, 12)
        self.digits_spin.setValue(settings.significant_digits)

        self.refresh_check = QCheckBox("Auto-refresh workspace browser")
        self.refresh_check.setChecked(settings.workspace_auto_refresh)

        self.refresh_interval_spin = QSpinBox()
        self.refresh_interval_spin.setRange(250, 10_000)
        self.refresh_interval_spin.setSingleStep(250)
        self.refresh_interval_spin.setValue(settings.workspace_refresh_interval_ms)

        form.addRow("Significant Digits", self.digits_spin)
        form.addRow("", self.refresh_check)
        form.addRow("Workspace Refresh (ms)", self.refresh_interval_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        root.addLayout(form)
        root.addWidget(buttons)

    def values(self) -> AnalyzerSettings:
        """Return new settings value object from dialog controls."""
        return AnalyzerSettings(
            significant_digits=int(self.digits_spin.value()),
            workspace_auto_refresh=bool(self.refresh_check.isChecked()),
            workspace_refresh_interval_ms=int(self.refresh_interval_spin.value()),
        )
