#!/bin/bash -eux
/usr/bin/python3 /usr/local/libexec/disable-rootfs-protection
apt update
apt install -y python3-pip
pip3 install --break-system-packages sphinx-rtd-theme Sphinx-Substitution-Extensions==2020.9.30.0
