#!/bin/sh
#########################################

transmission_rc=/usr/local/bin/transmission-daemon
transmission_pbi_path=/usr/pbi/transmission-$(uname -m)/

mkdir -p ${transmission_pbi_path}/mnt
mkdir -p ${transmission_pbi_path}/www
mkdir -p ${transmission_pbi_path}/etc/transmission/home/Downloads

mv ${transmission_pbi_path}/transmission /usr/local/etc/rc.d/

pw user add transmission -d ${transmission_pbi_path}/etc/transmission/home

chown -R transmission:transmission ${transmission_pbi_path}/etc/transmission
chmod 775 ${transmission_pbi_path}/etc/transmission/home
chmod 775 ${transmission_pbi_path}/etc/transmission/home/Downloads

${transmission_pbi_path}/bin/python ${transmission_pbi_path}/transmissionUI/manage.py syncdb --migrate --noinput
