#!/bin/sh
# PBI building script
# This will run after your port build is complete
##############################################################################

plexmediaserver_pbi_path=/usr/pbi/plexmediaserver-$(uname -m)/

find ${plexmediaserver_pbi_path}/lib -iname "*.a" -delete
rm -rf ${plexmediaserver_pbi_path}/include
rm -rf ${plexmediaserver_pbi_path}/share/doc
rm -rf ${plexmediaserver_pbi_path}/share/emacs
rm -rf ${plexmediaserver_pbi_path}/share/examples
rm -rf ${plexmediaserver_pbi_path}/share/gettext
