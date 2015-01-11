#!/bin/sh

if [ "${NANO_LABEL}" != "FreeNAS" ]; then
	echo Cannot push-to-download for \"${NANO_LABEL}\" 1>&2
	exit 1
fi

set -e
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

if [ ! -d ${STAGE}/$VERSION-$DATE ]; then
	echo ${STAGE}/$VERSION-$DATE not found
	exit 2
fi

ssh ${ID}@download.freenas.org rm -rf /tank/downloads/nightlies/$TRAIN/$DATE
ssh ${ID}@download.freenas.org mkdir -p /tank/downloads/nightlies/$TRAIN/$DATE
scp -pr $STAGE/$VERSION-$DATE/* ${ID}@download.freenas.org:/tank/downloads/nightlies/$TRAIN/$DATE/
ssh ${ID}@download.freenas.org "(cd /tank/downloads; rm -f nightly; ln -fs nightlies/$TRAIN/$DATE nightly)"
exit 0
