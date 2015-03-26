#!/bin/sh

if [ "${NANO_LABEL}" != "FreeNAS" ]; then
	echo Cannot push-to-download for \"${NANO_LABEL}\" 1>&2
	exit 1
fi

set -e
PUSHIT=9.3
ID=`id -un`

if [ "$ID" = "root" ]; then	
	ID="jkh"
fi

if [ $# -lt 4 ]; then
	echo Usage: $0 stagedir FreeNAS-version TRAIN datestamp
	echo Usage: e.g. $0 stagedir FreeNAS-9.3-BETA 9.3-BETA 20131225
	exit 1
fi

STAGE=$1
VERSION=$2
TRAIN=$3
DATE=$4

TDIR="`echo ${TRAIN}|awk -F- '{print $2 "/" $3}'`"
TARGET=/tank/downloads/$TDIR/$DATE

if [ ! -d ${STAGE}/$VERSION-$DATE ]; then
	echo ${STAGE}/$VERSION-$DATE not found
	exit 2
fi

if [ -z "${TDIR}" ]; then
	echo "Target directory is NULL"
	exit 3
fi

ssh ${ID}@download.freenas.org rm -rf $TARGET
ssh ${ID}@download.freenas.org mkdir -p $TARGET
scp -pr $STAGE/$VERSION-$DATE/* ${ID}@download.freenas.org:$TARGET
if [ "`echo ${TRAIN}|awk -F- '{print $3}'`" != "Nightlies" ]; then
	ssh ${ID}@download.freenas.org "(cd /tank/downloads/${PUSHIT}; rm -f latest; ln -s STABLE/$DATE latest)"
fi
exit 0
