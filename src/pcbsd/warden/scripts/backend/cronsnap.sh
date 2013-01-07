#!/bin/sh
# Prints a listing of the installed jails
######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

# Check if we have any jails
if [ ! -d "${JDIR}" ]
then
  exit 0
fi

cd ${JDIR}

for i in `ls -d .*.meta 2>/dev/null`
do
  if [ ! -e "${i}/cron" ] ; then continue ; fi
  if [ ! -e "${i}/cron-keep" ] ; then continue ; fi

  jIP="`cat ${i}/ip`"
  jHOST="`cat ${i}/host`"
  JAILDIR="${JDIR}/${jHOST}"

  if [ ! -d "${JAILDIR}" ] ; then continue ; fi

  CRONFREQ="`cat ${i}/cron`"
  CRONKEEPDAYS="`cat ${i}/cron-keep`"

  # Figure out if we need to create a new snapshot
  snaps=$(listZFSSnap "${JAILDIR}")
  lastsnap=`echo $snaps | rev | cut -d " " -f 1 | rev`
  needSnap=0
  zdate=`date +%Y%m%d-%H%M%S`
  if [ "$CRONFREQ" = "daily" ] ; then
     #echo "Checking for daily snapshots to ${jHOST}..."
     today=`date +%Y%m%d`
     lastsnap=`echo $lastsnap | cut -d '-' -f 1`
     if [ "$today" != "$lastsnap" ] ; then
        needSnap=1
     fi
  else
  # Hourly
     #echo "Checking for hourly snapshots to ${jHOST}..."
     today=`date +%Y%m%d`
     hour=`date +%H`
     lastday=`echo $lastsnap | cut -d '-' -f 1`
     lasthour=`echo $lastsnap | cut -d '-' -f 2 | cut -c 1-2`
     if [ "$today" != "$lastday" -o "$hour" != "$lasthour" ] ; then
        needSnap=1
     fi
  fi
  if [ "$needSnap" = "1" ] ; then
     mkZFSSnap "${JAILDIR}"
  fi

  # Do any pruning
  num=0
  for snap in `echo $snaps | sort -r`
  do
     cur="`echo $snap | cut -d '-' -f 1`" 
     if [ "$cur" != "$prev" ] ; then
        num=`expr $num + 1`
        prev="$cur"
     fi
     if [ $num -gt $CRONKEEPDAYS ] ; then
        #echo "Pruning old snapshot: $snap"
        rmZFSSnap "${JAILDIR}" "$snap"
     fi
  done
done
