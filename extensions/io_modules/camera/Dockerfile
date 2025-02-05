ARG BUILD_IMAGE=hello-world:invalid
ARG DEPLOY_IMAGE=hello-world:invalid

FROM ${BUILD_IMAGE} AS build-image
ARG MODULE_NAME=camera

# update and install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip git autoconf automake libtool

# build mp4fpsmod
RUN git clone https://github.com/nu774/mp4fpsmod.git /mp4fpsmod
WORKDIR /mp4fpsmod
RUN /mp4fpsmod/bootstrap.sh
RUN /mp4fpsmod/configure && make -j6 && strip mp4fpsmod
RUN make install

COPY ./deploy/requirements_core.txt .
COPY ./deploy/requirements_module.txt .
COPY ./extensions/io_modules/${MODULE_NAME}/requirements.txt .
RUN pip install -r requirements_core.txt -r requirements_module.txt -r requirements.txt


FROM ${DEPLOY_IMAGE} AS deploy-image
ARG MODULE_NAME=camera

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-opencv ffmpeg libsm6 libxext6

COPY --from=build-image /opt/venv /opt/venv
COPY --from=build-image /usr/local/bin/mp4fpsmod /usr/local/bin/mp4fpsmod

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
COPY extensions/io_modules/${MODULE_NAME}/*.py /python/extensions/io_modules/${MODULE_NAME}/

# copy module documentation to documentation directory
COPY extensions/io_modules/${MODULE_NAME}/documentation.html /python/extensions/io_modules/${MODULE_NAME}/

ENV PYTHONPATH="/python/extensions:/python/libs"

ENV PATH="/opt/venv/bin:$PATH"
# run
WORKDIR /python/extensions/io_modules/${MODULE_NAME}
CMD ["python3", "camera.py"]
