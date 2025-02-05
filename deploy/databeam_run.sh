#!/usr/bin/env bash

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
source $SCRIPT_DIR/../.env

cd ${ROOT_DIR}
COMPOSE_COMMAND="docker compose -f ${ROOT_DIR}/docker-compose.yml --project-name ${DOCKER_PROJECT_TAG}"

start () {
  # set filename of logfile
  LOG_FILE="$(date +"%Y_%m_%d_%H_%M_%S_log.txt")"
  ${COMPOSE_COMMAND} up -d --remove-orphans --force-recreate
  # inform systemd that we are up and running
  systemd-notify --ready
  # keep logging output to file
  mkdir -p ${ROOT_DIR}/logs/${DEPLOY_VERSION}
  docker compose -p ${DOCKER_PROJECT_TAG} logs --no-color -f -t > ${ROOT_DIR}/logs/${DEPLOY_VERSION}/${LOG_FILE}
}

# watch output with "docker compose -p databeam logs -f"

stop() {
  ${COMPOSE_COMMAND} down
}

case $1 in
    start) start;;
    stop) stop;;
    *) echo "Usage: ./databeam_run.sh start|stop"
esac
