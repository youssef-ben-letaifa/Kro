# Kronos IDE

Kronos is an open-source, Python-native scientific simulation IDE built with PyQt6.  
It combines a code editor, an embedded IPython console, plotting tools, block-diagram simulation (Aeon), and extensible engineering toolboxes (including an Autonomous Driving Toolbox).

## Highlights

- MATLAB-inspired desktop workflow (ribbon, panels, command window, figures).
- Embedded IPython kernel for interactive computation.
- Python editor with QScintilla (fallback editor if QScintilla is unavailable).
- Aeon block-diagram simulation engine for control/systems workflows.
- Dynamic toolbox loader (`kronos/toolboxes`) with runtime discovery.
- Optional native C++ acceleration via `pybind11` + Qt (`kronos_cpp`).

## Repository Layout

```text
Kro/
  kronos/
    main.py                    # App entrypoint
    engine/                    # Kernel bridge, routing, plots, settings, workspace
    ui/                        # Main window, panels, editor, Aeon canvas, dialogs, theming
    toolboxes/                 # Pluggable toolboxes (Autonomous Driving Toolbox included)
    native/                    # Python bridge to compiled native modules
  kronos_cpp/                  # C++/Qt native extension sources + CMake build
  tests/                       # Unit and smoke tests
  install.sh                   # Linux installation helper
  verify.sh                    # Environment and import validation script
  pyproject.toml               # Packaging metadata and dependencies
```

## Prerequisites

- Python 3.11+
- Linux desktop with Qt/OpenGL runtime support (for full GUI features)
- Build tools if compiling native modules (`cmake`, compiler toolchain, `pybind11`)

`install.sh` installs distro dependencies (Debian/Ubuntu/Parrot family), creates `.venv`, installs Python packages, and builds native modules.

## Quick Start

### Option A: Use installer (recommended on supported Linux distros)

```bash
bash install.sh
```

### Option B: Manual setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip wheel setuptools
pip install -e .
```

### Launch

```bash
source .venv/bin/activate
python -m kronos.main
```

You can also use the console script:

```bash
kronos
```

## Verification and Tests

Run built-in environment/import checks:

```bash
bash verify.sh
```

Run Python tests:

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

## Architecture

### 1) App Shell (`kronos/main.py`, `kronos/ui/mainwindow.py`)

- Starts `QApplication`, splash screen, and main desktop window.
- Builds the panel layout (left explorer, center editor/Aeon, right workspace, bottom console/figures).
- Wires UI actions to engine services and toolbox loading.

### 2) Execution Engine (`kronos/engine`)

- `kernel_bridge.py`: submits code/files to IPython kernel and emits execution/output/error signals.
- `kernel_message_router.py`: centralized IOPub message dispatch by `msg_id`.
- `workspace_manager.py`: queries `%whos`, parses variables, and updates workspace state.
- `plot_manager.py`: kernel-side matplotlib export code generation + manifest parsing.
- `settings_manager.py`: persistent user settings via `QSettings`.

### 3) UI Layer (`kronos/ui`)

- `bottom/console_panel.py`: embedded qtconsole kernel widget and command window UX.
- `center/editor.py`: code editor + Aeon simulator integration.
- `center/aeon/*`: block library, canvas, wiring, and simulation runtime.
- `theme/*`: stylesheet, design tokens, icon mapping.

### 4) Toolbox System (`kronos/toolboxes`)

- `registry.py` discovers toolboxes from directories and dynamically imports them.
- Supports toolbox directory names with spaces via generated module aliases.
- Current bundled toolbox: `Autonomous Driving Toolbox` with 2D/3D views, ADAS, sensor/perception simulation, and HD map ingestion.

### 5) Native Bridge (`kronos/native`, `kronos_cpp`)

- `kronos_cpp` builds `kronos_native` / `kronos_physics` modules with `pybind11`.
- `kronos/native/__init__.py` exposes safe wrappers and graceful Python fallbacks if native modules are unavailable.

## Common Runtime Notes

- If Qt display backend fails on Linux:

```bash
export QT_QPA_PLATFORM=xcb
python -m kronos.main
```

- If OpenGL issues appear:

```bash
export LIBGL_ALWAYS_SOFTWARE=1
python -m kronos.main
```

## Git Ignore Note

This repository includes a `.gitignore` that excludes Python caches (`__pycache__`, `*.pyc`), virtualenvs, build outputs, and common tooling artifacts.  
If cache files were already tracked before adding `.gitignore`, untrack them once with:

```bash
git rm -r --cached -- ':(glob)**/__pycache__/**' ':(glob)**/*.pyc'
```
