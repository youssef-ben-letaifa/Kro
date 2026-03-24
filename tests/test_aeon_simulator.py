from __future__ import annotations

import unittest

import control as ct
import numpy as np

from kronos.ui.center.aeon.simulator import DiagramSimulator


def _wire(wire_id: str, source: str, dest: str, source_port: int = 0, dest_port: int = 0) -> dict:
    return {
        "id": wire_id,
        "source": source,
        "dest": dest,
        "source_port": source_port,
        "dest_port": dest_port,
    }


class AeonSimulatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sim = DiagramSimulator()

    def test_transfer_function_step_response_matches_analytical(self) -> None:
        diagram = {
            "blocks": [
                {"id": "step", "type": "Step", "params": {"amplitude": 1.0, "step_time": 0.0, "initial": 0.0}, "inputs": 0, "outputs": 1},
                {"id": "plant", "type": "Transfer Fcn", "params": {"numerator": "[1]", "denominator": "[1, 1]"}, "inputs": 1, "outputs": 1},
                {"id": "scope", "type": "Scope", "params": {"variable": "y"}, "inputs": 1, "outputs": 0},
            ],
            "wires": [
                _wire("w1", "step", "plant"),
                _wire("w2", "plant", "scope"),
            ],
        }

        result = self.sim.simulate(diagram, t_end=5.0, dt=0.01)
        self.assertTrue(result["success"], msg=result.get("error"))

        t = np.asarray(result["time"], dtype=float)
        y = np.asarray(result["outputs"]["scope"], dtype=float)
        expected = 1.0 - np.exp(-t)
        self.assertLess(np.max(np.abs(y - expected)), 1.5e-2)

    def test_state_space_step_response_matches_analytical(self) -> None:
        diagram = {
            "blocks": [
                {"id": "step", "type": "Step", "params": {"amplitude": 1.0, "step_time": 0.0, "initial": 0.0}, "inputs": 0, "outputs": 1},
                {
                    "id": "ss",
                    "type": "State-Space",
                    "params": {"A": "[[-1.0]]", "B": "[[1.0]]", "C": "[[1.0]]", "D": "[[0.0]]"},
                    "inputs": 1,
                    "outputs": 1,
                },
                {"id": "scope", "type": "Scope", "params": {}, "inputs": 1, "outputs": 0},
            ],
            "wires": [
                _wire("w1", "step", "ss"),
                _wire("w2", "ss", "scope"),
            ],
        }

        result = self.sim.simulate(diagram, t_end=5.0, dt=0.01)
        self.assertTrue(result["success"], msg=result.get("error"))

        t = np.asarray(result["time"], dtype=float)
        y = np.asarray(result["outputs"]["scope"], dtype=float)
        expected = 1.0 - np.exp(-t)
        self.assertLess(np.max(np.abs(y - expected)), 1.5e-2)

    def test_closed_loop_pid_tracks_reference(self) -> None:
        kp, ki, kd = 2.0, 1.0, 0.0
        diagram = {
            "blocks": [
                {"id": "step", "type": "Step", "params": {"amplitude": 1.0, "step_time": 0.0, "initial": 0.0}, "inputs": 0, "outputs": 1},
                {"id": "sum", "type": "Sum", "params": {"signs": "+-"}, "inputs": 2, "outputs": 1},
                {"id": "pid", "type": "PID Controller", "params": {"Kp": kp, "Ki": ki, "Kd": kd, "N": 100.0}, "inputs": 1, "outputs": 1},
                {"id": "plant", "type": "Transfer Fcn", "params": {"numerator": "[1]", "denominator": "[1, 1]"}, "inputs": 1, "outputs": 1},
                {"id": "scope", "type": "Scope", "params": {}, "inputs": 1, "outputs": 0},
            ],
            "wires": [
                _wire("w1", "step", "sum", 0, 0),
                _wire("w2", "plant", "sum", 0, 1),
                _wire("w3", "sum", "pid"),
                _wire("w4", "pid", "plant"),
                _wire("w5", "plant", "scope"),
            ],
        }

        result = self.sim.simulate(diagram, t_end=8.0, dt=0.01)
        self.assertTrue(result["success"], msg=result.get("error"))

        t = np.asarray(result["time"], dtype=float)
        y = np.asarray(result["outputs"]["scope"], dtype=float)

        c_tf = ct.tf([kp, ki], [1.0, 0.0])
        g_tf = ct.tf([1.0], [1.0, 1.0])
        closed_loop = ct.feedback(c_tf * g_tf, 1)
        _, y_ref = ct.step_response(closed_loop, T=t)
        y_ref = np.asarray(y_ref, dtype=float)

        self.assertLess(np.max(np.abs(y - y_ref)), 7.5e-2)
        self.assertLess(abs(y[-1] - 1.0), 4e-2)

    def test_algebraic_loop_is_reported(self) -> None:
        diagram = {
            "blocks": [
                {"id": "const", "type": "Constant", "params": {"value": 1.0}, "inputs": 0, "outputs": 1},
                {"id": "sum", "type": "Sum", "params": {"signs": "++"}, "inputs": 2, "outputs": 1},
                {"id": "gain", "type": "Gain", "params": {"gain": 1.0}, "inputs": 1, "outputs": 1},
            ],
            "wires": [
                _wire("w1", "const", "sum", 0, 0),
                _wire("w2", "sum", "gain"),
                _wire("w3", "gain", "sum", 0, 1),
            ],
        }

        result = self.sim.simulate(diagram, t_end=1.0, dt=0.01)
        self.assertFalse(result["success"])
        self.assertIn("Algebraic loop", result["error"])

    def test_unit_delay_breaks_feedback_loop(self) -> None:
        diagram = {
            "blocks": [
                {"id": "const", "type": "Constant", "params": {"value": 1.0}, "inputs": 0, "outputs": 1},
                {"id": "sum", "type": "Sum", "params": {"signs": "++"}, "inputs": 2, "outputs": 1},
                {"id": "delay", "type": "Unit Delay", "params": {"initial_condition": 0.0, "sample_time": 0.01}, "inputs": 1, "outputs": 1},
                {"id": "scope", "type": "Scope", "params": {}, "inputs": 1, "outputs": 0},
            ],
            "wires": [
                _wire("w1", "const", "sum", 0, 0),
                _wire("w2", "delay", "sum", 0, 1),
                _wire("w3", "sum", "delay"),
                _wire("w4", "delay", "scope"),
            ],
        }

        result = self.sim.simulate(diagram, t_end=0.1, dt=0.01)
        self.assertTrue(result["success"], msg=result.get("error"))

    def test_discrete_transfer_function_matches_difference_equation(self) -> None:
        dt = 0.1
        diagram = {
            "blocks": [
                {"id": "step", "type": "Step", "params": {"amplitude": 1.0, "step_time": 0.0, "initial": 0.0}, "inputs": 0, "outputs": 1},
                {
                    "id": "d_tf",
                    "type": "Discrete Transfer Fcn",
                    "params": {"numerator": "[0.1]", "denominator": "[1, -0.9]", "sample_time": dt},
                    "inputs": 1,
                    "outputs": 1,
                },
                {"id": "scope", "type": "Scope", "params": {}, "inputs": 1, "outputs": 0},
            ],
            "wires": [
                _wire("w1", "step", "d_tf"),
                _wire("w2", "d_tf", "scope"),
            ],
        }

        result = self.sim.simulate(diagram, t_end=1.0, dt=dt)
        self.assertTrue(result["success"], msg=result.get("error"))

        y = np.asarray(result["outputs"]["scope"], dtype=float)
        expected = 1.0 - np.power(0.9, np.arange(1, len(y) + 1))
        self.assertLess(np.max(np.abs(y - expected)), 1e-10)


if __name__ == "__main__":
    unittest.main()
