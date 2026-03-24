#!/usr/bin/env bash
set -e

echo "→ Detecting Linux distribution..."
if [ ! -f /etc/os-release ]; then
  echo "Unsupported system: /etc/os-release not found."
  exit 1
fi

source /etc/os-release
DISTRO_ID="${ID:-unknown}"
DISTRO_LIKE="${ID_LIKE:-}"

case "${DISTRO_ID}" in
  debian|ubuntu|parrot)
    ;;
  *)
    if [[ "${DISTRO_LIKE}" != *debian* ]] && [[ "${DISTRO_LIKE}" != *ubuntu* ]]; then
      echo "Unsupported distribution: ${DISTRO_ID}"
      exit 1
    fi
    ;;
esac

echo "→ Installing system dependencies..."
sudo apt-get update -qq
if sudo apt-get install -y \
  python3.11 python3.11-venv python3.11-dev \
  python3-pip \
  cmake \
  pybind11-dev \
  libqt6-dev qt6-base-dev \
  gfortran \
  liblapack-dev \
  libopenblas-dev \
  libxcb-xinerama0 \
  libxcb-cursor0 \
  libgl1 \
  libglib2.0-0; then
  :
else
  echo "→ Falling back to distro package names..."
  sudo apt-get install -y \
    python3 python3-venv python3-dev \
    python3-pip \
    cmake \
    pybind11-dev \
    qt6-base-dev \
    gfortran \
    liblapack-dev \
    libopenblas-dev \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libgl1 \
    libglib2.0-0
fi

echo "→ Creating virtual environment..."
if command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="python3.11"
else
  PYTHON_BIN="python3"
fi

"${PYTHON_BIN}" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11+ is required.")
PY

"${PYTHON_BIN}" -m venv .venv

echo "→ Activating virtual environment..."
# shellcheck disable=SC1091
source .venv/bin/activate

echo "→ Upgrading pip tooling..."
pip install --upgrade pip wheel setuptools

echo "→ Installing Python dependencies..."
pip install PyQt6==6.6.1
pip install PyQt6-Qt6==6.6.1
pip install PyQt6-sip
pip install PyQt6-QScintilla
pip install pybind11
pip install -e .

echo "→ Building native C++ Qt extensions..."
if [ -d kronos_cpp ]; then
  cd kronos_cpp
  mkdir -p build
  cd build
  cmake .. -DCMAKE_BUILD_TYPE=Release
  make -j"$(nproc)"
  mkdir -p ../../kronos/native
  cp kronos_native*.so ../../kronos/native/ 2>/dev/null || true
  cd ../..
fi

echo "→ Creating launch wrapper..."
INSTALL_DIR="$(pwd)"
sudo tee /usr/local/bin/kronos >/dev/null <<EOF
#!/bin/bash
source "${INSTALL_DIR}/.venv/bin/activate"
python -m kronos.main "\$@"
EOF
sudo chmod +x /usr/local/bin/kronos

echo ""
echo "✅ Kronos installed successfully."
echo "👉 Run: source .venv/bin/activate && python -m kronos.main"
