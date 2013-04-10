#!/bin/sh

[ "$WMSCRIPTS_DIR" = '' ] && exit 1
DC="\\${WMFS_DEFAULT_STATUS_COLOR:-#ffffff}\\"

while true; do

RAM=`"$WMSCRIPTS_DIR/status/ram.sh" | awk '$1 { print "ram:" $1 "% " }'`
SCREENSAVER=`"$WMSCRIPTS_DIR/status/screensaver.sh" | awk '$1 { print $1 " " }'`
SWAP=`"$WMSCRIPTS_DIR/status/swap.sh" | awk '$1 { print "sw: " $1 "% " }'`
DATE="`date +%y%m%d@%H%M` "
HDD=`"$WMSCRIPTS_DIR/status/hdd.sh" "${1:-d}" | awk '$0 { print "hdd:" $1 "% " }'`
LANG=`"$WMSCRIPTS_DIR/status/lang.sh" | awk '$1 { print $1 " " }'`
LOAD=`"$WMSCRIPTS_DIR/status/load.sh" | awk '$1 { print $1 " " $3 " " $5 " " }'`
MIXER=`"$WMSCRIPTS_DIR/status/mixer.sh" | awk '
BEGIN {
l1=""
l2=""
}

$1 { l1=$1 ":" $2 "% " }
$4 { l2=$4 ":" $5 "% " }

l1 {
print l1 l2
}
'`

echo "${DATE}${MIXER}${LOAD}${HDD}${RAM}${SWAP}${LANG}${SCREENSAVER}"

sleep 1
done