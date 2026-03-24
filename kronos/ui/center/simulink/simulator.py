"""Diagram simulator for Simulink canvas."""

from __future__ import annotations

import ast
import json
import math

import control as ct
import networkx as nx
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal

from kronos.ui.center.simulink.block_registry import resolve_type


class SimulationError(RuntimeError):
    """Raised when diagram simulation fails."""


class DiagramSimulator(QObject):
    """Simulate block diagrams using a signal-flow graph."""

    simulation_finished = pyqtSignal(dict)
    simulation_error = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._graph = nx.MultiDiGraph()

    def build_graph(self, diagram: dict) -> None:
        """Build graph from serializable diagram payload."""
        self._graph.clear()
        for block in diagram.get("blocks", []):
            self._graph.add_node(str(block["id"]), **block)
        for wire in diagram.get("wires", []):
            self._graph.add_edge(
                str(wire["source"]),
                str(wire["dest"]),
                key=str(wire.get("id", "")),
                **wire,
            )

    def _ordered_inputs(self, node_id: str, outputs: dict[str, np.ndarray]) -> list[np.ndarray]:
        entries: list[tuple[int, np.ndarray]] = []
        for source, _, _, data in self._graph.in_edges(node_id, keys=True, data=True):
            if source in outputs:
                entries.append((int(data.get("dest_port", 0)), outputs[source]))
        entries.sort(key=lambda item: item[0])
        return [signal for _, signal in entries]

    @staticmethod
    def _forced_response(sys, time: np.ndarray, input_signal: np.ndarray) -> np.ndarray:
        response = ct.forced_response(sys, T=time, U=input_signal)
        if hasattr(response, "outputs"):
            values = np.asarray(response.outputs)
        elif isinstance(response, tuple) and len(response) > 1:
            values = np.asarray(response[1])
        else:
            values = np.asarray(response)
        return np.squeeze(values)

    @staticmethod
    def _require_input(block_type: str, inputs: list[np.ndarray]) -> np.ndarray:
        if inputs:
            return inputs[0]
        raise SimulationError(f"{block_type} requires an input signal but none is connected.")

    def simulate(self, diagram: dict, t_end: float = 10.0, dt: float = 0.01) -> dict:
        """Simulate diagram and return time series outputs/variables."""
        if t_end <= 0:
            error = "t_end must be greater than 0."
            self.simulation_error.emit(error)
            return {"success": False, "error": error, "time": [], "outputs": {}, "variables": {}}
        if dt <= 0:
            error = "dt must be greater than 0."
            self.simulation_error.emit(error)
            return {"success": False, "error": error, "time": [], "outputs": {}, "variables": {}}

        self.build_graph(diagram)
        try:
            order = list(nx.topological_sort(self._graph))
        except nx.NetworkXUnfeasible:
            error = "Algebraic loop detected. Add an integrator/state element to break the direct loop."
            self.simulation_error.emit(error)
            return {"success": False, "error": error, "time": [], "outputs": {}, "variables": {}}

        time = np.arange(0.0, t_end + dt, dt)
        outputs: dict[str, np.ndarray] = {}
        scope_outputs: dict[str, list[float]] = {}
        variables: dict[str, list[float]] = {}

        try:
            for node_id in order:
                node = self._graph.nodes[node_id]
                raw_type = str(node.get("type", ""))
                block_type = resolve_type(raw_type)
                params = dict(node.get("params", {}))
                inputs = self._ordered_inputs(node_id, outputs)

                output = self._simulate_block(block_type, params, inputs, time, dt, node_id,
                                              scope_outputs, variables)
                outputs[node_id] = output

        except (ValueError, TypeError, SyntaxError, json.JSONDecodeError, SimulationError) as exc:
            error = f"Simulation error: {exc}"
            self.simulation_error.emit(error)
            return {"success": False, "error": error, "time": [], "outputs": {}, "variables": {}}

        result = {
            "success": True,
            "error": None,
            "time": time.tolist(),
            "outputs": scope_outputs,
            "variables": variables,
        }
        self.simulation_finished.emit(result)
        return result

    def _simulate_block(
        self,
        block_type: str,
        params: dict,
        inputs: list[np.ndarray],
        time: np.ndarray,
        dt: float,
        node_id: str,
        scope_outputs: dict[str, list[float]],
        variables: dict[str, list[float]],
    ) -> np.ndarray:
        """Simulate a single block and return its output signal."""

        # ─── SOURCES ───────────────────────────────────────────────
        if block_type == "Step":
            amplitude = float(params.get("amplitude", 1.0))
            step_time = float(params.get("step_time", 0.0))
            initial = float(params.get("initial", 0.0))
            return np.where(time >= step_time, amplitude, initial)

        if block_type == "Ramp":
            slope = float(params.get("slope", 1.0))
            return slope * time

        if block_type in {"Sine Wave", "Sine"}:
            amplitude = float(params.get("amplitude", 1.0))
            frequency = float(params.get("frequency", 1.0))
            phase = float(params.get("phase", 0.0))
            bias = float(params.get("bias", 0.0))
            return amplitude * np.sin(2 * np.pi * frequency * time + phase) + bias

        if block_type in {"Constant", "Clock"}:
            if block_type == "Clock":
                return time.copy()
            return np.full_like(time, float(params.get("value", 1.0)), dtype=float)

        if block_type == "Digital Clock":
            sample_time = float(params.get("sample_time", 1.0))
            return np.floor(time / sample_time) * sample_time

        if block_type == "Pulse Generator":
            amplitude = float(params.get("amplitude", 1.0))
            period = float(params.get("period", 1.0))
            duty = float(params.get("duty_cycle", 50.0)) / 100.0
            phase_delay = float(params.get("phase_delay", 0.0))
            shifted = (time - phase_delay) % period
            return np.where(shifted < period * duty, amplitude, 0.0)

        if block_type == "Signal Generator":
            wave = str(params.get("wave_form", "sine"))
            amp = float(params.get("amplitude", 1.0))
            freq = float(params.get("frequency", 1.0))
            if wave == "square":
                return amp * np.sign(np.sin(2 * np.pi * freq * time))
            if wave == "sawtooth":
                return amp * (2 * ((freq * time) % 1.0) - 1.0)
            return amp * np.sin(2 * np.pi * freq * time)

        if block_type == "Chirp Signal":
            f0 = float(params.get("f0", 0.1))
            f1 = float(params.get("f1", 10.0))
            target = float(params.get("target_time", time[-1] if len(time) else 10.0))
            k = (f1 - f0) / target if target > 0 else 0.0
            return np.sin(2 * np.pi * (f0 * time + 0.5 * k * time**2))

        if block_type == "Band-Limited White Noise":
            noise_power = float(params.get("noise_power", 0.1))
            seed = int(params.get("seed", 0))
            rng = np.random.default_rng(seed if seed else None)
            return np.sqrt(noise_power / dt) * rng.standard_normal(len(time))

        if block_type == "Random Number":
            mean = float(params.get("mean", 0.0))
            variance = float(params.get("variance", 1.0))
            seed = int(params.get("seed", 0))
            rng = np.random.default_rng(seed if seed else None)
            return mean + np.sqrt(variance) * rng.standard_normal(len(time))

        if block_type == "Uniform Random Number":
            lo = float(params.get("minimum", -1.0))
            hi = float(params.get("maximum", 1.0))
            seed = int(params.get("seed", 0))
            rng = np.random.default_rng(seed if seed else None)
            return rng.uniform(lo, hi, len(time))

        if block_type == "Repeating Sequence":
            tv = np.array(ast.literal_eval(str(params.get("time_values", "[0,1]"))), dtype=float)
            ov = np.array(ast.literal_eval(str(params.get("output_values", "[0,1]"))), dtype=float)
            period = tv[-1] - tv[0] if len(tv) > 1 else 1.0
            wrapped = (time - tv[0]) % period + tv[0]
            return np.interp(wrapped, tv, ov)

        if block_type == "Ground":
            return np.zeros_like(time)

        if block_type == "Inport":
            return inputs[0] if inputs else np.zeros_like(time)

        # ─── MATH OPERATIONS ──────────────────────────────────────
        if block_type == "Gain":
            gain = float(params.get("gain", 1.0))
            signal = self._require_input(block_type, inputs)
            return gain * signal

        if block_type in {"Sum", "Subtract"}:
            if not inputs:
                raise SimulationError("Sum block requires at least one input.")
            if block_type == "Subtract":
                signs = "+-"
            else:
                signs = str(params.get("signs", "+" * len(inputs)))
            total = np.zeros_like(time)
            for idx, signal in enumerate(inputs):
                sign = signs[idx] if idx < len(signs) else "+"
                total = total - signal if sign == "-" else total + signal
            return total

        if block_type == "Product":
            if not inputs:
                raise SimulationError("Product block requires at least one input.")
            result = np.ones_like(time)
            for signal in inputs:
                result = result * signal
            return result

        if block_type == "Dot Product":
            if len(inputs) < 2:
                raise SimulationError("Dot Product requires two inputs.")
            return inputs[0] * inputs[1]

        if block_type == "Math Function":
            signal = self._require_input(block_type, inputs)
            func = str(params.get("function", "exp"))
            funcs = {
                "exp": np.exp, "log": np.log, "log10": np.log10,
                "sqrt": np.sqrt, "square": np.square,
                "abs": np.abs, "reciprocal": lambda x: 1.0 / x,
            }
            f = funcs.get(func, np.exp)
            return f(signal)

        if block_type == "Trigonometric Function":
            signal = self._require_input(block_type, inputs)
            func = str(params.get("function", "sin"))
            trig = {
                "sin": np.sin, "cos": np.cos, "tan": np.tan,
                "asin": np.arcsin, "acos": np.arccos, "atan": np.arctan,
                "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh,
            }
            return trig.get(func, np.sin)(signal)

        if block_type == "Abs":
            return np.abs(self._require_input(block_type, inputs))

        if block_type == "Sign":
            return np.sign(self._require_input(block_type, inputs))

        if block_type == "Sqrt":
            return np.sqrt(np.abs(self._require_input(block_type, inputs)))

        if block_type == "MinMax":
            if not inputs:
                raise SimulationError("MinMax requires at least one input.")
            func = str(params.get("function", "min"))
            stacked = np.stack(inputs, axis=0)
            return np.min(stacked, axis=0) if func == "min" else np.max(stacked, axis=0)

        if block_type == "Bias":
            signal = self._require_input(block_type, inputs)
            return signal + float(params.get("bias", 0.0))

        if block_type == "Unary Minus":
            return -self._require_input(block_type, inputs)

        if block_type == "Rounding Function":
            signal = self._require_input(block_type, inputs)
            func = str(params.get("function", "round"))
            if func == "floor":
                return np.floor(signal)
            if func == "ceil":
                return np.ceil(signal)
            if func == "fix":
                return np.fix(signal)
            return np.round(signal)

        if block_type == "Slider Gain":
            return float(params.get("gain", 1.0)) * self._require_input(block_type, inputs)

        # ─── CONTINUOUS ───────────────────────────────────────────
        if block_type == "Integrator":
            signal = self._require_input(block_type, inputs)
            ic = float(params.get("initial_condition", 0.0))
            return ic + np.cumsum(signal) * dt

        if block_type == "Integrator Limited":
            signal = self._require_input(block_type, inputs)
            ic = float(params.get("initial_condition", 0.0))
            lo = float(params.get("lower", -1.0))
            hi = float(params.get("upper", 1.0))
            return np.clip(ic + np.cumsum(signal) * dt, lo, hi)

        if block_type == "Derivative":
            signal = self._require_input(block_type, inputs)
            return np.gradient(signal, dt)

        if block_type in {"Transfer Fcn", "TransferFunction"}:
            num = ast.literal_eval(str(params.get("numerator", "[1]")))
            den = ast.literal_eval(str(params.get("denominator", "[1, 1]")))
            signal = self._require_input(block_type, inputs)
            sys = ct.tf(num, den)
            return self._forced_response(sys, time, signal)

        if block_type in {"PID Controller", "PID"}:
            kp = float(params.get("Kp", 1.0))
            ki = float(params.get("Ki", 0.0))
            kd = float(params.get("Kd", 0.0))
            signal = self._require_input(block_type, inputs)
            pid_sys = ct.tf([kd, kp, ki], [1, 0])
            return self._forced_response(pid_sys, time, signal)

        if block_type in {"State-Space", "StateSpace"}:
            signal = self._require_input(block_type, inputs)
            matrix_a = np.array(json.loads(str(params.get("A", "[[0,1],[-1,-2]]"))), dtype=float)
            matrix_b = np.array(json.loads(str(params.get("B", "[[0],[1]]"))), dtype=float)
            matrix_c = np.array(json.loads(str(params.get("C", "[[1,0]]"))), dtype=float)
            matrix_d = np.array(json.loads(str(params.get("D", "[[0]]"))), dtype=float)
            system = ct.ss(matrix_a, matrix_b, matrix_c, matrix_d)
            return self._forced_response(system, time, signal)

        if block_type == "Zero-Pole":
            signal = self._require_input(block_type, inputs)
            zeros = ast.literal_eval(str(params.get("zeros", "[]")))
            poles = ast.literal_eval(str(params.get("poles", "[-1]")))
            gain = float(params.get("gain", 1.0))
            sys = ct.zpk(zeros, poles, gain)
            return self._forced_response(sys, time, signal)

        if block_type == "Transport Delay":
            signal = self._require_input(block_type, inputs)
            delay = float(params.get("delay", 1.0))
            delay_samples = max(0, int(round(delay / dt)))
            delayed = np.zeros_like(signal)
            if delay_samples < len(signal):
                delayed[delay_samples:] = signal[:len(signal) - delay_samples]
            return delayed

        # ─── DISCRETE ─────────────────────────────────────────────
        if block_type == "Unit Delay":
            signal = self._require_input(block_type, inputs)
            ic = float(params.get("initial_condition", 0.0))
            return np.concatenate(([ic], signal[:-1]))

        if block_type == "Discrete Integrator":
            signal = self._require_input(block_type, inputs)
            ic = float(params.get("initial_condition", 0.0))
            ts = float(params.get("sample_time", dt))
            return ic + np.cumsum(signal) * ts

        if block_type in {"Discrete Transfer Fcn", "Discrete Filter"}:
            signal = self._require_input(block_type, inputs)
            num = ast.literal_eval(str(params.get("numerator", "[1]")))
            den = ast.literal_eval(str(params.get("denominator", "[1,-0.5]")))
            ts = float(params.get("sample_time", dt))
            from scipy.signal import dlsim
            _, yout, _ = dlsim((num, den, ts), signal.reshape(-1, 1))
            return np.squeeze(yout)

        if block_type == "Discrete FIR Filter":
            signal = self._require_input(block_type, inputs)
            coeffs = ast.literal_eval(str(params.get("coefficients", "[0.25,0.5,0.25]")))
            return np.convolve(signal, coeffs, mode="full")[:len(time)]

        if block_type == "Zero-Order Hold":
            signal = self._require_input(block_type, inputs)
            ts = float(params.get("sample_time", dt))
            period = max(1, int(round(ts / dt)))
            held = signal.copy()
            for i in range(0, len(held), period):
                held[i:i + period] = held[i]
            return held

        if block_type == "First-Order Hold":
            signal = self._require_input(block_type, inputs)
            ts = float(params.get("sample_time", dt))
            period = max(1, int(round(ts / dt)))
            result = signal.copy()
            for i in range(0, len(result) - period, period):
                s0 = result[i]
                s1 = result[min(i + period, len(result) - 1)]
                for j in range(1, period):
                    if i + j < len(result):
                        result[i + j] = s0 + (s1 - s0) * j / period
            return result

        if block_type == "Tapped Delay":
            signal = self._require_input(block_type, inputs)
            # Return latest delayed version
            n = int(params.get("num_delays", 3))
            ic = float(params.get("initial_condition", 0.0))
            prefix = np.full(n, ic)
            return np.concatenate((prefix, signal[:-n])) if n < len(signal) else np.full_like(signal, ic)

        if block_type == "Discrete PID Controller":
            kp = float(params.get("Kp", 1.0))
            ki = float(params.get("Ki", 0.0))
            kd = float(params.get("Kd", 0.0))
            ts = float(params.get("sample_time", dt))
            signal = self._require_input(block_type, inputs)
            p_term = kp * signal
            i_term = ki * np.cumsum(signal) * ts
            d_term = kd * np.gradient(signal, ts)
            return p_term + i_term + d_term

        # ─── DISCONTINUITIES ─────────────────────────────────────
        if block_type == "Saturation":
            signal = self._require_input(block_type, inputs)
            lower = float(params.get("lower", -1.0))
            upper = float(params.get("upper", 1.0))
            return np.clip(signal, lower, upper)

        if block_type in {"Dead Zone", "DeadZone"}:
            signal = self._require_input(block_type, inputs)
            lower = float(params.get("lower", -0.1))
            upper = float(params.get("upper", 0.1))
            clipped = signal.copy()
            inside = (clipped >= lower) & (clipped <= upper)
            clipped[inside] = 0.0
            clipped[clipped > upper] -= upper
            clipped[clipped < lower] -= lower
            return clipped

        if block_type == "Relay":
            signal = self._require_input(block_type, inputs)
            threshold = float(params.get("threshold", 0.0))
            on_value = float(params.get("on_value", 1.0))
            off_value = float(params.get("off_value", -1.0))
            return np.where(signal >= threshold, on_value, off_value)

        if block_type == "Rate Limiter":
            signal = self._require_input(block_type, inputs)
            rising = float(params.get("rising_slew", 1.0))
            falling = float(params.get("falling_slew", -1.0))
            out = np.zeros_like(signal)
            out[0] = signal[0]
            for i in range(1, len(signal)):
                delta = signal[i] - out[i - 1]
                delta = min(delta, rising * dt)
                delta = max(delta, falling * dt)
                out[i] = out[i - 1] + delta
            return out

        if block_type == "Quantizer":
            signal = self._require_input(block_type, inputs)
            interval = float(params.get("interval", 0.5))
            return np.round(signal / interval) * interval

        if block_type == "Backlash":
            signal = self._require_input(block_type, inputs)
            deadband = float(params.get("deadband", 1.0))
            out = np.zeros_like(signal)
            out[0] = signal[0]
            half = deadband / 2.0
            for i in range(1, len(signal)):
                diff = signal[i] - out[i - 1]
                if diff > half:
                    out[i] = signal[i] - half
                elif diff < -half:
                    out[i] = signal[i] + half
                else:
                    out[i] = out[i - 1]
            return out

        if block_type == "Coulomb & Viscous Friction":
            signal = self._require_input(block_type, inputs)
            coulomb = float(params.get("coulomb", 1.0))
            viscous = float(params.get("viscous", 0.1))
            return np.sign(signal) * (coulomb + viscous * np.abs(signal))

        if block_type == "Hit Crossing":
            signal = self._require_input(block_type, inputs)
            thresh = float(params.get("threshold", 0.0))
            crossed = np.zeros_like(signal)
            for i in range(1, len(signal)):
                if (signal[i - 1] < thresh <= signal[i]) or (signal[i - 1] > thresh >= signal[i]):
                    crossed[i] = 1.0
            return crossed

        if block_type == "Wrap To Zero":
            signal = self._require_input(block_type, inputs)
            threshold = float(params.get("threshold", 10.0))
            return np.where(np.abs(signal) >= threshold, 0.0, signal)

        # ─── LOGIC AND BIT OPERATIONS ────────────────────────────
        if block_type == "Logical Operator":
            op = str(params.get("operator", "AND"))
            if op == "NOT":
                signal = self._require_input(block_type, inputs)
                return (signal == 0.0).astype(float)
            if len(inputs) < 2:
                raise SimulationError("Logical Operator requires two inputs.")
            a, b = (inputs[0] != 0), (inputs[1] != 0)
            ops = {
                "AND": a & b, "OR": a | b, "NAND": ~(a & b),
                "NOR": ~(a | b), "XOR": a ^ b, "XNOR": ~(a ^ b),
            }
            return ops.get(op, a & b).astype(float)

        if block_type == "Relational Operator":
            if len(inputs) < 2:
                raise SimulationError("Relational Operator requires two inputs.")
            op = str(params.get("operator", "=="))
            ops = {
                "==": np.equal, "!=": np.not_equal,
                "<": np.less, ">": np.greater,
                "<=": np.less_equal, ">=": np.greater_equal,
            }
            return ops.get(op, np.equal)(inputs[0], inputs[1]).astype(float)

        if block_type == "Compare To Constant":
            signal = self._require_input(block_type, inputs)
            op = str(params.get("operator", "=="))
            k = float(params.get("constant", 0.0))
            ops = {
                "==": np.equal, "!=": np.not_equal,
                "<": np.less, ">": np.greater,
                "<=": np.less_equal, ">=": np.greater_equal,
            }
            return ops.get(op, np.equal)(signal, k).astype(float)

        if block_type == "Compare To Zero":
            signal = self._require_input(block_type, inputs)
            op = str(params.get("operator", "=="))
            ops = {
                "==": np.equal, "!=": np.not_equal,
                "<": np.less, ">": np.greater,
                "<=": np.less_equal, ">=": np.greater_equal,
            }
            return ops.get(op, np.equal)(signal, 0.0).astype(float)

        if block_type == "Detect Change":
            signal = self._require_input(block_type, inputs)
            diff = np.diff(signal, prepend=signal[0])
            return (diff != 0).astype(float)

        if block_type == "Detect Increase":
            signal = self._require_input(block_type, inputs)
            diff = np.diff(signal, prepend=signal[0])
            return (diff > 0).astype(float)

        if block_type == "Detect Decrease":
            signal = self._require_input(block_type, inputs)
            diff = np.diff(signal, prepend=signal[0])
            return (diff < 0).astype(float)

        if block_type == "Detect Rise Positive":
            signal = self._require_input(block_type, inputs)
            result = np.zeros_like(signal)
            for i in range(1, len(signal)):
                if signal[i - 1] <= 0 < signal[i]:
                    result[i] = 1.0
            return result

        if block_type == "Detect Fall Negative":
            signal = self._require_input(block_type, inputs)
            result = np.zeros_like(signal)
            for i in range(1, len(signal)):
                if signal[i - 1] >= 0 > signal[i]:
                    result[i] = 1.0
            return result

        if block_type == "Integer Delay":
            signal = self._require_input(block_type, inputs)
            n = max(1, int(params.get("delay_length", 1)))
            return np.concatenate((np.zeros(min(n, len(signal))), signal[:max(0, len(signal) - n)]))

        # ─── SIGNAL ROUTING ──────────────────────────────────────
        if block_type == "Switch":
            if len(inputs) < 3:
                return inputs[0] if inputs else np.zeros_like(time)
            threshold = float(params.get("threshold", 0.0))
            return np.where(inputs[1] >= threshold, inputs[0], inputs[2])

        if block_type == "Multiport Switch":
            if not inputs:
                return np.zeros_like(time)
            idx_signal = inputs[0]
            data_inputs = inputs[1:]
            if not data_inputs:
                return np.zeros_like(time)
            result = np.zeros_like(time)
            for i in range(len(time)):
                sel = int(np.clip(idx_signal[i], 0, len(data_inputs) - 1))
                result[i] = data_inputs[sel][i]
            return result

        if block_type in {"Mux", "Bus Creator", "Merge"}:
            if not inputs:
                return np.zeros_like(time)
            return inputs[0]

        if block_type in {"Demux", "Bus Selector"}:
            signal = self._require_input(block_type, inputs)
            return signal

        if block_type == "Selector":
            signal = self._require_input(block_type, inputs)
            return signal

        if block_type == "Manual Switch":
            pos = int(params.get("position", 0))
            if inputs:
                idx = min(pos, len(inputs) - 1)
                return inputs[idx]
            return np.zeros_like(time)

        if block_type in {"From", "Data Store Read"}:
            return inputs[0] if inputs else np.zeros_like(time)

        if block_type in {"Goto", "Data Store Write"}:
            return inputs[0] if inputs else np.zeros_like(time)

        # ─── LOOKUP TABLES ───────────────────────────────────────
        if block_type == "Lookup Table 1-D":
            signal = self._require_input(block_type, inputs)
            iv = np.array(ast.literal_eval(str(params.get("input_values", "[0,1,2]"))), dtype=float)
            ov = np.array(ast.literal_eval(str(params.get("output_values", "[0,1,4]"))), dtype=float)
            return np.interp(signal, iv, ov)

        if block_type in {"Cosine", "Sine (Lookup)"}:
            signal = self._require_input(block_type, inputs)
            if "Cos" in block_type or block_type == "Cosine":
                return np.cos(signal)
            return np.sin(signal)

        # ─── SIGNAL ATTRIBUTES ───────────────────────────────────
        if block_type in {"Data Type Conversion", "Signal Conversion"}:
            return self._require_input(block_type, inputs)

        if block_type == "IC":
            signal = self._require_input(block_type, inputs)
            ic_val = float(params.get("value", 0.0))
            out = signal.copy()
            out[0] = ic_val
            return out

        if block_type == "Width":
            return np.ones_like(time)

        if block_type == "Probe":
            return self._require_input(block_type, inputs) if inputs else np.zeros_like(time)

        # ─── SINKS ───────────────────────────────────────────────
        if block_type in {"Scope", "Display", "Floating Scope"}:
            signal = self._require_input(block_type, inputs)
            if block_type in {"Scope", "Floating Scope"}:
                scope_outputs[node_id] = signal.tolist()
            return signal

        if block_type in {"To Workspace", "ToWorkspace"}:
            signal = self._require_input(block_type, inputs)
            var_name = str(params.get("variable", f"var_{node_id}"))
            variables[var_name] = signal.tolist()
            return signal

        if block_type in {"Terminator", "Stop Simulation", "Outport"}:
            return inputs[0] if inputs else np.zeros_like(time)

        if block_type == "XY Graph":
            if len(inputs) >= 2:
                scope_outputs[node_id] = inputs[1].tolist()
            elif inputs:
                scope_outputs[node_id] = inputs[0].tolist()
            return inputs[0] if inputs else np.zeros_like(time)

        # ─── MODEL VERIFICATION (passthrough / assertion) ────────
        if block_type == "Assertion":
            signal = self._require_input(block_type, inputs)
            if np.any(signal == 0):
                raise SimulationError("Assertion failed: input went to zero.")
            return signal

        if block_type.startswith("Check Static") or block_type.startswith("Check Dynamic"):
            return inputs[0] if inputs else np.zeros_like(time)

        # ─── SUBSYSTEMS / USER-DEFINED (passthrough) ─────────────
        if block_type in {
            "Subsystem", "Enabled Subsystem", "Triggered Subsystem",
            "Function-Call Subsystem", "For Iterator Subsystem",
            "While Iterator Subsystem", "If", "Switch Case",
            "Atomic Subsystem", "Model", "MATLAB Function",
            "Simulink Function", "Function Caller", "S-Function",
            "S-Function Builder", "Initialize Function",
            "Terminate Function", "Reset Function",
            "Data Store Memory", "Goto Tag Visibility",
            "Data Type Duplicate", "Signal Specification",
            "Rate Transition", "Reshape", "Algebraic Constraint",
            "Index Vector", "Bus Assignment",
        }:
            return inputs[0] if inputs else np.zeros_like(time)

        # Fallback: passthrough or zeros
        return inputs[0] if inputs else np.zeros_like(time)
