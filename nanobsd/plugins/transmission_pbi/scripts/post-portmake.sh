#!/bin/sh
# PBI building script
# This will run after your port build is complete
##############################################################################

transmission_pbi_path=/usr/pbi/transmission-$(uname -m)/

find ${transmission_pbi_path}/lib -iname "*.py[co]" -delete
find ${transmission_pbi_path}/lib -iname "*.a" -delete
rm -rf ${transmission_pbi_path}/share/doc
rm -rf ${transmission_pbi_path}/share/emacs
rm -rf ${transmission_pbi_path}/share/examples
rm -rf ${transmission_pbi_path}/share/gettext
