#!/bin/sh
#
# Create a tarball at the top of the tree for easy upload/extract to sourceforge
# directory format.
#

cd "$(dirname "$0")/.."
TOP="$(pwd)"

. build/nano_env
. build/functions.sh

TARBALL="${TOP}/${NANO_LABEL}-${VERSION}-${BUILD_TIMESTAMP}.tar"
STAGEDIR="${NANO_LABEL}-${VERSION}-${BUILD_TIMESTAMP}"
rm -rf "${TOP}/${STAGEDIR}"
set -x
set -e
mkdir -p "${TOP}/${STAGEDIR}"

arch=x64
mapped_arch=amd64
mkdir -p ${TOP}/${STAGEDIR}/${arch}
for ext in img.xz GUI_Upgrade.txz iso vmdk.xz ; do
	if [ -f ${TOP}/os-base/$mapped_arch/${NANO_NAME%-*}-${arch}.${ext} ]; then
		ln ${TOP}/os-base/$mapped_arch/${NANO_NAME%-*}-${arch}.${ext} ${TOP}/${STAGEDIR}/${arch}
		ln ${TOP}/os-base/$mapped_arch/${NANO_NAME%-*}-${arch}.${ext}.sha256.txt ${TOP}/${STAGEDIR}/${arch}
	fi
done
