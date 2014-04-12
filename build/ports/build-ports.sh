#!/bin/sh
#

umask 022
cd "$(dirname "$0")/../.."
TOP="$(pwd)"
. build/nano_env

poudriere  -e ${NANO_OBJ}/poudriere/etc bulk -f ${NANO_OBJ}/poudriere/etc/ports.txt -j freebsd:9:x86:64 -p p
