#!make

ifneq (,$(wildcard ./.env))
	include .env
    export
endif

# default platform:
# PLATFORM ?= linux/amd64,linux/arm64
PLATFORM ?= linux/amd64
MODE ?= push
DOCKER_REGISTRY ?= docker.io
TAG_ROOT ?= $(DOCKER_REGISTRY)/$(DOCKER_TAG_PREFIX)

# relative path in repo, subfolders here contain modules
MODULE_ROOT = extensions/io_modules
# select all subfolders which contain Dockerfiles
MODULES = $(wildcard $(MODULE_ROOT)/*/Dockerfile)
# strip path from selected modules to create nice make targets
MODULE_TARGETS = $(patsubst $(MODULE_ROOT)/%/Dockerfile,module-%, $(MODULES))

# system components are handled like modules
SYSCOMP_ROOT = extensions/system
SYSCOMPONENTS = $(wildcard $(SYSCOMP_ROOT)/*/Dockerfile)
SYSCOMP_TARGETS = $(patsubst $(SYSCOMP_ROOT)/%/Dockerfile,system-%, $(SYSCOMPONENTS))

CORE_ROOT = core
CORE_APPS = $(wildcard $(CORE_ROOT)/*/Dockerfile)
CORE_TARGETS = $(patsubst $(CORE_ROOT)/%/Dockerfile,core-%, $(CORE_APPS))

IMG_BASE = $(TAG_ROOT)_base

IMG_UBUNTU = ubuntu:24.04


# --- help ---
# HELP
# This will output the help for each task
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
.PHONY: help

help: ## This help
	@printf "DATA.BEAM container build\n-------------------\n"
	@printf "general options (can be combined)\n"
	@printf '%b\n' "make xxx \033[1mNOCACHE=1\033[0m  -->  do not use caching"
	@printf '%b\n' "make xxx \033[1mVERSION=projectXY\033[0m  -->  set custom version tag"
	@printf '%b\n' "make xxx \033[1mPLATFORM=linux/amd64,linux/arm64\033[0m  -->  set custom platform(s)"
	@printf '%b\n' "make xxx \033[1mBUILD_LOCAL=1\033[0m  -->  build for local machine only"
	@printf '%b\n' "make xxx \033[1mBUILD_TAR=1 PLATFORM=linux/amd64\033[0m  -->  output will be a tarball for amd64 or arm64 (specify!)"
	@printf '%b\n' "make xxx \033[1mBUILD_TAR=1 TARGET=user@host SSHPORT=22\033[0m  -->  tarball will be uploaded to target via scp"
	@printf '%b\n' "make xxx \033[1mREGISTRY=localhost:5010\033[0m  -->  use custom registry"
# run registry: docker run --rm -d -p 5010:5000 -v registry_data:/var/lib/registry --name registry registry:2
	@printf "%s\n" "-------------------"
	@printf "explicit targets\n"
	@awk 'BEGIN {FS = ":.*?## "} /^[0-9a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "%s\n" "-------------------"
	@printf "Module components from ./extensions/io_modules\n"
	@printf "\033[36m%s\033[0m\n" $(MODULE_TARGETS)
	@printf "%s\n" "-------------------"
	@printf "System components from ./extensions/system\n"
	@printf "\033[36m%s\033[0m\n" $(SYSCOMP_TARGETS)
	@printf "%s\n" "-------------------"
	@printf "Core application components from ./core\n"
	@printf "\033[36m%s\033[0m\n" $(CORE_TARGETS)


.DEFAULT_GOAL := help

.PHONY: showinfo
showinfo:
	@printf "\n"
	@printf "*******\n"
	@printf "used registry: $(DOCKER_REGISTRY)\n"
	@printf "*******\n\n"

# base images should be used from repository, not local
define clean_base_images
	@if [ -z "$(BUILD_LOCAL)" ] || [ "$(BUILD_LOCAL)" = "0" ]; then \
		printf "[$(shell date '+%Y-%m-%d-%H:%M:%S')] - deleting local base images\n"; \
		-docker rmi $(docker images --format '{{.Repository}}:{{.Tag}}' | grep '$(IMG_BASE)') > /dev/null 2>&1 || true; \
	fi
endef

# # --- docker build ---
define buildx_base
	$(call clean_base_images)
	deploy/scripts/buildx.sh $(IMG_BASE)_$(1) deploy/docker-base-images/Dockerfile.$(1) linux/amd64,linux/arm64 $(MODE) --build-arg IMAGE=$(2)
endef

# build function
define buildx_container
	$(call clean_base_images)
	deploy/scripts/buildx.sh $(TAG_ROOT)_$(1)_$(2) $(3)/Dockerfile $(PLATFORM) $(MODE) --build-arg BUILD_IMAGE=$(IMG_BASE)_build --build-arg DEPLOY_IMAGE=$(IMG_BASE)_run
endef

.PHONY: run
run:  ## Run Databeam stack locally (docker compose up)
	bash -c "trap - EXIT; docker compose --project-name databeam up --remove-orphans --force-recreate --renew-anon-volumes"

.PHONY: develop
develop:  ## Prepare development environment
	./deploy/scripts/developer_init.sh

.PHONY: _prompt
_prompt:
	@bash -c "read -n 1 -p \"this will take a loooong time .. press any key to continue (abort with CTRL+C)\" foo"
	@printf "[$(shell date '+%Y-%m-%d-%H:%M:%S')] - start\n\n"

.PHONY: update
update: _prompt base-all  ## Update dependencies and build base- / run-images
# delete local base images (make sure they are not used)
	$(call clean_base_images)
	@printf "[$(shell date '+%Y-%m-%d-%H:%M:%S')] - finished\n"

.PHONY: base-all
base-all: base-run base-build  # Build both mulitstage base images

.PHONY: base-run
base-run: showinfo  # Build mulitstage "run" base image
	@printf "\nBuilding base-run images\n"
	$(call buildx_base,run_py,$(IMG_UBUNTU))
	$(call buildx_base,run_cpp,$(IMG_UBUNTU))

.PHONY: base-build
base-build: showinfo  # Build mulitstage "build" base image
	@printf "\nBuilding base-build images\n"
	$(call buildx_base,build_py,$(IMG_BASE)_run_py)
	$(call buildx_base,build_cpp,$(IMG_BASE)_run_cpp)

.PHONY: modules
modules: $(MODULE_TARGETS)  ## Build images of all modules

.PHONY: $(MODULE_TARGETS)
$(MODULE_TARGETS): module-%: showinfo	## Container build target for a module
	$(call buildx_container,module,$*,$(MODULE_ROOT)/$*)

.PHONY: $(SYSCOMP_TARGETS)
$(SYSCOMP_TARGETS): system-%: showinfo	## Container build target for a system component
	$(call buildx_container,system,$*,$(SYSCOMP_ROOT)/$*)

.PHONY: core-apps
core-apps: $(CORE_TARGETS)  ## Build images of all core components

.PHONY: $(CORE_TARGETS)
$(CORE_TARGETS): core-%: showinfo  ## Container build target for a core component
	$(call buildx_container,core,$*,$(CORE_ROOT)/$*)
