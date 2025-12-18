ARG BUILD_IMAGE=hello-world:invalid
ARG DEPLOY_IMAGE=hello-world:invalid

FROM ${BUILD_IMAGE} AS build-image

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=./deploy/requirements_core.txt,target=/tmp/requirements_core.txt \
    --mount=type=bind,source=./core/rest_api/requirements.txt,target=/tmp/requirements.txt \
    pip install -r /tmp/requirements_core.txt -r /tmp/requirements.txt


FROM ${DEPLOY_IMAGE} AS deploy-image

COPY --from=build-image /opt/venv /opt/venv

# copy js dependencies
ADD https://raw.githubusercontent.com/brillout/forge-sha256/master/build/forge-sha256.min.js /app/static/js/libs/

# copy python dependencies
COPY libs/python/vif/logger /python/libs/vif/logger
COPY libs/python/vif/data_interface /python/libs/vif/data_interface
COPY libs/python/vif/zmq /python/libs/vif/zmq
COPY libs/python/vif/network /python/libs/vif/network
COPY libs/python/vif/websockets /python/libs/vif/websockets

# copy app
COPY core/rest_api/templates /app/templates
COPY core/rest_api/static /app/static
COPY core/rest_api/*.py /app/

# update pythonpath
ENV PYTHONPATH="/python/libs"

# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
# run
# For development: python3 main.py
# For production with Gunicorn:
CMD ["gunicorn", "-c", "gunicorn.conf.py", "main:initialize()"]
# Or to test production:
# PYTHONPATH=../../libs/python gunicorn -c gunicorn.conf.py "main:initialize()"
