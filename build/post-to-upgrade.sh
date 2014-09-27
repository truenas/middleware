#!/bin/sh
#
# Given the output of a build, send the package set
# (FreeNAS-MANIFEST and Packages directory) up to
# an update-server.  Once there, run the "freenas-release"
# script to install it, generate delta packages, and
# keep track of everything.

# It's possible these should be set via getopt.

: ${UPDATE_HOST:=beta-update.freenas.org}
: ${UPDATE_USER:=jkh}
: ${UPDATE_DB:="sqlite:updates.db"}
: ${UPDATE_DEST:=/tank/www/FreeNAS}

prog=$(basename $0)
usage() {
    echo "Usage: ${prog} <update_source>" 1>&2
    exit 1
}

if [ $# -ne 1 ]; then
    usage
fi

SOURCE="$1"
MKREL="/usr/local/bin/freenas-release -D ${UPDATE_DB} --archive ${UPDATE_DEST} add"

set -e
set -x

TEMP_DEST=$(ssh ${UPDATE_USER}@${UPDATE_HOST} mktemp -d /tmp/update-XXXXXXXXX)
scp -r "${SOURCE}/." ${UPDATE_USER}@${UPDATE_HOST}:${TEMP_DEST}
ssh ${UPDATE_USER}@${UPDATE_HOST} "${MKREL} ${TEMP_DEST}"
ssh ${UPDATE_USER}@${UPDATE_HOST} "rm -rf ${TEMP_DEST}"

exit 0
