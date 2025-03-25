#!/bin/bash

# stop on error
set -e

IMG_NAME=$1
DOCKERFILE=$2
PLATFORM=$3
MODE=$4
BUILD_ARGS=${@:5}
DIRNAME="$(dirname "${DOCKERFILE}")"

echo ""
if [ -z "$IMG_NAME" ]; then
  echo "ERROR: Base Image Name not set"
  exit 1
fi

if [ -z "$DOCKERFILE" ]; then
  echo "ERROR: Dockerfile not set"
  exit 1
fi

if [ -z "$PLATFORM" ]; then
  echo "ERROR: target platform(s) not set"
  exit 1
fi

if [ -z "$MODE" ]; then
  echo "ERROR: mode not set"
  exit 1
fi

if [ -z "${VERSION}" ]; then
  echo "Warning: VERSION not set, no versioned tag will be created"
  TAG_ARG="-t ${IMG_NAME}:latest"
else
  TAG_ARG="-t ${IMG_NAME}:${VERSION}"
fi
TAG_CACHE="${IMG_NAME}:cache"

if [ -f "$DIRNAME/go.mod" ]; then
  BUILD_ARGS=$(echo $BUILD_ARGS | sed -e "s/base_build\>/base_build_go/g")
  BUILD_ARGS=$(echo $BUILD_ARGS | sed -e "s/base_run\>/base_run_go/g")
elif [ -f "$DIRNAME/main.cpp" ]; then
  BUILD_ARGS=$(echo $BUILD_ARGS | sed -e "s/base_build\>/base_build_cpp/g")
  BUILD_ARGS=$(echo $BUILD_ARGS | sed -e "s/base_run\>/base_run_cpp/g")
else
  BUILD_ARGS=$(echo $BUILD_ARGS | sed -e "s/base_build\>/base_build_py/g")
  BUILD_ARGS=$(echo $BUILD_ARGS | sed -e "s/base_run\>/base_run_py/g")
fi

echo "BUILD_ARGS = $BUILD_ARGS"
echo "TAG_ARG = $TAG_ARG"
echo ""

if [ -z "$NOCACHE" ] || [ $NOCACHE = 0 ]; then
  echo "use caching"
  CACHE_ARG="--cache-from=type=registry,ref=${TAG_CACHE} --cache-to=type=registry,ref=${TAG_CACHE},mode=max"
  CACHE_ARG_LOCAL=""
else
  CACHE_ARG_LOCAL="--no-cache"
  if [ $NOCACHE = 1 ]; then
    echo "do not use cache for build, but push cache update"
    CACHE_ARG="--no-cache --cache-to=type=registry,ref=${TAG_CACHE},mode=max"
  else
    echo "do not use cache at all"
    CACHE_ARG="--no-cache"
  fi
fi

echo ""
if [ -z "${BUILD_LOCAL}" ] && [ -z "${BUILD_TAR}" ] ; then
  # multi-arch build to registry
  set -x
  docker buildx build --progress=plain --platform ${PLATFORM} \
    ${TAG_ARG} \
    -f ${DOCKERFILE} \
    ${BUILD_ARGS} \
    ${CACHE_ARG} \
    --${MODE} \
    .
    # --${MODE} \
    # --output=type=registry,registry.insecure=true \
else
  if [ -z "${BUILD_TAR}" ] ; then
    # local build (BUILD_LOCAL)
    set -x
    docker buildx build --load --progress=plain \
      ${TAG_ARG} \
      -f ${DOCKERFILE} \
      ${BUILD_ARGS} \
      ${CACHE_ARG_LOCAL} \
      .
  else
    # building tar archive
    OUTFILE="$(basename $IMG_NAME).tar"
    echo "OUTFILE: $OUTFILE"
    # strip registry from tag as file is independant
    TAG_ARG=${TAG_ARG/"$DOCKER_REGISTRY/"/""}
    printf "TAG used: $TAG_ARG\n\n"
    
    if [ -n "${TARGET}" ] ; then
      # direct tar transfer to target
      if [ -z "$SSHPORT" ] || [ $SSHPORT = 0 ]; then
        SSHPORT=22
      fi
      
      TARCH=$(ssh -n -p $SSHPORT ${TARGET} "uname -m")
      if [ $TARCH == "aarch64" ]; then
          TARCH_BUILDX=arm64
          printf "using ARM64 TARGET-architecture\n\n"
      else
          TARCH_BUILDX=amd64
          printf "using AMD64 TARGET-architecture\n\n"
      fi

      set -x
      docker buildx build --output "type=docker,dest=$OUTFILE" --progress=plain --platform linux/$TARCH_BUILDX \
      ${TAG_ARG} \
      -f ${DOCKERFILE} \
      ${BUILD_ARGS} \
      ${CACHE_ARG} \
      .
      set +x

      echo "uploading to $TARGET"
      scp -P $SSHPORT $OUTFILE $TARGET:/opt/databeam/
      ssh -p $SSHPORT $TARGET "docker image load -i /opt/databeam/$OUTFILE"
      ssh -p $SSHPORT $TARGET "rm /opt/databeam/$OUTFILE"
      rm $OUTFILE

    else
      # save tar file locally
      if [ -z "$PLATFORM" ]; then
        echo "ERROR: platform not set! Choose amd64 or arm64"
        exit 1
      fi
      set -x
      docker buildx build --output "type=docker,dest=$OUTFILE" --progress=plain --platform ${PLATFORM} \
      ${TAG_ARG} \
      -f ${DOCKERFILE} \
      ${BUILD_ARGS} \
      ${CACHE_ARG} \
      .
      set +x

      printf "\nOUTFILE $OUTFILE for arm64 ready!\n"
    fi
  fi
fi
