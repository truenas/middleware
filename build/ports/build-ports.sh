#!/bin/sh
#

umask 022
cd "$(dirname "$0")/../.."
TOP="$(pwd)"
. build/nano_env

# XX: Uncomment to debug
#TRACE=-x

mkdir -p ${NANO_OBJ}/poudriere/ports/distfiles
poudriere ${TRACE} -e ${NANO_OBJ}/poudriere/etc bulk -f ${NANO_OBJ}/poudriere/etc/ports.txt -j j -p p
