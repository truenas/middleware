#!/bin/sh

#
# Build the release for upload.
#

set -x
set -e

mydir=`dirname $0`

rm -rf FreeBSD os-base release_stage

sh $mydir/do_build.sh -a
env FREENAS_ARCH=i386 sh $mydir/do_build.sh -a
sh $mydir/create_release_tarball.sh
