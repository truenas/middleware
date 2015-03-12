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

rm -f "${LATEST}"
ln -sf "${UPDATE_DIR}" "${LATEST}"

exit 0
