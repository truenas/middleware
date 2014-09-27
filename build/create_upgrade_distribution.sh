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
UPDATE_DIR="${TOP}/${OBJ}/${TRAIN}-${SEQUENCE}"
PKG_DIR="${TOP}/${OBJ}/os-base/${mapped_arch}/_.packages"

rm -rf "${UPDATE_DIR}"
set -x
set -e
mkdir -p "${UPDATE_DIR}"



cp "${PKG_DIR}/${NANO_LABEL}-MANIFEST" "${UPDATE_DIR}/${NANO_LABEL}-MANIFEST"
cp -R "${PKG_DIR}/Packages" "${UPDATE_DIR}"

exit 0
