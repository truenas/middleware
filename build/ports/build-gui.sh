#!/bin/sh
#

umask 022
. build/nano_env
. build/functions.sh
. build/poudriere-functions.sh
. build/repos.sh
. build/ports/ports_funcs.sh

set -e

NANO_GUI=${NANO_OBJ}/gui
NANO_GUI_DEST=${NANO_OBJ}/gui-dest
NANO_GUI_PLIST=${NANO_GUI_DEST}/gui-plist
NANO_NPM_MODULES=${NANO_GUI}/node_modules
CUSTOM_PLIST=${NANO_GUI}/custom-plist
BOWER=${NANO_NPM_MODULES}/bower/bin/bower
GRUNT=${NANO_NPM_MODULES}/grunt-cli/bin/grunt
NPM=npm

create_plist()
{
	cd ${NANO_GUI_DEST}
	find . -type f | sed 's/^\./\/usr\/local\/www\/gui/g'
	cat ${CUSTOM_PLIST}
}

gplusplus_version()
{
	ls -1 /usr/local/bin/g++?? | head -1
}

apply_npm_quirks()
{
	if [ ! -L /usr/local/bin/g++ ]; then
		ln -s `gplusplus_version` /usr/local/bin/g++
		quirks="$quirks /usr/local/bin/g++"
	fi

	if [ ! -L /usr/local/bin/c++ ]; then
		ln -s `gplusplus_version` /usr/local/bin/c++
		quirks="$quirks /usr/local/bin/c++"
	fi
}

remove_npm_quirks()
{
	if [ -n "${quirks}" ]; then
		rm ${quirks}
	fi
}

if [ -d ${NANO_GUI_DEST} ]; then
	echo "Skipping GUI build. If this is not what you want, type:"
	echo "make clean-ui-package"
	exit 0
fi

# Clean up the staging and deployment directories
mkdir -p ${NANO_GUI} ${NANO_GUI_DEST}
rm -rf ${NANO_GUI}/* ${NANO_GUI_DEST}/*

# Copy over gui src to staging directory
cd ${NANO_GUI}
cp -a ${AVATAR_ROOT}/src/gui/ ${NANO_GUI}

# Symlink g++ because npm modules tend to completely ignore CC
apply_npm_quirks

# Do the deployment
${NPM} install grunt grunt-cli bower
${NPM} install
${BOWER} install --allow-root --config.interactive=false
${GRUNT} deploy --force --dir=${NANO_GUI_DEST}

# Remove g++ symlinks
remove_npm_quirks

# Create package plist
create_plist > ${NANO_GUI_PLIST}
