"""Dialog for editing block parameters."""

from __future__ import annotations

import ast
import json

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from kronos.ui.center.simulink.block_registry import get_block_def, resolve_type


class BlockParamDialog(QDialog):
    """Modal dialog for block parameter editing."""

    def __init__(self, block_type: str, params: dict, parent=None) -> None:
        super().__init__(parent)
        self.block_type = resolve_type(block_type)
        self.params = dict(params)
        self.setWindowTitle(f"Edit: {self.block_type}")
        self.setMinimumWidth(380)
        self.setStyleSheet("QDialog { background: #0e1117; }")
        self._widgets: dict[str, object] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel(self.windowTitle())
        title.setStyleSheet("color: #c8ccd4; font-weight: bold;")
        layout.addWidget(title)

        # Description
        bdef = get_block_def(self.block_type)
        if bdef and bdef.description:
            desc = QLabel(bdef.description)
            desc.setStyleSheet("color: #6a7280; font-size: 10px; padding-bottom: 6px;")
            layout.addWidget(desc)

        form = QFormLayout()
        layout.addLayout(form)

        bt = self.block_type

        # ─── Sources ──────────────────────────────────────────────
        if bt == "Step":
            self._add_spin(form, "amplitude", "Amplitude", 0.0, 1000.0, 0.1)
            self._add_spin(form, "step_time", "Step Time", 0.0, 1000.0, 0.1)
            self._add_spin(form, "initial", "Initial Value", -1000.0, 1000.0, 0.1)

        elif bt == "Ramp":
            self._add_spin(form, "slope", "Slope", -1000.0, 1000.0, 0.1)

        elif bt in {"Sine Wave", "Sine"}:
            self._add_spin(form, "amplitude", "Amplitude", 0.0, 1000.0, 0.1)
            self._add_spin(form, "frequency", "Frequency (Hz)", 0.0, 10000.0, 0.1)
            self._add_spin(form, "phase", "Phase (rad)", -360.0, 360.0, 0.1)
            self._add_spin(form, "bias", "Bias", -1000.0, 1000.0, 0.1)

        elif bt == "Constant":
            self._add_spin(form, "value", "Value", -1000.0, 1000.0, 0.1)

        elif bt == "Clock":
            pass  # No params

        elif bt == "Digital Clock":
            self._add_spin(form, "sample_time", "Sample Time", 0.001, 100.0, 0.01)

        elif bt == "Pulse Generator":
            self._add_spin(form, "amplitude", "Amplitude", 0.0, 1000.0, 0.1)
            self._add_spin(form, "period", "Period (s)", 0.001, 1000.0, 0.1)
            self._add_spin(form, "duty_cycle", "Duty Cycle (%)", 0.0, 100.0, 1.0)
            self._add_spin(form, "phase_delay", "Phase Delay (s)", 0.0, 1000.0, 0.1)

        elif bt == "Signal Generator":
            combo = QComboBox()
            combo.addItems(["sine", "square", "sawtooth", "random"])
            combo.setCurrentText(str(self.params.get("wave_form", "sine")))
            form.addRow("Waveform:", combo)
            self._widgets["wave_form"] = combo
            self._add_spin(form, "amplitude", "Amplitude", 0.0, 1000.0, 0.1)
            self._add_spin(form, "frequency", "Frequency (Hz)", 0.0, 10000.0, 0.1)

        elif bt == "Chirp Signal":
            self._add_spin(form, "f0", "Start Frequency", 0.0, 10000.0, 0.1)
            self._add_spin(form, "f1", "End Frequency", 0.0, 10000.0, 0.1)
            self._add_spin(form, "target_time", "Target Time", 0.0, 10000.0, 0.1)

        elif bt == "Band-Limited White Noise":
            self._add_spin(form, "noise_power", "Noise Power", 0.0, 100.0, 0.01)
            self._add_spin(form, "sample_time", "Sample Time", 0.001, 1.0, 0.001)
            self._add_int_spin(form, "seed", "Seed", 0, 99999)

        elif bt in {"Random Number", "Uniform Random Number"}:
            if bt == "Random Number":
                self._add_spin(form, "mean", "Mean", -1000.0, 1000.0, 0.1)
                self._add_spin(form, "variance", "Variance", 0.0, 1000.0, 0.1)
            else:
                self._add_spin(form, "minimum", "Minimum", -1000.0, 1000.0, 0.1)
                self._add_spin(form, "maximum", "Maximum", -1000.0, 1000.0, 0.1)
            self._add_int_spin(form, "seed", "Seed", 0, 99999)

        elif bt == "Repeating Sequence":
            self._add_line(form, "time_values", "Time Values")
            self._add_line(form, "output_values", "Output Values")

        # ─── Math ─────────────────────────────────────────────────
        elif bt == "Gain":
            self._add_spin(form, "gain", "Gain (K)", -10000.0, 10000.0, 0.1)

        elif bt in {"Sum", "Subtract"}:
            self._add_line(form, "signs", "Signs (e.g. +-)")

        elif bt in {"Math Function", "Trigonometric Function", "Rounding Function"}:
            combo = QComboBox()
            if bt == "Math Function":
                combo.addItems(["exp", "log", "log10", "sqrt", "square", "abs", "reciprocal"])
            elif bt == "Trigonometric Function":
                combo.addItems(["sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh"])
            else:
                combo.addItems(["round", "floor", "ceil", "fix"])
            combo.setCurrentText(str(self.params.get("function", combo.itemText(0))))
            form.addRow("Function:", combo)
            self._widgets["function"] = combo

        elif bt == "MinMax":
            combo = QComboBox()
            combo.addItems(["min", "max"])
            combo.setCurrentText(str(self.params.get("function", "min")))
            form.addRow("Function:", combo)
            self._widgets["function"] = combo

        elif bt == "Bias":
            self._add_spin(form, "bias", "Bias", -10000.0, 10000.0, 0.1)

        elif bt == "Slider Gain":
            self._add_spin(form, "gain", "Gain", -10000.0, 10000.0, 0.1)
            self._add_spin(form, "min", "Min", -10000.0, 10000.0, 0.1)
            self._add_spin(form, "max", "Max", -10000.0, 10000.0, 0.1)

        # ─── Continuous ───────────────────────────────────────────
        elif bt in {"Transfer Fcn", "TransferFunction"}:
            self._add_line(form, "numerator", "Numerator")
            self._add_line(form, "denominator", "Denominator")
            combo = QComboBox()
            combo.addItems(["s", "z"])
            form.addRow("Variable:", combo)
            self._widgets["variable"] = combo

        elif bt in {"PID Controller", "PID"}:
            self._add_spin(form, "Kp", "Kp", 0.001, 10000.0, 0.1)
            self._add_spin(form, "Ki", "Ki", 0.0, 10000.0, 0.01)
            self._add_spin(form, "Kd", "Kd", 0.0, 10000.0, 0.01)

        elif bt in {"State-Space", "StateSpace"}:
            self._add_text(form, "A", "A Matrix")
            self._add_text(form, "B", "B Matrix")
            self._add_text(form, "C", "C Matrix")
            self._add_text(form, "D", "D Matrix")

        elif bt == "Zero-Pole":
            self._add_line(form, "zeros", "Zeros")
            self._add_line(form, "poles", "Poles")
            self._add_spin(form, "gain", "Gain", -10000.0, 10000.0, 0.1)

        elif bt == "Transport Delay":
            self._add_spin(form, "delay", "Delay (s)", 0.0, 1000.0, 0.1)

        elif bt in {"Integrator", "Integrator Limited"}:
            self._add_spin(form, "initial_condition", "Initial Condition", -10000.0, 10000.0, 0.1)
            if bt == "Integrator Limited":
                self._add_spin(form, "lower", "Lower Limit", -10000.0, 10000.0, 0.1)
                self._add_spin(form, "upper", "Upper Limit", -10000.0, 10000.0, 0.1)

        # ─── Discrete ─────────────────────────────────────────────
        elif bt == "Unit Delay":
            self._add_spin(form, "initial_condition", "Initial Condition", -10000.0, 10000.0, 0.1)
            self._add_spin(form, "sample_time", "Sample Time", 0.001, 100.0, 0.001)

        elif bt in {"Discrete Transfer Fcn", "Discrete Filter"}:
            self._add_line(form, "numerator", "Numerator")
            self._add_line(form, "denominator", "Denominator")
            self._add_spin(form, "sample_time", "Sample Time", 0.001, 100.0, 0.001)

        elif bt == "Discrete FIR Filter":
            self._add_line(form, "coefficients", "Coefficients")
            self._add_spin(form, "sample_time", "Sample Time", 0.001, 100.0, 0.001)

        elif bt in {"Zero-Order Hold", "First-Order Hold"}:
            self._add_spin(form, "sample_time", "Sample Time", 0.001, 100.0, 0.001)

        elif bt == "Discrete Integrator":
            self._add_spin(form, "initial_condition", "Initial Condition", -10000.0, 10000.0, 0.1)
            self._add_spin(form, "sample_time", "Sample Time", 0.001, 100.0, 0.001)

        elif bt == "Discrete PID Controller":
            self._add_spin(form, "Kp", "Kp", 0.001, 10000.0, 0.1)
            self._add_spin(form, "Ki", "Ki", 0.0, 10000.0, 0.01)
            self._add_spin(form, "Kd", "Kd", 0.0, 10000.0, 0.01)
            self._add_spin(form, "sample_time", "Sample Time", 0.001, 100.0, 0.001)

        elif bt == "Tapped Delay":
            self._add_int_spin(form, "num_delays", "Number of Delays", 1, 100)
            self._add_spin(form, "sample_time", "Sample Time", 0.001, 100.0, 0.001)
            self._add_spin(form, "initial_condition", "Initial Condition", -10000.0, 10000.0, 0.1)

        # ─── Discontinuities ─────────────────────────────────────
        elif bt == "Saturation":
            self._add_spin(form, "upper", "Upper Limit", -10000.0, 10000.0, 0.1)
            self._add_spin(form, "lower", "Lower Limit", -10000.0, 10000.0, 0.1)

        elif bt in {"Dead Zone", "DeadZone"}:
            self._add_spin(form, "upper", "Upper Limit", -10000.0, 10000.0, 0.1)
            self._add_spin(form, "lower", "Lower Limit", -10000.0, 10000.0, 0.1)

        elif bt == "Relay":
            self._add_spin(form, "threshold", "Threshold", -10000.0, 10000.0, 0.1)
            self._add_spin(form, "on_value", "On Value", -10000.0, 10000.0, 0.1)
            self._add_spin(form, "off_value", "Off Value", -10000.0, 10000.0, 0.1)

        elif bt == "Rate Limiter":
            self._add_spin(form, "rising_slew", "Rising Slew", 0.0, 10000.0, 0.1)
            self._add_spin(form, "falling_slew", "Falling Slew", -10000.0, 0.0, 0.1)

        elif bt == "Quantizer":
            self._add_spin(form, "interval", "Quantization Interval", 0.001, 10000.0, 0.1)

        elif bt == "Backlash":
            self._add_spin(form, "deadband", "Deadband Width", 0.0, 10000.0, 0.1)

        elif bt == "Coulomb & Viscous Friction":
            self._add_spin(form, "coulomb", "Coulomb Friction", 0.0, 10000.0, 0.1)
            self._add_spin(form, "viscous", "Viscous Coefficient", 0.0, 10000.0, 0.01)

        elif bt == "Hit Crossing":
            self._add_spin(form, "threshold", "Threshold", -10000.0, 10000.0, 0.1)
            combo = QComboBox()
            combo.addItems(["either", "rising", "falling"])
            combo.setCurrentText(str(self.params.get("direction", "either")))
            form.addRow("Direction:", combo)
            self._widgets["direction"] = combo

        elif bt == "Wrap To Zero":
            self._add_spin(form, "threshold", "Threshold", 0.0, 10000.0, 0.1)

        # ─── Logic ────────────────────────────────────────────────
        elif bt == "Logical Operator":
            combo = QComboBox()
            combo.addItems(["AND", "OR", "NOT", "NAND", "NOR", "XOR", "XNOR"])
            combo.setCurrentText(str(self.params.get("operator", "AND")))
            form.addRow("Operator:", combo)
            self._widgets["operator"] = combo

        elif bt == "Relational Operator":
            combo = QComboBox()
            combo.addItems(["==", "!=", "<", ">", "<=", ">="])
            combo.setCurrentText(str(self.params.get("operator", "==")))
            form.addRow("Operator:", combo)
            self._widgets["operator"] = combo

        elif bt in {"Compare To Constant", "Compare To Zero"}:
            combo = QComboBox()
            combo.addItems(["==", "!=", "<", ">", "<=", ">="])
            combo.setCurrentText(str(self.params.get("operator", "==")))
            form.addRow("Operator:", combo)
            self._widgets["operator"] = combo
            if bt == "Compare To Constant":
                self._add_spin(form, "constant", "Constant", -10000.0, 10000.0, 0.1)

        elif bt == "Integer Delay":
            self._add_int_spin(form, "delay_length", "Delay Length", 1, 10000)

        # ─── Lookup Tables ────────────────────────────────────────
        elif bt == "Lookup Table 1-D":
            self._add_line(form, "input_values", "Input Values")
            self._add_line(form, "output_values", "Output Values")

        # ─── Signal Routing ───────────────────────────────────────
        elif bt == "Switch":
            self._add_spin(form, "threshold", "Threshold", -10000.0, 10000.0, 0.1)

        elif bt in {"Mux", "Bus Creator"}:
            self._add_int_spin(form, "num_inputs", "Number of Inputs", 2, 20)

        elif bt in {"Demux", "Bus Selector"}:
            self._add_int_spin(form, "num_outputs", "Number of Outputs", 2, 20)

        elif bt == "Manual Switch":
            self._add_int_spin(form, "position", "Position (0 or 1)", 0, 1)

        elif bt in {"From", "Goto", "Goto Tag Visibility"}:
            self._add_line(form, "tag", "Tag")

        elif bt in {"Data Store Memory", "Data Store Read", "Data Store Write"}:
            self._add_line(form, "name", "Store Name")

        elif bt == "Selector":
            self._add_line(form, "indices", "Indices (e.g. [1,3])")

        # ─── Sinks ────────────────────────────────────────────────
        elif bt in {"Scope", "To Workspace", "ToWorkspace", "Floating Scope"}:
            self._add_line(form, "variable", "Variable Name")

        elif bt in {"Inport", "Outport"}:
            self._add_int_spin(form, "port_number", "Port Number", 1, 100)

        # ─── Signal Attributes ────────────────────────────────────
        elif bt == "IC":
            self._add_spin(form, "value", "Initial Condition Value", -10000.0, 10000.0, 0.1)

        elif bt == "Data Type Conversion":
            combo = QComboBox()
            combo.addItems(["double", "single", "int8", "int16", "int32", "uint8", "uint16", "uint32", "boolean"])
            combo.setCurrentText(str(self.params.get("output_type", "double")))
            form.addRow("Output Type:", combo)
            self._widgets["output_type"] = combo

        # ─── Ports and Subsystems ─────────────────────────────────
        elif bt == "If":
            self._add_line(form, "condition", "Condition (e.g. u1 > 0)")

        elif bt == "For Iterator Subsystem":
            self._add_int_spin(form, "iterations", "Number of Iterations", 1, 10000)

        elif bt == "Model":
            self._add_line(form, "model_name", "Model Name")

        # ─── User-Defined ─────────────────────────────────────────
        elif bt == "MATLAB Function":
            self._add_text(form, "code", "Function Body")

        elif bt == "Function Caller":
            self._add_line(form, "function_name", "Function Name")

        # ─── Generic fallback ─────────────────────────────────────
        else:
            # Show all params as line edits
            for key, val in sorted(self.params.items()):
                line = QLineEdit(str(val))
                form.addRow(f"{key}:", line)
                self._widgets[key] = line

        buttons = QDialogButtonBox()
        cancel = QPushButton("Cancel")
        apply_btn = QPushButton("Apply")
        ok = QPushButton("OK")
        buttons.addButton(cancel, QDialogButtonBox.ButtonRole.RejectRole)
        buttons.addButton(apply_btn, QDialogButtonBox.ButtonRole.ApplyRole)
        buttons.addButton(ok, QDialogButtonBox.ButtonRole.AcceptRole)
        cancel.clicked.connect(self.reject)
        apply_btn.clicked.connect(self._apply)
        ok.clicked.connect(self._accept)
        layout.addWidget(buttons)

    # ─── Widget helpers ──────────────────────────────────────────

    def _add_spin(
        self, form: QFormLayout, key: str, label: str, lo: float, hi: float, step: float
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(lo, hi)
        spin.setValue(float(self.params.get(key, 0.0)))
        spin.setSingleStep(step)
        spin.setDecimals(4)
        form.addRow(f"{label}:", spin)
        self._widgets[key] = spin
        return spin

    def _add_int_spin(
        self, form: QFormLayout, key: str, label: str, lo: int, hi: int
    ) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(lo, hi)
        spin.setValue(int(self.params.get(key, lo)))
        form.addRow(f"{label}:", spin)
        self._widgets[key] = spin
        return spin

    def _add_line(self, form: QFormLayout, key: str, label: str) -> QLineEdit:
        line = QLineEdit(str(self.params.get(key, "")))
        form.addRow(f"{label}:", line)
        self._widgets[key] = line
        return line

    def _add_text(self, form: QFormLayout, key: str, label: str) -> QTextEdit:
        text = QTextEdit(str(self.params.get(key, "")))
        text.setMaximumHeight(80)
        form.addRow(f"{label}:", text)
        self._widgets[key] = text
        return text

    # ─── Actions ─────────────────────────────────────────────────

    def _apply(self) -> None:
        if self._validate():
            self.params = self.get_params()

    def _accept(self) -> None:
        if self._validate():
            self.params = self.get_params()
            self.accept()

    def _validate(self) -> bool:
        bt = self.block_type
        if bt in {"Transfer Fcn", "TransferFunction"}:
            num_w = self._widgets.get("numerator")
            den_w = self._widgets.get("denominator")
            if num_w and den_w:
                try:
                    ast.literal_eval(num_w.text())
                    ast.literal_eval(den_w.text())
                except (ValueError, SyntaxError) as exc:
                    QMessageBox.warning(self, "Invalid transfer function", str(exc))
                    return False
        if bt in {"State-Space", "StateSpace"}:
            for key in ("A", "B", "C", "D"):
                w = self._widgets.get(key)
                if w and isinstance(w, QTextEdit):
                    try:
                        json.loads(w.toPlainText())
                    except json.JSONDecodeError as exc:
                        QMessageBox.warning(self, f"Invalid {key} matrix", str(exc))
                        return False
        return True

    def get_params(self) -> dict:
        params = dict(self.params)
        for key, widget in self._widgets.items():
            if isinstance(widget, QLineEdit):
                params[key] = widget.text()
            elif isinstance(widget, QComboBox):
                params[key] = widget.currentText()
            elif isinstance(widget, QDoubleSpinBox):
                params[key] = float(widget.value())
            elif isinstance(widget, QSpinBox):
                params[key] = int(widget.value())
            elif isinstance(widget, QTextEdit):
                params[key] = widget.toPlainText()
        return params
