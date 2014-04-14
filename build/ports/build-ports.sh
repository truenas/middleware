#!/bin/sh
#

umask 022
cd "$(dirname "$0")/../.."
TOP="$(pwd)"
. build/nano_env

mkdir -p ${NANO_OBJ}/poudriere/ports/distfiles
poudriere  -e ${NANO_OBJ}/poudriere/etc bulk -f ${NANO_OBJ}/poudriere/etc/ports.txt -j freebsd:9:${NANO_ARCH} -p p
