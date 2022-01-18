#!/bin/bash -eux
chmod +x /usr/bin/apt*
apt update
apt install -y python3-pip python3-sphinx-prompt python3-sphinx-rtd-theme
pip3 install Sphinx-Substitution-Extensions
