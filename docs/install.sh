#!/bin/bash -eux
apt update
apt install -y python3-pip python3-sphinx-rtd-theme
pip3 install Sphinx-Substitution-Extensions
