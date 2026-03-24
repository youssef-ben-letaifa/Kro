import sys
from PyQt6.QtCore import QCoreApplication
from kronos.ui.center.simulink.simulator import DiagramSimulator

app = QCoreApplication(sys.argv)

diagram = {
    'blocks': [
        {'id': 'sine', 'type': 'Sine Wave', 'params': {'amplitude': 1.0, 'frequency': 1.0}, 'inputs': 0, 'outputs': 1},
        {'id': 'gain', 'type': 'Gain', 'params': {'gain': 2.0}, 'inputs': 1, 'outputs': 1},
        {'id': 'scope', 'type': 'Scope', 'params': {'variable': 'y'}, 'inputs': 1, 'outputs': 0},
    ],
    'wires': [
        {'id': 'w1', 'source': 'sine', 'dest': 'gain', 'source_port': 0, 'dest_port': 0},
        {'id': 'w2', 'source': 'gain', 'dest': 'scope', 'source_port': 0, 'dest_port': 0},
    ]
}

sim = DiagramSimulator()
result = sim.simulate(diagram, 1.0, 0.1)
print(result)
