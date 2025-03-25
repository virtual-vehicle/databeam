#!/bin/bash

# stop on error
set -eE

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
ROOT_DIR="$SCRIPT_DIR/../.."

source $ROOT_DIR/deploy/scripts/helpers.sh

service_was_running=false

terminate() {
    exit_val_on_trigger=$?
    if [[ -n "$TRAP_CALLED" ]]; then return; fi
    TRAP_CALLED=1

    echo "TRAP (current exit code: $exit_val_on_trigger)"

    # check if exit code is not 0
    if [ $exit_val_on_trigger -ne 0 ]; then
        echo "exit code signals error: cleanup!"

        # restore old version to .env
        if [ -n "$current_version" ]; then
            echo "restoring version in .env: $current_version"
            sed -i "s/^DEPLOY_VERSION=.*/DEPLOY_VERSION=${current_version}/" $ROOT_DIR/.env
        fi

        # TODO do further cleanup

    fi

    # restart databeam service if it was active
    if $service_was_running; then
        echo "restarting databeam service"
        sudo systemctl start databeam.service
    fi

    echo "byebye"
    exit $exit_val_on_trigger
}

# trap for cleanup
trap terminate SIGTERM SIGINT ERR EXIT

# load current version
current_version=$(grep '^DEPLOY_VERSION=' $ROOT_DIR/.env | cut -d= -f2)
echo "current version: $current_version"
if [ -z "$current_version" ]; then
    echo "current DEPLOY_VERSION in .env is empty"
    exit 1
fi

# optionally give new version as argument
new_version=$1

if [ -z "$new_version" ]; then
    # ask for new version
    read -p "Enter new version: " new_version
fi

# check new version not empty, not the same as current version
if [ -z "$new_version" ]; then
    echo "new version is empty"
    exit 1
fi
if [ "$new_version" == "$current_version" ]; then
    echo "new version is the same as current version"
    exit 1
fi
echo "new version: $new_version"

if ! askNoYes "Do you want to continue?" ; then
    exit 0
fi

# stop databeam service
if docker ps --format '{{.Names}}' | grep -q 'databeam-'; then
    echo "databeam service is running, stopping it..."
    sudo systemctl stop databeam.service
    service_was_running=true
    
    # check docker ps output for any "databeam" services are left
    if docker ps --format '{{.Names}}' | grep -q 'databeam-'; then
        echo "databeam service is still running, aborting..."
        exit 1
    fi
else
    echo "databeam service is not running, skipping stop"
    service_was_running=false
fi

# change DEPLOY_VERSION in .env
sed -i "s/^DEPLOY_VERSION=.*/DEPLOY_VERSION=${new_version}/" $ROOT_DIR/.env
echo "changed DEPLOY_VERSION in .env to $new_version"

# pull new images, abort if something happened
echo "pulling images defined in docker-compose.yml"
docker compose --env-file ${ROOT_DIR}/.env -f ${ROOT_DIR}/docker-compose.yml pull

# ask if config should be copied
if askNoYes "Copy current config-directory to new version?" ; then
    # check if we have write access to config directory 
    if [ ! -w $ROOT_DIR/config ]; then
        echo "no write access to config directory - fixing..."
        sudo chmod a+w $ROOT_DIR/config
    fi
    cp -R $ROOT_DIR/config/$current_version $ROOT_DIR/config/$new_version
    echo "copied config directory from $current_version to $new_version"
fi

# ask if data should be moved (rename data dir)
if askNoYes "Move current data-directory to new version?" ; then
    # check if we have write access to data directory 
    if [ ! -w $ROOT_DIR/data ]; then
        echo "no write access to data directory - fixing..."
        sudo chmod a+w $ROOT_DIR/data
        sudo chmod a+w $ROOT_DIR/data/$current_version
    fi
    mv $ROOT_DIR/data/$current_version $ROOT_DIR/data/$new_version
    echo "moved data directory from $current_version to $new_version"
fi
