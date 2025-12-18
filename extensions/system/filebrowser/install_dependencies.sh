#!/bin/bash

set -e

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
pushd $SCRIPT_DIR

mkdir -p filebrowser
cd filebrowser
wget https://github.com/filebrowser/filebrowser/releases/download/v2.32.0/linux-amd64-filebrowser.tar.gz
tar -xf linux-amd64-filebrowser.tar.gz
rm linux-amd64-filebrowser.tar.gz
