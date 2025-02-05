#!/bin/bash

set -e
set -x

# call script from module directory
BASEDIR=$(pwd)
pushd "$BASEDIR"

rm -rf build
mkdir build

# detect conan binary when run during docker build
if [ -f "/root/.local/bin/conan" ]; then
    CONAN_BIN=/root/.local/bin/conan
else
    CONAN_BIN=conan
fi

# install common libs
$CONAN_BIN install ../../../libs/thirdparty --update --output-folder=build --build=missing

# install project specific libs
$CONAN_BIN install . --update --output-folder=build --build=missing

cd build
cmake .. -GNinja -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake -DCMAKE_BUILD_TYPE=Release
cmake --build . -j$(nproc)
