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
: ${UPDATE_USER:=jkh}
: ${UPDATE_DB:="sqlite:${NANO_LABEL}-updates.db"}
: ${UPDATE_DEST:=/tank/www/${NANO_LABEL}}
: ${FREENAS_KEYFILE:=/dev/null}

SSH=${UPDATE_USER}@${UPDATE_HOST}

prog=$(basename $0)
usage() {
    echo "Usage: ${prog} <update_source>" 1>&2
    exit 1
}

if [ $# -ne 1 ]; then
    usage
fi

SOURCE="$1"
MKREL="/usr/local/bin/freenas-release -P ${NANO_LABEL} -D ${UPDATE_DB} --archive ${UPDATE_DEST} -K ${FREENAS_KEYFILE}"

set -e
set -x

# Copy any release notes and notices
for note in ReleaseNotes ChangeLog NOTICE
do
    test -f ${note} && cp ${note} "${SOURCE}"
done

set -e
TEMP_DEST=$(ssh ${SSH} mktemp -d /tmp/update-${NANO_LABEL}-XXXXXXXXX < /dev/null)
if [ -n "${CHANGELOG}" ]; then
    TEMP_CHANGE=$(ssh ${SSH} mktemp /tmp/changelog-XXXXXX < /dev/null)
else
    TEMP_CHANGE=""
fi

if [ $? -ne 0 -o -z "${TEMP_DEST}" ]; then
    echo Cannot create temporary directory 1>&2
    exit 1
fi
if scp -r "${SOURCE}/." ${SSH}:${TEMP_DEST} < /dev/null; then
    if [ -n "${CHANGELOG}" ]; then
	if [ "${CHANGELOG}" = "-" ]; then
	    echo "Enter changelog, control-d to end"
	fi
	cat ${CHANGELOG} | ssh ${SSH} "cat > ${TEMP_CHANGE}"
	MKREL="${MKREL} -C ${TEMP_CHANGE}"
    fi
    ssh ${SSH} "${MKREL} add ${TEMP_DEST}"
fi
ssh ${SSH} "rm -rf ${TEMP_DEST}" < /dev/null
if [ -n "${TEMP_CHANGE}" ]; then
    ssh ${SSH} "rm -f ${TEMP_CHANGE}" < /dev/null
fi
set +e

exit 0
