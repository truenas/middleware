#!/bin/sh
#########################################

transmission_rc=/usr/local/bin/transmission-daemon
transmission_pbi_path=/usr/pbi/transmission-amd64/

mkdir -p ${transmission_pbi_path}/mnt
mkdir -p ${transmission_pbi_path}/www
mkdir -p ${transmission_pbi_path}/etc/transmission/home/Downloads

mv ${transmission_pbi_path}/edit.html ${transmission_pbi_path}/www/
mv ${transmission_pbi_path}/mp_edit.html ${transmission_pbi_path}/www/
mv ${transmission_pbi_path}/transmission /usr/local/etc/rc.d/

pw user add transmission -d ${transmission_pbi_path}/etc/transmission/home

chown -R transmission:transmission ${transmission_pbi_path}/etc/transmission
chmod 775 ${transmission_pbi_path}/etc/transmission/home
chmod 775 ${transmission_pbi_path}/etc/transmission/home/Downloads
