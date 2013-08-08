#!/bin/sh

#
# Build the release for upload.
#

set -x
set -e

mydir=`dirname $0`

rm -rf FreeBSD os-base pbi release_stage
rm -rf FreeNAS-9.1.0-RC1-release.tar
rm -rf firefly/ minidlna/ transmission/


sh $mydir/do_build.sh -Ja
env FREENAS_ARCH=i386 sh $mydir/do_build.sh -Ja
sh $mydir/make_checksums.sh
sh $mydir/create_release_tarball.sh

