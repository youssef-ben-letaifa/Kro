# Kronos v1.0 UI Audit

## Scope

Audited primary interactive surfaces used in normal workflows:
- `kronos/ui/mainwindow.py`
- `kronos/ui/ribbon.py`
- `kronos/ui/aeon_window.py`
- `kronos/toolboxes/signal_analyzer/signal_analyzer_window.py`
- Supporting dialogs under `kronos/ui/dialogs/`

## Main Window

### Menus
- File: New, Open, Save, Save As, Recent Files, Exit
- Edit: Undo, Redo, Find, Replace
- Run: Run File, Stop Kernel, Restart Kernel
- Tools: Bode Wizard, Step Response, Root Locus, PID Tuner, LQR Designer, Frequency Analyzer, Preferences
- Help: Documentation, About

### Status after stabilization
- Wired and operational: New/Open/Save/Save As, Undo/Redo, Run/Stop/Restart, control dialogs, Preferences, About, Documentation.
- Disabled with tooltip (`Coming soon`): Find, Replace.
- Recent file actions tested for open/clear paths.

## Ribbon (Main IDE)

### Enabled functional actions
- New/Open/Save
- Undo/Redo
- Workspace clear/show and panel navigation
- Run / Run+Time / Run Section
- Toolboxes / Preferences / About
- Aeon launcher

### Explicitly disabled (`Coming soon`)
- File import/new variable/analyze/add-ons placeholders
- Plot-construction placeholders (2D/3D/statistics/polar ribbon plot buttons)
- ML/AI app placeholders
- Live Editor placeholders
- Debug placeholders
- Path row navigation placeholders (Back/Forward/Up/Parent/Home)
- Quantum and Symbolic placeholder buttons

## Aeon Window

### Interactive controls
- Simulate, Stop, Validate, Auto Arrange, Clear, Save `.sim`, Load `.sim`, Fit View
- Connect mode toggle, Snap mode toggle
- Block parameter editor (double-click)

### Stabilization changes
- Added cooperative stop handling for simulation worker via interruption checks.
- Added close-time simulation-thread shutdown guard to prevent `QThread: Destroyed while thread is still running` abort.

## Signal Analyzer Toolbox

### Interactive controls
- Ribbon actions for session/file operations, display layout, signal actions, filtering, smoothing, views, measurement actions, export/script generation.
- Signal tree context menu: Rename, Duplicate, Delete, Send to Workspace, Export, Open Multiresolution Analyzer.
- Workspace double-click import.

### Status after stabilization
- Ribbon dispatch is wrapped with exception boundary and returns non-crashing user feedback.
- Representative full action sweep completed in offscreen smoke run with no exceptions.

## Crash Fixes Applied

- `python-control` API compatibility:
  - `ct.pole(...)` -> `ct.poles(...)`
  - `ct.zero(...)` -> `ct.zeros(...)`
- Applied in:
  - `kronos/ui/dialogs/pid_tuner.py`
  - `kronos/ui/dialogs/root_locus_dialog.py`
  - `kronos/ui/right_panel.py`
- Fixed infinite phase-margin overflow in system analysis progress bar update.

## Verification

- Automated tests: `21 passed` (`tests/`)
- Headless smokes executed for:
  - MainWindow dialog/menu/ribbon paths
  - Signal Analyzer ribbon action sweep
  - Aeon run/stop/close lifecycle
