#!/bin/sh
#########################################

firefly_pbi_path=/usr/pbi/firefly-amd64/

mkdir -p ${firefly_pbi_path}/mnt
mkdir -p ${firefly_pbi_path}/www

mv ${firefly_pbi_path}/edit.html ${firefly_pbi_path}/www/
mv ${firefly_pbi_path}/mp_edit.html ${firefly_pbi_path}/www/

pw user add daapd -d ${firefly_pbi_path}
