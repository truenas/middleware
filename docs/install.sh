#!/bin/bash -eux
chmod +x /usr/bin/apt* /usr/bin/dpkg
apt update
apt install -y python3-pip
pip3 install --break-system-packages sphinx-rtd-theme Sphinx-Substitution-Extensions==2020.9.30.0
