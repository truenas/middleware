#!/bin/sh
#########################################

minidlna_pbi_path=/usr/pbi/minidlna-amd64/

mkdir -p ${minidlna_pbi_path}/mnt
mkdir -p ${minidlna_pbi_path}/www

mv ${minidlna_pbi_path}/edit.html ${minidlna_pbi_path}/www/
mv ${minidlna_pbi_path}/mp_edit.html ${minidlna_pbi_path}/www/
mv ${minidlna_pbi_path}/minidlna /usr/local/etc/rc.d/

pw user add dlna -d ${minidlna_pbi_path}
