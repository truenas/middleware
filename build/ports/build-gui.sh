#!/bin/sh
#

umask 022
. build/nano_env
. build/functions.sh
. build/poudriere-functions.sh
. build/repos.sh
. build/ports/ports_funcs.sh

NANO_GUI=${NANO_OBJ}/gui
NANO_GUI_DEST=${NANO_OBJ}/gui-dest
NANO_GUI_PLIST=${NANO_GUI_DEST}/gui-plist
NANO_NPM_MODULES=${NANO_GUI}/node_modules
BOWER=${NANO_NPM_MODULES}/bower/bin/bower
GRUNT=${NANO_NPM_MODULES}/grunt-cli/bin/grunt
NPM=npm

mkdir -p ${NANO_GUI} && cd ${NANO_GUI}
cp -a ${AVATAR_ROOT}/src/gui/ ${NANO_GUI}
${NPM} install grunt grunt-cli bower
${BOWER} install --allow-root
${GRUNT} deploy --force --dir=${NANO_GUI_DEST}
cd ${NANO_GUI_DEST} && find . -type f | sed 's/^\./\/usr\/local\/www\/gui/g' > ${NANO_GUI_PLIST}
echo '/usr/local/etc/rc.d/gui' >> ${NANO_GUI_PLIST}
