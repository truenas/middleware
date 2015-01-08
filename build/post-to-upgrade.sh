#!/bin/sh
#
# Given the output of a build, send the package set
# (FreeNAS-MANIFEST and Packages directory) up to
# an update-server.  Once there, run the "freenas-release"
# script to install it, generate delta packages, and
# keep track of everything.

# It's possible these should be set via getopt.

: ${NANO_LABEL:=FreeNAS}
: ${UPDATE_HOST:=beta-update.freenas.org}
: ${UPDATE_USER:=sef}
: ${UPDATE_DB:="sqlite:${NANO_LABEL}-updates.db"}
: ${UPDATE_DEST:=/tank/www/${NANO_LABEL}}

prog=$(basename $0)
usage() {
    echo "Usage: ${prog} <update_source>" 1>&2
    exit 1
}

if [ $# -ne 1 ]; then
    usage
fi

SOURCE="$1"
MKREL="/usr/local/bin/freenas-release -P ${NANO_LABEL} -D ${UPDATE_DB} --archive ${UPDATE_DEST} add"

set -e
set -x

# Copy any release notes and notices
for note in ReleaseNotes ChangeLog NOTICE
do
    test -f ${note} && cp ${note} "${SOURCE}"
done

set -e
TEMP_DEST=$(ssh ${UPDATE_USER}@${UPDATE_HOST} mktemp -d /tmp/update-${NANO_LABEL}-XXXXXXXXX)
if [ $? -ne 0 -o -z "${TEMP_DEST}" ]; then
    echo Cannot create temporary directory 1>&2
    exit 1
fi
scp -r "${SOURCE}/." ${UPDATE_USER}@${UPDATE_HOST}:${TEMP_DEST} && \
    ssh ${UPDATE_USER}@${UPDATE_HOST} "${MKREL} ${TEMP_DEST}"
ssh ${UPDATE_USER}@${UPDATE_HOST} "rm -rf ${TEMP_DEST}"

set +e

exit 0
