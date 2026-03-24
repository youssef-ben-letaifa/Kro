# Running Kronos

## Install
bash install.sh

## Verify
bash verify.sh

## Launch
source .venv/bin/activate
python -m kronos.main

## If PyQt6 display error on Linux:
export QT_QPA_PLATFORM=xcb
python -m kronos.main

## If libGL error:
export LIBGL_ALWAYS_SOFTWARE=1
python -m kronos.main
