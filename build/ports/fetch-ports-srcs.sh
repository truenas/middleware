#!/bin/sh
#

umask 022
cd "$(dirname "$0")/../.."
TOP="$(pwd)"
. build/nano_env

poudriere -e ${NANO_OBJ}/poudriere/etc ports -c -p p -m git
