#!/bin/sh
# PBI building script
# This will run after your port build is complete
##############################################################################

firefly_pbi_path=/usr/pbi/firefly-$(uname -m)/

find ${firefly_pbi_path}/lib -iname "*.py[co]" -delete
find ${firefly_pbi_path}/lib -iname "*.a" -delete
rm -rf ${firefly_pbi_path}/share/doc
rm -rf ${firefly_pbi_path}/share/emacs
rm -rf ${firefly_pbi_path}/share/examples
rm -rf ${firefly_pbi_path}/share/gettext
