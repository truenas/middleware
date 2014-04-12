#!/bin/sh
#

umask 022
cd "$(dirname "$0")/../.."
TOP="$(pwd)"
. build/nano_env

poudriere -e ${NANO_OBJ}/poudriere/etc jail -c -j freebsd:9:x86:64 -v 9.2-RELEASE-p3 -a amd64
