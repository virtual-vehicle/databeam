ARG BUILD_IMAGE=hello-world:invalid
ARG DEPLOY_IMAGE=hello-world:invalid

FROM ${BUILD_IMAGE} AS build-image
ARG MODULE_NAME=plotter

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=./deploy/requirements_core.txt,target=/tmp/requirements_core.txt \
    --mount=type=bind,source=./deploy/requirements_module.txt,target=/tmp/requirements_module.txt \
    --mount=type=bind,source=./extensions/io_modules/${MODULE_NAME}/requirements.txt,target=/tmp/requirements.txt \
    pip install -r /tmp/requirements_core.txt -r /tmp/requirements_module.txt -r /tmp/requirements.txt

ADD https://github.com/Leaflet/Leaflet/releases/latest/download/leaflet.zip /leaflet/
RUN unzip -q /leaflet/leaflet.zip -d /leaflet

RUN VERSION_UPLOT="$(curl -s https://github.com/leeoniya/uPlot/releases/latest -L | grep -Eo "[\'\"]\/leeoniya\/uPlot\/releases\/tag\/[^\'\"]*" | head -n 1 | grep -Po "(\d+\.)+\d+")"; \
    curl -o uplot.zip https://github.com/leeoniya/uPlot/archive/refs/tags/$VERSION_UPLOT.zip -L && \
    unzip -q uplot.zip -d /uPlot

FROM ${DEPLOY_IMAGE} AS deploy-image
ARG MODULE_NAME=plotter

COPY --from=build-image /opt/venv /opt/venv

# copy data-interface dependencies
COPY libs/python/vif/logger /python/libs/vif/logger
COPY libs/python/vif/data_interface /python/libs/vif/data_interface
COPY libs/python/vif/zmq /python/libs/vif/zmq
COPY libs/python/vif/network /python/libs/vif/network
COPY libs/python/vif/flatten /python/libs/vif/flatten
COPY libs/python/vif/asyncio_helpers /python/libs/vif/asyncio_helpers
COPY libs/python/vif/file_helpers /python/libs/vif/file_helpers
COPY libs/python/vif/websockets /python/libs/vif/websockets
COPY libs/python/vif/jobs /python/libs/vif/jobs

# copy sensor dependencies
COPY extensions/io_modules/${MODULE_NAME}/*.py /python/extensions/io_modules/${MODULE_NAME}/
COPY extensions/io_modules/${MODULE_NAME}/static /python/extensions/io_modules/${MODULE_NAME}/static
COPY extensions/io_modules/${MODULE_NAME}/templates /python/extensions/io_modules/${MODULE_NAME}/templates

# copy leaflet lib
COPY --from=build-image /leaflet/dist/leaflet.js /python/extensions/io_modules/${MODULE_NAME}/static/js
COPY --from=build-image /leaflet/dist/leaflet.css /python/extensions/io_modules/${MODULE_NAME}/static/css
COPY --from=build-image /leaflet/dist/images /python/extensions/io_modules/${MODULE_NAME}/static/css/images

# copy uPlot lib
COPY --from=build-image /uPlot/*/dist/uPlot.iife.min.js /python/extensions/io_modules/${MODULE_NAME}/static/js
COPY --from=build-image /uPlot/*/dist/uPlot.min.css /python/extensions/io_modules/${MODULE_NAME}/static/css

# copy module documentation to documentation directory
COPY extensions/io_modules/${MODULE_NAME}/documentation.html /python/extensions/io_modules/${MODULE_NAME}/

ENV PYTHONPATH="/python/extensions:/python/libs"

ENV PATH="/opt/venv/bin:$PATH"
# run
WORKDIR /python/extensions/io_modules/${MODULE_NAME}
CMD ["python3", "plotter.py"]
