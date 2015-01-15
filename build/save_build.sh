#!/bin/sh

# 
# Script to capture the build
#   This will save a copy of your built image
#   to SAVED_BUILD_ENV_ROOT  (XXX: move to nano_env?)
#
# We do this so developers can analyze crashdumps against
# the shipped image.
#

myname=`basename "$0"`
mydir=`dirname "$0"`

. $mydir/nano_env

if [ -z "$NANO_LABEL" ] ; then
    echo "NANO_LABEL unset, please run this from the top level via:"
    echo "  make save-build-env"
    exit 1
fi

: ${SAVED_BUILD_ENV_ROOT="/freenas/BSD/releng/${NANO_LABEL}/build_env/"}

: ${SAVED_VERSION_NAME=${VERSION}-${BUILD_TIMESTAMP}}

SAVED_BUILD_ENV_DESTDIR="${SAVED_BUILD_ENV_ROOT}/${SAVED_VERSION_NAME}"
if [ -e "${SAVED_BUILD_ENV_DESTDIR}" ] ; then
    rm -rf ${SAVED_BUILD_ENV_DESTDIR}
fi

set -x
set -e
mkdir -p ${SAVED_BUILD_ENV_DESTDIR}
tar -C "$mydir/.." -cf - --exclude "dev" --exclude "*.iso" --exclude "Packages/*.tgz" --exclude "*GUI_Upgrade.txz" . | tar -C "${SAVED_BUILD_ENV_DESTDIR}" --no-same-permissions --no-same-owner -xf -
set +x
echo "Build saved to '$SAVED_BUILD_ENV_DESTDIR'"
exit 0

