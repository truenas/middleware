#!/bin/sh
#
# Create a directory at the top of the tree
# suitable for the update code.  (Or for the
# various tools to process such.)

cd "$(dirname "$0")/.."
TOP="$(pwd)"

. build/nano_env
. build/functions.sh

OBJ=objs

: ${SEQUENCE:-0}

mapped_arch=amd64
UPDATE_DIR="${TOP}/${OBJ}/${SEQUENCE}-Update"
PKG_DIR="${TOP}/${OBJ}/os-base/${mapped_arch}/_.packages"
LATEST="${TOP}/${OBJ}/LATEST"

set -x
set -e
mkdir -p "${UPDATE_DIR}"

cp "${PKG_DIR}/${NANO_LABEL}-MANIFEST" "${UPDATE_DIR}/${NANO_LABEL}-MANIFEST"
cp -R "${PKG_DIR}/Packages" "${UPDATE_DIR}"

# Copy any release notes and notices
for note in ReleaseNotes ChangeLog NOTICE
do
    test -f ${note} && cp ${note} "${UPDATE_DIR}"
done

# Copy any update scripts, if gien
if [ -n "${DELTA_SCRIPTS}" -a -d "${DELTA_SCRIPTS}" ]; then
    cp -R "${DELTA_SCRIPTS}"/* "${UPDATE_DIR}"/Packages
fi

if [ -e "${TOP}/ValidateUpdate" ]; then
	cp "${TOP}/ValidateUpdate" "${UPDATE_DIR}/ValidateUpdate"
fi
if [ -e "${TOP}/ValidateInstall" ]; then
	cp "${TOP}/ValidateInstall" "${UPDATE_DIR}/ValidateInstall"
fi

if printenv | grep -q "VALIDATE_UPDATE"; then
	if [ "${VALIDATE_UPDATE}" = "/dev/null" -o "${VALIDATE_UPDATE}" = "" ]; then
		rm -f "${UPDATE_DIR}/ValidateUpdate"
	else
		cp "${VALIDATE_UPDATE}" "${UPDATE_DIR}/ValidateUpdate"
	fi
fi

if printenv | grep -q "VALIDATE_INSTALL"; then
	if [ "${VALIDATE_INSTALL}" = "/dev/null" -o "${VALIDATE_INSTALL}" = "" ]; then
		rm -f "${UPDATE_DIR}/ValidateInstall"
	else
		cp "${VALIDATE_INSTALL}" "${UPDATE_DIR}/ValidateInstall"
	fi
fi

# If RESTART is given, save that
if [ -n "${RESTART}" ]; then
    echo ${RESTART} > ${UPDATE_DIR}/RESTART
fi

# And if REBOOT is given, put that in FORCEREBOOT
if [ -n "${REBOOT}" ]; then
    echo ${REBOOT} > ${UPDATE_DIR}/FORCEREBOOT
fi

rm -f "${LATEST}"
ln -sf "${SEQUENCE}-Update" "${LATEST}"

exit 0
