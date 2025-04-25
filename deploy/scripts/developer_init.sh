#!/bin/bash

# stop on error
set -e

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
ROOT_DIR="$SCRIPT_DIR/../.."

source $ROOT_DIR/deploy/scripts/helpers.sh

print_headline "This script will install system dependencies for the developer environment.\n(inspect deploy/scripts/developer_init.sh for details)"
if ! askNoYes "Do you want to continue?" ; then
    exit 0
fi

print_headline "installing dependencies ..\nplease provide sudo password if needed"
sudo apt-get update

print_headline "installing dependencies for cross-platform builds"
sudo apt-get install -y binfmt-support qemu-user-static

print_headline "installing python3"
sudo apt-get install -y python3 python3-pip python3-venv

# adopt docker IP ranges for compatibility with host network
print_headline "adopt docker daemon config .."
sudo mkdir -p /etc/docker

DOCKER_DAEMON_CONFIG=/etc/docker/daemon.json
printf "\nDocker config update .. old config:\n"
if [ -f $DOCKER_DAEMON_CONFIG ] ; then
    cat $DOCKER_DAEMON_CONFIG
    printf "\nbacking up Docker config.\n"
    sudo cp $DOCKER_DAEMON_CONFIG ${DOCKER_DAEMON_CONFIG}_BAK$(date +"%Y%m%d%H%M%S")
else
    printf "\ncreating Docker config.\n"
    sudo touch $DOCKER_DAEMON_CONFIG
fi

# fetch active DNS servers from host OS and add 8.8.8.8
dns_server_array=$(nmcli dev show | grep 'IP4.DNS' | awk '{print $2}' | sort -u | paste -sd, - | sed 's/\([^,]*\)/"\1"/g')
extra_dns=""
if askNoYes "Docker daemon.json: add 8.8.8.8 DNS?" ; then
    extra_dns='"8.8.8.8"'
fi
if [[ -n "$dns_server_array" && -n "$extra_dns" ]]; then
    dns_server_array="$dns_server_array,$extra_dns"
elif [[ -z "$dns_server_array" && -n "$extra_dns" ]]; then
    dns_server_array="$extra_dns"
fi
# add new entries, remove duplicates
jq '
  .["default-address-pools"] += [{"base":"10.16.0.0/16","size":24}] |
  .["default-address-pools"] |= (unique_by(.base, .size)) |
  if ('"[$dns_server_array]"' | length) > 0 then .["dns"] += '"[$dns_server_array]"' else . end |
  .["dns"] |= (unique) |
  .features += {"containerd-snapshotter": true} |
  .builder += {"gc": {"defaultKeepStorage": "10GB", "enabled": true}}
' $DOCKER_DAEMON_CONFIG > /tmp/tmp.json && sudo mv /tmp/tmp.json $DOCKER_DAEMON_CONFIG

cat /etc/docker/daemon.json
echo ""

# install docker if not present
if ! command -v docker &> /dev/null; then
    print_headline "installing docker .."
    sudo apt-get install -y --no-install-recommends curl
    curl -sSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo groupadd -f docker
    sudo usermod -aG docker ${USER}
    print_headline "docker setup done"

    # Create cross platform builder
    sudo docker buildx create --name mybuilder --driver-opt network=host --use
    sudo docker buildx inspect --bootstrap

    print_headline "Docker installed - reboot required!"
    bash -c "read -n 1 -p \"Press Enter to reboot or ctrl-c to abort. After reboot run script again.\" foo"
    sudo reboot now
fi

# prepare NetworkManager to ignore docker networks
if [ -d "/etc/NetworkManager/conf.d" ] && [ ! -f "/etc/NetworkManager/conf.d/ignore_docker.conf" ]; then
    print_headline "configuring NetworkManager to ignore docker networks .."
    sudo tee -a /etc/NetworkManager/conf.d/ignore_docker.conf <<- "EOF"
[main]
plugins=ifupdown,keyfile

[keyfile]
unmanaged-devices=interface-name:docker*;interface-name:veth*;interface-name:br-*;interface-name:vmnet*;interface-name:vboxnet*
EOF
    sudo systemctl reload NetworkManager
fi

print_headline "building docker image for library creation .."
# build docker image for developer's machine
docker pull ubuntu:$(lsb_release -sr)
docker build -f $ROOT_DIR/deploy/docker-base-images/Dockerfile.build_cpp -t db_libbuild --build-arg IMAGE=ubuntu:$(lsb_release -sr) .

print_headline "copying uldaq lib .."
# copy uldaq libs from cpp build image for debugging
mkdir -p $ROOT_DIR/libs/thirdparty/uldaq
rm -rf $ROOT_DIR/libs/thirdparty/uldaq/*
docker run -it --rm -v $ROOT_DIR/libs/thirdparty/uldaq:/out/usr/local db_libbuild bash -c "cd /build_uldaq/libuldaq && make DESTDIR=/out install && chmod -R a+w /out"

# download external module dependencies
print_headline "installing core dependencies .."
find core -name "install_dependencies.sh" -exec "{}" \;

print_headline "installing optional extension specific dependencies .."
extension_install_scripts=$(find extensions -name "install_dependencies.sh" -type f -print)
for install_script in $extension_install_scripts; do
    if askNoYes "Install $install_script?" ; then
        bash "$install_script"
    fi
done

print_headline "installing venv for python extension development .."
# setup python dev venv
if [ -f $ROOT_DIR/extensions/.venv/bin/activate ]; then
    rm -rf $ROOT_DIR/extensions/.venv
fi
python3.12 -m venv $ROOT_DIR/extensions/.venv
source $ROOT_DIR/extensions/.venv/bin/activate
pip install -r $ROOT_DIR/deploy/requirements_core.txt
pip install -r $ROOT_DIR/deploy/requirements_dev.txt
pip install -r $ROOT_DIR/deploy/requirements_module.txt
# install packages for all extensions
find $ROOT_DIR/extensions -name "requirements.txt" -exec pip install -r "{}" \;
deactivate

if [ -f $ROOT_DIR/core/.venv/bin/activate ]; then
    rm -rf $ROOT_DIR/core/.venv
fi
print_headline "installing venv for core development .."
python3.12 -m venv $ROOT_DIR/core/.venv
source $ROOT_DIR/core/.venv/bin/activate
pip install -r $ROOT_DIR/deploy/requirements_core.txt
pip install -r $ROOT_DIR/deploy/requirements_dev.txt
find $ROOT_DIR/core -name "requirements.txt" -exec pip install -r "{}" \;
deactivate

# setup conan last - may mess up subsequent apt calls (puts them in background: list with "jobs" .. restart with "fg 1")
print_headline "installing pipx"
sudo apt-get install -y pipx cmake ninja-build libusb-1.0-0-dev pkg-config

# Increases the USB kernel memory from 16MB to 1000MB can be important for high USB load measurement
# scenarios, such as using multiple cameras.
print_headline "increasing kernel usb memory buffer .."
$SCRIPT_DIR/change_usb_mem.sh

pipx ensurepath
print_headline "installing conan .."
pipx install conan
pipx upgrade conan
print_headline "initializing conan"
bash -i -c "conan profile detect --force"

print_headline "done (developer_init)"
