#!/bin/sh
#########################################

plexmediaserver_pbi_path=/usr/pbi/plexmediaserver-$(uname -m)/
plexmediaserver_plexdata="${plexmediaserver_pbi_path}/plexdata"
plexmediaserver_pms="${plexmediaserver_plexdata}/Plex Media Server"
plexmediaserver_media="${plexmediaserver_pms}/Media"

pw group add plex
pw user add plex -g plex -d "${plexmediaserver_pbi_path}"

mkdir -p "${plexmediaserver_media}/Movies"
mkdir -p "${plexmediaserver_media}/TV Shows"
mkdir -p "${plexmediaserver_media}/Music"
mkdir -p "${plexmediaserver_media}/Photos"
mkdir -p "${plexmediaserver_media}/Home Movies"

mv "${plexmediaserver_pbi_path}/Preferences.xml" "${plexmediaserver_pms}/Preferences.xml"

${plexmediaserver_pbi_path}/bin/python ${plexmediaserver_pbi_path}/plexmediaserverUI/manage.py syncdb --migrate --noinput
~
cp ${plexmediaserver_pbi_path}/etc/rc.d/plexmediaserver /usr/local/etc/rc.d/plexmediaserver

chown -R plex:plex "${plexmediaserver_plexdata}"
