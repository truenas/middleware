#!/bin/bash -eux
/usr/bin/python3 /usr/local/libexec/disable-rootfs-protection
apt update
apt install -y python3-pip python3-virtualenv
virtualenv virtualenv --system-site-packages
virtualenv/bin/pip3 install sphinx-rtd-theme Sphinx-Substitution-Extensions==2020.9.30.0
