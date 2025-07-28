ARG BUILD_IMAGE=hello-world:invalid
ARG DEPLOY_IMAGE=hello-world:invalid

FROM ${BUILD_IMAGE} AS build-image
# TODO adopt MODULE_NAME to name of module
ARG MODULE_NAME=filebrowser

COPY ./deploy/requirements_core.txt .
COPY ./deploy/requirements_module.txt .
COPY ./extensions/system/${MODULE_NAME}/requirements.txt .
RUN pip install -r requirements_core.txt -r requirements_module.txt -r requirements.txt


FROM ${DEPLOY_IMAGE} AS deploy-image
# TODO adopt MODULE_NAME to name of module
ARG MODULE_NAME=filebrowser

COPY --from=build-image /opt/venv /opt/venv

# install dependencies
RUN apt-get update && apt-get install -y wget

# copy data-interface dependencies
COPY libs/python/vif/logger /python/libs/vif/logger
COPY libs/python/vif/data_interface /python/libs/vif/data_interface
COPY libs/python/vif/zmq /python/libs/vif/zmq
COPY libs/python/vif/network /python/libs/vif/network
COPY libs/python/vif/flatten /python/libs/vif/flatten
COPY libs/python/vif/asyncio_helpers /python/libs/vif/asyncio_helpers
COPY libs/python/vif/file_helpers /python/libs/vif/file_helpers
COPY libs/python/vif/jobs /python/libs/vif/jobs

# copy sensor dependencies
COPY extensions/system/${MODULE_NAME}/*.py /python/extensions/system/${MODULE_NAME}/

# copy module documentation to documentation directory
COPY extensions/system/${MODULE_NAME}/documentation.html /python/extensions/system/${MODULE_NAME}/

# Install filebrowser standalone software
WORKDIR /python/extensions/system/${MODULE_NAME}
RUN mkdir filebrowser
WORKDIR /python/extensions/system/${MODULE_NAME}/filebrowser
RUN wget https://github.com/filebrowser/filebrowser/releases/download/v2.32.0/linux-amd64-filebrowser.tar.gz
RUN tar -xf linux-amd64-filebrowser.tar.gz
ENV PYTHONPATH="/python/extensions:/python/libs"

# Copy custom branding into filebrowser directory
COPY extensions/system/${MODULE_NAME}/branding /python/extensions/system/${MODULE_NAME}/branding

ENV PATH="/opt/venv/bin:$PATH"
# run
WORKDIR /python/extensions/system/${MODULE_NAME}
CMD ["python3", "filebrowser.py"]