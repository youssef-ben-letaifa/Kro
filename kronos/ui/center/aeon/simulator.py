"""Diagram simulator for Aeon canvas."""

from __future__ import annotations

import ast
import json
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

import networkx as nx
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal
from scipy import signal as spsignal

from kronos.ui.center.aeon.block_registry import resolve_type

Signal = float | np.ndarray
_EPS = 1e-12


class SimulationError(RuntimeError):
    """Raised when diagram simulation fails."""


@dataclass
class _BlockRuntime:
    """Compiled runtime information for a block."""

    node_id: str
    block_type: str
    params: dict[str, Any]
    num_inputs: int
    num_outputs: int
    direct_feedthrough: bool
    state: dict[str, Any] = field(default_factory=dict)


class DiagramSimulator(QObject):
    """Simulate block diagrams with stateful, step-by-step execution."""

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

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_signal(value: Any) -> Signal:
        if isinstance(value, np.ndarray):
            array = np.asarray(value, dtype=float)
            return float(array.reshape(-1)[0]) if array.size == 1 else array
        if isinstance(value, (list, tuple)):
            array = np.asarray(value, dtype=float)
            return float(array.reshape(-1)[0]) if array.size == 1 else array
        if isinstance(value, (bool, np.bool_)):
            return float(value)
        if isinstance(value, (int, float, np.number)):
            return float(value)
        return 0.0

    @staticmethod
    def _to_scalar(signal: Signal) -> float:
        array = np.asarray(signal, dtype=float)
        if array.size == 0:
            return 0.0
        return float(array.reshape(-1)[0])

    @staticmethod
    def _to_array(signal: Signal) -> np.ndarray:
        return np.asarray(signal, dtype=float)

    @staticmethod
    def _serialize_signal(signal: Signal) -> float | list[float]:
        array = np.asarray(signal, dtype=float)
        if array.size == 1:
            return float(array.reshape(-1)[0])
        return array.reshape(-1).tolist()

    def _parse_vector(self, raw: Any, name: str) -> np.ndarray:
        if isinstance(raw, np.ndarray):
            vector = np.asarray(raw, dtype=float).reshape(-1)
        elif isinstance(raw, (list, tuple)):
            vector = np.asarray(raw, dtype=float).reshape(-1)
        else:
            parsed = ast.literal_eval(str(raw))
            vector = np.asarray(parsed, dtype=float).reshape(-1)
        if vector.size == 0:
            raise SimulationError(f"{name} cannot be empty.")
        return vector

    def _parse_optional_vector(self, raw: Any) -> np.ndarray:
        if raw in (None, "", "[]"):
            return np.array([], dtype=float)
        try:
            parsed = ast.literal_eval(str(raw))
        except (ValueError, SyntaxError):
            return np.array([], dtype=float)
        return np.asarray(parsed, dtype=float).reshape(-1)

    def _parse_matrix(self, raw: Any, name: str) -> np.ndarray:
        if isinstance(raw, np.ndarray):
            matrix = np.asarray(raw, dtype=float)
        elif isinstance(raw, (list, tuple)):
            matrix = np.asarray(raw, dtype=float)
        else:
            text = str(raw)
            try:
                matrix = np.asarray(json.loads(text), dtype=float)
            except json.JSONDecodeError:
                matrix = np.asarray(ast.literal_eval(text), dtype=float)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        if matrix.ndim != 2:
            raise SimulationError(f"{name} must be a 2-D matrix.")
        return matrix

    @staticmethod
    def _sample_hit(step: int, dt: float, sample_time: float) -> bool:
        if sample_time <= 0:
            return True
        ratio = sample_time / dt
        nearest = round(ratio)
        if nearest > 0 and abs(ratio - nearest) < 1e-9:
            return (step % int(nearest)) == 0
        time_now = step * dt
        q = time_now / sample_time
        return abs(q - round(q)) < 1e-9

    def _pack_outputs(self, runtime: _BlockRuntime, value: Any) -> list[Signal]:
        count = max(1, runtime.num_outputs)
        if isinstance(value, list | tuple):
            values = [self._normalize_signal(v) for v in value]
        else:
            array = np.asarray(value, dtype=float)
            if array.ndim >= 1 and array.size > 1 and count > 1:
                flat = array.reshape(-1)
                values = [self._normalize_signal(flat[idx]) for idx in range(min(count, flat.size))]
            else:
                values = [self._normalize_signal(value)]
        if not values:
            values = [0.0]
        if len(values) < count:
            values.extend([values[-1]] * (count - len(values)))
        return values[:count]

    @staticmethod
    def _first_input(inputs: list[Signal], default: Signal = 0.0) -> Signal:
        return inputs[0] if inputs else default

    def _input_vector(self, inputs: list[Signal], width: int) -> np.ndarray:
        if width <= 0:
            return np.zeros(0, dtype=float)
        if len(inputs) >= width:
            return np.array([self._to_scalar(sig) for sig in inputs[:width]], dtype=float)
        if len(inputs) == 1:
            vec = np.asarray(inputs[0], dtype=float).reshape(-1)
            if vec.size >= width:
                return vec[:width]
        padded = np.zeros(width, dtype=float)
        for idx, sig in enumerate(inputs[:width]):
            padded[idx] = self._to_scalar(sig)
        return padded

    def _gather_inputs(
        self,
        runtime: _BlockRuntime,
        incoming: dict[str, dict[int, tuple[str, int]]],
        preferred_outputs: dict[str, list[Signal]],
        fallback_outputs: dict[str, list[Signal]],
    ) -> list[Signal]:
        mapping = incoming.get(runtime.node_id, {})
        if mapping:
            count = max(runtime.num_inputs, max(mapping) + 1)
        else:
            count = runtime.num_inputs
        signals: list[Signal] = []
        for dest_port in range(count):
            src_info = mapping.get(dest_port)
            if src_info is None:
                signals.append(0.0)
                continue
            src_id, src_port = src_info
            src_values = preferred_outputs.get(src_id)
            if src_values is None:
                src_values = fallback_outputs.get(src_id)
            if not src_values:
                signals.append(0.0)
                continue
            idx = src_port if 0 <= src_port < len(src_values) else 0
            signals.append(src_values[idx])
        return signals

    def _parse_initial_state(self, params: dict[str, Any], order: int) -> np.ndarray:
        raw = params.get("initial_state", params.get("x0", None))
        if raw is None:
            return np.zeros(order, dtype=float)
        if isinstance(raw, (int, float, np.number)):
            init = np.zeros(order, dtype=float)
            if order > 0:
                init[0] = float(raw)
            return init
        vector = self._parse_vector(raw, "initial_state")
        init = np.zeros(order, dtype=float)
        init[: min(order, vector.size)] = vector[: min(order, vector.size)]
        return init

    def _init_continuous_lti(
        self,
        runtime: _BlockRuntime,
        matrix_a: np.ndarray,
        matrix_b: np.ndarray,
        matrix_c: np.ndarray,
        matrix_d: np.ndarray,
        dt: float,
    ) -> None:
        if matrix_a.shape[0] != matrix_a.shape[1]:
            raise SimulationError(f"{runtime.block_type}: A matrix must be square.")
        if matrix_b.shape[0] != matrix_a.shape[0]:
            raise SimulationError(f"{runtime.block_type}: B rows must match A rows.")
        if matrix_c.shape[1] != matrix_a.shape[1]:
            raise SimulationError(f"{runtime.block_type}: C columns must match A columns.")
        if matrix_d.shape != (matrix_c.shape[0], matrix_b.shape[1]):
            raise SimulationError(
                f"{runtime.block_type}: D must have shape ({matrix_c.shape[0]}, {matrix_b.shape[1]})."
            )

        ad, bd, cd, dd, _ = spsignal.cont2discrete((matrix_a, matrix_b, matrix_c, matrix_d), dt, method="zoh")
        runtime.state["ss_mode"] = "continuous"
        runtime.state["ad"] = np.asarray(ad, dtype=float)
        runtime.state["bd"] = np.asarray(bd, dtype=float)
        runtime.state["cd"] = np.asarray(cd, dtype=float)
        runtime.state["dd"] = np.asarray(dd, dtype=float)
        runtime.state["x"] = self._parse_initial_state(runtime.params, matrix_a.shape[0])
        runtime.state["input_width"] = matrix_b.shape[1]
        runtime.state["output_width"] = matrix_c.shape[0]
        runtime.state["direct_feedthrough_override"] = bool(np.any(np.abs(dd) > _EPS))

    def _init_discrete_lti(
        self,
        runtime: _BlockRuntime,
        matrix_a: np.ndarray,
        matrix_b: np.ndarray,
        matrix_c: np.ndarray,
        matrix_d: np.ndarray,
    ) -> None:
        if matrix_a.shape[0] != matrix_a.shape[1]:
            raise SimulationError(f"{runtime.block_type}: A matrix must be square.")
        if matrix_b.shape[0] != matrix_a.shape[0]:
            raise SimulationError(f"{runtime.block_type}: B rows must match A rows.")
        if matrix_c.shape[1] != matrix_a.shape[1]:
            raise SimulationError(f"{runtime.block_type}: C columns must match A columns.")
        if matrix_d.shape != (matrix_c.shape[0], matrix_b.shape[1]):
            raise SimulationError(
                f"{runtime.block_type}: D must have shape ({matrix_c.shape[0]}, {matrix_b.shape[1]})."
            )

        runtime.state["ss_mode"] = "discrete"
        runtime.state["ad"] = np.asarray(matrix_a, dtype=float)
        runtime.state["bd"] = np.asarray(matrix_b, dtype=float)
        runtime.state["cd"] = np.asarray(matrix_c, dtype=float)
        runtime.state["dd"] = np.asarray(matrix_d, dtype=float)
        runtime.state["x"] = self._parse_initial_state(runtime.params, matrix_a.shape[0])
        runtime.state["input_width"] = matrix_b.shape[1]
        runtime.state["output_width"] = matrix_c.shape[0]
        runtime.state["sample_time"] = self._safe_float(runtime.params.get("sample_time", 0.0), 0.0)
        runtime.state["y_hold"] = np.zeros(matrix_c.shape[0], dtype=float)
        runtime.state["direct_feedthrough_override"] = bool(np.any(np.abs(matrix_d) > _EPS))

    def _init_discrete_filter(self, runtime: _BlockRuntime, numerator: np.ndarray, denominator: np.ndarray) -> None:
        if denominator.size == 0:
            raise SimulationError(f"{runtime.block_type}: denominator cannot be empty.")
        if abs(denominator[0]) < _EPS:
            raise SimulationError(f"{runtime.block_type}: denominator leading coefficient cannot be zero.")
        a0 = denominator[0]
        b = numerator / a0
        a = denominator / a0
        runtime.state["b"] = np.asarray(b, dtype=float)
        runtime.state["a"] = np.asarray(a, dtype=float)
        runtime.state["u_hist"] = np.zeros(max(0, b.size - 1), dtype=float)
        runtime.state["y_hist"] = np.zeros(max(0, a.size - 1), dtype=float)
        runtime.state["y_hold"] = 0.0
        runtime.state["sample_time"] = self._safe_float(runtime.params.get("sample_time", 0.0), 0.0)
        runtime.state["direct_feedthrough_override"] = bool(abs(b[0]) > _EPS)

    def _initialize_state(self, runtime: _BlockRuntime, dt: float) -> None:
        bt = runtime.block_type
        params = runtime.params
        state = runtime.state

        if bt in {"Band-Limited White Noise", "Random Number", "Uniform Random Number", "Signal Generator"}:
            seed = self._safe_int(params.get("seed", 0), 0)
            state["rng"] = np.random.default_rng(seed if seed else None)

        if bt == "Repeating Sequence":
            tv = self._parse_vector(params.get("time_values", "[0,1]"), "time_values")
            ov = self._parse_vector(params.get("output_values", "[0,1]"), "output_values")
            if tv.size != ov.size:
                raise SimulationError("Repeating Sequence requires matching time_values and output_values lengths.")
            if tv.size < 2:
                raise SimulationError("Repeating Sequence requires at least two points.")
            if np.any(np.diff(tv) <= 0):
                raise SimulationError("Repeating Sequence time_values must be strictly increasing.")
            state["time_values"] = tv
            state["output_values"] = ov
            state["period"] = float(tv[-1] - tv[0])

        if bt == "Integrator":
            state["x"] = self._safe_float(params.get("initial_condition", 0.0), 0.0)

        if bt == "Integrator Limited":
            lo = self._safe_float(params.get("lower", -1.0), -1.0)
            hi = self._safe_float(params.get("upper", 1.0), 1.0)
            x0 = self._safe_float(params.get("initial_condition", 0.0), 0.0)
            state["x"] = float(np.clip(x0, min(lo, hi), max(lo, hi)))

        if bt == "Derivative":
            state["prev_input"] = 0.0
            state["y"] = 0.0
            state["filter_coefficient"] = max(0.0, self._safe_float(params.get("filter_coefficient", 50.0), 50.0))
            state["initialized"] = False

        if bt in {"Transfer Fcn", "TransferFunction"}:
            num = self._parse_vector(params.get("numerator", "[1]"), "numerator")
            den = self._parse_vector(params.get("denominator", "[1,1]"), "denominator")
            if den.size == 0 or abs(den[0]) < _EPS:
                raise SimulationError("Transfer Fcn denominator must have nonzero leading coefficient.")
            if num.size > den.size:
                raise SimulationError("Transfer Fcn requires a proper transfer function (degree(num) <= degree(den)).")
            matrix_a, matrix_b, matrix_c, matrix_d = spsignal.tf2ss(num, den)
            self._init_continuous_lti(runtime, matrix_a, matrix_b, matrix_c, matrix_d, dt)

        if bt in {"State-Space", "StateSpace"}:
            matrix_a = self._parse_matrix(params.get("A", "[[0,1],[-1,-2]]"), "A")
            matrix_b = self._parse_matrix(params.get("B", "[[0],[1]]"), "B")
            matrix_c = self._parse_matrix(params.get("C", "[[1,0]]"), "C")
            matrix_d = self._parse_matrix(params.get("D", "[[0]]"), "D")
            self._init_continuous_lti(runtime, matrix_a, matrix_b, matrix_c, matrix_d, dt)

        if bt == "Zero-Pole":
            zeros = self._parse_optional_vector(params.get("zeros", "[]"))
            poles = self._parse_optional_vector(params.get("poles", "[-1]"))
            gain = self._safe_float(params.get("gain", 1.0), 1.0)
            num, den = spsignal.zpk2tf(zeros, poles, gain)
            if num.size > den.size:
                raise SimulationError("Zero-Pole requires a proper transfer function.")
            matrix_a, matrix_b, matrix_c, matrix_d = spsignal.tf2ss(num, den)
            self._init_continuous_lti(runtime, matrix_a, matrix_b, matrix_c, matrix_d, dt)

        if bt == "PID Controller":
            kp = self._safe_float(params.get("Kp", 1.0), 1.0)
            ki = self._safe_float(params.get("Ki", 0.0), 0.0)
            kd = self._safe_float(params.get("Kd", 0.0), 0.0)
            n = max(1e-6, self._safe_float(params.get("N", 100.0), 100.0))
            num = np.array([kp + kd * n, kp * n + ki, ki * n], dtype=float)
            den = np.array([1.0, n, 0.0], dtype=float)
            matrix_a, matrix_b, matrix_c, matrix_d = spsignal.tf2ss(num, den)
            self._init_continuous_lti(runtime, matrix_a, matrix_b, matrix_c, matrix_d, dt)

        if bt == "Transport Delay":
            delay = max(0.0, self._safe_float(params.get("delay", 0.0), 0.0))
            initial = self._safe_float(params.get("initial_output", 0.0), 0.0)
            state["delay"] = delay
            state["buffer"] = deque([(-1e12, initial)])

        if bt == "Variable Transport Delay":
            max_delay = max(0.0, self._safe_float(params.get("max_delay", 10.0), 10.0))
            initial = self._safe_float(params.get("initial_output", 0.0), 0.0)
            state["max_delay"] = max_delay
            state["buffer"] = deque([(-1e12, initial)])

        if bt == "Unit Delay":
            state["x"] = self._safe_float(params.get("initial_condition", 0.0), 0.0)
            state["sample_time"] = self._safe_float(params.get("sample_time", dt), dt)

        if bt == "Discrete Integrator":
            state["x"] = self._safe_float(params.get("initial_condition", 0.0), 0.0)
            state["sample_time"] = self._safe_float(params.get("sample_time", dt), dt)

        if bt in {"Discrete Transfer Fcn", "Discrete Filter"}:
            num = self._parse_vector(params.get("numerator", "[1]"), "numerator")
            den = self._parse_vector(params.get("denominator", "[1,-0.5]"), "denominator")
            self._init_discrete_filter(runtime, num, den)

        if bt == "Discrete FIR Filter":
            coeffs = self._parse_vector(params.get("coefficients", "[0.25,0.5,0.25]"), "coefficients")
            self._init_discrete_filter(runtime, coeffs, np.array([1.0], dtype=float))

        if bt == "Discrete State-Space":
            matrix_a = self._parse_matrix(params.get("A", "[[0.9]]"), "A")
            matrix_b = self._parse_matrix(params.get("B", "[[0.1]]"), "B")
            matrix_c = self._parse_matrix(params.get("C", "[[1.0]]"), "C")
            matrix_d = self._parse_matrix(params.get("D", "[[0.0]]"), "D")
            self._init_discrete_lti(runtime, matrix_a, matrix_b, matrix_c, matrix_d)

        if bt == "Discrete Zero-Pole":
            zeros = self._parse_optional_vector(params.get("zeros", "[]"))
            poles = self._parse_optional_vector(params.get("poles", "[0.5]"))
            gain = self._safe_float(params.get("gain", 1.0), 1.0)
            num, den = spsignal.zpk2tf(zeros, poles, gain)
            self._init_discrete_filter(runtime, np.asarray(num, dtype=float), np.asarray(den, dtype=float))

        if bt == "Discrete PID Controller":
            state["sample_time"] = self._safe_float(params.get("sample_time", dt), dt)
            state["integral"] = 0.0
            state["prev_error"] = 0.0
            state["d_state"] = 0.0
            state["y_hold"] = 0.0

        if bt == "Zero-Order Hold":
            state["sample_time"] = self._safe_float(params.get("sample_time", dt), dt)
            state["hold"] = 0.0
            state["initialized"] = False

        if bt == "First-Order Hold":
            state["sample_time"] = self._safe_float(params.get("sample_time", dt), dt)
            state["prev_sample"] = 0.0
            state["curr_sample"] = 0.0
            state["last_hit_step"] = 0
            state["initialized"] = False

        if bt in {"Tapped Delay", "Integer Delay"}:
            if bt == "Tapped Delay":
                n_delay = max(1, self._safe_int(params.get("num_delays", 3), 3))
                initial = self._safe_float(params.get("initial_condition", 0.0), 0.0)
                state["sample_time"] = self._safe_float(params.get("sample_time", dt), dt)
            else:
                n_delay = max(1, self._safe_int(params.get("delay_length", 1), 1))
                initial = 0.0
                state["sample_time"] = dt
            state["delay_line"] = deque([initial] * (n_delay + 1), maxlen=n_delay + 1)

        if bt == "Rate Limiter":
            state["y"] = 0.0
            state["initialized"] = False

        if bt == "Backlash":
            state["y"] = 0.0
            state["initialized"] = False

        if bt in {
            "Hit Crossing",
            "Detect Change",
            "Detect Increase",
            "Detect Decrease",
            "Detect Rise Positive",
            "Detect Fall Negative",
        }:
            state["prev_input"] = 0.0
            state["initialized"] = False

        if bt == "Data Store Memory":
            state["store_name"] = str(params.get("name", "A"))
            state["initial_value"] = self._safe_float(params.get("initial_value", 0.0), 0.0)

        if bt == "IC":
            state["first_sample"] = True

        runtime.direct_feedthrough = bool(
            runtime.state.get(
                "direct_feedthrough_override",
                self._is_direct_feedthrough_default(runtime.block_type),
            )
        )

    @staticmethod
    def _is_direct_feedthrough_default(block_type: str) -> bool:
        no_feedthrough = {
            "Step",
            "Ramp",
            "Sine Wave",
            "Sine",
            "Constant",
            "Clock",
            "Digital Clock",
            "Pulse Generator",
            "Signal Generator",
            "Chirp Signal",
            "Band-Limited White Noise",
            "Random Number",
            "Uniform Random Number",
            "Repeating Sequence",
            "Ground",
            "Integrator",
            "Integrator Limited",
            "Derivative",
            "Transport Delay",
            "Variable Transport Delay",
            "Unit Delay",
            "Discrete Integrator",
            "Discrete Transfer Fcn",
            "Discrete Filter",
            "Discrete FIR Filter",
            "Discrete State-Space",
            "Discrete Zero-Pole",
            "Discrete PID Controller",
            "Tapped Delay",
            "Integer Delay",
            "Rate Limiter",
            "Backlash",
            "From",
            "Data Store Read",
        }
        return block_type not in no_feedthrough

    def _compile_runtimes(
        self,
        dt: float,
    ) -> tuple[dict[str, _BlockRuntime], dict[str, dict[int, tuple[str, int]]], list[str]]:
        runtimes: dict[str, _BlockRuntime] = {}
        for node_id, data in self._graph.nodes(data=True):
            raw_type = str(data.get("type", ""))
            block_type = resolve_type(raw_type)
            params = dict(data.get("params", {}))
            num_inputs = max(0, self._safe_int(data.get("inputs", 1), 1))
            num_outputs = max(1, self._safe_int(data.get("outputs", 1), 1))
            runtime = _BlockRuntime(
                node_id=node_id,
                block_type=block_type,
                params=params,
                num_inputs=num_inputs,
                num_outputs=num_outputs,
                direct_feedthrough=True,
            )
            self._initialize_state(runtime, dt)
            runtimes[node_id] = runtime

        incoming: dict[str, dict[int, tuple[str, int]]] = defaultdict(dict)
        for source, dest, _, data in self._graph.edges(keys=True, data=True):
            source_port = self._safe_int(data.get("source_port", 0), 0)
            dest_port = self._safe_int(data.get("dest_port", 0), 0)
            incoming[dest][dest_port] = (source, source_port)

        dependency = nx.DiGraph()
        dependency.add_nodes_from(runtimes.keys())
        for source, dest, _, _ in self._graph.edges(keys=True, data=True):
            if runtimes[dest].direct_feedthrough:
                dependency.add_edge(source, dest)

        try:
            order = list(nx.topological_sort(dependency))
        except nx.NetworkXUnfeasible as exc:
            raise SimulationError(
                "Algebraic loop detected among direct-feedthrough blocks. "
                "Insert a stateful block (Integrator/Unit Delay/Transfer Fcn)."
            ) from exc

        return runtimes, incoming, order

    def _compute_transport_delay_output(self, runtime: _BlockRuntime, target_time: float) -> float:
        buffer: deque[tuple[float, float]] = runtime.state["buffer"]
        if not buffer:
            return 0.0
        if target_time <= buffer[0][0]:
            return float(buffer[0][1])

        items = list(buffer)
        for idx in range(len(items) - 1):
            t0, y0 = items[idx]
            t1, y1 = items[idx + 1]
            if t0 <= target_time <= t1:
                if abs(t1 - t0) < _EPS:
                    return float(y1)
                alpha = (target_time - t0) / (t1 - t0)
                return float(y0 + alpha * (y1 - y0))
        return float(items[-1][1])

    def _evaluate_lti_output(self, runtime: _BlockRuntime, inputs: list[Signal]) -> list[Signal]:
        state = runtime.state
        u_vec = self._input_vector(inputs, int(state.get("input_width", 1)))
        x_vec = np.asarray(state.get("x", np.zeros(1, dtype=float)), dtype=float)
        c_mat = np.asarray(state["cd"], dtype=float)
        d_mat = np.asarray(state["dd"], dtype=float)
        y_vec = c_mat @ x_vec + d_mat @ u_vec
        return self._pack_outputs(runtime, y_vec)

    def _evaluate_block(
        self,
        runtime: _BlockRuntime,
        inputs: list[Signal],
        time_now: float,
        step: int,
        dt: float,
        context: dict[str, Any],
    ) -> list[Signal]:
        block_type = runtime.block_type
        params = runtime.params
        state = runtime.state

        # Sources
        if block_type == "Step":
            amplitude = self._safe_float(params.get("amplitude", 1.0), 1.0)
            step_time = self._safe_float(params.get("step_time", 0.0), 0.0)
            initial = self._safe_float(params.get("initial", 0.0), 0.0)
            return self._pack_outputs(runtime, amplitude if time_now >= step_time else initial)

        if block_type == "Ramp":
            slope = self._safe_float(params.get("slope", 1.0), 1.0)
            offset = self._safe_float(params.get("offset", 0.0), 0.0)
            start = self._safe_float(params.get("start_time", 0.0), 0.0)
            value = offset if time_now < start else offset + slope * (time_now - start)
            return self._pack_outputs(runtime, value)

        if block_type in {"Sine Wave", "Sine"}:
            amplitude = self._safe_float(params.get("amplitude", 1.0), 1.0)
            frequency = self._safe_float(params.get("frequency", 1.0), 1.0)
            phase = self._safe_float(params.get("phase", 0.0), 0.0)
            bias = self._safe_float(params.get("bias", 0.0), 0.0)
            value = amplitude * math.sin(2.0 * math.pi * frequency * time_now + phase) + bias
            return self._pack_outputs(runtime, value)

        if block_type == "Constant":
            return self._pack_outputs(runtime, self._safe_float(params.get("value", 1.0), 1.0))

        if block_type == "Clock":
            return self._pack_outputs(runtime, time_now)

        if block_type == "Digital Clock":
            sample_time = max(dt, self._safe_float(params.get("sample_time", dt), dt))
            value = math.floor(time_now / sample_time) * sample_time
            return self._pack_outputs(runtime, value)

        if block_type == "Pulse Generator":
            amplitude = self._safe_float(params.get("amplitude", 1.0), 1.0)
            period = max(_EPS, self._safe_float(params.get("period", 1.0), 1.0))
            duty = np.clip(self._safe_float(params.get("duty_cycle", 50.0), 50.0) / 100.0, 0.0, 1.0)
            phase_delay = self._safe_float(params.get("phase_delay", 0.0), 0.0)
            shifted = (time_now - phase_delay) % period
            return self._pack_outputs(runtime, amplitude if shifted < period * duty else 0.0)

        if block_type == "Signal Generator":
            wave = str(params.get("wave_form", "sine")).lower()
            amplitude = self._safe_float(params.get("amplitude", 1.0), 1.0)
            frequency = self._safe_float(params.get("frequency", 1.0), 1.0)
            if wave == "square":
                value = amplitude if math.sin(2.0 * math.pi * frequency * time_now) >= 0.0 else -amplitude
            elif wave == "sawtooth":
                value = amplitude * (2.0 * ((frequency * time_now) % 1.0) - 1.0)
            elif wave == "random":
                rng = state.get("rng")
                value = amplitude * float(rng.standard_normal()) if rng is not None else 0.0
            else:
                value = amplitude * math.sin(2.0 * math.pi * frequency * time_now)
            return self._pack_outputs(runtime, value)

        if block_type == "Chirp Signal":
            f0 = self._safe_float(params.get("f0", 0.1), 0.1)
            f1 = self._safe_float(params.get("f1", 10.0), 10.0)
            target = max(_EPS, self._safe_float(params.get("target_time", 10.0), 10.0))
            slope = (f1 - f0) / target
            phase = 2.0 * math.pi * (f0 * time_now + 0.5 * slope * time_now * time_now)
            return self._pack_outputs(runtime, math.sin(phase))

        if block_type == "Band-Limited White Noise":
            noise_power = max(0.0, self._safe_float(params.get("noise_power", 0.1), 0.1))
            sample_time = max(dt, self._safe_float(params.get("sample_time", dt), dt))
            rng = state.get("rng")
            if rng is None:
                return self._pack_outputs(runtime, 0.0)
            if not state.get("initialized", False) or self._sample_hit(step, dt, sample_time):
                sigma = math.sqrt(noise_power / sample_time)
                state["hold"] = float(sigma * rng.standard_normal())
                state["initialized"] = True
            return self._pack_outputs(runtime, state.get("hold", 0.0))

        if block_type == "Random Number":
            mean = self._safe_float(params.get("mean", 0.0), 0.0)
            variance = max(0.0, self._safe_float(params.get("variance", 1.0), 1.0))
            rng = state.get("rng")
            value = mean + math.sqrt(variance) * float(rng.standard_normal()) if rng is not None else mean
            return self._pack_outputs(runtime, value)

        if block_type == "Uniform Random Number":
            lo = self._safe_float(params.get("minimum", -1.0), -1.0)
            hi = self._safe_float(params.get("maximum", 1.0), 1.0)
            rng = state.get("rng")
            value = float(rng.uniform(lo, hi)) if rng is not None else lo
            return self._pack_outputs(runtime, value)

        if block_type == "Repeating Sequence":
            tv = np.asarray(state["time_values"], dtype=float)
            ov = np.asarray(state["output_values"], dtype=float)
            period = max(_EPS, float(state["period"]))
            wrapped = ((time_now - tv[0]) % period) + tv[0]
            return self._pack_outputs(runtime, np.interp(wrapped, tv, ov))

        if block_type == "Ground":
            return self._pack_outputs(runtime, 0.0)

        if block_type == "Inport":
            return self._pack_outputs(runtime, self._first_input(inputs, 0.0))

        # Math
        if block_type == "Gain":
            gain = self._safe_float(params.get("gain", 1.0), 1.0)
            return self._pack_outputs(runtime, gain * self._to_array(self._first_input(inputs, 0.0)))

        if block_type in {"Sum", "Subtract"}:
            if not inputs:
                raise SimulationError("Sum block requires at least one input.")
            signs = "+-" if block_type == "Subtract" else str(params.get("signs", "+" * len(inputs)))
            total = np.zeros_like(self._to_array(inputs[0]), dtype=float)
            for idx, signal in enumerate(inputs):
                sign = signs[idx] if idx < len(signs) else "+"
                arr = self._to_array(signal)
                total = total - arr if sign == "-" else total + arr
            return self._pack_outputs(runtime, total)

        if block_type == "Product":
            if not inputs:
                raise SimulationError("Product block requires at least one input.")
            result = np.ones_like(self._to_array(inputs[0]), dtype=float)
            for signal in inputs:
                result = result * self._to_array(signal)
            return self._pack_outputs(runtime, result)

        if block_type == "Dot Product":
            if len(inputs) < 2:
                raise SimulationError("Dot Product requires two inputs.")
            a_vec = self._to_array(inputs[0]).reshape(-1)
            b_vec = self._to_array(inputs[1]).reshape(-1)
            size = min(a_vec.size, b_vec.size)
            return self._pack_outputs(runtime, float(np.dot(a_vec[:size], b_vec[:size])))

        if block_type == "Math Function":
            signal = self._to_array(self._first_input(inputs, 0.0))
            func = str(params.get("function", "exp")).lower()
            if func == "exp":
                out = np.exp(signal)
            elif func == "log":
                out = np.log(signal)
            elif func == "log10":
                out = np.log10(signal)
            elif func == "sqrt":
                out = np.sqrt(np.maximum(signal, 0.0))
            elif func == "square":
                out = np.square(signal)
            elif func == "abs":
                out = np.abs(signal)
            elif func == "reciprocal":
                out = 1.0 / signal
            else:
                out = np.exp(signal)
            return self._pack_outputs(runtime, out)

        if block_type == "Trigonometric Function":
            signal = self._to_array(self._first_input(inputs, 0.0))
            func = str(params.get("function", "sin")).lower()
            trig_map = {
                "sin": np.sin,
                "cos": np.cos,
                "tan": np.tan,
                "asin": np.arcsin,
                "acos": np.arccos,
                "atan": np.arctan,
                "sinh": np.sinh,
                "cosh": np.cosh,
                "tanh": np.tanh,
            }
            return self._pack_outputs(runtime, trig_map.get(func, np.sin)(signal))

        if block_type == "Abs":
            return self._pack_outputs(runtime, np.abs(self._to_array(self._first_input(inputs, 0.0))))

        if block_type == "Sign":
            return self._pack_outputs(runtime, np.sign(self._to_array(self._first_input(inputs, 0.0))))

        if block_type == "Sqrt":
            signal = np.maximum(self._to_array(self._first_input(inputs, 0.0)), 0.0)
            return self._pack_outputs(runtime, np.sqrt(signal))

        if block_type == "MinMax":
            if not inputs:
                raise SimulationError("MinMax requires at least one input.")
            function = str(params.get("function", "min")).lower()
            stacked = np.stack([self._to_array(sig) for sig in inputs], axis=0)
            out = np.max(stacked, axis=0) if function == "max" else np.min(stacked, axis=0)
            return self._pack_outputs(runtime, out)

        if block_type == "Bias":
            bias = self._safe_float(params.get("bias", 0.0), 0.0)
            return self._pack_outputs(runtime, self._to_array(self._first_input(inputs, 0.0)) + bias)

        if block_type == "Unary Minus":
            return self._pack_outputs(runtime, -self._to_array(self._first_input(inputs, 0.0)))

        if block_type == "Rounding Function":
            signal = self._to_array(self._first_input(inputs, 0.0))
            mode = str(params.get("function", "round")).lower()
            if mode == "floor":
                out = np.floor(signal)
            elif mode == "ceil":
                out = np.ceil(signal)
            elif mode == "fix":
                out = np.fix(signal)
            else:
                out = np.round(signal)
            return self._pack_outputs(runtime, out)

        if block_type == "Slider Gain":
            gain = self._safe_float(params.get("gain", 1.0), 1.0)
            return self._pack_outputs(runtime, gain * self._to_array(self._first_input(inputs, 0.0)))

        # Continuous
        if block_type in {
            "Integrator",
            "Integrator Limited",
            "Derivative",
            "Transfer Fcn",
            "TransferFunction",
            "State-Space",
            "StateSpace",
            "Zero-Pole",
            "PID Controller",
        }:
            if block_type == "Integrator" or block_type == "Integrator Limited":
                return self._pack_outputs(runtime, state.get("x", 0.0))
            if block_type == "Derivative":
                return self._pack_outputs(runtime, state.get("y", 0.0))
            return self._evaluate_lti_output(runtime, inputs)

        if block_type == "Transport Delay":
            delay = max(0.0, self._safe_float(params.get("delay", state.get("delay", 0.0)), state.get("delay", 0.0)))
            return self._pack_outputs(runtime, self._compute_transport_delay_output(runtime, time_now - delay))

        if block_type == "Variable Transport Delay":
            signal_input = self._to_scalar(self._first_input(inputs, 0.0))
            delay_input = self._to_scalar(inputs[1]) if len(inputs) > 1 else 0.0
            max_delay = max(0.0, self._safe_float(params.get("max_delay", state.get("max_delay", 10.0)), state.get("max_delay", 10.0)))
            delay = float(np.clip(delay_input, 0.0, max_delay))
            delayed = self._compute_transport_delay_output(runtime, time_now - delay)
            if math.isfinite(signal_input):
                return self._pack_outputs(runtime, delayed)
            return self._pack_outputs(runtime, 0.0)

        # Discrete
        if block_type in {
            "Unit Delay",
            "Discrete Integrator",
            "Discrete Transfer Fcn",
            "Discrete Filter",
            "Discrete FIR Filter",
            "Discrete PID Controller",
        }:
            if block_type in {"Unit Delay", "Discrete Integrator"}:
                return self._pack_outputs(runtime, state.get("x", 0.0))
            sample_time = max(dt, self._safe_float(state.get("sample_time", dt), dt))
            if self._sample_hit(step, dt, sample_time):
                if block_type == "Discrete PID Controller":
                    error = self._to_scalar(self._first_input(inputs, 0.0))
                    kp = self._safe_float(params.get("Kp", 1.0), 1.0)
                    ki = self._safe_float(params.get("Ki", 0.0), 0.0)
                    kd = self._safe_float(params.get("Kd", 0.0), 0.0)
                    n = max(0.0, self._safe_float(params.get("N", 0.0), 0.0))
                    integral = self._safe_float(state.get("integral", 0.0), 0.0) + ki * sample_time * error
                    prev_error = self._safe_float(state.get("prev_error", 0.0), 0.0)
                    derivative_raw = (error - prev_error) / sample_time
                    if n > 0.0:
                        alpha = math.exp(-n * sample_time)
                        d_state = alpha * self._safe_float(state.get("d_state", 0.0), 0.0) + (1.0 - alpha) * derivative_raw
                    else:
                        d_state = derivative_raw
                    y_pred = kp * error + integral + kd * d_state
                    state["pid_preview"] = {
                        "integral": float(integral),
                        "prev_error": float(error),
                        "d_state": float(d_state),
                        "y": float(y_pred),
                    }
                    return self._pack_outputs(runtime, y_pred)

                u_val = self._to_scalar(self._first_input(inputs, 0.0))
                b = np.asarray(state.get("b", np.array([1.0])), dtype=float)
                a = np.asarray(state.get("a", np.array([1.0])), dtype=float)
                u_hist = np.asarray(state.get("u_hist", np.zeros(max(0, b.size - 1))), dtype=float)
                y_hist = np.asarray(state.get("y_hist", np.zeros(max(0, a.size - 1))), dtype=float)
                y_pred = b[0] * u_val
                if b.size > 1 and u_hist.size > 0:
                    y_pred += float(np.dot(b[1:], u_hist))
                if a.size > 1 and y_hist.size > 0:
                    y_pred -= float(np.dot(a[1:], y_hist))
                state["filter_preview"] = float(y_pred)
                return self._pack_outputs(runtime, y_pred)

            return self._pack_outputs(runtime, state.get("y_hold", 0.0))

        if block_type == "Discrete State-Space":
            sample_time = max(dt, self._safe_float(state.get("sample_time", dt), dt))
            if self._sample_hit(step, dt, sample_time):
                return self._evaluate_lti_output(runtime, inputs)
            return self._pack_outputs(runtime, state.get("y_hold", np.zeros(int(state.get("output_width", 1)), dtype=float)))

        if block_type == "Discrete Zero-Pole":
            sample_time = max(dt, self._safe_float(state.get("sample_time", dt), dt))
            if self._sample_hit(step, dt, sample_time):
                u_val = self._to_scalar(self._first_input(inputs, 0.0))
                b = np.asarray(state.get("b", np.array([1.0])), dtype=float)
                a = np.asarray(state.get("a", np.array([1.0])), dtype=float)
                u_hist = np.asarray(state.get("u_hist", np.zeros(max(0, b.size - 1))), dtype=float)
                y_hist = np.asarray(state.get("y_hist", np.zeros(max(0, a.size - 1))), dtype=float)
                y_pred = b[0] * u_val
                if b.size > 1 and u_hist.size > 0:
                    y_pred += float(np.dot(b[1:], u_hist))
                if a.size > 1 and y_hist.size > 0:
                    y_pred -= float(np.dot(a[1:], y_hist))
                state["filter_preview"] = float(y_pred)
                return self._pack_outputs(runtime, y_pred)
            return self._pack_outputs(runtime, state.get("y_hold", 0.0))

        if block_type == "Zero-Order Hold":
            signal = self._first_input(inputs, 0.0)
            sample_time = max(dt, self._safe_float(state.get("sample_time", dt), dt))
            if not state.get("initialized", False):
                return self._pack_outputs(runtime, signal)
            if self._sample_hit(step, dt, sample_time):
                return self._pack_outputs(runtime, signal)
            return self._pack_outputs(runtime, state.get("hold", 0.0))

        if block_type == "First-Order Hold":
            signal = self._to_scalar(self._first_input(inputs, 0.0))
            sample_time = max(dt, self._safe_float(state.get("sample_time", dt), dt))
            if not state.get("initialized", False):
                return self._pack_outputs(runtime, signal)
            if self._sample_hit(step, dt, sample_time):
                return self._pack_outputs(runtime, signal)
            steps_per_sample = max(1, int(round(sample_time / dt)))
            alpha = (step - int(state.get("last_hit_step", step))) / steps_per_sample
            alpha = float(np.clip(alpha, 0.0, 1.0))
            prev_sample = float(state.get("prev_sample", 0.0))
            curr_sample = float(state.get("curr_sample", 0.0))
            value = curr_sample + alpha * (curr_sample - prev_sample)
            return self._pack_outputs(runtime, value)

        if block_type in {"Tapped Delay", "Integer Delay"}:
            delay_line: deque[float] = state.get("delay_line", deque([0.0]))
            return self._pack_outputs(runtime, delay_line[0] if delay_line else 0.0)

        # Discontinuities
        if block_type == "Saturation":
            signal = self._to_array(self._first_input(inputs, 0.0))
            lower = self._safe_float(params.get("lower", -1.0), -1.0)
            upper = self._safe_float(params.get("upper", 1.0), 1.0)
            lo, hi = min(lower, upper), max(lower, upper)
            return self._pack_outputs(runtime, np.clip(signal, lo, hi))

        if block_type in {"Dead Zone", "DeadZone"}:
            signal = self._to_array(self._first_input(inputs, 0.0))
            lower = self._safe_float(params.get("lower", -0.1), -0.1)
            upper = self._safe_float(params.get("upper", 0.1), 0.1)
            lo, hi = min(lower, upper), max(lower, upper)
            out = signal.copy()
            inside = (out >= lo) & (out <= hi)
            out[inside] = 0.0
            out[out > hi] -= hi
            out[out < lo] -= lo
            return self._pack_outputs(runtime, out)

        if block_type == "Relay":
            signal = self._to_scalar(self._first_input(inputs, 0.0))
            threshold = self._safe_float(params.get("threshold", 0.0), 0.0)
            on_value = self._safe_float(params.get("on_value", 1.0), 1.0)
            off_value = self._safe_float(params.get("off_value", -1.0), -1.0)
            return self._pack_outputs(runtime, on_value if signal >= threshold else off_value)

        if block_type == "Rate Limiter":
            if not state.get("initialized", False):
                return self._pack_outputs(runtime, self._first_input(inputs, 0.0))
            return self._pack_outputs(runtime, state.get("y", 0.0))

        if block_type == "Quantizer":
            signal = self._to_array(self._first_input(inputs, 0.0))
            interval = max(_EPS, self._safe_float(params.get("interval", 0.5), 0.5))
            return self._pack_outputs(runtime, np.round(signal / interval) * interval)

        if block_type == "Backlash":
            if not state.get("initialized", False):
                return self._pack_outputs(runtime, self._first_input(inputs, 0.0))
            return self._pack_outputs(runtime, state.get("y", 0.0))

        if block_type == "Coulomb & Viscous Friction":
            signal = self._to_array(self._first_input(inputs, 0.0))
            coulomb = self._safe_float(params.get("coulomb", 1.0), 1.0)
            viscous = self._safe_float(params.get("viscous", 0.1), 0.1)
            return self._pack_outputs(runtime, np.sign(signal) * (coulomb + viscous * np.abs(signal)))

        if block_type == "Hit Crossing":
            current = self._to_scalar(self._first_input(inputs, 0.0))
            if not state.get("initialized", False):
                return self._pack_outputs(runtime, 0.0)
            previous = self._safe_float(state.get("prev_input", current), current)
            threshold = self._safe_float(params.get("threshold", 0.0), 0.0)
            direction = str(params.get("direction", "either")).lower()
            rising = previous < threshold <= current
            falling = previous > threshold >= current
            hit = (rising and direction in {"either", "rising"}) or (falling and direction in {"either", "falling"})
            return self._pack_outputs(runtime, 1.0 if hit else 0.0)

        if block_type == "Wrap To Zero":
            signal = self._to_array(self._first_input(inputs, 0.0))
            threshold = max(0.0, self._safe_float(params.get("threshold", 10.0), 10.0))
            out = np.where(np.abs(signal) >= threshold, 0.0, signal)
            return self._pack_outputs(runtime, out)

        # Logic
        if block_type == "Logical Operator":
            op = str(params.get("operator", "AND")).upper()
            if op == "NOT":
                value = self._to_array(self._first_input(inputs, 0.0))
                return self._pack_outputs(runtime, (value == 0.0).astype(float))
            if len(inputs) < 2:
                raise SimulationError("Logical Operator requires two inputs.")
            a = self._to_array(inputs[0]) != 0.0
            b = self._to_array(inputs[1]) != 0.0
            operations = {
                "AND": a & b,
                "OR": a | b,
                "NAND": ~(a & b),
                "NOR": ~(a | b),
                "XOR": a ^ b,
                "XNOR": ~(a ^ b),
            }
            return self._pack_outputs(runtime, operations.get(op, a & b).astype(float))

        if block_type == "Relational Operator":
            if len(inputs) < 2:
                raise SimulationError("Relational Operator requires two inputs.")
            op = str(params.get("operator", "=="))
            a = self._to_array(inputs[0])
            b = self._to_array(inputs[1])
            operations = {
                "==": np.equal,
                "!=": np.not_equal,
                "<": np.less,
                ">": np.greater,
                "<=": np.less_equal,
                ">=": np.greater_equal,
            }
            return self._pack_outputs(runtime, operations.get(op, np.equal)(a, b).astype(float))

        if block_type == "Compare To Constant":
            signal = self._to_array(self._first_input(inputs, 0.0))
            op = str(params.get("operator", "=="))
            constant = self._safe_float(params.get("constant", 0.0), 0.0)
            operations = {
                "==": np.equal,
                "!=": np.not_equal,
                "<": np.less,
                ">": np.greater,
                "<=": np.less_equal,
                ">=": np.greater_equal,
            }
            return self._pack_outputs(runtime, operations.get(op, np.equal)(signal, constant).astype(float))

        if block_type == "Compare To Zero":
            signal = self._to_array(self._first_input(inputs, 0.0))
            op = str(params.get("operator", "=="))
            operations = {
                "==": np.equal,
                "!=": np.not_equal,
                "<": np.less,
                ">": np.greater,
                "<=": np.less_equal,
                ">=": np.greater_equal,
            }
            return self._pack_outputs(runtime, operations.get(op, np.equal)(signal, 0.0).astype(float))

        if block_type in {"Detect Change", "Detect Increase", "Detect Decrease", "Detect Rise Positive", "Detect Fall Negative"}:
            current = self._to_scalar(self._first_input(inputs, 0.0))
            if not state.get("initialized", False):
                return self._pack_outputs(runtime, 0.0)
            previous = self._safe_float(state.get("prev_input", current), current)
            if block_type == "Detect Change":
                value = 1.0 if abs(current - previous) > _EPS else 0.0
            elif block_type == "Detect Increase":
                value = 1.0 if current > previous else 0.0
            elif block_type == "Detect Decrease":
                value = 1.0 if current < previous else 0.0
            elif block_type == "Detect Rise Positive":
                value = 1.0 if previous <= 0.0 < current else 0.0
            else:
                value = 1.0 if previous >= 0.0 > current else 0.0
            return self._pack_outputs(runtime, value)

        # Signal routing
        if block_type == "Switch":
            if len(inputs) < 3:
                return self._pack_outputs(runtime, self._first_input(inputs, 0.0))
            threshold = self._safe_float(params.get("threshold", 0.0), 0.0)
            control = self._to_scalar(inputs[1])
            chosen = inputs[0] if control >= threshold else inputs[2]
            return self._pack_outputs(runtime, chosen)

        if block_type == "Multiport Switch":
            if not inputs:
                return self._pack_outputs(runtime, 0.0)
            index_signal = self._to_scalar(inputs[0])
            data_inputs = inputs[1:]
            if not data_inputs:
                return self._pack_outputs(runtime, 0.0)
            idx = int(np.clip(round(index_signal), 0, len(data_inputs) - 1))
            return self._pack_outputs(runtime, data_inputs[idx])

        if block_type in {"Mux", "Bus Creator"}:
            vector = np.array([self._to_scalar(sig) for sig in inputs], dtype=float)
            return self._pack_outputs(runtime, vector)

        if block_type == "Merge":
            return self._pack_outputs(runtime, self._first_input(inputs, 0.0))

        if block_type in {"Demux", "Bus Selector"}:
            vector = self._to_array(self._first_input(inputs, 0.0)).reshape(-1)
            outputs = [vector[idx] if idx < vector.size else 0.0 for idx in range(runtime.num_outputs)]
            return self._pack_outputs(runtime, outputs)

        if block_type == "Selector":
            vector = self._to_array(self._first_input(inputs, 0.0)).reshape(-1)
            indices_raw = params.get("indices", "[1]")
            try:
                indices = np.asarray(ast.literal_eval(str(indices_raw)), dtype=int).reshape(-1)
            except (ValueError, SyntaxError):
                indices = np.array([1], dtype=int)
            selected = []
            for raw_idx in indices:
                idx = int(raw_idx) - 1
                selected.append(vector[idx] if 0 <= idx < vector.size else 0.0)
            if len(selected) == 1:
                return self._pack_outputs(runtime, float(selected[0]))
            return self._pack_outputs(runtime, np.asarray(selected, dtype=float))

        if block_type == "Manual Switch":
            if not inputs:
                return self._pack_outputs(runtime, 0.0)
            pos = int(np.clip(self._safe_int(params.get("position", 0), 0), 0, len(inputs) - 1))
            return self._pack_outputs(runtime, inputs[pos])

        if block_type == "Goto":
            signal = self._first_input(inputs, 0.0)
            tag = str(params.get("tag", "A"))
            context["goto_tags"][tag] = signal
            return self._pack_outputs(runtime, signal)

        if block_type == "From":
            tag = str(params.get("tag", "A"))
            if tag in context["goto_tags"]:
                return self._pack_outputs(runtime, context["goto_tags"][tag])
            return self._pack_outputs(runtime, context["goto_memory"].get(tag, 0.0))

        if block_type == "Data Store Read":
            name = str(params.get("name", "A"))
            return self._pack_outputs(runtime, context["data_store"].get(name, 0.0))

        if block_type == "Data Store Write":
            signal = self._first_input(inputs, 0.0)
            return self._pack_outputs(runtime, signal)

        # Lookup tables
        if block_type == "Lookup Table 1-D":
            signal = self._to_array(self._first_input(inputs, 0.0))
            iv = self._parse_vector(params.get("input_values", "[0,1,2]"), "input_values")
            ov = self._parse_vector(params.get("output_values", "[0,1,4]"), "output_values")
            if iv.size != ov.size:
                raise SimulationError("Lookup Table 1-D requires matching input/output vectors.")
            return self._pack_outputs(runtime, np.interp(signal, iv, ov))

        if block_type in {"Cosine", "Sine (Lookup)"}:
            signal = self._to_array(self._first_input(inputs, 0.0))
            return self._pack_outputs(runtime, np.cos(signal) if block_type == "Cosine" else np.sin(signal))

        # Signal attributes
        if block_type in {"Data Type Conversion", "Signal Conversion", "Data Type Duplicate", "Signal Specification", "Rate Transition", "Probe"}:
            return self._pack_outputs(runtime, self._first_input(inputs, 0.0))

        if block_type == "IC":
            if state.get("first_sample", True):
                return self._pack_outputs(runtime, self._safe_float(params.get("value", 0.0), 0.0))
            return self._pack_outputs(runtime, self._first_input(inputs, 0.0))

        if block_type == "Width":
            signal = self._to_array(self._first_input(inputs, 0.0))
            return self._pack_outputs(runtime, float(signal.size if signal.size > 0 else 1.0))

        # Sinks
        if block_type in {"Scope", "Floating Scope", "Display"}:
            signal = self._first_input(inputs, 0.0)
            if block_type in {"Scope", "Floating Scope"}:
                context["scope_outputs"][runtime.node_id].append(self._serialize_signal(signal))
            return self._pack_outputs(runtime, signal)

        if block_type in {"To Workspace", "ToWorkspace"}:
            signal = self._first_input(inputs, 0.0)
            var_name = str(params.get("variable", f"var_{runtime.node_id}"))
            context["workspace_outputs"][var_name].append(self._serialize_signal(signal))
            return self._pack_outputs(runtime, signal)

        if block_type == "XY Graph":
            if len(inputs) >= 2:
                signal = self._first_input(inputs[1:], 0.0)
            else:
                signal = self._first_input(inputs, 0.0)
            context["scope_outputs"][runtime.node_id].append(self._serialize_signal(signal))
            return self._pack_outputs(runtime, self._first_input(inputs, 0.0))

        if block_type == "Stop Simulation":
            signal = self._first_input(inputs, 0.0)
            if abs(self._to_scalar(signal)) > _EPS:
                context["stop_requested"] = True
            return self._pack_outputs(runtime, signal)

        if block_type in {"Terminator", "Outport"}:
            return self._pack_outputs(runtime, self._first_input(inputs, 0.0))

        # Model verification
        if block_type == "Assertion":
            signal = self._first_input(inputs, 0.0)
            if abs(self._to_scalar(signal)) <= _EPS:
                raise SimulationError(f"Assertion failed at t={time_now:.6g} s on block {runtime.node_id}.")
            return self._pack_outputs(runtime, signal)

        if block_type.startswith("Check Static") or block_type.startswith("Check Dynamic"):
            return self._pack_outputs(runtime, self._first_input(inputs, 0.0))

        # Subsystems / user-defined and unimplemented blocks: pass-through.
        passthrough_blocks = {
            "Subsystem",
            "Enabled Subsystem",
            "Triggered Subsystem",
            "Function-Call Subsystem",
            "For Iterator Subsystem",
            "While Iterator Subsystem",
            "If",
            "Switch Case",
            "Atomic Subsystem",
            "Model",
            "MATLAB Function",
            "Aeon Function",
            "Function Caller",
            "S-Function",
            "S-Function Builder",
            "Initialize Function",
            "Terminate Function",
            "Reset Function",
            "Data Store Memory",
            "Goto Tag Visibility",
            "Reshape",
            "Algebraic Constraint",
            "Index Vector",
            "Bus Assignment",
            "Lookup Table 2-D",
            "Lookup Table n-D",
            "Lookup Table Dynamic",
            "Interpolation Using Prelookup",
            "Prelookup",
            "Direct Lookup Table",
            "Saturation Dynamic",
            "Dead Zone Dynamic",
            "Rate Limiter Dynamic",
            "Bit Clear",
            "Bit Set",
            "Bitwise Operator",
            "Shift Arithmetic",
            "Combinatorial Logic",
            "Extract Bits",
        }
        if block_type in passthrough_blocks:
            return self._pack_outputs(runtime, self._first_input(inputs, 0.0))

        # Unknown blocks are explicit errors to avoid silent incorrect simulation.
        raise SimulationError(f"Unsupported block type: {block_type}")

    def _update_block_state(
        self,
        runtime: _BlockRuntime,
        inputs: list[Signal],
        outputs: list[Signal],
        time_now: float,
        step: int,
        dt: float,
        context: dict[str, Any],
    ) -> None:
        block_type = runtime.block_type
        params = runtime.params
        state = runtime.state

        if block_type == "Integrator":
            u_val = self._to_scalar(self._first_input(inputs, 0.0))
            state["x"] = float(state.get("x", 0.0) + dt * u_val)
            return

        if block_type == "Integrator Limited":
            u_val = self._to_scalar(self._first_input(inputs, 0.0))
            lo = self._safe_float(params.get("lower", -1.0), -1.0)
            hi = self._safe_float(params.get("upper", 1.0), 1.0)
            lower, upper = min(lo, hi), max(lo, hi)
            x_val = self._safe_float(state.get("x", 0.0), 0.0)
            delta = dt * u_val
            if (x_val >= upper and delta > 0.0) or (x_val <= lower and delta < 0.0):
                next_x = x_val
            else:
                next_x = x_val + delta
            state["x"] = float(np.clip(next_x, lower, upper))
            return

        if block_type == "Derivative":
            current = self._to_scalar(self._first_input(inputs, 0.0))
            if not state.get("initialized", False):
                state["prev_input"] = current
                state["y"] = 0.0
                state["initialized"] = True
                return
            previous = self._safe_float(state.get("prev_input", current), current)
            raw = (current - previous) / dt
            coeff = self._safe_float(state.get("filter_coefficient", 50.0), 50.0)
            if coeff <= 0.0:
                filtered = raw
            else:
                alpha = math.exp(-coeff * dt)
                filtered = alpha * self._safe_float(state.get("y", 0.0), 0.0) + (1.0 - alpha) * raw
            state["y"] = float(filtered)
            state["prev_input"] = current
            return

        if block_type in {"Transfer Fcn", "TransferFunction", "State-Space", "StateSpace", "Zero-Pole", "PID Controller"}:
            u_vec = self._input_vector(inputs, int(state.get("input_width", 1)))
            ad = np.asarray(state["ad"], dtype=float)
            bd = np.asarray(state["bd"], dtype=float)
            x_vec = np.asarray(state.get("x", np.zeros(ad.shape[0], dtype=float)), dtype=float)
            state["x"] = ad @ x_vec + bd @ u_vec
            return

        if block_type == "Discrete State-Space":
            sample_time = max(dt, self._safe_float(state.get("sample_time", dt), dt))
            if self._sample_hit(step, dt, sample_time):
                u_vec = self._input_vector(inputs, int(state.get("input_width", 1)))
                ad = np.asarray(state["ad"], dtype=float)
                bd = np.asarray(state["bd"], dtype=float)
                x_vec = np.asarray(state.get("x", np.zeros(ad.shape[0], dtype=float)), dtype=float)
                state["x"] = ad @ x_vec + bd @ u_vec
                state["y_hold"] = np.asarray(outputs, dtype=float)
            return

        if block_type in {"Transport Delay", "Variable Transport Delay"}:
            signal_val = self._to_scalar(self._first_input(inputs, 0.0))
            buffer: deque[tuple[float, float]] = state.get("buffer", deque())
            buffer.append((time_now, signal_val))
            if block_type == "Transport Delay":
                max_window = max(dt, self._safe_float(state.get("delay", 0.0), 0.0)) + 2.0 * dt
            else:
                max_window = max(dt, self._safe_float(state.get("max_delay", 10.0), 10.0)) + 2.0 * dt
            while len(buffer) > 2 and (time_now - buffer[1][0]) > max_window:
                buffer.popleft()
            state["buffer"] = buffer
            return

        if block_type == "Unit Delay":
            sample_time = max(dt, self._safe_float(state.get("sample_time", dt), dt))
            if self._sample_hit(step, dt, sample_time):
                state["x"] = self._to_scalar(self._first_input(inputs, 0.0))
            return

        if block_type == "Discrete Integrator":
            sample_time = max(dt, self._safe_float(state.get("sample_time", dt), dt))
            if self._sample_hit(step, dt, sample_time):
                u_val = self._to_scalar(self._first_input(inputs, 0.0))
                state["x"] = float(state.get("x", 0.0) + sample_time * u_val)
            return

        if block_type in {"Discrete Transfer Fcn", "Discrete Filter", "Discrete FIR Filter", "Discrete Zero-Pole"}:
            sample_time = max(dt, self._safe_float(state.get("sample_time", dt), dt))
            if not self._sample_hit(step, dt, sample_time):
                return
            u_val = self._to_scalar(self._first_input(inputs, 0.0))
            b = np.asarray(state.get("b", np.array([1.0])), dtype=float)
            a = np.asarray(state.get("a", np.array([1.0])), dtype=float)
            u_hist = np.asarray(state.get("u_hist", np.zeros(max(0, b.size - 1))), dtype=float)
            y_hist = np.asarray(state.get("y_hist", np.zeros(max(0, a.size - 1))), dtype=float)

            if "filter_preview" in state:
                y_val = float(state.pop("filter_preview"))
            else:
                y_val = b[0] * u_val
                if b.size > 1 and u_hist.size > 0:
                    y_val += float(np.dot(b[1:], u_hist))
                if a.size > 1 and y_hist.size > 0:
                    y_val -= float(np.dot(a[1:], y_hist))

            if u_hist.size > 0:
                u_hist[1:] = u_hist[:-1]
                u_hist[0] = u_val
            if y_hist.size > 0:
                y_hist[1:] = y_hist[:-1]
                y_hist[0] = y_val

            state["u_hist"] = u_hist
            state["y_hist"] = y_hist
            state["y_hold"] = float(y_val)
            return

        if block_type == "Discrete PID Controller":
            sample_time = max(dt, self._safe_float(state.get("sample_time", dt), dt))
            if not self._sample_hit(step, dt, sample_time):
                return
            preview = state.pop("pid_preview", None)
            if preview is not None:
                state["integral"] = float(preview["integral"])
                state["prev_error"] = float(preview["prev_error"])
                state["d_state"] = float(preview["d_state"])
                state["y_hold"] = float(preview["y"])
                return

            error = self._to_scalar(self._first_input(inputs, 0.0))
            kp = self._safe_float(params.get("Kp", 1.0), 1.0)
            ki = self._safe_float(params.get("Ki", 0.0), 0.0)
            kd = self._safe_float(params.get("Kd", 0.0), 0.0)
            n = max(0.0, self._safe_float(params.get("N", 0.0), 0.0))

            integral = self._safe_float(state.get("integral", 0.0), 0.0) + ki * sample_time * error
            prev_error = self._safe_float(state.get("prev_error", 0.0), 0.0)
            derivative_raw = (error - prev_error) / sample_time
            if n > 0.0:
                alpha = math.exp(-n * sample_time)
                d_state = alpha * self._safe_float(state.get("d_state", 0.0), 0.0) + (1.0 - alpha) * derivative_raw
            else:
                d_state = derivative_raw
            output = kp * error + integral + kd * d_state

            state["integral"] = float(integral)
            state["prev_error"] = float(error)
            state["d_state"] = float(d_state)
            state["y_hold"] = float(output)
            return

        if block_type == "Zero-Order Hold":
            sample_time = max(dt, self._safe_float(state.get("sample_time", dt), dt))
            u_val = self._to_scalar(self._first_input(inputs, 0.0))
            if (not state.get("initialized", False)) or self._sample_hit(step, dt, sample_time):
                state["hold"] = float(u_val)
                state["initialized"] = True
            return

        if block_type == "First-Order Hold":
            sample_time = max(dt, self._safe_float(state.get("sample_time", dt), dt))
            u_val = self._to_scalar(self._first_input(inputs, 0.0))
            if not state.get("initialized", False):
                state["prev_sample"] = float(u_val)
                state["curr_sample"] = float(u_val)
                state["last_hit_step"] = step
                state["initialized"] = True
                return
            if self._sample_hit(step, dt, sample_time):
                state["prev_sample"] = float(state.get("curr_sample", 0.0))
                state["curr_sample"] = float(u_val)
                state["last_hit_step"] = step
            return

        if block_type in {"Tapped Delay", "Integer Delay"}:
            sample_time = max(dt, self._safe_float(state.get("sample_time", dt), dt))
            if self._sample_hit(step, dt, sample_time):
                line: deque[float] = state.get("delay_line", deque([0.0]))
                line.append(self._to_scalar(self._first_input(inputs, 0.0)))
                state["delay_line"] = line
            return

        if block_type == "Rate Limiter":
            u_val = self._to_scalar(self._first_input(inputs, 0.0))
            if not state.get("initialized", False):
                state["y"] = float(u_val)
                state["initialized"] = True
                return
            rising = self._safe_float(params.get("rising_slew", 1.0), 1.0)
            falling = self._safe_float(params.get("falling_slew", -1.0), -1.0)
            y_prev = self._safe_float(state.get("y", 0.0), 0.0)
            delta = u_val - y_prev
            delta = min(delta, rising * dt)
            delta = max(delta, falling * dt)
            state["y"] = float(y_prev + delta)
            return

        if block_type == "Backlash":
            u_val = self._to_scalar(self._first_input(inputs, 0.0))
            if not state.get("initialized", False):
                state["y"] = float(u_val)
                state["initialized"] = True
                return
            deadband = max(0.0, self._safe_float(params.get("deadband", 1.0), 1.0))
            half = deadband / 2.0
            y_prev = self._safe_float(state.get("y", 0.0), 0.0)
            diff = u_val - y_prev
            if diff > half:
                state["y"] = float(u_val - half)
            elif diff < -half:
                state["y"] = float(u_val + half)
            else:
                state["y"] = float(y_prev)
            return

        if block_type in {
            "Hit Crossing",
            "Detect Change",
            "Detect Increase",
            "Detect Decrease",
            "Detect Rise Positive",
            "Detect Fall Negative",
        }:
            current = self._to_scalar(self._first_input(inputs, 0.0))
            state["prev_input"] = float(current)
            state["initialized"] = True
            return

        if block_type == "Data Store Memory":
            name = str(state.get("store_name", params.get("name", "A")))
            if name not in context["data_store"]:
                context["data_store"][name] = self._safe_float(state.get("initial_value", 0.0), 0.0)
            return

        if block_type == "Data Store Write":
            name = str(params.get("name", "A"))
            context["data_store"][name] = self._first_input(inputs, 0.0)
            return

        if block_type == "Goto":
            tag = str(params.get("tag", "A"))
            context["goto_memory"][tag] = self._first_input(inputs, 0.0)
            return

        if block_type == "IC":
            if state.get("first_sample", False):
                state["first_sample"] = False
            return

    def simulate(self, diagram: dict, t_end: float = 10.0, dt: float = 0.01) -> dict:
        """Simulate diagram and return time series outputs and variables."""
        if t_end <= 0.0:
            error = "t_end must be greater than 0."
            self.simulation_error.emit(error)
            return {"success": False, "error": error, "time": [], "outputs": {}, "variables": {}}
        if dt <= 0.0:
            error = "dt must be greater than 0."
            self.simulation_error.emit(error)
            return {"success": False, "error": error, "time": [], "outputs": {}, "variables": {}}

        self.build_graph(diagram)

        try:
            runtimes, incoming, order = self._compile_runtimes(dt)
        except (SimulationError, ValueError, TypeError, SyntaxError, json.JSONDecodeError) as exc:
            error = f"Simulation error: {exc}"
            self.simulation_error.emit(error)
            return {"success": False, "error": error, "time": [], "outputs": {}, "variables": {}}

        base_time = np.arange(0.0, t_end + dt * 0.5, dt, dtype=float)
        last_outputs: dict[str, list[Signal]] = {
            node_id: [0.0] * max(1, runtime.num_outputs) for node_id, runtime in runtimes.items()
        }
        time_points: list[float] = []

        context: dict[str, Any] = {
            "scope_outputs": defaultdict(list),
            "workspace_outputs": defaultdict(list),
            "goto_tags": {},
            "goto_memory": {},
            "data_store": {},
            "stop_requested": False,
        }

        try:
            for step, time_now in enumerate(base_time):
                context["goto_tags"] = {}
                time_points.append(float(time_now))

                current_outputs: dict[str, list[Signal]] = {}
                for node_id in order:
                    runtime = runtimes[node_id]
                    inputs = self._gather_inputs(runtime, incoming, current_outputs, last_outputs)
                    current_outputs[node_id] = self._evaluate_block(
                        runtime=runtime,
                        inputs=inputs,
                        time_now=float(time_now),
                        step=step,
                        dt=dt,
                        context=context,
                    )

                for node_id in order:
                    runtime = runtimes[node_id]
                    inputs = self._gather_inputs(runtime, incoming, current_outputs, current_outputs)
                    self._update_block_state(
                        runtime=runtime,
                        inputs=inputs,
                        outputs=current_outputs[node_id],
                        time_now=float(time_now),
                        step=step,
                        dt=dt,
                        context=context,
                    )

                last_outputs = current_outputs
                if context.get("stop_requested", False):
                    break

        except (SimulationError, ValueError, TypeError, OverflowError, FloatingPointError) as exc:
            error = f"Simulation error: {exc}"
            self.simulation_error.emit(error)
            return {"success": False, "error": error, "time": [], "outputs": {}, "variables": {}}

        result = {
            "success": True,
            "error": None,
            "time": time_points,
            "outputs": dict(context["scope_outputs"]),
            "variables": dict(context["workspace_outputs"]),
        }
        self.simulation_finished.emit(result)
        return result
