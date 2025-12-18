ARG BUILD_IMAGE=hello-world:invalid
ARG DEPLOY_IMAGE=hello-world:invalid

FROM ${BUILD_IMAGE} AS build-image
ARG MODULE_NAME=startstop_forwarder

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=./deploy/requirements_core.txt,target=/tmp/requirements_core.txt \
    --mount=type=bind,source=./deploy/requirements_module.txt,target=/tmp/requirements_module.txt \
    --mount=type=bind,source=./extensions/system/${MODULE_NAME}/requirements.txt,target=/tmp/requirements.txt \
    pip install -r /tmp/requirements_core.txt -r /tmp/requirements_module.txt -r /tmp/requirements.txt


FROM ${DEPLOY_IMAGE} AS deploy-image
ARG MODULE_NAME=startstop_forwarder

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get -y --no-install-recommends install avahi-daemon avahi-utils libnss-mdns
RUN printf "[server]\nenable-dbus=no\n" >> /etc/avahi/avahi-daemon.conf
COPY extensions/system/${MODULE_NAME}/entrypoint.sh /
RUN chmod +x /entrypoint.sh

COPY --from=build-image /opt/venv /opt/venv

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

ENV PYTHONPATH="/python/extensions:/python/libs"

ENV PATH="/opt/venv/bin:$PATH"
# run
WORKDIR /python/extensions/system/${MODULE_NAME}
ENTRYPOINT ["bash", "/entrypoint.sh"]
CMD ["python3", "startstop_forwarder.py"]
