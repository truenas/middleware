#!/bin/sh

set -e
STAGE=/freenas/Dev/releng/FreeNAS/jkh-nightlies/
PUSHIT=9.3
ID=`id -un`
if [ "$ID" = "root" ]; then	
	ID="jkh"
fi

if [ $# -lt 2 ]; then
	echo Usage: $0 FreeNAS-version datestamp
	echo Usage: e.g. $0 FreeNAS-9.2.1-BETA 20131225
	exit 1
fi
VERSION=$1
DATE=$2

if [ ! -d ${STAGE}/$VERSION-$DATE ]; then
	echo ${STAGE}/$VERSION-$DATE not found
	exit 2
fi

FV=`echo $VERSION|sed -e 's/FreeNAS-\(.*\)-.*/\1/'`
FT=`echo $VERSION|sed -e 's/FreeNAS-.*-\(.*\)/\1/'`

ssh ${ID}@download.freenas.org rm -rf /tank/downloads/nightlies/$FV/$FT/$DATE
ssh ${ID}@download.freenas.org mkdir -p /tank/downloads/nightlies/$FV/$FT/$DATE
scp -pr $STAGE/$VERSION-$DATE/* ${ID}@download.freenas.org:/tank/downloads/nightlies/$FV/$FT/$DATE/
if [ "${FV}" = "${PUSHIT}" ]; then
	ssh ${ID}@download.freenas.org "(cd /tank/downloads; rm -f nightly; ln -s nightlies/$FV/$FT/$DATE nightly)"
fi
exit 0
