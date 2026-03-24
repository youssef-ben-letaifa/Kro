#!/usr/bin/env bash

failures=()

if [ ! -f .venv/bin/activate ]; then
  echo "FAIL: .venv/bin/activate not found"
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate
export MPLCONFIGDIR="${MPLCONFIGDIR:-$PWD/.venv/mplconfig}"
mkdir -p "$MPLCONFIGDIR"

echo "→ Running py_compile checks..."
while IFS= read -r -d '' file; do
  python -m py_compile "$file"
  if [ $? -eq 0 ]; then
    echo "PASS: $file"
  else
    echo "FAIL: $file"
    failures+=("py_compile:$file")
  fi
done < <(find kronos -type f -name "*.py" -print0)

run_check() {
  local label="$1"
  local cmd="$2"
  python -c "$cmd"
  if [ $? -eq 0 ]; then
    echo "PASS: $label"
  else
    echo "FAIL: $label"
    failures+=("$label")
  fi
}

echo "→ Running import checks..."
run_check "PyQt6 OK" "import PyQt6; print('PyQt6 OK')"
run_check "QScintilla OK" "import PyQt6.Qsci; print('QScintilla OK')"
run_check "qtconsole OK" "import qtconsole; print('qtconsole OK')"
run_check "matplotlib OK" "import matplotlib; print('matplotlib OK')"
run_check "python-control OK" "import control; print('python-control OK')"
run_check "numpy OK" "import numpy; print('numpy OK')"
run_check "scipy OK" "import scipy; print('scipy OK')"
run_check "sympy OK" "import sympy; print('sympy OK')"
run_check "psutil OK" "import psutil; print('psutil OK')"
run_check "Toolbar OK" "from kronos.ui.toolbar import KronosToolBar; print('Toolbar OK')"
run_check "StatusBar OK" "from kronos.ui.statusbar import KronosStatusBar; print('StatusBar OK')"
run_check "Aeon Canvas OK" "from kronos.ui.center.aeon.canvas import AeonCanvas; print('Aeon Canvas OK')"
run_check "Aeon Simulator OK" "from kronos.ui.center.aeon.simulator import DiagramSimulator; print('Aeon Simulator OK')"
run_check "Block Param Dialog OK" "from kronos.ui.center.aeon.block_param_dialog import BlockParamDialog; print('Block Param Dialog OK')"
run_check "Bode Wizard OK" "from kronos.ui.dialogs.bode_wizard import BodeWizardDialog; print('Bode Wizard OK')"
run_check "PID Tuner OK" "from kronos.ui.dialogs.pid_tuner import PIDTunerDialog; print('PID Tuner OK')"
run_check "Step Response OK" "from kronos.ui.dialogs.step_response_dialog import StepResponseDialog; print('Step Response OK')"
run_check "Ribbon OK" "from kronos.ui.ribbon import MatlabRibbon; print('Ribbon OK')"
run_check "MainWindow import OK" "from kronos.ui.mainwindow import MainWindow; print('MainWindow import OK')"
run_check "SettingsManager OK" "from kronos.engine.settings_manager import SettingsManager; print('SettingsManager OK')"
run_check "SettingsDialog OK" "from kronos.ui.dialogs.settings_dialog import SettingsDialog; print('SettingsDialog OK')"
run_check "AboutDialog OK" "from kronos.ui.dialogs.about_dialog import AboutDialog; print('AboutDialog OK')"
run_check "SplashScreen OK" "from kronos.ui.splash_screen import KronosSplashScreen; print('SplashScreen OK')"
run_check "RootLocusDialog OK" "from kronos.ui.dialogs.root_locus_dialog import RootLocusDialog; print('RootLocusDialog OK')"
run_check "LQRDesigner OK" "from kronos.ui.dialogs.lqr_designer import LQRDesignerDialog; print('LQRDesigner OK')"
run_check "FrequencyAnalyzer OK" "from kronos.ui.dialogs.frequency_analyzer import FrequencyAnalyzerDialog; print('FrequencyAnalyzer OK')"

if [ ${#failures[@]} -eq 0 ]; then
  echo "✅ All checks passed — run: python -m kronos.main"
  exit 0
fi

echo "Checks failed:"
for item in "${failures[@]}"; do
  echo " - $item"
done
exit 1
