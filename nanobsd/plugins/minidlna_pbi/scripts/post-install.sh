#!/bin/sh
#########################################

minidlna_pbi_path=/usr/pbi/minidlna-$(uname -m)/

mkdir -p ${minidlna_pbi_path}/mnt

mv ${minidlna_pbi_path}/minidlna /usr/local/etc/rc.d/

pw user add dlna -d ${minidlna_pbi_path}

cd ${minidlna_pbi_path}/plugins/minidlna/application
mkdir -p ../data/db
${minidlna_pbi_path}/bin/php bin/doctrine.php orm:schema-tool:create
touch ${minidlna_pbi_path}/etc/rc.conf
chown -R www:www ../data/db ${minidlna_pbi_path}/etc/rc.conf ${minidlna_pbi_path}/etc/minidlna.conf
chmod u+w ${minidlna_pbi_path}/etc/rc.conf ${minidlna_pbi_path}/etc/minidlna.conf
mkdir -p /var/db/minidlna
chown -R dlna:dlna /var/db/minidlna
chmod -R 744 /var/db/minidlna

echo "www ALL=(ALL) NOPASSWD: /usr/local/etc/rc.d/minidlna, ${minidlna_pbi_path}tweak-rcconf" >> ${minidlna_pbi_path}/etc/sudoers
