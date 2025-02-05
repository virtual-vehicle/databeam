#!/bin/bash

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
pushd $SCRIPT_DIR

python3 install_js_libs.py
