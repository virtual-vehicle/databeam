#!/bin/bash

# stop on error
set -e

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
ROOT_DIR="$SCRIPT_DIR/../.."

source $ROOT_DIR/deploy/scripts/helpers.sh

print_headline "installing dependencies ..\nplease provide sudo password if needed"
sudo apt-get update

print_headline "installing dependencies for cross-platform builds"
sudo apt-get install -y binfmt-support qemu-user-static

print_headline "installing python3"
sudo apt-get install -y python3 python3-pip python3-venv

# adopt docker IP ranges for compatibility with host network
print_headline "adopt docker daemon config .."
sudo mkdir -p /etc/docker
sudo python3 -c """
import os, json, re, subprocess, shutil

# get dns servers from host OS
dns = []
if shutil.which('nmcli') is not None:
    output = subprocess.check_output(['nmcli', 'dev', 'show']).decode()
    trigger = False
    for line in output.split('\n'):
        if 'ethernet' in line or 'wifi' in line:
            trigger = True
        if trigger and 'IP4.DNS' in line:
            dns.append(re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', line).group())
        if 'GENERAL.DEVICE' in line:
            trigger = False
    dns = list(set(dns))
    dns.append('8.8.8.8')

# read existing daemon.json
data = {}
if os.path.isfile('/etc/docker/daemon.json'):
    data = json.load(open('/etc/docker/daemon.json', 'r'))
# write new daemon.json
data['builder'] = {'gc': {'defaultKeepStorage': '10GB', 'enabled': True}}
data['default-address-pools'] = [{'base': '172.16.0.0/16', 'size': 24}]
if len(dns) > 0:
    data['dns'] = dns
json.dump(data, open('/etc/docker/daemon.json', 'w'), indent=2)
"""
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
