#!/bin/sh
#
# Create a tarball at the top of the tree for easy upload/extract to sourceforge
# directory format.
#

cd "$(dirname "$0")/.."
TOP="$(pwd)"

. build/nano_env
. build/functions.sh

map_x86=i386
map_x64=amd64

TARBALL="${TOP}/${NANO_LABEL}-${VERSION}-${BUILD_TIMESTAMP}.tar"
STAGEDIR="${NANO_LABEL}-${VERSION}-${BUILD_TIMESTAMP}
rm -rf "${TOP}/${STAGEDIR}"
set -x
set -e
mkdir -p "${TOP}/${STAGEDIR}"
for arch in x64 x86 ; do 
	eval mapped_arch=\$map_$arch
	echo $arch = $mapped_arch
	mkdir -p ${TOP}/${STAGEDIR}/${arch}
	for ext in img.xz GUI_Upgrade.txz iso ; do
		ln ${TOP}/os-base/$mapped_arch/${NANO_NAME%-*}-${arch}.${ext} ${TOP}/${STAGEDIR}/${arch}
		ln ${TOP}/os-base/$mapped_arch/${NANO_NAME%-*}-${arch}.${ext}.sha256.txt ${TOP}/${STAGEDIR}/${arch}
	done
done
tar -czvf $TARBALL -H ${STAGEDIR}
