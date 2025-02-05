#!/bin/bash

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
pushd $SCRIPT_DIR

mkdir -p static/js/libs
cd static/js/libs
curl -L -O https://raw.githubusercontent.com/brillout/forge-sha256/master/build/forge-sha256.min.js
