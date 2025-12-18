ARG BUILD_IMAGE=hello-world:invalid
ARG DEPLOY_IMAGE=hello-world:invalid

FROM ${BUILD_IMAGE} AS build-image

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=./deploy/requirements_core.txt,target=/tmp/requirements_core.txt \
    pip install -r /tmp/requirements_core.txt


FROM ${DEPLOY_IMAGE} AS deploy-image

COPY --from=build-image /opt/venv /opt/venv

# copy python dependencies
COPY libs/python/vif/logger /python/libs/vif/logger

# copy app
COPY core/zmq_router/*.py /app/
COPY core/zmq_router/start.sh /app/
RUN chmod a+x /app/start.sh

# update pythonpath
ENV PYTHONPATH="/python/libs"

# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# define healthcheck CMD in docker-compose.yml
HEALTHCHECK --interval=10s --timeout=1s --retries=3 --start-period=5s --start-interval=200ms CMD exit 1

# run
CMD ["/app/start.sh"]
