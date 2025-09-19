#!/bin/bash

set -e

python3.12 -m venv .venv_test_wheel
. ./.venv_test_wheel/bin/activate

pip install dist/databeam_mcap_reader-*-cp312-cp312-*linux*.whl

echo ""
echo "running test_wheel.py ..."
echo ""
python3.12 test_wheel.py

deactivate
rm -rf .venv_test_wheel
echo "done"
