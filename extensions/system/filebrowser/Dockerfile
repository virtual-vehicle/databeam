ARG BUILD_IMAGE=hello-world:invalid
ARG DEPLOY_IMAGE=hello-world:invalid

FROM ${BUILD_IMAGE} AS build-image
ARG MODULE_NAME=filebrowser

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=./deploy/requirements_core.txt,target=/tmp/requirements_core.txt \
    --mount=type=bind,source=./deploy/requirements_module.txt,target=/tmp/requirements_module.txt \
    --mount=type=bind,source=./extensions/system/${MODULE_NAME}/requirements.txt,target=/tmp/requirements.txt \
    pip install -r /tmp/requirements_core.txt -r /tmp/requirements_module.txt -r /tmp/requirements.txt


FROM ${DEPLOY_IMAGE} AS deploy-image
ARG MODULE_NAME=filebrowser

COPY --from=build-image /opt/venv /opt/venv

# install dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y wget

# copy data-interface dependencies
COPY libs/python/vif/logger /python/libs/vif/logger
COPY libs/python/vif/data_interface /python/libs/vif/data_interface
COPY libs/python/vif/zmq /python/libs/vif/zmq
COPY libs/python/vif/network /python/libs/vif/network
COPY libs/python/vif/flatten /python/libs/vif/flatten
COPY libs/python/vif/asyncio_helpers /python/libs/vif/asyncio_helpers
COPY libs/python/vif/file_helpers /python/libs/vif/file_helpers
COPY libs/python/vif/jobs /python/libs/vif/jobs

# Install filebrowser standalone software
COPY extensions/system/${MODULE_NAME}/install_dependencies.sh /python/extensions/system/${MODULE_NAME}/
RUN /python/extensions/system/${MODULE_NAME}/install_dependencies.sh

# Copy custom branding into filebrowser directory
COPY extensions/system/${MODULE_NAME}/branding /python/extensions/system/${MODULE_NAME}/branding

# copy module documentation to documentation directory
COPY extensions/system/${MODULE_NAME}/documentation.html /python/extensions/system/${MODULE_NAME}/

# copy sensor dependencies
COPY extensions/system/${MODULE_NAME}/*.py /python/extensions/system/${MODULE_NAME}/

ENV PYTHONPATH="/python/extensions:/python/libs"
ENV PATH="/opt/venv/bin:$PATH"
# run
WORKDIR /python/extensions/system/${MODULE_NAME}
CMD ["python3", "filebrowser.py"]
