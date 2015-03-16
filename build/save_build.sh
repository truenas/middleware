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
: ${SAVED_UPDATE_ROOT="/freenas/BSD/releng/${NANO_LABEL}/updates"}

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

if [ -h "${AVATAR_ROOT}/objs/LATEST" ]; then
    upd=$(realpath "${AVATAR_ROOT}/objs/LATEST")
    upd_name=$(basename "${upd}")
    SAVED_UPDATE_DESTDIR="${SAVED_UPDATE_ROOT}/${upd_name}"

    if [ -e "${SAVED_UPDATE_DESTDIR}/${upd_name}" ]; then
	echo "${upd_name} already exists in update archive, doing nothing" 1>&2
    else
	set -x
	mkdir -p "${SAVED_UPDATE_DESTDIR}"
	tar -C "${AVATAR_ROOT}/objs/${upd_name}" -cf - . | tar -C "${SAVED_UPDATE_DESTDIR}" --no-same-permissions --no-same-owner -xf -
	set +x
	echo "Update saved to ${SAVED_UPDATE_DESTDIR}"
    fi
fi

exit 0

