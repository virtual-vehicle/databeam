#!/bin/bash

# this script prepares and uploads a tarball with needed files for Data.Beam device

# REQUIREMENTS:
# create key and copy to target device:
#   ssh-keygen -t ed25519 -m PEM -C "XXXthe.name@v2c2.at" -f "/home/${USER}/.ssh/databeam_deploy" -N ""
#   ssh-copy-id -i /home/${USER}/.ssh/databeam_deploy databeam@databeamlp01.v2c2.at


# stop on error
set -e

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
echo "SCRIPT_DIR = $SCRIPT_DIR"
source $SCRIPT_DIR/../../.env
echo "remote DEPLOY_DIR = $DEPLOY_DIR"

TARGET_USERNAME=$1
TARGET_HOSTNAME=$2
DOCKERHUB_USER=$3
DOCKERHUB_TOKEN=$4

if [ "${TARGET_USERNAME}" == "" ] || [ "${TARGET_HOSTNAME}" == "" ] || [ "${DOCKERHUB_USER}" == "" ] || [ "${DOCKERHUB_TOKEN}" == "" ]; then
    echo "***** please provide user, hostname, dockerhub-user, dockerhub-token as argument: e.g.:"
    echo "      ./setup_remote.sh databeam databeam01.local hubuser aBcDeFgHiJkLmNoPqRsTuVwXyZ"
    exit
fi

# check ssh connectivity with key-auth
if [ "$(ssh -o PreferredAuthentications=publickey ${TARGET_USERNAME}@${TARGET_HOSTNAME} "echo test")" != "test" ]; then
    echo "Please check SSH connection with public key auth (use ssh-copy-id)"
    exit
fi
echo "SSH check OK"

printf '\n***** Please provide sudo password for %s@%s:\n' "${TARGET_USERNAME}" "${TARGET_HOSTNAME}"
ssh -t ${TARGET_USERNAME}@${TARGET_HOSTNAME} "\
    sudo mkdir -p ${DEPLOY_DIR}/scripts; \
    sudo chown -R ${TARGET_USERNAME} ${ROOT_DIR};"

printf '\n***** copy installer files:\n'
scp $SCRIPT_DIR/setup.sh ${TARGET_USERNAME}@${TARGET_HOSTNAME}:$DEPLOY_DIR/scripts
scp $SCRIPT_DIR/helpers.sh ${TARGET_USERNAME}@${TARGET_HOSTNAME}:$DEPLOY_DIR/scripts
scp $SCRIPT_DIR/change_version.sh ${TARGET_USERNAME}@${TARGET_HOSTNAME}:$DEPLOY_DIR/scripts
scp $SCRIPT_DIR/change_usb_mem.sh ${TARGET_USERNAME}@${TARGET_HOSTNAME}:$DEPLOY_DIR/scripts
scp $SCRIPT_DIR/../databeam.service ${TARGET_USERNAME}@${TARGET_HOSTNAME}:$DEPLOY_DIR
scp $SCRIPT_DIR/../databeam_run.sh ${TARGET_USERNAME}@${TARGET_HOSTNAME}:$DEPLOY_DIR
scp $SCRIPT_DIR/../databeam_hostcmd.service ${TARGET_USERNAME}@${TARGET_HOSTNAME}:$DEPLOY_DIR
scp $SCRIPT_DIR/../../.env ${TARGET_USERNAME}@${TARGET_HOSTNAME}:$DEPLOY_DIR/..
scp $SCRIPT_DIR/../../docker-compose.yml ${TARGET_USERNAME}@${TARGET_HOSTNAME}:$DEPLOY_DIR/..
scp -r $SCRIPT_DIR/../compose-files ${TARGET_USERNAME}@${TARGET_HOSTNAME}:$DEPLOY_DIR/

printf '\n***** compiling host-command-helper daemon (golang):\n'
TARCH=$(ssh -n ${TARGET_USERNAME}@${TARGET_HOSTNAME} "uname -m")
if [ $TARCH == "aarch64" ]; then
    TARCH_GO=arm64
    echo "using ARM64 GO-architecture"
else
    TARCH_GO=amd64
    echo "using AMD64 GO-architecture"
fi
if [ -f "$SCRIPT_DIR/databeam_hostcmd" ]; then
    rm $SCRIPT_DIR/databeam_hostcmd || true
fi
env GOOS=linux GOARCH=$TARCH_GO go build -o $SCRIPT_DIR/databeam_hostcmd $SCRIPT_DIR/../../core/hostcmd_helper/main.go || true
scp $SCRIPT_DIR/databeam_hostcmd ${TARGET_USERNAME}@${TARGET_HOSTNAME}:$DEPLOY_DIR || true
if [ ! -f "$SCRIPT_DIR/databeam_hostcmd" ]; then
    echo "\n***** databeam_hostcmd compile failed!\n"
fi
rm $SCRIPT_DIR/databeam_hostcmd || true

printf '\n***** executing setup script on remote host:\n'
printf '***** Please provide sudo password for %s@%s (if asked):\n\n' "${TARGET_USERNAME}" "${TARGET_HOSTNAME}"
ssh -t ${TARGET_USERNAME}@${TARGET_HOSTNAME} "${DEPLOY_DIR}/scripts/setup.sh ${TARGET_USERNAME} ${DOCKERHUB_USER} ${DOCKERHUB_TOKEN}"

printf '\n***** done\n'
