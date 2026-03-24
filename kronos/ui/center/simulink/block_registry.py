"""Centralized Simulink block registry.

Every block available in the Kronos Simulink library is defined here
exactly once.  The ``left_panel``, ``SimulinkLibrary`` tree, canvas
drop handler, and ``BlockItem`` all consume this registry so that
adding a new block only requires editing this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BlockDef:
    """Immutable definition of a Simulink block type."""

    type: str
    category: str
    color: str
    inputs: int
    outputs: int
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    symbol: str = ""          # short glyph drawn inside the block


# ---------------------------------------------------------------------------
# Color palette (Simulink-inspired)
# ---------------------------------------------------------------------------
_SRC   = "#e5a100"   # Sources – orange/yellow
_SINK  = "#1a4080"   # Sinks – dark blue
_CONT  = "#f0f0f0"   # Continuous – white/light
_DISC  = "#6090b0"   # Discrete – blue-gray
_MATH  = "#90c8ff"   # Math Operations – light blue
_DISC2 = "#d0d8e0"   # Discontinuities – light
_LOGIC = "#b0c0d0"   # Logic & Bit Operations
_LUT   = "#c8d8e0"   # Lookup Tables
_ROUTE = "#a0b8d0"   # Signal Routing
_PORT  = "#e0e0e0"   # Ports & Subsystems
_SATTR = "#d0d0e0"   # Signal Attributes
_VERIF = "#e0d0d0"   # Model Verification
_UTIL  = "#d0d0d0"   # Model-Wide Utilities
_MATRX = "#90c8ff"   # Matrix Operations
_UDEF  = "#d0e0d0"   # User-Defined Functions
_STR   = "#d0d0d0"   # String
_CTRL  = "#98c379"   # Control (kept for backward compat in Continuous)
_NONL  = "#e06c75"   # Nonlinear (kept for backward compat)

# ---------------------------------------------------------------------------
# 1. SOURCES
# ---------------------------------------------------------------------------
_SOURCES: list[BlockDef] = [
    BlockDef("Step",       "Sources", _SRC, 0, 1,
             {"amplitude": 1.0, "step_time": 0.0, "initial": 0.0},
             "Step function", "⌐"),
    BlockDef("Ramp",       "Sources", _SRC, 0, 1,
             {"slope": 1.0},
             "Linearly increasing signal", "/"),
    BlockDef("Sine Wave",  "Sources", _SRC, 0, 1,
             {"amplitude": 1.0, "frequency": 1.0, "phase": 0.0, "bias": 0.0},
             "Sinusoidal signal", "∿"),
    BlockDef("Constant",   "Sources", _SRC, 0, 1,
             {"value": 1.0},
             "Fixed scalar output", "K"),
    BlockDef("Clock",      "Sources", _SRC, 0, 1,
             {},
             "Simulation time", "⏲"),
    BlockDef("Digital Clock", "Sources", _SRC, 0, 1,
             {"sample_time": 1.0},
             "Discrete simulation time", "⏲d"),
    BlockDef("Pulse Generator", "Sources", _SRC, 0, 1,
             {"amplitude": 1.0, "period": 1.0, "duty_cycle": 50.0, "phase_delay": 0.0},
             "Square pulses", "⌐⌐"),
    BlockDef("Signal Generator", "Sources", _SRC, 0, 1,
             {"wave_form": "sine", "amplitude": 1.0, "frequency": 1.0},
             "Sine/square/sawtooth/random", "~"),
    BlockDef("Chirp Signal", "Sources", _SRC, 0, 1,
             {"f0": 0.1, "f1": 10.0, "target_time": 10.0},
             "Frequency-sweep sine", "↗∿"),
    BlockDef("Band-Limited White Noise", "Sources", _SRC, 0, 1,
             {"noise_power": 0.1, "sample_time": 0.01, "seed": 0},
             "Random noise", "≋"),
    BlockDef("Random Number", "Sources", _SRC, 0, 1,
             {"mean": 0.0, "variance": 1.0, "seed": 0},
             "Normal distribution", "Rn"),
    BlockDef("Uniform Random Number", "Sources", _SRC, 0, 1,
             {"minimum": -1.0, "maximum": 1.0, "seed": 0},
             "Uniform distribution", "Ru"),
    BlockDef("Repeating Sequence", "Sources", _SRC, 0, 1,
             {"time_values": "[0,1]", "output_values": "[0,1]"},
             "Repeatable waveform", "↻"),
    BlockDef("Ground",     "Sources", _SRC, 0, 1,
             {},
             "Outputs zero", "⏚"),
    BlockDef("Inport",     "Sources", _SRC, 0, 1,
             {"port_number": 1},
             "External input port", "→"),
]

# ---------------------------------------------------------------------------
# 2. SINKS
# ---------------------------------------------------------------------------
_SINKS: list[BlockDef] = [
    BlockDef("Scope",      "Sinks", _SINK, 1, 0,
             {"variable": "y"},
             "Time-domain plot", "📈"),
    BlockDef("Floating Scope", "Sinks", _SINK, 1, 0,
             {},
             "Click-to-connect scope", "📈~"),
    BlockDef("XY Graph",   "Sinks", _SINK, 2, 0,
             {},
             "Phase-plane plot", "XY"),
    BlockDef("Display",    "Sinks", _SINK, 1, 0,
             {},
             "Numeric display", "▯"),
    BlockDef("To Workspace", "Sinks", _SINK, 1, 0,
             {"variable": "y"},
             "Save to workspace variable", "→WS"),
    BlockDef("Stop Simulation", "Sinks", _SINK, 1, 0,
             {},
             "Halt on nonzero", "⏹"),
    BlockDef("Terminator", "Sinks", _SINK, 1, 0,
             {},
             "Cap unconnected output", "⊣"),
    BlockDef("Outport",    "Sinks", _SINK, 1, 0,
             {"port_number": 1},
             "External output port", "→|"),
]

# ---------------------------------------------------------------------------
# 3. CONTINUOUS
# ---------------------------------------------------------------------------
_CONTINUOUS: list[BlockDef] = [
    BlockDef("Integrator",  "Continuous", _CONT, 1, 1,
             {"initial_condition": 0.0},
             "∫u dt", "1/s"),
    BlockDef("Integrator Limited", "Continuous", _CONT, 1, 1,
             {"initial_condition": 0.0, "upper": 1.0, "lower": -1.0},
             "Integrator with saturation", "1/s⌐"),
    BlockDef("Derivative",  "Continuous", _CONT, 1, 1,
             {},
             "du/dt", "du/dt"),
    BlockDef("Transfer Fcn", "Continuous", _CTRL, 1, 1,
             {"numerator": "[1]", "denominator": "[1,1]"},
             "Laplace transfer function", "N/D"),
    BlockDef("State-Space", "Continuous", _CTRL, 1, 1,
             {"A": "[[0,1],[-1,-2]]", "B": "[[0],[1]]",
              "C": "[[1,0]]", "D": "[[0]]"},
             "State-space model", "SS"),
    BlockDef("Zero-Pole",   "Continuous", _CTRL, 1, 1,
             {"zeros": "[]", "poles": "[-1]", "gain": 1.0},
             "Zeros, poles, gain form", "ZPK"),
    BlockDef("PID Controller", "Continuous", _CTRL, 1, 1,
             {"Kp": 1.0, "Ki": 0.0, "Kd": 0.0},
             "PID with anti-windup", "PID"),
    BlockDef("Transport Delay", "Continuous", _CONT, 1, 1,
             {"delay": 1.0},
             "Fixed time delay", "e⁻ˢᵀ"),
    BlockDef("Variable Transport Delay", "Continuous", _CONT, 2, 1,
             {"max_delay": 10.0},
             "Signal-controlled delay", "e⁻ˢᵀ~"),
]

# ---------------------------------------------------------------------------
# 4. DISCRETE
# ---------------------------------------------------------------------------
_DISCRETE: list[BlockDef] = [
    BlockDef("Unit Delay",  "Discrete", _DISC, 1, 1,
             {"initial_condition": 0.0, "sample_time": 0.01},
             "z⁻¹ delay", "z⁻¹"),
    BlockDef("Discrete Integrator", "Discrete", _DISC, 1, 1,
             {"method": "Forward Euler", "sample_time": 0.01, "initial_condition": 0.0},
             "Discrete-time integration", "Ts z/(z-1)"),
    BlockDef("Discrete Transfer Fcn", "Discrete", _DISC, 1, 1,
             {"numerator": "[1]", "denominator": "[1,-0.5]", "sample_time": 0.01},
             "z-domain transfer function", "N(z)/D(z)"),
    BlockDef("Discrete State-Space", "Discrete", _DISC, 1, 1,
             {"A": "[[0.9]]", "B": "[[0.1]]", "C": "[[1]]", "D": "[[0]]",
              "sample_time": 0.01},
             "Discrete state-space", "SS(z)"),
    BlockDef("Discrete Zero-Pole", "Discrete", _DISC, 1, 1,
             {"zeros": "[]", "poles": "[0.5]", "gain": 1.0, "sample_time": 0.01},
             "z-plane poles and zeros", "ZPK(z)"),
    BlockDef("Discrete PID Controller", "Discrete", _DISC, 1, 1,
             {"Kp": 1.0, "Ki": 0.0, "Kd": 0.0, "sample_time": 0.01},
             "Discrete-time PID", "PID(z)"),
    BlockDef("Zero-Order Hold", "Discrete", _DISC, 1, 1,
             {"sample_time": 0.01},
             "Sample and hold", "ZOH"),
    BlockDef("First-Order Hold", "Discrete", _DISC, 1, 1,
             {"sample_time": 0.01},
             "Linear interpolation hold", "FOH"),
    BlockDef("Tapped Delay", "Discrete", _DISC, 1, 1,
             {"num_delays": 3, "sample_time": 0.01, "initial_condition": 0.0},
             "N previous values", "z⁻ⁿ"),
    BlockDef("Discrete Filter", "Discrete", _DISC, 1, 1,
             {"numerator": "[1]", "denominator": "[1,-0.5]", "sample_time": 0.01},
             "IIR/FIR filter in z-domain", "H(z)"),
    BlockDef("Discrete FIR Filter", "Discrete", _DISC, 1, 1,
             {"coefficients": "[0.25,0.5,0.25]", "sample_time": 0.01},
             "FIR-specific filter", "FIR"),
]

# ---------------------------------------------------------------------------
# 5. MATH OPERATIONS
# ---------------------------------------------------------------------------
_MATH_OPS: list[BlockDef] = [
    BlockDef("Sum",        "Math Operations", _MATH, 2, 1,
             {"signs": "++"},
             "Add or subtract inputs", "Σ"),
    BlockDef("Gain",       "Math Operations", _MATH, 1, 1,
             {"gain": 1.0},
             "Multiply by constant", "K"),
    BlockDef("Product",    "Math Operations", _MATH, 2, 1,
             {},
             "Multiply or divide inputs", "×"),
    BlockDef("Dot Product", "Math Operations", _MATH, 2, 1,
             {},
             "Dot product of two vectors", "·"),
    BlockDef("Math Function", "Math Operations", _MATH, 1, 1,
             {"function": "exp"},
             "exp, log, sqrt, square, pow, abs", "f(u)"),
    BlockDef("Trigonometric Function", "Math Operations", _MATH, 1, 1,
             {"function": "sin"},
             "sin, cos, tan, asin, acos, atan", "trig"),
    BlockDef("Abs",        "Math Operations", _MATH, 1, 1,
             {},
             "Absolute value", "|u|"),
    BlockDef("Sign",       "Math Operations", _MATH, 1, 1,
             {},
             "Sign function", "sgn"),
    BlockDef("Sqrt",       "Math Operations", _MATH, 1, 1,
             {},
             "Square root", "√"),
    BlockDef("MinMax",     "Math Operations", _MATH, 2, 1,
             {"function": "min"},
             "Min or max of inputs", "min/max"),
    BlockDef("Algebraic Constraint", "Math Operations", _MATH, 1, 1,
             {},
             "Solve f(z) = 0", "f(z)=0"),
    BlockDef("Bias",       "Math Operations", _MATH, 1, 1,
             {"bias": 0.0},
             "Add constant offset", "+B"),
    BlockDef("Reshape",    "Math Operations", _MATH, 1, 1,
             {"output_dimensions": "[1]"},
             "Reshape signal dimensions", "↹"),
    BlockDef("Rounding Function", "Math Operations", _MATH, 1, 1,
             {"function": "round"},
             "floor, ceil, round, fix", "⌊⌉"),
    BlockDef("Slider Gain", "Math Operations", _MATH, 1, 1,
             {"gain": 1.0, "min": 0.0, "max": 10.0},
             "Interactive slider gain", "K↕"),
    BlockDef("Subtract",   "Math Operations", _MATH, 2, 1,
             {},
             "Subtract one signal from another", "−"),
    BlockDef("Unary Minus", "Math Operations", _MATH, 1, 1,
             {},
             "Negate input", "−u"),
]

# ---------------------------------------------------------------------------
# 6. DISCONTINUITIES
# ---------------------------------------------------------------------------
_DISCONTINUITIES: list[BlockDef] = [
    BlockDef("Saturation",  "Discontinuities", _NONL, 1, 1,
             {"lower": -1.0, "upper": 1.0},
             "Clip between bounds", "⌐⌐"),
    BlockDef("Saturation Dynamic", "Discontinuities", _NONL, 3, 1,
             {},
             "Dynamic saturation bounds", "⌐⌐~"),
    BlockDef("Dead Zone",   "Discontinuities", _NONL, 1, 1,
             {"lower": -0.1, "upper": 0.1},
             "Zero within range", "▬"),
    BlockDef("Dead Zone Dynamic", "Discontinuities", _NONL, 3, 1,
             {},
             "Dynamic dead zone bounds", "▬~"),
    BlockDef("Backlash",    "Discontinuities", _NONL, 1, 1,
             {"deadband": 1.0},
             "Mechanical backlash", "↔"),
    BlockDef("Relay",       "Discontinuities", _NONL, 1, 1,
             {"on_value": 1.0, "off_value": -1.0, "threshold": 0.0},
             "Switch between two values", "⇌"),
    BlockDef("Rate Limiter", "Discontinuities", _NONL, 1, 1,
             {"rising_slew": 1.0, "falling_slew": -1.0},
             "Slew rate limiter", "↗↘"),
    BlockDef("Rate Limiter Dynamic", "Discontinuities", _NONL, 3, 1,
             {},
             "Dynamic slew limiter", "↗↘~"),
    BlockDef("Coulomb & Viscous Friction", "Discontinuities", _NONL, 1, 1,
             {"coulomb": 1.0, "viscous": 0.1},
             "Static + dynamic friction", "μ"),
    BlockDef("Quantizer",   "Discontinuities", _NONL, 1, 1,
             {"interval": 0.5},
             "Round to quantization interval", "Q"),
    BlockDef("Hit Crossing", "Discontinuities", _NONL, 1, 1,
             {"threshold": 0.0, "direction": "either"},
             "Detect threshold crossing", "⨯"),
    BlockDef("Wrap To Zero", "Discontinuities", _NONL, 1, 1,
             {"threshold": 10.0},
             "Output zero if above threshold", "↩0"),
]

# ---------------------------------------------------------------------------
# 7. LOGIC AND BIT OPERATIONS
# ---------------------------------------------------------------------------
_LOGIC_OPS: list[BlockDef] = [
    BlockDef("Logical Operator", "Logic and Bit Operations", _LOGIC, 2, 1,
             {"operator": "AND"},
             "AND, OR, NOT, NAND, NOR, XOR, XNOR", "&&"),
    BlockDef("Relational Operator", "Logic and Bit Operations", _LOGIC, 2, 1,
             {"operator": "=="},
             "==, !=, <, >, <=, >=", "≡"),
    BlockDef("Bit Clear",  "Logic and Bit Operations", _LOGIC, 1, 1,
             {"bit": 0},
             "Clear a specific bit", "b̄"),
    BlockDef("Bit Set",    "Logic and Bit Operations", _LOGIC, 1, 1,
             {"bit": 0},
             "Set a specific bit", "b"),
    BlockDef("Bitwise Operator", "Logic and Bit Operations", _LOGIC, 2, 1,
             {"operator": "AND"},
             "AND, OR, XOR on bits", "&"),
    BlockDef("Shift Arithmetic", "Logic and Bit Operations", _LOGIC, 1, 1,
             {"direction": "left", "bits": 1},
             "Bit shift", "≪"),
    BlockDef("Detect Change", "Logic and Bit Operations", _LOGIC, 1, 1,
             {},
             "True when input changes", "Δ"),
    BlockDef("Detect Decrease", "Logic and Bit Operations", _LOGIC, 1, 1,
             {},
             "True when input decreases", "↓"),
    BlockDef("Detect Increase", "Logic and Bit Operations", _LOGIC, 1, 1,
             {},
             "True when input increases", "↑"),
    BlockDef("Detect Fall Negative", "Logic and Bit Operations", _LOGIC, 1, 1,
             {},
             "Falling edge below zero", "↓₋"),
    BlockDef("Detect Rise Positive", "Logic and Bit Operations", _LOGIC, 1, 1,
             {},
             "Rising edge above zero", "↑₊"),
    BlockDef("Combinatorial Logic", "Logic and Bit Operations", _LOGIC, 1, 1,
             {"truth_table": "[[0],[1]]"},
             "Truth table", "TT"),
    BlockDef("Compare To Constant", "Logic and Bit Operations", _LOGIC, 1, 1,
             {"operator": "==", "constant": 0.0},
             "Compare signal to constant", "≡K"),
    BlockDef("Compare To Zero", "Logic and Bit Operations", _LOGIC, 1, 1,
             {"operator": "=="},
             "Compare signal to zero", "≡0"),
    BlockDef("Extract Bits", "Logic and Bit Operations", _LOGIC, 1, 1,
             {"start_bit": 0, "num_bits": 8},
             "Extract bit range", "[n:m]"),
    BlockDef("Integer Delay", "Logic and Bit Operations", _LOGIC, 1, 1,
             {"delay_length": 1},
             "Delay by integer samples", "z⁻ⁿ"),
]

# ---------------------------------------------------------------------------
# 8. LOOKUP TABLES
# ---------------------------------------------------------------------------
_LOOKUP_TABLES: list[BlockDef] = [
    BlockDef("Lookup Table 1-D", "Lookup Tables", _LUT, 1, 1,
             {"input_values": "[0,1,2]", "output_values": "[0,1,4]"},
             "1-D data table", "T₁"),
    BlockDef("Lookup Table 2-D", "Lookup Tables", _LUT, 2, 1,
             {},
             "2-D data table", "T₂"),
    BlockDef("Lookup Table n-D", "Lookup Tables", _LUT, 1, 1,
             {},
             "N-dimensional lookup", "Tₙ"),
    BlockDef("Cosine",      "Lookup Tables", _LUT, 1, 1,
             {},
             "Lookup-based cosine", "cos"),
    BlockDef("Sine (Lookup)", "Lookup Tables", _LUT, 1, 1,
             {},
             "Lookup-based sine", "sin"),
    BlockDef("Lookup Table Dynamic", "Lookup Tables", _LUT, 3, 1,
             {},
             "Dynamic 1-D lookup", "T~"),
    BlockDef("Interpolation Using Prelookup", "Lookup Tables", _LUT, 1, 1,
             {},
             "Index-based interpolation", "⇢"),
    BlockDef("Prelookup",   "Lookup Tables", _LUT, 1, 1,
             {},
             "Compute index and fraction", "idx"),
    BlockDef("Direct Lookup Table", "Lookup Tables", _LUT, 1, 1,
             {},
             "Index-based direct lookup", "T[]"),
]

# ---------------------------------------------------------------------------
# 9. SIGNAL ROUTING
# ---------------------------------------------------------------------------
_SIGNAL_ROUTING: list[BlockDef] = [
    BlockDef("Bus Creator",  "Signal Routing", _ROUTE, 2, 1,
             {"num_inputs": 2},
             "Combine signals into bus", "{ }"),
    BlockDef("Bus Selector", "Signal Routing", _ROUTE, 1, 2,
             {"num_outputs": 2},
             "Extract from bus", "} {"),
    BlockDef("Mux",         "Signal Routing", _ROUTE, 2, 1,
             {"num_inputs": 2},
             "Combine into vector", "⊕"),
    BlockDef("Demux",       "Signal Routing", _ROUTE, 1, 2,
             {"num_outputs": 2},
             "Split vector", "⊖"),
    BlockDef("Switch",      "Signal Routing", _ROUTE, 3, 1,
             {"threshold": 0.0},
             "Select input 1 or 3 by input 2", "⇋"),
    BlockDef("Multiport Switch", "Signal Routing", _ROUTE, 3, 1,
             {"num_inputs": 3},
             "Select one of N inputs", "M⇋"),
    BlockDef("Manual Switch", "Signal Routing", _ROUTE, 2, 1,
             {"position": 0},
             "Toggle between two inputs", "↕"),
    BlockDef("Merge",       "Signal Routing", _ROUTE, 2, 1,
             {},
             "Merge conditionally executed outputs", "∪"),
    BlockDef("Selector",    "Signal Routing", _ROUTE, 1, 1,
             {"indices": "[1]"},
             "Select vector elements", "[]"),
    BlockDef("Index Vector", "Signal Routing", _ROUTE, 2, 1,
             {},
             "Select one of N inputs by index", "i→"),
    BlockDef("Data Store Memory", "Signal Routing", _ROUTE, 0, 0,
             {"name": "A"},
             "Shared memory definition", "DS"),
    BlockDef("Data Store Read",  "Signal Routing", _ROUTE, 0, 1,
             {"name": "A"},
             "Read from data store", "DS→"),
    BlockDef("Data Store Write", "Signal Routing", _ROUTE, 1, 0,
             {"name": "A"},
             "Write to data store", "→DS"),
    BlockDef("From",        "Signal Routing", _ROUTE, 0, 1,
             {"tag": "A"},
             "Receive from Goto block", "[A]→"),
    BlockDef("Goto",        "Signal Routing", _ROUTE, 1, 0,
             {"tag": "A"},
             "Send to From blocks", "→[A]"),
    BlockDef("Goto Tag Visibility", "Signal Routing", _ROUTE, 0, 0,
             {"tag": "A"},
             "Define Goto/From scope", "[A]"),
]

# ---------------------------------------------------------------------------
# 10. PORTS AND SUBSYSTEMS
# ---------------------------------------------------------------------------
_PORTS_SUBSYSTEMS: list[BlockDef] = [
    BlockDef("Subsystem",          "Ports and Subsystems", _PORT, 1, 1,
             {},
             "Encapsulated group of blocks", "⊞"),
    BlockDef("Enabled Subsystem",  "Ports and Subsystems", _PORT, 2, 1,
             {},
             "Runs when enable > 0", "⊞ₑ"),
    BlockDef("Triggered Subsystem","Ports and Subsystems", _PORT, 2, 1,
             {},
             "Runs on trigger edge", "⊞ₜ"),
    BlockDef("Function-Call Subsystem", "Ports and Subsystems", _PORT, 1, 1,
             {},
             "Runs on function call", "⊞ₓ"),
    BlockDef("For Iterator Subsystem", "Ports and Subsystems", _PORT, 1, 1,
             {"iterations": 10},
             "Fixed iteration loop", "for"),
    BlockDef("While Iterator Subsystem", "Ports and Subsystems", _PORT, 1, 1,
             {},
             "Conditional loop", "while"),
    BlockDef("If",                 "Ports and Subsystems", _PORT, 1, 2,
             {"condition": "u1 > 0"},
             "If-else control flow", "if"),
    BlockDef("Switch Case",        "Ports and Subsystems", _PORT, 1, 2,
             {},
             "Switch-case control flow", "case"),
    BlockDef("Atomic Subsystem",   "Ports and Subsystems", _PORT, 1, 1,
             {},
             "Nonvirtual subsystem", "⊞ₐ"),
    BlockDef("Model",              "Ports and Subsystems", _PORT, 1, 1,
             {"model_name": ""},
             "Reference another model", "Mdl"),
]

# ---------------------------------------------------------------------------
# 11. SIGNAL ATTRIBUTES
# ---------------------------------------------------------------------------
_SIGNAL_ATTRIBUTES: list[BlockDef] = [
    BlockDef("Data Type Conversion", "Signal Attributes", _SATTR, 1, 1,
             {"output_type": "double"},
             "Convert signal type", "⟹"),
    BlockDef("Data Type Duplicate",  "Signal Attributes", _SATTR, 2, 1,
             {},
             "Force same type", "==T"),
    BlockDef("Signal Conversion",    "Signal Attributes", _SATTR, 1, 1,
             {},
             "Virtual/nonvirtual bus", "↔"),
    BlockDef("Signal Specification", "Signal Attributes", _SATTR, 1, 1,
             {},
             "Enforce type/size/rate", "spec"),
    BlockDef("IC",                   "Signal Attributes", _SATTR, 1, 1,
             {"value": 0.0},
             "Initial condition", "IC"),
    BlockDef("Rate Transition",      "Signal Attributes", _SATTR, 1, 1,
             {},
             "Cross sample-rate boundary", "R↔"),
    BlockDef("Probe",                "Signal Attributes", _SATTR, 1, 1,
             {},
             "Output signal attributes", "?"),
    BlockDef("Width",                "Signal Attributes", _SATTR, 1, 1,
             {},
             "Output signal width", "W"),
]

# ---------------------------------------------------------------------------
# 12. MODEL VERIFICATION
# ---------------------------------------------------------------------------
_MODEL_VERIFICATION: list[BlockDef] = [
    BlockDef("Assertion",            "Model Verification", _VERIF, 1, 0,
             {},
             "Stop if condition false", "!"),
    BlockDef("Check Static Lower Bound", "Model Verification", _VERIF, 1, 0,
             {"bound": 0.0},
             "Verify signal ≥ bound", "≥"),
    BlockDef("Check Static Upper Bound", "Model Verification", _VERIF, 1, 0,
             {"bound": 1.0},
             "Verify signal ≤ bound", "≤"),
    BlockDef("Check Static Range",   "Model Verification", _VERIF, 1, 0,
             {"lower": 0.0, "upper": 1.0},
             "Verify signal within range", "[a,b]"),
    BlockDef("Check Dynamic Lower Bound", "Model Verification", _VERIF, 2, 0,
             {},
             "Dynamic lower bound check", "≥~"),
    BlockDef("Check Dynamic Upper Bound", "Model Verification", _VERIF, 2, 0,
             {},
             "Dynamic upper bound check", "≤~"),
    BlockDef("Check Dynamic Range",  "Model Verification", _VERIF, 3, 0,
             {},
             "Dynamic range check", "[~]"),
]

# ---------------------------------------------------------------------------
# 13. USER-DEFINED FUNCTIONS
# ---------------------------------------------------------------------------
_USER_DEFINED: list[BlockDef] = [
    BlockDef("MATLAB Function",     "User-Defined Functions", _UDEF, 1, 1,
             {"code": "y = u"},
             "Custom MATLAB/Python function", "fcn"),
    BlockDef("Simulink Function",   "User-Defined Functions", _UDEF, 1, 1,
             {},
             "Callable Simulink function", "f()"),
    BlockDef("Function Caller",     "User-Defined Functions", _UDEF, 1, 1,
             {"function_name": ""},
             "Call a Simulink Function", "call"),
    BlockDef("S-Function",          "User-Defined Functions", _UDEF, 1, 1,
             {},
             "Custom C/Python block", "S"),
    BlockDef("S-Function Builder",  "User-Defined Functions", _UDEF, 1, 1,
             {},
             "GUI for S-Functions", "S+"),
    BlockDef("Initialize Function",  "User-Defined Functions", _UDEF, 0, 0,
             {},
             "Runs once at sim start", "init"),
    BlockDef("Terminate Function",   "User-Defined Functions", _UDEF, 0, 0,
             {},
             "Runs once at sim end", "term"),
    BlockDef("Reset Function",       "User-Defined Functions", _UDEF, 0, 0,
             {},
             "Runs on reset event", "rst"),
]


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

ALL_CATEGORIES: list[tuple[str, list[BlockDef]]] = [
    ("Sources",                  _SOURCES),
    ("Sinks",                    _SINKS),
    ("Continuous",               _CONTINUOUS),
    ("Discrete",                 _DISCRETE),
    ("Math Operations",          _MATH_OPS),
    ("Discontinuities",          _DISCONTINUITIES),
    ("Logic and Bit Operations", _LOGIC_OPS),
    ("Lookup Tables",            _LOOKUP_TABLES),
    ("Signal Routing",           _SIGNAL_ROUTING),
    ("Ports and Subsystems",     _PORTS_SUBSYSTEMS),
    ("Signal Attributes",        _SIGNAL_ATTRIBUTES),
    ("Model Verification",       _MODEL_VERIFICATION),
    ("User-Defined Functions",   _USER_DEFINED),
]
"""Ordered list of (category_name, block_definitions)."""


# Flat lookup by block type name.
BLOCK_BY_TYPE: dict[str, BlockDef] = {}
for _cat_name, _blocks in ALL_CATEGORIES:
    for _bdef in _blocks:
        BLOCK_BY_TYPE[_bdef.type] = _bdef


# Legacy type aliases for backward compatibility with saved .sim files.
_LEGACY_ALIASES: dict[str, str] = {
    "Sine":             "Sine Wave",
    "ToWorkspace":      "To Workspace",
    "TransferFunction": "Transfer Fcn",
    "StateSpace":       "State-Space",
    "PID":              "PID Controller",
    "DeadZone":         "Dead Zone",
    "LookupTable":      "Lookup Table 1-D",
}


def resolve_type(raw_type: str) -> str:
    """Return the canonical block type, resolving legacy aliases."""
    return _LEGACY_ALIASES.get(raw_type, raw_type)


def get_block_def(block_type: str) -> BlockDef | None:
    """Look up a block definition by type name (with legacy alias support)."""
    canonical = resolve_type(block_type)
    return BLOCK_BY_TYPE.get(canonical)


# Category and type sets used by the simulator and canvas validation.
SOURCE_TYPES: frozenset[str] = frozenset(b.type for b in _SOURCES)
SINK_TYPES: frozenset[str] = frozenset(b.type for b in _SINKS)
