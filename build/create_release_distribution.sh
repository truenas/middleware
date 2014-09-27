#!/bin/sh
#
# Create a tarball at the top of the tree for easy upload/extract to sourceforge
# directory format.
#

cd "$(dirname "$0")/.."
TOP="$(pwd)"

. build/nano_env
. build/functions.sh

OBJ=objs

STAGEDIR="${NANO_LABEL}-${VERSION}-${BUILD_TIMESTAMP}"
rm -rf "${TOP}/${OBJ}/${STAGEDIR}"
set -x
set -e
mkdir -p "${TOP}/${OBJ}/${STAGEDIR}"

arch=x64
mapped_arch=amd64
mkdir -p ${TOP}/${OBJ}/${STAGEDIR}/${arch}
for ext in GUI_Upgrade.txz iso; do
	if [ -f ${TOP}/${OBJ}/os-base/$mapped_arch/${NANO_NAME%-*}-${arch}.${ext} ]; then
		ln ${TOP}/${OBJ}/os-base/$mapped_arch/${NANO_NAME%-*}-${arch}.${ext} ${TOP}/${OBJ}/${STAGEDIR}/${arch}
		ln ${TOP}/${OBJ}/os-base/$mapped_arch/${NANO_NAME%-*}-${arch}.${ext}.sha256.txt ${TOP}/${OBJ}/${STAGEDIR}/${arch}
	fi
done
