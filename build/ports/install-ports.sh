#!/bin/sh
#

umask 022
cd "$(dirname "$0")/../.."
TOP="$(pwd)"
. build/nano_env
. build/functions.sh
. build/poudriere-functions.sh
. build/repos.sh

cleanup()
{
	umountfs ${NANO_OBJ}/_.w/usr/ports/packages
}

# XX: Uncomment to debug
#TRACE=-x

trap cleanup EXIT

JAIL=$(basename $(realpath ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/j))
PORTS=p
mkdir -p ${NANO_OBJ}/_.w/usr/ports/packages
mount -t nullfs ${NANO_OBJ}/ports/packages/${JAIL}-${PORTS} ${NANO_OBJ}/_.w/usr/ports/packages  || exit 1

build/ports/install-ports-from-list.py --index ${NANO_OBJ}/ports/packages/${JAIL}-${PORTS}/INDEX-${FREEBSD_RELEASE_MAJOR_VERSION}.bz2 \
                                       --packages ${NANO_OBJ}/ports/packages/${JAIL}-${PORTS} \
                                       --chroot ${NANO_OBJ}/_.w \
                                       --ports ${NANO_OBJ}/poudriere/etc/ports.txt

