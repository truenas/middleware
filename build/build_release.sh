#!/bin/sh

#
# Build the release for upload.
#

set -x
set -e

mydir=`dirname $0`

rm -rf FreeBSD os-base pbi release_stage
rm -rf firefly/ minidlna/ transmission/


sh $mydir/do_build.sh -a
env FREENAS_ARCH=i386 sh $mydir/do_build.sh -a
for arch in amd64   i386 ; do 
	(
	cd os-base/$arch ;
	for file in FreeNAS-*.GUI_Upgrade.txz FreeNAS-*.iso FreeNAS-*.img.xz ; do
		sha256 $file > $file.sha256.txt
	done
	)
done

sh $mydir/create_release_tarball.sh
