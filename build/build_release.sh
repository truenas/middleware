#!/bin/sh

#
# Build the release for upload.
#

set -x
set -e

mydir=`dirname $0`

env PACKAGE_PREP_BUILD=1 sh $mydir/do_build.sh
sh $mydir/do_build.sh
sh $mydir/create_release_distribution.sh
