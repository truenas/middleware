#!/bin/sh

#
# Build the release for upload.
#

set -x
set -e

mydir=`dirname $0`

for arch in amd64 i386 ; do 
	(
	cd os-base/$arch ;
	for file in \
        FreeNAS-*.GUI_Upgrade.txz \
        FreeNAS-*.8_0_x_LEGACY_GUI_Upgrade.xz \
        FreeNAS-*.iso \
        FreeNAS-*.img.xz ; do
		sha256 $file > $file.sha256.txt
	done
	)
done
