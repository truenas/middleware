#!/bin/sh
#
# Create a tarball at the top of the tree for easy upload/extract to sourceforge
# directory format.
#

cd "$(dirname "$0")/.."
TOP="$(pwd)"

. build/nano_env
. build/functions.sh
. build/pbi_env

IMG_PREFIX=$NANO_LABEL-$VERSION

PLUGINS="transmission firefly minidlna"

map_x86=i386
map_x64=amd64

TARBALL="$TOP/$IMG_PREFIX-release.tar"
rm -rf release_stage
set -x
set -e
mkdir -p release_stage
for arch in x64 x86 ; do 
	cd ${TOP}/release_stage
	eval mapped_arch=\$map_$arch
	echo $arch = $mapped_arch
	mkdir $arch
	cd $arch
	for ext in img.xz GUI_Upgrade.txz 8_0_x_LEGACY_GUI_Upgrade.xz iso ; do
		ln ${TOP}/os-base/$mapped_arch/${IMG_PREFIX}-${arch}.${ext} .
		ln ${TOP}/os-base/$mapped_arch/${IMG_PREFIX}-${arch}.${ext}.sha256.txt .
	done
	mkdir plugins
	cd plugins
	for plugin in $PLUGINS ; do
		# XXX: wildcard here... is there a way to derive the version of the port?
		ln ${TOP}/$plugin/$mapped_arch/${plugin}-*-${mapped_arch}.pbi .
	done
done
cd ${TOP}
tar -czvf $TARBALL -H release_stage
