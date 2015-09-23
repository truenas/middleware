#!/bin/sh

if [ $# -lt 3 ]; then
	echo Usage: $0 stagedir TrueNAS-version datestamp
	echo Usage: e.g. $0 stagedir TrueNAS-9.3-BETA 20131225
	exit 1
fi

STAGE=$1
VERSION=$2
DATE=$3

PUSHIT=9.3.1
ID=`id -un`

if [ "$ID" = "root" ]; then	
	ID="jkh"
fi

if [ ! -d ${STAGE}/$VERSION-$DATE ]; then
	echo ${STAGE}/$VERSION-$DATE not found
	exit 2
fi

# For TrueNAS, just copy the ISO and GUI image files to a special location and
# bail out early, otherwise go on to do the more complex FreeNAS stuff.
if [ "${NANO_LABEL}" = "FreeNAS" ]; then
	echo "This download script only works for TrueNAS"
	exit 3
fi

scp -pr $STAGE/$VERSION-$DATE/x64/*.{GUI,iso}* ${ID}@download.freenas.org:/tank/truenas/downloads
