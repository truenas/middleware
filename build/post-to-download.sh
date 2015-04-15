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
MILESTONE=M1

if [ ! -d ${STAGE}/$VERSION-$DATE ]; then
	echo ${STAGE}/$VERSION-$DATE not found
	exit 2
fi

BASEDIR=/tank/downloads/10/Nightlies
TARGETDIR=${BASEDIR}/${MILESTONE}/${DATE}

ssh ${ID}@download.freenas.org rm -rf ${TARGETDIR}
ssh ${ID}@download.freenas.org mkdir -p ${TARGETDIR}
scp -pr $STAGE/$VERSION-$DATE/* ${ID}@download.freenas.org:${TARGETDIR}/
exit 0
