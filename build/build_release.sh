#!/bin/sh

#
# Build the release for upload.
#

set -x
set -e

mydir=`dirname $0`

sh $mydir/do_build.sh -z
sh $mydir/do_build.sh -a
env FREENAS_ARCH=i386 sh $mydir/do_build.sh -z
env FREENAS_ARCH=i386 sh $mydir/do_build.sh -a
sh $mydir/create_release_tarball.sh
