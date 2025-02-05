#!/bin/bash

# stop on error
set -e

sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev

# setting python3.12 as default might affect apt - skip
#python3.12 -m ensurepip --upgrade
#sudo update-alternatives --install $(which python3) python3 $(which python3.12) 1
