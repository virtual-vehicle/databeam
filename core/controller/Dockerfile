ARG BUILD_IMAGE=hello-world:invalid
ARG DEPLOY_IMAGE=hello-world:invalid

FROM ${BUILD_IMAGE} AS build-image

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=./deploy/requirements_core.txt,target=/tmp/requirements_core.txt \
    --mount=type=bind,source=./core/controller/requirements.txt,target=/tmp/requirements.txt \
    pip install -r /tmp/requirements_core.txt -r /tmp/requirements.txt


FROM ${DEPLOY_IMAGE} AS deploy-image

COPY --from=build-image /opt/venv /opt/venv

# install mcap CLI
RUN PARCH="$(dpkg --print-architecture)"; \
    DOWNLOAD_URL=$(curl -s https://api.github.com/repos/foxglove/mcap/releases \
    | jq -r '[.[] | select(.tag_name | startswith("releases/mcap-cli/"))][0].assets[] | select(.name == "'mcap-linux-${PARCH}'") | .browser_download_url') \
    && curl -L "$DOWNLOAD_URL" -o /usr/local/bin/mcap \
    && chmod +x /usr/local/bin/mcap

# copy python dependencies
COPY libs/python/vif/logger /python/libs/vif/logger
COPY libs/python/vif/jobs /python/libs/vif/jobs
COPY libs/python/vif/asyncio_helpers /python/libs/vif/asyncio_helpers
COPY libs/python/vif/file_helpers /python/libs/vif/file_helpers
COPY libs/python/vif/data_interface /python/libs/vif/data_interface
COPY libs/python/vif/zmq /python/libs/vif/zmq
COPY libs/python/vif/network /python/libs/vif/network
COPY libs/python/vif/plot_juggler /python/libs/vif/plot_juggler

# copy app
COPY core/controller/*.py /app/

# update pythonpath
ENV PYTHONPATH="/python/libs"

# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

HEALTHCHECK --interval=10s --timeout=1s --retries=3 --start-period=5s --start-interval=200ms CMD nc -z localhost 1100 || exit 1

# run
CMD ["python3", "controller.py"]
