#!/bin/bash

set -e

# check if we are being run in docker
if [ "$DBDOCKERBUILD" != "yes" ]; then
    echo "This script is not intended to be run locally, but in manylinux docker image"
    exit 1
fi

PY_VERSIONS=("$@")  # all arguments as array

if [ ${#PY_VERSIONS[@]} -eq 0 ]; then
    echo "Usage: $0 <python_version> [<python_version> ...]"
    echo "Example:"
    echo " $0 cp310-cp310 cp311-cp311 cp312-cp312 cp313-cp313"
    exit 1
fi

cd /src

echo "Make sure MCAP-CLI is available..."
/opt/python/cp312-cp312/bin/python3 -m pip install requests
/opt/python/cp312-cp312/bin/python3 src/download_mcap_cli.py

echo "Building wheel package..."
for PYVER in "${PY_VERSIONS[@]}"; do
    printf "\n\n"
    PY_BIN=/opt/python/$PYVER/bin/python3
    echo "Building for $PYVER with $PY_BIN..."
    $PY_BIN -m venv /venvs/$PYVER
    /venvs/$PYVER/bin/python3 -m pip install conan build
    /venvs/$PYVER/bin/conan profile detect --force
    /venvs/$PYVER/bin/conan install . --update --output-folder=build --build=missing -g CMakeDeps -g CMakeToolchain -s compiler.cppstd=20
    /venvs/$PYVER/bin/python3 -m build --wheel --outdir /src/dist_temp
    rm -rf ./build
done

echo "Checking wheels with auditwheel"

mkdir -p /src/dist
for whl in /src/dist_temp/*-linux_*.whl; do
    auditwheel repair "$whl" --wheel-dir /src/dist
done

rm -rf /src/dist_temp

chmod -R a+rw /src/dist

echo "Wheels built successfully in dist:"
ls -1 /src/dist
