#!/bin/sh
# PBI building script
# This will run after your port build is complete
##############################################################################

minidlna_pbi_path=/usr/pbi/minidlna-$(uname -m)/

rm -rf ${minidlna_pbi_path}/share/doc
rm -rf ${minidlna_pbi_path}/share/emacs
rm -rf ${minidlna_pbi_path}/share/examples
rm -rf ${minidlna_pbi_path}/share/gettext
