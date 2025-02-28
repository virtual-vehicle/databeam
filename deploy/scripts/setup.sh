#!/bin/bash

# stop on error
set -e

# this script shall contain everything needed to setup Data.Beam software environment on a target machine
# software packages are NOT included (since those are machine specific)

echo "staring setup on $(date)"

TARGET_USERNAME=$1
DOCKERHUB_USER=$2
DOCKERHUB_TOKEN=$3

if [ "${TARGET_USERNAME}" == "" ]; then
    echo "***** please provide user as argument: e.g.:"
    echo "      ./setup.sh databeam"
    exit
fi

# script directory
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
echo "SCRIPT_DIR = $SCRIPT_DIR"

source $SCRIPT_DIR/../../.env

printf "script directory: $SCRIPT_DIR\n"
printf "target username: $TARGET_USERNAME\n"
printf "dockerhub user: $DOCKERHUB_USER\n"
printf "dockerhub token: $DOCKERHUB_TOKEN\n"

if ! grep -q ^NTP= "/etc/systemd/timesyncd.conf"; then
    printf "\nconfigure NTP with server $DEPLOY_TIMESERVER\n"
    echo 'NTP=${DEPLOY_TIMESERVER}' | sudo tee -a /etc/systemd/timesyncd.conf
    sudo systemctl daemon-reload
    sudo systemctl restart systemd-timesyncd.service || true   # rely on a reboot .. NTP daemon differs on every OS
    sleep 5
fi

printf "\npreparing directories ..\n"

# create a shared directory for internal data
sudo mkdir -p $ROOT_DIR

# create directory for log files
sudo mkdir -p $ROOT_DIR/logs

# install service file for databeam_run.sh
sudo rm -f /etc/systemd/system/databeam.service
sudo mv $DEPLOY_DIR/databeam.service /etc/systemd/system/databeam.service

# install docker if not present
if ! command -v docker &> /dev/null; then
    printf "\ninstalling docker ..\n"
    sudo apt-get update && sudo apt-get install -y --no-install-recommends curl
    curl -sSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo groupadd -f docker
    sudo usermod -aG docker ${TARGET_USERNAME}
    printf "\n\ndocker setup done\n"
fi

# adopt docker IP ranges for compatibility with host network
DOCKER_DAEMON_CONFIG=/etc/docker/daemon.json
if [ ! -f "$DOCKER_DAEMON_CONFIG" ] || [ -z $(grep "default-address-pools" "$DOCKER_DAEMON_CONFIG") ] ; then
    printf "\nadding network ranges to docker config ..\n"
    sudo tee -a $DOCKER_DAEMON_CONFIG <<- "EOF"
{
        "default-address-pools":[
                {"base":"172.16.0.0/16","size":24}
        ]
}
EOF
fi

# prepare NetworkManager to ignore docker networks
if [ ! -f "/etc/NetworkManager/conf.d/ignore_docker.conf" ]; then
    printf "\nconfiguring NetworkManager to ignore docker networks ..\n"
    sudo tee -a /etc/NetworkManager/conf.d/ignore_docker.conf <<- "EOF"
[main]
plugins=ifupdown,keyfile

[keyfile]
unmanaged-devices=interface-name:docker*;interface-name:veth*;interface-name:br-*;interface-name:vmnet*;interface-name:vboxnet*
EOF
    sudo systemctl reload NetworkManager
fi

printf "\ncleanup ..\n"
# change ownership to docker group (we need to be part of it anyways)
sudo chgrp -R docker $ROOT_DIR
# grant write access to group
sudo chmod -R g+w $ROOT_DIR

# enable hostcmd helper if binary is available
if [ -f "$DEPLOY_DIR/databeam_hostcmd" ]; then
    # install service file for hostcmd helper
    sudo rm -f /etc/systemd/system/databeam_hostcmd.service
    sudo mv $DEPLOY_DIR/databeam_hostcmd.service /etc/systemd/system/databeam_hostcmd.service
    sudo systemctl daemon-reload
    sudo systemctl enable databeam_hostcmd.service
    echo "databeam hostcmd helper enabled!"
else
    echo "databeam hostcmd helper not available!"
    # just reload systemd scripts
    sudo systemctl daemon-reload
fi

# enable databeam main service
sudo systemctl enable databeam.service

# pull basic images
printf "\ndockerhub login\n"
sudo docker login -u $DOCKERHUB_USER -p $DOCKERHUB_TOKEN

printf "\npulling images defined in docker-compose.yml\n"
sudo docker compose --env-file ${ROOT_DIR}/.env -f ${ROOT_DIR}/docker-compose.yml pull -q

# Increases the USB kernel memory from 16MB to 1000MB can be important for high USB load measurement
# scenarios, such as using multiple cameras.
echo "Increasing kernel USB memory buffer."
sudo bash $SCRIPT_DIR/change_usb_mem.sh


printf "\nsetup done! $(date)\n"
echo ""
echo "--> please reboot device! <--"
echo ""
