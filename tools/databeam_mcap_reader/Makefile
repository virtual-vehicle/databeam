# Makefile for databeam_mcap_reader Python package

PYTHON_USED ?= python3
PYTHON_DEV_EXECUTABLE := $(shell which $(PYTHON_USED))
PYTHON_DEV_EXECUTABLE_VERSION := $(shell $(PYTHON_USED) --version)
PYTHON_BASE_PATH := $(shell $(PYTHON_DEV_EXECUTABLE) -m site --user-base)
CONAN_BIN := $(shell if [ -f "/root/.local/bin/conan" ]; then echo "/root/.local/bin/conan"; else echo "$(PYTHON_BASE_PATH)/bin/conan"; fi)
DEV_DEBUG ?= 1

BUILD_IMAGE := quay.io/pypa/manylinux_2_34_x86_64
BUILD_VERSIONS ?= cp310-cp310 cp311-cp311 cp312-cp312 cp313-cp313 cp314-cp314

# Default target
.DEFAULT_GOAL := help

# Help target
.PHONY: help
help:
	@echo "Available targets:"
	@echo "  linux_wheels    - Build Python wheel packages for Linux"
	@echo "                    specify BUILD_VERSIONS to override default:"
	@echo "                    >  BUILD_VERSIONS=cp312-cp312 make linux_wheels"
	@echo "  dev             - Build development C++ extension"
	@echo "  dev_quickbuild  - Rebuild development C++ extension"
	@echo "  clean           - Clean all build artifacts"
	@echo ""
	@echo "Available environment variables:"
	@echo "  PYTHON_USED     - Python version to use (default: $(PYTHON_USED), e.g. \"python3.12\")"

# Build Python wheel packages for multiple Python versions using Docker
.PHONY: linux_wheels
linux_wheels:
	@echo "Preparing to build wheel packages for Linux..."
	docker pull $(BUILD_IMAGE)
	docker run --rm -e DBDOCKERBUILD=yes -e BUILD_VERSIONS="$(BUILD_VERSIONS)" -v $(shell pwd):/src $(BUILD_IMAGE) /bin/bash -c "cd /src && make docker_wheels"

# Build Python wheel package
.PHONY: docker_wheels
docker_wheels: clean-wheel
	@printf "Building wheel packages for Linux: $(BUILD_VERSIONS)\n"
	./build_wheels_manylinux.sh $(BUILD_VERSIONS)

.PHONY: _prompt
_prompt:
	@printf "\nPython version to be used: <$(PYTHON_DEV_EXECUTABLE)> version: <$(PYTHON_DEV_EXECUTABLE_VERSION)>\n\n"
	@printf "Specify by calling:\n    PYTHON_USED=python3.12 make dev\n\n"
	@printf "Debug output (DEV_DEBUG): $(DEV_DEBUG)\n\n"
	@bash -c "read -n 1 -p \"(abort with CTRL+C, continue with Return)\" foo"

# Build development C++ extension
.PHONY: dev
dev: _prompt clean-dev
	@echo "Building development C++ extension for Python: <$(PYTHON_DEV_EXECUTABLE)> version: <$(PYTHON_DEV_EXECUTABLE_VERSION)>"
	$(CONAN_BIN) install . --update --output-folder=build_dev --build=missing -g CMakeDeps -g CMakeToolchain -s compiler.cppstd=20
	cmake -S . -B build_dev -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake -DCMAKE_BUILD_TYPE=Release -DPYTHON_EXECUTABLE=$(PYTHON_DEV_EXECUTABLE) -DDEBUG_OUTPUT=$(DEV_DEBUG)
	cmake --build build_dev -j$$(nproc)
	cp build_dev/_core.*.so src/databeam_mcap_reader/
	@echo "Development build completed in build_dev/"
	@echo "Import for testing: import build_dev._core as mr"

# quickly rebuild development C++ extension
.PHONY: dev_quickbuild
dev_quickbuild:
	@echo "Quick-building development C++ extension..."
	cmake --build build_dev -j$$(nproc)
	cp build_dev/_core.*.so src/databeam_mcap_reader/

# Clean all build artifacts
.PHONY: clean
clean: clean-wheel clean-dist clean-dev
	rm -rf ./mcap_cli
	@echo "All build artifacts cleaned"

# Clean wheel build artifacts
.PHONY: clean-wheel
clean-wheel:
	@echo "Cleaning wheel build artifacts..."
	rm -rf ./build
	rm -rf ./dist_temp

.PHONY: clean-dist
clean-dist:
	@echo "Cleaning wheel dist artifacts..."
	rm -rf ./dist

# Clean development build artifacts
.PHONY: clean-dev
clean-dev:
	@echo "Cleaning development build artifacts..."
	rm -rf ./build_dev
	rm -f ./src/databeam_mcap_reader/_core.*.so
