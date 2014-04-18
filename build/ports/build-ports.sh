#!/bin/sh
#

umask 022
cd "$(dirname "$0")/../.."
TOP="$(pwd)"
. build/nano_env
. build/functions.sh
. build/repos.sh

cleanup()
{
	umountfs ${NANO_OBJ}/_.w/usr/src
}

# XX: Uncomment to debug
#TRACE=-x

trap cleanup EXIT

mount -t nullfs ${GIT_FREEBSD_CHECKOUT_PATH} ${NANO_OBJ}/_.w/usr/src  || exit 1

mkdir -p ${NANO_OBJ}/ports/distfiles
poudriere ${TRACE} -e ${NANO_OBJ}/poudriere/etc bulk -f ${NANO_OBJ}/poudriere/etc/ports.txt -j j -p p
