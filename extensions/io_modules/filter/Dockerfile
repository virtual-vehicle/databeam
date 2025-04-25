ARG BUILD_IMAGE=hello-world:invalid
ARG DEPLOY_IMAGE=hello-world:invalid

FROM ${BUILD_IMAGE} AS build-image

ARG MODULE_NAME=filter

COPY libs/cpp /libs/cpp
COPY libs/thirdparty/conanfile.txt /libs/thirdparty/
COPY deploy/scripts/build_cpp_module.sh /extensions/io_modules/${MODULE_NAME}/
COPY extensions/io_modules/${MODULE_NAME}/conanfile.txt /extensions/io_modules/${MODULE_NAME}/
COPY extensions/io_modules/${MODULE_NAME}/CMakeLists.txt /extensions/io_modules/${MODULE_NAME}/
COPY extensions/io_modules/${MODULE_NAME}/*.cpp /extensions/io_modules/${MODULE_NAME}/
COPY extensions/io_modules/${MODULE_NAME}/header /extensions/io_modules/${MODULE_NAME}/header
COPY extensions/io_modules/${MODULE_NAME}/source /extensions/io_modules/${MODULE_NAME}/source

WORKDIR /extensions/io_modules/${MODULE_NAME}
RUN ./build_cpp_module.sh

RUN mv /extensions/io_modules/${MODULE_NAME}/build/main /main
COPY extensions/io_modules/${MODULE_NAME}/documentation.html /


FROM ${DEPLOY_IMAGE} AS deploy-image

COPY --from=build-image /main /main
COPY --from=build-image /documentation.html /

WORKDIR /
CMD ["/main"]
