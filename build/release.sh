#!/bin/sh

if [ ! -d build ]; then
	echo "You are not in a FreeNAS checkout directory.  You suck."
	exit 1
fi

if [ $# -lt 1 ]; then
	echo Usage: $0 FreeNAS\|TrueNAS [PRODUCTION]
	exit 2
fi

N=$1
shift

if [ $N != "FreeNAS" -a $N != "TrueNAS" ]; then
	echo Usage: $0 FreeNAS\|TrueNAS
	exit 3
fi

make-changelog() {
       local yesterday
       rm -f ChangeLog
       yesterday=$(expr $(date +%s) - \( 24 \* 3600 \))
       yesterday=$(date -r ${yesterday} +%Y/%m/%d)
       git log --oneline --since ${yesterday} > /tmp/changes.$$
       if [ -s /tmp/changes.$$ ]; then
               cp /tmp/changes.$$ ChangeLog
       fi
       rm -f /tmp/changes.$$
}

PRODUCTION=no
if [ $# -gt 0 -a "$1" != "no" ]; then
	PRODUCTION=yes
fi

_N=`make -V NANO_LABEL`
if [ $_N != $N -a "${PRODUCTION}" = "yes" ]; then
	echo "Working directory $_N != stated version $N"
	exit 4
fi

if [ -z "${TRAIN}" ]; then
	TRAIN=`make -V TRAIN`
fi

if [ "${UPDATE_UNDO}" = "yes" ]; then
	TARGET=update-undo
else
	TARGET=release-push
fi

echo "Building $N, PRODUCTION=$PRODUCTION, TRAIN=${TRAIN}, $TARGET"

git pull --no-rebase
if [ "${PRODUCTION}" = "no" -a ! -f ChangeLog ]; then
	make-changelog
fi
env NANO_LABEL=$N TRAIN=${TRAIN} make checkout
env NANO_LABEL=$N TRAIN=${TRAIN} make ${TARGET} PRODUCTION=${PRODUCTION}
